"""Widget screenshot capture: QWidget.grab() -> PNG/JPEG -> base64."""

from __future__ import annotations

import base64
import os

from qt_mcp.probe._qt_compat import QtCore, QtWidgets
from qt_mcp.probe.ref_registry import RefRegistry

QBuffer = QtCore.QBuffer
QIODevice = QtCore.QIODevice
Qt = QtCore.Qt
QApplication = QtWidgets.QApplication
QWidget = QtWidgets.QWidget

def _clamp_env(name: str, default: int, lo: int, hi: int) -> int:
    return max(lo, min(int(os.getenv(name, str(default))), hi))


DEFAULT_SCREENSHOT_MAX_WIDTH = _clamp_env("QT_MCP_SCREENSHOT_MAX_WIDTH", 1920, 1, 7680)
DEFAULT_SCREENSHOT_MAX_HEIGHT = _clamp_env("QT_MCP_SCREENSHOT_MAX_HEIGHT", 1080, 1, 4320)
DEFAULT_JPEG_QUALITY = _clamp_env("QT_MCP_JPEG_QUALITY", 80, 1, 100)


class Screenshotter:
    """Captures widget screenshots as base64-encoded images."""

    def __init__(self, registry: RefRegistry) -> None:
        self._registry = registry

    def screenshot(
        self,
        ref: str | None = None,
        full_window: bool = False,
        max_width: int = DEFAULT_SCREENSHOT_MAX_WIDTH,
        max_height: int = DEFAULT_SCREENSHOT_MAX_HEIGHT,
        format: str = "png",
        quality: int = DEFAULT_JPEG_QUALITY,
    ) -> dict:
        """Grab a widget (or full window) as a base64 image."""
        if ref:
            obj = self._registry.resolve_or_raise(ref)
            if not isinstance(obj, QWidget):
                raise ValueError(f"Ref {ref} is not a QWidget")
            widget = obj
        elif full_window:
            app = QApplication.instance()
            if app is None:
                raise ValueError("No QApplication running")
            windows = [w for w in app.topLevelWidgets() if w.isVisible()]
            if not windows:
                raise ValueError("No visible top-level window")
            widget = windows[0]
        else:
            app = QApplication.instance()
            if app is None:
                raise ValueError("No QApplication running")
            widget = app.activeWindow()
            if widget is None:
                windows = [w for w in app.topLevelWidgets() if w.isVisible()]
                if not windows:
                    raise ValueError("No visible window")
                widget = windows[0]

        pixmap = widget.grab()
        if pixmap.isNull():
            raise ValueError("grab() returned null pixmap")

        # Downscale if exceeds max dimensions
        if pixmap.width() > max_width or pixmap.height() > max_height:
            pixmap = pixmap.scaled(
                max_width,
                max_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        fmt = format.upper()
        if fmt not in ("PNG", "JPEG"):
            fmt = "PNG"

        buf = QBuffer()
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        if fmt == "JPEG":
            pixmap.save(buf, "JPEG", quality)
        else:
            pixmap.save(buf, "PNG")
        img_bytes = bytes(buf.data())
        buf.close()

        b64 = base64.b64encode(img_bytes).decode("ascii")
        return {
            "image": b64,
            "width": pixmap.width(),
            "height": pixmap.height(),
            "format": fmt.lower(),
        }
