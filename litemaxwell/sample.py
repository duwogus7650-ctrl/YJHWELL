"""Build a simple PM-motor 2D cross-section, echoing the video geometry:
outer region, slotted stator, windings, and an alternating-pole magnet rotor.
Used by the 'Insert sample motor' action so there is something to mesh."""
from __future__ import annotations

import math

from shapely.geometry import Point
from shapely.affinity import rotate, translate

from .model.geometry import Shape, boolean_subtract


def build_motor(poles: int = 10, slots: int = 12) -> list[Shape]:
    shapes: list[Shape] = []

    region = Shape.circle("Region", 0, 0, 60, material="vacuum", color="#eef1f4")
    shapes.append(region)

    # --- stator: ring + slots cut out ---------------------------------
    stator_outer = Point(0, 0).buffer(45, quad_segs=48)
    stator_inner = Point(0, 0).buffer(26, quad_segs=48)
    stator_geom = stator_outer.difference(stator_inner)
    slot = Point(0, 34).buffer(4.2, quad_segs=16)            # one slot opening
    slots_geom = None
    wind_shapes = []
    for k in range(slots):
        ang = 360.0 / slots * k
        s = rotate(slot, ang, origin=(0, 0))
        slots_geom = s if slots_geom is None else slots_geom.union(s)
        wind_shapes.append(Shape("Winding%d" % (k + 1),
                                 rotate(Point(0, 34).buffer(3.0, quad_segs=16),
                                        ang, origin=(0, 0)),
                                 material="copper", color="#d98c3f"))
    stator = Shape("Stator", stator_geom.difference(slots_geom),
                   material="20PNX1200F", color="#8a939c")
    shapes.append(stator)
    shapes.extend(wind_shapes)

    # --- rotor: hub + surface magnets ---------------------------------
    rotor = Shape.circle("Rotor", 0, 0, 18, material="20PNX1200F",
                         color="#8a939c")
    shapes.append(rotor)
    span = 360.0 / poles * 0.78
    base = Point(0, 0).buffer(24, quad_segs=64).difference(
        Point(0, 0).buffer(18.3, quad_segs=64))
    for k in range(poles):
        a0 = 360.0 / poles * k - span / 2
        a1 = 360.0 / poles * k + span / 2
        wedge = _wedge(0, 0, 18.3, 24, a0, a1)
        seg = base.intersection(wedge)
        if seg.is_empty:
            continue
        color = "#c0392b" if k % 2 == 0 else "#2f5f8f"
        shapes.append(Shape("Magnet%d" % (k + 1), seg, material="N45UH",
                            color=color, ))
    return shapes


def _wedge(cx, cy, r0, r1, a0, a1, steps=24):
    from shapely.geometry import Polygon
    pts = []
    for i in range(steps + 1):
        a = math.radians(a0 + (a1 - a0) * i / steps)
        pts.append((cx + r1 * math.sin(a), cy + r1 * math.cos(a)))
    for i in range(steps + 1):
        a = math.radians(a1 - (a1 - a0) * i / steps)
        pts.append((cx + r0 * math.sin(a), cy + r0 * math.cos(a)))
    return Polygon(pts)
