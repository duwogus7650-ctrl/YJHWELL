"""2D modeler canvas: an engineering-style drawing surface.

Coordinates are model millimetres with +Y pointing up (the view is Y-flipped).
Supports grid + axes, wheel zoom, middle-drag pan, and circle/rect/polygon
draw tools plus selection. A generated mesh is drawn as a foreground overlay.
"""
from __future__ import annotations

import numpy as np
from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal
from PyQt6.QtGui import (QPainter, QPen, QBrush, QColor, QPainterPath,
                         QPolygonF, QFont)
from PyQt6.QtWidgets import (QGraphicsView, QGraphicsScene, QGraphicsPathItem,
                             QGraphicsLineItem)

from shapely.geometry import Point as _SPoint

from ..model.geometry import Shape, CoordSystem


def _seg_dist(px, py, x0, y0, x1, y1):
    """Distance from point (px,py) to the segment (x0,y0)-(x1,y1)."""
    dx, dy = x1 - x0, y1 - y0
    L2 = dx * dx + dy * dy
    if L2 < 1e-12:
        return ((px - x0) ** 2 + (py - y0) ** 2) ** 0.5
    t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / L2))
    cx, cy = x0 + t * dx, y0 + t * dy
    return ((px - cx) ** 2 + (py - cy) ** 2) ** 0.5

def _jet(t: float) -> QColor:
    """Jet-style colormap (blue->cyan->green->yellow->red) for t in [0,1]."""
    t = 0.0 if t < 0 else 1.0 if t > 1 else t
    r = max(0.0, min(1.0, 1.5 - abs(4 * t - 3)))
    g = max(0.0, min(1.0, 1.5 - abs(4 * t - 2)))
    b = max(0.0, min(1.0, 1.5 - abs(4 * t - 1)))
    return QColor(int(r * 255), int(g * 255), int(b * 255))


CANVAS_BG = QColor("#0a1422")          # tech deep-navy
GRID = QColor("#12283f")
GRID_MAJOR = QColor("#1c4869")
AXIS_X = QColor("#ff5a6a")
AXIS_Y = QColor("#46d39a")
PREVIEW = QColor("#2bd6ff")
MESH_PEN = QColor(43, 214, 255, 90)
SEL = QColor("#2bd6ff")


