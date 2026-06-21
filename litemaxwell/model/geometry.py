"""2D geometry primitives for the modeler, backed by shapely.

All coordinates are in model units (millimetres). Each Shape owns a shapely
geometry (Polygon or MultiPolygon) so boolean operations come for free.
"""
from __future__ import annotations

import itertools
import math
from dataclasses import dataclass, field

import numpy as np
from shapely.geometry import Polygon, MultiPolygon, Point, box, LineString
from shapely.ops import unary_union

_counter = itertools.count(1)


def _next_id() -> int:
    return next(_counter)


@dataclass
class Shape:
    """A named 2D region with an assigned material and display colour."""

    name: str
    geom: Polygon | MultiPolygon
    material: str = "vacuum"
    color: str = "#9aa7b4"
    visible: bool = True
    cmd: dict | None = None          # creation command (CreateCircle, ...)
    uid: int = field(default_factory=_next_id)

    # --- factory helpers -------------------------------------------------
    @staticmethod
    def circle(name: str, cx: float, cy: float, r: float, segments: int = 0, **kw) -> "Shape":
        qs = 24 if segments <= 0 else max(2, segments // 4)   # 0 = true (smooth) circle
        s = Shape(name, Point(cx, cy).buffer(r, quad_segs=qs), **kw)
        s.cmd = {"kind": "CreateCircle", "cx": cx, "cy": cy, "r": r, "segs": segments}
        return s

    @staticmethod
    def rectangle(name: str, x0: float, y0: float, x1: float, y1: float, **kw) -> "Shape":
        s = Shape(name, box(min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)), **kw)
        s.cmd = {"kind": "CreateRectangle", "x0": x0, "y0": y0, "x1": x1, "y1": y1}
        return s

    @staticmethod
    def polygon(name: str, points: list[tuple[float, float]], **kw) -> "Shape":
        s = Shape(name, Polygon(points), **kw)
        s.cmd = {"kind": "CreatePolyline", "points": list(points), "closed": True}
        return s

    @staticmethod
    def open_polyline(name: str, points: list[tuple[float, float]], **kw) -> "Shape":
        """An OPEN polyline (line/arc/spline) — a curve, not a filled region."""
        s = Shape(name, LineString(points), **kw)
        s.cmd = {"kind": "CreatePolyline", "points": list(points), "closed": False}
        return s

    @property
    def is_closed(self) -> bool:
        return isinstance(self.geom, (Polygon, MultiPolygon))

    # --- geometry helpers ------------------------------------------------
    @property
    def area(self) -> float:
        return float(self.geom.area)      # 0 for open polylines (LineString)

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        return self.geom.bounds  # (minx, miny, maxx, maxy)

    def contains_point(self, x: float, y: float) -> bool:
        if not self.is_closed:
            return False
        return self.geom.contains(Point(x, y))

    def polygons(self) -> list[Polygon]:
        """Flatten to a list of simple polygons (handles MultiPolygon)."""
        if isinstance(self.geom, MultiPolygon):
            return list(self.geom.geoms)
        if isinstance(self.geom, Polygon):
            return [self.geom]
        return []                          # open polyline -> no polygons

    def exterior_xy(self) -> list[np.ndarray]:
        """Exterior ring coordinates of each constituent polygon."""
        return [np.asarray(p.exterior.coords) for p in self.polygons()]

    def rings(self) -> list[np.ndarray]:
        """All rings (closed) or the open path coordinates."""
        if not self.is_closed:
            return [np.asarray(self.geom.coords)]
        out: list[np.ndarray] = []
        for p in self.polygons():
            out.append(np.asarray(p.exterior.coords))
            for hole in p.interiors:
                out.append(np.asarray(hole.coords))
        return out


