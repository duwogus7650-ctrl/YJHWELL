"""AEDT-style Properties panel: tabbed grid (Attribute / Command / Variables)
with columns Name | Value | Unit | Evaluated Value | Type.

The Command tab is editable for dimension fields (Center Position, Radius, …)
so dimensions are set exactly like Maxwell's CreateCircle command properties.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QTabWidget, QTableWidget, QTableWidgetItem,
                             QComboBox, QPushButton)

COLS = ["Name", "Value", "Unit", "Evaluated Value", "Type"]
EDITABLE_CMD = {"Center Position", "Radius", "Number of Segments",
                "Position", "X Size", "Y Size"}


class _Grid(QTableWidget):
    def __init__(self):
        super().__init__(0, len(COLS))
        self.setHorizontalHeaderLabels(COLS)
        self.verticalHeader().setVisible(False)
        self.horizontalHeader().setStretchLastSection(True)
        self.setColumnWidth(0, 130); self.setColumnWidth(1, 140)

    def set_rows(self, rows, editable_keys=(), value_editable=False):
        self.blockSignals(True)
        self.setRowCount(0)
        for r in rows:
            i = self.rowCount(); self.insertRow(i)
            for c, val in enumerate(r):
                it = QTableWidgetItem(str(val))
                editable = (c == 1 and (value_editable or r[0] in editable_keys))
                if not editable:
                    it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.setItem(i, c, it)
        self.blockSignals(False)


class PropertiesPanel(QTabWidget):
    nameChanged = pyqtSignal(str)
    materialChanged = pyqtSignal(str)
    colorRequested = pyqtSignal()
    commandEdited = pyqtSignal(str, str)      # (field, new value)
    variableEdited = pyqtSignal(str, str)     # (var name, new expr/value)

    def __init__(self):
        super().__init__()
        self.setTabPosition(QTabWidget.TabPosition.South)
        self._shape = None
        self._materials = []

        self.attr = _Grid(); self.cmd = _Grid(); self.vars = _Grid()
        self.addTab(self.vars, "Variables")     # Variables first
        self.addTab(self.attr, "Attribute")
        self.addTab(self.cmd, "Command")
        self.setCurrentWidget(self.vars)
        self.attr.itemChanged.connect(self._attr_edited)
        self.cmd.itemChanged.connect(self._cmd_edited)
        self.vars.itemChanged.connect(self._var_edited)

    # -- population -----------------------------------------------------
    def set_materials(self, names):
        self._materials = list(names)

    def show_shape(self, shape):
        self._shape = shape
        if shape is None:
            self.attr.set_rows([]); self.cmd.set_rows([])
            self.setCurrentWidget(self.vars)
            return
        self.setCurrentWidget(self.attr)     # selecting an object -> Attribute
        self.attr.set_rows([
            ["Name", shape.name, "", "", ""],
            ["Material", shape.material, "", "", ""],
            ["Solve Inside", "True", "", "", ""],
            ["Orientation", "Global", "", "", ""],
            ["Model", "True", "", "", ""],
            ["Group", "Model", "", "", ""],
            ["Color", shape.color, "", "", ""],
            ["Transparent", "0", "", "", ""],
        ])
        combo = QComboBox(); combo.addItems(self._materials)
        i = combo.findText(shape.material)
        if i >= 0:
            combo.setCurrentIndex(i)
        combo.currentTextChanged.connect(self.materialChanged)
        self.attr.setCellWidget(1, 1, combo)
        btn = QPushButton(shape.color); btn.clicked.connect(self.colorRequested)
        self.attr.setCellWidget(6, 1, btn)
        self.cmd.set_rows(*self._cmd_rows(shape))

    def _cmd_rows(self, shape):
        c = shape.cmd or {}
        kind = c.get("kind", "Create")
        rows = [["Command", kind, "", "", ""],
                ["Coordinate System", "Global", "", "", ""]]
        if kind == "CreateCircle":
            rows += [
                ["Center Position", f"{c['cx']:g} , {c['cy']:g} , 0", "mm",
                 f"{c['cx']:g}mm , {c['cy']:g}mm , 0mm", ""],
                ["Axis", "Z", "", "", ""],
                ["Radius", f"{c['r']:g}", "mm", f"{c['r']:g}mm", ""],
                ["Number of Segments", f"{int(c.get('segs', 0))}", "", "", ""],
            ]
        elif kind == "CreateRectangle":
            rows += [
                ["Position", f"{c['x0']:g} , {c['y0']:g} , 0", "mm", "", ""],
                ["Axis", "Z", "", "", ""],
                ["X Size", f"{c['x1'] - c['x0']:g}", "mm", "", ""],
                ["Y Size", f"{c['y1'] - c['y0']:g}", "mm", "", ""],
            ]
        elif kind == "CreatePolyline":
            rows += [["Number of points", str(len(c.get("points", []))), "", "", ""]]
        return rows, EDITABLE_CMD

    def show_variables(self, rows):
        """rows: iterable of (name, expr, evaluated). Value column is editable."""
        self.vars.set_rows([[n, e, "mm", ev, "Design"] for n, e, ev in rows],
                           value_editable=True)

    def _var_edited(self, item):
        if item.column() != 1:
            return
        name = self.vars.item(item.row(), 0).text()
        self.variableEdited.emit(name, item.text())

    # -- edits ----------------------------------------------------------
    def _attr_edited(self, item):
        if self._shape is None or item.column() != 1:
            return
        if self.attr.item(item.row(), 0).text() == "Name":
            self.nameChanged.emit(item.text())

    def _cmd_edited(self, item):
        if self._shape is None or item.column() != 1:
            return
        key = self.cmd.item(item.row(), 0).text()
        if key in EDITABLE_CMD:
            self.commandEdited.emit(key, item.text())