class ShapeItem(QGraphicsPathItem):
    """A selectable graphics item bound to a model Shape."""

    def __init__(self, shape: Shape):
        super().__init__()
        self.shape = shape
        self.setFlag(QGraphicsPathItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.rebuild()

    def rebuild(self) -> None:
        path = QPainterPath()
        c = QColor(self.shape.color)
        if not self.shape.is_closed:
            # open polyline / arc / spline -> stroked curve, no fill
            coords = np.asarray(self.shape.geom.coords)
            if len(coords):
                path.moveTo(QPointF(*coords[0]))
                for x, y in coords[1:]:
                    path.lineTo(QPointF(x, y))
            self.setPath(path)
            self.setBrush(QBrush())          # no fill
            pen = QPen(c, 0); pen.setCosmetic(True); pen.setWidth(2)
            self.setPen(pen)
            self.setVisible(self.shape.visible)
            return
        for poly in self.shape.polygons():
            ext = np.asarray(poly.exterior.coords)
            path.addPolygon(QPolygonF([QPointF(x, y) for x, y in ext]))
            path.closeSubpath()
            for hole in poly.interiors:
                hc = np.asarray(hole.coords)
                path.addPolygon(QPolygonF([QPointF(x, y) for x, y in hc]))
                path.closeSubpath()
        self.setPath(path)
        self.setBrush(QBrush(QColor(c.red(), c.green(), c.blue(), 170)))
        self.setPen(QPen(c.darker(140), 0))
        self.setVisible(self.shape.visible)

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        if self.isSelected():
            pen = QPen(SEL, 0)
            pen.setCosmetic(True)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(self.path())


class ModelerView(QGraphicsView):
    selectionChanged = pyqtSignal()
    shapeCreated = pyqtSignal(object)        # emits Shape
    coordMoved = pyqtSignal(float, float)
    promptChanged = pyqtSignal(str)          # draw-step hint for status bar
    subPicked = pyqtSignal(str, object)      # ('object'|'face'|'edge'|'vertex', payload)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = QGraphicsScene(self)
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        self.setBackgroundBrush(CANVAS_BG)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setMouseTracking(True)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.scale(1, -1)                    # Y up
        self.setSceneRect(-200, -200, 400, 400)

        self.tool = "select"
        self._naming = {"circle": 0, "rect": 0, "polygon": 0, "spline": 0}
        self._items: list[ShapeItem] = []
        self._drawing = False
        self._start = QPointF()
        self._poly_pts: list[QPointF] = []
        self._pts: list[QPointF] = []      # multi-click points (circle)
        self._cpress_view = None           # press pos for drag-vs-click detection
        self._edge_type = "straight"       # straight | cpa | 3pa | spline
        self._arc_center = None            # pending centre of a centre-point arc
        self._arc_start_ang = None         # angle of arc start about centre
        self._arc_last_ang = None          # last cursor angle (for unwrapping)
        self._arc_sweep = 0.0              # accumulated sweep (follows the mouse)
        self._arc3_mid = None              # pending mid point of a 3-point arc
        self._poly_segs = []               # parametric segments of current polyline
        self._poly_start = None            # first point of current polyline
        self._preview = None
        self.mesh = None
        self.show_mesh = False
        self.field = None
        self.show_field = False
        self.snap = False
        self.select_mode = "object"        # object | face | edge | vertex (O/E/V/F)
        self.picked = None                 # last sub-entity pick (dict)
        self._pick_items = []              # highlight graphics for the pick
        self.wcs = CoordSystem()           # active working coordinate system
        self._cs_items: list = []          # the CS triad graphics
        self._osnap = True                 # object snap to existing vertices
        self._snap_marker = None           # (x, y) of active snap, for the marker
        # themeable colours (default dark)
        self.c_bg = CANVAS_BG
        self.c_grid = GRID
        self.c_grid_major = GRID_MAJOR
        self.c_axis_x = AXIS_X
        self.c_axis_y = AXIS_Y
        self.c_mesh = MESH_PEN
        self._scene.selectionChanged.connect(self.selectionChanged)

    # --- working coordinate system (Maxwell 'Relative CS') ---------------
    def to_global(self, x, y):
        """Map a point typed in the active CS to global model coords."""
        return self.wcs.to_global(x, y)

    def from_global(self, gx, gy):
        """Map a global point to the active CS (for the coordinate readout)."""
        return self.wcs.from_global(gx, gy)

    def set_wcs(self, name="Global", ox=0.0, oy=0.0, rot_deg=0.0):
        self.wcs = CoordSystem(name, ox, oy, rot_deg)
        self._draw_cs_triad()

    def _draw_cs_triad(self):
        for it in self._cs_items:
            self._scene.removeItem(it)
        self._cs_items = []
        if self.wcs.is_global:
            return                         # global CS shares the main axes
        L = 14.0
        ox, oy = self.wcs.ox, self.wcs.oy
        for (ex, ey), col in ((self.wcs.to_global(L, 0), "#e0524b"),
                              (self.wcs.to_global(0, L), "#3fae57")):
            ln = QGraphicsLineItem(ox, oy, ex, ey)
            pen = QPen(QColor(col)); pen.setWidthF(1.6)
            ln.setPen(pen); ln.setZValue(900)
            self._scene.addItem(ln); self._cs_items.append(ln)

    def set_dark(self, dark: bool):
        if dark:
            self.c_bg = CANVAS_BG; self.c_grid = GRID; self.c_grid_major = GRID_MAJOR
            self.c_axis_x = AXIS_X; self.c_axis_y = AXIS_Y; self.c_mesh = MESH_PEN
        else:
            self.c_bg = QColor("#ffffff"); self.c_grid = QColor("#e6e9ee")
            self.c_grid_major = QColor("#cfd6df")
            self.c_axis_x = QColor("#c0392b"); self.c_axis_y = QColor("#2e7d32")
            self.c_mesh = QColor(45, 63, 99, 130)
        self.setBackgroundBrush(self.c_bg)
        self.viewport().update()

    # --- snapping --------------------------------------------------------
    def _grid_step(self) -> float:
        unit_px = self.transform().m11()
        for cand in (0.1, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500):
            if cand * unit_px >= 18:
                return cand
        return 1.0

    def _snap_pt(self, p: QPointF) -> QPointF:
        """Snap to the polyline start (close), existing vertices, or the grid.
        Sets self._snap_marker = (x, y, kind) for the on-canvas marker."""
        self._snap_marker = None
        if not self._osnap:
            return p
        thr = 12 / max(self.transform().m11(), 1e-6)
        px, py = p.x(), p.y()
        best = None; bd = thr; kind = None
        # 1) closing point — snap back to the polyline start (highest priority)
        if (self.tool in ("polygon", "spline") and self._poly_start is not None
                and len(self._poly_pts) >= 2):
            S = self._poly_start
            d = ((S.x() - px) ** 2 + (S.y() - py) ** 2) ** .5
            if d < bd:
                best = (S.x(), S.y()); bd = d; kind = "close"
        # 2) existing vertices
        v, dv = self._nearest_vertex(p, thr)
        if v is not None and dv < bd:
            best = v; bd = dv; kind = "vertex"
        # 3) grid intersection — always available (clean grid-aligned drawing)
        step = self._grid_step()
        gx = round(px / step) * step; gy = round(py / step) * step
        dg = ((gx - px) ** 2 + (gy - py) ** 2) ** .5
        if best is None or dg < bd * 0.5:
            best = (gx, gy); kind = "grid"
        self._snap_marker = (best[0], best[1], kind)
        return QPointF(best[0], best[1])

    def snap_is_close(self) -> bool:
        return self._snap_marker is not None and self._snap_marker[2] == "close"

    def _nearest_vertex(self, p: QPointF, thr: float):
        best = None; bd = thr
        px, py = p.x(), p.y()
        for it in self._items:
            for ring in it.shape.rings():
                for x, y in ring:
                    d = ((x - px) ** 2 + (y - py) ** 2) ** .5
                    if d < bd:
                        bd = d; best = (float(x), float(y))
        return best, bd

    def set_osnap(self, on: bool):
        self._osnap = on
        self._snap_marker = None
        self.viewport().update()

    # --- selection modes (Maxwell O=object E=edge V=vertex F=face) --------
    def _pick_thr(self):
        m = abs(self.transform().m11()) or 1.0
        return 10.0 / m                       # ~10 px tolerance in scene units

    def set_select_mode(self, mode):
        self.set_tool("select")
        self.select_mode = mode
        self._clear_pick()
        lbl = {"object": "Object (O)", "face": "Face (F)",
               "edge": "Edge (E)", "vertex": "Vertex (V)"}.get(mode, mode)
        self.promptChanged.emit(f"Select mode: {lbl}")

    def _clear_pick(self):
        for it in self._pick_items:
            self._scene.removeItem(it)
        self._pick_items = []
        self.picked = None

    def _shape_at(self, p):
        best, ba = None, None
        sp = _SPoint(p.x(), p.y())
        for it in self._items:
            s = it.shape
            if s.is_closed and not s.geom.is_empty and s.geom.contains(sp):
                if ba is None or s.area < ba:
                    ba, best = s.area, s
        return best

    def _pick_vertex(self, p):
        v, _ = self._nearest_vertex(p, self._pick_thr())
        if v is None:
            return None
        owner = None
        for it in self._items:
            for ring in it.shape.rings():
                if any(abs(x - v[0]) < 1e-6 and abs(y - v[1]) < 1e-6 for x, y in ring):
                    owner = it.shape; break
            if owner:
                break
        return {"shape": owner, "x": v[0], "y": v[1]}

    def _pick_edge(self, p):
        px, py = p.x(), p.y(); bd = self._pick_thr(); best = None
        for it in self._items:
            for ring in it.shape.rings():
                r = list(ring)
                for i in range(len(r) - 1):
                    d = _seg_dist(px, py, r[i][0], r[i][1], r[i + 1][0], r[i + 1][1])
                    if d < bd:
                        bd = d
                        best = {"shape": it.shape,
                                "p0": (float(r[i][0]), float(r[i][1])),
                                "p1": (float(r[i + 1][0]), float(r[i + 1][1]))}
        return best

    def _do_pick(self, p):
        mode = self.select_mode
        if mode == "vertex":
            pk = self._pick_vertex(p)
        elif mode == "edge":
            pk = self._pick_edge(p)
        elif mode == "face":
            s = self._shape_at(p); pk = {"shape": s} if s else None
        else:
            pk = None
        self._clear_pick()
        if not pk or not pk.get("shape"):
            self.promptChanged.emit(f"Select mode: {mode} — nothing here")
            return
        self.picked = dict(pk, mode=mode)
        self._show_pick()
        self.subPicked.emit(mode, self.picked)

    def _show_pick(self):
        pk = self.picked; mode = pk["mode"]
        if mode == "vertex":
            r = self._pick_thr() * 0.6; x, y = pk["x"], pk["y"]
            it = self._scene.addRect(x - r, y - r, 2 * r, 2 * r,
                                     QPen(QColor("#ffb020"), 0),
                                     QBrush(QColor("#ffb020")))
            it.setZValue(950); self._pick_items.append(it)
        elif mode == "edge":
            (x0, y0), (x1, y1) = pk["p0"], pk["p1"]
            ln = QGraphicsLineItem(x0, y0, x1, y1)
            pen = QPen(QColor("#ffb020")); pen.setWidthF(self._pick_thr() * 0.5)
            ln.setPen(pen); ln.setZValue(950)
            self._scene.addItem(ln); self._pick_items.append(ln)
        elif mode == "face":
            it = self.item_for(pk["shape"])
            if it:
                it.setSelected(True)

    # --- public API ------------------------------------------------------
    def set_tool(self, tool: str) -> None:
        self.tool = tool
        self._cancel_draw()
        # rubber-band selection (single click selects items) in Select mode
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag if tool == "select"
                         else QGraphicsView.DragMode.NoDrag)

    def finish_current(self, closed: bool = False) -> None:
        if self.tool == "spline":
            self._finish_spline(closed)
        else:
            self._finish_polygon(closed)

    def undo_segment(self) -> None:
        from ..model.geometry import polyline_points
        if self._poly_segs:
            self._poly_segs.pop()
            if self._poly_start is not None:
                pts = polyline_points((self._poly_start.x(), self._poly_start.y()),
                                      self._poly_segs)
                self._poly_pts = [QPointF(x, y) for x, y in pts]
        elif self._poly_pts:
            self._poly_pts.pop()
        self._clear_preview()
        self.viewport().update()

    def add_shape(self, shape: Shape) -> ShapeItem:
        item = ShapeItem(shape)
        self._scene.addItem(item)
        self._items.append(item)
        return item

    def clear_shapes(self) -> None:
        for it in self._items:
            self._scene.removeItem(it)
        self._items.clear()

    def reload(self, shapes: list[Shape]) -> None:
        self.clear_shapes()
        for s in shapes:
            self.add_shape(s)

    def selected_shapes(self) -> list[Shape]:
        return [it.shape for it in self._items if it.isSelected()]

    def item_for(self, shape: Shape) -> ShapeItem | None:
        return next((it for it in self._items if it.shape is shape), None)

    def fit(self) -> None:
        if self._items:
            r = self._scene.itemsBoundingRect()
            if not r.isEmpty():
                self.fitInView(r.adjusted(-r.width() * .08, -r.height() * .08,
                                          r.width() * .08, r.height() * .08),
                               Qt.AspectRatioMode.KeepAspectRatio)
        else:
            self.fitInView(QRectF(-30, -30, 60, 60),
                           Qt.AspectRatioMode.KeepAspectRatio)

    def fit_selected(self) -> None:
        sel = [it for it in self._items if it.isSelected()]
        if not sel:
            self.fit(); return
        r = sel[0].sceneBoundingRect()
        for it in sel[1:]:
            r = r.united(it.sceneBoundingRect())
        if not r.isEmpty():
            self.fitInView(r.adjusted(-r.width() * .1, -r.height() * .1,
                                      r.width() * .1, r.height() * .1),
                           Qt.AspectRatioMode.KeepAspectRatio)

    def set_mesh(self, mesh) -> None:
        self.mesh = mesh
        self.show_mesh = mesh is not None
        self.viewport().update()

    def set_field(self, field) -> None:
        self.field = field
        self.show_field = field is not None
        self.viewport().update()

    # --- mouse / zoom ----------------------------------------------------
    def wheelEvent(self, e):
        f = 1.2 if e.angleDelta().y() > 0 else 1 / 1.2
        self.scale(f, f)

    def mousePressEvent(self, e):
        p = self._snap_pt(self.mapToScene(e.position().toPoint()))
        if e.button() == Qt.MouseButton.MiddleButton:
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            fake = self._fake_left(e)
            super().mousePressEvent(fake)
            return
        if self.tool == "select":
            if (self.select_mode != "object"
                    and e.button() == Qt.MouseButton.LeftButton):
                self._do_pick(self.mapToScene(e.position().toPoint()))
                return
            super().mousePressEvent(e)
            return
        if self.tool in ("circle", "rect"):
            self._drawing = True
            self._start = p
            self.promptChanged.emit(
                ("Circle" if self.tool == "circle" else "Rectangle")
                + ": drag to the opposite point and release")
        elif self.tool == "spline":
            if e.button() == Qt.MouseButton.LeftButton:
                self._poly_pts.append(p)
                self.promptChanged.emit("Spline: next point (right-click → Done)")
            # right-click handled by the context menu (Done / Undo)
        elif self.tool == "polygon":
            if e.button() == Qt.MouseButton.RightButton:
                pass                          # context menu handles Done/segment type
            elif not self._poly_pts:
                self._poly_pts = [p]; self._poly_start = p
                self._edge_prompt()
            elif self.snap_is_close() and len(self._poly_pts) >= 3:
                self._finish_polygon(closed=True)   # clicked the start -> close
            elif self._edge_type == "cpa":
                if self._arc_center is None:
                    self._begin_arc(p)
                else:
                    self._finalize_arc(p)
            elif self._edge_type == "3pa":
                if self._arc3_mid is None:
                    self._arc3_mid = p
                    self.promptChanged.emit("3 Point Arc: pick end point")
                else:
                    self._finalize_3pt_arc(p)
            else:                                   # straight
                self._add_line_segment(p)

    def mouseMoveEvent(self, e):
        old = self._snap_marker
        p = self._snap_pt(self.mapToScene(e.position().toPoint()))
        if self._snap_marker != old:
            self.viewport().update()
        self.coordMoved.emit(p.x(), p.y())
        if self._drawing and self.tool in ("circle", "rect"):
            self._update_preview(p)
        elif self.tool == "spline" and self._poly_pts:
            self._update_spline_preview(p)
        elif (self.tool == "polygon" and self._edge_type == "cpa"
                and self._arc_center is not None and self._poly_pts):
            self._track_arc(p)
        elif (self.tool == "polygon" and self._edge_type == "3pa"
                and self._arc3_mid is not None and self._poly_pts):
            self._update_3pt_preview(p)
        elif self.tool == "polygon" and self._poly_pts:
            self._update_poly_preview(p)
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if self.dragMode() == QGraphicsView.DragMode.ScrollHandDrag:
            super().mouseReleaseEvent(e)
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag
                             if self.tool == "select"
                             else QGraphicsView.DragMode.NoDrag)
            return
        if self._drawing and self.tool in ("circle", "rect"):
            p = self._snap_pt(self.mapToScene(e.position().toPoint()))
            self._commit(p)
            self._drawing = False
        else:
            super().mouseReleaseEvent(e)

    def mouseDoubleClickEvent(self, e):
        if self.tool == "polygon":
            self._finish_polygon()
        elif self.tool == "spline":
            self._finish_spline()
        else:
            super().mouseDoubleClickEvent(e)

    def keyPressEvent(self, e):
        k = e.key()
        if k == Qt.Key.Key_Escape:
            self._cancel_draw(); self.set_select_mode("object")
        elif k == Qt.Key.Key_O:
            self.set_select_mode("object")
        elif k == Qt.Key.Key_E:
            self.set_select_mode("edge")
        elif k == Qt.Key.Key_V:
            self.set_select_mode("vertex")
        elif k == Qt.Key.Key_F:
            self.set_select_mode("face")
        super().keyPressEvent(e)

    # --- drawing helpers -------------------------------------------------
    def _fake_left(self, e):
        from PyQt6.QtGui import QMouseEvent
        return QMouseEvent(e.type(), e.position(), e.globalPosition(),
                           Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
                           e.modifiers())

    def _clear_preview(self):
        if self._preview is not None:
            self._scene.removeItem(self._preview)
            self._preview = None

    def _preview_item(self, path: QPainterPath):
        self._clear_preview()
        it = QGraphicsPathItem(path)
        pen = QPen(PREVIEW, 0)
        pen.setCosmetic(True)
        pen.setStyle(Qt.PenStyle.DashLine)
        it.setPen(pen)
        # only closed primitives (circle/rect) get a faint fill; polyline/arc/
        # spline previews are outline-only so an open curve doesn't look filled
        if self.tool in ("circle", "rect"):
            it.setBrush(QBrush(QColor(47, 95, 143, 50)))
        else:
            it.setBrush(QBrush())
        self._scene.addItem(it)
        self._preview = it

    def _update_preview(self, p: QPointF):
        path = QPainterPath()
        if self.tool == "circle":
            cx = (self._start.x() + p.x()) / 2; cy = (self._start.y() + p.y()) / 2
            r = ((p.x() - self._start.x()) ** 2 + (p.y() - self._start.y()) ** 2) ** .5 / 2
            path.addEllipse(QPointF(cx, cy), r, r)
        else:
            path.addRect(QRectF(self._start, p).normalized())
        self._preview_item(path)

    def _update_poly_preview(self, p: QPointF):
        path = QPainterPath()
        path.addPolygon(QPolygonF(list(self._poly_pts) + [p]))
        self._preview_item(path)

    @property
    def _arc_mode(self) -> bool:           # compat: CenterPointArc active
        return self._edge_type == "cpa"

    def set_arc_mode(self, on: bool):
        self.set_edge_type("cpa" if on else "straight")

    def set_edge_type(self, t: str):
        """Polyline segment edge type: straight | cpa | 3pa | spline."""
        self._edge_type = t
        self._arc_center = None
        self._arc3_mid = None
        if self._poly_pts:
            self._edge_prompt()

    def _edge_prompt(self):
        msg = {"straight": "Polyline: pick next point (right-click → Done)",
               "cpa": "CenterPointArc: pick centre point",
               "3pa": "3 Point Arc: pick a point on the arc",
               "spline": "Spline: pick next point"}.get(self._edge_type, "")
        self.promptChanged.emit(msg)

    def _add_line_segment(self, p: QPointF):
        import math
        prev = self._poly_pts[-1]
        self._poly_segs.append({
            "type": "line",
            "length": ((p.x() - prev.x()) ** 2 + (p.y() - prev.y()) ** 2) ** .5,
            "dir": math.degrees(math.atan2(p.y() - prev.y(), p.x() - prev.x())),
        })
        self._poly_pts.append(p)

    def _three_point_arc(self, S, M, E):
        """Arc through start S, mid M, end E -> (points excluding S, seg dict)."""
        import math
        ax, ay = S.x(), S.y(); bx, by = M.x(), M.y(); cx, cy = E.x(), E.y()
        d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
        if abs(d) < 1e-9:
            self._poly_segs_tmp = {"type": "line",
                                   "length": math.hypot(cx - ax, cy - ay),
                                   "dir": math.degrees(math.atan2(cy - ay, cx - ax))}
            return [E]
        a2 = ax * ax + ay * ay; b2 = bx * bx + by * by; c2 = cx * cx + cy * cy
        ux = (a2 * (by - cy) + b2 * (cy - ay) + c2 * (ay - by)) / d
        uy = (a2 * (cx - bx) + b2 * (ax - cx) + c2 * (bx - ax)) / d
        r = math.hypot(ax - ux, ay - uy)
        a0 = math.atan2(ay - uy, ax - ux); am = math.atan2(by - uy, bx - ux)
        a1 = math.atan2(cy - uy, cx - ux); tau = 2 * math.pi
        d_ccw = (a1 - a0) % tau; m_ccw = (am - a0) % tau
        sweep = d_ccw if m_ccw <= d_ccw else d_ccw - tau
        n = max(4, int(abs(sweep) / (math.pi / 24)))
        pts = [QPointF(ux + r * math.cos(a0 + sweep * i / n),
                       uy + r * math.sin(a0 + sweep * i / n)) for i in range(1, n + 1)]
        self._poly_segs_tmp = {"type": "arc", "cx_off": ux - ax, "cy_off": uy - ay,
                               "angle": math.degrees(sweep)}
        return pts

    def _update_3pt_preview(self, E: QPointF):
        pts = self._three_point_arc(self._poly_pts[-1], self._arc3_mid, E)
        path = QPainterPath()
        path.addPolygon(QPolygonF(list(self._poly_pts) + pts))
        self._preview_item(path)

    def _finalize_3pt_arc(self, E: QPointF):
        pts = self._three_point_arc(self._poly_pts[-1], self._arc3_mid, E)
        self._poly_pts.extend(pts)
        self._poly_segs.append(self._poly_segs_tmp)
        self._arc3_mid = None
        self.promptChanged.emit("Polyline: next point (right-click → Done)")

    def _begin_arc(self, C: QPointF):
        """Centre clicked: start tracking the sweep angle from the cursor."""
        import math
        S = self._poly_pts[-1]
        self._arc_center = C
        self._arc_start_ang = math.atan2(S.y() - C.y(), S.x() - C.x())
        self._arc_last_ang = self._arc_start_ang
        self._arc_sweep = 0.0
        self.promptChanged.emit("CenterPointArc: move to sweep the arc, click end")

    def _track_arc(self, M: QPointF):
        """Accumulate sweep as the cursor orbits the centre (allows >180°)."""
        import math
        C = self._arc_center
        cur = math.atan2(M.y() - C.y(), M.x() - C.x())
        d = cur - self._arc_last_ang
        while d <= -math.pi:
            d += 2 * math.pi
        while d > math.pi:
            d -= 2 * math.pi
        self._arc_sweep += d
        self._arc_last_ang = cur
        pts = self._arc_points_from_sweep(self._poly_pts[-1], C, self._arc_sweep)
        path = QPainterPath()
        path.addPolygon(QPolygonF(list(self._poly_pts) + pts))
        self._preview_item(path)

    def _arc_points_from_sweep(self, S: QPointF, C: QPointF, sweep: float):
        import math
        r = math.hypot(S.x() - C.x(), S.y() - C.y())
        a0 = math.atan2(S.y() - C.y(), S.x() - C.x())
        n = max(4, int(abs(sweep) / (math.pi / 24)))
        return [QPointF(C.x() + r * math.cos(a0 + sweep * i / n),
                        C.y() + r * math.sin(a0 + sweep * i / n))
                for i in range(1, n + 1)]

    def _finalize_arc(self, E: QPointF):
        import math
        C = self._arc_center; S = self._poly_pts[-1]
        sweep = self._arc_sweep
        if abs(sweep) < 1e-3:             # no mouse travel -> shortest arc to end
            aE = math.atan2(E.y() - C.y(), E.x() - C.x())
            sweep = aE - self._arc_start_ang
            while sweep <= -math.pi:
                sweep += 2 * math.pi
            while sweep > math.pi:
                sweep -= 2 * math.pi
        pts = self._arc_points_from_sweep(S, C, sweep)
        self._poly_pts.extend(pts)
        self._poly_segs.append({"type": "arc", "cx_off": C.x() - S.x(),
                                "cy_off": C.y() - S.y(),
                                "angle": math.degrees(sweep)})
        self._arc_center = None; self._arc_start_ang = None
        self._arc_last_ang = None; self._arc_sweep = 0.0
        self.promptChanged.emit("Polyline: next point (right-click → Done)")

    def _commit(self, p: QPointF):
        self._clear_preview()
        if self.tool == "circle":
            cx = (self._start.x() + p.x()) / 2; cy = (self._start.y() + p.y()) / 2
            r = ((p.x() - self._start.x()) ** 2 + (p.y() - self._start.y()) ** 2) ** .5 / 2
            if r < 1e-6:
                return
            self._naming["circle"] += 1
            s = Shape.circle(f"Circle{self._naming['circle']}", cx, cy, r)
        else:
            rect = QRectF(self._start, p).normalized()
            if rect.width() < 1e-6 or rect.height() < 1e-6:
                return
            self._naming["rect"] += 1
            s = Shape.rectangle(f"Rectangle{self._naming['rect']}",
                                rect.left(), rect.top(),
                                rect.right(), rect.bottom())
        self.add_shape(s)
        self.shapeCreated.emit(s)

    def _update_spline_preview(self, p: QPointF):
        from ..model.geometry import spline_points
        ctrl = [(q.x(), q.y()) for q in self._poly_pts] + [(p.x(), p.y())]
        pts = spline_points(ctrl, closed=False) if len(ctrl) >= 3 else ctrl
        path = QPainterPath()
        path.addPolygon(QPolygonF([QPointF(x, y) for x, y in pts]))
        self._preview_item(path)

    def _finish_spline(self, closed: bool = False):
        from ..model.geometry import spline_points
        if len(self._poly_pts) >= 3:
            ctrl = [(q.x(), q.y()) for q in self._poly_pts]
            pts = spline_points(ctrl, closed=closed)
            self._naming["spline"] += 1
            name = f"Spline{self._naming['spline']}"
            s = (Shape.polygon(name, pts) if closed
                 else Shape.open_polyline(name, pts))
            s.cmd = {"kind": "CreateSpline", "control": ctrl, "points": pts,
                     "closed": closed}
            self.add_shape(s)
            self.shapeCreated.emit(s)
        self._cancel_draw()

    def _finish_polygon(self, closed: bool = False):
        need = 3 if closed else 2
        if len(self._poly_pts) >= need:
            self._naming["polygon"] += 1
            pts = [(q.x(), q.y()) for q in self._poly_pts]
            name = f"Polyline{self._naming['polygon']}"
            s = (Shape.polygon(name, pts) if closed
                 else Shape.open_polyline(name, pts))
            if self._poly_start is not None and self._poly_segs:
                s.cmd["start"] = (self._poly_start.x(), self._poly_start.y())
                s.cmd["segments"] = list(self._poly_segs)
            self.add_shape(s)
            self.shapeCreated.emit(s)
        self._cancel_draw()

    def _cancel_draw(self):
        self._drawing = False
        self._poly_pts = []
        self._pts = []
        self._arc_center = None
        self._arc_start_ang = None
        self._arc_last_ang = None
        self._arc_sweep = 0.0
        self._arc3_mid = None
        self._poly_segs = []
        self._poly_start = None
        self._clear_preview()

    # --- circle: centre then radius (drag OR two clicks both work) ------
    def _finalize_circle(self, p: QPointF):
        if not self._pts:
            return
        c = self._pts[0]
        r = ((p.x() - c.x()) ** 2 + (p.y() - c.y()) ** 2) ** .5
        self._pts = []
        self._cpress_view = None
        self._clear_preview()
        self.promptChanged.emit("Circle: pick centre")
        if r > 1e-6:
            self._naming["circle"] += 1
            s = Shape.circle(f"Circle{self._naming['circle']}", c.x(), c.y(), r)
            self.add_shape(s)
            self.shapeCreated.emit(s)

    def _update_circle_preview(self, p: QPointF):
        c = self._pts[0]
        r = ((p.x() - c.x()) ** 2 + (p.y() - c.y()) ** 2) ** .5
        path = QPainterPath(); path.addEllipse(c, r, r)
        self._preview_item(path)

    def last_point(self) -> QPointF:
        if self.tool == "circle" and self._pts:
            return self._pts[-1]
        if self.tool == "rect" and self._drawing:
            return self._start
        if self.tool == "polygon" and self._poly_pts:
            return self._poly_pts[-1]
        return QPointF(0, 0)

    def submit_point(self, x: float, y: float):
        """Place a draw point from the coordinate-entry bar (typed input)."""
        p = QPointF(x, y)
        if self.tool in ("circle", "rect"):
            if not self._drawing:
                self._drawing = True; self._start = p
                self.promptChanged.emit(
                    ("Circle" if self.tool == "circle" else "Rectangle")
                    + ": enter the opposite point")
            else:
                self._commit(p); self._drawing = False
        elif self.tool == "polygon":
            self._poly_pts.append(p)
            self.promptChanged.emit("Polyline: pick next point (right-click to finish)")

    # --- background grid / axes -----------------------------------------
    def drawBackground(self, painter: QPainter, rect: QRectF):
        super().drawBackground(painter, rect)
        # adaptive grid step based on current zoom
        unit_px = self.transform().m11()
        step = 1.0
        for cand in (0.1, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500):
            if cand * unit_px >= 18:
                step = cand
                break
        left = np.floor(rect.left() / step) * step
        top = np.floor(rect.top() / step) * step
        pen = QPen(self.c_grid, 0); pen.setCosmetic(True)
        major = QPen(self.c_grid_major, 0); major.setCosmetic(True)
        x = left
        while x <= rect.right():
            pen2 = major if abs(x % (step * 5)) < step * .01 else pen
            painter.setPen(pen2)
            painter.drawLine(QPointF(x, rect.top()), QPointF(x, rect.bottom()))
            x += step
        y = top
        while y <= rect.bottom():
            pen2 = major if abs(y % (step * 5)) < step * .01 else pen
            painter.setPen(pen2)
            painter.drawLine(QPointF(rect.left(), y), QPointF(rect.right(), y))
            y += step
        # axes
        ax = QPen(self.c_axis_x, 0); ax.setCosmetic(True); ax.setWidth(2)
        ay = QPen(self.c_axis_y, 0); ay.setCosmetic(True); ay.setWidth(2)
        painter.setPen(ax)
        painter.drawLine(QPointF(rect.left(), 0), QPointF(rect.right(), 0))
        painter.setPen(ay)
        painter.drawLine(QPointF(0, rect.top()), QPointF(0, rect.bottom()))

    def _draw_colorbar(self, painter, bmax):
        """Vertical |B| legend, drawn in viewport (device) pixels."""
        painter.save()
        painter.resetTransform()
        vw = self.viewport().width()
        x = vw - 74; y = 34; w = 16; h = 200
        for i in range(h):
            painter.setPen(QPen(_jet(1 - i / h)))
            painter.drawLine(x, y + i, x + w, y + i)
        painter.setPen(QPen(QColor("#cfe0ee")))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(x, y, w, h)
        fnt = painter.font(); fnt.setPointSize(8); painter.setFont(fnt)
        painter.drawText(x - 4, y - 8, "B [T]")
        painter.drawText(x + w + 4, y + 9, f"{bmax:.2f}")
        painter.drawText(x + w + 4, y + h // 2 + 4, f"{bmax / 2:.2f}")
        painter.drawText(x + w + 4, y + h, "0.00")
        painter.restore()

    def drawForeground(self, painter: QPainter, rect: QRectF):
        super().drawForeground(painter, rect)
        # B-field overlay — fill each triangle by |B| (jet colormap)
        if self.show_field and self.field is not None:
            f = self.field
            bmax = f.bmax or 1.0
            nodes = f.nodes
            painter.setPen(Qt.PenStyle.NoPen)
            for k, (a, b, c) in enumerate(f.triangles):
                t = min(f.Bmag[k] / bmax, 1.0)
                painter.setBrush(QBrush(_jet(t)))
                painter.drawPolygon(QPolygonF([
                    QPointF(*nodes[a]), QPointF(*nodes[b]), QPointF(*nodes[c])]))
            self._draw_colorbar(painter, bmax)
        # snap marker — triangle=close, square=vertex, cross=grid
        if self._snap_marker is not None:
            mx, my, kind = self._snap_marker
            hs = 7 / max(self.transform().m11(), 1e-6)
            col = "#39c06a" if kind == "close" else "#e6a23c"
            pen = QPen(QColor(col), 0); pen.setCosmetic(True); pen.setWidth(2)
            painter.setPen(pen); painter.setBrush(Qt.BrushStyle.NoBrush)
            if kind == "close":
                tri = QPolygonF([QPointF(mx, my - hs), QPointF(mx - hs, my + hs),
                                 QPointF(mx + hs, my + hs)])
                painter.drawPolygon(tri)
            elif kind == "vertex":
                painter.drawRect(QRectF(mx - hs, my - hs, 2 * hs, 2 * hs))
            else:                                   # grid -> small cross
                painter.drawLine(QPointF(mx - hs, my), QPointF(mx + hs, my))
                painter.drawLine(QPointF(mx, my - hs), QPointF(mx, my + hs))
        if not (self.show_mesh and self.mesh is not None):
            return
        pen = QPen(self.c_mesh, 0)
        pen.setCosmetic(True)
        painter.setPen(pen)
        nodes = self.mesh.nodes
        for a, b, c in self.mesh.triangles:
            pa, pb, pc = nodes[a], nodes[b], nodes[c]
            painter.drawLine(QPointF(*pa), QPointF(*pb))
            painter.drawLine(QPointF(*pb), QPointF(*pc))
            painter.drawLine(QPointF(*pc), QPointF(*pa))
