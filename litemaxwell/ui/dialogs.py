"""Small parametric dialogs for precise drawing and Maxwell-style duplication."""
from __future__ import annotations

from PyQt6.QtWidgets import (QDialog, QFormLayout, QDoubleSpinBox, QSpinBox,
                             QComboBox, QDialogButtonBox, QLineEdit, QPushButton,
                             QColorDialog)
from PyQt6.QtGui import QColor


def _spin(lo, hi, dec, val=0.0, step=1.0):
    s = QDoubleSpinBox(); s.setRange(lo, hi); s.setDecimals(dec)
    s.setValue(val); s.setSingleStep(step); s.setMinimumWidth(140)
    return s


class _Base(QDialog):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.form = QFormLayout(self)

    def _add_buttons(self):
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        self.form.addRow(bb)


class SegmentDialog(QDialog):
    """Per-segment properties, type-specific (faithful to Maxwell):
    Line -> Point1/Point2 ; Center Point Arc -> Start/Centre/Angle/Plane.
    """

    def __init__(self, shape, index, evaluate=None, on_apply=None, parent=None):
        super().__init__(parent)
        import math
        from PyQt6.QtWidgets import QVBoxLayout, QTableWidget, QTableWidgetItem
        from PyQt6.QtCore import Qt
        from ..model.geometry import segment_geometry
        self.shape = shape
        self.index = index
        self._eval = evaluate or (lambda s: float(s))
        self._on_apply = on_apply
        seg = shape.cmd["segments"][index]
        info = segment_geometry(shape.cmd["start"], shape.cmd["segments"])[index]
        self._is_line = seg["type"] == "line"
        kind = "CreateLine" if self._is_line else "CreateAngularArc"
        self.setWindowTitle(f"Properties: {shape.name} — {kind}")
        self.resize(640, 320)
        root = QVBoxLayout(self)
        self.tbl = QTableWidget(0, 5)
        self.tbl.setHorizontalHeaderLabels(
            ["Name", "Value", "Unit", "Evaluated Value", "Description"])
        self.tbl.horizontalHeader().setStretchLastSection(True)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setColumnWidth(0, 140); self.tbl.setColumnWidth(1, 170)
        root.addWidget(self.tbl, 1)
        self._rows = {}
        self._all_rows = {}

        def fmt(p):
            return f"{p[0]:g} ,{p[1]:g} ,0"

        def add(name, value, unit="", evald="", editable=False):
            r = self.tbl.rowCount(); self.tbl.insertRow(r)
            for c, v in enumerate((name, value, unit, evald, "")):
                it = QTableWidgetItem(str(v))
                if not (c == 1 and editable):
                    it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.tbl.setItem(r, c, it)
            self._all_rows[name] = r
            if editable:
                self._rows[name] = r

        if self._is_line:
            add("Segment Type", "Line")
            add("Point1", fmt(info["start"]), "mm", fmt(info["start"]))
            add("Point2", fmt(info["end"]), "mm", fmt(info["end"]))
            add("Length", f"{seg['length']:g}", "mm", f"{seg['length']:g}mm",
                editable=True)
            add("Direction", f"{seg['dir']:g}", "deg", f"{seg['dir']:g}deg",
                editable=True)
        else:
            rad = math.hypot(seg["cx_off"], seg["cy_off"])
            add("Segment Type", "Center Point Arc")
            add("Start Point", fmt(info["start"]), "mm", fmt(info["start"]))
            add("Center Point", fmt(info["center"]), "mm", fmt(info["center"]),
                editable=True)
            add("Radius", f"{rad:g}", "mm", f"{rad:g}mm", editable=True)
            add("Angle", f"{seg['angle']:g}", "deg", f"{seg['angle']:g}deg",
                editable=True)
            add("Plane", "XY")
            add("Number of segments", "0")
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel
                              | QDialogButtonBox.StandardButton.Apply)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText("확인")
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText("취소")
        bb.button(QDialogButtonBox.StandardButton.Apply).setText("적용(A)")
        bb.accepted.connect(self._ok); bb.rejected.connect(self.reject)
        bb.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._apply)
        root.addWidget(bb)
        self.tbl.itemChanged.connect(self._live_edit)

    def _num(self, name, default):
        try:
            return self._eval(self.tbl.item(self._rows[name], 1).text())
        except (ValueError, IndexError, KeyError, TypeError):
            return default

    def _xy(self, name, default):
        import re
        try:
            txt = self.tbl.item(self._rows[name], 1).text()
            parts = [p for p in re.split(r"[ ,]+", txt.strip()) if p]
            return self._eval(parts[0]), self._eval(parts[1])
        except (ValueError, IndexError, KeyError, TypeError):
            return default

    def _live_edit(self, item):
        if item.column() == 1:
            self._apply()

    def _apply(self):
        import math
        from ..model.geometry import segment_geometry, apply_cmd
        seg = self.shape.cmd["segments"][self.index]
        info = segment_geometry(self.shape.cmd["start"],
                                self.shape.cmd["segments"])[self.index]
        start = info["start"]
        if self._is_line:
            seg["length"] = self._num("Length", seg["length"])
            seg["dir"] = self._num("Direction", seg["dir"])
        else:
            cur_r = math.hypot(seg["cx_off"], seg["cy_off"]) or 1.0
            c = self._xy("Center Point", info["center"])
            seg["cx_off"] = c[0] - start[0]; seg["cy_off"] = c[1] - start[1]
            new_r = self._num("Radius", cur_r); old = math.hypot(seg["cx_off"], seg["cy_off"]) or 1.0
            s = new_r / old
            seg["cx_off"] *= s; seg["cy_off"] *= s
            seg["angle"] = self._num("Angle", seg["angle"])
        apply_cmd(self.shape)
        self._refresh_evaluated()
        if self._on_apply:
            self._on_apply()

    def _refresh_evaluated(self):
        import math
        from ..model.geometry import segment_geometry
        info = segment_geometry(self.shape.cmd["start"],
                                self.shape.cmd["segments"])[self.index]
        seg = self.shape.cmd["segments"][self.index]
        self.tbl.blockSignals(True)

        def setev(name, text):
            r = self._all_rows.get(name)
            if r is not None and self.tbl.item(r, 3):
                self.tbl.item(r, 3).setText(text)

        def setval(name, text):
            r = self._all_rows.get(name)
            if r is not None and self.tbl.item(r, 1):
                self.tbl.item(r, 1).setText(text)

        def fmt(p):
            return f"{p[0]:g} ,{p[1]:g} ,0"
        if self._is_line:
            setval("Point2", fmt(info["end"])); setev("Point2", fmt(info["end"]))
            setev("Length", f"{seg['length']:g}mm")
            setev("Direction", f"{seg['dir']:g}deg")
        else:
            rad = math.hypot(seg["cx_off"], seg["cy_off"])
            setev("Center Point", fmt(info["center"]))
            setev("Radius", f"{rad:g}mm")
            setev("Angle", f"{seg['angle']:g}deg")
        self.tbl.blockSignals(False)

    def _ok(self):
        self._apply(); self.accept()


