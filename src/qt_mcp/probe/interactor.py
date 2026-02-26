"""Interaction primitives: click, type, key press, property set, slot invoke, wait."""

from __future__ import annotations

import time
from typing import Any

from qt_mcp.probe._qt_compat import QtCore, QtGui, QtWidgets
from qt_mcp.probe.ref_registry import RefRegistry

Q_ARG = QtCore.Q_ARG
QEvent = QtCore.QEvent
QMetaObject = QtCore.QMetaObject
QObject = QtCore.QObject
QPointF = QtCore.QPointF
Qt = QtCore.Qt
QThread = QtCore.QThread
QKeyEvent = QtGui.QKeyEvent
QMouseEvent = QtGui.QMouseEvent
QApplication = QtWidgets.QApplication
QWidget = QtWidgets.QWidget

DEFAULT_WAIT_TIMEOUT_MS = 5000
WAIT_POLL_INTERVAL_MS = 50

_BUTTON_MAP = {
    "left": Qt.MouseButton.LeftButton,
    "right": Qt.MouseButton.RightButton,
    "middle": Qt.MouseButton.MiddleButton,
}

_MODIFIER_MAP = {
    "shift": Qt.KeyboardModifier.ShiftModifier,
    "ctrl": Qt.KeyboardModifier.ControlModifier,
    "alt": Qt.KeyboardModifier.AltModifier,
    "meta": Qt.KeyboardModifier.MetaModifier,
}

_KEY_MAP: dict[str, int] = {
    "return": Qt.Key.Key_Return,
    "enter": Qt.Key.Key_Return,
    "escape": Qt.Key.Key_Escape,
    "esc": Qt.Key.Key_Escape,
    "tab": Qt.Key.Key_Tab,
    "backspace": Qt.Key.Key_Backspace,
    "delete": Qt.Key.Key_Delete,
    "space": Qt.Key.Key_Space,
    "up": Qt.Key.Key_Up,
    "down": Qt.Key.Key_Down,
    "left": Qt.Key.Key_Left,
    "right": Qt.Key.Key_Right,
    "home": Qt.Key.Key_Home,
    "end": Qt.Key.Key_End,
    "pageup": Qt.Key.Key_PageUp,
    "pagedown": Qt.Key.Key_PageDown,
    "f1": Qt.Key.Key_F1,
    "f2": Qt.Key.Key_F2,
    "f3": Qt.Key.Key_F3,
    "f4": Qt.Key.Key_F4,
    "f5": Qt.Key.Key_F5,
    "f6": Qt.Key.Key_F6,
    "f7": Qt.Key.Key_F7,
    "f8": Qt.Key.Key_F8,
    "f9": Qt.Key.Key_F9,
    "f10": Qt.Key.Key_F10,
    "f11": Qt.Key.Key_F11,
    "f12": Qt.Key.Key_F12,
}


def _parse_modifiers(modifiers: list[str] | None) -> Qt.KeyboardModifier:
    result = Qt.KeyboardModifier.NoModifier
    for m in modifiers or []:
        mod = _MODIFIER_MAP.get(m.lower())
        if mod:
            result = result | mod
    return result


def _parse_key(key_str: str) -> tuple[int, Qt.KeyboardModifier, str]:
    """Parse key string like 'Ctrl+S' into (qt_key, modifiers, text)."""
    parts = key_str.split("+")
    modifiers = Qt.KeyboardModifier.NoModifier
    key_part = parts[-1]
    for mod_str in parts[:-1]:
        mod = _MODIFIER_MAP.get(mod_str.lower())
        if mod:
            modifiers = modifiers | mod

    key_lower = key_part.lower()
    if key_lower in _KEY_MAP:
        return _KEY_MAP[key_lower], modifiers, ""

    # Single character
    if len(key_part) == 1:
        char = key_part
        qt_key = ord(char.upper())
        return qt_key, modifiers, char

    return 0, modifiers, key_part


def _find_widget_by_name(name: str) -> QWidget | None:
    """Find a visible widget by objectName across all top-level widgets."""
    app = QApplication.instance()
    if app is None:
        return None
    for tlw in app.topLevelWidgets():
        if tlw.objectName() == name and tlw.isVisible():
            return tlw
        found = tlw.findChild(QWidget, name)
        if found and found.isVisible():
            return found
    return None


