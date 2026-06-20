"""Deterministic screenshot + logic verification for the ribbon shell."""
import sys
from PyQt6.QtWidgets import QApplication

from litemaxwell.app import DARK_QSS, LIGHT_QSS
from litemaxwell.ui.main_window import MainWindow

OUT = r"C:\Users\user\maxwell_frames"

app = QApplication(sys.argv)
app.setStyleSheet(LIGHT_QSS)
w = MainWindow()
w.toggle_theme()  # start dark -> toggle to light to match canvas
w.resize(1480, 900)
w.show()
app.processEvents()

w.insert_sample()
app.processEvents()
w.grab().save(rf"{OUT}\shell2_light.png")

w.do_mesh(); w.view.show_mesh = True; w.view.set_mesh(w.design.mesh)
app.processEvents(); w.view.viewport().repaint(); app.processEvents()
w.grab().save(rf"{OUT}\shell2_mesh.png")

print("SHAPES", len(w.design.shapes))
print("MESH_TRIS", w.design.mesh.n_tris if w.design.mesh else None)
print("TABS", [w.ribbon.tabText(i) for i in range(w.ribbon.count())])
print("THEME_DARK", w._dark)
print("OK", len(w.design.shapes) > 20 and w.design.mesh.n_tris > 1000)