class ProjectVariablesDialog(QDialog):
    """Project Variables editor (Name | Value/expression | Evaluated Value)."""

    def __init__(self, variables, parent=None):
        super().__init__(parent)
        from PyQt6.QtWidgets import (QVBoxLayout, QHBoxLayout, QTableWidget,
                                     QTableWidgetItem, QPushButton)
        self.vars = variables
        self.setWindowTitle("Project Variables")
        self.resize(460, 420)
        root = QVBoxLayout(self)
        self.tbl = QTableWidget(0, 3)
        self.tbl.setHorizontalHeaderLabels(["Name", "Value", "Evaluated Value"])
        self.tbl.horizontalHeader().setStretchLastSection(True)
        self.tbl.itemChanged.connect(self._recalc)
        root.addWidget(self.tbl, 1)
        self._load()
        btns = QHBoxLayout()
        add = QPushButton("Add"); add.clicked.connect(self._add)
        rem = QPushButton("Remove"); rem.clicked.connect(self._remove)
        btns.addWidget(add); btns.addWidget(rem); btns.addStretch(1)
        root.addLayout(btns)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        root.addWidget(bb)

    def _load(self):
        from PyQt6.QtWidgets import QTableWidgetItem
        from PyQt6.QtCore import Qt as _Qt
        self.tbl.blockSignals(True); self.tbl.setRowCount(0)
        for name, expr, ev in self.vars.rows():
            r = self.tbl.rowCount(); self.tbl.insertRow(r)
            self.tbl.setItem(r, 0, QTableWidgetItem(name))
            self.tbl.setItem(r, 1, QTableWidgetItem(expr))
            it = QTableWidgetItem(ev); it.setFlags(it.flags() & ~_Qt.ItemFlag.ItemIsEditable)
            self.tbl.setItem(r, 2, it)
        self.tbl.blockSignals(False)

    def _add(self):
        from PyQt6.QtWidgets import QTableWidgetItem
        r = self.tbl.rowCount(); self.tbl.insertRow(r)
        self.tbl.setItem(r, 0, QTableWidgetItem("Var1"))
        self.tbl.setItem(r, 1, QTableWidgetItem("0"))

    def _remove(self):
        r = self.tbl.currentRow()
        if r >= 0:
            self.tbl.removeRow(r); self._recalc()

    def _recalc(self, *_):
        self.apply_to(self.vars)
        self._load()

    def apply_to(self, variables):
        new = {}
        for r in range(self.tbl.rowCount()):
            n = self.tbl.item(r, 0); v = self.tbl.item(r, 1)
            if n and n.text().strip():
                new[n.text().strip()] = v.text() if v else "0"
        variables.exprs = new
        variables.reevaluate()


