"""Thread affinity inspector — detects QObjects/QWidgets on wrong threads."""

from __future__ import annotations

from typing import Any

from qt_mcp.probe._qt_compat import QtCore, QtWidgets

QObject = QtCore.QObject
QThread = QtCore.QThread
QApplication = QtWidgets.QApplication
QWidget = QtWidgets.QWidget


class ThreadInspector:
    """Walks the QObject tree and reports thread affinity information."""

    def thread_check(self) -> dict[str, Any]:
        app = QApplication.instance()
        if app is None:
            return {
                "gui_thread": None,
                "threads": [],
                "warnings": [],
                "qthreads": [],
            }

        gui_thread = app.thread()

        # Collect all QObjects by walking top-level widgets + app children
        all_objects: list[QObject] = []
        for widget in app.topLevelWidgets():
            self._collect_objects(widget, all_objects)
        for child in app.children():
            self._collect_objects(child, all_objects)

        # Group by thread (use Python id of QThread object as key)
        thread_map: dict[int, dict[str, Any]] = {}
        warnings: list[dict[str, str]] = []
        qthreads: list[dict[str, Any]] = []

        for obj in all_objects:
            try:
                obj_thread = obj.thread()
                if obj_thread is None:
                    continue
                tid = id(obj_thread)
            except RuntimeError:
                continue  # C++ object deleted

            if tid not in thread_map:
                is_gui = obj_thread is gui_thread
                thread_name = obj_thread.objectName() or ("main" if is_gui else f"thread-{tid}")
                thread_map[tid] = {
                    "name": thread_name,
                    "id": tid,
                    "object_count": 0,
                    "widget_count": 0,
                    "_thread": obj_thread,
                }

            thread_map[tid]["object_count"] += 1
            if isinstance(obj, QWidget):
                thread_map[tid]["widget_count"] += 1
                # Flag widgets on non-GUI threads
                if obj_thread is not gui_thread:
                    try:
                        warnings.append(
                            {
                                "class": type(obj).__name__,
                                "object_name": obj.objectName(),
                                "thread_name": thread_map[tid]["name"],
                            }
                        )
                    except RuntimeError:
                        continue

            # Track QThread instances
            if isinstance(obj, QThread):
                try:
                    qthreads.append(
                        {
                            "object_name": obj.objectName(),
                            "running": obj.isRunning(),
                            "finished": obj.isFinished(),
                        }
                    )
                except RuntimeError:
                    continue

        # Strip internal _thread refs before returning
        threads_out = [{k: v for k, v in t.items() if k != "_thread"} for t in thread_map.values()]

        return {
            "gui_thread": gui_thread.objectName() or "main",
            "threads": threads_out,
            "warnings": warnings,
            "qthreads": qthreads,
        }

    def _collect_objects(self, obj: QObject, result: list[QObject]) -> None:
        """Recursively collect all QObjects in the tree."""
        try:
            result.append(obj)
            for child in obj.children():
                self._collect_objects(child, result)
        except RuntimeError:
            pass  # C++ object deleted
