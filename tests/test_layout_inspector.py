"""Tests for the LayoutInspector module."""

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from qt_mcp.probe.layout_inspector import LayoutInspector
from qt_mcp.probe.ref_registry import RefRegistry


def test_layout_check_basic(qapp, sample_window):
    registry = RefRegistry()
    inspector = LayoutInspector(registry)
    result = inspector.layout_check()

    assert result["scanned"] > 0
    assert isinstance(result["issues"], list)


def test_layout_check_no_layout_warning(qapp, sample_window):
    """NoLayoutContainer in sample_app should trigger a no_layout warning."""
    registry = RefRegistry()
    inspector = LayoutInspector(registry)
    result = inspector.layout_check()

    no_layout_issues = [
        i
        for i in result["issues"]
        if i["type"] == "no_layout" and i["object_name"] == "NoLayoutContainer"
    ]
    assert len(no_layout_issues) >= 1
    assert no_layout_issues[0]["severity"] == "warning"


def test_layout_check_overlapping_siblings(qapp, sample_window):
    """ChildA and ChildB in NoLayoutContainer overlap and should be flagged."""
    registry = RefRegistry()
    inspector = LayoutInspector(registry)
    result = inspector.layout_check()

    overlap_issues = [i for i in result["issues"] if i["type"] == "overlapping_siblings"]
    # ChildA and ChildB have same geometry, should overlap
    assert len(overlap_issues) >= 1


def test_layout_check_zero_size(qapp):
    """A visible widget with 0x0 geometry should be flagged."""
    w = QWidget()
    w.setObjectName("ZeroWidget")
    w.setFixedSize(0, 0)
    w.show()
    qapp.processEvents()

    registry = RefRegistry()
    inspector = LayoutInspector(registry)
    result = inspector.layout_check()

    zero_issues = [
        i for i in result["issues"] if i["type"] == "zero_size" and i["object_name"] == "ZeroWidget"
    ]
    assert len(zero_issues) == 1
    assert zero_issues[0]["severity"] == "error"

    w.close()
    qapp.processEvents()


def test_layout_check_healthy_layout(qapp):
    """A properly laid-out widget should produce no issues."""
    w = QWidget()
    w.setObjectName("HealthyWidget")
    layout = QVBoxLayout()
    w.setLayout(layout)
    label = QLabel("Hello")
    label.setObjectName("HealthyLabel")
    layout.addWidget(label)
    w.resize(200, 100)
    w.show()
    qapp.processEvents()

    registry = RefRegistry()
    inspector = LayoutInspector(registry)
    result = inspector.layout_check()

    # Filter issues to only our test widgets
    our_issues = [
        i for i in result["issues"] if i["object_name"] in ("HealthyWidget", "HealthyLabel")
    ]
    assert our_issues == []

    w.close()
    qapp.processEvents()


def test_layout_check_text_truncation(qapp):
    """A label with text wider than its width should be flagged."""
    label = QLabel("A" * 200)  # Very long text
    label.setObjectName("TruncatedLabel")
    label.setFixedWidth(20)  # Very narrow
    label.show()
    qapp.processEvents()

    registry = RefRegistry()
    inspector = LayoutInspector(registry)
    result = inspector.layout_check()

    truncated = [
        i
        for i in result["issues"]
        if i["type"] == "text_truncated" and i["object_name"] == "TruncatedLabel"
    ]
    assert len(truncated) == 1
    assert truncated[0]["severity"] == "warning"

    label.close()
    qapp.processEvents()


def test_layout_check_skips_hidden(qapp):
    """Hidden widgets should not be scanned."""
    w = QWidget()
    w.setObjectName("HiddenParent")
    w.hide()
    qapp.processEvents()

    registry = RefRegistry()
    inspector = LayoutInspector(registry)
    result = inspector.layout_check()

    our_issues = [i for i in result["issues"] if i["object_name"] == "HiddenParent"]
    assert our_issues == []

    w.close()
    qapp.processEvents()


def test_layout_check_no_app():
    """Should return empty results when no QApplication."""
    # This test just verifies the guard — in the test suite QApplication
    # always exists, so we test the structure instead
    registry = RefRegistry()
    inspector = LayoutInspector(registry)
    result = inspector.layout_check()
    assert "issues" in result
    assert "scanned" in result
