"""Excitation-assignment dialogs — faithful to Ansys Maxwell 2D's
Winding / Coil Excitation / Add Terminals / Set Core Loss dialogs
(Maxwell 2024 R1). Each dialog exposes a values() method.

Korean button text matches the litemaxwell house style:
  Ok -> "확인", Cancel -> "취소", Apply -> "적용(A)".
"""
from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog, QFormLayout, QVBoxLayout, QHBoxLayout,
                             QLineEdit, QDoubleSpinBox, QComboBox, QLabel,
                             QListWidget, QListWidgetItem, QPushButton,
                             QTableWidget, QTableWidgetItem, QDialogButtonBox,
                             QWidget)


# --- shared house-style helpers ------------------------------------------
def _spin(lo, hi, dec, val, step=1.0, suffix=""):
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
        it.setCheckState(Qt.CheckState.Checked if nm in pre else Qt.CheckState.Unchecked)
        lw.addItem(it)
    return lw


def _checked(lw):
    return [lw.item(i).text() for i in range(lw.count())
            if lw.item(i).checkState() == Qt.CheckState.Checked]


def _ok_cancel(layout, dialog):
    """Standard 확인/취소 button box wired to accept/reject."""
    bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok
                          | QDialogButtonBox.StandardButton.Cancel)
    bb.button(QDialogButtonBox.StandardButton.Ok).setText("확인")
    bb.button(QDialogButtonBox.StandardButton.Cancel).setText("취소")
    bb.accepted.connect(dialog.accept); bb.rejected.connect(dialog.reject)
    layout.addWidget(bb)
    return bb


