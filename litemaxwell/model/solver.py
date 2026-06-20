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
                        n_pole=10, rotor_angle_deg=0.0) -> Field:
    """Run the FEM solve.  Returns a Field (Az, B per element).

    rotor_angle_deg rotates the magnet pole pattern around the ring (used by
    the torque sweep so the mesh is built only once)."""
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
    for i, s in enumerate(shapes):
        mat = materials.get(s.material)
        if mat:
            mur_s[i] = mat.mu_r if mat.mu_r > 0 else 1.0
            ismag_s[i] = bool(getattr(mat, "is_magnet", False))
            br_s[i] = mat.br
    tag = np.asarray(mesh.tri_shape, int)
    valid = tag >= 0
    mur = np.where(valid, mur_s[np.clip(tag, 0, ns - 1)], 1.0)
    nu = 1.0 / (MU0 * mur)                            # (M,)

    # --- stiffness assembly (vectorised COO) --------------------------
    fac = nu / (4.0 * A)                              # (M,)
    ke = fac[:, None, None] * (bx[:, :, None] * bx[:, None, :]
                               + cx[:, :, None] * cx[:, None, :])   # (M,3,3)
    ri = np.repeat(tris, 3, axis=1).reshape(M, 3, 3)
    ci = np.tile(tris, 3).reshape(M, 3, 3)
    K = sp.coo_matrix((ke.ravel(), (ri.ravel(), ci.ravel())),
                      shape=(N, N)).tocsr()

    rhs = np.zeros(N)
    cents = P.mean(axis=1)                            # (M,2) metres
    # coil currents
    if excitations:
        Jz = np.zeros(M)
        cur = _current_density(shapes, excitations)
        idx = {s.name: i for i, s in enumerate(shapes)}
        sidx_to_J = {idx[n]: j for n, j in cur.items() if n in idx}
        for e_si, j in sidx_to_J.items():
            Jz[tag == e_si] = j
        np.add.at(rhs, tris, (Jz * A / 3.0)[:, None])
    # permanent magnets — radial Br, polarity alternating by pole
    ismag = np.where(valid, ismag_s[np.clip(tag, 0, ns - 1)], False)
    if ismag.any():
        br = np.where(valid, br_s[np.clip(tag, 0, ns - 1)], 0.0)
        r = np.hypot(cents[:, 0], cents[:, 1])
        rot = math.radians(rotor_angle_deg)
        ang = np.mod(np.arctan2(cents[:, 1], cents[:, 0]) - rot, 2 * np.pi)
        pole = (ang / (2 * np.pi / max(n_pole, 1))).astype(int)
        pol = np.where(pole % 2 == 0, 1.0, -1.0)
        safe = (r > 1e-9) & ismag
        Brx = np.where(safe, pol * br * cents[:, 0] / np.where(r > 0, r, 1), 0.0)
        Bry = np.where(safe, pol * br * cents[:, 1] / np.where(r > 0, r, 1), 0.0)
        term = (nu / 2.0)[:, None] * (Brx[:, None] * cx - Bry[:, None] * bx)
        np.add.at(rhs, tris, term)

    # --- Dirichlet Az=0 on the outer boundary, solve -----------------
    bnd = _boundary_nodes(tris)
    free = np.ones(N, bool)
    if bnd:
        free[np.fromiter(bnd, int)] = False
    fidx = np.where(free)[0]
    Az = np.zeros(N)
    if len(fidx):
        Az[fidx] = spla.spsolve(K[fidx][:, fidx].tocsc(), rhs[fidx])

    # --- B per element (vectorised) ----------------------------------
    az = Az[tris]                                     # (M,3)
    Bx = (az * cx).sum(axis=1) / twoA
    By = -(az * bx).sum(axis=1) / twoA
    B = np.stack([Bx, By], axis=1)
    Bmag = np.hypot(Bx, By)
    return Field(nodes_mm, tris, Az, B, Bmag)


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