class PropertiesDialog(QDialog):
    """Faithful 'Properties: <proj> - <design> - Modeler' modal with Command /
    Attribute tabs and editable dimension cells (matches Maxwell's dialog)."""

    def __init__(self, shape, materials, title_path, tab="Command",
                 evaluate=None, on_apply=None, parent=None):
        super().__init__(parent)
        from PyQt6.QtWidgets import (QVBoxLayout, QTabWidget, QTableWidget,
                                     QTableWidgetItem, QCheckBox, QHBoxLayout)
        from PyQt6.QtCore import Qt as _Qt
        self.shape = shape
        self._evaluate = evaluate or (lambda s: float(s))
        self._on_apply = on_apply
        self._applied = False
        self.setWindowTitle(f"Properties: {title_path} - Modeler")
        self.resize(560, 380)
        root = QVBoxLayout(self)
        self.tabs = QTabWidget(); root.addWidget(self.tabs, 1)

        COLS = ["Name", "Value", "Unit", "Evaluated Value", "Description"]
        # --- Command tab ------------------------------------------------
        self.cmd_tbl = QTableWidget(0, len(COLS))
        self.cmd_tbl.setHorizontalHeaderLabels(COLS)
        self.cmd_tbl.verticalHeader().setVisible(False)
        self.cmd_tbl.horizontalHeader().setStretchLastSection(True)
        self._editable_rows = {}
        self._fill_command()
        self.tabs.addTab(self.cmd_tbl, "Command")
        # --- Attribute tab ---------------------------------------------
        self.attr_tbl = QTableWidget(0, len(COLS))
        self.attr_tbl.setHorizontalHeaderLabels(COLS)
        self.attr_tbl.verticalHeader().setVisible(False)
        self.attr_tbl.horizontalHeader().setStretchLastSection(True)
        self.mat_combo = QComboBox(); self.mat_combo.addItems(list(materials))
        self._fill_attribute()
        self.tabs.addTab(self.attr_tbl, "Attribute")
        self.tabs.setCurrentIndex(0 if tab == "Command" else 1)

        self.show_hidden = QCheckBox("Show Hidden")
        root.addWidget(self.show_hidden, 0, _Qt.AlignmentFlag.AlignRight)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel
                              | QDialogButtonBox.StandardButton.Apply)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText("확인")
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText("취소")
        bb.button(QDialogButtonBox.StandardButton.Apply).setText("적용(A)")
        bb.accepted.connect(self._ok)
        bb.rejected.connect(self.reject)
        bb.button(QDialogButtonBox.StandardButton.Apply).clicked.connect(self._apply)
        root.addWidget(bb)
        # live: committing an edit updates evaluated values + geometry immediately
        self.cmd_tbl.itemChanged.connect(self._live_edit)

    def _live_edit(self, item):
        if item.column() == 1:
            self._apply()

    def _row(self, tbl, name, value, unit="", evald="", editable=False):
        from PyQt6.QtWidgets import QTableWidgetItem
        from PyQt6.QtCore import Qt as _Qt
        r = tbl.rowCount(); tbl.insertRow(r)
        for c, v in enumerate((name, value, unit, evald, "")):
            it = QTableWidgetItem(str(v))
            if not (c == 1 and editable):
                it.setFlags(it.flags() & ~_Qt.ItemFlag.ItemIsEditable)
            tbl.setItem(r, c, it)
        if editable:
            self._editable_rows[name] = r

    def _fill_command(self):
        c = self.shape.cmd or {}
        k = c.get("kind", "Create")
        self._row(self.cmd_tbl, "Command", k)
        self._row(self.cmd_tbl, "Coordinate System", "Global")
        if k == "CreateCircle":
            cexpr = c.get("center_expr", f"{c['cx']:g} ,{c['cy']:g} ,0")
            rexpr = c.get("r_expr", f"{c['r']:g}")
            self._row(self.cmd_tbl, "Center Position", cexpr,
                      "mm", f"{c['cx']:g}mm ,{c['cy']:g}mm ,0mm", editable=True)
            self._row(self.cmd_tbl, "Axis", "Z")
            self._row(self.cmd_tbl, "Radius", rexpr, "mm", f"{c['r']:g}mm",
                      editable=True)
            self._row(self.cmd_tbl, "Number of Segments", f"{int(c.get('segs', 0))}",
                      editable=True)
        elif k == "CreateRectangle":
            self._row(self.cmd_tbl, "Position", f"{c['x0']:g} ,{c['y0']:g} ,0",
                      "mm", editable=True)
            self._row(self.cmd_tbl, "Axis", "Z")
            self._row(self.cmd_tbl, "X Size", f"{c['x1'] - c['x0']:g}", "mm",
                      editable=True)
            self._row(self.cmd_tbl, "Y Size", f"{c['y1'] - c['y0']:g}", "mm",
                      editable=True)
        elif k == "CreatePolyline":
            self._row(self.cmd_tbl, "Number of points",
                      str(len(c.get("points", []))))

    def _fill_attribute(self):
        s = self.shape
        self._row(self.attr_tbl, "Name", s.name, editable=True)
        self._row(self.attr_tbl, "Material", s.material)
        i = self.mat_combo.findText(s.material)
        if i >= 0:
            self.mat_combo.setCurrentIndex(i)
        self.attr_tbl.setCellWidget(self.attr_tbl.rowCount() - 1, 1, self.mat_combo)
        self._editable_rows["Name"] = 0
        for nm, val in (("Solve Inside", "True"), ("Orientation", "Global"),
                        ("Model", "True"), ("Group", "Model"),
                        ("Color", s.color), ("Transparent", "0")):
            self._row(self.attr_tbl, nm, val)

    # -- apply ----------------------------------------------------------
    def _apply(self):
        from ..model import apply_cmd
        c = self.shape.cmd
        ev = self._evaluate
        try:
            if c and "Radius" in self._editable_rows:
                t = self.cmd_tbl.item(self._editable_rows["Radius"], 1).text()
                c["r"] = ev(t); c["r_expr"] = t
            if c and "Center Position" in self._editable_rows:
                t = self.cmd_tbl.item(self._editable_rows["Center Position"], 1).text()
                parts = [s for s in t.replace(",", " ").split() if s]
                c["cx"], c["cy"] = ev(parts[0]), ev(parts[1])
                c["center_expr"] = t
            if c and "Number of Segments" in self._editable_rows:
                v = int(float(self.cmd_tbl.item(
                    self._editable_rows["Number of Segments"], 1).text()))
                if v > 0:
                    c["segs"] = v
            if c and "Position" in self._editable_rows:
                t = self.cmd_tbl.item(self._editable_rows["Position"], 1).text()
                p = [float(x) for x in t.replace(",", " ").split()]
                w = c["x1"] - c["x0"]; h = c["y1"] - c["y0"]
                c["x0"], c["y0"] = p[0], p[1]; c["x1"], c["y1"] = p[0] + w, p[1] + h
            if c and "X Size" in self._editable_rows:
                c["x1"] = c["x0"] + float(self.cmd_tbl.item(
                    self._editable_rows["X Size"], 1).text())
            if c and "Y Size" in self._editable_rows:
                c["y1"] = c["y0"] + float(self.cmd_tbl.item(
                    self._editable_rows["Y Size"], 1).text())
        except (ValueError, IndexError, KeyError):
            return
        if c:
            apply_cmd(self.shape)
            self._refresh_evaluated()
        # attribute edits
        nm = self.attr_tbl.item(0, 1)
        if nm and nm.text().strip():
            self.shape.name = nm.text().strip()
        self.shape.material = self.mat_combo.currentText()
        self._applied = True
        if self._on_apply:
            self._on_apply()                 # live geometry update (no close)

    def _refresh_evaluated(self):
        """Update the Evaluated Value column live after an edit."""
        c = self.shape.cmd or {}
        self.cmd_tbl.blockSignals(True)
        def setev(key, text):
            r = self._editable_rows.get(key)
            if r is not None and self.cmd_tbl.item(r, 3):
                self.cmd_tbl.item(r, 3).setText(text)
        if c.get("kind") == "CreateCircle":
            setev("Radius", f"{c['r']:g}mm")
            setev("Center Position", f"{c['cx']:g}mm ,{c['cy']:g}mm ,0mm")
        self.cmd_tbl.blockSignals(False)

    def _ok(self):
        self._apply(); self.accept()


