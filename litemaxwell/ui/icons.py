"""Programmatically drawn ribbon icons (no proprietary assets).

Simple, recognizable CAD glyphs so the ribbon reads like a tool ribbon rather
than a row of text buttons. Each icon is a 22x22 QIcon.
"""
from __future__ import annotations

from functools import lru_cache

from PyQt6.QtCore import Qt, QRectF, QPointF
from PyQt6.QtGui import (QIcon, QPixmap, QPainter, QPen, QColor, QBrush,
                         QPolygonF, QPainterPath)

S = 22
BLUE = "#3b78c4"
STEEL = "#5a6b7b"
AMBER = "#e6a23c"
RED = "#c0392b"
GREEN = "#2e9e5b"


def _new():
    pm = QPixmap(S, S)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    return pm, p


def _pen(p, color, w=1.8):
    pen = QPen(QColor(color)); pen.setWidthF(w)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(pen); p.setBrush(Qt.BrushStyle.NoBrush)
    return p


@lru_cache(maxsize=64)
def icon(kind: str) -> QIcon:
    pm, p = _new()
    if kind == "select":
        _pen(p, "#cdd6df", 1.4)
        p.setBrush(QBrush(QColor("#cdd6df")))
        poly = QPolygonF([QPointF(5, 3), QPointF(5, 17), QPointF(9, 13),
                          QPointF(12, 19), QPointF(14, 18), QPointF(11, 12),
                          QPointF(16, 12)])
        p.drawPolygon(poly)
    elif kind == "circle":
        _pen(p, BLUE); p.drawEllipse(QRectF(3, 3, 16, 16))
    elif kind == "rect":
        _pen(p, BLUE); p.drawRect(QRectF(3, 5, 16, 12))
    elif kind == "polyline":
        _pen(p, BLUE)
        path = QPainterPath(QPointF(3, 16)); path.lineTo(8, 6)
        path.lineTo(13, 14); path.lineTo(19, 4); p.drawPath(path)
    elif kind == "spline":
        _pen(p, BLUE)
        path = QPainterPath(); path.moveTo(3, 16)
        path.cubicTo(7, 2, 14, 22, 19, 7)
        p.drawPath(path)
    elif kind == "osnap":
        _pen(p, AMBER, 1.8); p.drawRect(QRectF(5, 5, 12, 12))
        p.setBrush(QBrush(QColor(BLUE))); _pen(p, BLUE, 0.5)
        p.drawEllipse(QRectF(9, 9, 4, 4))
    elif kind == "arc":
        _pen(p, BLUE)
        path = QPainterPath(); path.moveTo(4, 18)
        path.arcTo(QRectF(4, 4, 28, 28), 180, -90)
        p.drawPath(path)
        p.setBrush(QBrush(QColor(BLUE))); _pen(p, BLUE, 0.5)
        for x, y in ((4, 18), (18, 4)):
            p.drawEllipse(QRectF(x - 2, y - 2, 4, 4))
    elif kind == "circledim":
        _pen(p, BLUE); p.drawEllipse(QRectF(4, 4, 14, 14))
        _pen(p, AMBER, 1.3); p.drawLine(2, 20, 20, 20)
        p.drawLine(2, 18, 2, 22); p.drawLine(20, 18, 20, 22)
    elif kind == "rectdim":
        _pen(p, BLUE); p.drawRect(QRectF(4, 5, 14, 10))
        _pen(p, AMBER, 1.3); p.drawLine(2, 20, 20, 20)
        p.drawLine(2, 18, 2, 22); p.drawLine(20, 18, 20, 22)
    elif kind == "around":
        _pen(p, STEEL, 1.5); p.drawEllipse(QRectF(6, 6, 10, 10))
        p.setBrush(QBrush(QColor(BLUE))); _pen(p, BLUE, 0.5)
        for x, y in ((10, 1), (19, 10), (10, 19), (1, 10)):
            p.drawEllipse(QRectF(x - 2, y - 2, 4, 4))
    elif kind == "along":
        p.setBrush(QBrush(QColor(BLUE))); _pen(p, BLUE, 0.5)
        for x in (3, 9, 15):
            p.drawRect(QRectF(x, 8, 5, 6))
    elif kind == "mirror":
        _pen(p, AMBER, 1.0); pen = p.pen(); pen.setStyle(Qt.PenStyle.DashLine)
        p.setPen(pen); p.drawLine(11, 2, 11, 20)
        _pen(p, BLUE); p.setBrush(QBrush(QColor(59, 120, 196, 80)))
        p.drawPolygon(QPolygonF([QPointF(3, 4), QPointF(9, 11), QPointF(3, 18)]))
        p.drawPolygon(QPolygonF([QPointF(19, 4), QPointF(13, 11), QPointF(19, 18)]))
    elif kind == "unite":
        p.setBrush(QBrush(QColor(59, 120, 196, 140))); _pen(p, BLUE)
        p.drawEllipse(QRectF(3, 5, 12, 12)); p.drawEllipse(QRectF(8, 5, 12, 12))
    elif kind == "subtract":
        p.setBrush(QBrush(QColor(59, 120, 196, 140))); _pen(p, BLUE)
        p.drawEllipse(QRectF(3, 5, 12, 12))
        p.setBrush(QBrush(QColor("#1b1f24"))); _pen(p, STEEL, 1.2)
        p.drawEllipse(QRectF(9, 5, 12, 12))
    elif kind == "delete":
        _pen(p, RED, 2.2); p.drawLine(5, 5, 17, 17); p.drawLine(17, 5, 5, 17)
    elif kind in ("mesh", "showmesh"):
        col = STEEL if kind == "mesh" else AMBER
        _pen(p, col, 1.1)
        pts = [QPointF(3, 18), QPointF(8, 5), QPointF(13, 17),
               QPointF(18, 4), QPointF(20, 18)]
        for a in pts:
            for b in pts:
                if a != b:
                    p.drawLine(a, b)
    elif kind == "material":
        for i, c in enumerate((RED, AMBER, GREEN, BLUE)):
            p.setBrush(QBrush(QColor(c))); _pen(p, "#11151a", 0.6)
            p.drawRect(QRectF(3 + (i % 2) * 8, 3 + (i // 2) * 8, 7, 7))
    elif kind == "editmat":
        p.setBrush(QBrush(QColor(BLUE))); _pen(p, "#11151a", 0.6)
        p.drawRect(QRectF(3, 3, 11, 11))
        _pen(p, AMBER, 2.0); p.drawLine(11, 19, 19, 11)
    elif kind == "newmat":
        p.setBrush(QBrush(QColor(BLUE))); _pen(p, "#11151a", 0.6)
        p.drawRect(QRectF(3, 3, 11, 11))
        _pen(p, GREEN, 2.2); p.drawLine(16, 12, 16, 20); p.drawLine(12, 16, 20, 16)
    elif kind == "save":
        p.setBrush(QBrush(QColor(BLUE))); _pen(p, BLUE, 1.0)
        p.drawRect(QRectF(3, 3, 16, 16))
        p.setBrush(QBrush(QColor("#e8eef4"))); p.drawRect(QRectF(7, 12, 8, 7))
        p.setBrush(QBrush(QColor("#cdd6df"))); p.drawRect(QRectF(11, 4, 3, 5))
    elif kind == "open":
        p.setBrush(QBrush(QColor(AMBER))); _pen(p, "#a87a2a", 1.0)
        p.drawRect(QRectF(3, 7, 16, 11))
        p.drawPolygon(QPolygonF([QPointF(3, 7), QPointF(7, 4),
                                 QPointF(12, 4), QPointF(13, 7)]))
    elif kind == "new":
        p.setBrush(QBrush(QColor("#e8eef4"))); _pen(p, STEEL, 1.0)
        p.drawPolygon(QPolygonF([QPointF(5, 3), QPointF(14, 3), QPointF(18, 7),
                                 QPointF(18, 19), QPointF(5, 19)]))
    elif kind == "fit":
        _pen(p, GREEN, 1.8)
        for (x, y, dx, dy) in ((3, 3, 1, 1), (19, 3, -1, 1),
                               (3, 19, 1, -1), (19, 19, -1, -1)):
            p.drawLine(int(x), int(y), int(x + dx * 5), int(y))
            p.drawLine(int(x), int(y), int(x), int(y + dy * 5))
    elif kind == "snap":
        p.setBrush(QBrush(QColor(STEEL))); _pen(p, STEEL, 0.5)
        for gx in (4, 11, 18):
            for gy in (4, 11, 18):
                p.drawEllipse(QRectF(gx - 1.3, gy - 1.3, 2.6, 2.6))
    elif kind == "analyze":
        p.setBrush(QBrush(QColor(GREEN))); _pen(p, GREEN, 0.5)
        p.drawPolygon(QPolygonF([QPointF(6, 4), QPointF(6, 18), QPointF(18, 11)]))
    elif kind == "report":
        _pen(p, STEEL, 1.2); p.drawLine(4, 3, 4, 19); p.drawLine(4, 19, 20, 19)
        p.setBrush(QBrush(QColor(BLUE))); _pen(p, BLUE, 0.5)
        for i, h in enumerate((5, 9, 6, 11)):
            p.drawRect(QRectF(6 + i * 3.5, 18 - h, 2.6, h))
    elif kind == "theme":
        _pen(p, AMBER, 1.4); p.setBrush(QBrush(QColor(AMBER)))
        p.drawEllipse(QRectF(7, 7, 8, 8))
        p.setBrush(QBrush(QColor("#11151a")))
        p.drawEllipse(QRectF(10, 5, 8, 8))
    elif kind == "motor":
        _pen(p, STEEL, 1.5); p.drawEllipse(QRectF(2, 2, 18, 18))
        p.setBrush(QBrush(QColor(RED))); _pen(p, RED, 0.5)
        p.drawEllipse(QRectF(8, 8, 6, 6))
        _pen(p, AMBER, 1.4)
        for x1, y1, x2, y2 in ((11, 2, 11, 7), (11, 15, 11, 20),
                               (2, 11, 7, 11), (15, 11, 20, 11)):
            p.drawLine(x1, y1, x2, y2)
    elif kind == "hamburger":
        _pen(p, "#cfe0ee", 1.8)
        for y in (6, 11, 16):
            p.drawLine(4, y, 18, y)
    elif kind == "panel":
        _pen(p, "#cfe0ee", 1.5); p.drawRoundedRect(QRectF(3, 4, 16, 14), 2, 2)
        p.drawLine(9, 4, 9, 18)
    elif kind == "search":
        _pen(p, "#cfe0ee", 1.8); p.drawEllipse(QRectF(4, 4, 10, 10))
        p.drawLine(13, 13, 18, 18)
    elif kind == "back":
        _pen(p, "#cfe0ee", 1.8)
        p.drawLine(14, 5, 8, 11); p.drawLine(8, 11, 14, 17)
    elif kind == "fwd":
        _pen(p, "#cfe0ee", 1.8)
        p.drawLine(8, 5, 14, 11); p.drawLine(14, 11, 8, 17)
    elif kind == "win_min":
        _pen(p, "#cfe0ee", 1.4); p.drawLine(6, 12, 16, 12)
    elif kind == "win_max":
        _pen(p, "#cfe0ee", 1.4); p.drawRect(QRectF(6, 6, 10, 10))
    elif kind == "win_restore":
        _pen(p, "#cfe0ee", 1.3)
        p.drawRect(QRectF(7, 8, 8, 8)); p.drawLine(9, 8, 9, 6)
        p.drawLine(9, 6, 17, 6); p.drawLine(17, 6, 17, 14); p.drawLine(17, 14, 15, 14)
    elif kind == "win_close":
        _pen(p, "#e06c7a", 1.6); p.drawLine(6, 6, 16, 16); p.drawLine(16, 6, 6, 16)
    else:
        _pen(p, STEEL); p.drawRect(QRectF(4, 4, 14, 14))
    p.end()
    return QIcon(pm)
