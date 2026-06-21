"""Optional FEMM backend / verification oracle.

FEMM (https://www.femm.info) is a validated open-source 2D electromagnetic FEM.
When it (and the `femm` python package) is installed, this module rebuilds the
SAME geometry the lite solver uses inside FEMM, solves it, and reads back the
air-gap flux density / peak B — giving a Maxwell-grade reference to cross-check
the in-process solver against, plus an optional high-accuracy backend.

Everything degrades gracefully: `available()` is False when FEMM is absent and
callers fall back to the built-in solver.
"""
from __future__ import annotations

import math
import os
import tempfile

import numpy as np


def available() -> bool:
    try:
        import femm  # noqa: F401
    except Exception:
        return False
    return True


def _mat_kind(mat):
    if mat is None:
        return "air"
    if getattr(mat, "is_magnet", False):
        return "magnet"
    if mat.mu_r > 50 or not mat.bh.is_empty():
        return "steel"
    if mat.conductivity > 1e6:
        return "copper"
    return "air"


def _ensure_materials(femm, shapes, materials):
    """Register the FEMM materials we need (idempotent)."""
    femm.mi_getmaterial("Air")
    seen = set()
    for s in shapes:
        mat = materials.get(s.material)
        kind = _mat_kind(mat)
        nm = s.material
        if nm in seen:
            continue
        seen.add(nm)
        if kind == "air":
            continue
        if kind == "copper":
            # linear copper (sigma in MS/m); current set per block
            femm.mi_addmaterial(nm, 1, 1, 0, 0, 58, 0, 0, 1, 0, 0, 0)
        elif kind == "steel":
            if not mat.bh.is_empty():
                femm.mi_addmaterial(nm, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0)
                for h, b in zip(mat.bh.H, mat.bh.B):
                    if b >= 0:
                        femm.mi_addbhpoint(nm, float(b), float(h))
            else:
                mu = mat.mu_r if mat.mu_r > 0 else 1000.0
                femm.mi_addmaterial(nm, mu, mu, 0, 0, 0, 0, 0, 1, 0, 0, 0)
        elif kind == "magnet":
            hc = mat.hc if mat.hc > 0 else mat.br / (4e-7 * math.pi * max(mat.mu_r, 1.0))
            mur = mat.mu_r if mat.mu_r > 0 else 1.05
            femm.mi_addmaterial(nm, mur, mur, hc, 0, 0, 0, 0, 1, 0, 0, 0)


def _add_ring(femm, ring):
    """Add a closed polyline (ring of (x,y)) to the FEMM model as segments."""
    pts = np.asarray(ring, float)
    if len(pts) > 1 and np.allclose(pts[0], pts[-1]):
        pts = pts[:-1]
    n = len(pts)
    for x, y in pts:
        femm.mi_addnode(float(x), float(y))
    for i in range(n):
        x0, y0 = pts[i]; x1, y1 = pts[(i + 1) % n]
        femm.mi_addsegment(float(x0), float(y0), float(x1), float(y1))


def _radii(shapes, names):
    rs = []
    for s in shapes:
        if s.name.startswith(names):
            for ring in s.rings():
                r = np.hypot(np.asarray(ring)[:, 0], np.asarray(ring)[:, 1])
                rs.extend(r.tolist())
    return rs


def solve(shapes, materials, n_pole=10, depth_mm=28.0, currents=None,
          gap_samples=180):
    """Build the design in FEMM, solve magnetostatics, return a dict with
    air-gap |B| mean/max (sampled on the mid-gap circle) and peak |B|."""
    import femm
    rotor = _radii(shapes, ("Magnet", "Rotor"))
    stator = [r for r in _radii(shapes, ("Stator",)) if r > 1.0]
    rotor_out = max(rotor) if rotor else 24.0
    stator_in = min(stator) if stator else 26.0
    region_out = max(_radii(shapes, ("Region",)) or [60.0])
    r_gap = 0.5 * (rotor_out + stator_in)

    femm.openfemm(1)
    femm.newdocument(0)
    femm.mi_probdef(0, "millimeters", "planar", 1e-8, depth_mm, 30)
    _ensure_materials(femm, shapes, materials)

    closed = [s for s in shapes if s.is_closed and not s.geom.is_empty]
    for s in closed:
        for ring in s.rings():
            _add_ring(femm, ring)

    # block labels: one per solid sub-polygon at its representative point
    from shapely.ops import unary_union
    cur = currents or {}
    solids = []
    for s in closed:
        mat = materials.get(s.material)
        kind = _mat_kind(mat)
        if kind == "air":
            continue
        for poly in s.polygons():
            rp = poly.representative_point()
            femm.mi_addblocklabel(rp.x, rp.y)
            femm.mi_selectlabel(rp.x, rp.y)
            if kind == "magnet":
                ang = math.degrees(math.atan2(rp.y, rp.x))
                pole = int((ang % 360) / (360.0 / max(n_pole, 1)))
                magdir = ang if pole % 2 == 0 else ang + 180.0
                femm.mi_setblockprop(s.material, 1, 0, "", magdir, 0, 0)
            elif kind == "copper":
                femm.mi_setblockprop(s.material, 1, 0, "", 0, 0, cur.get(s.name, 0.0))
            else:
                femm.mi_setblockprop(s.material, 1, 0, "", 0, 0, 0)
            femm.mi_clearselected()
            solids.append(poly)

    # air = region disk minus every solid -> a label in EVERY air pocket
    region_shape = max(closed, key=lambda s: s.geom.area)
    air = region_shape.geom
    if solids:
        air = air.difference(unary_union(solids))
    air_polys = (list(air.geoms) if air.geom_type == "MultiPolygon"
                 else ([] if air.is_empty else [air]))
    for poly in air_polys:
        rp = poly.representative_point()
        femm.mi_addblocklabel(rp.x, rp.y)
        femm.mi_selectlabel(rp.x, rp.y)
        femm.mi_setblockprop("Air", 1, 0, "", 0, 0, 0)
        femm.mi_clearselected()

    # Az = 0 on the region's outer ring (matches the lite solver's Dirichlet)
    femm.mi_addboundprop("A0", 0, 0, 0, 0, 0, 0, 0, 0, 0)
    ext = np.asarray(region_shape.geom.exterior.coords)
    femm.mi_clearselected()
    for i in range(len(ext) - 1):
        mx = 0.5 * (ext[i, 0] + ext[i + 1, 0]); my = 0.5 * (ext[i, 1] + ext[i + 1, 1])
        femm.mi_selectsegment(float(mx), float(my))
    femm.mi_setsegmentprop("A0", 0, 1, 0, 0)
    femm.mi_clearselected()

    d = tempfile.mkdtemp()
    fp = os.path.join(d, "yjh.fem")
    femm.mi_saveas(fp)
    femm.mi_analyze(1)
    femm.mi_loadsolution()

    # sample |B| on the mid-gap circle
    bmag = []
    for k in range(gap_samples):
        a = 2 * math.pi * k / gap_samples
        bx, by = femm.mo_getb(r_gap * math.cos(a), r_gap * math.sin(a))
        bmag.append(math.hypot(bx, by))
    bmag = np.asarray(bmag)
    femm.closefemm()
    return {"airgap_B_mean": float(bmag.mean()),
            "airgap_B_max": float(bmag.max()),
            "r_gap_mm": r_gap}
