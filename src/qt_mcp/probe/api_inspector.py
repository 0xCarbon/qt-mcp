"""Signal connection auditor — enumerates signals and their connection state."""

from __future__ import annotations

from typing import Any

from qt_mcp.probe._qt_compat import QtCore
from qt_mcp.probe.ref_registry import RefRegistry

QObject = QtCore.QObject
QMetaMethod = QtCore.QMetaMethod


class ApiInspector:
    """Inspects signal connections on live QObjects."""

    def __init__(self, registry: RefRegistry) -> None:
        self._registry = registry

    def signals(self, ref: str) -> dict[str, Any]:
        """Enumerate all signals on a QObject and report connection state."""
        obj = self._registry.resolve_or_raise(ref)
        if not isinstance(obj, QObject):
            raise ValueError(f"Ref {ref} ({type(obj).__name__}) is not a QObject")

        meta = obj.metaObject()
        result_signals: list[dict[str, Any]] = []

        for i in range(meta.methodCount()):
            method = meta.method(i)
            if method.methodType() != QMetaMethod.MethodType.Signal:
                continue

            signature = method.methodSignature().data().decode()
            name = method.name().data().decode()

            connected = obj.isSignalConnected(method)
            receiver_count = obj.receivers(f"2{signature}")  # SIGNAL() macro prefix

            result_signals.append(
                {
                    "name": name,
                    "signature": signature,
                    "connected": connected,
                    "receiver_count": receiver_count,
                }
            )

        return {
            "class": type(obj).__name__,
            "object_name": obj.objectName(),
            "signals": result_signals,
        }
