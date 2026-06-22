"""Second-order (P2 / quadratic) triangular finite elements for the 2D
magnetostatic A-formulation.

A P2 triangle carries 6 nodes — the 3 vertices plus the 3 edge midpoints — and
quadratic shape functions, so the vector potential is quadratic and the flux
density B = curl A is LINEAR within each element (vs. piecewise-constant for the
linear P1/CST elements). That removes most of the per-element field error and
smooths the gradient field, which is what Maxwell's higher-order elements buy.

This module supplies the order-2 pieces the solver needs:
  - p2_build()      : add edge-midpoint nodes -> (p2_xy, p2_tris, n_p1, bnd_mask)
  - p2_stiffness()  : the 6x6  integral(grad Nk . grad Nl) dA   (no nu)
  - p2_centroid_grad: grad Nk at the element centroid (for B recovery + magnet RHS)
  - p2_edge_nodes   : local indices of the 3 edge nodes (for the Jz source)

Shape-function / node ordering (standard): local nodes 0,1,2 = vertices,
3,4,5 = midpoints of the edges OPPOSITE vertices 0,1,2 i.e. edges (1,2),(2,0),(0,1).
  N0=L0(2L0-1) N1=L1(2L1-1) N2=L2(2L2-1)  N3=4L1L2 N4=4L2L0 N5=4L0L1
with Li the barycentric coordinates and grad Li = (b_i,c_i)/(2A) constant per cell.
"""
from __future__ import annotations

import numpy as np


def p2_build(p1_xy: np.ndarray, tris: np.ndarray):
    """Add a midpoint node on every unique edge of the P1 mesh.

    Returns (p2_xy (Np2,2), p2_tris (M,6) int, n_p1 int, bnd_mask (Np2,) bool).
    bnd_mask flags P2 nodes on the outer boundary (boundary vertices + midpoints
    of boundary edges) — those carry the Az=0 Dirichlet condition.
    """
    p1_xy = np.asarray(p1_xy, float)
    tris = np.asarray(tris, int)
    n_p1 = len(p1_xy)
    M = len(tris)

    # the 3 edges of each triangle, as (local opposite-vertex index, (a,b))
    # edge opposite v0 = (v1,v2); opposite v1 = (v2,v0); opposite v2 = (v0,v1)
    ea = np.stack([tris[:, 1], tris[:, 2], tris[:, 0]], axis=1)   # (M,3)
    eb = np.stack([tris[:, 2], tris[:, 0], tris[:, 1]], axis=1)   # (M,3)
    lo = np.minimum(ea, eb); hi = np.maximum(ea, eb)
    edge_key = lo.astype(np.int64) * n_p1 + hi.astype(np.int64)   # (M,3) unique per edge

    flat = edge_key.ravel()
    uniq, inv, counts = np.unique(flat, return_inverse=True, return_counts=True)
    mid_id = n_p1 + inv.reshape(M, 3)            # global midpoint node index (M,3)

    # midpoint coordinates
    mid_xy = 0.5 * (p1_xy[lo.ravel()] + p1_xy[hi.ravel()])
    mid_xy_unique = np.zeros((len(uniq), 2))
    mid_xy_unique[inv] = mid_xy                  # any duplicate writes the same value
    p2_xy = np.vstack([p1_xy, mid_xy_unique])

    p2_tris = np.hstack([tris, mid_id])          # (M,6): v0 v1 v2 m12 m20 m01

    # boundary: an edge on the boundary appears in exactly ONE triangle (count==1)
    bnd_edge = counts == 1                        # (n_unique_edges,)
    bnd_mask = np.zeros(len(p2_xy), bool)
    # boundary midpoints
    bnd_mask[n_p1 + np.where(bnd_edge)[0]] = True
    # boundary vertices = endpoints of boundary edges
    be = uniq[bnd_edge]
    bv = np.concatenate([be // n_p1, be % n_p1])
    bnd_mask[np.unique(bv)] = True
    return p2_xy, p2_tris, n_p1, bnd_mask


# 3-point quadrature at the edge midpoints (weights A/3) — exact for the
# degree-2 integrand grad Nk . grad Nl. Barycentric L at each point:
_QPTS = np.array([[0.0, 0.5, 0.5],     # mid of edge (1,2)
                  [0.5, 0.0, 0.5],     # mid of edge (2,0)
                  [0.5, 0.5, 0.0]])    # mid of edge (0,1)


def _gradN(L, g):
    """grad of the 6 P2 shape functions at barycentric L=(l0,l1,l2).
    g: (M,3,2) = [grad L0, grad L1, grad L2] per element. Returns (M,6,2)."""
    l0, l1, l2 = L                               # scalar barycentric coords
    g0, g1, g2 = g[:, 0], g[:, 1], g[:, 2]       # each (M,2)
    out = np.empty((g.shape[0], 6, 2))
    out[:, 0] = (4 * l0 - 1) * g0
    out[:, 1] = (4 * l1 - 1) * g1
    out[:, 2] = (4 * l2 - 1) * g2
    out[:, 3] = 4 * (l2 * g1 + l1 * g2)
    out[:, 4] = 4 * (l0 * g2 + l2 * g0)
    out[:, 5] = 4 * (l1 * g0 + l0 * g1)
    return out


def _grads(b, c, twoA):
    """Per-element constant barycentric gradients grad Li = (b_i,c_i)/(2A)."""
    g = np.stack([b, c], axis=2)                 # (M,3,2)
    return g / twoA[:, None, None]


def p2_stiffness(b, c, twoA, area):
    """6x6 element matrix  integral_T grad Nk . grad Nl dA  (no nu).  (M,6,6)."""
    g = _grads(b, c, twoA)
    M = len(area)
    Ke = np.zeros((M, 6, 6))
    for L in _QPTS:                              # 3 quad points, weight A/3 each
        gN = _gradN(tuple(L), g)                 # (M,6,2)
        Ke += (area / 3.0)[:, None, None] * np.einsum("eka,ela->ekl", gN, gN)
    return Ke


def p2_centroid_grad(b, c, twoA):
    """grad Nk at the element centroid (L=1/3). (M,6,2). Linear field -> exact
    for the magnetization RHS (centroid rule) and used for B recovery."""
    g = _grads(b, c, twoA)
    return _gradN((1.0 / 3, 1.0 / 3, 1.0 / 3), g)


# local indices of the 3 edge (midpoint) nodes — the only ones the uniform Jz
# source loads ( integral N_vertex dA = 0,  integral N_edge dA = A/3 ).
P2_EDGE_NODES = (3, 4, 5)
