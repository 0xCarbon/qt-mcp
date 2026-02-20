"""Layout health diagnostics — detects sizing and layout issues in the widget tree."""

from __future__ import annotations

from typing import Any

from qt_mcp.probe._qt_compat import QtWidgets
from qt_mcp.probe.ref_registry import RefRegistry

QApplication = QtWidgets.QApplication
QWidget = QtWidgets.QWidget


def _safe_text(widget: QWidget) -> str | None:
    """Try to read displayable text from a widget."""
    for attr in ("text", "toPlainText", "title"):
        fn = getattr(widget, attr, None)
        if fn is not None and callable(fn):
            try:
                val = fn()
                if isinstance(val, str) and val:
                    return val
            except (RuntimeError, TypeError):
                continue
    return None


class LayoutInspector:
    """Walks visible widgets and reports layout issues."""

    def __init__(self, registry: RefRegistry) -> None:
        self._registry = registry

    def layout_check(self) -> dict[str, Any]:
        app = QApplication.instance()
        if app is None:
            return {"issues": [], "scanned": 0}

        issues: list[dict[str, Any]] = []
        scanned = 0

        for window in app.topLevelWidgets():
            if not window.isVisible():
                continue
            scanned += self._check_widget(window, issues)

        return {"issues": issues, "scanned": scanned}

    def _check_widget(self, widget: QWidget, issues: list[dict[str, Any]]) -> int:
        """Check a single widget and recurse into children. Returns count of scanned widgets."""
        try:
            if not widget.isVisible():
                return 0
        except RuntimeError:
            return 0

        scanned = 1
        ref = self._registry.register(widget, prefix="w")
        cls = type(widget).__name__
        name = widget.objectName()

        g = widget.geometry()
        w, h = g.width(), g.height()

        # Zero-size visible widget
        if w == 0 and h == 0:
            issues.append(
                {
                    "type": "zero_size",
                    "ref": ref,
                    "widget_class": cls,
                    "object_name": name,
                    "severity": "error",
                    "detail": "Visible widget has 0x0 geometry",
                }
            )

        # No layout manager but has visible widget children
        child_widgets = [c for c in widget.children() if isinstance(c, QWidget)]
        visible_children = []
        for c in child_widgets:
            try:
                if c.isVisible():
                    visible_children.append(c)
            except RuntimeError:
                continue
        if visible_children and widget.layout() is None:
            issues.append(
                {
                    "type": "no_layout",
                    "ref": ref,
                    "widget_class": cls,
                    "object_name": name,
                    "severity": "warning",
                    "detail": f"Has {len(visible_children)} visible children but no layout manager",
                }
            )

        # Smaller than size hint
        try:
            hint = widget.sizeHint()
            if hint.isValid() and (w < hint.width() or h < hint.height()):
                issues.append(
                    {
                        "type": "smaller_than_hint",
                        "ref": ref,
                        "widget_class": cls,
                        "object_name": name,
                        "severity": "warning",
                        "detail": (
                            f"Size {w}x{h} is smaller than sizeHint {hint.width()}x{hint.height()}"
                        ),
                    }
                )
        except RuntimeError:
            pass

        # Text truncation
        text = _safe_text(widget)
        if text and w > 0:
            try:
                fm = widget.fontMetrics()
                text_width = fm.horizontalAdvance(text)
                if text_width > w:
                    issues.append(
                        {
                            "type": "text_truncated",
                            "ref": ref,
                            "widget_class": cls,
                            "object_name": name,
                            "severity": "warning",
                            "detail": (f"Text needs {text_width}px but widget is only {w}px wide"),
                        }
                    )
            except (RuntimeError, AttributeError):
                pass

        # Overlapping siblings
        if len(visible_children) > 1:
            for i, a in enumerate(visible_children):
                for b in visible_children[i + 1 :]:
                    try:
                        ga = a.geometry()
                        gb = b.geometry()
                        if ga.intersects(gb):
                            ref_a = self._registry.register(a, prefix="w")
                            ref_b = self._registry.register(b, prefix="w")
                            issues.append(
                                {
                                    "type": "overlapping_siblings",
                                    "ref": ref_a,
                                    "widget_class": type(a).__name__,
                                    "object_name": a.objectName(),
                                    "severity": "info",
                                    "detail": (
                                        f"Overlaps with {type(b).__name__} "
                                        f'"{b.objectName()}" [ref={ref_b}]'
                                    ),
                                }
                            )
                    except RuntimeError:
                        continue

        # Recurse
        for child in child_widgets:
            scanned += self._check_widget(child, issues)

        return scanned
