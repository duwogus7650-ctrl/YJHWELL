"""Analysis-setup dialogs (v2): excitation, boundary, motion band, mesh
operation, and solve setup — faithful to Maxwell's assignment dialogs."""
from __future__ import annotations

from PyQt6.QtWidgets import (QDialog, QFormLayout, QLineEdit, QDoubleSpinBox,
                             QSpinBox, QComboBox, QCheckBox, QDialogButtonBox,
                             QTabWidget, QWidget, QVBoxLayout)


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
    def __init__(self, default_name, parent=None):
        super().__init__("Element Length Based Refinement", parent)
        self.name = QLineEdit(default_name)
        self.max_len = _spin(1e-3, 1e4, 4, 1.0, 0.1, suffix="mm")
        self.form.addRow("Name", self.name)
        self.form.addRow("Maximum element length", self.max_len)
        self._buttons()

    def values(self):
        return {"name": self.name.text(), "max_length": self.max_len.value()}


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
        # --- Save Fields tab (Maxwell: save field at a single point in time) ---
        sf = QWidget(); sff = QFormLayout(sf)
        self.save_single = QCheckBox("Save fields at a single point")
        self.save_single.setChecked(e.get("save_single", True))
        self.save_time = _spin(0, 1e12, 3, e.get("save_time_ns", 0.0), suffix="ns")
        sff.addRow(self.save_single)
        sff.addRow("Time", self.save_time)
        tabs.addTab(sf, "Save Fields")
        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                              | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept); bb.rejected.connect(self.reject)
        root.addWidget(bb)

    def values(self):
        d = {"name": self.name.text(), "enabled": self.enabled.isChecked(),
             "solver": self.solver,
             "save_single": self.save_single.isChecked(),
             "save_time_ns": self.save_time.value()}
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
