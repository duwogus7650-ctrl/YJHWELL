"""Application entry point and engineering-palette stylesheet."""
from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from .ui.main_window import MainWindow

DARK_QSS = """
QMainWindow, QWidget { background: #1b1f24; color: #cdd6df;
    font-family: 'Segoe UI'; font-size: 12px; }
QToolBar { background: #11151a; spacing: 4px; padding: 4px; border: none;
    border-bottom: 1px solid #2c343d; }
QToolBar QToolButton {
    color: #cdd6df; padding: 5px 10px; border-radius: 4px; }
QToolBar QToolButton:hover { background: #2f5f8f; color: #ffffff; }
QToolBar QToolButton:checked { background: #e6a23c; color: #11151a; }
QToolBar::separator { background: #2c343d; width: 1px; margin: 4px 4px; }
QMenuBar { background: #11151a; color: #cdd6df; }
QMenuBar::item:selected { background: #2f5f8f; color: #ffffff; }
QMenu { background: #232a31; border: 1px solid #2c343d; color: #cdd6df; }
QMenu::item:selected { background: #2f5f8f; color: #ffffff; }
QDockWidget { color: #cdd6df; }
QDockWidget::title { background: #11151a; color: #9fb3c8; padding: 4px 8px;
    border-bottom: 1px solid #2c343d; }
QTreeWidget, QPlainTextEdit, QTableWidget, QLineEdit, QComboBox, QDoubleSpinBox {
    background: #232a31; color: #cdd6df; border: 1px solid #2c343d;
    border-radius: 4px; selection-background-color: #2f5f8f; }
QHeaderView::section { background: #11151a; color: #9fb3c8; border: 0;
    border-right: 1px solid #2c343d; padding: 3px; }
QTableWidget { gridline-color: #2c343d; }
QPlainTextEdit { font-family: 'Consolas','Courier New',monospace; font-size: 11px;
    color: #9fd0a0; }
QTableWidget, QDoubleSpinBox, QLineEdit { font-family: 'Consolas',monospace; }
QGroupBox { border: 1px solid #2c343d; border-radius: 4px; margin-top: 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 8px; color: #9fb3c8; }
QLabel { color: #cdd6df; }
QCheckBox { color: #cdd6df; }
QPushButton { background: #2f5f8f; color: #ffffff; border-radius: 4px;
    padding: 5px 12px; }
QPushButton:hover { background: #4a90d9; }
QStatusBar { background: #11151a; color: #9fb3c8; }
QStatusBar QLabel { color: #9fb3c8; font-family: 'Consolas',monospace; }
/* panel tabs (Attribute/Command/Variables, BH curve, etc.) */
QTabWidget::pane { border: 1px solid #2c343d; }
QTabBar::tab { background: #1b1f24; color: #cdd6df; padding: 5px 14px;
    border: 1px solid #2c343d; margin-right: 1px; }
QTabBar::tab:selected { background: #2f5f8f; color: #ffffff; font-weight: bold; }
QTabBar::tab:hover { background: #2a323b; color: #ffffff; }
/* ribbon */
QTabWidget#ribbon::pane { background: #232a31; border: 0; border-bottom: 1px solid #2c343d; }
QTabWidget#ribbon QTabBar::tab { background: #11151a; color: #9fb3c8;
    padding: 5px 16px; border: 0; }
QTabWidget#ribbon QTabBar::tab:selected { background: #232a31; color: #ffffff;
    border-bottom: 2px solid #e6a23c; }
QFrame#ribbonGroup { background: #232a31; border: 0; }
QFrame#ribbonSep { color: #2c343d; }
QLabel#ribbonCaption { color: #6f8093; font-size: 10px; }
QToolButton#ribbonButton { color: #cdd6df; padding: 3px 5px; border-radius: 4px;
    font-size: 10px; }
QToolButton#ribbonButton:hover { background: #2f5f8f; color: #ffffff; }
QToolButton#ribbonButton:checked { background: #e6a23c; color: #11151a; }
"""

