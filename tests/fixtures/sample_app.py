"""Minimal PySide6 app for testing: representative widget hierarchy."""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt, QThread
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsEllipseItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsTextItem,
    QGraphicsView,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

OFFSCREEN_ARGS = ["-platform", "offscreen"]


def build_sample_app(app: QApplication) -> QMainWindow:
    """Build a representative widget hierarchy for testing."""
    win = QMainWindow()
    win.setObjectName("MainWindow")
    win.resize(800, 600)

    central = QWidget()
    central.setObjectName("CentralWidget")
    win.setCentralWidget(central)

    root_layout = QHBoxLayout()
    central.setLayout(root_layout)

    # --- Left panel: tree widget ---
    left = QFrame()
    left.setObjectName("LeftPanel")
    left_layout = QVBoxLayout()
    left.setLayout(left_layout)

    tree = QTreeWidget()
    tree.setObjectName("ProjectExplorer")
    tree.setHeaderLabels(["Name"])
    wells = QTreeWidgetItem(tree, ["Wells"])
    QTreeWidgetItem(wells, ["SGS-1"])
    QTreeWidgetItem(wells, ["SGS-3"])
    volumes = QTreeWidgetItem(tree, ["Volumes"])
    QTreeWidgetItem(volumes, ["Seismic-A"])
    tree.expandAll()
    left_layout.addWidget(tree)

    # --- Right panel: form + graphics view ---
    right = QFrame()
    right.setObjectName("RightPanel")
    right_layout = QVBoxLayout()
    right.setLayout(right_layout)

    right_layout.addWidget(QLabel("Property Inspector"))

    edit = QLineEdit()
    edit.setObjectName("SearchField")
    edit.setPlaceholderText("Search...")
    right_layout.addWidget(edit)

    # Counter label (updated by button click)
    counter_label = QLabel("Count: 0")
    counter_label.setObjectName("CounterLabel")
    right_layout.addWidget(counter_label)

    btn = QPushButton("Increment")
    btn.setObjectName("IncrementButton")
    # Connect: clicking button increments the counter label
    _counter = {"value": 0}

    def _on_click() -> None:
        _counter["value"] += 1
        counter_label.setText(f"Count: {_counter['value']}")

    btn.clicked.connect(_on_click)
    right_layout.addWidget(btn)

    # Tab widget
    tabs = QTabWidget()
    tabs.setObjectName("TestTabWidget")
    tabs.addTab(QTextEdit("Editor content"), "Editor")
    tabs.addTab(QTextEdit("Console output"), "Console")
    tabs.addTab(QLabel("Help text"), "Help")
    tabs.setCurrentIndex(0)
    right_layout.addWidget(tabs)

    # Graphics view with scene
    gview = QGraphicsView()
    gview.setObjectName("TestGraphicsView")
    scene = QGraphicsScene(gview)  # parent to gview to prevent GC
    scene.setObjectName("TestScene")
    scene.addItem(QGraphicsRectItem(0, 0, 100, 50))
    scene.addItem(QGraphicsEllipseItem(120, 0, 80, 80))
    text_item = QGraphicsTextItem("Hello")
    text_item.setPos(0, 60)
    scene.addItem(text_item)
    gview.setScene(scene)
    right_layout.addWidget(gview)

    # Layout-less container (for layout inspector testing)
    no_layout_container = QWidget()
    no_layout_container.setObjectName("NoLayoutContainer")
    child_a = QLabel("ChildA", no_layout_container)
    child_a.setObjectName("ChildA")
    child_a.setGeometry(0, 0, 50, 20)
    child_b = QLabel("ChildB", no_layout_container)
    child_b.setObjectName("ChildB")
    child_b.setGeometry(0, 0, 50, 20)  # overlaps with ChildA
    right_layout.addWidget(no_layout_container)

    # QThread worker (for thread inspector testing)
    worker_thread = QThread(win)
    worker_thread.setObjectName("WorkerThread")

    # Splitter
    splitter = QSplitter(Qt.Orientation.Horizontal)
    splitter.setObjectName("MainSplitter")
    splitter.addWidget(left)
    splitter.addWidget(right)
    root_layout.addWidget(splitter)

    return win


def create_app() -> tuple[QApplication, QMainWindow]:
    """Create app + sample window. Caller must call app.processEvents()."""
    args = sys.argv[:] + OFFSCREEN_ARGS
    app = QApplication(args)
    win = build_sample_app(app)
    win.show()
    app.processEvents()
    return app, win


if __name__ == "__main__":
    app, win = create_app()
    print("Sample app created. Window visible:", win.isVisible())
    sys.exit(0)
