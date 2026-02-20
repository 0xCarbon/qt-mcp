"""Tests for the ApiInspector (signal connection auditor)."""

import pytest

from qt_mcp.probe.api_inspector import ApiInspector


@pytest.fixture()
def api_inspector(registry):
    return ApiInspector(registry)


def test_signals_on_button(qapp, sample_window, api_inspector, registry):
    from PySide6.QtWidgets import QPushButton

    btn = sample_window.findChild(QPushButton, "IncrementButton")
    assert btn is not None
    ref = registry.register(btn, prefix="w")

    result = api_inspector.signals(ref)
    assert result["class"] == "QPushButton"
    assert result["object_name"] == "IncrementButton"

    # QPushButton has clicked signal
    sig_names = [s["name"] for s in result["signals"]]
    assert "clicked" in sig_names

    # clicked should be connected (sample_app connects it)
    clicked = next(s for s in result["signals"] if s["name"] == "clicked")
    assert clicked["connected"] is True
    assert clicked["receiver_count"] >= 1


def test_signals_unconnected(qapp, api_inspector, registry):
    from PySide6.QtWidgets import QPushButton

    btn = QPushButton("Lonely")
    btn.setObjectName("LonelyButton")
    ref = registry.register(btn, prefix="w")

    result = api_inspector.signals(ref)
    clicked = next(s for s in result["signals"] if s["name"] == "clicked")
    assert clicked["connected"] is False
    assert clicked["receiver_count"] == 0


def test_signals_after_disconnect(qapp, api_inspector, registry):
    from PySide6.QtWidgets import QPushButton

    btn = QPushButton("Toggle")
    ref = registry.register(btn, prefix="w")

    handler = lambda: None  # noqa: E731
    btn.clicked.connect(handler)
    r1 = api_inspector.signals(ref)
    clicked1 = next(s for s in r1["signals"] if s["name"] == "clicked")
    assert clicked1["connected"] is True

    btn.clicked.disconnect(handler)
    r2 = api_inspector.signals(ref)
    clicked2 = next(s for s in r2["signals"] if s["name"] == "clicked")
    assert clicked2["connected"] is False


def test_signals_non_qobject_raises(qapp, api_inspector, registry):
    """Passing a non-QObject ref should raise ValueError."""
    from PySide6.QtWidgets import QTreeWidgetItem

    item = QTreeWidgetItem(["test"])
    ref = registry.register(item, prefix="i")
    with pytest.raises(ValueError, match="not a QObject"):
        api_inspector.signals(ref)


def test_signals_lists_all_signals(qapp, api_inspector, registry):
    """A QLineEdit should have textChanged, returnPressed, etc."""
    from PySide6.QtWidgets import QLineEdit

    edit = QLineEdit()
    ref = registry.register(edit, prefix="w")

    result = api_inspector.signals(ref)
    sig_names = [s["name"] for s in result["signals"]]
    assert "textChanged" in sig_names
    assert "returnPressed" in sig_names
