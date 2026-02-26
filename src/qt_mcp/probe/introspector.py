"""QObject tree traversal, property reading, and snapshot generation."""

from __future__ import annotations

import time
from typing import Any

from qt_mcp.probe._qt_compat import QtCore, QtWidgets
from qt_mcp.probe.ref_registry import RefRegistry

QObject = QtCore.QObject
QApplication = QtWidgets.QApplication
QWidget = QtWidgets.QWidget

# Properties already shown in the snapshot header line
_SKIP_PROPS = {"objectName", "visible", "enabled", "geometry"}

MAX_PROPERTY_LENGTH = 500

WINDOW_RETRY_DELAY_SEC = 0.05


def _truncate(val: str, limit: int = MAX_PROPERTY_LENGTH) -> str:
    if len(val) > limit:
        return val[:limit] + f" [...{len(val) - limit} more chars]"
    return val


def _safe_text(obj: QObject) -> str | None:
    """Try to read .text() from widget, return None on failure."""
    if not hasattr(obj, "text"):
        return None
    try:
        val = obj.text()  # type: ignore[call-arg, attr-defined]
        return str(val) if val else None
    except (TypeError, RuntimeError):
        return None


def _read_properties(obj: QObject) -> dict[str, Any]:
    """Read all QMetaObject properties, skipping ones in the header."""
    meta = obj.metaObject()
    props: dict[str, Any] = {}
    for i in range(meta.propertyCount()):
        prop = meta.property(i)
        name = prop.name()
        if name in _SKIP_PROPS:
            continue
        try:
            val = obj.property(name)
            if val is None:
                continue
            if isinstance(val, (str, int, float, bool)):
                props[name] = _truncate(val) if isinstance(val, str) else val
            else:
                props[name] = _truncate(repr(val))
        except (RuntimeError, TypeError):
            continue
    return props


def _read_tree_widget_items(tree_widget: Any, registry: RefRegistry) -> list[dict]:
    """Extract items from QTreeWidget."""
    from qt_mcp.probe._qt_compat import QtWidgets as _QtW

    QTreeWidget = _QtW.QTreeWidget
    QTreeWidgetItem = _QtW.QTreeWidgetItem

    if not isinstance(tree_widget, QTreeWidget):
        return []

    items: list[dict] = []

    def _walk_item(item: QTreeWidgetItem, depth: int) -> None:
        text = item.text(0)
        ref = registry.register(item, prefix="i")
        expanded = item.isExpanded()
        child_count = item.childCount()
        info: dict[str, Any] = {
            "ref": ref,
            "text": text,
            "depth": depth,
            "expanded": expanded,
            "children": child_count,
        }
        items.append(info)
        for i in range(child_count):
            _walk_item(item.child(i), depth + 1)

    top_count = tree_widget.topLevelItemCount()
    for i in range(top_count):
        _walk_item(tree_widget.topLevelItem(i), 0)

    return items


def _visible_top_level_widgets(app: QApplication) -> list[QWidget]:
    return [w for w in app.topLevelWidgets() if w.isVisible()]


