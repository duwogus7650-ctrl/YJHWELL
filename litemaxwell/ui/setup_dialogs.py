"""Analysis-setup dialogs (v2): excitation, boundary, motion band, mesh
operation, and solve setup — faithful to Maxwell's assignment dialogs."""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QFormLayout, QLineEdit, QDoubleSpinBox,
                             QSpinBox, QComboBox, QCheckBox, QDialogButtonBox,
                             QTabWidget, QWidget, QVBoxLayout, QListWidget,
                             QListWidgetItem, QLabel)


def _spin(lo, hi, dec, val, step=1.0, suffix=""):
    s = QDoubleSpinBox(); s.setRange(lo, hi); s.setDecimals(dec); s.setValue(val)
    s.setSingleStep(step)
    if suffix:
        s.setSuffix(" " + suffix)
    s.setMinimumWidth(160)
    return s


class _Base(QDialog):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.form = QFormLayout(self)

    def _buttons(self):
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        self.form.addRow(bb)


class CurrentExcitationDialog(_Base):
    def __init__(self, default_name, parent=None):
        super().__init__("Current Excitation", parent)
        self.name = QLineEdit(default_name)
        self.value = _spin(-1e6, 1e6, 3, 1.0, suffix="A")
        self.ctype = QComboBox(); self.ctype.addItems(["Stranded", "Solid"])
        self.branches = QSpinBox(); self.branches.setRange(1, 1000); self.branches.setValue(1)
        self.form.addRow("Name", self.name)
        self.form.addRow("Value", self.value)
        self.form.addRow("Type", self.ctype)
        self.form.addRow("Number of parallel branches", self.branches)
        self._buttons()

    def values(self):
        return {"name": self.name.text(), "type": "Current",
                "value": self.value.value(), "conductor": self.ctype.currentText(),
                "branches": self.branches.value()}


class VectorPotentialDialog(_Base):
    def __init__(self, default_name, parent=None):
        super().__init__("Vector Potential Boundary", parent)
        self.name = QLineEdit(default_name)
        self.value = _spin(-1e3, 1e3, 6, 0.0, 0.001, suffix="Wb/m")
        self.form.addRow("Name", self.name)
        self.form.addRow("Value", self.value)
        self._buttons()

    def values(self):
        return {"name": self.name.text(), "type": "VectorPotential",
                "value": self.value.value()}


class BandMotionDialog(_Base):
    def __init__(self, parent=None):
        super().__init__("Assign Band — Motion Setup", parent)
        self.name = QLineEdit("Moving1")
        self.mtype = QComboBox(); self.mtype.addItems(["Rotation", "Translation"])
        self.vector = QComboBox(); self.vector.addItems(["Global::Z"])
        self.direction = QComboBox(); self.direction.addItems(["Positive", "Negative"])
        self.init_pos = _spin(-360, 360, 3, -15.0, suffix="deg")
        self.speed = _spin(-1e6, 1e6, 1, 1000.0, suffix="rpm")
        self.form.addRow("Name", self.name)
        self.form.addRow("Motion Type", self.mtype)
        self.form.addRow("Moving Vector", self.vector)
        self.form.addRow("Direction", self.direction)
        self.form.addRow("Initial Position", self.init_pos)
        self.form.addRow("Angular Velocity", self.speed)
        self._buttons()

    def values(self):
        return {"name": self.name.text(), "type": self.mtype.currentText(),
                "vector": self.vector.currentText(),
                "direction": self.direction.currentText(),
                "init_pos": self.init_pos.value(), "speed": self.speed.value()}


class MeshOpDialog(_Base):
    """Maxwell 'Element Length Based Refinement': cap element length on selected
    objects, optionally limiting the number of added elements."""
    def __init__(self, default_name, parent=None):
        super().__init__("Element Length Based Refinement", parent)
        self.name = QLineEdit(default_name)
        self.apply_initial = QCheckBox(); self.apply_initial.setChecked(True)
        self.enabled = QCheckBox(); self.enabled.setChecked(True)
        self.restrict_len = QCheckBox(); self.restrict_len.setChecked(True)
        self.max_len = _spin(1e-3, 1e4, 4, 1.0, 0.1, suffix="mm")
        self.restrict_num = QCheckBox(); self.restrict_num.setChecked(True)
        self.max_elems = QSpinBox(); self.max_elems.setRange(1, 100_000_000)
        self.max_elems.setValue(1000)
        self.form.addRow("Name", self.name)
        self.form.addRow("Apply to Initial Mesh", self.apply_initial)
        self.form.addRow("Enable", self.enabled)
        self.form.addRow("Restrict the maximum element length", self.restrict_len)
        self.form.addRow("Maximum element length", self.max_len)
        self.form.addRow("Restrict the number of additional elements",
                         self.restrict_num)
        self.form.addRow("Maximum number of additional elements", self.max_elems)
        self._buttons()

    def values(self):
        return {"name": self.name.text(),
                "apply_initial": self.apply_initial.isChecked(),
                "enabled": self.enabled.isChecked(),
                "restrict_length": self.restrict_len.isChecked(),
                "max_length": self.max_len.value(),
                "restrict_number": self.restrict_num.isChecked(),
                "max_elems": self.max_elems.value()}