LIGHT_QSS = """
QMainWindow, QWidget { background: #eef1f4; color: #1d3f63; font-family: 'Segoe UI'; font-size: 12px; }
QMenuBar { background: #dde3ea; color: #1d3f63; }
QMenuBar::item:selected { background: #2f5f8f; color: #ffffff; }
QMenu { background: #ffffff; border: 1px solid #c2cbd4; }
QMenu::item:selected { background: #2f5f8f; color: #ffffff; }
QDockWidget::title { background: #cdd6df; color: #1d3f63; padding: 4px 8px; }
QTreeWidget, QPlainTextEdit, QTableWidget, QLineEdit, QComboBox, QDoubleSpinBox {
    background: #ffffff; color: #1d3f63; border: 1px solid #c2cbd4; border-radius: 4px;
    selection-background-color: #2f5f8f; selection-color: #ffffff; }
QHeaderView::section { background: #dde3ea; color: #1d3f63; border: 0;
    border-right: 1px solid #c2cbd4; padding: 3px; }
QPlainTextEdit { font-family: 'Consolas',monospace; font-size: 11px; color: #1d5c2e; }
QTableWidget, QDoubleSpinBox, QLineEdit { font-family: 'Consolas',monospace; }
QGroupBox { border: 1px solid #c2cbd4; border-radius: 4px; margin-top: 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 8px; color: #2f5f8f; }
QPushButton { background: #2f5f8f; color: #ffffff; border-radius: 4px; padding: 5px 12px; }
QPushButton:hover { background: #1d3f63; }
QStatusBar { background: #dde3ea; color: #1d3f63; }
QStatusBar QLabel { color: #1d3f63; font-family: 'Consolas',monospace; }
QTabWidget::pane { border: 1px solid #c2cbd4; }
QTabBar::tab { background: #dde3ea; color: #1d3f63; padding: 5px 14px;
    border: 1px solid #c2cbd4; margin-right: 1px; }
QTabBar::tab:selected { background: #2f5f8f; color: #ffffff; font-weight: bold; }
QTabBar::tab:hover { background: #c9d3df; }
QTabWidget#ribbon::pane { background: #f2f4f7; border: 0; border-bottom: 1px solid #c2cbd4; }
QTabWidget#ribbon QTabBar::tab { background: #dde3ea; color: #44566a; padding: 5px 16px; border: 0; }
QTabWidget#ribbon QTabBar::tab:selected { background: #f2f4f7; color: #1d3f63; border-bottom: 2px solid #e6a23c; }
QFrame#ribbonGroup { background: #f2f4f7; border: 0; }
QFrame#ribbonSep { color: #c2cbd4; }
QLabel#ribbonCaption { color: #8190a0; font-size: 10px; }
QToolButton#ribbonButton { color: #1d3f63; padding: 3px 5px; border-radius: 4px;
    font-size: 10px; }
QToolButton#ribbonButton:hover { background: #2f5f8f; color: #ffffff; }
QToolButton#ribbonButton:checked { background: #e6a23c; color: #11151a; }
QToolBar#headerBar { background: #dde3ea; border: 0; border-bottom: 1px solid #c2cbd4; }
QLabel#appName { color: #1d3f63; font-size: 25px; font-weight: bold; letter-spacing: 1px; }
QLabel#appMaker { color: #2f5f8f; font-size: 15px; }
QLabel#hdrSep { background: #c2cbd4; }
QLabel#hdrTitle { color: #1d3f63; font-size: 14px; }
QToolButton#hdrIcon, QToolButton#winBtn, QToolButton#winClose {
    background: transparent; border: 0; border-radius: 8px; }
QToolButton#hdrIcon:hover, QToolButton#winBtn:hover { background: #c9d3df; }
QToolButton#winClose:hover { background: #e06c7a; }
QToolButton::menu-indicator { image: none; }
"""