class Introspector:
    """Walks QObject trees and reads widget properties."""

    def __init__(self, registry: RefRegistry) -> None:
        self._registry = registry

    def snapshot(
        self,
        max_depth: int = 10,
        root_ref: str | None = None,
        skip_hidden: bool = False,
    ) -> dict:
        """Build widget tree snapshot from all top-level windows."""
        app = QApplication.instance()
        if app is None:
            return {"tree": "(no QApplication)", "widget_count": 0, "generation": 0}

        if root_ref:
            # Subtree snapshot: don't clear registry
            root = self._registry.resolve_or_raise(root_ref)
            if not isinstance(root, QWidget):
                raise ValueError(f"Ref {root_ref} is not a QWidget")
            lines: list[str] = []
            count = self._walk_widget(root, 0, max_depth, lines, skip_hidden)
            return {
                "tree": "\n".join(lines),
                "widget_count": count,
                "generation": self._registry.generation,
            }

        self._registry.clear()
        lines = []
        count = 0

        windows = _visible_top_level_widgets(app)

        # Issue #1: retry once if no visible windows during transition
        if not windows:
            app.processEvents()
            time.sleep(WINDOW_RETRY_DELAY_SEC)
            app.processEvents()
            windows = _visible_top_level_widgets(app)

        for window in windows:
            c = self._walk_widget(window, 0, max_depth, lines, skip_hidden)
            count += c

        # Issue #8: include active popup if not already in top-level widgets
        popup = app.activePopupWidget()
        if popup and popup.isVisible() and popup not in [w for w in app.topLevelWidgets()]:
            count += self._walk_widget(popup, 0, max_depth, lines, skip_hidden)

        return {
            "tree": "\n".join(lines),
            "widget_count": count,
            "generation": self._registry.generation,
        }

    def widget_details(self, ref: str) -> dict:
        """Get detailed properties of a specific widget."""
        obj = self._registry.resolve_or_raise(ref)

        meta = obj.metaObject() if isinstance(obj, QObject) else None
        result: dict[str, Any] = {
            "class": type(obj).__name__,
            "objectName": obj.objectName() if isinstance(obj, QObject) else "",
        }

        if isinstance(obj, QWidget):
            g = obj.geometry()
            result["geometry"] = {
                "x": g.x(),
                "y": g.y(),
                "width": g.width(),
                "height": g.height(),
            }
            result["visible"] = obj.isVisible()
            result["enabled"] = obj.isEnabled()

        if isinstance(obj, QWidget):
            # Layout fields — only available on live widgets
            try:
                hint = obj.sizeHint()
                result["size_hint"] = (hint.width(), hint.height())
            except RuntimeError:
                pass
            try:
                min_hint = obj.minimumSizeHint()
                result["min_size_hint"] = (min_hint.width(), min_hint.height())
            except RuntimeError:
                pass
            try:
                sp = obj.sizePolicy()
                h_name = sp.horizontalPolicy().name
                v_name = sp.verticalPolicy().name
                if isinstance(h_name, bytes):
                    h_name = h_name.decode()
                if isinstance(v_name, bytes):
                    v_name = v_name.decode()
                result["size_policy"] = f"{h_name}x{v_name}"
            except (RuntimeError, AttributeError):
                pass
            layout = obj.layout()
            result["layout"] = type(layout).__name__ if layout is not None else "none"
            try:
                m = obj.contentsMargins()
                result["margins"] = (m.left(), m.top(), m.right(), m.bottom())
            except RuntimeError:
                pass

        if meta is not None:
            result["properties"] = _read_properties(obj)
            # Parent chain
            chain: list[str] = []
            p = obj.parent()
            while p is not None:
                chain.append(f"{type(p).__name__}({p.objectName()})")
                p = p.parent()
            result["parent_chain"] = chain

        # Tree widget items
        QTreeWidget = QtWidgets.QTreeWidget

        if isinstance(obj, QTreeWidget):
            result["items"] = _read_tree_widget_items(obj, self._registry)

        return result

    def find_widget(
        self,
        pattern: str = "",
        class_name: str = "",
        object_name: str = "",
        text: str = "",
        root_ref: str | None = None,
        visible_only: bool = True,
        max_results: int = 20,
    ) -> dict:
        """Search the widget tree for widgets matching criteria.

        At least one of pattern, class_name, object_name, or text must be set.
        Returns refs registered in the current registry (no clear performed).
        """
        if not (pattern or class_name or object_name or text):
            raise ValueError("At least one of pattern, class_name, object_name, or text required")

        app = QApplication.instance()
        if app is None:
            return {"widgets": [], "count": 0}

        if root_ref:
            root = self._registry.resolve_or_raise(root_ref)
            if not isinstance(root, QWidget):
                raise ValueError(f"Ref {root_ref} is not a QWidget")
            search_roots: list[QWidget] = [root]
        elif visible_only:
            search_roots = _visible_top_level_widgets(app)
        else:
            search_roots = list(app.topLevelWidgets())

        pattern_lower = pattern.lower()
        class_lower = class_name.lower()
        object_lower = object_name.lower()
        text_lower = text.lower()

        matches: list[dict] = []

        def _walk(widget: QWidget) -> None:
            if len(matches) >= max_results:
                return
            if visible_only and not widget.isVisible():
                return

            w_class = type(widget).__name__
            w_name = widget.objectName()
            w_text = _safe_text(widget) or ""

            # All explicit filters must match (AND logic)
            ok = True
            if class_name and w_class.lower() != class_lower:
                ok = False
            if ok and object_name and object_lower not in w_name.lower():
                ok = False
            if ok and text and text_lower not in w_text.lower():
                ok = False
            if ok and pattern and not (
                pattern_lower in w_class.lower()
                or pattern_lower in w_name.lower()
                or pattern_lower in w_text.lower()
            ):
                ok = False

            if ok:
                ref = self._registry.register(widget, prefix="w")
                g = widget.geometry()
                matches.append(
                    {
                        "ref": ref,
                        "class": w_class,
                        "objectName": w_name,
                        "text": w_text or None,
                        "geometry": {
                            "x": g.x(),
                            "y": g.y(),
                            "width": g.width(),
                            "height": g.height(),
                        },
                        "visible": widget.isVisible(),
                        "enabled": widget.isEnabled(),
                    }
                )

            for child in widget.children():
                if isinstance(child, QWidget) and len(matches) < max_results:
                    _walk(child)

        for root in search_roots:
            _walk(root)
            if len(matches) >= max_results:
                break

        return {"widgets": matches, "count": len(matches)}

    def list_windows(self, skip_hidden: bool = True) -> dict:
        """List all top-level windows."""
        app = QApplication.instance()
        if app is None:
            return {"windows": []}

        widgets = app.topLevelWidgets()
        if skip_hidden:
            widgets = [w for w in widgets if w.isVisible()]

        windows: list[dict] = []
        for w in widgets:
            try:
                windows.append(
                    {
                        "class": type(w).__name__,
                        "objectName": w.objectName(),
                        "size": f"{w.width()}x{w.height()}",
                        "visible": w.isVisible(),
                    }
                )
            except RuntimeError:
                continue  # C++ object deleted
        return {"windows": windows}

    def object_tree(self, root_ref: str | None = None, max_depth: int = 10) -> dict:
        """Get the full QObject tree (not just visible widgets)."""
        if root_ref:
            # Issue #2: resolve FIRST, then walk WITHOUT clearing
            root = self._registry.resolve_or_raise(root_ref)
            lines: list[str] = []
            count = self._walk_object(root, 0, max_depth, lines)
            return {"tree": "\n".join(lines), "count": count}

        # From QApplication: walk top-level widgets (they aren't QApplication children)
        app = QApplication.instance()
        if app is None:
            return {"tree": "(no QApplication)", "count": 0}

        self._registry.clear()
        lines = []
        ref = self._registry.register(app, prefix="w")
        lines.append(f"- QApplication [ref={ref}]")
        count = 1

        for widget in app.topLevelWidgets():
            try:
                if isinstance(widget, QWidget):
                    count += self._walk_object(widget, 1, max_depth, lines)
            except RuntimeError:
                continue
        return {"tree": "\n".join(lines), "count": count}

    def active_popup(self) -> dict:
        """Check for active popup/modal widgets."""
        app = QApplication.instance()
        if app is None:
            return {"popup": None, "modal": None}

        result: dict[str, Any] = {"popup": None, "modal": None}

        popup = app.activePopupWidget()
        if popup and popup.isVisible():
            result["popup"] = {
                "class": type(popup).__name__,
                "objectName": popup.objectName(),
                "size": f"{popup.width()}x{popup.height()}",
            }

        modal = app.activeModalWidget()
        if modal and modal.isVisible():
            result["modal"] = {
                "class": type(modal).__name__,
                "objectName": modal.objectName(),
                "size": f"{modal.width()}x{modal.height()}",
            }

        return result

    def menu_items(self, ref: str) -> dict:
        """Enumerate actions in a QMenu."""
        QMenu = QtWidgets.QMenu

        obj = self._registry.resolve_or_raise(ref)
        if not isinstance(obj, QMenu):
            raise ValueError(f"Ref {ref} ({type(obj).__name__}) is not a QMenu")

        actions: list[dict[str, Any]] = []
        for action in obj.actions():
            info: dict[str, Any] = {
                "text": action.text(),
                "enabled": action.isEnabled(),
                "separator": action.isSeparator(),
            }
            if action.isCheckable():
                info["checked"] = action.isChecked()
            actions.append(info)

        return {"actions": actions}

    def _walk_widget(
        self,
        widget: QWidget,
        depth: int,
        max_depth: int,
        lines: list[str],
        skip_hidden: bool = False,
    ) -> int:
        """Recursively walk widget tree, building snapshot lines."""
        if depth > max_depth:
            return 0

        ref = self._registry.register(widget, prefix="w")
        cls = type(widget).__name__
        name = widget.objectName()
        indent = "  " * depth

        # Build header
        parts: list[str] = [f"{indent}- {cls}"]
        if name:
            parts.append(f'"{name}"')
        parts.append(f"[ref={ref}]")

        text = _safe_text(widget)
        if text:
            parts.append(f'"{text}"')

        g = widget.geometry()
        parts.append(f"[{g.width()}x{g.height()}]")

        hidden = not widget.isVisible()
        if hidden:
            parts.append("[hidden]")
        if not widget.isEnabled():
            parts.append("[disabled]")

        # Issue #10: checked state
        checker = getattr(widget, "isChecked", None)
        if checker is not None and callable(checker):
            try:
                if checker():
                    parts.append("[checked]")
            except (RuntimeError, TypeError):
                checker = None

        # Tab labels for QTabWidget / QTabBar
        QTabWidget = QtWidgets.QTabWidget
        QTabBar = QtWidgets.QTabBar

        if isinstance(widget, (QTabWidget, QTabBar)):
            tab_labels = []
            for i in range(widget.count()):
                marker = "*" if i == widget.currentIndex() else ""
                tab_labels.append(f"{marker}{widget.tabText(i)}")
            if tab_labels:
                parts.append(f"[tabs: {' | '.join(tab_labels)}]")

        lines.append(" ".join(parts))
        count = 1

        # Issue #9: skip children of hidden containers
        if skip_hidden and hidden:
            return count

        # Tree widget items inline
        QTreeWidget = QtWidgets.QTreeWidget

        if isinstance(widget, QTreeWidget):
            items = _read_tree_widget_items(widget, self._registry)
            for item in items:
                item_indent = "  " * (depth + 1 + item["depth"])
                exp = " [expanded]" if item["expanded"] else ""
                lines.append(
                    f'{item_indent}- QTreeWidgetItem "{item["text"]}" [ref={item["ref"]}]{exp}'
                )

        # Recurse into child widgets
        for child in widget.children():
            if isinstance(child, QWidget):
                count += self._walk_widget(child, depth + 1, max_depth, lines, skip_hidden)

        return count

    def _walk_object(self, obj: QObject, depth: int, max_depth: int, lines: list[str]) -> int:
        """Recursively walk QObject tree (all objects, not just widgets)."""
        if depth > max_depth:
            return 0

        ref = self._registry.register(obj, prefix="w")
        cls = type(obj).__name__
        name = obj.objectName()
        indent = "  " * depth

        parts = [f"{indent}- {cls}"]
        if name:
            parts.append(f'"{name}"')
        parts.append(f"[ref={ref}]")

        lines.append(" ".join(parts))
        count = 1

        for child in obj.children():
            count += self._walk_object(child, depth + 1, max_depth, lines)

        return count
