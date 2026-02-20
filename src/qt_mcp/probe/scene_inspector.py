"""QGraphicsScene inspection: item enumeration and detail extraction."""

from __future__ import annotations

from typing import Any

from qt_mcp.probe._qt_compat import QtWidgets
from qt_mcp.probe.ref_registry import RefRegistry

QGraphicsView = QtWidgets.QGraphicsView


class SceneInspector:
    """Inspects QGraphicsView scenes and their items."""

    def __init__(self, registry: RefRegistry) -> None:
        self._registry = registry

    def scene_snapshot(self, ref: str) -> dict:
        """Get all items in a QGraphicsScene."""
        obj = self._registry.resolve_or_raise(ref)
        if not isinstance(obj, QGraphicsView):
            raise ValueError(f"Ref {ref} is not a QGraphicsView")

        scene = obj.scene()
        if scene is None:
            return {"items": []}

        items = []
        for item in scene.items():
            info: dict[str, Any] = {
                "class": type(item).__name__,
                "pos": [item.pos().x(), item.pos().y()],
                "bounds": [item.boundingRect().width(), item.boundingRect().height()],
                "z": item.zValue(),
                "visible": item.isVisible(),
            }
            # Try to get text for text items
            if hasattr(item, "toPlainText"):
                try:
                    info["text"] = item.toPlainText()
                except (RuntimeError, TypeError):
                    info["text"] = ""
            # Custom data
            data = item.data(0)
            if data is not None:
                info["data"] = repr(data)

            items.append(info)

        return {"items": items}

    def scene_item_details(self, ref: str, item_index: int) -> dict:
        """Get details of a specific scene item by index."""
        obj = self._registry.resolve_or_raise(ref)
        if not isinstance(obj, QGraphicsView):
            raise ValueError(f"Ref {ref} is not a QGraphicsView")

        scene = obj.scene()
        if scene is None:
            raise ValueError("No scene attached to view")

        all_items = scene.items()
        if item_index < 0 or item_index >= len(all_items):
            raise ValueError(f"Item index {item_index} out of range (0..{len(all_items) - 1})")

        item = all_items[item_index]
        bounds = item.boundingRect()
        position = item.pos()
        scene_bounds = item.sceneBoundingRect()

        result: dict[str, Any] = {
            "class": type(item).__name__,
            "pos": [position.x(), position.y()],
            "bounds": [bounds.width(), bounds.height()],
            "scene_bounds": [
                scene_bounds.x(),
                scene_bounds.y(),
                scene_bounds.width(),
                scene_bounds.height(),
            ],
            "z": item.zValue(),
            "visible": item.isVisible(),
            "enabled": item.isEnabled(),
            "flags": item.flags().value if hasattr(item.flags(), "value") else 0,
            "child_count": len(item.childItems()),
        }

        if hasattr(item, "toPlainText"):
            try:
                result["text"] = item.toPlainText()
            except (RuntimeError, TypeError):
                result["text"] = ""

        if hasattr(item, "pen"):
            try:
                pen = item.pen()
                result["pen_color"] = pen.color().name()
                result["pen_width"] = pen.widthF()
            except (RuntimeError, TypeError):
                result["pen_color"] = None

        if hasattr(item, "brush"):
            try:
                brush = item.brush()
                result["brush_color"] = brush.color().name()
            except (RuntimeError, TypeError):
                result["brush_color"] = None

        return result