class AttributesDialog(_Base):
    """Object Attribute dialog (Maxwell 'Properties' double-click feel)."""

    def __init__(self, shape, materials, parent=None):
        super().__init__(f"Properties: {shape.name}", parent)
        self._color = shape.color
        self.name = QLineEdit(shape.name)
        self.mat = QComboBox(); self.mat.addItems(list(materials))
        i = self.mat.findText(shape.material)
        if i >= 0:
            self.mat.setCurrentIndex(i)
        self.colorbtn = QPushButton(shape.color)
        self.colorbtn.clicked.connect(self._pick)
        self.form.addRow("Name", self.name)
        self.form.addRow("Material", self.mat)
        self.form.addRow("Color", self.colorbtn)
        self._add_buttons()

    def _pick(self):
        c = QColorDialog.getColor(QColor(self._color), self, "Object colour")
        if c.isValid():
            self._color = c.name(); self.colorbtn.setText(self._color)

    def values(self):
        return self.name.text().strip(), self.mat.currentText(), self._color


class CircleDialog(_Base):
    def __init__(self, parent=None):
        super().__init__("Create Circle", parent)
        self.cx = _spin(-1e4, 1e4, 3); self.cy = _spin(-1e4, 1e4, 3)
        self.r = _spin(1e-3, 1e4, 3, 10.0)
        self.form.addRow("Center X [mm]", self.cx)
        self.form.addRow("Center Y [mm]", self.cy)
        self.form.addRow("Radius [mm]", self.r)
        self._add_buttons()

    def values(self):
        return self.cx.value(), self.cy.value(), self.r.value()


