"""Tests for the Introspector module."""

import pytest

from qt_mcp.probe.introspector import MAX_PROPERTY_LENGTH

LONG_STYLE_CHARS = MAX_PROPERTY_LENGTH * 40
MAX_TRUNCATED_STYLE_LEN = MAX_PROPERTY_LENGTH + 100


def test_snapshot_returns_tree(qapp, sample_window, introspector):
    result = introspector.snapshot(max_depth=10)
    assert result["widget_count"] > 0
    tree = result["tree"]
    assert "MainWindow" in tree
    assert "[ref=w" in tree


def test_snapshot_contains_key_widgets(qapp, sample_window, introspector):
    result = introspector.snapshot()
    tree = result["tree"]
    assert "ProjectExplorer" in tree
    assert "SearchField" in tree
    assert "IncrementButton" in tree
    assert "CounterLabel" in tree


def test_snapshot_shows_tree_items(qapp, sample_window, introspector):
    result = introspector.snapshot()
    tree = result["tree"]
    assert "Wells" in tree
    assert "SGS-1" in tree
    assert "[ref=i" in tree


def test_widget_details(qapp, sample_window, introspector, registry):
    # First take a snapshot to populate the registry
    introspector.snapshot()

    # Find the SearchField ref
    tree = introspector.snapshot()["tree"]
    # Extract ref for SearchField
    for line in tree.split("\n"):
        if "SearchField" in line:
            # Extract ref=wN
            start = line.index("[ref=") + 5
            end = line.index("]", start)
            ref = line[start:end]
            break
    else:
        pytest.fail("SearchField not found in snapshot")

    details = introspector.widget_details(ref)
    assert details["class"] == "QLineEdit"
    assert details["objectName"] == "SearchField"
    assert "geometry" in details
    assert "properties" in details
    assert len(details["parent_chain"]) > 0


def test_widget_details_unknown_ref(qapp, sample_window, introspector):
    introspector.snapshot()
    with pytest.raises(ValueError, match="not found"):
        introspector.widget_details("w9999")


def test_list_windows(qapp, sample_window, introspector):
    result = introspector.list_windows()
    windows = result["windows"]
    assert len(windows) >= 1
    main = [w for w in windows if w["objectName"] == "MainWindow" and w["visible"]]
    assert len(main) >= 1


def test_object_tree(qapp, sample_window, introspector):
    result = introspector.object_tree(max_depth=5)
    assert result["count"] > 1
    assert "MainWindow" in result["tree"]


def test_snapshot_returns_generation(qapp, sample_window, introspector):
    r1 = introspector.snapshot()
    gen1 = r1["generation"]
    r2 = introspector.snapshot()
    gen2 = r2["generation"]
    assert gen2 > gen1


def test_widget_details_does_not_invalidate_refs(qapp, sample_window, introspector, registry):
    tree = introspector.snapshot()["tree"]
    ref = None
    for line in tree.split("\n"):
        if "SearchField" in line and "[ref=" in line:
            start = line.index("[ref=") + 5
            end = line.index("]", start)
            ref = line[start:end]
            break
    assert ref is not None

    introspector.widget_details(ref)

    # Ref should still resolve after widget_details
    assert registry.resolve(ref) is not None


def test_object_tree_with_root_ref_preserves_refs(qapp, sample_window, introspector, registry):
    tree = introspector.snapshot()["tree"]
    ref = None
    for line in tree.split("\n"):
        if "MainWindow" in line and "[ref=" in line:
            start = line.index("[ref=") + 5
            end = line.index("]", start)
            ref = line[start:end]
            break
    assert ref is not None

    introspector.object_tree(root_ref=ref, max_depth=3)

    # Original ref should still resolve
    assert registry.resolve(ref) is not None


def test_list_windows_does_not_invalidate_refs(qapp, sample_window, introspector, registry):
    tree = introspector.snapshot()["tree"]
    ref = None
    for line in tree.split("\n"):
        if "SearchField" in line and "[ref=" in line:
            start = line.index("[ref=") + 5
            end = line.index("]", start)
            ref = line[start:end]
            break
    assert ref is not None

    introspector.list_windows()

    assert registry.resolve(ref) is not None


def test_snapshot_skip_hidden(qapp, sample_window, introspector):
    from PySide6.QtWidgets import QWidget

    # Hide a panel to test skip_hidden
    left = sample_window.findChild(QWidget, "LeftPanel")
    left.setVisible(False)
    qapp.processEvents()

    r_all = introspector.snapshot(skip_hidden=False)
    r_skip = introspector.snapshot(skip_hidden=True)

    # skip_hidden should produce fewer widgets
    assert r_skip["widget_count"] < r_all["widget_count"]

    # Restore
    left.setVisible(True)
    qapp.processEvents()


def test_snapshot_root_ref(qapp, sample_window, introspector, registry):
    tree = introspector.snapshot()["tree"]
    ref = None
    for line in tree.split("\n"):
        if "RightPanel" in line and "[ref=" in line:
            start = line.index("[ref=") + 5
            end = line.index("]", start)
            ref = line[start:end]
            break
    assert ref is not None

    result = introspector.snapshot(root_ref=ref, max_depth=3)
    assert result["widget_count"] > 0
    # Subtree should contain RightPanel's children but not LeftPanel
    assert "SearchField" in result["tree"]
    assert "LeftPanel" not in result["tree"]


