"""2D magnetostatic finite-element solver (linear, A-formulation).

Solves  ∇·(ν ∇Az) = -Jz - (curl of magnetisation)  on the triangular mesh,
with Az = 0 on the outer boundary.  Then B = (∂Az/∂y, -∂Az/∂x) per element.

Sources:
  - permanent magnets: radial magnetisation, polarity alternating by pole
  - coil currents: uniform Jz over the coil region (from Current excitations)

This is the engine behind "Analyze" + the B field overlay.  Linear materials
(uses each material's μr); good enough for a faithful flux-density picture.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

MU0 = 4e-7 * math.pi


@dataclass
class Field:
    nodes: np.ndarray          # (N,2)
    triangles: np.ndarray      # (M,3)
    Az: np.ndarray             # (N,) nodal vector potential
    B: np.ndarray              # (M,2) per-element flux density
    Bmag: np.ndarray           # (M,) |B| per element
    iters: int = 1             # nonlinear iterations taken (1 = linear solve)

    @property
    def bmax(self) -> float:
        return float(self.Bmag.max()) if len(self.Bmag) else 0.0


def _tri_grads(p0, p1, p2):
    """Linear-triangle b,c coefficients and area (2A)."""
    b = np.array([p1[1] - p2[1], p2[1] - p0[1], p0[1] - p1[1]])
    c = np.array([p2[0] - p1[0], p0[0] - p2[0], p1[0] - p0[0]])
    twoA = (p1[0] - p0[0]) * (p2[1] - p0[1]) - (p2[0] - p0[0]) * (p1[1] - p0[1])
    return b, c, twoA


def solve_magnetostatic(mesh, shapes, materials, excitations=None,
                        n_pole=10, rotor_angle_deg=0.0, coil_currents=None,
                        nonlinear=False, max_nl_iter=40, nl_tol=2e-3,
                        nl_relax=0.3) -> Field:
    """Run the FEM solve.  Returns a Field (Az, B per element).

    rotor_angle_deg rotates the magnet pole pattern around the ring (used by
    the torque/EMF sweeps so the mesh is built only once).
    coil_currents : optional {shape_index: amp-turns} injected as Jz over that
        coil region — this is how the load-torque sweep drives the windings.
    nonlinear : if True, fixed-point iterate each steel element's reluctivity
        nu from its B-H curve until max|dB| < nl_tol (models saturation)."""
    nodes_mm = np.asarray(mesh.nodes, float)       # for rendering (scene = mm)
    nodes = nodes_mm * 1e-3                         # SI metres for the FEM
    tris = np.asarray(mesh.triangles, int)
    N = len(nodes); M = len(tris)
    if M == 0:
        raise ValueError("메시가 없습니다. 먼저 Generate Mesh.")

    # --- per-triangle geometry (vectorised) ---------------------------
    P = nodes[tris]                                  # (M,3,2)
    p0, p1, p2 = P[:, 0], P[:, 1], P[:, 2]
    bx = np.stack([p1[:, 1] - p2[:, 1], p2[:, 1] - p0[:, 1],
                   p0[:, 1] - p1[:, 1]], axis=1)      # b_i  (M,3)
    cx = np.stack([p2[:, 0] - p1[:, 0], p0[:, 0] - p2[:, 0],
                   p1[:, 0] - p0[:, 0]], axis=1)      # c_i  (M,3)
    twoA = ((p1[:, 0] - p0[:, 0]) * (p2[:, 1] - p0[:, 1])
            - (p2[:, 0] - p0[:, 0]) * (p1[:, 1] - p0[:, 1]))
    A = 0.5 * np.abs(twoA)
    A = np.where(A < 1e-15, 1e-15, A)

    # --- per-triangle material props ----------------------------------
    ns = len(shapes)
    mur_s = np.ones(ns); ismag_s = np.zeros(ns, bool); br_s = np.zeros(ns)
    bh_s = [None] * ns
    for i, s in enumerate(shapes):
        mat = materials.get(s.material)
        if mat:
            mur_s[i] = mat.mu_r if mat.mu_r > 0 else 1.0
            ismag_s[i] = bool(getattr(mat, "is_magnet", False))
            br_s[i] = mat.br
            if (getattr(mat, "nonlinear", False)
                    and not getattr(mat, "is_magnet", False)):
                bh_s[i] = mat.bh
    tag = np.asarray(mesh.tri_shape, int)
    valid = tag >= 0
    cl = np.clip(tag, 0, ns - 1)
    mur0 = np.where(valid, mur_s[cl], 1.0)

    cents = P.mean(axis=1)                            # (M,2) metres

    # --- permanent-magnet source geometry (radial Br, alternating pole) ---
    ismag = np.where(valid, ismag_s[cl], False)
    Brx = Bry = None
    if ismag.any():
        br = np.where(valid, br_s[cl], 0.0)
        r = np.hypot(cents[:, 0], cents[:, 1])
        rot = math.radians(rotor_angle_deg)
        ang = np.mod(np.arctan2(cents[:, 1], cents[:, 0]) - rot, 2 * np.pi)
        pole = (ang / (2 * np.pi / max(n_pole, 1))).astype(int)
        pol = np.where(pole % 2 == 0, 1.0, -1.0)
        safe = (r > 1e-9) & ismag
        Brx = np.where(safe, pol * br * cents[:, 0] / np.where(r > 0, r, 1), 0.0)
        Bry = np.where(safe, pol * br * cents[:, 1] / np.where(r > 0, r, 1), 0.0)

    # --- coil current density Jz [A/m^2]: excitations + explicit currents ---
    Jz = np.zeros(M)
    idx = {s.name: i for i, s in enumerate(shapes)}
    if excitations:
        for nm, j in _current_density(shapes, excitations).items():
            if nm in idx:
                Jz[tag == idx[nm]] = j
    if coil_currents:
        for si, amp_turns in coil_currents.items():
            area_m2 = max(shapes[si].area, 1e-9) * 1e-6
            Jz[tag == si] = amp_turns / area_m2

    # --- boundary (Az=0 on outer edge) --------------------------------
    bnd = _boundary_nodes(tris)
    free = np.ones(N, bool)
    if bnd:
        free[np.fromiter(bnd, int)] = False
    fidx = np.where(free)[0]
    ri = np.repeat(tris, 3, axis=1).reshape(M, 3, 3)
    ci = np.tile(tris, 3).reshape(M, 3, 3)

    def _solve(nu):
        fac = nu / (4.0 * A)
        ke = fac[:, None, None] * (bx[:, :, None] * bx[:, None, :]
                                   + cx[:, :, None] * cx[:, None, :])
        K = sp.coo_matrix((ke.ravel(), (ri.ravel(), ci.ravel()),),
                          shape=(N, N)).tocsr()
        rhs = np.zeros(N)
        if Jz.any():
            np.add.at(rhs, tris, (Jz * A / 3.0)[:, None])
        if Brx is not None:                          # magnet term scales with nu
            term = (nu / 2.0)[:, None] * (Brx[:, None] * cx - Bry[:, None] * bx)
            np.add.at(rhs, tris, term)
        Az = np.zeros(N)
        if len(fidx):
            Az[fidx] = spla.spsolve(K[fidx][:, fidx].tocsc(), rhs[fidx])
        return Az

    def _bfield(Az):
        az = Az[tris]
        Bx = (az * cx).sum(axis=1) / twoA
        By = -(az * bx).sum(axis=1) / twoA
        return Bx, By, np.hypot(Bx, By)

    nu = 1.0 / (MU0 * mur0)
    Az = _solve(nu)
    Bx, By, Bmag = _bfield(Az)
    iters = 1

    nl_idx = [i for i in range(ns) if bh_s[i] is not None]
    if nonlinear and nl_idx:
        relax = nl_relax
        for it in range(max_nl_iter):
            mur_new = mur0.copy()
            for i in nl_idx:
                m = valid & (tag == i)
                if not m.any():
                    continue
                b = Bmag[m]
                h = np.interp(b, bh_s[i].B, bh_s[i].H)   # A/m at this |B|
                mur_new[m] = np.where(h > 1e-9, b / (MU0 * h), mur0[m])
            mur_new = np.clip(mur_new, 1.0, None)
            nu = (1.0 - relax) * nu + relax / (MU0 * mur_new)
            Az = _solve(nu)
            Bx, By, Bmag_new = _bfield(Az)
            # RMS change (robust: a few knee elements can jitter forever while
            # the bulk solution is already converged — max|dB| never settles).
            dB = float(np.sqrt(np.mean((Bmag_new - Bmag) ** 2)))
            Bmag = Bmag_new
            iters = it + 2
            if dB < nl_tol:
                break

    B = np.stack([Bx, By], axis=1)
    return Field(nodes_mm, tris, Az, B, Bmag, iters=int(iters))


def torque_stress(field, r_gap_mm, L_stk_m, dr_mm=1.2):
    """Torque on the rotor via the Maxwell stress tensor over a gap annulus.
    T = (L/μ0) * (1/2dr) * Σ r·Br·Bθ·A_elem  [N·m]."""
    nodes = field.nodes                              # mm
    tris = field.triangles
    P = nodes[tris] * 1e-3                            # m
    cm = P.mean(axis=1)
    r = np.hypot(cm[:, 0], cm[:, 1])
    twoA = ((P[:, 1, 0] - P[:, 0, 0]) * (P[:, 2, 1] - P[:, 0, 1])
            - (P[:, 2, 0] - P[:, 0, 0]) * (P[:, 1, 1] - P[:, 0, 1]))
    Ael = 0.5 * np.abs(twoA)
    dr = dr_mm * 1e-3; rg = r_gap_mm * 1e-3
    band = np.abs(r - rg) < dr
    if not band.any():
        return 0.0
    rs = np.where(r > 0, r, 1.0)
    rhx, rhy = cm[:, 0] / rs, cm[:, 1] / rs
    Br = field.B[:, 0] * rhx + field.B[:, 1] * rhy
    Bth = -field.B[:, 0] * rhy + field.B[:, 1] * rhx
    contrib = r * Br * Bth * Ael
    return float(L_stk_m / MU0 / (2 * dr) * contrib[band].sum())


def rotor_sweep(shapes, materials, n_pole=10, n_steps=19, span_deg=None,
                L_stk_m=0.028, r_gap_mm=25.0, mesh_area=6.0, progress=None):
    """Torque vs rotor position.  The mesh is built ONCE (coarse) and the magnet
    pole pattern is rotated in the solver — fast, no per-step re-meshing.
    Returns (angles_deg, torques[N·m])."""
    from .mesh import generate
    if span_deg is None:
        span_deg = 360.0 / max(n_pole, 1)            # one pole pitch (mech)
    mesh = generate(shapes, max_area=mesh_area)
    angles = np.linspace(0.0, span_deg, n_steps)
    torques = np.zeros(n_steps)
    for i, th in enumerate(angles):
        f = solve_magnetostatic(mesh, shapes, materials, None,
                                n_pole=n_pole, rotor_angle_deg=th)
        torques[i] = torque_stress(f, r_gap_mm, L_stk_m)
        if progress:
            progress(i + 1, n_steps)
    return angles, torques


_PHASE_AXIS = {"A": 0.0, "B": 120.0, "C": 240.0}      # electrical axis [deg]


def phase_map(shapes, n_pole=10):
    """Fundamental winding-function model for the 'Winding*' coils.

    A coil at mechanical angle θ sits at electrical angle αe = θ·(p/2); it
    couples to phase k with weight cos(αe − axis_k) (axes A=0°, B=120°, C=240°).
    Returns {phase: [(shape_idx, weight)]}.  Using the cosine projection instead
    of a hard ±1 phase belt makes the 3-phase set balanced by construction and
    immune to the boundary-binning self-cancellation a discrete belt suffers for
    fractional slot/pole counts.  Same weights drive both flux linkage and the
    injected MMF, so back-EMF and load torque stay mutually consistent."""
    pp = max(n_pole / 2.0, 1.0)
    out = {"A": [], "B": [], "C": []}
    for i, s in enumerate(shapes):
        if not s.name.startswith("Winding"):
            continue
        c = s.geom.centroid
        alpha = math.degrees(math.atan2(c.y, c.x)) * pp
        for ph, axis in _PHASE_AXIS.items():
            out[ph].append((i, math.cos(math.radians(alpha - axis))))
    return out


def _coil_mean_Az(Az, mesh):
    """Area-weighted mean Az [Wb/m] per shape index -> dict{idx: meanAz}."""
    tris = np.asarray(mesh.triangles, int)
    nodes = np.asarray(mesh.nodes, float) * 1e-3
    P = nodes[tris]
    twoA = ((P[:, 1, 0] - P[:, 0, 0]) * (P[:, 2, 1] - P[:, 0, 1])
            - (P[:, 2, 0] - P[:, 0, 0]) * (P[:, 1, 1] - P[:, 0, 1]))
    Ael = 0.5 * np.abs(twoA)
    az_tri = Az[tris].mean(axis=1)
    tag = np.asarray(mesh.tri_shape, int)
    out = {}
    for si in np.unique(tag[tag >= 0]):
        m = tag == si
        a = Ael[m].sum()
        if a > 0:
            out[int(si)] = float((az_tri[m] * Ael[m]).sum() / a)
    return out


def flux_linkage(Az, mesh, pmap, L_stk_m, turns):
    """Per-phase PM flux linkage λ [Wb]:  λ = N·L·Σ_coils w·meanAz, where
    meanAz = (1/S)∫∫_coil Az dS and w is the coil's winding-function weight."""
    mean_az = _coil_mean_Az(Az, mesh)
    out = {}
    for ph, coils in pmap.items():
        out[ph] = turns * L_stk_m * sum(w * mean_az.get(si, 0.0)
                                        for si, w in coils)
    return out


