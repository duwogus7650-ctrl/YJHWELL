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
             min_angle: float = 28.0) -> Mesh:
    """Triangulate the union of all shape boundaries.

    max_area: maximum triangle area (model units^2). Defaults to a fraction of
    the overall bounding-box area so the mesh is visible but not enormous.
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