@dataclass
class CoordSystem:
    """A working coordinate system (Maxwell 'Relative CS'): an origin offset plus
    a rotation.  A point typed in this CS maps to global coordinates via
        (gx, gy) = origin + R(rot)·(xr, yr),   R = [[cosθ,-sinθ],[sinθ,cosθ]].
    Offset-only = rot 0; Rotated-only = origin 0; Both = a general frame."""

    name: str = "Global"
    ox: float = 0.0
    oy: float = 0.0
    rot_deg: float = 0.0

    def to_global(self, xr: float, yr: float) -> tuple[float, float]:
        t = math.radians(self.rot_deg); c = math.cos(t); s = math.sin(t)
        return (self.ox + xr * c - yr * s, self.oy + xr * s + yr * c)

    def from_global(self, gx: float, gy: float) -> tuple[float, float]:
        t = math.radians(self.rot_deg); c = math.cos(t); s = math.sin(t)
        dx, dy = gx - self.ox, gy - self.oy
        return (dx * c + dy * s, -dx * s + dy * c)

    @property
    def is_global(self) -> bool:
        return self.ox == 0.0 and self.oy == 0.0 and self.rot_deg == 0.0


def fillet_corner(shape: "Shape", vx: float, vy: float, radius: float,
                  seg: int = 12) -> "Shape":
    """Round the polygon corner nearest (vx,vy) with the given fillet radius
    (Maxwell: Fillet on magnet end vertices).  Returns a new filleted Shape."""
    polys = shape.polygons()
    if not polys:
        return shape
    poly = polys[0]
    ring = list(poly.exterior.coords)[:-1]      # drop closing dup
    n = len(ring)
    if n < 3:
        return shape
    # nearest vertex index
    k = min(range(n), key=lambda i: (ring[i][0] - vx) ** 2 + (ring[i][1] - vy) ** 2)
    A = np.array(ring[(k - 1) % n]); V = np.array(ring[k]); B = np.array(ring[(k + 1) % n])
    u1 = A - V; u2 = B - V
    l1 = np.hypot(*u1); l2 = np.hypot(*u2)
    if l1 < 1e-9 or l2 < 1e-9:
        return shape
    u1 /= l1; u2 /= l2
    half = math.acos(max(-1.0, min(1.0, float(np.dot(u1, u2))))) / 2.0
    if half < 1e-6 or abs(half - math.pi / 2) > math.pi / 2:
        return shape
    setback = radius / math.tan(half)           # distance from V along each edge
    setback = min(setback, 0.49 * l1, 0.49 * l2)
    r = setback * math.tan(half)
    t1 = V + u1 * setback; t2 = V + u2 * setback
    bis = (u1 + u2); bis = bis / (np.hypot(*bis) + 1e-12)
    center = V + bis * (r / math.sin(half))
    a1 = math.atan2(t1[1] - center[1], t1[0] - center[0])
    a2 = math.atan2(t2[1] - center[1], t2[0] - center[0])
    # sweep the short way
    da = a2 - a1
    while da <= -math.pi:
        da += 2 * math.pi
    while da > math.pi:
        da -= 2 * math.pi
    arc = [(center[0] + r * math.cos(a1 + da * i / seg),
            center[1] + r * math.sin(a1 + da * i / seg)) for i in range(seg + 1)]
    new_ring = ring[:k] + arc + ring[k + 1:]
    s = Shape(shape.name, Polygon(new_ring), material=shape.material,
              color=shape.color)
    s.cmd = {"kind": "Fillet", "base": shape.cmd, "vx": vx, "vy": vy,
             "radius": radius}
    return s


# --- boolean operations --------------------------------------------------

def _operand_cmd(s: "Shape") -> dict:
    """Capture a shape as a boolean operand, preserving its editable history."""
    import copy
    if s.cmd:
        c = copy.deepcopy(s.cmd); c["name"] = s.name
        return c
    return {"kind": "Static", "geom": s.geom, "name": s.name}


def boolean_unite(shapes: list[Shape], name: str, **kw) -> Shape:
    merged = unary_union([s.geom for s in shapes])
    s = Shape(name, merged, **kw)
    s.cmd = {"kind": "Unite", "operands": [_operand_cmd(x) for x in shapes]}
    return s


def boolean_subtract(base: Shape, tools: list[Shape], name: str, **kw) -> Shape:
    g = base.geom
    for t in tools:
        g = g.difference(t.geom)
    s = Shape(name, g, material=base.material, color=base.color, **kw)
    s.cmd = {"kind": "Subtract",
             "operands": [_operand_cmd(base)] + [_operand_cmd(t) for t in tools]}
    return s


def boolean_intersect(shapes: list[Shape], name: str, **kw) -> Shape:
    it = iter(shapes)
    g = next(it).geom
    for x in it:
        g = g.intersection(x.geom)
    s = Shape(name, g, **kw)
    s.cmd = {"kind": "Intersect", "operands": [_operand_cmd(x) for x in shapes]}
    return s