def test_checked_annotation(qapp, introspector):
    from PySide6.QtWidgets import QPushButton

    btn = QPushButton("Toggle")
    btn.setObjectName("TestCheckedBtn")
    btn.setCheckable(True)
    btn.setChecked(True)
    btn.show()
    qapp.processEvents()

    result = introspector.snapshot()
    assert "[checked]" in result["tree"]

    btn.close()
    qapp.processEvents()


def test_active_popup_empty(qapp, sample_window, introspector):
    result = introspector.active_popup()
    assert result["popup"] is None
    assert result["modal"] is None


def test_menu_items(qapp, sample_window, introspector, registry):
    from PySide6.QtWidgets import QMenu

    menu = QMenu("TestMenu")
    menu.setObjectName("TestMenu")
    menu.addAction("Open")
    menu.addAction("Save")
    menu.addSeparator()
    action = menu.addAction("Bold")
    action.setCheckable(True)
    action.setChecked(True)

    ref = registry.register(menu, prefix="w")
    result = introspector.menu_items(ref)
    actions = result["actions"]
    assert len(actions) == 4
    assert actions[0]["text"] == "Open"
    assert actions[2]["separator"] is True
    assert actions[3]["checked"] is True

    menu.deleteLater()
    qapp.processEvents()


def test_truncate_long_property(qapp, sample_window, introspector, registry):
    from PySide6.QtWidgets import QWidget

    w = QWidget()
    w.setObjectName("BigStyleWidget")
    w.setStyleSheet("a" * LONG_STYLE_CHARS)
    w.show()
    qapp.processEvents()

    ref = registry.register(w, prefix="w")
    details = introspector.widget_details(ref)
    style = details["properties"]["styleSheet"]
    assert len(style) <= MAX_TRUNCATED_STYLE_LEN
    assert "more chars]" in style

    w.close()
    qapp.processEvents()


def test_list_windows_skip_hidden(qapp, introspector):
    from PySide6.QtWidgets import QWidget

    w1 = QWidget()
    w1.setObjectName("VisibleWin")
    w1.show()
    w2 = QWidget()
    w2.setObjectName("HiddenWin")
    w2.show()
    w2.hide()
    qapp.processEvents()

    r_all = introspector.list_windows(skip_hidden=False)
    r_vis = introspector.list_windows(skip_hidden=True)

    all_names = [w["objectName"] for w in r_all["windows"]]
    vis_names = [w["objectName"] for w in r_vis["windows"]]

    assert "HiddenWin" in all_names
    assert "HiddenWin" not in vis_names
    assert "VisibleWin" in vis_names

    w1.close()
    w2.close()
    qapp.processEvents()


def test_snapshot_shows_tab_labels(qapp, sample_window, introspector):
    result = introspector.snapshot()
    tree = result["tree"]
    assert "[tabs: *Editor | Console | Help]" in tree


# --- find_widget tests ---


def test_find_widget_by_class_name(qapp, sample_window, introspector):
    result = introspector.find_widget(class_name="QPushButton")
    assert result["count"] > 0
    for w in result["widgets"]:
        assert w["class"] == "QPushButton"
    # Returned refs are usable
    assert all(w["ref"].startswith("w") for w in result["widgets"])


def test_find_widget_by_object_name(qapp, sample_window, introspector):
    result = introspector.find_widget(object_name="IncrementButton")
    assert result["count"] >= 1
    assert any(w["objectName"] == "IncrementButton" for w in result["widgets"])


def test_find_widget_by_text(qapp, sample_window, introspector):
    result = introspector.find_widget(text="Count: 0")
    assert result["count"] >= 1
    assert any("Count: 0" in (w["text"] or "") for w in result["widgets"])


def test_find_widget_by_pattern(qapp, sample_window, introspector):
    # 'Increment' appears in objectName of the button
    result = introspector.find_widget(pattern="Increment")
    assert result["count"] >= 1


def test_find_widget_max_results(qapp, sample_window, introspector):
    result = introspector.find_widget(class_name="QWidget", max_results=3)
    assert result["count"] <= 3


def test_find_widget_no_criteria_raises(qapp, sample_window, introspector):
    import pytest as _pytest

    with _pytest.raises(ValueError, match="At least one"):
        introspector.find_widget()


def test_find_widget_with_root_ref(qapp, sample_window, introspector):
    # First get a top-level ref via snapshot
    snap = introspector.snapshot()
    tree = snap["tree"]
    import re

    # Find root window ref — format is: - QMainWindow "MainWindow" [ref=wN] ...
    m = re.search(r'- Q?MainWindow\b.*\[ref=(w\d+)\]', tree)
    assert m, "MainWindow not in snapshot"
    root_ref = m.group(1)

    result = introspector.find_widget(class_name="QPushButton", root_ref=root_ref)
    assert result["count"] > 0


def test_find_widget_returns_geometry(qapp, sample_window, introspector):
    result = introspector.find_widget(object_name="IncrementButton")
    assert result["count"] >= 1
    w = result["widgets"][0]
    g = w["geometry"]
    assert g["width"] > 0 and g["height"] > 0


def test_find_widget_refs_usable_for_interaction(qapp, sample_window, introspector, interactor):
    from PySide6.QtWidgets import QLabel

    label = sample_window.findChild(QLabel, "CounterLabel")
    assert label.text() == "Count: 0"

    result = introspector.find_widget(object_name="IncrementButton")
    assert result["count"] >= 1
    ref = result["widgets"][0]["ref"]

    interactor.click(ref)
    assert label.text() == "Count: 1"
