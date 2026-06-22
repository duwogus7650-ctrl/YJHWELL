"""Triangular finite-element mesh generation via Shewchuk's Triangle.

Builds a single planar straight-line graph (PSLG) from every shape boundary,
triangulates it with quality constraints, then tags each triangle with the
innermost (smallest-area) shape that contains its centroid. That tagging is
what later turns the mesh into material regions for the FEM solver.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import triangle as tr

from .geometry import Shape


@dataclass
class Mesh:
    nodes: np.ndarray            # (N, 2) float
    triangles: np.ndarray        # (M, 3) int
    tri_shape: np.ndarray        # (M,) int -> index into shapes (-1 = none)

    @property
    def n_nodes(self) -> int:
        return len(self.nodes)

    @property
    def n_tris(self) -> int:
        return len(self.triangles)

    def centroids(self) -> np.ndarray:
        return self.nodes[self.triangles].mean(axis=1)


def _dedup(points: np.ndarray, tol: float = 1e-9):
    """Return unique points (rounded) and an index map for incoming rows."""
    rounded = np.round(points / tol).astype(np.int64)
    _, idx, inv = np.unique(rounded, axis=0, return_index=True, return_inverse=True)
    return points[idx], inv


def generate(shapes: list[Shape], max_area: float | None = None,
             min_angle: float = 28.0,
             refinements: dict[str, float] | None = None) -> Mesh:
    """Triangulate the union of all shape boundaries.

    max_area: maximum triangle area (model units^2). Defaults to a fraction of
    the overall bounding-box area so the mesh is visible but not enormous.

    refinements: optional mapping of shape NAME -> maximum element LENGTH (mm).
    Each refined shape gets a per-region maximum triangle area derived from the
    equilateral-triangle formula  area = (sqrt(3)/4) * L**2 . This is fed to
    Triangle via its regional-attribute mechanism: a region seed point is placed
    at each refined shape's interior representative point, carrying that shape's
    per-region max area in the 4th column of the regions array. The connected
    area containing the seed inherits that area constraint, so a nested shape
    (e.g. a Magnet inside a Region) correctly gets ITS refinement rather than the
    parent's. If refinements is None/empty the behaviour is identical to before.
    """
    visible = [s for s in shapes if s.visible and not s.geom.is_empty
               and s.is_closed]
    if not visible:
        raise ValueError("메시를 만들 닫힌 형상이 없습니다 (열린 폴리라인은 제외).")

    verts: list[np.ndarray] = []
    segs: list[tuple[int, int]] = []
    base = 0
    for s in visible:
        for ring in s.rings():
            ring = ring[:-1] if np.allclose(ring[0], ring[-1]) else ring
            n = len(ring)
            if n < 3:
                continue
            verts.append(ring)
            segs.extend((base + i, base + (i + 1) % n) for i in range(n))
            base += n

    pts = np.vstack(verts)
    pts, inv = _dedup(pts)
    segs = np.array([(inv[a], inv[b]) for a, b in segs])
    # drop degenerate / duplicate segments
    segs = segs[segs[:, 0] != segs[:, 1]]

    if max_area is None:
        minx = pts[:, 0].min(); maxx = pts[:, 0].max()
        miny = pts[:, 1].min(); maxy = pts[:, 1].max()
        bbox_area = max((maxx - minx) * (maxy - miny), 1e-9)
        max_area = bbox_area / 1500.0

    pslg = {"vertices": pts, "segments": segs}

    # Per-region (per-object) area control via Triangle's "regions" mechanism.
    #
    # Triangle's per-region area is ONLY honoured when the 'a' switch carries NO
    # trailing number: a fixed  a{value}  overrides the regions array entirely
    # (verified: 'pq28Aa50' ignores column 4, while bare 'pq28Aa' applies it).
    # So when refinements are requested we drop the global  a{max_area}  number
    # and instead give EVERY connected area its own seed in the regions array:
    #   - a refined shape gets  area = (sqrt(3)/4) * L**2  (equilateral tri),
    #   - every other visible shape gets the global  max_area,
    #   - the leftover background (outside all shapes) gets  max_area  too,
    # so nothing is left without an area cap. Each seed is placed at the shape's
    # representative interior point (guaranteed inside the solid, handles
    # holes/donuts), so a nested shape (Magnet inside Region) gets ITS own area,
    # because Triangle assigns a region's area to the connected component that
    # actually contains the seed.
    regions: list[list[float]] = []
    if refinements:
        from math import sqrt
        from shapely.ops import unary_union
        equilat = sqrt(3.0) / 4.0          # area = (sqrt(3)/4) * L**2
        attr = 0
        for i, s in enumerate(visible):
            length = refinements.get(s.name)
            if length is not None and length > 0:
                area = equilat * float(length) ** 2
            else:
                area = float(max_area)     # unrefined shape -> global cap
            # Seed must sit in the part of this shape the tagging logic actually
            # assigns to it. Tagging is "smallest-area shape wins", so subtract
            # every OTHER visible shape with a smaller (or equal) area — those
            # would otherwise own those triangles and form their own connected
            # mesh areas. This guarantees a nested shape (Magnet inside Region)
            # gets ITS refinement and the parent's seed lands in the leftover
            # annulus, not inside the child.
            others = [o.geom for j, o in enumerate(visible)
                      if j != i and o.area <= s.area]
            excl = s.geom
            if others:
                excl = s.geom.difference(unary_union(others))
            if excl.is_empty:
                continue                   # fully covered by smaller shapes
            rp = excl.representative_point()
            attr += 1
            regions.append([float(rp.x), float(rp.y), float(attr), area])

        # Background seed: a point inside the meshed domain but outside every
        # shape, so the leftover area still gets the global max_area under the
        # bare 'a' switch (otherwise it would be left unconstrained).
        from shapely.geometry import Point as _Pt
        from shapely.ops import unary_union
        union = unary_union([s.geom for s in visible])
        minx = pts[:, 0].min(); maxx = pts[:, 0].max()
        miny = pts[:, 1].min(); maxy = pts[:, 1].max()
        bg = None
        nx = ny = 7
        for iy in range(1, ny):
            for ix in range(1, nx):
                px = minx + (maxx - minx) * ix / nx
                py = miny + (maxy - miny) * iy / ny
                if not union.intersects(_Pt(px, py)):
                    bg = (px, py)
                    break
            if bg is not None:
                break
        if bg is not None:
            attr += 1
            regions.append([float(bg[0]), float(bg[1]), float(attr),
                            float(max_area)])

    if regions:
        pslg["regions"] = np.array(regions, float)
        # 'A' = regional attributes, bare 'a' (no number) = per-region areas
        # read from the regions array's 4th column.
        opts = f"pq{min_angle:g}Aa"
    else:
        opts = f"pq{min_angle:g}a{max_area:.6g}"
    out = tr.triangulate(pslg, opts)

    nodes = np.asarray(out["vertices"], float)
    tris = np.asarray(out["triangles"], int)

    # tag each triangle by innermost containing shape (smallest area wins)
    cents = nodes[tris].mean(axis=1)
    order = sorted(range(len(visible)), key=lambda i: visible[i].area, reverse=True)
    tag = np.full(len(tris), -1, int)
    from shapely.geometry import Point
    for i in order:                       # large first so small overwrite
        g = visible[i].geom
        for t, (cx, cy) in enumerate(cents):
            if g.contains(Point(cx, cy)):
                tag[t] = i
    return Mesh(nodes, tris, tag)