def backemf_sweep(shapes, materials, n_pole=10, n_steps=37, L_stk_m=0.028,
                  turns=14, base_rpm=3000.0, mesh_area=10.0, progress=None,
                  mesh=None):
    """No-load back-EMF: sweep the rotor over one electrical period, track each
    phase's PM flux linkage λ(θ), then e = -dλ/dt = -(dλ/dθ_mech)·ω_mech.

    Pass a prebuilt `mesh` to reuse it across sweeps (avoids re-meshing).
    Returns (angles_deg, emf{A,B,C}[V], lam{A,B,C}[Wb])."""
    from .mesh import generate
    pmap = phase_map(shapes, n_pole)
    if mesh is None:
        mesh = generate(shapes, max_area=mesh_area)
    span = 720.0 / max(n_pole, 1)                     # one elec period in mech deg
    angles = np.linspace(0.0, span, n_steps)
    lam = {"A": np.zeros(n_steps), "B": np.zeros(n_steps), "C": np.zeros(n_steps)}
    for i, th in enumerate(angles):
        f = solve_magnetostatic(mesh, shapes, materials, None,
                                n_pole=n_pole, rotor_angle_deg=th)
        lk = flux_linkage(f.Az, mesh, pmap, L_stk_m, turns)
        for ph in lam:
            lam[ph][i] = lk[ph]
        if progress:
            progress(i + 1, n_steps)
    wm = base_rpm * 2 * math.pi / 60.0                # mechanical rad/s
    th_rad = np.radians(angles)
    emf = {ph: -np.gradient(lam[ph], th_rad) * wm for ph in lam}
    return angles, emf, lam