class RectDialog(_Base):
    def __init__(self, parent=None):
        super().__init__("Create Rectangle", parent)
        self.x = _spin(-1e4, 1e4, 3); self.y = _spin(-1e4, 1e4, 3)
        self.w = _spin(1e-3, 1e4, 3, 10.0); self.h = _spin(1e-3, 1e4, 3, 10.0)
        self.form.addRow("Corner X [mm]", self.x)
        self.form.addRow("Corner Y [mm]", self.y)
        self.form.addRow("Width [mm]", self.w)
        self.form.addRow("Height [mm]", self.h)
        self._add_buttons()

    def values(self):
        x, y = self.x.value(), self.y.value()
        return x, y, x + self.w.value(), y + self.h.value()


class RelativeCSDialog(_Base):
    """Maxwell-style Relative Coordinate System: offset origin + rotation.
    Type is a hint (Offset/Rotated/Both); all fields apply."""
    def __init__(self, parent=None, default_name="RelativeCS1"):
        super().__init__("Create Relative CS", parent)
        self.name = QLineEdit(default_name)
        self.mode = QComboBox(); self.mode.addItems(["Offset", "Rotated", "Both"])
        self.ox = _spin(-1e4, 1e4, 3); self.oy = _spin(-1e4, 1e4, 3)
        self.rot = _spin(-360.0, 360.0, 3, 0.0)
        self.form.addRow("Name", self.name)
        self.form.addRow("Type", self.mode)
        self.form.addRow("Origin X [mm]", self.ox)
        self.form.addRow("Origin Y [mm]", self.oy)
        self.form.addRow("Rotation [deg]", self.rot)
        self._add_buttons()

    def values(self):
        return (self.name.text().strip() or "RelativeCS1",
                self.ox.value(), self.oy.value(), self.rot.value())


