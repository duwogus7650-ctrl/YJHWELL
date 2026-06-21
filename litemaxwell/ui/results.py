"""Result plot windows — Rectangular Plot (Torque/Back-EMF vs position) with
CSV export, and the Optimetrics parametric sweep dialog."""
from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QMenu,
                             QPushButton, QFileDialog, QFormLayout, QComboBox,
                             QDoubleSpinBox, QSpinBox, QTableWidget,
                             QTableWidgetItem, QDialogButtonBox, QProgressBar)


class ResultPlotDialog(QDialog):
    """Rectangular plot (x vs y) with CSV export and a Maxwell-style right-click
    statistics menu (Average / Pk-Pk / Max / Min / RMS) that drops marker lines."""

    def __init__(self, x, y, xlabel, ylabel, title, parent=None, series=None):
        super().__init__(parent)
        self.x = np.asarray(x, float)
        self.xlabel, self.ylabel = xlabel, ylabel
        # series: optional [(label, y_array), ...] for multi-trace (e.g. 3-phase
        # back-EMF). When given, it overrides the single y curve.
        self.series = [(lab, np.asarray(yy, float)) for lab, yy in (series or [])]
        if not self.series:
            self.series = [(ylabel, np.asarray(y, float))]
        self.setWindowTitle(title)
        self.resize(720, 460)
        root = QVBoxLayout(self)
        self.plot = pg.PlotWidget(background="#0c1830")
        for ax in ("bottom", "left"):
            self.plot.getAxis(ax).setPen("#5a6b7b")
            self.plot.getAxis(ax).setTextPen("#9fb3c8")
        self.plot.setLabel("bottom", xlabel, color="#9fb3c8")
        self.plot.setLabel("left", ylabel, color="#9fb3c8")
        self.plot.showGrid(x=True, y=True, alpha=0.25)
        colors = ["#2bd6ff", "#e6a23c", "#7ee081", "#ff6b6b"]
        multi = len(self.series) > 1
        if multi:
            self.plot.addLegend(labelTextColor="#9fb3c8")
        for i, (lab, yy) in enumerate(self.series):
            kw = dict(pen=pg.mkPen(colors[i % len(colors)], width=2), name=lab)
            if not multi:
                kw.update(symbol="o", symbolSize=5, symbolBrush="#e6a23c")
            self.plot.plot(self.x, yy, **kw)
        root.addWidget(self.plot, 1)
        self._stat_lines = {}                # name -> [InfiniteLine,...]
        self.info = QLabel("")
        self._refresh_info()
        root.addWidget(self.info)
        hint = QLabel("plot 우클릭 → Average / Pk-Pk / Max / Min / RMS 마커")
        hint.setStyleSheet("color:#6f8093; font-size:10px;")
        root.addWidget(hint)
        row = QHBoxLayout()
        exp = QPushButton("Export CSV…"); exp.clicked.connect(self._export)
        row.addWidget(exp); row.addStretch(1)
        close = QPushButton("Close"); close.clicked.connect(self.accept)
        row.addWidget(close)
        root.addLayout(row)

    # --- statistics (primary trace) --------------------------------------
    def _stat(self, name):
        y = self.series[0][1]
        return {"Average": float(y.mean()), "Max": float(y.max()),
                "Min": float(y.min()), "Pk-Pk": float(y.max() - y.min()),
                "RMS": float(np.sqrt(np.mean(y ** 2)))}[name]

    def _refresh_info(self):
        y = self.series[0][1]
        self.info.setText(
            f"[{self.series[0][0]}]  mean={y.mean():.4g}  pk-pk={y.max()-y.min():.4g}  "
            f"max={y.max():.4g}  min={y.min():.4g}  rms={np.sqrt(np.mean(y**2)):.4g}")

    def contextMenuEvent(self, ev):
        m = QMenu(self)
        for name in ("Average", "Pk-Pk", "Max", "Min", "RMS"):
            a = m.addAction(name); a.setCheckable(True)
            a.setChecked(name in self._stat_lines)
            a.toggled.connect(lambda on, n=name: self._toggle_stat(n, on))
        m.exec(ev.globalPos())

    def _toggle_stat(self, name, on):
        for ln in self._stat_lines.pop(name, []):
            self.plot.removeItem(ln)
        if not on:
            return
        pen = pg.mkPen("#e6a23c", width=1, style=Qt.PenStyle.DashLine)
        lines = []
        if name == "Pk-Pk":
            vals = [("max", self._stat("Max")), ("min", self._stat("Min"))]
        else:
            vals = [(name, self._stat(name))]
        for tag, v in vals:
            ln = pg.InfiniteLine(pos=v, angle=0, pen=pen, label=f"{tag}={v:.4g}",
                                 labelOpts={"color": "#e6a23c", "position": 0.05})
            self.plot.addItem(ln); lines.append(ln)
        self._stat_lines[name] = lines

    def _export(self):
        fn, _ = QFileDialog.getSaveFileName(self, "Export CSV", "result.csv",
                                            "CSV (*.csv)")
        if fn:
            cols = [self.x] + [yy for _, yy in self.series]
            header = ",".join([self.xlabel] + [lab for lab, _ in self.series])
            np.savetxt(fn, np.column_stack(cols), delimiter=",",
                       header=header, comments="")


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
        self.metric.addItems(["Torque pk-pk [N·m]", "Bmax [T]",
                              "Back-EMF peak [V]", "Load torque avg [N·m]"])
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
