"""View / Edit Material dialog (faithful to Maxwell) + B-H Curve editor.

The material dialog shows the 'Properties of the Material' grid
(Name | Type | Value | Units) with the rows seen in the video, a B-H Curve…
button that opens the curve editor, and the right-side option panels.
"""
from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QFormLayout, QLabel, QLineEdit, QComboBox,
                             QTableWidget, QTableWidgetItem, QPushButton,
                             QGroupBox, QRadioButton, QCheckBox, QDialogButtonBox,
                             QFileDialog, QWidget, QHeaderView, QDoubleSpinBox)

from ..model.materials import Material, BHCurve


class BHCurveDialog(QDialog):
    """B-H Curve editor: editable H/B table + live plot + import/export."""

    def __init__(self, bh: BHCurve, name: str = "", parent=None):
        super().__init__(parent)
        self.setWindowTitle("BH Curve")
        self.resize(820, 520)
        root = QHBoxLayout(self)

        left = QVBoxLayout()
        bar = QHBoxLayout()
        for txt, fn in (("Add Row", self._add), ("Delete Row", self._del),
                        ("Import Dataset…", self._imp), ("Export Dataset…", self._exp)):
            b = QPushButton(txt); b.clicked.connect(fn); bar.addWidget(b)
        left.addLayout(bar)
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["H (A_per_meter)", "B (tesla)"])
        self.table.setFixedWidth(260)
        self.table.itemChanged.connect(self._replot)
        left.addWidget(self.table)
        root.addLayout(left)

        self.plot = pg.PlotWidget(background="#232a31")
        for ax in ("bottom", "left"):
            self.plot.getAxis(ax).setPen("#5a6b7b")
            self.plot.getAxis(ax).setTextPen("#9fb3c8")
        self.plot.setTitle(name, color="#9fb3c8")
        self.plot.setLabel("bottom", "H", units="A/m", color="#9fb3c8")
        self.plot.setLabel("left", "B", units="T", color="#9fb3c8")
        self.plot.showGrid(x=True, y=True, alpha=0.25)
        self.curve = self.plot.plot([], [], pen=pg.mkPen("#39c06a", width=2))
        rr = QVBoxLayout(); rr.addWidget(self.plot, 1)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        rr.addWidget(bb)
        root.addLayout(rr, 1)
        self._load(bh.rows())

    def _load(self, rows):
        self.table.blockSignals(True); self.table.setRowCount(0)
        for h, b in rows:
            r = self.table.rowCount(); self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(f"{h:g}"))
            self.table.setItem(r, 1, QTableWidgetItem(f"{b:g}"))
        self.table.blockSignals(False); self._replot()

    def _add(self):
        r = self.table.rowCount(); self.table.insertRow(r)
        self.table.setItem(r, 0, QTableWidgetItem("0"))
        self.table.setItem(r, 1, QTableWidgetItem("0"))

    def _del(self):
        r = self.table.currentRow()
        if r >= 0:
            self.table.removeRow(r); self._replot()

    def rows(self):
        out = []
        for r in range(self.table.rowCount()):
            try:
                out.append((float(self.table.item(r, 0).text()),
                            float(self.table.item(r, 1).text())))
            except (ValueError, AttributeError):
                pass
        return out

    def _replot(self, *_):
        rows = sorted(self.rows())
        if rows:
            a = np.asarray(rows); self.curve.setData(a[:, 0], a[:, 1])
        else:
            self.curve.setData([], [])

    def _imp(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Import Dataset", "", "CSV (*.csv)")
        if fn:
            self._load(BHCurve.from_csv(fn).rows())

    def _exp(self):
        fn, _ = QFileDialog.getSaveFileName(self, "Export Dataset", "", "CSV (*.csv)")
        if fn:
            BHCurve.from_rows(self.rows()).to_csv(fn)

    def result_curve(self) -> BHCurve:
        return BHCurve.from_rows(self.rows())


class BPCurveDialog(QDialog):
    """B-P (core-loss) curve editor.  Enter measured loss P[W/m^3] vs B[T] at a
    test frequency, then 'Fit' least-squares the Bertotti coefficients
    P = Kh*f*B^2 + Kc*(f*B)^2 + Ke*(f*B)^1.5 used by the core-loss solver."""

    def __init__(self, material, parent=None):
        super().__init__(parent)
        self.m = material
        self.setWindowTitle(f"B-P Curve (core loss) — {material.name}")
        self.resize(560, 460)
        root = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("Frequency"))
        self.freq = QDoubleSpinBox(); self.freq.setRange(1, 1e6); self.freq.setValue(60)
        self.freq.setSuffix(" Hz"); top.addWidget(self.freq); top.addStretch(1)
        root.addLayout(top)
        self.tbl = QTableWidget(0, 2)
        self.tbl.setHorizontalHeaderLabels(["B [T]", "P [W/m^3]"])
        self.tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        root.addWidget(self.tbl, 1)
        # seed from current coefficients (or a blank few rows)
        f0 = 60.0
        seed = [(b, material.kh * f0 * b ** 2 + material.kc * (f0 * b) ** 2
                 + material.ke * (f0 * b) ** 1.5) for b in (0.5, 1.0, 1.5, 1.8)]
        if not (material.kh or material.kc or material.ke):
            seed = [(0.5, 0.0), (1.0, 0.0), (1.5, 0.0), (1.8, 0.0)]
        self._load(seed)
        self.plot = pg.PlotWidget(background="#0c1830"); self.plot.setMaximumHeight(150)
        self.plot.setLabel("bottom", "B [T]"); self.plot.setLabel("left", "P [W/m^3]")
        root.addWidget(self.plot)
        self.lbl = QLabel("Kh / Kc / Ke: (fit to compute)")
        root.addWidget(self.lbl)
        bar = QHBoxLayout()
        for txt, fn in (("+ Row", lambda: self.tbl.insertRow(self.tbl.rowCount())),
                        ("Fit Kh/Kc/Ke", self._fit)):
            b = QPushButton(txt); b.clicked.connect(fn); bar.addWidget(b)
        bar.addStretch(1)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        bar.addWidget(bb)
        root.addLayout(bar)
        self._kh = material.kh; self._kc = material.kc; self._ke = material.ke

    def _load(self, rows):
        self.tbl.setRowCount(0)
        for b, p in rows:
            r = self.tbl.rowCount(); self.tbl.insertRow(r)
            self.tbl.setItem(r, 0, QTableWidgetItem(f"{b:g}"))
            self.tbl.setItem(r, 1, QTableWidgetItem(f"{p:g}"))

    def _points(self):
        pts = []
        for r in range(self.tbl.rowCount()):
            try:
                b = float(self.tbl.item(r, 0).text()); p = float(self.tbl.item(r, 1).text())
                pts.append((b, p))
            except (ValueError, AttributeError):
                continue
        return pts

    def _fit(self):
        pts = self._points()
        if len(pts) < 3:
            self.lbl.setText("최소 3점 필요"); return
        f = self.freq.value()
        B = np.array([p[0] for p in pts]); P = np.array([p[1] for p in pts])
        A = np.column_stack([f * B ** 2, (f * B) ** 2, (f * B) ** 1.5])
        coef, *_ = np.linalg.lstsq(A, P, rcond=None)
        self._kh, self._kc, self._ke = (max(c, 0.0) for c in coef)
        self.lbl.setText(f"Kh={self._kh:.4g}  Kc={self._kc:.4g}  Ke={self._ke:.4g}")
        self.plot.clear()
        self.plot.plot(B, P, pen=None, symbol="o", symbolBrush="#2bd6ff")
        Bf = np.linspace(B.min(), B.max(), 50)
        Pf = self._kh * f * Bf ** 2 + self._kc * (f * Bf) ** 2 + self._ke * (f * Bf) ** 1.5
        self.plot.plot(Bf, Pf, pen=pg.mkPen("#e6a23c", width=2))

    def fitted(self):
        return self._kh, self._kc, self._ke


