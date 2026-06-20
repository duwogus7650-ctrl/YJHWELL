"""Result plot windows — Rectangular Plot (Torque/Back-EMF vs position) with
CSV export, and the Optimetrics parametric sweep dialog."""
from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QPushButton, QFileDialog, QFormLayout, QComboBox,
                             QDoubleSpinBox, QSpinBox, QTableWidget,
                             QTableWidgetItem, QDialogButtonBox, QProgressBar)


class ResultPlotDialog(QDialog):
    """Rectangular plot (x vs y) with peak-to-peak readout and CSV export."""

    def __init__(self, x, y, xlabel, ylabel, title, parent=None):
        super().__init__(parent)
        self.x = np.asarray(x, float); self.y = np.asarray(y, float)
        self.xlabel, self.ylabel = xlabel, ylabel
        self.setWindowTitle(title)
        self.resize(720, 460)
        root = QVBoxLayout(self)
        plot = pg.PlotWidget(background="#0c1830")
        for ax in ("bottom", "left"):
            plot.getAxis(ax).setPen("#5a6b7b"); plot.getAxis(ax).setTextPen("#9fb3c8")
        plot.setLabel("bottom", xlabel, color="#9fb3c8")
        plot.setLabel("left", ylabel, color="#9fb3c8")
        plot.showGrid(x=True, y=True, alpha=0.25)
        plot.plot(self.x, self.y, pen=pg.mkPen("#2bd6ff", width=2),
                  symbol="o", symbolSize=5, symbolBrush="#e6a23c")
        root.addWidget(plot, 1)
        pk = float(self.y.max() - self.y.min())
        info = QLabel(f"pk-pk = {pk:.4g}    mean = {float(self.y.mean()):.4g}    "
                     f"max = {float(self.y.max()):.4g}    min = {float(self.y.min()):.4g}")
        root.addWidget(info)
        row = QHBoxLayout()
        exp = QPushButton("Export CSV…"); exp.clicked.connect(self._export)
        row.addWidget(exp); row.addStretch(1)
        close = QPushButton("Close"); close.clicked.connect(self.accept)
        row.addWidget(close)
        root.addLayout(row)

    def _export(self):
        fn, _ = QFileDialog.getSaveFileName(self, "Export CSV", "result.csv",
                                            "CSV (*.csv)")
        if fn:
            np.savetxt(fn, np.column_stack([self.x, self.y]), delimiter=",",
                       header=f"{self.xlabel},{self.ylabel}", comments="")


class OptimetricsDialog(QDialog):
    """Parametric sweep: vary one design variable, re-solve, tabulate a metric."""

    def __init__(self, var_names, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Setup Sweep Analysis — Optimetrics")
        self.resize(560, 460)
        root = QVBoxLayout(self)
        form = QFormLayout()
        self.var = QComboBox(); self.var.addItems(var_names)
        self.start = self._spin(1.0); self.stop = self._spin(2.0)
        self.steps = QSpinBox(); self.steps.setRange(2, 50); self.steps.setValue(6)
        self.metric = QComboBox()
        self.metric.addItems(["Torque pk-pk [N·m]", "Bmax [T]"])
        form.addRow("Variable", self.var)
        form.addRow("Start", self.start)
        form.addRow("Stop", self.stop)
        form.addRow("Steps", self.steps)
        form.addRow("Output", self.metric)
        root.addLayout(form)
        self.run_btn = QPushButton("Analyze (run sweep)")
        root.addWidget(self.run_btn)
        self.bar = QProgressBar(); self.bar.setVisible(False); root.addWidget(self.bar)
        self.tbl = QTableWidget(0, 2)
        self.tbl.setHorizontalHeaderLabels(["Variable value", "Output"])
        self.tbl.horizontalHeader().setStretchLastSection(True)
        root.addWidget(self.tbl, 1)
        row = QHBoxLayout()
        self.exp = QPushButton("Export CSV…"); self.exp.setEnabled(False)
        self.exp.clicked.connect(self._export)
        row.addWidget(self.exp); row.addStretch(1)
        close = QPushButton("Close"); close.clicked.connect(self.accept)
        row.addWidget(close); root.addLayout(row)
        self._results = []

    def _spin(self, val):
        s = QDoubleSpinBox(); s.setRange(-1e6, 1e6); s.setDecimals(4); s.setValue(val)
        return s

    def values(self):
        return (self.var.currentText(), self.start.value(), self.stop.value(),
                self.steps.value(), self.metric.currentIndex())

    def set_results(self, rows):
        self._results = rows
        self.tbl.setRowCount(0)
        for v, m in rows:
            r = self.tbl.rowCount(); self.tbl.insertRow(r)
            self.tbl.setItem(r, 0, QTableWidgetItem(f"{v:g}"))
            self.tbl.setItem(r, 1, QTableWidgetItem(f"{m:g}"))
        self.exp.setEnabled(bool(rows))

    def _export(self):
        fn, _ = QFileDialog.getSaveFileName(self, "Export CSV", "sweep.csv",
                                            "CSV (*.csv)")
        if fn and self._results:
            arr = np.asarray(self._results, float)
            np.savetxt(fn, arr, delimiter=",",
                       header=f"{self.var.currentText()},{self.metric.currentText()}",
                       comments="")