def load_torque_sweep(shapes, materials, n_pole=10, n_steps=19, L_stk_m=0.028,
                      r_gap_mm=25.0, turns=14, i_peak=11.6, gamma_deg=0.0,
                      base_rpm=3000.0, mesh_area=12.0, progress=None, mesh=None):
    """Torque under balanced 3-phase current synchronised to the rotor.

    At rotor mech angle θ, electrical angle θe = (n_pole/2)·θ + gamma; phase
    currents i_a=I·cos(θe), i_b=I·cos(θe−120°), i_c=I·cos(θe+120°).  Each coil's
    injected amp-turns is N·Σ_ph i_ph·w_ph (same winding weights as the EMF).
    Pass a prebuilt `mesh` to reuse it across gamma/current sweeps.
    Returns (angles_deg, torque[N·m]); the mean is the load torque, the spread
    is torque ripple."""
    from .mesh import generate
    pmap = phase_map(shapes, n_pole)
    if mesh is None:
        mesh = generate(shapes, max_area=mesh_area)
    span = 720.0 / max(n_pole, 1)
    angles = np.linspace(0.0, span, n_steps)
    tq = np.zeros(n_steps)
    pp = n_pole / 2.0
    for i, th in enumerate(angles):
        th_e = math.radians(pp * th + gamma_deg)
        iabc = {"A": i_peak * math.cos(th_e),
                "B": i_peak * math.cos(th_e - 2 * math.pi / 3),
                "C": i_peak * math.cos(th_e + 2 * math.pi / 3)}
        coil_currents = {}
        for ph, coils in pmap.items():
            for si, w in coils:
                coil_currents[si] = coil_currents.get(si, 0.0) + turns * w * iabc[ph]
        f = solve_magnetostatic(mesh, shapes, materials, None, n_pole=n_pole,
                                rotor_angle_deg=th, coil_currents=coil_currents)
        tq[i] = torque_stress(f, r_gap_mm, L_stk_m)
        if progress:
            progress(i + 1, n_steps)
    return angles, tq


