"""Select Definition — the Maxwell material browser (faithful to the video).

Search by name, library list, results grid (Name | Location | Origin), and
View/Edit / Add buttons. Returns the chosen material name; system-library picks
are copied into the project on OK.
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
                             QGroupBox, QLineEdit, QPushButton, QRadioButton,
                             QComboBox, QListWidget, QCheckBox, QLabel,
                             QTableWidget, QTableWidgetItem, QDialogButtonBox,
                             QHeaderView)

from ..model.materials import system_library


class SelectDefinitionDialog(QDialog):
    def __init__(self, project, parent=None):
        super().__init__(parent)
        self.project = project
        self._sys = system_library()
        self.setWindowTitle("Select Definition")
        self.resize(820, 520)
        root = QVBoxLayout(self)

        # --- top: search / criteria / libraries ------------------------
        top = QHBoxLayout()
        gp = QGroupBox("Search Parameters"); gpl = QGridLayout(gp)
        gpl.addWidget(QLabel("Search by Name"), 0, 0)
        self.search = QLineEdit(); self.search.textChanged.connect(self._refresh)
        gpl.addWidget(self.search, 1, 0)
        sbtn = QPushButton("Search"); sbtn.clicked.connect(self._refresh)
        gpl.addWidget(sbtn, 2, 0)
        top.addWidget(gp)

        gc = QGroupBox("Search Criteria"); gcl = QVBoxLayout(gc)
        self.by_name = QRadioButton("by Name"); self.by_name.setChecked(True)
        self.by_prop = QRadioButton("by Property")
        gcl.addWidget(self.by_name); gcl.addWidget(self.by_prop)
        self.prop = QComboBox(); self.prop.addItems(
            ["Relative Permittivity", "Relative Permeability", "Conductivity"])
        self.prop.setEnabled(False)
        self.by_prop.toggled.connect(self.prop.setEnabled)
        gcl.addWidget(self.prop)
        top.addWidget(gc)

        gl = QGroupBox("Libraries"); gll = QVBoxLayout(gl)
        self.libs = QListWidget()
        self.libs.addItems(["[sys] ArnoldMagnetics", "[sys] Benchmark",
                            "[sys] ChinaSteel", "[sys] Granta"])
        gll.addWidget(self.libs)
        self.show_proj = QCheckBox("Show Project definitions"); self.show_proj.setChecked(True)
        self.all_libs = QCheckBox("Select all libraries"); self.all_libs.setChecked(True)
        gll.addWidget(self.show_proj); gll.addWidget(self.all_libs)
        self.show_proj.toggled.connect(self._refresh)
        top.addWidget(gl, 1)
        root.addLayout(top)

        # --- results grid ----------------------------------------------
        self.grid = QTableWidget(0, 3)
        self.grid.setHorizontalHeaderLabels(["Name", "Location", "Origin"])
        self.grid.verticalHeader().setVisible(False)
        self.grid.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.grid.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.grid.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch)
        self.grid.doubleClicked.connect(self.accept)
        root.addWidget(self.grid, 1)

        # --- bottom buttons --------------------------------------------
        row = QHBoxLayout()
        for txt, fn in (("View/Edit Materials…", self._edit),
                        ("Add Material…", self._add),
                        ("Clone Material(s)", lambda: None),
                        ("Remove Material(s)", lambda: None),
                        ("Export to Library…", lambda: None)):
            b = QPushButton(txt); b.clicked.connect(fn); row.addWidget(b)
        root.addLayout(row)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        bb.button(QDialogButtonBox.StandardButton.Ok).setText("확인")
        bb.button(QDialogButtonBox.StandardButton.Cancel).setText("취소")
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        root.addWidget(bb)

        self._rows = []
        self._refresh()

    def _refresh(self, *_):
        q = self.search.text().strip().lower()
        rows = []
        if self.show_proj.isChecked():
            for name in self.project.materials:
                rows.append((name, "Project", "Materials"))
        for name, loc, origin, _m in self._sys:
            rows.append((name, loc, origin))
        rows = [r for r in rows if q in r[0].lower()]
        self._rows = rows
        self.grid.setRowCount(0)
        for r in rows:
            i = self.grid.rowCount(); self.grid.insertRow(i)
            for c, v in enumerate(r):
                self.grid.setItem(i, c, QTableWidgetItem(v))
        if rows:
            self.grid.selectRow(0)

    def selected_name(self):
        r = self.grid.currentRow()
        if r < 0 or r >= len(self._rows):
            return None
        return self._rows[r][0]

    def _ensure_in_project(self, name):
        if name in self.project.materials:
            return
        for n, _loc, _o, m in self._sys:
            if n == name:
                self.project.materials[name] = m
                return

    def _edit(self):
        from .material_dialog import ViewEditMaterialDialog
        name = self.selected_name()
        if not name:
            return
        self._ensure_in_project(name)
        dlg = ViewEditMaterialDialog(self.project.materials[name], self)
        if dlg.exec():
            self.project.materials[name] = dlg.apply_to_material()

    def _add(self):
        from PyQt6.QtWidgets import QInputDialog
        from ..model.materials import Material
        nm, ok = QInputDialog.getText(self, "Add Material", "Name:")
        if ok and nm:
            self.project.materials[nm] = Material(nm)
            self._refresh()

    def accept(self):
        name = self.selected_name()
        if name:
            self._ensure_in_project(name)
        super().accept()