# --- transforms ----------------------------------------------------------
from shapely import affinity  # noqa: E402


def translated(shape: Shape, dx: float, dy: float, name: str | None = None) -> Shape:
    return Shape(name or shape.name, affinity.translate(shape.geom, dx, dy),
                 material=shape.material, color=shape.color)


def rotated(shape: Shape, angle_deg: float, ox: float = 0.0, oy: float = 0.0,
            name: str | None = None) -> Shape:
    return Shape(name or shape.name,
                 affinity.rotate(shape.geom, angle_deg, origin=(ox, oy)),
                 material=shape.material, color=shape.color)


def mirrored(shape: Shape, axis: str = "x", offset: float = 0.0,
             name: str | None = None) -> Shape:
    """Mirror across the X or Y axis (optionally offset)."""
    if axis == "x":      # mirror over horizontal line y=offset
        g = affinity.scale(shape.geom, xfact=1, yfact=-1, origin=(0, offset))
    else:                # mirror over vertical line x=offset
        g = affinity.scale(shape.geom, xfact=-1, yfact=1, origin=(offset, 0))
    return Shape(name or f"{shape.name}_mir", g,
                 material=shape.material, color=shape.color)


def duplicate_around_axis(shape: Shape, count: int, total_angle: float = 360.0,
                          ox: float = 0.0, oy: float = 0.0) -> list[Shape]:
    """Maxwell-style 'Duplicate Around Axis': count copies evenly spaced."""
    out: list[Shape] = []
    if count < 2:
        return out
    full = abs(total_angle - 360.0) < 1e-6
    step = total_angle / (count if full else count - 1)
    for i in range(1, count):
        out.append(rotated(shape, step * i, ox, oy,
                           name=f"{shape.name}_{i}"))
    return out


def polyline_points(start, segments) -> list[tuple[float, float]]:
    """Build the point list of a polyline from a start point and a list of
    parametric segments — line {length, dir} or arc {cx_off, cy_off, angle}."""
    import math
    prev = (float(start[0]), float(start[1]))
    pts = [prev]
    for seg in segments:
        if seg["type"] == "line":
            th = math.radians(seg["dir"])
            prev = (prev[0] + seg["length"] * math.cos(th),
                    prev[1] + seg["length"] * math.sin(th))
            pts.append(prev)
        elif seg["type"] == "arc":
            cx = prev[0] + seg["cx_off"]; cy = prev[1] + seg["cy_off"]
            r = math.hypot(seg["cx_off"], seg["cy_off"])
            a0 = math.atan2(prev[1] - cy, prev[0] - cx)
            sweep = math.radians(seg["angle"])
            n = max(4, int(abs(sweep) / (math.pi / 24)))
            for i in range(1, n + 1):
                a = a0 + sweep * i / n
                pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
            prev = pts[-1]
    return pts


def segment_geometry(start, segments):
    """Absolute start/end (and centre for arcs) of each polyline segment."""
    import math
    prev = (float(start[0]), float(start[1]))
    out = []
    for seg in segments:
        if seg["type"] == "line":
            th = math.radians(seg["dir"])
            end = (prev[0] + seg["length"] * math.cos(th),
                   prev[1] + seg["length"] * math.sin(th))
            out.append({"type": "line", "start": prev, "end": end})
            prev = end
        else:
            cx = prev[0] + seg["cx_off"]; cy = prev[1] + seg["cy_off"]
            r = math.hypot(seg["cx_off"], seg["cy_off"])
            a0 = math.atan2(prev[1] - cy, prev[0] - cx)
            aE = a0 + math.radians(seg["angle"])
            end = (cx + r * math.cos(aE), cy + r * math.sin(aE))
            out.append({"type": "arc", "start": prev, "center": (cx, cy),
                        "end": end, "angle": seg["angle"]})
            prev = end
    return out


def _catmull(p0, p1, p2, p3, t):
    t2 = t * t; t3 = t2 * t
    def c(a, b, cc, d):
        return 0.5 * (2 * b + (-a + cc) * t + (2 * a - 5 * b + 4 * cc - d) * t2
                      + (-a + 3 * b - 3 * cc + d) * t3)
    return (c(p0[0], p1[0], p2[0], p3[0]), c(p0[1], p1[1], p2[1], p3[1]))