class ViewEditMaterialDialog(QDialog):
    def __init__(self, material: Material, parent=None):
        super().__init__(parent)
        self.m = material
        self.setWindowTitle("View / Edit Material")
        self.resize(880, 560)
        root = QVBoxLayout(self)

        top = QFormLayout()
        self.name = QLineEdit(material.name)
        self.cs = QComboBox(); self.cs.addItems(["Cartesian", "Cylindrical", "Spherical"])
        top.addRow("Material Name", self.name)
        top.addRow("Material Coordinate System Type:", self.cs)
        root.addLayout(top)

        body = QHBoxLayout()
        self.grid = QTableWidget(0, 4)
        self.grid.setHorizontalHeaderLabels(["Name", "Type", "Value", "Units"])
        self.grid.verticalHeader().setVisible(False)
        self.grid.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self._val = {}            # row name -> table row index (editable Value)
        self._build_grid()
        body.addWidget(self.grid, 1)

        # right-side option panels (faithful, mostly informational)
        side = QVBoxLayout()
        g1 = QGroupBox("View/Edit Material for"); l1 = QVBoxLayout(g1)
        for i, t in enumerate(("Active Design", "Active Project", "All Properties")):
            rb = QRadioButton(t); rb.setChecked(i == 0); l1.addWidget(rb)
        side.addWidget(g1)
        g2 = QGroupBox("Physics:"); l2 = QVBoxLayout(g2)
        for t in ("Electromagnetic", "Thermal", "Structural"):
            cb = QCheckBox(t); cb.setChecked(t == "Electromagnetic"); l2.addWidget(cb)
        side.addWidget(g2)
        side.addWidget(QPushButton("Validate Material"))
        side.addStretch(1)
        body.addLayout(side)
        root.addLayout(body, 1)

        self.notes = QLineEdit(f"Autogenerated for {material.name}")
        root.addWidget(QLabel("Notes")); root.addWidget(self.notes)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Reset
                              | QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self._ok); bb.rejected.connect(self.reject)
        root.addWidget(bb)

    # -- grid -----------------------------------------------------------
    def _add(self, name, typ, value, units, editable=False, button=None, cb=None):
        r = self.grid.rowCount(); self.grid.insertRow(r)
        for c, v in enumerate((name, typ, value, units)):
            it = QTableWidgetItem(str(v))
            if not (c == 2 and editable):
                it.setFlags(it.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.grid.setItem(r, c, it)
        if editable:
            self._val[name.strip(" -")] = r
        if button:
            b = QPushButton(button)
            b.clicked.connect(cb or self._edit_bh)
            self.grid.setCellWidget(r, 2, b)

    def _build_grid(self):
        m = self.m
        if m.nonlinear:
            self._add("Relative Permeability", "Nonlinear", "B-H Curve…", "",
                      button="B-H Curve…")
        else:
            self._add("Relative Permeability", "Simple", f"{m.mu_r:g}", "",
                      editable=True)
        self._add("Bulk Conductivity", "Simple", f"{m.conductivity:g}",
                  "siemens/m", editable=True)
        self._add("Magnetic Coercivity", "Vector", "", "")
        self._add("  - Magnitude", "Vector Mag", f"{m.hc:g}", "A_per_meter",
                  editable=True)
        self._add("  - X Component", "Unit Vector", "1", "")
        self._add("  - Y Component", "Unit Vector", "0", "")
        self._add("  - Z Component", "Unit Vector", "0", "")
        clm = "Electrical Steel" if (m.kh or m.kc or m.ke) else "None"
        self._add("Core Loss Model", "", clm, "w/m^3")
        if clm == "Electrical Steel":
            self._add("  - Kh", "Simple", f"{m.kh:g}", "", editable=True)
            self._add("  - Kc", "Simple", f"{m.kc:g}", "", editable=True)
            self._add("  - Ke", "Simple", f"{m.ke:g}", "", editable=True)
            self._add("  - Y", "Simple", "2", "")
            self._add("  - Kdc", "Simple", "0", "")
            self._add("  - Equiv. Cut Depth", "Simple", "0.001", "meter")
            self._add("  - B-P Curve", "Custom", "Edit & Fit…", "",
                      button="B-P Curve…", cb=self._edit_bp)
        self._add("Mass Density", "Simple", f"{m.mass_density:g}", "kg/m^3",
                  editable=True)
        self._add("Composition", "", "Lamination" if clm == "Electrical Steel"
                  else "Solid", "")
        self._add("Young's Modulus", "Simple", "0", "N/m^2")
        self._add("Poisson's Ratio", "Simple", "0", "")
        self._add("Magnetostriction", "Custom", "Edit…", "")
        self._add("Inverse Magnetostriction", "Custom", "Edit…", "")

    def _edit_bh(self):
        dlg = BHCurveDialog(self.m.bh, self.m.name, self)
        if dlg.exec():
            self.m.bh = dlg.result_curve()

    def _edit_bp(self):
        dlg = BPCurveDialog(self.m, self)
        if dlg.exec():
            self.m.kh, self.m.kc, self.m.ke = dlg.fitted()
            for nm, val in (("Kh", self.m.kh), ("Kc", self.m.kc), ("Ke", self.m.ke)):
                r = self._val.get(nm)
                if r is not None and self.grid.item(r, 2):
                    self.grid.item(r, 2).setText(f"{val:g}")

    def _cell(self, name):
        r = self._val.get(name)
        if r is None:
            return None
        it = self.grid.item(r, 2)
        return it.text() if it else None

    def _ok(self):
        m = self.m
        m.name = self.name.text().strip() or m.name
        try:
            if not m.nonlinear and self._cell("Relative Permeability"):
                m.mu_r = float(self._cell("Relative Permeability"))
            m.conductivity = float(self._cell("Bulk Conductivity") or m.conductivity)
            m.hc = float(self._cell("Magnitude") or m.hc)
            m.mass_density = float(self._cell("Mass Density") or m.mass_density)
            if "Kh" in self._val:
                m.kh = float(self._cell("Kh")); m.kc = float(self._cell("Kc"))
                m.ke = float(self._cell("Ke"))
        except (ValueError, TypeError):
            pass
        self.accept()

    def apply_to_material(self) -> Material:
        return self.m
