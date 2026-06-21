"""Main window — faithful Ansys Electronics Desktop / Maxwell 2D shell:
ribbon + dual left trees (Project Manager + Model history) + Properties grid +
Message Manager. Stage-1 engine (geometry / materials / mesh) wired underneath.
"""
from __future__ import annotations

import time

from PyQt6.QtCore import Qt, QEvent, QSize
from PyQt6.QtGui import QAction, QColor, QShortcut, QKeySequence, QPixmap
from PyQt6.QtWidgets import (QMainWindow, QWidget, QDockWidget, QTreeWidget,
                             QTreeWidgetItem, QPlainTextEdit, QToolBar, QLabel,
                             QButtonGroup, QMessageBox, QColorDialog, QInputDialog,
                             QHBoxLayout, QVBoxLayout, QToolButton)

from ..model import (Project, Shape, generate, boolean_unite, boolean_subtract,
                     rotated, mirrored, duplicate_around_axis,
                     duplicate_along_line, apply_cmd)
from ..model.materials import Material
from .modeler_view import ModelerView
from .material_editor import MaterialEditor
from .properties_panel import PropertiesPanel
from .ribbon import RibbonBar
from .coordbar import CoordBar
from .dialogs import (CircleDialog, RectDialog, AroundAxisDialog,
                      AlongLineDialog, MirrorDialog, AttributesDialog,
                      PropertiesDialog, ProjectVariablesDialog, SegmentDialog)
from PyQt6.QtWidgets import QMenu, QInputDialog as _QInputDialog
from ..sample import build_motor

DESIGN_NODES = ["3D Components", "Model", "Boundaries", "Excitations",
                "Parameters", "Mesh", "Analysis", "Optimetrics", "Results",
                "Field Overlays"]

RESIZE_MARGIN = 6


