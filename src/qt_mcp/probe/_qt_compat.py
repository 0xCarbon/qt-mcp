"""Qt6 binding compatibility — PySide6 or PyQt6.

Detects which Qt6 binding is available (prefers already-imported).
Qt5 bindings (PyQt5, PySide2) are not supported.

Usage:
    from qt_mcp.probe._qt_compat import QtCore, QtWidgets, QtGui
"""

from __future__ import annotations

import importlib
import sys

_BINDINGS = ["PySide6", "PyQt6"]

QT_BINDING: str = ""

# Prefer what's already imported (the target app's binding)
for _name in _BINDINGS:
    if _name in sys.modules:
        QT_BINDING = _name
        break

if not QT_BINDING:
    for _name in _BINDINGS:
        try:
            importlib.import_module(_name)
            QT_BINDING = _name
            break
        except ImportError:
            continue

if not QT_BINDING:
    raise ImportError("No supported Qt binding found. Install PySide6 or PyQt6.")

# Both PySide6 and PyQt6 are Qt6 — identical API surface
QtCore = importlib.import_module(f"{QT_BINDING}.QtCore")
QtWidgets = importlib.import_module(f"{QT_BINDING}.QtWidgets")
QtGui = importlib.import_module(f"{QT_BINDING}.QtGui")
QtNetwork = importlib.import_module(f"{QT_BINDING}.QtNetwork")

# PyQt6 uses pyqtSlot/pyqtSignal instead of Slot/Signal
if not hasattr(QtCore, "Slot") and hasattr(QtCore, "pyqtSlot"):
    QtCore.Slot = QtCore.pyqtSlot
if not hasattr(QtCore, "Signal") and hasattr(QtCore, "pyqtSignal"):
    QtCore.Signal = QtCore.pyqtSignal
