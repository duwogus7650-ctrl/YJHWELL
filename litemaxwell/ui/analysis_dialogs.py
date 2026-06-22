"""Analysis / post-processing dialogs — faithful to Ansys Maxwell 2D 2024 R1:
'2D Design Settings', the 'New Report - New Trace(s)' trace builder, the field-
legend colormap editor, and 'Clean Up Solutions'.  These are deliberately kept
self-contained (each dialog exposes a values() dict) so the main window can drive
them without coupling to the solver/model layer."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QFormLayout, QVBoxLayout, QHBoxLayout,
                             QGridLayout, QLineEdit, QDoubleSpinBox, QSpinBox,
                             QComboBox, QCheckBox, QRadioButton, QButtonGroup,
                             QGroupBox, QDialogButtonBox, QTabWidget, QWidget,
                             QListWidget, QListWidgetItem, QLabel, QPushButton,
                             QTableWidget, QTableWidgetItem)


def _spin(lo, hi, dec, val, step=1.0, suffix=""):
    """Shared numeric spin helper (matches setup_dialogs._spin)."""
    s = QDoubleSpinBox(); s.setRange(lo, hi); s.setDecimals(dec); s.setValue(val)
    s.setSingleStep(step)
    if suffix:
        s.setSuffix(" " + suffix)
    s.setMinimumWidth(160)
    return s


def _checklist(names, preselected):
    lw = QListWidget()
    pre = set(preselected or [])
    for nm in names:
        it = QListWidgetItem(nm)
        it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        it.setCheckState(Qt.CheckState.Checked if nm in pre
                         else Qt.CheckState.Unchecked)
        lw.addItem(it)
    return lw


def _checked(lw):
    return [lw.item(i).text() for i in range(lw.count())
            if lw.item(i).checkState() == Qt.CheckState.Checked]


def _korean_buttons(bb):
    """Apply Korean labels to the standard buttons present on a QDialogButtonBox."""
    SB = QDialogButtonBox.StandardButton
    for std, txt in ((SB.Ok, "확인"), (SB.Cancel, "취소"), (SB.Apply, "적용(A)")):
        b = bb.button(std)
        if b is not None:
            b.setText(txt)


class DesignSettingsDialog(QDialog):
    """Maxwell 2D '2D Design Settings' (tabbed): material thresholds, symmetry
    multiplier, and model settings incl. an optional skew model.

    The symmetry multiplier scales reported torque/EMF/loss when only a fraction
    of the machine is modelled (1 = full model).  Model depth is kept as a raw
    string because it is usually a design variable (e.g. ``L_stk``)."""

    def __init__(self, sym_mult=1, depth="L_stk", use_skew=False,
                 n_slices=5, skew_angle=5.0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("2D Design Settings")
        self.resize(460, 460)
        root = QVBoxLayout(self)
        tabs = QTabWidget(); root.addWidget(tabs, 1)

        # --- Material Thresholds ---------------------------------------
        mt = QWidget(); f1 = QFormLayout(mt)
        self.pec = QLineEdit("1e+30")
        self.ins = QLineEdit("1")
        f1.addRow("Perfect Conductor >=", self.pec)
        f1.addRow("", QLabel("Siemens/m"))
        f1.addRow("Insulator <", self.ins)
        f1.addRow("", QLabel("Siemens/m"))
        tabs.addTab(mt, "Material Thresholds")

        # --- Symmetry Multiplier ---------------------------------------
        sm = QWidget(); f2 = QFormLayout(sm)
        self.sym = QSpinBox(); self.sym.setRange(1, 360)
        self.sym.setValue(int(sym_mult)); self.sym.setMinimumWidth(160)
        f2.addRow("Symmetry Multiplier", self.sym)
        tabs.addTab(sm, "Symmetry Multiplier")

        # --- Model Settings --------------------------------------------
        ms = QWidget(); f3 = QFormLayout(ms)
        self.depth = QLineEdit(str(depth))      # raw expression (may be a variable)
        self.depth_unit = QComboBox(); self.depth_unit.addItems(["meter", "mm"])
        self.depth_unit.setCurrentText("mm")
        f3.addRow("Model Depth", self.depth)
        f3.addRow("Units", self.depth_unit)

        skew = QGroupBox("Skew Model")
        sg = QFormLayout(skew)
        self.use_skew = QCheckBox("Use Skew Model")
        self.use_skew.setChecked(bool(use_skew))
        sg.addRow(self.use_skew)
        # Skew Part radios (Rotor / Stator)
        self.skew_rotor = QRadioButton("Rotor")
        self.skew_stator = QRadioButton("Stator")
        self.skew_rotor.setChecked(True)
        self._skew_part = QButtonGroup(self)
        self._skew_part.addButton(self.skew_rotor)
        self._skew_part.addButton(self.skew_stator)
        part_row = QHBoxLayout()
        part_row.addWidget(self.skew_rotor); part_row.addWidget(self.skew_stator)
        part_row.addStretch(1)
        part_w = QWidget(); part_w.setLayout(part_row)
        sg.addRow("Skew Part", part_w)
        self.skew_type = QComboBox()
        self.skew_type.addItems(["Continuous", "Discrete"])
        sg.addRow("Skew Type", self.skew_type)
        self.n_slices = QSpinBox(); self.n_slices.setRange(1, 1000)
        self.n_slices.setValue(int(n_slices)); self.n_slices.setMinimumWidth(160)
        sg.addRow("No. of Slices", self.n_slices)
        self.skew_angle = _spin(-360.0, 360.0, 4, float(skew_angle), suffix="deg")
        sg.addRow("Skew Angle", self.skew_angle)
        self.slice_tbl = QTableWidget(0, 3)
        self.slice_tbl.setHorizontalHeaderLabels(
            ["Slice No.", "Skew Angle (deg)", "Slice Length"])
        self.slice_tbl.horizontalHeader().setStretchLastSection(True)
        self.slice_tbl.verticalHeader().setVisible(False)
        sg.addRow(self.slice_tbl)
        f3.addRow(skew)
        tabs.addTab(ms, "Model Settings")

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        _korean_buttons(bb)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        root.addWidget(bb)

    def values(self):
        return {
            "symmetry_mult": self.sym.value(),
            "model_depth": self.depth.text(),          # raw string (variable expr)
            "depth_unit": self.depth_unit.currentText(),
            "use_skew": self.use_skew.isChecked(),
            "skew_part": "Rotor" if self.skew_rotor.isChecked() else "Stator",
            "skew_type": self.skew_type.currentText(),
            "n_slices": self.n_slices.value(),
            "skew_angle": self.skew_angle.value(),
        }


class ReportTraceDialog(QDialog):
    """Maxwell 'Report: New Report - New Trace(s)' trace builder.  The Quantity
    list is repopulated whenever the Category selection changes, mirroring the
    real dialog's left-to-right Category -> Quantity flow."""

    CATEGORIES = ["Torque", "Speed", "Position", "Winding", "Loss",
                  "Variables", "Output Variables"]
    QUANTITIES = {
        "Torque": ["Moving1.Torque", "Moving1.LoadTorque"],
        "Speed": ["Moving1.Speed"],
        "Position": ["Moving1.Position"],
        "Winding": ["InducedVoltage(PhaseA)", "InducedVoltage(PhaseB)",
                    "InducedVoltage(PhaseC)",
                    "FluxLinkage(PhaseA)", "FluxLinkage(PhaseB)",
                    "FluxLinkage(PhaseC)",
                    "InputCurrent(PhaseA)", "InputCurrent(PhaseB)",
                    "InputCurrent(PhaseC)"],
        "Loss": ["CoreLoss", "SolidLoss", "StrandedLoss"],
        "Variables": [],
        "Output Variables": [],
    }
    FUNCTIONS = ["<none>", "abs", "avg", "rms", "ang_deg"]

    def __init__(self, solutions=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Report: New Report - New Trace(s)")
        self.resize(640, 480)
        root = QVBoxLayout(self)

        # --- Context group ---------------------------------------------
        ctx = QGroupBox("Context")
        cf = QFormLayout(ctx)
        self.solution = QComboBox()
        self.solution.addItems(solutions or ["Setup1 : Transient"])
        self.domain = QComboBox(); self.domain.addItems(["Sweep", "Time"])
        self.parameter = QComboBox(); self.parameter.addItems(["None"])
        cf.addRow("Solution", self.solution)
        cf.addRow("Domain", self.domain)
        cf.addRow("Parameter", self.parameter)
        root.addWidget(ctx)

        # --- Trace area -------------------------------------------------
        trace = QGroupBox("Trace")
        grid = QGridLayout(trace)
        self.primary = QComboBox(); self.primary.addItems(["Time"])  # fixed
        grid.addWidget(QLabel("Primary Sweep"), 0, 0)
        grid.addWidget(self.primary, 0, 1)

        grid.addWidget(QLabel("Category"), 1, 0)
        grid.addWidget(QLabel("Quantity"), 1, 1)
        grid.addWidget(QLabel("Function"), 1, 2)

        self.category = QListWidget()
        self.category.addItems(self.CATEGORIES)
        self.quantity = QListWidget()
        self.function = QListWidget()
        self.function.addItems(self.FUNCTIONS)
        grid.addWidget(self.category, 2, 0)
        grid.addWidget(self.quantity, 2, 1)
        grid.addWidget(self.function, 2, 2)
        root.addWidget(trace, 1)

        # repopulate Quantity when Category changes
        self.category.currentItemChanged.connect(self._on_category)
        self.category.setCurrentRow(0)        # selects Torque, fills quantity

        # --- Buttons (New Report -> accept, Close -> reject) -----------
        bb = QDialogButtonBox()
        self.btn_new = bb.addButton("New Report",
                                    QDialogButtonBox.ButtonRole.AcceptRole)
        self.btn_close = bb.addButton("Close",
                                      QDialogButtonBox.ButtonRole.RejectRole)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        root.addWidget(bb)

    def _on_category(self, cur, _prev=None):
        self.quantity.clear()
        if cur is None:
            return
        self.quantity.addItems(self.QUANTITIES.get(cur.text(), []))
        if self.quantity.count():
            self.quantity.setCurrentRow(0)

    def values(self):
        cat_item = self.category.currentItem()
        qty_item = self.quantity.currentItem()
        fn_item = self.function.currentItem()
        return {
            "solution": self.solution.currentText(),
            "domain": self.domain.currentText(),
            "category": cat_item.text() if cat_item else None,
            "quantity": qty_item.text() if qty_item else None,
            "function": fn_item.text() if fn_item else "<none>",
        }


class ColormapDialog(QDialog):
    """Field-legend colormap editor (Maxwell: double-click the 'B [mTesla]'
    legend).  Tabs: 'Color map' (type + spectrum) and 'Scale' (divisions,
    auto/limits, linear/log, units)."""

    def __init__(self, vmin=0.0, vmax=2354.657, divisions=10,
                 units="mTesla", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Color Map")
        self.resize(380, 360)
        root = QVBoxLayout(self)
        tabs = QTabWidget(); root.addWidget(tabs, 1)

        # --- Color map tab ---------------------------------------------
        cm = QWidget(); cl = QVBoxLayout(cm)
        type_box = QGroupBox("Type")
        tl = QHBoxLayout(type_box)
        self.rb_uniform = QRadioButton("Uniform")
        self.rb_ramp = QRadioButton("Ramp")
        self.rb_spectrum = QRadioButton("Spectrum")
        self.rb_spectrum.setChecked(True)     # default Spectrum
        self._type = QButtonGroup(self)
        for rb in (self.rb_uniform, self.rb_ramp, self.rb_spectrum):
            self._type.addButton(rb); tl.addWidget(rb)
        tl.addStretch(1)
        cl.addWidget(type_box)
        spec_form = QFormLayout()
        self.spectrum = QComboBox()
        self.spectrum.addItems(["Rainbow", "GrayScale", "Magma"])
        self.spectrum.setCurrentText("Rainbow")   # default
        spec_form.addRow("Spectrum", self.spectrum)
        cl.addLayout(spec_form)
        cl.addStretch(1)
        tabs.addTab(cm, "Color map")

        # --- Scale tab -------------------------------------------------
        sc = QWidget(); sf = QFormLayout(sc)
        self.divisions = QSpinBox(); self.divisions.setRange(1, 100)
        self.divisions.setValue(int(divisions)); self.divisions.setMinimumWidth(160)
        sf.addRow("Num. Division", self.divisions)

        self.rb_auto = QRadioButton("Auto")
        self.rb_limits = QRadioButton("Use Limits")
        self.rb_auto.setChecked(True)
        self._scale_mode = QButtonGroup(self)
        self._scale_mode.addButton(self.rb_auto)
        self._scale_mode.addButton(self.rb_limits)
        mode_row = QHBoxLayout()
        mode_row.addWidget(self.rb_auto); mode_row.addWidget(self.rb_limits)
        mode_row.addStretch(1)
        mode_w = QWidget(); mode_w.setLayout(mode_row)
        sf.addRow(mode_w)

        self.vmin = QLineEdit(f"{vmin:g}")
        self.vmax = QLineEdit(f"{vmax:g}")
        sf.addRow("Min", self.vmin)
        sf.addRow("Max", self.vmax)

        self.rb_linear = QRadioButton("Linear")
        self.rb_log = QRadioButton("Log")
        self.rb_linear.setChecked(True)
        self._scale_type = QButtonGroup(self)
        self._scale_type.addButton(self.rb_linear)
        self._scale_type.addButton(self.rb_log)
        sty_row = QHBoxLayout()
        sty_row.addWidget(self.rb_linear); sty_row.addWidget(self.rb_log)
        sty_row.addStretch(1)
        sty_w = QWidget(); sty_w.setLayout(sty_row)
        sf.addRow(sty_w)

        self.units = QComboBox(); self.units.addItems(["mTesla", "Tesla", "Gauss"])
        self.units.setCurrentText(units if units in ("mTesla", "Tesla", "Gauss")
                                  else "mTesla")
        sf.addRow("Units", self.units)
        tabs.addTab(sc, "Scale")

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        _korean_buttons(bb)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        root.addWidget(bb)

    def _type_text(self):
        if self.rb_uniform.isChecked():
            return "Uniform"
        if self.rb_ramp.isChecked():
            return "Ramp"
        return "Spectrum"

    def values(self):
        def _f(le, default):
            try:
                return float(le.text())
            except ValueError:
                return default
        return {
            "type": self._type_text(),
            "spectrum": self.spectrum.currentText(),
            "divisions": self.divisions.value(),
            "auto": self.rb_auto.isChecked(),
            "vmin": _f(self.vmin, 0.0),
            "vmax": _f(self.vmax, 0.0),
            "log": self.rb_log.isChecked(),
            "units": self.units.currentText(),
        }


class CleanUpSolutionsDialog(QDialog):
    """Maxwell 'Clean Up Solutions': pick what to delete (solutions scope) and
    over which variations.  Deletions are immediate and unrecoverable."""

    SOLUTIONS = ["Linked Data Only", "Fields Only", "Fields and Meshes",
                 "All Solutions"]
    VARIATIONS = ["All Except Current Variation", "All Variations", "Select"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Clean Up Solutions")
        self.resize(380, 300)
        root = QVBoxLayout(self)

        sol_box = QGroupBox("Solutions")
        sl = QVBoxLayout(sol_box)
        self._sol = QButtonGroup(self)
        self._sol_rbs = []
        for nm in self.SOLUTIONS:
            rb = QRadioButton(nm)
            self._sol.addButton(rb); sl.addWidget(rb); self._sol_rbs.append(rb)
            if nm == "All Solutions":           # default
                rb.setChecked(True)
        root.addWidget(sol_box)

        var_box = QGroupBox("Variations")
        vl = QVBoxLayout(var_box)
        self._var = QButtonGroup(self)
        self._var_rbs = []
        for nm in self.VARIATIONS:
            rb = QRadioButton(nm)
            self._var.addButton(rb); vl.addWidget(rb); self._var_rbs.append(rb)
            if nm == "All Variations":          # default
                rb.setChecked(True)
        root.addWidget(var_box)

        note = QLabel("All deletions will occur immediately and "
                      "cannot be recovered.")
        note.setWordWrap(True)
        root.addWidget(note)

        bb = QDialogButtonBox()
        self.btn_do = bb.addButton("Do Deletions",
                                   QDialogButtonBox.ButtonRole.AcceptRole)
        self.btn_cancel = bb.addButton("취소",
                                       QDialogButtonBox.ButtonRole.RejectRole)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        root.addWidget(bb)

    def _checked_text(self, rbs, default):
        for rb in rbs:
            if rb.isChecked():
                return rb.text()
        return default

    def values(self):
        return {
            "solutions": self._checked_text(self._sol_rbs, "All Solutions"),
            "variations": self._checked_text(self._var_rbs, "All Variations"),
        }


class SetViewContextDialog(QDialog):
    """Maxwell 'Set View Context' — opened by double-clicking the on-canvas
    'Time = …' overlay.  Chooses which solved time instant the model window shows
    and whether the Speed/Position labels are drawn."""

    CORNERS = ["Upper left", "Upper right", "Lower left", "Lower right"]

    def __init__(self, solutions=None, time="0", times=None,
                 corner="Lower left", show_speed_pos=True, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set View Context")
        self.resize(360, 260)
        root = QVBoxLayout(self)
        form = QFormLayout()
        self.solution = QComboBox()
        self.solution.addItems(solutions or ["Setup1 : Transient"])
        self.time = QComboBox(); self.time.setEditable(True)
        for t in (times or [str(time)]):
            self.time.addItem(str(t))
        self.time.setCurrentText(str(time))
        form.addRow("Solution Name", self.solution)
        form.addRow("Time", self.time)
        root.addLayout(form)

        box = QGroupBox("Display label at screen corner")
        grid = QGridLayout(box)
        self._corner = QButtonGroup(self)
        self._corner_rbs = []
        for i, nm in enumerate(self.CORNERS):
            rb = QRadioButton(nm)
            if nm == corner:
                rb.setChecked(True)
            self._corner.addButton(rb); self._corner_rbs.append(rb)
            grid.addWidget(rb, i // 2, i % 2)
        root.addWidget(box)

        self.show_sp = QCheckBox("Display speed and position values")
        self.show_sp.setChecked(bool(show_speed_pos))
        root.addWidget(self.show_sp)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        _korean_buttons(bb)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        root.addWidget(bb)

    def values(self):
        corner = next((rb.text() for rb in self._corner_rbs if rb.isChecked()),
                      "Lower left")
        return {"solution": self.solution.currentText(),
                "time": self.time.currentText(), "corner": corner,
                "show_speed_pos": self.show_sp.isChecked()}
