"""Air-gap BAND LAYER for robust sliding-band rotor motion.

The fragile route (litemaxwell.model.solver.backemf_sweep_moving) re-triangulates
the WHOLE cross-section at every rotor angle, which makes Triangle hard-crash at
some angles. The robust, standard motor-FE technique implemented here instead:

  * meshes the ROTOR side (everything inside radius r_rb) ONCE,
  * meshes the STATOR side (everything outside r_sb) ONCE,
  * and at each rotor angle only RIGIDLY ROTATES the rotor sub-mesh and
    re-stitches the thin air-gap annulus (r_rb -> r_sb) between the two clean
    node rings.

That band annulus sits between two convex circles of well-spaced nodes, so it
triangulates trivially at ANY angle — no acute features, no segfault. The rotor
topology never changes; only ~2*N_band band triangles are rebuilt per step.
"""
from __future__ import annotations

import numpy as np
from shapely.geometry import Point
from shapely.ops import unary_union

from .geometry import Shape
from .mesh import Mesh, generate

ROTOR_NAMES = ("Rotor", "Shaft")


def _is_rotor(name):
    return name in ROTOR_NAMES or name.startswith("Magnet")


def build_split(shapes, r_rb=27.0, r_sb=27.1, r_region=43.15):
    """Split a full motor `shapes` list into (rotor_shapes, stator_shapes), each
    carrying a vacuum gap-filler so its band-side boundary is a clean circle:
      rotor side  -> everything inside r_rb  (+ RotorGap vacuum out to r_rb)
      stator side -> everything outside r_sb (+ StatorGap vacuum in to r_sb)."""
    rotor = [s for s in shapes if _is_rotor(s.name)]
    stator = [s for s in shapes if not _is_rotor(s.name) and s.name != "Region"]

    rotor_solid = unary_union([s.geom for s in rotor])
    rotor_gap = Point(0, 0).buffer(r_rb, quad_segs=192).difference(rotor_solid)
    rotor = rotor + [Shape("RotorGap", rotor_gap, material="vacuum",
                           color="#eef1f4")]

    stator_solid = unary_union([s.geom for s in stator])
    stator_ann = (Point(0, 0).buffer(r_region, quad_segs=192)
                  .difference(Point(0, 0).buffer(r_sb, quad_segs=192)))
    stator_gap = stator_ann.difference(stator_solid)
    stator = stator + [Shape("StatorGap", stator_gap, material="vacuum",
                             color="#eef1f4")]
    return rotor, stator


def _band_ring(nodes, r, tol=0.02):
    """Indices of mesh nodes lying on the circle of radius r, sorted by angle."""
    rad = np.hypot(nodes[:, 0], nodes[:, 1])
    idx = np.where(np.abs(rad - r) < tol)[0]
    ang = np.arctan2(nodes[idx, 1], nodes[idx, 0])
    return idx[np.argsort(ang)]


def _stitch(inner_xy, outer_xy):
    """Triangulate the gap annulus between an inner ring (inner_xy, radius r_rb)
    and an outer ring (outer_xy, radius r_sb), both sorted by angle. Returns
    triangles as indices into the stacked [inner; outer] vertex array.

    A MANUAL advancing-front zipper: keep a base edge (inner[i], outer[j]) and at
    each step advance whichever ring's next node is angularly closer, emitting one
    triangle. This tiles the thin annulus correctly by construction (no gaps /
    overlaps) and CANNOT crash — no geometric kernel is involved. Triangle and
    Delaunay both choke on this thin two-ring annulus at some rotor angles; pure
    index logic is bulletproof at every angle."""
    ni, no = len(inner_xy), len(outer_xy)
    # sort both rings into [0, 2pi) (oi/oo map sorted-position -> local index)
    ai = np.arctan2(inner_xy[:, 1], inner_xy[:, 0]) % (2 * np.pi)
    ao = np.arctan2(outer_xy[:, 1], outer_xy[:, 0]) % (2 * np.pi)
    oi = np.argsort(ai); oo = np.argsort(ao)
    ai_s, ao_s = ai[oi], ao[oo]
    i = j = 0
    tris = np.empty((ni + no, 3), int)
    for k in range(ni + no):
        # absolute (unwrapped) angle of each ring's NEXT node; advance the
        # one that comes first, so the front sweeps monotonically around (no
        # disk-spanning triangles, no overlaps).
        na = ai_s[(i + 1) % ni] + (2 * np.pi if i + 1 >= ni else 0.0)
        nb = ao_s[(j + 1) % no] + (2 * np.pi if j + 1 >= no else 0.0)
        if na <= nb:                                     # advance inner
            tris[k] = (oi[i % ni], oi[(i + 1) % ni], ni + oo[j % no])
            i += 1
        else:                                            # advance outer
            tris[k] = (oi[i % ni], ni + oo[(j + 1) % no], ni + oo[j % no])
            j += 1
    return tris