class _DragBar(QWidget):
    """Custom title-bar area: drag moves the window, double-click maximises."""

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            wh = self.window().windowHandle()
            if wh is not None:
                wh.startSystemMove()
        super().mousePressEvent(e)

    def mouseDoubleClickEvent(self, e):
        win = self.window()
        win.showNormal() if win.isMaximized() else win.showMaximized()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setMouseTracking(True)
        self.project = Project(name="400W_10P12S_AMR")
        self.design.name = "BasicModel_RatedLoad"
        self.design.solver = "Transient"
        self._dark = True
        self._update_title()
        self.resize(1480, 900)

        self.view = ModelerView()
        self.setCentralWidget(self.view)
        self.view.shapeCreated.connect(self._on_shape_created)
        self.view.selectionChanged.connect(self._on_canvas_selection)
        self.view.coordMoved.connect(self._on_coord)
        self.view.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.view.customContextMenuRequested.connect(self._view_menu)
        self.view.promptChanged.connect(self._on_prompt)
        self.view.viewport().installEventFilter(self)

        self._build_menu()
        self._build_header()
        self._build_ribbon()
        self._build_trees_dock()
        self._build_props_dock()
        self._build_log_dock()

        self.status = self.statusBar()
        self.sel_lbl = QLabel("Nothing is selected")
        self.units_lbl = QLabel("Units: mm")
        self.coordbar = CoordBar()
        self.coordbar.pointSubmitted.connect(self._coord_submitted)
        self.status.addWidget(self.sel_lbl)
        self.status.addPermanentWidget(self.coordbar)
        self.status.addPermanentWidget(self.units_lbl)
        self.view.coordMoved.connect(self.coordbar.set_live)
        self.props.commandEdited.connect(self._on_command_edited)
        self.props.variableEdited.connect(self._on_variable_edited)

        self.props.set_materials(list(self.project.materials.keys()))
        self.props.show_variables(self.project.variables.rows())
        self._undo_stack = []
        self._redo_stack = []
        from PyQt6.QtWidgets import QApplication
        QApplication.instance().installEventFilter(self)   # frameless resize
        QShortcut(QKeySequence(Qt.Key.Key_Delete), self,
                  activated=self.do_delete)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self,
                  activated=lambda: self.set_tool("select"))
        QShortcut(QKeySequence.StandardKey.Undo, self, activated=self.undo)
        QShortcut(QKeySequence.StandardKey.Redo, self, activated=self.redo)
        QShortcut(QKeySequence("Ctrl+Y"), self, activated=self.redo)
        self.refresh_trees()
        self.log("LiteMaxwell 0.2 — ribbon shell (geometry + materials + mesh)")
        self.view.fit()
        # Project Manager small, Model history large (AEDT proportions)
        self.resizeDocks([self._dock_pm, self._dock_model], [200, 560],
                         Qt.Orientation.Vertical)

    # ----------------------------------------------------------- properties
    @property
    def design(self):
        return self.project.active

    def _update_title(self):
        d = self.design
        self.setWindowTitle(
            f"YJHWell  ·  Made By 여재현 — {self.project.name} - {d.name} "
            f"- 3D Modeler")

    # ----------------------------------------------------------------- menu
    def _build_menu(self):
        for name in ("File", "Edit", "View", "Project", "Draw", "Modeler",
                     "Maxwell 2D", "Tools", "Window", "Help"):
            m = self.menuBar().addMenu(name)
            if name == "Draw":
                for k, lbl in (("circle", "Circle"), ("rect", "Rectangle"),
                               ("polygon", "Polygon")):
                    a = QAction(lbl, self)
                    a.triggered.connect(lambda _, kk=k: self.set_tool(kk))
                    m.addAction(a)
            elif name == "Modeler":
                for lbl, fn in (("Cover Lines", self.do_cover_lines),
                                ("Unite", self.do_unite),
                                ("Subtract", self.do_subtract),
                                ("Duplicate Around Axis…", self.do_around_axis),
                                ("Mirror…", self.do_mirror),
                                ("Delete", self.do_delete)):
                    a = QAction(lbl, self); a.triggered.connect(fn); m.addAction(a)
            elif name == "View":
                a = QAction("Toggle Dark/Light theme", self)
                a.triggered.connect(self.toggle_theme); m.addAction(a)
            elif name == "Project":
                a = QAction("Project Variables…", self)
                a.triggered.connect(self.edit_variables); m.addAction(a)
            elif name == "Maxwell 2D":
                a = QAction("Generate Mesh", self)
                a.triggered.connect(self.do_mesh); m.addAction(a)

    # --------------------------------------------------------------- header
    def _build_header(self):
        """Claude-app-style top bar: icon buttons left, centred title, brand."""
        import os
        from .icons import icon as mk
        from PyQt6.QtWidgets import QMenu
        bar = QToolBar("Header"); bar.setMovable(False)
        bar.setObjectName("headerBar")
        host = _DragBar(); lay = QHBoxLayout(host)
        lay.setContentsMargins(22, 10, 8, 8); lay.setSpacing(3)

        def iconbtn(ic, tip, cb=None, menu=None, name="hdrIcon"):
            b = QToolButton(); b.setIcon(mk(ic)); b.setIconSize(QSize(22, 22))
            b.setObjectName(name); b.setToolTip(tip); b.setAutoRaise(True)
            b.setFixedSize(36, 32)
            if menu is not None:
                b.setMenu(menu)
                b.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
            if cb:
                b.clicked.connect(cb)
            return b

        # --- brand (SPG logo + name) on the LEFT ------------------------
        logo = QLabel()
        pm = QPixmap(os.path.join(os.path.dirname(__file__), "..", "resources",
                                  "spg_logo.png"))
        if not pm.isNull():
            logo.setPixmap(pm.scaledToHeight(
                48, Qt.TransformationMode.SmoothTransformation))
        lay.addWidget(logo)
        col = QVBoxLayout(); col.setSpacing(1); col.setContentsMargins(4, 2, 0, 0)
        nm = QLabel("YJHWell"); nm.setObjectName("appName")
        md = QLabel("Made By 여재현"); md.setObjectName("appMaker")
        col.addWidget(nm); col.addWidget(md)
        cw = QWidget(); cw.setLayout(col); lay.addWidget(cw)

        sep = QLabel(); sep.setObjectName("hdrSep"); sep.setFixedSize(1, 26)
        lay.addSpacing(8); lay.addWidget(sep); lay.addSpacing(4)

        # --- icon buttons ----------------------------------------------
        appmenu = QMenu(self)
        for act in self.menuBar().actions():
            if act.menu():
                appmenu.addMenu(act.menu())
        lay.addWidget(iconbtn("hamburger", "Menu", menu=appmenu))
        lay.addWidget(iconbtn("panel", "Toggle panels", self._toggle_panels))
        lay.addWidget(iconbtn("search", "Find object", self._find_object))
        lay.addWidget(iconbtn("back", "Undo", self.undo))
        lay.addWidget(iconbtn("fwd", "Redo", self.redo))

        lay.addStretch(1)
        self.hdr_title = QLabel(f"{self.project.name}  ›  {self.design.name}")
        self.hdr_title.setObjectName("hdrTitle")
        lay.addWidget(self.hdr_title)
        lay.addStretch(1)

        # --- window controls (frameless custom chrome) on the RIGHT -----
        bmin = iconbtn("win_min", "Minimize", self.showMinimized, name="winBtn")
        self.btn_max = iconbtn("win_max", "Maximize", self._toggle_max, name="winBtn")
        bclose = iconbtn("win_close", "Close", self.close, name="winClose")
        lay.addSpacing(6)
        for b in (bmin, self.btn_max, bclose):
            lay.addWidget(b)

        bar.addWidget(host)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, bar)
        self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)
        self.menuBar().setVisible(False)

    def _toggle_max(self):
        from .icons import icon as _icon
        if self.isMaximized():
            self.showNormal(); self.btn_max.setIcon(_icon("win_max"))
        else:
            self.showMaximized(); self.btn_max.setIcon(_icon("win_restore"))

    def _toggle_panels(self):
        vis = not self._dock_pm.isVisible()
        for d in (self._dock_pm, self._dock_model, self._dock_props):
            d.setVisible(vis)

    def _find_object(self):
        names = [s.name for s in self.design.shapes]
        if not names:
            self.log("Find: 형상이 없습니다."); return
        name, ok = _QInputDialog.getItem(self, "Find object", "Object:",
                                         names, 0, True)
        if ok and name:
            s = self.design.find(name)
            if s:
                self.view._scene.clearSelection()
                it = self.view.item_for(s)
                if it:
                    it.setSelected(True); self.view.fit_selected()

    # --------------------------------------------------------------- ribbon
    def _build_ribbon(self):
        self.ribbon = RibbonBar()
        self.tool_group = QButtonGroup(self); self.tool_group.setExclusive(True)

        # Desktop
        t = self.ribbon.add_tab("Desktop")
        g = t.add_group("Project")
        g.add_button("New", self._todo, icon="new")
        g.add_button("Open", self._todo, icon="open")
        g.add_button("Save", self._todo, icon="save")
        g = t.add_group("Insert Design")
        g.add_button("Maxwell 2D", self._todo, icon="motor")
        g = t.add_group("Appearance")
        g.add_button("Theme", self.toggle_theme, icon="theme")
        t.finish()

        # View
        t = self.ribbon.add_tab("View")
        g = t.add_group("Navigate")
        g.add_button("Fit All", self.view.fit, icon="fit")
        g.add_button("Fit Selected", self.view.fit_selected, icon="fit")
        g = t.add_group("Grid")
        self.btn_snap = g.add_button("Snap", self.toggle_snap, checkable=True,
                                     icon="snap")
        g = t.add_group("Appearance")
        g.add_button("Theme", self.toggle_theme, icon="theme")
        t.finish()

        # Draw  (primary)
        t = self.ribbon.add_tab("Draw")
        g = t.add_group("Clipboard")
        g.add_button("Save", self._todo, icon="save")
        g.add_button("Delete", self.do_delete, icon="delete")
        g = t.add_group("Select")
        self.tool_buttons = {}
        self.tool_buttons["select"] = g.add_button(
            "Select", lambda: self.set_tool("select"),
            checkable=True, group=self.tool_group, icon="select")
        self.tool_buttons["select"].setChecked(True)
        g = t.add_group("View")
        g.add_button("Fit All", self.view.fit, icon="fit")
        g.add_button("Fit Sel", self.view.fit_selected, icon="fit")
        g = t.add_group("Draw")
        self.tool_buttons["circle"] = g.add_button(
            "Circle", lambda: self.set_tool("circle"),
            checkable=True, group=self.tool_group, icon="circle")
        self.tool_buttons["rect"] = g.add_button(
            "Rectangle", lambda: self.set_tool("rect"),
            checkable=True, group=self.tool_group, icon="rect")
        self.tool_buttons["polygon"] = g.add_button(
            "Polyline", lambda: self.set_tool("polygon"),
            checkable=True, group=self.tool_group, icon="polyline")
        self.tool_buttons["spline"] = g.add_button(
            "Spline", lambda: self.set_tool("spline"),
            checkable=True, group=self.tool_group, icon="spline")
        self.tool_buttons["arc"] = g.add_button(
            "CenterPointArc", lambda: self.set_tool("arc"),
            checkable=True, group=self.tool_group, icon="arc")
        self.btn_osnap = g.add_button("Osnap", self.toggle_osnap,
                                      checkable=True, icon="osnap")
        self.btn_osnap.setChecked(True)
        g.add_button("Circle", self.draw_circle_dims, icon="circledim")
        g.add_button("Rect", self.draw_rect_dims, icon="rectdim")
        g = t.add_group("Edit")
        g.add_button("Around Axis", self.do_around_axis, icon="around")
        g.add_button("Along Line", self.do_along_line, icon="along")
        g.add_button("Mirror", self.do_mirror, icon="mirror")
        g.add_button("Fillet", self.do_fillet, icon="around")
        g = t.add_group("Boolean")
        g.add_button("Unite", self.do_unite, icon="unite")
        g.add_button("Subtract", self.do_subtract, icon="subtract")
        g = t.add_group("Material")
        g.add_button("Assign", self.assign_material_dialog, icon="material")
        g.add_button("Edit", self.edit_selected_material, icon="editmat")
        g.add_button("New", self.new_material, icon="newmat")
        g = t.add_group("Coordinates")
        g.add_button("Relative CS", self.relative_cs_dialog, icon="around")
        g.add_button("Face CS", self.do_face_cs, icon="around")
        g.add_button("Set Global", self.set_global_cs, icon="fit")
        g = t.add_group("Select (O/E/V/F)")
        g.add_button("Object", lambda: self.view.set_select_mode("object"), icon="select")
        g.add_button("Edge", lambda: self.view.set_select_mode("edge"), icon="select")
        g.add_button("Vertex", lambda: self.view.set_select_mode("vertex"), icon="select")
        g.add_button("Face", lambda: self.view.set_select_mode("face"), icon="select")
        t.finish()

        # Model
        t = self.ribbon.add_tab("Model")
        g = t.add_group("Insert")
        g.add_button("Sample Motor", self.insert_sample, icon="motor")
        g = t.add_group("Boolean")
        g.add_button("Unite", self.do_unite, icon="unite")
        g.add_button("Subtract", self.do_subtract, icon="subtract")
        g = t.add_group("Duplicate")
        g.add_button("Around Axis", self.do_around_axis, icon="around")
        g.add_button("Along Line", self.do_along_line, icon="along")
        t.finish()

        # Simulation
        t = self.ribbon.add_tab("Simulation")
        g = t.add_group("Mesh")
        g.add_button("Generate", self.do_mesh, icon="mesh")
        self.btn_showmesh = g.add_button("Show Mesh", self.toggle_mesh,
                                         checkable=True, icon="showmesh")
        g = t.add_group("Analysis")
        g.add_button("Solve Setup", self.edit_solve_setup, icon="new")
        g.add_button("Analyze", self.do_analyze, icon="analyze")
        self.btn_nl = g.add_button("Nonlinear (BH)", lambda: None,
                                   checkable=True, icon="mesh")
        t.finish()

        # Results / Automation (placeholders for later stages)
        t = self.ribbon.add_tab("Results")
        g = t.add_group("Create Report")
        g.add_button("Torque Plot", self.do_torque_plot, icon="report")
        g.add_button("Back-EMF", self.do_backemf_plot, icon="report")
        g.add_button("Load Torque", self.do_load_torque_plot, icon="report")
        g.add_button("Transient EMF", self.do_transient_emf, icon="report")
        g.add_button("Core Loss", self.do_core_loss, icon="report")
        self.btn_field = g.add_button("Field Overlay", self.toggle_field,
                                      checkable=True, icon="mesh")
        g = t.add_group("Optimetrics")
        g.add_button("Param Sweep", self.do_optimetrics, icon="report")
        t.finish()
        t = self.ribbon.add_tab("Automation")
        g = t.add_group("Scripting")
        g.add_button("Record", self._todo, icon="new")
        t.finish()

        self.ribbon.setCurrentIndex(2)  # Draw
        bar = QToolBar("Ribbon"); bar.setMovable(False)
        bar.setAllowedAreas(Qt.ToolBarArea.TopToolBarArea)
        bar.addWidget(self.ribbon)
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, bar)

    # ----------------------------------------------------------------- docks
    def _build_trees_dock(self):
        self.proj_tree = QTreeWidget(); self.proj_tree.setHeaderHidden(True)
        self.proj_tree.setMinimumWidth(240)
        self.proj_tree.itemClicked.connect(self._on_tree_click)
        self.proj_tree.itemDoubleClicked.connect(self._on_tree_double)
        self.proj_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.proj_tree.customContextMenuRequested.connect(self._proj_menu)
        d1 = QDockWidget("Project Manager", self); d1.setWidget(self.proj_tree)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, d1)

        self.model_tree = QTreeWidget(); self.model_tree.setHeaderHidden(True)
        self.model_tree.itemClicked.connect(self._on_tree_click)
        self.model_tree.itemDoubleClicked.connect(self._on_tree_double)
        self.model_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.model_tree.customContextMenuRequested.connect(self._model_menu)
        d2 = QDockWidget("Model", self); d2.setWidget(self.model_tree)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, d2)
        self.splitDockWidget(d1, d2, Qt.Orientation.Vertical)
        self._dock_pm, self._dock_model = d1, d2

    def _build_props_dock(self):
        self.props = PropertiesPanel()
        self.props.nameChanged.connect(self._rename)
        self.props.materialChanged.connect(self._assign_mat)
        self.props.colorRequested.connect(self._pick_color)
        d = QDockWidget("Properties", self); d.setWidget(self.props)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, d)
        self._dock_props = d

    def _build_log_dock(self):
        self.logbox = QPlainTextEdit(); self.logbox.setReadOnly(True)
        self.logbox.setMaximumBlockCount(500)
        d = QDockWidget("Progress / Message Manager", self)
        d.setWidget(self.logbox)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, d)

    # --------------------------------------------------------------- helpers
    def log(self, msg):
        self.logbox.appendPlainText(f"[{time.strftime('%H:%M:%S')}] {msg}")

    def _todo(self):
        self.log("이 기능은 다음 단계(솔버/결과)에서 구현 예정입니다.")

    def _active_tool_name(self):
        if self.view.tool == "polygon":
            return "arc" if self.view._arc_mode else "polygon"
        return self.view.tool

    def _check_tool(self, name):
        for k, b in self.tool_buttons.items():
            b.setChecked(k == name)

    def set_tool(self, tool):
        # clicking the already-active draw tool returns to Select (toggle off)
        if tool != "select" and tool == self._active_tool_name():
            tool = "select"
        if tool == "arc":               # CenterPointArc = polyline, arc default
            self.view.set_tool("polygon"); self.view.set_arc_mode(True)
        elif tool == "polygon":         # Polyline = line default
            self.view.set_tool("polygon"); self.view.set_arc_mode(False)
        else:
            self.view.set_tool(tool)
            if tool == "select":
                self.view.set_arc_mode(False)
        self._check_tool(tool)

    _CMD_LABEL = {"CreateCircle": "CreateCircle", "CreateRectangle": "CreateRectangle",
                  "CreatePolyline": "CreatePolyline", "CreateSpline": "CreateSpline",
                  "Static": "Imported", "Subtract": "Subtract", "Unite": "Unite",
                  "Intersect": "Intersect"}

    def _build_history_nodes(self, parent_item, shape):
        """Build the construction-history tree under a shape node, so booleans
        show their operands' CreateCircle/… nodes (editable)."""
        c = shape.cmd
        if c and c.get("kind") in ("Subtract", "Unite", "Intersect"):
            ops = c["operands"]
            # base (first clicked) stays at top; the rest go INSIDE the op node
            self._add_cmd_node(parent_item, shape, ops[0])
            opn = QTreeWidgetItem([self._CMD_LABEL[c["kind"]]])
            for op_cmd in ops[1:]:
                self._add_cmd_node(opn, shape, op_cmd)
            parent_item.addChild(opn)
            return
        # single create op (with polyline segment children)
        op = QTreeWidgetItem([self._op_name(shape)])
        op.setData(0, Qt.ItemDataRole.UserRole, ("cmd", shape))
        if c and c.get("kind") == "CreatePolyline" and c.get("segments"):
            for i, seg in enumerate(c["segments"]):
                label = "CreateLine" if seg["type"] == "line" else "CreateAngularArc"
                segn = QTreeWidgetItem([label])
                segn.setData(0, Qt.ItemDataRole.UserRole, ("seg", (shape, i)))
                op.addChild(segn)
        parent_item.addChild(op)

    def _add_cmd_node(self, parent_item, root_shape, op_cmd):
        """A node for one boolean operand; editing it re-applies the boolean."""
        kind = op_cmd.get("kind", "Create")
        label = f"{self._CMD_LABEL.get(kind, kind)}"
        nm = op_cmd.get("name")
        node = QTreeWidgetItem([f"{label}" + (f"  [{nm}]" if nm else "")])
        if kind in ("Subtract", "Unite", "Intersect"):
            for sub in op_cmd["operands"]:
                self._add_cmd_node(node, root_shape, sub)
            node.addChild(QTreeWidgetItem([self._CMD_LABEL[kind]]))
        else:
            node.setData(0, Qt.ItemDataRole.UserRole, ("opcmd", (root_shape, op_cmd)))
        parent_item.addChild(node)

    def _op_name(self, shape):
        if shape.cmd and shape.cmd.get("kind"):
            return shape.cmd["kind"]
        n = shape.name.lower()
        if n.startswith("circle"):
            return "CreateCircle"
        if n.startswith("rect"):
            return "CreateRectangle"
        return "CreatePolyline"

    def refresh_trees(self):
        # Project Manager
        self.proj_tree.clear()
        root = QTreeWidgetItem([self.project.name + "*"])
        root.setData(0, Qt.ItemDataRole.UserRole, ("project", None))
        self.proj_tree.addTopLevelItem(root)
        d = QTreeWidgetItem([f"{self.design.name} ({self.design.solver}, XY)*"])
        root.addChild(d)
        des = self.design
        for node in DESIGN_NODES:
            it = QTreeWidgetItem([node]); d.addChild(it)
            if node == "Model" and des.motion:
                ms = QTreeWidgetItem(["MotionSetup1"]); it.addChild(ms)
                mv = QTreeWidgetItem([des.motion.get("name", "Moving1")])
                mv.setData(0, Qt.ItemDataRole.UserRole, ("motion", None))
                ms.addChild(mv)
            elif node == "Boundaries":
                for b in des.boundaries:
                    bi = QTreeWidgetItem([b["name"]])
                    bi.setData(0, Qt.ItemDataRole.UserRole, ("bnd", b))
                    it.addChild(bi)
            elif node == "Excitations":
                for ex in des.excitations:
                    ei = QTreeWidgetItem([ex["name"]])
                    ei.setData(0, Qt.ItemDataRole.UserRole, ("exc", ex))
                    it.addChild(ei)
            elif node == "Mesh":
                for mo in des.mesh_ops:
                    it.addChild(QTreeWidgetItem([mo["name"]]))
                if des.mesh is not None:
                    it.addChild(QTreeWidgetItem(
                        [f"Mesh ({des.mesh.n_tris} elements)"]))
            elif node == "Analysis" and des.setup:
                si = QTreeWidgetItem([des.setup["name"]])
                si.setData(0, Qt.ItemDataRole.UserRole, ("setup", None))
                it.addChild(si)
            elif node == "Field Overlays" and des.field is not None:
                b = QTreeWidgetItem([f"B  (Mag_B, max {des.field.bmax:.3f} T)"])
                it.addChild(b)
        defs = QTreeWidgetItem(["Definitions"]); root.addChild(defs)
        for name in self.project.materials:
            mi = QTreeWidgetItem([name])
            mi.setData(0, Qt.ItemDataRole.UserRole, ("mat", self.project.materials[name]))
            defs.addChild(mi)
        self.proj_tree.expandAll()

        # Model history (grouped by material)
        self.model_tree.clear()
        model = QTreeWidgetItem(["Model"]); self.model_tree.addTopLevelItem(model)
        sheets = QTreeWidgetItem(["Sheets"]); model.addChild(sheets)
        by_mat: dict[str, list] = {}
        for s in self.design.shapes:
            by_mat.setdefault(s.material, []).append(s)
        for mat, shapes in by_mat.items():
            mnode = QTreeWidgetItem([mat]); sheets.addChild(mnode)
            for s in shapes:
                sn = QTreeWidgetItem([s.name])
                sn.setData(0, Qt.ItemDataRole.UserRole, ("shape", s))
                sn.setForeground(0, QColor(s.color))
                self._build_history_nodes(sn, s)
                if s.is_closed:
                    sn.addChild(QTreeWidgetItem(["CoverLines"]))
                mnode.addChild(sn)
        cs_node = QTreeWidgetItem(["Coordinate Systems"])
        cs_node.addChild(QTreeWidgetItem(["Global"]))
        for cs in self.design.coord_systems:
            cs_node.addChild(QTreeWidgetItem(
                [f"{cs['name']}  (o={cs['ox']:g},{cs['oy']:g}  rot={cs['rot']:g}°)"]))
        self.model_tree.addTopLevelItem(cs_node)
        for extra in ("Planes", "Lists"):
            self.model_tree.addTopLevelItem(QTreeWidgetItem([extra]))
        self.model_tree.expandToDepth(2)
        self.props.set_materials(list(self.project.materials.keys()))

    def _selected(self):
        sel = self.view.selected_shapes()
        return sel[0] if sel else None

    # --------------------------------------------------------------- events
    # --------------------------------------------------------------- undo/redo
    def _snapshot(self):
        import copy
        self._undo_stack.append(copy.deepcopy(self.design.shapes))
        if len(self._undo_stack) > 80:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def _restore(self, shapes):
        self.design.shapes = shapes
        self.view.reload(self.design.shapes)
        self.refresh_trees()
        self._on_canvas_selection()

    def undo(self):
        if not self._undo_stack:
            self.log("Undo: 더 되돌릴 작업이 없습니다."); return
        import copy
        self._redo_stack.append(copy.deepcopy(self.design.shapes))
        self._restore(self._undo_stack.pop())
        self.log("Undo")

    def redo(self):
        if not self._redo_stack:
            self.log("Redo: 다시 실행할 작업이 없습니다."); return
        import copy
        self._undo_stack.append(copy.deepcopy(self.design.shapes))
        self._restore(self._redo_stack.pop())
        self.log("Redo")

    def _on_shape_created(self, shape):
        self._snapshot()
        self.design.add(shape)
        self.log(f"Created {shape.name}  (area {shape.area:.2f} mm²)")
        self.set_tool("select")          # one-shot: return to Select after drawing
        self.refresh_trees()
        self.view._scene.clearSelection()
        it = self.view.item_for(shape)
        if it:
            it.setSelected(True)        # show its Command props immediately

    def _on_canvas_selection(self):
        sel = self.view.selected_shapes()
        n = len(sel)
        self.sel_lbl.setText("Nothing is selected" if n == 0
                             else f"{n} object{'s' if n > 1 else ''} selected")
        s = sel[0] if sel else None
        self.props.show_shape(s)

    def _on_coord(self, x, y):
        # readout in the active CS (Maxwell shows coords relative to the WCS)
        rx, ry = self.view.from_global(x, y)
        cs = "" if self.view.wcs.is_global else f"  [{self.view.wcs.name}]"
        self.units_lbl.setText(f"X {rx:.2f}  Y {ry:.2f}   |  Units: mm{cs}")

    def _on_prompt(self, msg):
        self.sel_lbl.setText(msg)
        lp = self.view.last_point()
        bx, by = self.view.from_global(lp.x(), lp.y())   # base in WCS frame
        self.coordbar.set_base(bx, by)

    def _coord_submitted(self, x, y):
        # the coordbar works in the active CS frame -> map to global to place it
        gx, gy = self.view.to_global(x, y)
        self.view.submit_point(gx, gy)
        lp = self.view.last_point()
        bx, by = self.view.from_global(lp.x(), lp.y())
        self.coordbar.set_base(bx, by)

    def _on_command_edited(self, field, value):
        s = self._selected()
        if not s or not s.cmd:
            return
        ev = self._evaluate_var
        try:
            if field == "Radius":
                s.cmd["r"] = ev(value); s.cmd["r_expr"] = value
            elif field == "Number of Segments":
                s.cmd["segs"] = int(float(value))
            elif field == "Center Position":
                parts = [p for p in value.replace(",", " ").split() if p]
                s.cmd["cx"], s.cmd["cy"] = ev(parts[0]), ev(parts[1])
                s.cmd["center_expr"] = value
            elif field == "Position":
                parts = [float(p) for p in value.replace(",", " ").split()]
                w = s.cmd["x1"] - s.cmd["x0"]; h = s.cmd["y1"] - s.cmd["y0"]
                s.cmd["x0"], s.cmd["y0"] = parts[0], parts[1]
                s.cmd["x1"], s.cmd["y1"] = parts[0] + w, parts[1] + h
            elif field == "X Size":
                s.cmd["x1"] = s.cmd["x0"] + float(value)
            elif field == "Y Size":
                s.cmd["y1"] = s.cmd["y0"] + float(value)
        except (ValueError, IndexError, KeyError):
            self.log(f"치수 입력 형식 오류: {field}={value}")
            return
        apply_cmd(s)
        it = self.view.item_for(s)
        if it:
            it.rebuild()
        self.log(f"{s.name}: {field} = {value}")
        self.refresh_trees()

    def _on_tree_click(self, item, _col):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if data and data[0] == "shape":
            self.view._scene.clearSelection()
            it = self.view.item_for(data[1])
            if it:
                it.setSelected(True)

    def _on_tree_double(self, item, _col):
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        if data[0] == "mat":
            self.edit_material(data[1])
        elif data[0] == "opcmd":
            self._edit_operand(*data[1])
        elif data[0] == "seg":
            self._edit_segment(*data[1])
        elif data[0] == "cmd":
            self._open_properties(data[1], "Command")
        elif data[0] == "shape":
            self._open_properties(data[1], "Attribute")

    _VAR_FUNCS = {"sin", "cos", "tan", "asin", "acos", "atan", "atan2", "sqrt",
                  "abs", "pi", "PI", "radians", "degrees", "min", "max", "pow",
                  "exp", "mm", "deg", "rpm", "A"}

    def _reeval_cmd(self, c):
        """Re-evaluate expression-based dimensions in a cmd (recurses booleans)."""
        if not c:
            return
        ev = self.project.variables.evaluate
        if c.get("kind") in ("Subtract", "Unite", "Intersect"):
            for o in c["operands"]:
                self._reeval_cmd(o)
            return
        import re
        try:
            if "r_expr" in c:
                c["r"] = ev(c["r_expr"])
            if "center_expr" in c:
                p = [x for x in re.split(r"[ ,]+", c["center_expr"].strip()) if x]
                c["cx"], c["cy"] = ev(p[0]), ev(p[1])
        except ValueError:
            pass

    def _on_variable_edited(self, name, value):
        from ..model import apply_cmd
        self._snapshot()
        self.project.variables.set(name, value or "0")
        # propagate to any geometry defined by an expression using this variable
        for s in self.design.shapes:
            self._reeval_cmd(s.cmd)
            apply_cmd(s)
            it = self.view.item_for(s)
            if it:
                it.rebuild()
        self.props.show_variables(self.project.variables.rows())
        self.refresh_trees()
        self.log(f"Variable '{name}' = {value} (dependent geometry updated)")

    def _evaluate_var(self, expr):
        """Evaluate a dimension expression; prompt to define unknown variables
        (Maxwell's 'Add Variable' behaviour), then return the value."""
        import re
        for nm in set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", str(expr))):
            if nm in self._VAR_FUNCS or nm in self.project.variables.exprs:
                continue
            val, ok = _QInputDialog.getText(
                self, "Add Variable", f"변수 '{nm}' 값/식 정의:", text="0")
            if ok:
                self.project.variables.set(nm, val or "0")
                self.props.show_variables(self.project.variables.rows())
        v = self.project.variables.evaluate(expr)
        self.props.show_variables(self.project.variables.rows())
        return v

    def _edit_operand(self, root_shape, op_cmd):
        """Edit a boolean operand's dimensions, then re-evaluate the boolean."""
        from ..model import apply_cmd
        from .dialogs import PropertiesDialog
        kind = op_cmd.get("kind")
        # wrap the operand cmd in a temp shape so the existing editors mutate it
        tmp = Shape(op_cmd.get("name", "op"), Shape.circle("t", 0, 0, 1).geom)
        tmp.cmd = op_cmd
        if kind == "CreatePolyline" and op_cmd.get("segments"):
            segs = op_cmd["segments"]
            items = [f"{i + 1}: {'CreateLine' if s['type'] == 'line' else 'CreateAngularArc'}"
                     for i, s in enumerate(segs)]
            choice, ok = _QInputDialog.getItem(self, "Edit Segment", "Segment:",
                                               items, 0, False)
            if not ok:
                return
            from .dialogs import SegmentDialog
            self._snapshot()
            dlg = SegmentDialog(tmp, int(choice.split(":")[0]) - 1,
                                evaluate=self._evaluate_var, parent=self)
            if not dlg.exec():
                self._undo_stack.pop(); return
        else:
            dlg = PropertiesDialog(tmp, self.project.materials.keys(),
                                   f"{self.project.name} - {self.design.name}",
                                   tab="Command",
                                   evaluate=self._evaluate_var, parent=self)
            if not (dlg.exec() and dlg._applied):
                return
            self._snapshot()
        apply_cmd(root_shape)
        it = self.view.item_for(root_shape)
        if it:
            it.rebuild()
        self.log(f"{root_shape.name}: '{op_cmd.get('name')}' 치수 수정 → boolean 재계산")
        self.refresh_trees(); self._on_canvas_selection()

    def _edit_segment(self, shape, index):
        self._snapshot()

        def live():
            from ..model import apply_cmd
            apply_cmd(shape)
            it = self.view.item_for(shape)
            if it:
                it.rebuild()

        dlg = SegmentDialog(shape, index, evaluate=self._evaluate_var,
                            on_apply=live, parent=self)
        if dlg.exec():
            live()
            seg = shape.cmd["segments"][index]
            self.log(f"{shape.name}: segment {index + 1} ({seg['type']}) edited")
            self.refresh_trees(); self._on_canvas_selection()
        else:
            self._undo_stack.pop()           # cancelled -> discard snapshot

    def _open_properties(self, shape, tab):
        # polyline dimension editing (Command/canvas only) -> segment picker.
        # The shape node (Attribute, e.g. rename) falls through to the dialog.
        if (tab == "Command" and shape.cmd
                and shape.cmd.get("kind") == "CreatePolyline"
                and shape.cmd.get("segments")):
            segs = shape.cmd["segments"]
            if len(segs) == 1:
                self._edit_segment(shape, 0); return
            items = [f"{i + 1}: {'CreateLine' if s['type'] == 'line' else 'CreateAngularArc'}"
                     for i, s in enumerate(segs)]
            choice, ok = _QInputDialog.getItem(
                self, f"{shape.name} — Edit Segment", "Segment:", items, 0, False)
            if ok and choice:
                self._edit_segment(shape, int(choice.split(":")[0]) - 1)
            return
        title = f"{self.project.name} - {self.design.name}"

        def live():
            from ..model import apply_cmd
            apply_cmd(shape)
            it = self.view.item_for(shape)
            if it:
                it.rebuild()

        dlg = PropertiesDialog(shape, self.project.materials.keys(), title,
                               tab=tab, evaluate=self._evaluate_var,
                               on_apply=live, parent=self)
        if dlg.exec() and dlg._applied:
            mat = self.project.materials.get(shape.material)
            if mat:
                shape.color = mat.color
            it = self.view.item_for(shape)
            if it:
                it.rebuild()
            self.log(f"{shape.name}: properties applied "
                     f"({shape.cmd.get('kind') if shape.cmd else ''})")
            self.refresh_trees(); self._on_canvas_selection()

    # --------------------------------------------------------- interaction
    def eventFilter(self, obj, event):
        et = event.type()
        # frameless-window edge resize (works over any child via app filter)
        if et in (QEvent.Type.MouseMove, QEvent.Type.MouseButtonPress) and \
                not self.isMaximized() and self.isActiveWindow():
            try:
                gp = event.globalPosition().toPoint()
            except AttributeError:
                gp = None
            if gp is not None:
                edges = self._edge_at(gp)
                if et == QEvent.Type.MouseMove and \
                        event.buttons() == Qt.MouseButton.NoButton:
                    self._apply_resize_cursor(edges)
                elif (et == QEvent.Type.MouseButtonPress and edges
                      and event.button() == Qt.MouseButton.LeftButton):
                    wh = self.windowHandle()
                    if wh is not None:
                        wh.startSystemResize(edges)
                        return True
        if (obj is self.view.viewport()
                and et == QEvent.Type.MouseButtonDblClick
                and self.view.tool == "select"):
            it = self.view.itemAt(event.position().toPoint())
            from .modeler_view import ShapeItem
            while it is not None and not isinstance(it, ShapeItem):
                it = it.parentItem()
            if it is not None:
                self._open_properties(it.shape, "Command")
                return True
        return super().eventFilter(obj, event)

    def _edge_at(self, gp):
        r = self.frameGeometry()
        m = RESIZE_MARGIN
        x, y = gp.x(), gp.y()
        if not (r.left() - 1 <= x <= r.right() + 1
                and r.top() - 1 <= y <= r.bottom() + 1):
            return Qt.Edge(0)
        e = Qt.Edge(0)
        if x <= r.left() + m:
            e |= Qt.Edge.LeftEdge
        elif x >= r.right() - m:
            e |= Qt.Edge.RightEdge
        if y <= r.top() + m:
            e |= Qt.Edge.TopEdge
        elif y >= r.bottom() - m:
            e |= Qt.Edge.BottomEdge
        return e

    def _apply_resize_cursor(self, edges):
        from PyQt6.QtCore import Qt as _Qt
        L, R = _Qt.Edge.LeftEdge, _Qt.Edge.RightEdge
        T, B = _Qt.Edge.TopEdge, _Qt.Edge.BottomEdge
        if (edges & L and edges & T) or (edges & R and edges & B):
            self.setCursor(_Qt.CursorShape.SizeFDiagCursor)
        elif (edges & R and edges & T) or (edges & L and edges & B):
            self.setCursor(_Qt.CursorShape.SizeBDiagCursor)
        elif edges & (L | R):
            self.setCursor(_Qt.CursorShape.SizeHorCursor)
        elif edges & (T | B):
            self.setCursor(_Qt.CursorShape.SizeVerCursor)
        else:
            self.unsetCursor()

    def _edit_attributes(self, shape):
        dlg = AttributesDialog(shape, self.project.materials.keys(), self)
        if dlg.exec():
            name, mat, color = dlg.values()
            if name:
                shape.name = name
            shape.material = mat
            shape.color = color
            it = self.view.item_for(shape)
            if it:
                it.rebuild()
            self.log(f"Edited {shape.name} (material={mat})")
            self.refresh_trees(); self._on_canvas_selection()

    def _view_menu(self, pos):
        gp = self.view.viewport().mapToGlobal(pos)
        # while drawing a polyline/spline -> Done / segment-type / Undo menu
        if self.view.tool in ("polygon", "spline") and self.view._poly_pts:
            self._polyline_menu(gp); return
        if self.view.tool != "select":
            return
        sel = self.view.selected_shapes()
        m = QMenu(self)
        if sel:
            if any(not s.is_closed for s in sel):
                m.addAction("Cover Lines", self.do_cover_lines)
            m.addAction("Assign Material…", self.assign_material_dialog)
            ex = m.addMenu("Assign Excitation")
            ex.addAction("Current…", self.assign_current)
            bn = m.addMenu("Assign Boundary")
            bn.addAction("Vector Potential…", self.assign_vector_potential)
            m.addAction("Assign Band (Motion)…", self.assign_band)
            mo = m.addMenu("Assign Mesh Operation")
            mo.addAction("Length Based…", self.assign_mesh_op)
            m.addAction("Properties…", lambda: self._open_properties(sel[0], "Command"))
            m.addSeparator()
            m.addAction("Duplicate Around Axis…", self.do_around_axis)
            m.addAction("Mirror…", self.do_mirror)
            m.addAction("Unite", self.do_unite)
            m.addAction("Subtract", self.do_subtract)
            m.addAction("Delete", self.do_delete)
            m.addSeparator()
        m.addAction("Fit All", self.view.fit)
        m.addAction("Generate Mesh", self.do_mesh)
        m.addAction("Plot Mesh", self.toggle_mesh)
        m.exec(self.view.viewport().mapToGlobal(pos))

    def _polyline_menu(self, gp):
        m = QMenu(self)
        m.addAction("Escape Draw Mode\tESC", lambda: self.set_tool("select"))
        m.addAction("Done", lambda: self.view.finish_current(closed=False))
        m.addAction("Close Polyline", lambda: self.view.finish_current(closed=True))
        m.addAction("Undo Previous Segment", self.view.undo_segment)
        if self.view.tool == "polygon":
            m.addSeparator()
            edge = m.addMenu("Set Edge Type")
            cur = self.view._edge_type
            for label, key in (("Straight", "straight"), ("Spline", "spline"),
                               ("3 Point Arc", "3pa"),
                               ("Center Point Arc", "cpa")):
                a = edge.addAction(label); a.setCheckable(True)
                a.setChecked(cur == key)
                a.triggered.connect(lambda _=False, k=key: self._set_edge_type(k))
        m.exec(gp)

    def _set_edge_type(self, key):
        if key == "spline":
            self.log("Spline edge: Spline 도구를 사용하세요(추후 폴리라인 내 지원).")
            return
        self.view.set_edge_type(key)
        self._check_tool("arc" if key == "cpa" else "polygon")

    def _model_menu(self, pos):
        item = self.model_tree.itemAt(pos)
        data = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        m = QMenu(self)
        if data and data[0] == "shape":
            sh = data[1]
            self._on_tree_click(item, 0)
            m.addAction("Assign Material…", self.assign_material_dialog)
            m.addAction("Properties…", lambda: self._open_properties(sh, "Command"))
            m.addAction("Delete", self.do_delete)
        else:
            m.addAction("Insert Sample Motor", self.insert_sample)
            m.addAction("Generate Mesh", self.do_mesh)
        m.exec(self.model_tree.viewport().mapToGlobal(pos))

    def _proj_menu(self, pos):
        item = self.proj_tree.itemAt(pos)
        data = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        m = QMenu(self)
        m.addAction("Rename Project…", self.rename_project)
        if data and data[0] == "mat":
            mat = data[1]
            m.addAction("View / Edit Material…", lambda: self.edit_material(mat))
        m.addAction("New Material…", self.new_material)
        m.exec(self.proj_tree.viewport().mapToGlobal(pos))

    def rename_project(self):
        name, ok = _QInputDialog.getText(self, "Rename Project", "Project name:",
                                         text=self.project.name)
        if ok and name.strip():
            self.project.name = name.strip()
            self._update_title()
            if hasattr(self, "hdr_title"):
                self.hdr_title.setText(f"{self.project.name}  ›  {self.design.name}")
            self.refresh_trees()
            self.log(f"Project renamed → {self.project.name}")

    def edit_variables(self):
        dlg = ProjectVariablesDialog(self.project.variables, self)
        if dlg.exec():
            dlg.apply_to(self.project.variables)
        self.props.show_variables(self.project.variables.rows())
        self.log(f"Project variables: {len(self.project.variables.exprs)} defined")

    def assign_material_dialog(self):
        sel = self.view.selected_shapes()
        if not sel:
            self.log("Assign Material: 객체 선택 필요"); return
        from .select_definition import SelectDefinitionDialog
        dlg = SelectDefinitionDialog(self.project, self)
        if not dlg.exec():
            return
        name = dlg.selected_name()
        if not name:
            return
        for s in sel:
            s.material = name
            mat = self.project.materials.get(name)
            if mat:
                s.color = mat.color
            it = self.view.item_for(s)
            if it:
                it.rebuild()
        self.props.set_materials(list(self.project.materials.keys()))
        self.log(f"Assigned '{name}' to {len(sel)} object(s)")
        self.refresh_trees(); self._on_canvas_selection()

    # ----------------------------------------------------------- prop edits
    def _rename(self, name):
        s = self._selected()
        if s and name.strip():
            s.name = name.strip(); self.refresh_trees()

    def _assign_mat(self, name):
        s = self._selected()
        if s and name:
            s.material = name
            mat = self.project.materials.get(name)
            if mat:
                s.color = mat.color
            it = self.view.item_for(s)
            if it:
                it.rebuild()
            self.log(f"Assigned material '{name}' to {s.name}")
            self.refresh_trees()

    def _pick_color(self):
        s = self._selected()
        if not s:
            return
        c = QColorDialog.getColor(QColor(s.color), self, "Object colour")
        if c.isValid():
            s.color = c.name()
            it = self.view.item_for(s)
            if it:
                it.rebuild()
            self.refresh_trees(); self._on_canvas_selection()

    # ------------------------------------------------------------- actions
    def do_unite(self):
        sel = self.view.selected_shapes()
        if len(sel) < 2:
            self.log("Unite: 2개 이상 선택 필요"); return
        self._snapshot()
        new = boolean_unite(sel, sel[0].name, material=sel[0].material,
                            color=sel[0].color)
        for s in sel:
            self.design.remove(s)
        self.design.add(new); self.view.reload(self.design.shapes)
        self.log(f"United {len(sel)} → {new.name}"); self.refresh_trees()

    def do_subtract(self):
        sel = self.view.selected_shapes()
        if len(sel) < 2:
            self.log("Subtract: base + tool(들) 선택 필요"); return
        self._snapshot()
        new = boolean_subtract(sel[0], sel[1:], sel[0].name)
        for s in sel:
            self.design.remove(s)
        self.design.add(new); self.view.reload(self.design.shapes)
        self.log(f"Subtracted → {new.name}"); self.refresh_trees()

    # ----------------------------------------------------------- v2 setup
    def assign_current(self):
        from .setup_dialogs import CurrentExcitationDialog
        sel = self.view.selected_shapes()
        if not sel:
            self.log("Assign Excitation: 객체 선택 필요"); return
        n = len(self.design.excitations) + 1
        dlg = CurrentExcitationDialog(f"Current_{n}", self)
        if dlg.exec():
            d = dlg.values(); d["shapes"] = [s.name for s in sel]
            self.design.excitations.append(d)
            self.log(f"Excitation '{d['name']}' = {d['value']} A → {len(sel)} obj")
            self.refresh_trees()

    def assign_vector_potential(self):
        from .setup_dialogs import VectorPotentialDialog
        pk = self.view.picked
        edge = pk if (pk and pk.get("mode") == "edge") else None
        sel = self.view.selected_shapes()
        if not sel and not edge:
            self.log("Assign Boundary: E키로 모서리 선택(또는 객체 선택) 필요"); return
        n = len(self.design.boundaries) + 1
        dlg = VectorPotentialDialog(f"VectorPotential{n}", self)
        if dlg.exec():
            d = dlg.values()
            if edge:
                d["edge"] = {"shape": edge["shape"].name,
                             "p0": edge["p0"], "p1": edge["p1"]}
                d["shapes"] = [edge["shape"].name]
                self.log(f"Boundary '{d['name']}' = {d['value']} Wb/m "
                         f"→ {edge['shape'].name} 모서리 (E선택)")
            else:
                d["shapes"] = [s.name for s in sel]
                self.log(f"Boundary '{d['name']}' = {d['value']} Wb/m → {len(sel)} obj")
            self.design.boundaries.append(d)
            self.refresh_trees()

    def assign_band(self):
        from .setup_dialogs import BandMotionDialog
        sel = self.view.selected_shapes()
        if not sel:
            self.log("Assign Band: 밴드 객체 선택 필요"); return
        dlg = BandMotionDialog(self)
        if dlg.exec():
            d = dlg.values(); d["band"] = sel[0].name
            self.design.motion = d
            self.log(f"Motion '{d['name']}' {d['type']} {d['speed']} rpm "
                     f"(init {d['init_pos']}°)")
            self.refresh_trees()

    def assign_mesh_op(self):
        from .setup_dialogs import MeshOpDialog
        sel = self.view.selected_shapes()
        if not sel:
            self.log("Assign Mesh Operation: 객체 선택 필요"); return
        n = len(self.design.mesh_ops) + 1
        dlg = MeshOpDialog(f"Length{n}", self)
        if dlg.exec():
            d = dlg.values(); d["shapes"] = [s.name for s in sel]
            self.design.mesh_ops.append(d)
            self.log(f"Mesh op '{d['name']}' max len {d['max_length']} mm")
            self.refresh_trees()

    def do_analyze(self):
        """Run the 2D magnetostatic FEM solve and show the B-field overlay."""
        if self.design.mesh is None:
            self.do_mesh()
            if self.design.mesh is None:
                return
        from ..model.solver import solve_magnetostatic
        try:
            t0 = time.perf_counter()
            npole = int(self.project.variables.value("N_pole", 10))
            nl = bool(getattr(self, "btn_nl", None) and self.btn_nl.isChecked())
            field = solve_magnetostatic(
                self.design.mesh, self.design.shapes, self.project.materials,
                self.design.excitations, n_pole=npole, nonlinear=nl)
            self.design.field = field
            self.view.set_field(field)
            self.btn_field.setChecked(True)
            dt = (time.perf_counter() - t0) * 1e3
            mode = f"nonlinear, {field.iters} it" if nl else "linear"
            self.log(f"Analyzed (magnetostatic, {mode}): Bmax = {field.bmax:.3f} T  "
                     f"({dt:.0f} ms)")
            self.ribbon.setCurrentIndex(5)        # Results tab
            self.refresh_trees()
        except Exception as e:
            QMessageBox.warning(self, "Analyze error", str(e))
            self.log(f"Analyze FAILED: {e}")

    def toggle_field(self):
        on = self.btn_field.isChecked()
        if on and self.design.field is None:
            self.log("먼저 Analyze를 실행하세요.")
            self.btn_field.setChecked(False); return
        self.view.show_field = on and self.design.field is not None
        self.view.set_field(self.design.field if self.view.show_field else None)

    def _estimate_gap_mm(self):
        """Mid air-gap radius: between the outer rotor/magnet radius and the
        inner stator radius (used as the Maxwell-stress integration contour)."""
        import numpy as np
        rotor_max = 0.0; stator_min = 1e9
        for s in self.design.shapes:
            m = self.project.materials.get(s.material)
            rr = []
            for ring in s.rings():
                rr.extend(np.hypot(ring[:, 0], ring[:, 1]).tolist())
            if not rr:
                continue
            is_rot = ((m and getattr(m, "is_magnet", False))
                      or s.name.startswith(("Rotor", "Magnet", "Shaft")))
            if is_rot:
                rotor_max = max(rotor_max, max(rr))
            elif s.name.startswith("Stator"):
                inner = [v for v in rr if v > 1.0]
                if inner:
                    stator_min = min(stator_min, min(inner))
        if rotor_max > 0 and stator_min < 1e9 and stator_min > rotor_max:
            return 0.5 * (rotor_max + stator_min)
        return rotor_max * 1.04 if rotor_max > 0 else 25.0

    def do_torque_plot(self):
        """Torque vs rotor position (rotation sweep) -> Rectangular Plot."""
        from PyQt6.QtWidgets import QApplication
        from ..model.solver import rotor_sweep
        from .results import ResultPlotDialog
        npole = int(self.project.variables.value("N_pole", 10))
        Lstk = self.project.variables.value("L_stk", 28.0) * 1e-3
        rgap = self._estimate_gap_mm()

        def prog(i, n):
            self.statusBar().showMessage(f"Torque sweep… {i}/{n}")
            QApplication.processEvents()

        self.log("Torque vs position 계산 중… (회전 스윕)")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            ang, tq = rotor_sweep(self.design.shapes, self.project.materials,
                                  n_pole=npole, n_steps=19, L_stk_m=Lstk,
                                  r_gap_mm=rgap, mesh_area=10.0, progress=prog)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Torque error", str(e)); return
        QApplication.restoreOverrideCursor()
        self.statusBar().clearMessage()
        pk = float(tq.max() - tq.min())
        self.log(f"Torque Plot: pk-pk = {pk:.4g} N·m, mean = {float(tq.mean()):.4g} "
                 f"N·m (무여자 코깅 토크; 권선 전류 인가 시 평균토크 발생)")
        ResultPlotDialog(ang, tq, "Rotor position [deg]", "Torque [N·m]",
                         "Torque Plot 1", self).exec()

    def do_backemf_plot(self):
        """No-load back-EMF (3-phase) vs rotor position -> Winding Plot."""
        from PyQt6.QtWidgets import QApplication
        from ..model.solver import backemf_sweep
        from .results import ResultPlotDialog
        v = self.project.variables
        npole = int(v.value("N_pole", 10))
        Lstk = v.value("L_stk", 28.0) * 1e-3
        turns = int(v.value("Zc", 14))
        rpm = v.value("BaseRPM", 3000.0)

        def prog(i, n):
            self.statusBar().showMessage(f"Back-EMF sweep… {i}/{n}")
            QApplication.processEvents()

        self.log("무부하 Back-EMF 계산 중… (자속쇄교 λ → e = -dλ/dt)")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            ang, emf, _ = backemf_sweep(self.design.shapes, self.project.materials,
                                        n_pole=npole, n_steps=37, L_stk_m=Lstk,
                                        turns=turns, base_rpm=rpm, mesh_area=10.0,
                                        progress=prog)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Back-EMF error", str(e)); return
        QApplication.restoreOverrideCursor()
        self.statusBar().clearMessage()
        pk = max(float(abs(emf[p]).max()) for p in "ABC")
        self.log(f"Back-EMF: peak ≈ {pk:.3g} V @ {rpm:g} rpm (PhaseA/B/C)")
        series = [("InducedVoltage(PhaseA)", emf["A"]),
                  ("InducedVoltage(PhaseB)", emf["B"]),
                  ("InducedVoltage(PhaseC)", emf["C"])]
        ResultPlotDialog(ang, emf["A"], "Rotor position [deg]",
                         "Induced voltage [V]", "Winding Plot 1 (Back-EMF)",
                         self, series=series).exec()

    def do_load_torque_plot(self):
        """Load torque under rated 3-phase current (q-axis) vs rotor position."""
        from PyQt6.QtWidgets import QApplication
        from ..model.solver import load_torque_sweep
        from .results import ResultPlotDialog
        v = self.project.variables
        npole = int(v.value("N_pole", 10))
        Lstk = v.value("L_stk", 28.0) * 1e-3
        turns = int(v.value("Zc", 14))
        rpm = v.value("BaseRPM", 3000.0)
        ipk = v.value("I_rms", 8.2) * (2 ** 0.5)
        rgap = self._estimate_gap_mm()

        def prog(i, n):
            self.statusBar().showMessage(f"Load-torque sweep… {i}/{n}")
            QApplication.processEvents()

        self.log("부하 토크 계산 중… (3상 전류 인가, 회전 동기 γ=90°)")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            ang, tq = load_torque_sweep(self.design.shapes, self.project.materials,
                                        n_pole=npole, n_steps=19, L_stk_m=Lstk,
                                        r_gap_mm=rgap, turns=turns, i_peak=ipk,
                                        gamma_deg=90.0, base_rpm=rpm,
                                        mesh_area=12.0, progress=prog)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Load torque error", str(e)); return
        QApplication.restoreOverrideCursor()
        self.statusBar().clearMessage()
        avg = float(tq.mean()); rip = float(tq.max() - tq.min())
        self.log(f"Load Torque: avg ≈ {avg:.3g} N·m, ripple = {rip:.3g} N·m "
                 f"(I_pk={ipk:.3g} A, q축 γ=90°)")
        ResultPlotDialog(ang, tq, "Rotor position [deg]", "Torque [N·m]",
                         "Load Torque Plot", self).exec()

    def do_transient_emf(self):
        """Back-EMF as a time-domain waveform (constant-speed transient)."""
        from PyQt6.QtWidgets import QApplication
        from ..model.solver import transient_emf
        from .results import ResultPlotDialog
        v = self.project.variables
        npole = int(v.value("N_pole", 10))
        Lstk = v.value("L_stk", 28.0) * 1e-3
        turns = int(v.value("Zc", 14))
        rpm = v.value("BaseRPM", 3000.0)
        self.log("Transient Back-EMF (시간영역) 계산 중…")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            t_ms, emf, period = transient_emf(self.design.shapes,
                                              self.project.materials, n_pole=npole,
                                              base_rpm=rpm, turns=turns,
                                              L_stk_m=Lstk, n_cycles=2, mesh_area=12.0)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Transient error", str(e)); return
        QApplication.restoreOverrideCursor()
        self.log(f"Transient EMF: f_elec = {1.0/period:.1f} Hz "
                 f"(period {period*1e3:.3f} ms), 2 cycles @ {rpm:g} rpm")
        series = [("InducedVoltage(PhaseA)", emf["A"]),
                  ("InducedVoltage(PhaseB)", emf["B"]),
                  ("InducedVoltage(PhaseC)", emf["C"])]
        ResultPlotDialog(t_ms, emf["A"], "Time [ms]", "Induced voltage [V]",
                         "Transient Back-EMF vs Time", self, series=series).exec()

    def do_core_loss(self):
        """Iron (core) loss via Steinmetz/Bertotti over one electrical cycle."""
        from PyQt6.QtWidgets import QApplication
        from ..model.solver import core_loss_sweep, electrical_freq
        v = self.project.variables
        npole = int(v.value("N_pole", 10))
        Lstk = v.value("L_stk", 28.0) * 1e-3
        rpm = v.value("BaseRPM", 3000.0)
        f = electrical_freq(rpm, npole)
        self.log(f"Core loss 계산 중… (f_elec={f:.1f} Hz, 회전 1주기 peak B)")
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            r = core_loss_sweep(self.design.shapes, self.project.materials,
                                freq_hz=f, n_pole=npole, L_stk_m=Lstk,
                                n_steps=13, mesh_area=12.0)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Core loss error", str(e)); return
        QApplication.restoreOverrideCursor()
        self.log(f"Core Loss @ {f:.1f} Hz: total {r['total']:.3f} W "
                 f"(hyst {r['hyst']:.3f} / eddy {r['eddy']:.3f} / excess {r['excess']:.3f})")
        QMessageBox.information(
            self, "Core Loss (Steinmetz/Bertotti)",
            f"Electrical frequency: {f:.1f} Hz\n\n"
            f"Total iron loss: {r['total']:.3f} W\n"
            f"  · hysteresis : {r['hyst']:.3f} W\n"
            f"  · eddy        : {r['eddy']:.3f} W\n"
            f"  · excess      : {r['excess']:.3f} W")

    def do_optimetrics(self):
        """Parametric sweep over one design variable -> metric table + CSV."""
        from PyQt6.QtWidgets import QApplication
        import numpy as np
        from ..model import generate, apply_cmd
        from ..model.solver import (solve_magnetostatic, rotor_sweep,
                                    backemf_sweep, load_torque_sweep)
        from .results import OptimetricsDialog
        names = list(self.project.variables.exprs.keys())
        dlg = OptimetricsDialog(names, self)
        if "MagnetR" in names:
            dlg.var.setCurrentText("MagnetR")

        def run():
            var, start, stop, steps, metric = dlg.values()
            vals = np.linspace(start, stop, steps)
            dlg.bar.setVisible(True); dlg.bar.setRange(0, steps); dlg.bar.setValue(0)
            npole = int(self.project.variables.value("N_pole", 10))
            Lstk = self.project.variables.value("L_stk", 28.0) * 1e-3
            turns = int(self.project.variables.value("Zc", 14))
            rpm = self.project.variables.value("BaseRPM", 3000.0)
            ipk = self.project.variables.value("I_rms", 8.2) * (2 ** 0.5)
            rgap = self._estimate_gap_mm()
            saved = self.project.variables.exprs.get(var)
            rows = []
            for i, vv in enumerate(vals):
                self.project.variables.set(var, str(float(vv)))
                for s in self.design.shapes:
                    self._reeval_cmd(s.cmd); apply_cmd(s)
                if metric == 1:                       # Bmax [T]
                    mesh = generate(self.design.shapes, max_area=10.0)
                    f = solve_magnetostatic(mesh, self.design.shapes,
                                            self.project.materials,
                                            self.design.excitations, n_pole=npole)
                    m = f.bmax
                elif metric == 2:                     # Back-EMF peak [V]
                    _, emf, _ = backemf_sweep(self.design.shapes,
                                              self.project.materials, n_pole=npole,
                                              n_steps=19, L_stk_m=Lstk, turns=turns,
                                              base_rpm=rpm, mesh_area=14.0)
                    m = max(float(abs(emf[p]).max()) for p in "ABC")
                elif metric == 3:                     # Load torque avg [N·m]
                    _, tq = load_torque_sweep(self.design.shapes,
                                              self.project.materials, n_pole=npole,
                                              n_steps=7, L_stk_m=Lstk, r_gap_mm=rgap,
                                              turns=turns, i_peak=ipk, gamma_deg=90.0,
                                              base_rpm=rpm, mesh_area=16.0)
                    m = float(tq.mean())
                else:                                 # Torque pk-pk (cogging) [N·m]
                    _, tq = rotor_sweep(self.design.shapes, self.project.materials,
                                        n_pole=npole, n_steps=9, L_stk_m=Lstk,
                                        r_gap_mm=rgap, mesh_area=14.0)
                    m = float(tq.max() - tq.min())
                rows.append((float(vv), float(m)))
                dlg.bar.setValue(i + 1); QApplication.processEvents()
            if saved is not None:                     # restore the variable
                self.project.variables.set(var, saved)
                for s in self.design.shapes:
                    self._reeval_cmd(s.cmd); apply_cmd(s)
                    it = self.view.item_for(s)
                    if it:
                        it.rebuild()
                self.props.show_variables(self.project.variables.rows())
            dlg.set_results(rows); dlg.bar.setVisible(False)
            self.log(f"Optimetrics: {var} {start:g}→{stop:g} ({steps} pts) 완료")

        dlg.run_btn.clicked.connect(run)
        dlg.exec()

    def edit_solve_setup(self):
        from .setup_dialogs import SolveSetupDialog
        dlg = SolveSetupDialog(self.design.solver, self.design.setup, self)
        if dlg.exec():
            self.design.setup = dlg.values()
            self.log(f"Solve Setup '{self.design.setup['name']}' "
                     f"({self.design.solver})")
            self.refresh_trees()

    def do_cover_lines(self):
        from ..model import cover_lines
        sel = self.view.selected_shapes()
        if not sel:
            return
        self._snapshot()
        n = 0
        for s in sel:
            if cover_lines(s):
                it = self.view.item_for(s)
                if it:
                    it.rebuild()
                n += 1
        self.log(f"Cover Lines: {n} open polyline(s) → sheet")
        self.refresh_trees(); self._on_canvas_selection()

    def do_delete(self):
        sel = self.view.selected_shapes()
        if not sel:
            return
        self._snapshot()
        for s in sel:
            self.design.remove(s)
        self.view.reload(self.design.shapes)
        self.log(f"Deleted {len(sel)} object(s)"); self.refresh_trees()

    def toggle_snap(self):
        self.view.snap = not self.view.snap
        self.log(f"Grid snap {'ON' if self.view.snap else 'OFF'}")

    def toggle_osnap(self):
        on = self.btn_osnap.isChecked()
        self.view.set_osnap(on)
        self.log(f"Object snap {'ON' if on else 'OFF'}")


    def draw_circle_dims(self):
        d = CircleDialog(self)
        if d.exec():
            self._snapshot()
            cx, cy, r = d.values()
            cx, cy = self.view.to_global(cx, cy)         # center in active CS
            self.view._naming["circle"] += 1
            s = Shape.circle(f"Circle{self.view._naming['circle']}", cx, cy, r)
            self.design.add(s); self.view.add_shape(s)
            self.log(f"Created {s.name} (r={r:g} mm)"); self.refresh_trees()

    def draw_rect_dims(self):
        d = RectDialog(self)
        if d.exec():
            self._snapshot()
            x0, y0, x1, y1 = d.values()
            self.view._naming["rect"] += 1
            if self.view.wcs.is_global:
                s = Shape.rectangle(f"Rectangle{self.view._naming['rect']}",
                                    x0, y0, x1, y1)
            else:                                  # rotated/offset CS -> polygon
                corners = [self.view.to_global(x0, y0), self.view.to_global(x1, y0),
                           self.view.to_global(x1, y1), self.view.to_global(x0, y1)]
                s = Shape.polygon(f"Rectangle{self.view._naming['rect']}", corners)
            self.design.add(s); self.view.add_shape(s)
            self.log(f"Created {s.name}"); self.refresh_trees()

    def relative_cs_dialog(self):
        """Create/activate a Relative CS (offset + rotation) like Maxwell."""
        from .dialogs import RelativeCSDialog
        n = len([c for c in self.design.coord_systems]) + 1
        d = RelativeCSDialog(self, default_name=f"RelativeCS{n}")
        if d.exec():
            name, ox, oy, rot = d.values()
            self.view.set_wcs(name, ox, oy, rot)
            self.design.coord_systems = [c for c in self.design.coord_systems
                                         if c["name"] != name]
            self.design.coord_systems.append(
                {"name": name, "ox": ox, "oy": oy, "rot": rot})
            self.refresh_trees()
            self.log(f"Working CS = {name} (origin {ox:g},{oy:g} mm, rot {rot:g}°). "
                     f"이후 입력 좌표는 이 CS 기준으로 배치됩니다.")

    def set_global_cs(self):
        """Reset the working coordinate system back to Global."""
        self.view.set_wcs()
        self.log("Working CS = Global")

    def do_face_cs(self):
        """Face CS: create a working CS from the picked face/edge (Maxwell Face CS).
        Edge pick -> origin at edge midpoint, X axis along the edge; face/object
        pick -> origin at the body centroid."""
        import math
        pk = self.view.picked
        if not pk:
            self.log("Face CS: F(면) 또는 E(모서리)로 먼저 선택하세요."); return
        if pk["mode"] == "edge":
            (x0, y0), (x1, y1) = pk["p0"], pk["p1"]
            ox, oy = 0.5 * (x0 + x1), 0.5 * (y0 + y1)
            rot = math.degrees(math.atan2(y1 - y0, x1 - x0))
        else:
            c = pk["shape"].geom.representative_point()
            ox, oy, rot = c.x, c.y, 0.0
        n = len(self.design.coord_systems) + 1
        name = f"FaceCS{n}"
        self.view.set_wcs(name, ox, oy, rot)
        self.design.coord_systems = [c for c in self.design.coord_systems
                                     if c["name"] != name]
        self.design.coord_systems.append({"name": name, "ox": ox, "oy": oy, "rot": rot})
        self.refresh_trees()
        self.log(f"{name} @ ({ox:.2f},{oy:.2f}) rot {rot:.1f}° — 피킹 기준 좌표계")

    def do_fillet(self):
        """Fillet the picked vertex's corner (Maxwell: round magnet ends).
        Default radius = the MagnetR design variable."""
        from ..model.geometry import fillet_corner
        pk = self.view.picked
        if not pk or pk.get("mode") != "vertex":
            self.log("Fillet: V키로 꼭짓점을 먼저 선택하세요."); return
        shape = pk["shape"]
        default_r = self.project.variables.value("MagnetR", 1.0) or 1.0
        r, ok = _QInputDialog.getDouble(self, "Fillet", "Radius [mm]:",
                                        float(default_r), 0.001, 1e4, 3)
        if not ok:
            return
        self._snapshot()
        new = fillet_corner(shape, pk["x"], pk["y"], r)
        if shape in self.design.shapes:
            self.design.shapes[self.design.shapes.index(shape)] = new
        it = self.view.item_for(shape)
        if it:
            it.shape = new; it.rebuild()
        self.view._clear_pick()
        self.refresh_trees()
        self.log(f"Filleted {new.name} corner (r={r:g} mm)")

    def do_around_axis(self):
        sel = self.view.selected_shapes()
        if not sel:
            self.log("Around Axis: 객체 선택 필요"); return
        d = AroundAxisDialog(self)
        if d.exec():
            self._snapshot()
            count, angle, ox, oy = d.values(); n = 0
            for s in sel:
                for cp in duplicate_around_axis(s, count, angle, ox, oy):
                    self.design.add(cp); n += 1
            self.view.reload(self.design.shapes)
            self.log(f"Duplicated around axis: +{n}"); self.refresh_trees()

    def do_along_line(self):
        sel = self.view.selected_shapes()
        if not sel:
            self.log("Along Line: 객체 선택 필요"); return
        d = AlongLineDialog(self)
        if d.exec():
            self._snapshot()
            count, dx, dy = d.values(); n = 0
            for s in sel:
                for cp in duplicate_along_line(s, count, dx, dy):
                    self.design.add(cp); n += 1
            self.view.reload(self.design.shapes)
            self.log(f"Duplicated along line: +{n}"); self.refresh_trees()

    def do_mirror(self):
        sel = self.view.selected_shapes()
        if not sel:
            self.log("Mirror: 객체 선택 필요"); return
        d = MirrorDialog(self)
        if d.exec():
            self._snapshot()
            axis, off, keep = d.values()
            for s in sel:
                m = mirrored(s, axis, off)
                if not keep:
                    self.design.remove(s)
                self.design.add(m)
            self.view.reload(self.design.shapes)
            self.log(f"Mirrored {len(sel)} about {axis}-axis"); self.refresh_trees()

    def do_mesh(self):
        if not self.design.shapes:
            self.log("Mesh: 형상이 없습니다."); return
        try:
            t0 = time.perf_counter()
            mesh = generate(self.design.shapes)
            self.design.mesh = mesh
            self.view.set_mesh(mesh)
            self.btn_showmesh.setChecked(True)
            dt = (time.perf_counter() - t0) * 1e3
            self.log(f"Mesh generated: {mesh.n_nodes} nodes, "
                     f"{mesh.n_tris} elements  ({dt:.0f} ms)")
            self.refresh_trees()
        except Exception as e:
            QMessageBox.warning(self, "Mesh error", str(e))
            self.log(f"Mesh FAILED: {e}")

    def toggle_mesh(self):
        on = not self.view.show_mesh
        self.view.show_mesh = on and self.design.mesh is not None
        self.view.set_mesh(self.design.mesh if self.view.show_mesh else None)
        if on and self.design.mesh is None:
            self.log("먼저 Generate Mesh를 실행하세요.")

    def insert_sample(self):
        self._snapshot()
        for s in build_motor():
            self.design.add(s)
        self.view.reload(self.design.shapes); self.view.fit()
        self.log(f"Inserted sample PM motor ({len(self.design.shapes)} objects)")
        self.refresh_trees()

    # ----------------------------------------------------------- materials
    def new_material(self):
        name, ok = QInputDialog.getText(self, "New material", "Name:")
        if ok and name:
            self.project.materials[name] = Material(name)
            self.edit_material(self.project.materials[name])

    def edit_selected_material(self):
        s = self._selected()
        if not s:
            self.log("Edit Material: 객체 선택 필요"); return
        mat = self.project.materials.get(s.material)
        if mat:
            self.edit_material(mat)

    def edit_material(self, mat):
        from .material_dialog import ViewEditMaterialDialog
        old = mat.name
        dlg = ViewEditMaterialDialog(mat, self)
        if dlg.exec():
            updated = dlg.apply_to_material()
            if updated.name != old:
                self.project.materials.pop(old, None)
            self.project.materials[updated.name] = updated
            self.log(f"Edited material '{updated.name}' "
                     f"(BH pts: {updated.bh.H.size}, μr={updated.mu_r:g})")
            self.refresh_trees()

    # -------------------------------------------------------------- theme
    def toggle_theme(self):
        from ..app import TECH_QSS, LIGHT_QSS
        from PyQt6.QtWidgets import QApplication
        self._dark = not self._dark
        QApplication.instance().setStyleSheet(TECH_QSS if self._dark else LIGHT_QSS)
        self.view.set_dark(self._dark)
        self.log(f"Theme: {'Dark' if self._dark else 'Light'}")
