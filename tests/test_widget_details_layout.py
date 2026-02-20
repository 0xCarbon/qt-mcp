"""Tests for the layout fields added to widget_details."""

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from qt_mcp.probe.introspector import Introspector
from qt_mcp.probe.ref_registry import RefRegistry


def test_widget_details_has_layout_fields(qapp):
    """widget_details should include size_hint, size_policy, layout, margins."""
    registry = RefRegistry()
    introspector = Introspector(registry)

    w = QWidget()
    w.setObjectName("LayoutTestWidget")
    layout = QVBoxLayout()
    w.setLayout(layout)
    layout.addWidget(QLabel("test"))
    w.show()
    qapp.processEvents()

    ref = registry.register(w, prefix="w")
    details = introspector.widget_details(ref)

    assert "size_hint" in details
    assert isinstance(details["size_hint"], tuple)
    assert len(details["size_hint"]) == 2

    assert "size_policy" in details
    assert "x" in details["size_policy"]  # e.g. "Preferred×Preferred"

    assert details["layout"] == "QVBoxLayout"

    assert "margins" in details
    assert isinstance(details["margins"], tuple)
    assert len(details["margins"]) == 4

    w.close()
    qapp.processEvents()


def test_widget_details_no_layout(qapp):
    """A widget without a layout should show layout: 'none'."""
    registry = RefRegistry()
    introspector = Introspector(registry)

    w = QWidget()
    w.setObjectName("NoLayoutWidget")
    w.show()
    qapp.processEvents()

    ref = registry.register(w, prefix="w")
    details = introspector.widget_details(ref)

    assert details["layout"] == "none"

    w.close()
    qapp.processEvents()


def test_widget_details_min_size_hint(qapp):
    """QLabel should have a valid minimumSizeHint."""
    registry = RefRegistry()
    introspector = Introspector(registry)

    label = QLabel("Hello World")
    label.setObjectName("HintLabel")
    label.show()
    qapp.processEvents()

    ref = registry.register(label, prefix="w")
    details = introspector.widget_details(ref)

    assert "min_size_hint" in details
    assert isinstance(details["min_size_hint"], tuple)

    label.close()
    qapp.processEvents()