def electrical_freq(base_rpm, n_pole):
    """Electrical frequency [Hz] = mechanical rev/s × pole pairs."""
    return base_rpm / 60.0 * (n_pole / 2.0)


def transient_emf(shapes, materials, n_pole=10, base_rpm=3000.0, turns=14,
                  L_stk_m=0.028, n_cycles=2, n_steps=37, mesh_area=12.0, mesh=None):
    """No-load back-EMF as a TIME-domain waveform (constant-speed quasi-static
    transient): the one-electrical-period position sweep is mapped to time
    t = θ_mech/(360·rev_per_s) and tiled over n_cycles, matching the Maxwell
    transient 'Time=' plots.  Returns (t_ms, emf{A,B,C}[V], period_s)."""
    ang, emf, _ = backemf_sweep(shapes, materials, n_pole=n_pole, n_steps=n_steps,
                                L_stk_m=L_stk_m, turns=turns, base_rpm=base_rpm,
                                mesh_area=mesh_area, mesh=mesh)
    period_s = 120.0 / (n_pole * base_rpm)          # one electrical period [s]
    t1 = ang / ang[-1] * period_s
    t = []; e = {p: [] for p in "ABC"}
    for c in range(max(1, int(n_cycles))):
        t.extend((t1[:-1] + c * period_s).tolist())
        for p in "ABC":
            e[p].extend(emf[p][:-1].tolist())
    t.append(int(max(1, n_cycles)) * period_s)
    for p in "ABC":
        e[p].append(emf[p][0])
    return np.asarray(t) * 1e3, {p: np.asarray(e[p]) for p in "ABC"}, period_s


