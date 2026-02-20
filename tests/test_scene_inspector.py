"""Tests for the SceneInspector module."""

import pytest


def _snapshot_and_find_ref(introspector, name):
    tree = introspector.snapshot()["tree"]
    for line in tree.split("\n"):
        if name in line and "[ref=" in line:
            start = line.index("[ref=") + 5
            end = line.index("]", start)
            return line[start:end]
    raise ValueError(f"Widget '{name}' not found in snapshot")


def test_scene_snapshot(qapp, sample_window, introspector, scene_inspector):
    ref = _snapshot_and_find_ref(introspector, "TestGraphicsView")
    result = scene_inspector.scene_snapshot(ref)
    items = result["items"]
    # We added 3 items: rect, ellipse, text
    assert len(items) == 3

    classes = [i["class"] for i in items]
    assert "QGraphicsRectItem" in classes
    assert "QGraphicsEllipseItem" in classes
    assert "QGraphicsTextItem" in classes


def test_scene_item_has_text(qapp, sample_window, introspector, scene_inspector):
    ref = _snapshot_and_find_ref(introspector, "TestGraphicsView")
    result = scene_inspector.scene_snapshot(ref)
    text_items = [i for i in result["items"] if "text" in i]
    assert len(text_items) == 1
    assert text_items[0]["text"] == "Hello"


def test_scene_item_details(qapp, sample_window, introspector, scene_inspector):
    ref = _snapshot_and_find_ref(introspector, "TestGraphicsView")
    scene_inspector.scene_snapshot(ref)
    # Get details of first item
    details = scene_inspector.scene_item_details(ref, 0)
    assert "class" in details
    assert "pos" in details
    assert "bounds" in details


def test_scene_snapshot_not_graphics_view(qapp, sample_window, introspector, scene_inspector):
    ref = _snapshot_and_find_ref(introspector, "SearchField")
    with pytest.raises(ValueError, match="not a QGraphicsView"):
        scene_inspector.scene_snapshot(ref)