# Tech "QDD control" theme — deep navy + cyan accents (from the user's ui.png)
TECH_QSS = """
QMainWindow, QWidget { background: #0a1422; color: #cfe0ee;
    font-family: 'Segoe UI'; font-size: 12px; }
QMenuBar { background: #061020; color: #8fbfdc; }
QMenuBar::item:selected { background: #1f7ae0; color: #ffffff; }
QMenu { background: #0e1c30; border: 1px solid #1f5e80; color: #cfe0ee; }
QMenu::item:selected { background: #1f7ae0; color: #ffffff; }
QMenu::separator { background: #15324c; height: 1px; }
QDockWidget { color: #cfe0ee; }
QDockWidget::title { background: #0c1830; color: #2bd6ff; padding: 5px 8px;
    border: 1px solid #1f5e80; }
QTreeWidget, QPlainTextEdit, QTableWidget, QLineEdit, QComboBox, QDoubleSpinBox, QSpinBox {
    background: #0c1830; color: #cfe0ee; border: 1px solid #1f5e80;
    border-radius: 4px; selection-background-color: #1f7ae0; selection-color: #ffffff; }
QHeaderView::section { background: #0a1a30; color: #2bd6ff; border: 0;
    border-right: 1px solid #1f5e80; padding: 4px; }
QTableWidget { gridline-color: #15324c; }
QPlainTextEdit { font-family: 'Consolas',monospace; font-size: 11px; color: #46d39a; }
QTableWidget, QDoubleSpinBox, QLineEdit, QSpinBox { font-family: 'Consolas',monospace; }
QGroupBox { border: 1px solid #1f6e90; border-radius: 6px; margin-top: 8px; }
QGroupBox::title { subcontrol-origin: margin; left: 8px; color: #2bd6ff; }
QLabel { color: #cfe0ee; }
QCheckBox { color: #cfe0ee; }
QPushButton { background: #14385f; color: #cfe9f7; border: 1px solid #2bd6ff;
    border-radius: 4px; padding: 5px 12px; }
QPushButton:hover { background: #1f7ae0; color: #ffffff; }
QStatusBar { background: #061020; color: #2bd6ff; }
QStatusBar QLabel { color: #6fd8f0; font-family: 'Consolas',monospace; }
QScrollBar:vertical, QScrollBar:horizontal { background: #0a1422; }
QScrollBar::handle { background: #1f5e80; border-radius: 3px; }
QTabWidget::pane { border: 1px solid #1f6e90; }
QTabBar::tab { background: #0a1422; color: #8fbfdc; padding: 5px 14px;
    border: 1px solid #15324c; margin-right: 1px; }
QTabBar::tab:selected { background: #123a5a; color: #2bd6ff;
    border-bottom: 2px solid #2bd6ff; font-weight: bold; }
QTabBar::tab:hover { color: #2bd6ff; }
QToolBar { background: #061020; spacing: 4px; padding: 4px; border: 0;
    border-bottom: 1px solid #1f6e90; }
QTabWidget#ribbon::pane { background: #0c1830; border: 0; border-bottom: 1px solid #1f6e90; }
QTabWidget#ribbon QTabBar::tab { background: #061020; color: #7fb4d0;
    padding: 5px 16px; border: 0; }
QTabWidget#ribbon QTabBar::tab:selected { background: #0c1830; color: #2bd6ff;
    border-bottom: 2px solid #2bd6ff; }
QFrame#ribbonGroup { background: #0c1830; border: 0; }
QFrame#ribbonSep { color: #1f5e80; }
QLabel#ribbonCaption { color: #4a7a96; font-size: 10px; }
QToolButton#ribbonButton { color: #cfe0ee; padding: 3px 5px; border-radius: 4px;
    font-size: 10px; }
QToolButton#ribbonButton:hover { background: #1f7ae0; color: #ffffff; }
QToolButton#ribbonButton:checked { background: #2bd6ff; color: #06121f; }
QToolBar#headerBar { background: #061020; border: 0; border-bottom: 1px solid #1f6e90; }
QLabel#appName { color: #eaf4ff; font-size: 25px; font-weight: bold;
    letter-spacing: 1px; }
QLabel#appMaker { color: #2bd6ff; font-size: 15px; }
QLabel#hdrSep { background: #1f5e80; }
QLabel#hdrTitle { color: #cfe0ee; font-size: 14px; }
QToolButton#hdrIcon, QToolButton#winBtn, QToolButton#winClose {
    background: transparent; border: 0; border-radius: 8px; }
QToolButton#hdrIcon:hover, QToolButton#winBtn:hover { background: #16385a; }
QToolButton#winClose:hover { background: #c0392b; }
QToolButton::menu-indicator { image: none; }
"""


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(TECH_QSS)
    w = MainWindow()
    w.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
