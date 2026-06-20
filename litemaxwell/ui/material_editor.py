"""Material editor with a B-H curve table and live plot (mirrors Maxwell's
B-H Curve dialog: editable table, import/export dataset, plotted curve)."""
from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                             QLineEdit, QDoubleSpinBox, QCheckBox, QPushButton,
                             QTableWidget, QTableWidgetItem, QLabel, QFileDialog,
                             QGroupBox, QDialogButtonBox, QWidget)

from ..model.materials import Material, BHCurve


class MaterialEditor(QDialog):
    def __init__(self, material: Material, parent=None):
        super().__init__(parent)
        self.m = material
        self.setWindowTitle(f"View / Edit Material — {material.name}")
        self.resize(820, 560)
        root = QHBoxLayout(self)

        # --- left: scalar properties ------------------------------------
        left = QFormLayout()
        self.name = QLineEdit(material.name)
        self.mu_r = self._spin(material.mu_r, 1, 1e6, 1)
        self.cond = self._spin(material.conductivity, 0, 1e9, 0)
        self.dens = self._spin(material.mass_density, 0, 1e5, 0)
        self.is_mag = QCheckBox("Permanent magnet")
        self.is_mag.setChecked(material.is_magnet)
        self.br = self._spin(material.br, 0, 3, 4)
        self.hc = self._spin(material.hc, 0, 1e7, 0)
        self.mdir = self._spin(material.mag_dir_deg, -360, 360, 1)
        self.kh = self._spin(material.kh, 0, 1e6, 3)
        self.kc = self._spin(material.kc, 0, 1e6, 3)
        self.ke = self._spin(material.ke, 0, 1e6, 3)
        left.addRow("Name", self.name)
        left.addRow("Relative permeability μr", self.mu_r)
        left.addRow("Conductivity [S/m]", self.cond)
        left.addRow("Mass density [kg/m³]", self.dens)
        left.addRow(self.is_mag)
        left.addRow("Br [T]", self.br)
        left.addRow("Hc [A/m]", self.hc)
        left.addRow("Magnetisation dir [°]", self.mdir)
        left.addRow(QLabel("— Core loss (Steinmetz) —"))
        left.addRow("Kh", self.kh)
        left.addRow("Kc", self.kc)
        left.addRow("Ke", self.ke)
        lw = QWidget(); lw.setLayout(left); lw.setFixedWidth(280)
        root.addWidget(lw)

        # --- right: B-H curve table + plot ------------------------------
        right = QVBoxLayout()
        gb = QGroupBox("B-H Curve")
        gbl = QVBoxLayout(gb)
        btns = QHBoxLayout()
        for txt, fn in (("Add row", self._add_row), ("Delete row", self._del_row),
                        ("Import…", self._import), ("Export…", self._export)):
            b = QPushButton(txt); b.clicked.connect(fn); btns.addWidget(b)
        btns.addStretch(1)
        gbl.addLayout(btns)

        body = QHBoxLayout()
        self.table = QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels(["H [A/m]", "B [T]"])
        self.table.setFixedWidth(230)
        self.table.itemChanged.connect(self._replot)
        body.addWidget(self.table)

        self.plot = pg.PlotWidget(background="#232a31")
        for ax in ("bottom", "left"):
            self.plot.getAxis(ax).setPen("#5a6b7b")
            self.plot.getAxis(ax).setTextPen("#9fb3c8")
        self.plot.setLabel("bottom", "H", units="A/m", color="#9fb3c8")
        self.plot.setLabel("left", "B", units="T", color="#9fb3c8")
        self.plot.showGrid(x=True, y=True, alpha=0.25)
        self.curve = self.plot.plot([], [], pen=pg.mkPen("#4a90d9", width=2),
                                    symbol="o", symbolSize=5,
                                    symbolBrush="#e6a23c", symbolPen=None)
        body.addWidget(self.plot, 1)
        gbl.addLayout(body)
        right.addWidget(gb, 1)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        right.addWidget(bb)
        root.addLayout(right, 1)

        self._load_rows(material.bh.rows())

    # --- helpers --------------------------------------------------------
    def _spin(self, val, lo, hi, dec):
        s = QDoubleSpinBox(); s.setRange(lo, hi); s.setDecimals(dec)
        s.setValue(val); s.setMaximumWidth(160)
        return s

    def _load_rows(self, rows):
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for h, b in rows:
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QTableWidgetItem(f"{h:g}"))
            self.table.setItem(r, 1, QTableWidgetItem(f"{b:g}"))
        self.table.blockSignals(False)
        self._replot()

    def _add_row(self):
        r = self.table.rowCount()
        self.table.insertRow(r)
        self.table.setItem(r, 0, QTableWidgetItem("0"))
        self.table.setItem(r, 1, QTableWidgetItem("0"))

    def _del_row(self):
        r = self.table.currentRow()
        if r >= 0:
            self.table.removeRow(r)
            self._replot()

    def _read_rows(self):
        rows = []
        for r in range(self.table.rowCount()):
            try:
                h = float(self.table.item(r, 0).text())
                b = float(self.table.item(r, 1).text())
                rows.append((h, b))
            except (ValueError, AttributeError):
                continue
        return rows

    def _replot(self, *_):
        rows = sorted(self._read_rows())
        if rows:
            arr = np.asarray(rows)
            self.curve.setData(arr[:, 0], arr[:, 1])
        else:
            self.curve.setData([], [])

    def _import(self):
        fn, _ = QFileDialog.getOpenFileName(self, "Import B-H dataset", "",
                                            "CSV (*.csv);;All (*)")
        if fn:
            bh = BHCurve.from_csv(fn)
            self._load_rows(bh.rows())

    def _export(self):
        fn, _ = QFileDialog.getSaveFileName(self, "Export B-H dataset", "",
                                            "CSV (*.csv)")
        if fn:
            BHCurve.from_rows(self._read_rows()).to_csv(fn)

    # --- result ---------------------------------------------------------
    def apply_to_material(self) -> Material:
        m = self.m
        m.name = self.name.text()
        m.mu_r = self.mu_r.value()
        m.conductivity = self.cond.value()
        m.mass_density = self.dens.value()
        m.is_magnet = self.is_mag.isChecked()
        m.br = self.br.value()
        m.hc = self.hc.value()
        m.mag_dir_deg = self.mdir.value()
        m.kh = self.kh.value()
        m.kc = self.kc.value()
        m.ke = self.ke.value()
        m.bh = BHCurve.from_rows(self._read_rows())
        return m