def _steinmetz(Bpeak, mesh, shapes, materials, freq_hz, L_stk_m):
    """Bertotti/Steinmetz iron loss [W] from a per-element peak |B| array.
    P_v = Kh·f·Bm² + Kc·(f·Bm)² + Ke·(f·Bm)^1.5  [W/m³], integrated over the
    steel volume (element area × stack length).  Returns {total,hyst,eddy,excess}."""
    tris = np.asarray(mesh.triangles, int)
    P = np.asarray(mesh.nodes, float)[tris] * 1e-3
    twoA = ((P[:, 1, 0] - P[:, 0, 0]) * (P[:, 2, 1] - P[:, 0, 1])
            - (P[:, 2, 0] - P[:, 0, 0]) * (P[:, 1, 1] - P[:, 0, 1]))
    vol = 0.5 * np.abs(twoA) * L_stk_m                 # m³ per element
    ns = len(shapes)
    kh = np.zeros(ns); kc = np.zeros(ns); ke = np.zeros(ns); steel = np.zeros(ns, bool)
    for i, s in enumerate(shapes):
        mat = materials.get(s.material)
        if mat and not getattr(mat, "is_magnet", False):
            kh[i], kc[i], ke[i] = mat.kh, mat.kc, mat.ke
            steel[i] = (mat.kh > 0 or mat.kc > 0 or mat.ke > 0)
    tag = np.asarray(mesh.tri_shape, int)
    cl = np.clip(tag, 0, ns - 1)
    m = (tag >= 0) & steel[cl]
    f = float(freq_hz)
    Bm = np.asarray(Bpeak, float)
    fB = f * Bm
    ph = (kh[cl] * f * Bm ** 2 * vol)[m].sum()
    pe = (kc[cl] * fB ** 2 * vol)[m].sum()
    px = (ke[cl] * fB ** 1.5 * vol)[m].sum()
    return {"total": float(ph + pe + px), "hyst": float(ph),
            "eddy": float(pe), "excess": float(px)}


