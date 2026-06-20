"""A lightweight ribbon bar mimicking Ansys Electronics Desktop.

Tabs hold horizontal groups; each group is a row of tool buttons with a caption
underneath, separated by vertical rules — the AEDT ribbon idiom.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, QSize
from PyQt6.QtWidgets import (QTabWidget, QWidget, QHBoxLayout, QVBoxLayout,
                             QToolButton, QLabel, QFrame, QButtonGroup)

from .icons import icon as make_icon


class RibbonGroup(QFrame):
    def __init__(self, title: str):
        super().__init__()
        self.setObjectName("ribbonGroup")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(6, 4, 6, 2)
        outer.setSpacing(2)
        self._row = QHBoxLayout()
        self._row.setSpacing(2)
        self._row.setContentsMargins(0, 0, 0, 0)
        roww = QWidget(); roww.setLayout(self._row)
        outer.addWidget(roww, 1)
        cap = QLabel(title); cap.setObjectName("ribbonCaption")
        cap.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        outer.addWidget(cap)

    def add_button(self, text, callback=None, checkable=False, group=None,
                   icon=None):
        b = QToolButton()
        b.setText(text)
        b.setCheckable(checkable)
        if icon:
            b.setIcon(make_icon(icon))
            b.setIconSize(QSize(22, 22))
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        else:
            b.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        b.setObjectName("ribbonButton")
        b.setToolTip(text)
        if callback:
            b.clicked.connect(lambda _=False: callback())
        self._row.addWidget(b)
        if group is not None:
            group.addButton(b)
        return b


class RibbonTab(QWidget):
    def __init__(self):
        super().__init__()
        self._lay = QHBoxLayout(self)
        self._lay.setContentsMargins(4, 2, 4, 2)
        self._lay.setSpacing(0)
        self._lay.setAlignment(Qt.AlignmentFlag.AlignLeft)

    def add_group(self, title: str) -> RibbonGroup:
        g = RibbonGroup(title)
        self._lay.addWidget(g)
        sep = QFrame(); sep.setFrameShape(QFrame.Shape.VLine)
        sep.setObjectName("ribbonSep")
        self._lay.addWidget(sep)
        return g

    def finish(self):
        self._lay.addStretch(1)


class RibbonBar(QTabWidget):
    def __init__(self):
        super().__init__()
        self.setObjectName("ribbon")
        self.setMaximumHeight(108)
        self.setMinimumHeight(108)

    def add_tab(self, name: str) -> RibbonTab:
        t = RibbonTab()
        self.addTab(t, name)
        return t
