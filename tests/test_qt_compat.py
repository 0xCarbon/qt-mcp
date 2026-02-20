"""Tests for the Qt binding compatibility layer."""

from qt_mcp.probe._qt_compat import QT_BINDING, QtCore, QtGui, QtNetwork, QtWidgets


def test_binding_detection():
    assert QT_BINDING in ("PySide6", "PyQt6")


def test_core_modules_available():
    assert hasattr(QtCore, "QObject")
    assert hasattr(QtCore, "Slot")
    assert hasattr(QtWidgets, "QApplication")
    assert hasattr(QtGui, "QKeyEvent")
    assert hasattr(QtNetwork, "QTcpServer")


def test_qaction_in_qtgui():
    """QAction lives in QtGui for all Qt6 bindings."""
    assert hasattr(QtGui, "QAction")
