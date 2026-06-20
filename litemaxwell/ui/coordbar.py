"""Maxwell-style coordinate entry bar (sits in the status bar).

Lets you place draw points by typing exact values — Absolute/Relative origin
and Cartesian (X/Y) or Polar (r/θ) — and press Enter, just like AEDT.
"""
from __future__ import annotations

import math

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QComboBox, QLineEdit, QLabel)
from PyQt6.QtGui import QDoubleValidator


class CoordBar(QWidget):
    pointSubmitted = pyqtSignal(float, float)   # absolute scene coords

    def __init__(self):
        super().__init__()
        self._base = (0.0, 0.0)
        lay = QHBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0); lay.setSpacing(4)
        self.origin = QComboBox(); self.origin.addItems(["Absolute", "Relative"])
        self.system = QComboBox(); self.system.addItems(["Cartesian", "Polar"])
        self.lx = QLabel("X"); self.ly = QLabel("Y")
        self.x = QLineEdit("0"); self.y = QLineEdit("0")
        for w in (self.x, self.y):
            w.setValidator(QDoubleValidator()); w.setFixedWidth(70)
            w.returnPressed.connect(self._submit)
        self.system.currentTextChanged.connect(self._relabel)
        for w in (self.origin, self.system, self.lx, self.x, self.ly, self.y):
            lay.addWidget(w)

    def _relabel(self, mode):
        if mode == "Polar":
            self.lx.setText("r"); self.ly.setText("θ°")
        else:
            self.lx.setText("X"); self.ly.setText("Y")

    def set_base(self, x, y):
        self._base = (x, y)

    def set_live(self, x, y):
        if not self.x.hasFocus() and not self.y.hasFocus():
            if self.system.currentText() == "Cartesian":
                self.x.setText(f"{x:.3g}"); self.y.setText(f"{y:.3g}")

    def _submit(self):
        try:
            a = float(self.x.text()); b = float(self.y.text())
        except ValueError:
            return
        if self.system.currentText() == "Polar":
            dx = a * math.cos(math.radians(b)); dy = a * math.sin(math.radians(b))
        else:
            dx, dy = a, b
        if self.origin.currentText() == "Relative":
            dx += self._base[0]; dy += self._base[1]
        self.pointSubmitted.emit(dx, dy)