def core_loss(field, mesh, shapes, materials, freq_hz, L_stk_m):
    """Iron loss [W] from a single solved field (uses that snapshot's |B|)."""
    return _steinmetz(field.Bmag, mesh, shapes, materials, freq_hz, L_stk_m)


def core_loss_sweep(shapes, materials, freq_hz, n_pole=10, L_stk_m=0.028,
                    n_steps=13, mesh_area=12.0, mesh=None):
    """Iron loss [W] using the PEAK |B| each element reaches over one electrical
    period (rotor swept, magnets-only) — the physically correct B_m for Steinmetz."""
    from .mesh import generate
    if mesh is None:
        mesh = generate(shapes, max_area=mesh_area)
    span = 720.0 / max(n_pole, 1)
    Bpeak = None
    for th in np.linspace(0.0, span, n_steps):
        f = solve_magnetostatic(mesh, shapes, materials, None,
                                n_pole=n_pole, rotor_angle_deg=th)
        Bpeak = f.Bmag if Bpeak is None else np.maximum(Bpeak, f.Bmag)
    return _steinmetz(Bpeak, mesh, shapes, materials, freq_hz, L_stk_m)


def _current_density(shapes, excitations):
    """Map coil shape name -> uniform current density Jz [A/mm^2 -> A/m^2]."""
    area = {s.name: max(s.area, 1e-9) for s in shapes}
    out = {}
    for ex in excitations or []:
        if ex.get("type") != "Current":
            continue
        for nm in ex.get("shapes", []):
            if nm in area:
                # value [A] over the coil area (mm^2) -> A/m^2
                out[nm] = ex["value"] / (area[nm] * 1e-6)
    return out


def _boundary_nodes(tris):
    from collections import defaultdict
    edge = defaultdict(int)
    for a, b, c in tris:
        for u, v in ((a, b), (b, c), (c, a)):
            edge[(min(u, v), max(u, v))] += 1
    bnd = set()
    for (u, v), n in edge.items():
        if n == 1:
            bnd.add(u); bnd.add(v)
    return bnd