class Interactor:
    """Synthesizes Qt events for widget interaction."""

    def __init__(self, registry: RefRegistry) -> None:
        self._registry = registry

    def click(
        self,
        ref: str,
        button: str = "left",
        modifiers: list[str] | None = None,
        position: list[int] | None = None,
    ) -> dict:
        """Synthesize a mouse click on a widget."""
        widget = self._resolve_widget(ref)

        qt_button = _BUTTON_MAP.get(button, Qt.MouseButton.LeftButton)
        qt_mods = _parse_modifiers(modifiers)

        if position:
            pos = QPointF(float(position[0]), float(position[1]))
        else:
            pos = QPointF(widget.rect().center())

        global_pos = QPointF(widget.mapToGlobal(pos.toPoint()))

        press = QMouseEvent(
            QEvent.Type.MouseButtonPress, pos, global_pos, qt_button, qt_button, qt_mods
        )
        release = QMouseEvent(
            QEvent.Type.MouseButtonRelease,
            pos,
            global_pos,
            qt_button,
            Qt.MouseButton.NoButton,
            qt_mods,
        )

        QApplication.sendEvent(widget, press)
        QApplication.sendEvent(widget, release)
        QApplication.processEvents()

        return {"ok": True}

    def type_text(
        self, ref: str, text: str, clear_first: bool = False, use_clipboard: bool = False
    ) -> dict:
        """Type text into a widget by sending key events or via clipboard paste.

        Args:
            ref: Widget ref.
            text: Text to insert.
            clear_first: Select-all + delete before inserting.
            use_clipboard: Paste via Ctrl+V instead of character-by-character key events.
                Use this for multi-line text to prevent each newline from acting as
                a submit (e.g. in IPython/terminal widgets).
        """
        widget = self._resolve_widget(ref)
        widget.setFocus()
        QApplication.processEvents()

        if clear_first:
            ctrl = Qt.KeyboardModifier.ControlModifier
            no_mod = Qt.KeyboardModifier.NoModifier
            select_all = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_A, ctrl, "")
            QApplication.sendEvent(widget, select_all)
            delete = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Delete, no_mod, "")
            QApplication.sendEvent(widget, delete)
            QApplication.processEvents()

        if use_clipboard:
            clipboard = QApplication.clipboard()
            previous = clipboard.text()
            clipboard.setText(text)
            ctrl = Qt.KeyboardModifier.ControlModifier
            paste = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_V, ctrl, "")
            paste_rel = QKeyEvent(QEvent.Type.KeyRelease, Qt.Key.Key_V, ctrl, "")
            QApplication.sendEvent(widget, paste)
            QApplication.sendEvent(widget, paste_rel)
            QApplication.processEvents()
            clipboard.setText(previous)  # restore previous clipboard content
        else:
            for char in text:
                key_press = QKeyEvent(QEvent.Type.KeyPress, 0, Qt.KeyboardModifier.NoModifier, char)
                key_release = QKeyEvent(
                    QEvent.Type.KeyRelease, 0, Qt.KeyboardModifier.NoModifier, char
                )
                QApplication.sendEvent(widget, key_press)
                QApplication.sendEvent(widget, key_release)

        QApplication.processEvents()
        return {"ok": True}

    def key_press(self, key: str, ref: str | None = None) -> dict:
        """Send a key event to a widget or the focused widget."""
        if ref:
            widget = self._resolve_widget(ref)
        else:
            widget = QApplication.focusWidget()
            if widget is None:
                raise ValueError("No focused widget and no ref provided")

        qt_key, qt_mods, text = _parse_key(key)
        press = QKeyEvent(QEvent.Type.KeyPress, qt_key, qt_mods, text)
        release = QKeyEvent(QEvent.Type.KeyRelease, qt_key, qt_mods, text)
        QApplication.sendEvent(widget, press)
        QApplication.sendEvent(widget, release)
        QApplication.processEvents()

        return {"ok": True}

    def set_property(self, ref: str, property_name: str, value: Any) -> dict:
        """Set a Qt property on a QObject."""
        obj = self._registry.resolve(ref)
        if obj is None:
            raise ValueError(f"Ref not found: {ref}")
        if not isinstance(obj, QObject):
            raise ValueError(f"Ref {ref} is not a QObject")

        old_value = obj.property(property_name)
        ok = obj.setProperty(property_name, value)
        QApplication.processEvents()
        return {"ok": ok, "old_value": repr(old_value)}

    def invoke_slot(self, ref: str, method_name: str, args: list | None = None) -> dict:
        """Invoke a slot/method on a QObject using QMetaObject.invokeMethod."""
        obj = self._registry.resolve(ref)
        if obj is None:
            raise ValueError(f"Ref not found: {ref}")
        if not isinstance(obj, QObject):
            raise ValueError(f"Ref {ref} is not a QObject")

        qt_args = [Q_ARG(type(value), value) for value in (args or [])]
        ok = QMetaObject.invokeMethod(obj, method_name, *qt_args)
        QApplication.processEvents()
        return {"ok": ok}

    def wait_for(
        self,
        condition: str,
        timeout_ms: int = DEFAULT_WAIT_TIMEOUT_MS,
        object_name: str | None = None,
        ref: str | None = None,
        property_name: str | None = None,
        value: Any = None,
    ) -> dict:
        """Poll for a UI condition within the Qt event loop."""
        app = QApplication.instance()
        if app is None:
            raise ValueError("No QApplication running")

        start = time.monotonic()
        deadline = start + timeout_ms / 1000.0

        if condition == "widget_visible":
            if not object_name:
                raise ValueError("object_name required for widget_visible condition")
            while time.monotonic() < deadline:
                app.processEvents()
                if _find_widget_by_name(object_name):
                    elapsed = int((time.monotonic() - start) * 1000)
                    return {"ok": True, "elapsed_ms": elapsed}
                QThread.msleep(WAIT_POLL_INTERVAL_MS)
                app.processEvents()

        elif condition == "window_count_changed":
            initial = len(app.topLevelWidgets())
            while time.monotonic() < deadline:
                app.processEvents()
                if len(app.topLevelWidgets()) != initial:
                    elapsed = int((time.monotonic() - start) * 1000)
                    return {"ok": True, "elapsed_ms": elapsed}
                QThread.msleep(WAIT_POLL_INTERVAL_MS)
                app.processEvents()

        elif condition == "property_equals":
            if not ref or not property_name:
                raise ValueError("ref and property_name required for property_equals condition")
            obj = self._registry.resolve(ref)
            if obj is None:
                raise ValueError(f"Ref not found: {ref}")
            if not isinstance(obj, QObject):
                raise ValueError(f"Ref {ref} is not a QObject")
            while time.monotonic() < deadline:
                app.processEvents()
                try:
                    current = obj.property(property_name)
                    if current == value:
                        elapsed = int((time.monotonic() - start) * 1000)
                        return {"ok": True, "elapsed_ms": elapsed}
                except (RuntimeError, TypeError):
                    if not self._registry.resolve(ref):
                        raise ValueError(f"Ref not found: {ref}") from None
                QThread.msleep(WAIT_POLL_INTERVAL_MS)
                app.processEvents()

        else:
            raise ValueError(f"Unknown condition: {condition}")

        raise TimeoutError(f"Timed out after {timeout_ms}ms waiting for condition: {condition}")

    def get_text(self, ref: str) -> dict:
        """Extract text content from a text-bearing widget."""
        obj = self._registry.resolve(ref)
        if obj is None:
            raise ValueError(f"Ref not found: {ref}")

        text = None
        document = None
        if hasattr(obj, "toPlainText"):
            text = obj.toPlainText()
        elif hasattr(obj, "text") and callable(obj.text):
            text = obj.text()
        elif hasattr(obj, "currentText") and callable(obj.currentText):
            text = obj.currentText()
        elif hasattr(obj, "document"):
            document = obj.document()
            if document is not None and hasattr(document, "toPlainText"):
                text = document.toPlainText()

        if text is None:
            raise ValueError(f"Widget {type(obj).__name__} does not support text extraction")

        text_value = str(text)
        result: dict[str, Any] = {"text": text_value, "length": len(text_value)}

        if document is None and hasattr(obj, "document"):
            document = obj.document()

        if document is not None and hasattr(document, "lineCount"):
            result["line_count"] = document.lineCount()
        elif document is not None and hasattr(document, "blockCount"):
            result["line_count"] = document.blockCount()
        else:
            result["line_count"] = text_value.count("\n") + 1
        if hasattr(obj, "isReadOnly"):
            result["read_only"] = obj.isReadOnly()
        return result

    def trigger_action(
        self,
        ref: str,
        action_text: str | None = None,
        action_index: int | None = None,
    ) -> dict:
        """Trigger a QAction by text or index from any widget with actions()."""
        obj = self._registry.resolve(ref)
        if obj is None:
            raise ValueError(f"Ref not found: {ref}")
        if not hasattr(obj, "actions"):
            raise ValueError(f"Widget {type(obj).__name__} has no actions()")

        actions = obj.actions()
        if not actions:
            raise ValueError("Widget has no actions")

        if (action_text is None) == (action_index is None):
            raise ValueError("Provide exactly one of action_text or action_index")

        target = None
        if action_index is not None:
            if action_index < 0 or action_index >= len(actions):
                raise ValueError(
                    f"action_index {action_index} out of range (0..{len(actions) - 1})"
                )
            target = actions[action_index]
        elif action_text is not None:
            clean = action_text.replace("&", "").strip()
            for action in actions:
                if action.text().replace("&", "").strip() == clean:
                    target = action
                    break
            if target is None:
                available = [a.text() for a in actions if not a.isSeparator()]
                raise ValueError(f"No action matching '{action_text}'. Available: {available}")
        if target.isSeparator():
            raise ValueError("Cannot trigger a separator")
        if not target.isEnabled():
            raise ValueError(f"Action '{target.text()}' is disabled")

        target.trigger()
        QApplication.processEvents()
        return {"ok": True, "action_text": target.text()}

    def _resolve_widget(self, ref: str) -> QWidget:
        obj = self._registry.resolve(ref)
        if obj is None:
            raise ValueError(f"Widget ref not found: {ref}")
        if not isinstance(obj, QWidget):
            raise ValueError(f"Ref {ref} ({type(obj).__name__}) is not a QWidget")
        return obj