# --- 1) Winding -----------------------------------------------------------
class WindingDialog(QDialog):
    """Maxwell 'Winding' (Add Winding) dialog.

    The winding groups coil terminals and drives them with a Current,
    Voltage, or External source.  Current/Voltage/Resistance/Inductance and
    the parallel-branch count are entered as EXPRESSION strings so that
    project variables (Ia_max, omega, a, …) can be used directly.
    """
    def __init__(self, default_name="PhaseA",
                 default_current="Ia_max*sin(omega*time)", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Winding")
        self.resize(360, 320)
        form = QFormLayout(self)

        self.name = QLineEdit(default_name)
        self.wtype = QComboBox()
        self.wtype.addItems(["Current", "Voltage", "External"])
        self.conductor = QComboBox()
        self.conductor.addItems(["Stranded", "Solid"])   # default Stranded
        # Source / parasitic expressions — strings so variables are allowed.
        self.current = QLineEdit(default_current)
        self.resistance = QLineEdit("0")
        self.inductance = QLineEdit("0")
        self.voltage = QLineEdit("0")
        self.branches = QLineEdit("a")   # may be a variable expr

        form.addRow("Name", self.name)
        form.addRow("Type", self.wtype)
        form.addRow("Conductor model", self.conductor)
        form.addRow("Current", self.current)
        # suffixes shown as plain labels (units), value stays an expression
        form.addRow("Resistance (ohm)", self.resistance)
        form.addRow("Inductance (nH)", self.inductance)
        form.addRow("Voltage (mV)", self.voltage)
        form.addRow("Number of parallel branches", self.branches)

        _ok_cancel(form, self)

    def values(self):
        return {
            "name": self.name.text(),
            "type": self.wtype.currentText(),
            "conductor": self.conductor.currentText(),
            "current": self.current.text(),
            "resistance": self.resistance.text(),
            "inductance": self.inductance.text(),
            "voltage": self.voltage.text(),
            "branches": self.branches.text(),
        }


# --- 2) Coil Excitation ---------------------------------------------------
class CoilExcitationDialog(QDialog):
    """Maxwell 'Coil Excitation' dialog.

    Assigns the base name, number of conductors per coil (Zc, can be a
    variable) and the polarity used when the coil is bundled into a winding.
    """
    def __init__(self, default_base="Ph_A", default_conductors="Zc", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Coil Excitation")
        self.resize(320, 180)
        form = QFormLayout(self)

        self.base_name = QLineEdit(default_base)
        self.conductors = QLineEdit(default_conductors)   # e.g. "Zc"
        self.polarity = QComboBox()
        self.polarity.addItems(["Positive", "Negative", "Function"])

        form.addRow("Base Name", self.base_name)
        form.addRow("Number of Conductors", self.conductors)
        form.addRow("Polarity", self.polarity)

        _ok_cancel(form, self)

    def values(self):
        return {
            "base_name": self.base_name.text(),
            "conductors": self.conductors.text(),
            "polarity": self.polarity.currentText(),
        }


# --- 3) Add Terminals -----------------------------------------------------
class AddTerminalsDialog(QDialog):
    """Maxwell 'Add Terminals' dialog.

    Lists candidate coil terminals; the user ticks the ones to add to the
    current winding.  Columns mirror Maxwell:
        Coil Terminal | Conductor Number | Currently Assigned To
    """
    LISTING_OPTIONS = [
        "Terminals not assigned to any winding",
        "Terminals not assigned to this winding",
    ]
    COLS = ["Coil Terminal", "Conductor Number", "Currently Assigned To"]

    def __init__(self, terminals, conductor_number="Zc", parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Terminals")
        self.resize(440, 360)
        root = QVBoxLayout(self)

        opt_row = QHBoxLayout()
        opt_row.addWidget(QLabel("Terminal Listing Options"))
        self.listing = QComboBox()
        self.listing.addItems(self.LISTING_OPTIONS)
        opt_row.addWidget(self.listing, 1)
        root.addLayout(opt_row)

        terminals = list(terminals or [])
        self.tbl = QTableWidget(len(terminals), len(self.COLS))
        self.tbl.setHorizontalHeaderLabels(self.COLS)
        self.tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl.verticalHeader().setVisible(False)
        for r, name in enumerate(terminals):
            # col 0: terminal name, checkable (user picks which to assign)
            it = QTableWidgetItem(name)
            it.setFlags((it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                        & ~Qt.ItemFlag.ItemIsEditable)
            it.setCheckState(Qt.CheckState.Unchecked)
            self.tbl.setItem(r, 0, it)
            # col 1: conductor number
            cn = QTableWidgetItem(str(conductor_number))
            cn.setFlags(cn.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.tbl.setItem(r, 1, cn)
            # col 2: currently assigned to (empty -> assignable)
            asg = QTableWidgetItem("")
            asg.setFlags(asg.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.tbl.setItem(r, 2, asg)
        self.tbl.resizeColumnsToContents()
        root.addWidget(self.tbl, 1)

        _ok_cancel(root, self)

    def values(self):
        """list[str] of CHECKED terminal names."""
        out = []
        for r in range(self.tbl.rowCount()):
            it = self.tbl.item(r, 0)
            if it is not None and it.checkState() == Qt.CheckState.Checked:
                out.append(it.text())
        return out


# --- 4) Set Core Loss -----------------------------------------------------
class SetCoreLossDialog(QDialog):
    """Maxwell 'Set Core Loss' dialog (mirror of Set Eddy Effect).

    Tick the objects on which core loss is computed.  The right column is a
    read-only indicator of whether that object's assigned material actually
    defines core-loss coefficients in the material library — without a
    definition the setting has no effect.
    """
    NOTE = ("Use checkboxes to turn on/off core loss settings. The setting "
            "only takes effect if the object has a corresponding core loss "
            "definition in the material library.")
    COLS = ["Object", "Core Loss Setting", "Defined in Material"]

    def __init__(self, object_names, preselected=None,
                 defined_in_material=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Set Core Loss")
        self.resize(420, 400)
        root = QVBoxLayout(self)

        note = QLabel(self.NOTE)
        note.setWordWrap(True)
        root.addWidget(note)

        names = list(object_names or [])
        pre = set(preselected or [])
        defined = set(defined_in_material or [])

        self.tbl = QTableWidget(len(names), len(self.COLS))
        self.tbl.setHorizontalHeaderLabels(self.COLS)
        self.tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tbl.verticalHeader().setVisible(False)
        for r, name in enumerate(names):
            # col 0: object name + checkbox = the core-loss "on" setting
            it = QTableWidgetItem(name)
            it.setFlags((it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                        & ~Qt.ItemFlag.ItemIsEditable)
            it.setCheckState(Qt.CheckState.Checked if name in pre
                             else Qt.CheckState.Unchecked)
            self.tbl.setItem(r, 0, it)
            # col 1: read-only check echoing the on/off state
            cl = QTableWidgetItem("")
            cl.setFlags((cl.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                        & ~Qt.ItemFlag.ItemIsEditable
                        & ~Qt.ItemFlag.ItemIsEnabled)
            cl.setCheckState(it.checkState())
            self.tbl.setItem(r, 1, cl)
            # col 2: does the material define core loss?  read-only.
            dm = QTableWidgetItem("Yes" if name in defined else "No")
            dm.setFlags(dm.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.tbl.setItem(r, 2, dm)
        self.tbl.resizeColumnsToContents()
        self.tbl.itemChanged.connect(self._sync_setting_col)
        root.addWidget(self.tbl, 1)

        btn_row = QHBoxLayout()
        self.btn_select = QPushButton("Select By Name")
        self.btn_deselect = QPushButton("Deselect All")
        self.btn_select.clicked.connect(self._select_all)
        self.btn_deselect.clicked.connect(self._deselect_all)
        btn_row.addWidget(self.btn_select)
        btn_row.addWidget(self.btn_deselect)
        btn_row.addStretch(1)
        root.addLayout(btn_row)

        _ok_cancel(root, self)

    def _sync_setting_col(self, item):
        """Keep the read-only 'Core Loss Setting' column mirroring col 0."""
        if item.column() != 0:
            return
        mirror = self.tbl.item(item.row(), 1)
        if mirror is not None:
            mirror.setCheckState(item.checkState())

    def _set_all(self, state):
        for r in range(self.tbl.rowCount()):
            it = self.tbl.item(r, 0)
            if it is not None:
                it.setCheckState(state)

    def _select_all(self):
        self._set_all(Qt.CheckState.Checked)

    def _deselect_all(self):
        self._set_all(Qt.CheckState.Unchecked)

    def values(self):
        """list[str] of CHECKED objects."""
        out = []
        for r in range(self.tbl.rowCount()):
            it = self.tbl.item(r, 0)
            if it is not None and it.checkState() == Qt.CheckState.Checked:
                out.append(it.text())
        return out
