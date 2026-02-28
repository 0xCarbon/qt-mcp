"""qt-mcp probe: in-process instrumentation for Qt/PySide6 applications.

Usage::

    from qt_mcp.probe import install
    install()  # or install(port=<custom port>)
"""

from __future__ import annotations

import collections
import time

from qt_mcp.probe._qt_compat import QtCore, QtWidgets
from qt_mcp.probe.api_inspector import ApiInspector
from qt_mcp.probe.interactor import Interactor
from qt_mcp.probe.introspector import Introspector
from qt_mcp.probe.layout_inspector import LayoutInspector
from qt_mcp.probe.ref_registry import RefRegistry
from qt_mcp.probe.rpc_server import JsonRpcServer
from qt_mcp.probe.scene_inspector import SceneInspector
from qt_mcp.probe.screenshotter import Screenshotter
from qt_mcp.probe.thread_inspector import ThreadInspector
from qt_mcp.probe.vtk_inspector import VtkInspector

QObject = QtCore.QObject
QThread = QtCore.QThread
QApplication = QtWidgets.QApplication

DEFAULT_PORT = 9142
PROBE_OBJECT_NAME = "qt_mcp_probe"
MESSAGE_BUFFER_MAX = 500

# Map QtMsgType enum values to string level names
_MSG_TYPE_MAP = {
    QtCore.QtMsgType.QtDebugMsg: "debug",
    QtCore.QtMsgType.QtInfoMsg: "info",
    QtCore.QtMsgType.QtWarningMsg: "warning",
    QtCore.QtMsgType.QtCriticalMsg: "critical",
    QtCore.QtMsgType.QtFatalMsg: "critical",
}

_LEVEL_SEVERITY = {"debug": 0, "info": 1, "warning": 2, "critical": 3}


class Probe(QObject):
    """Central coordinator: JSON-RPC server dispatching to capability modules."""

    def __init__(self, parent: QObject, port: int = DEFAULT_PORT) -> None:
        super().__init__(parent)
        self.setObjectName(PROBE_OBJECT_NAME)

        self._registry = RefRegistry()
        self._introspector = Introspector(self._registry)
        self._interactor = Interactor(self._registry)
        self._screenshotter = Screenshotter(self._registry)
        self._scene_inspector = SceneInspector(self._registry)
        self._vtk_inspector = VtkInspector(self._registry)
        self._thread_inspector = ThreadInspector()
        self._layout_inspector = LayoutInspector(self._registry)
        self._api_inspector = ApiInspector(self._registry)

        # Qt message capture ring buffer
        self._messages: collections.deque[dict] = collections.deque(maxlen=MESSAGE_BUFFER_MAX)
        self._previous_handler = QtCore.qInstallMessageHandler(self._message_handler)

        self._rpc = JsonRpcServer(self._dispatch, parent=self)
        self._port = port

    def _message_handler(self, msg_type, context, message: str) -> None:
        """Callback for qInstallMessageHandler — captures Qt internal warnings."""
        level = _MSG_TYPE_MAP.get(msg_type, "warning")
        self._messages.append(
            {
                "level": level,
                "message": message,
                "timestamp": time.time(),
            }
        )
        # Chain to previous handler so messages still reach stderr
        if self._previous_handler is not None:
            self._previous_handler(msg_type, context, message)

    def _get_messages(self, level: str = "info") -> dict:
        """Return captured Qt messages at or above the given severity level, then clear."""
        min_severity = _LEVEL_SEVERITY.get(level, 1)
        filtered = [m for m in self._messages if _LEVEL_SEVERITY.get(m["level"], 0) >= min_severity]
        self._messages.clear()
        return {"messages": filtered, "count": len(filtered)}

    def start(self) -> bool:
        return self._rpc.start(self._port)

    def port(self) -> int:
        return self._rpc.port()

    def _dispatch(self, method: str, params: dict) -> object:
        if method == "ping":
            return "pong"
        if method == "snapshot":
            return self._introspector.snapshot(**params)
        if method == "screenshot":
            return self._screenshotter.screenshot(**params)
        if method == "widget_details":
            return self._introspector.widget_details(**params)
        if method == "click":
            return self._interactor.click(**params)
        if method == "type_text":
            return self._interactor.type_text(**params)
        if method == "key_press":
            return self._interactor.key_press(**params)
        if method == "set_property":
            return self._interactor.set_property(**params)
        if method == "invoke_slot":
            return self._interactor.invoke_slot(**params)
        if method == "wait_for":
            return self._interactor.wait_for(**params)
        if method == "get_text":
            return self._interactor.get_text(**params)
        if method == "trigger_action":
            return self._interactor.trigger_action(**params)
        if method == "list_windows":
            return self._introspector.list_windows(**params)
        if method == "object_tree":
            return self._introspector.object_tree(**params)
        if method == "active_popup":
            return self._introspector.active_popup()
        if method == "menu_items":
            return self._introspector.menu_items(**params)
        if method == "scene_snapshot":
            return self._scene_inspector.scene_snapshot(**params)
        if method == "scene_item_details":
            return self._scene_inspector.scene_item_details(**params)
        if method == "vtk_scene_info":
            return self._vtk_inspector.vtk_scene_info(**params)
        if method == "vtk_screenshot":
            return self._vtk_inspector.vtk_screenshot(**params)
        if method == "qt_messages":
            return self._get_messages(**params)
        if method == "thread_check":
            return self._thread_inspector.thread_check()
        if method == "signals":
            return self._api_inspector.signals(**params)
        if method == "layout_check":
            return self._layout_inspector.layout_check()
        if method == "find_widget":
            return self._introspector.find_widget(**params)
        if method == "batch":
            return self._batch(**params)
        raise ValueError(f"Unknown method: {method}")

    def _batch(self, steps: list) -> dict:
        """Execute multiple RPC methods sequentially in one round trip."""
        results = []
        for i, step in enumerate(steps):
            method = step.get("method")
            params = step.get("params") or {}
            wait_ms = step.get("wait_ms", 0)

            if not method:
                results.append({"ok": False, "error": "Missing 'method' in step"})
                return {"results": results, "completed": i, "failed_at": i}

            if method == "batch":
                results.append({"ok": False, "error": "Nested batch not allowed"})
                return {"results": results, "completed": i, "failed_at": i}

            try:
                if method == "wait":
                    ms = int(params.get("ms", 0))
                    _process_events_for(ms)
                    results.append({"ok": True, "result": {"waited_ms": ms}})
                else:
                    results.append({"ok": True, "result": self._dispatch(method, params)})
            except Exception as exc:
                results.append({"ok": False, "error": str(exc)})
                return {"results": results, "completed": i, "failed_at": i}

            if wait_ms > 0:
                _process_events_for(int(wait_ms))

        return {"results": results, "completed": len(steps), "failed_at": None}


