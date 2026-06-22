"""Build the 400W 10-pole/12-slot SPM motor 2D cross-section to the real
parametric spec (from the Maxwell design): surface magnets on a rotor back-iron,
a slotted stator with parallel teeth + pole shoes, and the coil pockets.

Dimensions are the verified design variables (mm):
  D_ro=53.6 (R_mag_out=26.8), T_m=2.9, D_shaft=42, g=0.5, D_si=54.6 (R_si=27.3),
  D_so=82.3 (R_so=41.15), T_yoke=3.3, N_slot=12, W_t=5.6, H_t=9.25, W_so=3,
  d_1=0.8, d_2=0.5, a_m=0.89 (theta_one=16.02deg half magnet arc).

CONFORMAL MESHING: every circular boundary is sampled on one global angular grid
(`_NDIV` divisions), so a boundary shared by two regions (e.g. the rotor outer
circle and each magnet's inner arc, both at R=23.9) lands on identical vertices.
The mesher then sees one shared edge, not two mismatched faceted curves — no
sliver explosion, no crossing segments. Feature angles are snapped to that grid.
Used by 'Insert sample motor' and by the feedback harness (solve_case.py).
"""
from __future__ import annotations

import math

import shapely
from shapely.geometry import Polygon, box
from shapely.affinity import rotate
from shapely.ops import unary_union

from .model.geometry import Shape

_NDIV = 720                                    # global angular grid (0.5 deg)


def _c(g):
    """Snap to a 1nm grid to drop the zero-length edges / duplicate vertices that
    shapely boolean ops (union/difference/buffer) leave behind. These degenerate
    0deg corners are invisible to area but make Triangle's quality mesher fail.
    Identical grid inputs snap identically, so shared boundaries stay conformal."""
    return shapely.set_precision(g, 1e-6)


def _pt(R, i):
    a = 2.0 * math.pi * i / _NDIV
    return (R * math.cos(a), R * math.sin(a))


def _ring(R):
    return [_pt(R, i) for i in range(_NDIV)]


def _disk(R):
    return Polygon(_ring(R))


def _annulus(r0, r1):
    return Polygon(_ring(r1), [_ring(r0)])


def _arc(R, a0_deg, a1_deg):
    """Grid-aligned arc points from a0..a1 (deg), inclusive (snapped to grid)."""
    i0 = round(a0_deg / 360.0 * _NDIV)
    i1 = round(a1_deg / 360.0 * _NDIV)
    return [_pt(R, i) for i in range(i0, i1 + 1)]


def _wedge(r0, r1, a0_deg, a1_deg):
    """Annular sector with grid-aligned arcs (inner arc shared-vertex friendly)."""
    return Polygon(_arc(r1, a0_deg, a1_deg) + _arc(r0, a0_deg, a1_deg)[::-1])


def build_motor(poles: int = 10, slots: int = 12) -> list[Shape]:
    # --- 400W 10P12S SPM spec (mm) ------------------------------------
    R_mag_out = 26.8                       # D_ro/2  (magnet outer = gap-facing)
    T_m       = 2.9
    R_mag_in  = R_mag_out - T_m            # 23.9
    theta_one = 16.02                      # half magnet arc  (a_m*180/poles)
    g         = 0.5
    R_si      = R_mag_out + g              # 27.3   (= D_si/2, stator bore)
    R_so      = 41.15                      # D_so/2
    T_yoke    = 3.3
    R_yoke_in = R_so - T_yoke              # 37.85
    W_so      = 3.0
    d_1, d_2  = 0.8, 0.5
    W_t       = 5.6
    R_body_in = R_si + d_1 + d_2           # 28.6   (tooth body / coil start)
    R_region  = R_so + 2.0

    shapes: list[Shape] = []
    shapes.append(Shape("Region", _disk(R_region),
                        material="vacuum", color="#eef1f4"))

    # --- rotor back-iron (solid steel disk; its rim is shared with magnets) ---
    shapes.append(Shape("Rotor", _disk(R_mag_in),
                        material="20PNX1200F", color="#8a939c"))

    # --- surface magnets: centred at (k+0.5)*pitch so each sits cleanly inside
    #     the solver's pole bin (no 0deg-wrap split-polarity) ----------------
    pitch_m = 360.0 / poles
    for k in range(poles):
        c = pitch_m * (k + 0.5)
        seg = _wedge(R_mag_in, R_mag_out, c - theta_one, c + theta_one)
        if seg.is_empty:
            continue
        color = "#c0392b" if k % 2 == 0 else "#2f5f8f"
        shapes.append(Shape("Magnet%d" % (k + 1), seg, material="N45UH",
                            color=color))

    # --- stator steel = yoke ring + 12 parallel teeth (body + pole shoe) ----
    pitch_s = 360.0 / slots
    opening_deg = math.degrees(2 * math.asin((W_so / 2) / R_si))   # ~6.30 (theta_so)
    shoe_half = (pitch_s - opening_deg) / 2                        # ~11.85
    yoke_cap = _disk(R_yoke_in)                          # clip teeth to the bore-side
    parts = [_annulus(R_yoke_in, R_so)]
    for k in range(slots):
        phi = pitch_s * k                                # tooth axis [deg]
        body = box(-W_t / 2, R_si, W_t / 2, R_yoke_in)   # +y bar, constant width
        body = rotate(body, phi - 90.0, origin=(0, 0))   # point it along phi
        # clip the body to the R_yoke_in disk so its top follows the grid arc
        # (the bare box corners poke ~0.1mm past R_yoke_in, which leaves a 0deg
        # spike on the coil when differenced — that breaks quality meshing).
        body = body.intersection(yoke_cap)
        parts.append(body)
        parts.append(_wedge(R_si, R_body_in, phi - shoe_half, phi + shoe_half))
    stator = _c(unary_union(parts).buffer(0))
    shapes.append(Shape("Stator", stator, material="20PNX1200F", color="#8a939c"))

    # --- coils = slot pockets = (coil band) - stator steel -------------------
    # Inset each coil ~0.3mm from the slot walls (slot insulation): the copper
    # becomes a clean island that shares NO edge with the stator steel, so the
    # conformal mesh has no degenerate slot-bottom slivers. Physically faithful
    # (real coils are insulated from the core).
    coil_region = _annulus(R_body_in, R_yoke_in).difference(stator).buffer(0)
    pieces = (list(coil_region.geoms)
              if coil_region.geom_type == "MultiPolygon" else [coil_region])
    geoms = []
    for gm in pieces:
        if gm.area <= 0.5:
            continue
        c = gm.buffer(-0.3, join_style=2)
        if c.is_empty:
            continue
        if c.geom_type == "MultiPolygon":
            c = max(c.geoms, key=lambda p: p.area)
        geoms.append(_c(c))
    geoms.sort(key=lambda gm: math.degrees(
        math.atan2(gm.centroid.y, gm.centroid.x)) % 360.0)
    for i, gm in enumerate(geoms):
        shapes.append(Shape("Winding%d" % (i + 1), gm, material="copper",
                            color="#d98c3f"))
    return shapes