def assemble(rotor_shapes, stator_shapes, r_rb=27.0, r_sb=27.1, rotor_deg=0.0,
             max_area=8.0, mesh_rotor=None, mesh_stator=None):
    """Build one combined Mesh for the given rotor angle. Pass prebuilt
    mesh_rotor/mesh_stator (at 0deg) to reuse them across angles — only the
    rotor nodes are rotated and the band is re-stitched. Returns
    (Mesh, unified_shapes, mesh_rotor, mesh_stator)."""
    if mesh_rotor is None:
        mesh_rotor = generate(rotor_shapes, max_area=max_area)
    if mesh_stator is None:
        # The stator side is an ANNULUS, but generate() meshes the convex hull
        # and does NOT treat the central r<r_sb region as a hole — it fills the
        # empty centre too (tagged vacuum), which would OVERLAP the rotor
        # sub-mesh and corrupt the FEM (two meshes in one region -> shorted
        # field). Drop those central triangles and compact the orphaned nodes.
        ms = generate(stator_shapes, max_area=max_area)
        cents = ms.nodes[ms.triangles].mean(axis=1)
        keep = np.hypot(cents[:, 0], cents[:, 1]) >= r_sb - 0.05
        tris = ms.triangles[keep]
        used = np.unique(tris)
        remap = -np.ones(len(ms.nodes), int)
        remap[used] = np.arange(len(used))
        mesh_stator = Mesh(ms.nodes[used], remap[tris], ms.tri_shape[keep])

    # rigidly rotate the rotor sub-mesh nodes
    th = np.radians(rotor_deg)
    c, s = np.cos(th), np.sin(th)
    R = np.array([[c, -s], [s, c]])
    rn = mesh_rotor.nodes @ R.T
    sn = mesh_stator.nodes

    rb_idx = _band_ring(rn, r_rb)
    sb_idx = _band_ring(sn, r_sb)
    band_tris_local = _stitch(rn[rb_idx], sn[sb_idx])

    nr = len(rn)
    nodes = np.vstack([rn, sn])
    # remap band stitch local indices -> combined node indices
    n_in = len(rb_idx)
    local2comb = np.concatenate([rb_idx, nr + sb_idx])     # inner then outer
    band_tris = local2comb[band_tris_local]

    rot_tris = mesh_rotor.triangles
    sta_tris = mesh_stator.triangles + nr
    tris = np.vstack([rot_tris, sta_tris, band_tris])

    # tags index into unified_shapes = rotor_shapes + stator_shapes
    nrs = len(rotor_shapes)
    band_air = nrs + stator_shapes.index(next(s for s in stator_shapes
                                              if s.name == "StatorGap"))
    tags = np.concatenate([
        mesh_rotor.tri_shape,
        np.where(mesh_stator.tri_shape >= 0, mesh_stator.tri_shape + nrs, -1),
        np.full(len(band_tris), band_air, int)])
    unified = list(rotor_shapes) + list(stator_shapes)
    return Mesh(nodes, tris, tags), unified, mesh_rotor, mesh_stator


def backemf_band(shapes, materials, n_pole=10, n_steps=25, L_stk_m=0.028,
                 turns=14, base_rpm=3000.0, max_area=8.0, r_rb=27.0, r_sb=27.1,
                 progress=None):
    """Robust sliding-band no-load back-EMF: rotor & stator meshed ONCE, only the
    rotor nodes rotate and the gap band re-stitches each angle. Crash-free at all
    angles (unlike solver.backemf_sweep_moving) and matches the fixed-mesh field
    to <1%. Returns (angles_deg, emf{A,B,C}[V], lam{A,B,C}[Wb]).

    Works with both build_motor() and build_motor(eccentric=True); the eccentric
    bread-loaf de-peaks the EMF (peak 24.9 -> 23.6, toward Maxwell ~22) while
    keeping form ~1.40 ~ Maxwell 1.375.
    """
    import numpy as np
    from .solver import solve_magnetostatic, flux_linkage, phase_map
    rotor_sh, stator_sh = build_split(shapes, r_rb=r_rb, r_sb=r_sb)
    mr = ms = None
    span = 720.0 / max(n_pole, 1)
    angles = np.linspace(0.0, span, n_steps)
    lam = {"A": np.zeros(n_steps), "B": np.zeros(n_steps), "C": np.zeros(n_steps)}
    for i, th in enumerate(angles):
        mesh, uni, mr, ms = assemble(rotor_sh, stator_sh, r_rb=r_rb, r_sb=r_sb,
                                     rotor_deg=float(th), max_area=max_area,
                                     mesh_rotor=mr, mesh_stator=ms)
        f = solve_magnetostatic(mesh, uni, materials, None, n_pole=n_pole,
                                rotor_angle_deg=float(th))
        lk = flux_linkage(f.Az, mesh, phase_map(uni, n_pole), L_stk_m, turns)
        for ph in lam:
            lam[ph][i] = lk[ph]
        if progress:
            progress(i + 1, n_steps)
    wm = base_rpm * 2 * np.pi / 60.0
    emf = {ph: -np.gradient(lam[ph], np.radians(angles)) * wm for ph in lam}
    return angles, emf, lam
