"""VTK/PyVista scene inspection (optional, graceful degradation if VTK unavailable)."""

from __future__ import annotations

import base64
from typing import Any

from qt_mcp.probe._qt_compat import QtWidgets
from qt_mcp.probe.ref_registry import RefRegistry

QWidget = QtWidgets.QWidget


def _try_import_vtk() -> bool:
    try:
        import vtkmodules  # noqa: F401

        return True
    except ImportError:
        return False


def _invoke(obj: Any, method_name: str) -> Any:
    method = getattr(obj, method_name, None)
    if method is None or not callable(method):
        return None
    return method()


class VtkInspector:
    """Inspects PyVista/VTK render windows embedded in Qt."""

    def __init__(self, registry: RefRegistry) -> None:
        self._registry = registry

    def vtk_scene_info(self, ref: str) -> dict:
        """Get VTK scene state from a widget that wraps a VTK render window."""
        widget = self._resolve(ref)
        render_window = self._get_render_window(widget)

        renderer_collection = _invoke(render_window, "GetRenderers")
        renderer = _invoke(renderer_collection, "GetFirstRenderer")
        if renderer is None:
            return {"error": "No renderer found"}

        # Camera
        camera = _invoke(renderer, "GetActiveCamera")
        camera_info: dict[str, Any] = {}
        if camera:
            camera_info = {
                "position": list(_invoke(camera, "GetPosition") or []),
                "focal_point": list(_invoke(camera, "GetFocalPoint") or []),
                "view_up": list(_invoke(camera, "GetViewUp") or []),
                "clipping_range": list(_invoke(camera, "GetClippingRange") or []),
            }

        # Actors
        actors: list[dict[str, Any]] = []
        actor_collection = _invoke(renderer, "GetActors")
        _invoke(actor_collection, "InitTraversal")
        actor_count = int(_invoke(actor_collection, "GetNumberOfItems") or 0)
        for _ in range(actor_count):
            actor = _invoke(actor_collection, "GetNextActor")
            if actor is None:
                break
            info: dict[str, Any] = {
                "class": type(actor).__name__,
                "visibility": bool(_invoke(actor, "GetVisibility")),
                "bounds": list(_invoke(actor, "GetBounds") or []),
            }
            mapper = _invoke(actor, "GetMapper")
            dataset = _invoke(mapper, "GetInput")
            if mapper and dataset:
                info["points"] = _invoke(dataset, "GetNumberOfPoints")
                info["cells"] = _invoke(dataset, "GetNumberOfCells")
                info["scalar_range"] = list(_invoke(mapper, "GetScalarRange") or [])
            actors.append(info)

        # Background
        bg = list(_invoke(renderer, "GetBackground") or [])

        size = _invoke(render_window, "GetSize") or (0, 0)

        return {
            "camera": camera_info,
            "actors": actors,
            "background": bg,
            "size": list(size),
        }

    def vtk_screenshot(self, ref: str) -> dict:
        """Capture VTK render window to base64 PNG."""
        widget = self._resolve(ref)

        # First, try QWidget.grab() which often works
        pixmap = widget.grab()
        if not pixmap.isNull():
            from qt_mcp.probe._qt_compat import QtCore as _QtC

            QBuffer = _QtC.QBuffer
            QIODevice = _QtC.QIODevice

            buf = QBuffer()
            buf.open(QIODevice.OpenModeFlag.WriteOnly)
            pixmap.save(buf, "PNG")
            png_bytes = bytes(buf.data())
            buf.close()
            b64 = base64.b64encode(png_bytes).decode("ascii")
            return {"image": b64, "width": pixmap.width(), "height": pixmap.height()}

        # Fallback: use vtkWindowToImageFilter
        render_window = self._get_render_window(widget)
        render_window.Render()

        from vtkmodules.vtkIOImage import vtkPNGWriter
        from vtkmodules.vtkRenderingCore import vtkWindowToImageFilter

        w2i = vtkWindowToImageFilter()
        w2i.SetInput(render_window)
        w2i.Update()

        writer = vtkPNGWriter()
        writer.SetInputConnection(w2i.GetOutputPort())
        writer.WriteToMemoryOn()
        writer.Write()

        png_bytes = bytes(writer.GetResult())
        b64 = base64.b64encode(png_bytes).decode("ascii")
        size = render_window.GetSize()
        return {"image": b64, "width": size[0], "height": size[1]}

    def _resolve(self, ref: str) -> QWidget:
        obj = self._registry.resolve(ref)
        if obj is None:
            raise ValueError(f"Ref not found: {ref}")
        if not isinstance(obj, QWidget):
            raise ValueError(f"Ref {ref} is not a QWidget")
        return obj

    def _get_render_window(self, widget: QWidget) -> Any:
        """Extract vtkRenderWindow from a PyVista or VTK Qt widget."""
        # pyvistaqt.QtInteractor
        if hasattr(widget, "GetRenderWindow"):
            return widget.GetRenderWindow()
        # Try finding child with render window
        for child in widget.children():
            if hasattr(child, "GetRenderWindow"):
                return child.GetRenderWindow()
        raise ValueError(f"No VTK render window found in {type(widget).__name__}")