class SplitDialog(_Base):
    """Split selected objects along a plane (Maxwell Split): X or Y line."""
    def __init__(self, parent=None):
        super().__init__("Split", parent)
        self.axis = QComboBox(); self.axis.addItems(["X", "Y"])
        self.pos = _spin(-1e4, 1e4, 3, 0.0)
        self.form.addRow("Split plane (line ⟂)", self.axis)
        self.form.addRow("Position [mm]", self.pos)
        self._add_buttons()

    def values(self):
        return self.axis.currentText(), self.pos.value()


class AroundAxisDialog(_Base):
    def __init__(self, parent=None):
        super().__init__("Duplicate Around Axis", parent)
        self.count = QSpinBox(); self.count.setRange(2, 360); self.count.setValue(6)
        self.angle = _spin(-360, 360, 2, 360.0)
        self.ox = _spin(-1e4, 1e4, 3); self.oy = _spin(-1e4, 1e4, 3)
        self.form.addRow("Total number", self.count)
        self.form.addRow("Total angle [°]", self.angle)
        self.form.addRow("Axis X [mm]", self.ox)
        self.form.addRow("Axis Y [mm]", self.oy)
        self._add_buttons()

    def values(self):
        return self.count.value(), self.angle.value(), self.ox.value(), self.oy.value()


class AlongLineDialog(_Base):
    def __init__(self, parent=None):
        super().__init__("Duplicate Along Line", parent)
        self.count = QSpinBox(); self.count.setRange(2, 1000); self.count.setValue(3)
        self.dx = _spin(-1e4, 1e4, 3, 10.0); self.dy = _spin(-1e4, 1e4, 3)
        self.form.addRow("Total number", self.count)
        self.form.addRow("Step ΔX [mm]", self.dx)
        self.form.addRow("Step ΔY [mm]", self.dy)
        self._add_buttons()

    def values(self):
        return self.count.value(), self.dx.value(), self.dy.value()


class MirrorDialog(_Base):
    def __init__(self, parent=None):
        super().__init__("Mirror / Duplicate", parent)
        self.axis = QComboBox(); self.axis.addItems(["X axis (horizontal)",
                                                     "Y axis (vertical)"])
        self.offset = _spin(-1e4, 1e4, 3)
        self.keep = QComboBox(); self.keep.addItems(["Duplicate (keep original)",
                                                     "Move (replace)"])
        self.form.addRow("Mirror about", self.axis)
        self.form.addRow("Offset [mm]", self.offset)
        self.form.addRow("Mode", self.keep)
        self._add_buttons()

    def values(self):
        axis = "x" if self.axis.currentIndex() == 0 else "y"
        return axis, self.offset.value(), self.keep.currentIndex() == 0