class SolveSetupDialog(QDialog):
    def __init__(self, solver, existing=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Solve Setup")
        self.resize(420, 300)
        root = QVBoxLayout(self)
        tabs = QTabWidget(); root.addWidget(tabs, 1)
        gen = QWidget(); f = QFormLayout(gen)
        e = existing or {}
        self.name = QLineEdit(e.get("name", "Setup1"))
        self.enabled = QCheckBox(); self.enabled.setChecked(e.get("enabled", True))
        f.addRow("Name", self.name)
        f.addRow("Enabled", self.enabled)
        self.solver = solver
        if solver == "Transient":
            self.stop = _spin(0, 1e6, 6, e.get("stop", 0.02), suffix="s")
            self.step = _spin(0, 1e6, 8, e.get("step", 0.0002), suffix="s")
            f.addRow("Stop time", self.stop)
            f.addRow("Time step", self.step)
        else:
            self.passes = QSpinBox(); self.passes.setRange(1, 100)
            self.passes.setValue(e.get("passes", 6))
            self.err = _spin(0, 100, 4, e.get("error", 1.0), suffix="%")
            f.addRow("Maximum number of passes", self.passes)
            f.addRow("Percent error", self.err)
        tabs.addTab(gen, "General")
        # --- Save Fields tab: None / Every / Custom distribution --------------
        # Maxwell: the stop time is always saved; this adds extra field-save
        # times via a distribution (Linear Step / Linear Count / Single Point /
        # Single Point Sweep).
        sf = QWidget(); sff = QFormLayout(sf)
        sfd = e.get("save_fields", {})
        sff.addRow(QLabel("The stop time is saved automatically.\n"
                          "Additional field save times:"))
        self.sf_mode = QComboBox(); self.sf_mode.addItems(["None", "Every", "Custom"])
        self.sf_mode.setCurrentText(sfd.get("mode", "None"))
        self.sf_dist = QComboBox()
        self.sf_dist.addItems(["Linear Step", "Linear Count", "Single Point",
                               "Single Point Sweep"])
        self.sf_dist.setCurrentText(sfd.get("distribution", "Linear Step"))
        self.sf_start = _spin(0, 1e12, 8, sfd.get("start", 0.0), suffix="ns")
        self.sf_stop = _spin(0, 1e12, 8, sfd.get("stop", 0.004), suffix="ns")
        self.sf_step = _spin(0, 1e12, 11, sfd.get("step", 0.00011111), suffix="ns")
        self.sf_count = QSpinBox(); self.sf_count.setRange(1, 1000000)
        self.sf_count.setValue(int(sfd.get("count", 37)))
        sff.addRow("Type", self.sf_mode)
        sff.addRow("Distribution", self.sf_dist)
        sff.addRow("Start", self.sf_start)
        sff.addRow("Stop", self.sf_stop)
        sff.addRow("Step size", self.sf_step)
        sff.addRow("Count", self.sf_count)
        tabs.addTab(sf, "Save Fields")
        self.sf_mode.currentTextChanged.connect(self._sf_update)
        self.sf_dist.currentTextChanged.connect(self._sf_update)
        self._sf_update()
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        root.addWidget(bb)

    def _sf_update(self, *_):
        """Enable only the fields the chosen save-fields mode/distribution uses."""
        mode = self.sf_mode.currentText()
        custom = mode == "Custom"; every = mode == "Every"
        dist = self.sf_dist.currentText()
        self.sf_dist.setEnabled(custom)
        self.sf_start.setEnabled(custom)
        self.sf_stop.setEnabled(custom and dist in (
            "Linear Step", "Linear Count", "Single Point Sweep"))
        self.sf_step.setEnabled(custom and dist == "Linear Step")
        self.sf_count.setEnabled(every or (custom and dist in (
            "Linear Count", "Single Point Sweep")))

    def values(self):
        d = {"name": self.name.text(), "enabled": self.enabled.isChecked(),
             "solver": self.solver,
             "save_fields": {"mode": self.sf_mode.currentText(),
                             "distribution": self.sf_dist.currentText(),
                             "start": self.sf_start.value(),
                             "stop": self.sf_stop.value(),
                             "step": self.sf_step.value(),
                             "count": self.sf_count.value()}}
        if self.solver == "Transient":
            d["stop"] = self.stop.value(); d["step"] = self.step.value()
        else:
            d["passes"] = self.passes.value(); d["error"] = self.err.value()
        return d


class DesignSettingsDialog(QDialog):
    """Maxwell 2D 'Design Settings' + 'Model Settings': symmetry multiplier and
    model depth (stack length).  Symmetry multiplier scales reported torque/EMF/
    loss when only a fraction of the machine is modelled (1 = full model)."""

    def __init__(self, sym_mult=1, depth_mm=28.0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("2D Design Settings")
        self.resize(380, 200)
        root = QVBoxLayout(self)
        tabs = QTabWidget(); root.addWidget(tabs, 1)
        d1 = QWidget(); f1 = QFormLayout(d1)
        self.sym = QSpinBox(); self.sym.setRange(1, 360); self.sym.setValue(int(sym_mult))
        f1.addRow("Symmetry Multiplier", self.sym)
        tabs.addTab(d1, "Design Settings")
        d2 = QWidget(); f2 = QFormLayout(d2)
        self.depth = _spin(1e-3, 1e5, 4, depth_mm, suffix="mm")
        f2.addRow("Model Depth (L_stk)", self.depth)
        tabs.addTab(d2, "Model Settings")
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        root.addWidget(bb)

    def values(self):
        return {"symmetry_mult": self.sym.value(), "model_depth": self.depth.value()}


def _checklist(names, preselected):
    lw = QListWidget()
    pre = set(preselected or [])
    for nm in names:
        it = QListWidgetItem(nm)
        it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        it.setCheckState(Qt.CheckState.Checked if nm in pre else Qt.CheckState.Unchecked)
        lw.addItem(it)
    return lw


def _checked(lw):
    return [lw.item(i).text() for i in range(lw.count())
            if lw.item(i).checkState() == Qt.CheckState.Checked]


class SetEddyEffectDialog(QDialog):
    """Maxwell 'Set Eddy Effect': tick the conductors that carry eddy currents."""
    def __init__(self, object_names, preselected=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set Eddy Effect")
        self.resize(320, 360)
        root = QVBoxLayout(self)
        root.addWidget(QLabel("Eddy effect on:"))
        self.lst = _checklist(object_names, preselected)
        root.addWidget(self.lst, 1)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        root.addWidget(bb)

    def values(self):
        return _checked(self.lst)


class CreateFieldPlotDialog(QDialog):
    """Maxwell 'Create Field Plot': name, folder, quantity, the bodies (In Volume,
    incl. AllObjects), and edge/streamline options."""
    QUANTITIES = ["Flux_Lines", "A_Vector", "Mag_H", "H_Vector", "Mag_B",
                  "B_Vector", "Jz", "J_Vector", "energy", "coEnergy", "appEnergy",
                  "Core_Loss", "Ohmic_Loss", "Total_Loss", "surfaceForceDensity",
                  "edgeForceDensity", "Temperature", "Demag_Coef"]

    def __init__(self, object_names, default_name="B1", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Field Plot")
        self.resize(360, 460)
        root = QVBoxLayout(self)
        form = QFormLayout()
        self.name = QLineEdit(default_name)
        self.folder = QLineEdit("B")
        self.category = QComboBox(); self.category.addItems(["Standard"])
        self.quantity = QComboBox(); self.quantity.addItems(self.QUANTITIES)
        self.quantity.setCurrentText("Mag_B")          # Maxwell default
        form.addRow("Name", self.name)
        form.addRow("Folder", self.folder)
        form.addRow("Category", self.category)
        form.addRow("Quantity", self.quantity)
        root.addLayout(form)
        root.addWidget(QLabel("In Volume:"))
        # AllObjects first (Maxwell lists it at the bottom but it's the common pick)
        self.lst = _checklist(list(object_names) + ["AllObjects"], ["AllObjects"])
        root.addWidget(self.lst, 1)
        self.edge_only = QCheckBox("Plot on edge only")
        self.streamline = QCheckBox("Streamline plot")
        root.addWidget(self.edge_only)
        root.addWidget(self.streamline)
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        root.addWidget(bb)

    def values(self):
        objs = _checked(self.lst)
        if "AllObjects" in objs:               # expand to every body
            objs = [self.lst.item(i).text() for i in range(self.lst.count())
                    if self.lst.item(i).text() != "AllObjects"]
        return {"name": self.name.text(), "folder": self.folder.text(),
                "quantity": self.quantity.currentText(), "objects": objs,
                "edge_only": self.edge_only.isChecked(),
                "streamline": self.streamline.isChecked()}