def _process_events_for(ms: int) -> None:
    """Process Qt events for the given number of milliseconds."""
    app = QApplication.instance()
    deadline = time.monotonic() + ms / 1000.0
    while time.monotonic() < deadline:
        if app:
            app.processEvents()
        remaining = deadline - time.monotonic()
        if remaining > 0:
            QThread.msleep(min(50, max(1, int(remaining * 1000))))


def install(port: int = DEFAULT_PORT) -> Probe | None:
    """Attach probe to the running QApplication.

    Idempotent: returns existing probe if already installed.
    Returns None if no QApplication is running or if the server fails to start.
    """
    app = QApplication.instance()
    if app is None:
        return None

    for child in app.children():
        if isinstance(child, Probe) or (
            isinstance(child, QObject) and child.objectName() == PROBE_OBJECT_NAME
        ):
            return child  # type: ignore[return-value]

    probe = Probe(app, port)
    if not probe.start():
        probe.setParent(None)
        probe.deleteLater()
        return None
    return probe


def _auto_hook() -> None:
    """If QT_MCP_PROBE=1, patch QApplication to auto-install probe on creation."""
    import os as _os

    if _os.environ.get("QT_MCP_PROBE") != "1":
        return

    hook_flag = "_qt_mcp_probe_hooked"
    if getattr(QApplication, hook_flag, False):
        return
    setattr(QApplication, hook_flag, True)

    default_port = int(_os.environ.get("QT_MCP_PORT", str(DEFAULT_PORT)))
    _original_init = QApplication.__init__

    def _patched_init(self, *args, **kwargs):
        _original_init(self, *args, **kwargs)
        port = int(_os.environ.get("QT_MCP_PORT", str(DEFAULT_PORT)))
        install(port=port)

    QApplication.__init__ = _patched_init
    if QApplication.instance() is not None:
        install(port=default_port)


_auto_hook()