def spline_points(control, closed: bool = True, samples: int = 16):
    """Smooth Catmull-Rom spline through the control points."""
    P = [(float(x), float(y)) for x, y in control]
    n = len(P)
    if n < 3:
        return list(P)
    pts = []
    for i in (range(n) if closed else range(n - 1)):
        p0 = P[(i - 1) % n] if closed else P[max(i - 1, 0)]
        p1 = P[i]
        p2 = P[(i + 1) % n] if closed else P[i + 1]
        p3 = P[(i + 2) % n] if closed else P[min(i + 2, n - 1)]
        for s in range(samples):
            pts.append(_catmull(p0, p1, p2, p3, s / samples))
    return pts


def cover_lines(shape: Shape) -> bool:
    """Cover an open polyline into a filled sheet (Maxwell 'Cover Lines')."""
    if shape.is_closed or shape.cmd is None:
        return False
    pts = shape.cmd.get("points")
    if not pts or len(pts) < 3:
        return False
    shape.cmd["closed"] = True
    shape.geom = Polygon(pts)
    return True


def geom_from_cmd(c: dict):
    """Build a shapely geometry from a command dict (recursive for booleans)."""
    k = c["kind"]
    if k == "CreateCircle":
        segs = int(c.get("segs", 0)); qs = 24 if segs <= 0 else max(2, segs // 4)
        return Point(c["cx"], c["cy"]).buffer(c["r"], quad_segs=qs)
    if k == "CreateRectangle":
        return box(min(c["x0"], c["x1"]), min(c["y0"], c["y1"]),
                   max(c["x0"], c["x1"]), max(c["y0"], c["y1"]))
    if k == "CreatePolyline":
        pts = (polyline_points(c["start"], c["segments"])
               if c.get("segments") else c["points"])
        return Polygon(pts) if c.get("closed") else LineString(pts)
    if k == "CreateSpline":
        pts = spline_points(c["control"], closed=c.get("closed", True))
        return Polygon(pts) if c.get("closed") else LineString(pts)
    if k == "Static":
        return c["geom"]
    if k in ("Subtract", "Unite", "Intersect"):
        gs = [geom_from_cmd(o) for o in c["operands"]]
        if k == "Unite":
            return unary_union(gs)
        g = gs[0]
        for o in gs[1:]:
            g = g.difference(o) if k == "Subtract" else g.intersection(o)
        return g
    raise ValueError(f"unknown cmd kind: {k}")


def apply_cmd(shape: Shape) -> None:
    """Rebuild a shape's geometry from its creation command (Maxwell-style
    parametric dimension editing) — works for booleans via the operand tree."""
    c = shape.cmd
    if not c:
        return
    if c["kind"] in ("Subtract", "Unite", "Intersect"):
        shape.geom = geom_from_cmd(c)
        return
    if c["kind"] == "CreateCircle":
        segs = int(c.get("segs", 0))
        qs = 24 if segs <= 0 else max(2, segs // 4)
        shape.geom = Point(c["cx"], c["cy"]).buffer(c["r"], quad_segs=qs)
    elif c["kind"] == "CreateRectangle":
        shape.geom = box(min(c["x0"], c["x1"]), min(c["y0"], c["y1"]),
                         max(c["x0"], c["x1"]), max(c["y0"], c["y1"]))
    elif c["kind"] == "CreatePolyline":
        if c.get("segments"):
            c["points"] = polyline_points(c["start"], c["segments"])
        shape.geom = (Polygon(c["points"]) if c.get("closed")
                      else LineString(c["points"]))
    elif c["kind"] == "CreateSpline":
        closed = c.get("closed", True)
        c["points"] = spline_points(c["control"], closed=closed)
        shape.geom = Polygon(c["points"]) if closed else LineString(c["points"])


def duplicate_along_line(shape: Shape, count: int, dx: float, dy: float) -> list[Shape]:
    """Maxwell-style 'Duplicate Along Line': count copies at (dx,dy) steps."""
    out: list[Shape] = []
    for i in range(1, max(count, 1)):
        out.append(translated(shape, dx * i, dy * i, name=f"{shape.name}_{i}"))
    return out
