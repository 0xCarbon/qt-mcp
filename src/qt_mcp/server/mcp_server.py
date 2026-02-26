"""MCP server that exposes Qt probe capabilities as MCP tools."""

from __future__ import annotations

import os

from mcp.server.fastmcp import FastMCP
from mcp.types import ImageContent, TextContent

from qt_mcp.server.probe_client import DEFAULT_PROBE_PORT, ProbeClient

DEFAULT_SNAPSHOT_DEPTH = 10
DEFAULT_SCREENSHOT_MAX_WIDTH = 1920
DEFAULT_SCREENSHOT_MAX_HEIGHT = 1080
DEFAULT_SCREENSHOT_FORMAT = "png"
DEFAULT_JPEG_QUALITY = 80
DEFAULT_WAIT_TIMEOUT_MS = 5000
MAX_TEXT_PREVIEW_CHARS = 5000

_HOST = os.getenv("QT_MCP_HOST", "localhost")
_PORT = int(os.getenv("QT_MCP_PORT", str(DEFAULT_PROBE_PORT)))

mcp = FastMCP(
    "qt-mcp",
    instructions=(
        "Qt/PySide6 desktop application inspection and interaction.\n"
        "- qt_find_widget: search for widgets by class/name/text — prefer this over qt_snapshot "
        "when you know what you're looking for. Returns refs immediately usable with other tools.\n"
        "- qt_snapshot: full widget tree when you need to understand overall structure or discover "
        "unknown widget hierarchies.\n"
        "- qt_batch: chain multiple operations (click, type, key_press, wait, snapshot, "
        "find_widget...) in a single round trip — use this instead of separate tool calls.\n"
        "- qt_screenshot: ONLY for visual content verification (rendered plots, images, custom "
        "drawing). Never use it to check widget state — qt_snapshot and qt_get_text are faster "
        "and cheaper for that.\n"
        "- qt_type with use_clipboard=True for multi-line text (prevents newlines from submitting "
        "each line as a command in console widgets)."
    ),
)

_client = ProbeClient(host=_HOST, port=_PORT)


async def _ensure_connected() -> ProbeClient:
    if not _client.connected:
        await _client.connect()
    return _client


# --- Snapshot & Navigation ---


@mcp.tool()
async def qt_snapshot(
    max_depth: int = DEFAULT_SNAPSHOT_DEPTH,
    root_ref: str | None = None,
    skip_hidden: bool = False,
) -> str:
    """Capture the full Qt widget tree as a structured accessibility-like snapshot.

    Returns a YAML-like text tree with widget types, object names, text content,
    geometry, visibility, enabled state, and interaction refs (w1, w2, ...).
    Use the refs to interact with specific widgets via other tools.
    """
    client = await _ensure_connected()
    params = {"max_depth": max_depth}
    if root_ref:
        params["root_ref"] = root_ref
    if skip_hidden:
        params["skip_hidden"] = skip_hidden
    result = await client.call("snapshot", params)
    tree = result.get("tree", "")
    count = result.get("widget_count", 0)
    gen = result.get("generation", 0)
    return f"Widgets: {count} (generation {gen})\n\n{tree}"


@mcp.tool()
async def qt_find_widget(
    pattern: str = "",
    class_name: str = "",
    object_name: str = "",
    text: str = "",
    root_ref: str | None = None,
    visible_only: bool = True,
    max_results: int = 20,
) -> str:
    """Search the widget tree for widgets matching criteria. Prefer over qt_snapshot.

    Registers found widgets in the ref registry — returned refs are immediately
    usable with qt_click, qt_type, qt_get_text, etc.

    Args:
        pattern: Case-insensitive substring matched against class name, objectName,
            or text content (OR logic across fields).
        class_name: Exact class name (e.g. 'QLineEdit', 'QPushButton', 'ControlWidget').
        object_name: Substring match on objectName.
        text: Substring match on widget text/label content.
        root_ref: Restrict search to subtree of this widget.
        visible_only: Only return visible widgets (default True).
        max_results: Cap on results returned (default 20).

    At least one of pattern, class_name, object_name, or text must be provided.
    """
    client = await _ensure_connected()
    params: dict = {
        "pattern": pattern,
        "class_name": class_name,
        "object_name": object_name,
        "text": text,
        "visible_only": visible_only,
        "max_results": max_results,
    }
    if root_ref:
        params["root_ref"] = root_ref
    result = await client.call("find_widget", params)

    widgets = result.get("widgets", [])
    count = result.get("count", 0)
    if not widgets:
        return "No widgets found matching criteria."

    lines = [f"Found {count} widget(s):"]
    for w in widgets:
        g = w.get("geometry", {})
        size = f"{g.get('width', 0)}x{g.get('height', 0)}"
        name = f' "{w["objectName"]}"' if w.get("objectName") else ""
        text_val = f' text="{w["text"]}"' if w.get("text") else ""
        flags = []
        if not w.get("visible", True):
            flags.append("hidden")
        if not w.get("enabled", True):
            flags.append("disabled")
        flag_str = f" [{', '.join(flags)}]" if flags else ""
        lines.append(f'  - {w["class"]}{name} [ref={w["ref"]}] {size}{text_val}{flag_str}')
    return "\n".join(lines)


@mcp.tool()
async def qt_screenshot(
    ref: str | None = None,
    full_window: bool = False,
    max_width: int = DEFAULT_SCREENSHOT_MAX_WIDTH,
    max_height: int = DEFAULT_SCREENSHOT_MAX_HEIGHT,
    format: str = DEFAULT_SCREENSHOT_FORMAT,
    quality: int = DEFAULT_JPEG_QUALITY,
) -> list:
    """Take a screenshot of the entire window or a specific widget.

    Args:
        ref: Widget ref from qt_snapshot (e.g., 'w5'). If omitted, captures active window.
        full_window: If True, captures the first visible top-level window.
        max_width: Max width before downscaling (default 1920).
        max_height: Max height before downscaling (default 1080).
        format: Image format - 'png' or 'jpeg' (default 'png').
        quality: JPEG quality 1-100 (default 80, ignored for PNG).

    Returns a base64-encoded PNG image.
    """
    client = await _ensure_connected()
    params = {
        "max_width": max_width,
        "max_height": max_height,
        "format": format,
        "quality": quality,
    }
    if ref:
        params["ref"] = ref
    if full_window:
        params["full_window"] = full_window
    result = await client.call("screenshot", params)
    fmt = result.get("format", "png")
    mime = "image/jpeg" if fmt == "jpeg" else "image/png"
    return [
        ImageContent(type="image", data=result["image"], mimeType=mime),
        TextContent(type="text", text=f"Size: {result['width']}x{result['height']}"),
    ]


@mcp.tool()
async def qt_widget_details(ref: str) -> str:
    """Get detailed properties of a specific widget.

    Args:
        ref: Widget ref from qt_snapshot (e.g., 'w5').

    Returns all Qt properties, geometry, parent chain, and more.
    """
    client = await _ensure_connected()
    result = await client.call("widget_details", {"ref": ref})
    lines = [f"Class: {result.get('class', '?')}"]
    if result.get("objectName"):
        lines.append(f"Name: {result['objectName']}")
    if "geometry" in result:
        g = result["geometry"]
        lines.append(f"Geometry: {g['x']},{g['y']} {g['width']}x{g['height']}")
    lines.append(f"Visible: {result.get('visible', '?')}")
    lines.append(f"Enabled: {result.get('enabled', '?')}")
    if "size_hint" in result:
        lines.append(f"Size hint: {result['size_hint'][0]}x{result['size_hint'][1]}")
    if "min_size_hint" in result:
        lines.append(f"Min size hint: {result['min_size_hint'][0]}x{result['min_size_hint'][1]}")
    if "size_policy" in result:
        lines.append(f"Size policy: {result['size_policy']}")
    if "layout" in result:
        lines.append(f"Layout: {result['layout']}")
    if "margins" in result:
        m = result["margins"]
        lines.append(f"Margins: left={m[0]} top={m[1]} right={m[2]} bottom={m[3]}")
    if result.get("parent_chain"):
        lines.append(f"Parent chain: {' > '.join(result['parent_chain'])}")
    if result.get("properties"):
        lines.append("\nProperties:")
        for k, v in result["properties"].items():
            lines.append(f"  {k}: {v}")
    if result.get("items"):
        lines.append(f"\nTree items ({len(result['items'])}):")
        for item in result["items"]:
            indent = "  " * (item.get("depth", 0) + 1)
            lines.append(f"{indent}{item['text']} [ref={item['ref']}]")
    return "\n".join(lines)


# --- Interaction ---


@mcp.tool()
async def qt_click(
    ref: str,
    button: str = "left",
    modifiers: list[str] | None = None,
    position: list[int] | None = None,
) -> str:
    """Click a widget.

    Args:
        ref: Widget ref from qt_snapshot.
        button: Mouse button - 'left', 'right', or 'middle'.
        modifiers: Keyboard modifiers - 'shift', 'ctrl', 'alt', 'meta'.
        position: [x, y] relative to widget top-left. Default: center.
    """
    client = await _ensure_connected()
    params = {"ref": ref, "button": button}
    if modifiers:
        params["modifiers"] = modifiers
    if position:
        params["position"] = position
    await client.call("click", params)
    return "Clicked."


@mcp.tool()
async def qt_type(
    ref: str, text: str, clear_first: bool = False, use_clipboard: bool = False
) -> str:
    """Type text into a widget.

    Args:
        ref: Widget ref from qt_snapshot.
        text: Text to type.
        clear_first: If True, select all and delete before typing.
        use_clipboard: If True, insert via Ctrl+V paste instead of key-by-key events.
            Use this for multi-line text in console/terminal widgets — character-by-character
            typing treats each newline as Enter (submit), corrupting multi-line input.
    """
    client = await _ensure_connected()
    await client.call(
        "type_text",
        {"ref": ref, "text": text, "clear_first": clear_first, "use_clipboard": use_clipboard},
    )
    return "Typed."


@mcp.tool()
async def qt_key_press(key: str, ref: str | None = None) -> str:
    """Send a key event to a widget or the focused widget.

    Args:
        key: Key name (e.g., 'Return', 'Escape', 'Ctrl+S', 'a').
        ref: Widget ref. If omitted, sends to the currently focused widget.
    """
    client = await _ensure_connected()
    params = {"key": key}
    if ref:
        params["ref"] = ref
    await client.call("key_press", params)
    return "Key pressed."


@mcp.tool()
async def qt_set_property(ref: str, property_name: str, value: str | int | float | bool) -> str:
    """Set a Qt property on a widget.

    Args:
        ref: Widget ref from qt_snapshot.
        property_name: Qt property name.
        value: New value for the property.
    """
    client = await _ensure_connected()
    result = await client.call(
        "set_property", {"ref": ref, "property_name": property_name, "value": value}
    )
    return f"Set {property_name}. Old value: {result.get('old_value', '?')}"


@mcp.tool()
async def qt_invoke_slot(ref: str, method_name: str) -> str:
    """Invoke a slot or method on a QObject.

    Args:
        ref: Widget ref from qt_snapshot.
        method_name: Slot/method name to invoke.
    """
    client = await _ensure_connected()
    result = await client.call("invoke_slot", {"ref": ref, "method_name": method_name})
    ok = result.get("ok", False)
    return f"Invoked {method_name}: {'success' if ok else 'failed'}"


@mcp.tool()
async def qt_get_text(ref: str) -> str:
    """Extract text content from a text editor or input widget.

    Args:
        ref: Widget ref from qt_snapshot (e.g., 'w5').

    Works with QPlainTextEdit, QTextEdit, QLineEdit, QLabel, QComboBox,
    and any widget with a text() or toPlainText() method.
    """
    client = await _ensure_connected()
    result = await client.call("get_text", {"ref": ref})
    text = result["text"]
    length = result["length"]
    line_count = result.get("line_count", "?")
    read_only = result.get("read_only")

    header = f"Text ({length} chars, {line_count} lines)"
    if read_only:
        header += " [read-only]"

    if length > MAX_TEXT_PREVIEW_CHARS:
        display_text = (
            text[:MAX_TEXT_PREVIEW_CHARS]
            + f"\n\n... ({length - MAX_TEXT_PREVIEW_CHARS} more chars)"
        )
    else:
        display_text = text

    return f"{header}\n\n{display_text}"


@mcp.tool()
async def qt_trigger_action(
    ref: str,
    action_text: str | None = None,
    action_index: int | None = None,
) -> str:
    """Trigger a menu action or toolbar action by text or index.

    Args:
        ref: Ref to a QMenu, QMenuBar, QToolBar, or any widget with actions.
        action_text: The action's display text (e.g., 'Save', '&Open').
            Ampersands are stripped for matching.
        action_index: The 0-based index of the action
            (matching qt_menu_items order).

    Provide either action_text or action_index (not both).
    Use qt_menu_items first to see available actions.
    """
    if (action_text is None) == (action_index is None):
        raise ValueError("Provide exactly one of action_text or action_index")

    client = await _ensure_connected()
    params = {"ref": ref}
    if action_text is not None:
        params["action_text"] = action_text
    if action_index is not None:
        params["action_index"] = action_index
    result = await client.call("trigger_action", params)
    return f"Triggered: {result.get('action_text', '?')}"


@mcp.tool()
async def qt_wait_for(
    condition: str,
    timeout_ms: int = DEFAULT_WAIT_TIMEOUT_MS,
    object_name: str | None = None,
    ref: str | None = None,
    property_name: str | None = None,
    value: str | int | float | bool | None = None,
) -> str:
    """Wait for a UI state change.

    Args:
        condition: One of 'widget_visible', 'window_count_changed', 'property_equals'.
        timeout_ms: Max time to wait in milliseconds (default 5000).
        object_name: Widget objectName (for widget_visible).
        ref: Widget ref (for property_equals).
        property_name: Property name (for property_equals).
        value: Expected value (for property_equals).
    """
    client = await _ensure_connected()
    params = {"condition": condition, "timeout_ms": timeout_ms}
    if object_name:
        params["object_name"] = object_name
    if ref:
        params["ref"] = ref
    if property_name:
        params["property_name"] = property_name
    if value is not None:
        params["value"] = value
    result = await client.call("wait_for", params)
    elapsed = result.get("elapsed_ms", 0)
    return f"Condition met after {elapsed}ms."


@mcp.tool()
async def qt_batch(steps: list[dict]) -> str:
    """Execute multiple Qt operations in a single round trip.

    Chains clicks, types, key presses, waits, snapshots, and reads into one
    server call — dramatically reduces latency compared to sequential tool calls.

    Each step dict:
        method  (str, required): RPC method — same names as probe methods:
            click, type_text, key_press, set_property, invoke_slot, get_text,
            trigger_action, wait_for, snapshot, find_widget, screenshot.
            Special: "wait" with params {"ms": N} sleeps N ms processing events.
        params  (dict, optional): Parameters forwarded to the method.
        wait_ms (int, optional): Extra pause after the step (default 0).

    Execution stops on the first error; partial results are returned.
    Screenshot steps return size only (not base64 data) — call qt_screenshot
    separately when you actually need the image.

    Example — type multi-line code into IPython console and read back output:
        qt_batch([
            {"method": "find_widget", "params": {"class_name": "ControlWidget"}},
            {"method": "click",       "params": {"ref": "<ref from step 0>"}},
            {"method": "type_text",   "params": {"ref": "...", "text": "%run /tmp/x.py",
                                                  "use_clipboard": true}},
            {"method": "key_press",   "params": {"key": "Return"}},
            {"method": "wait",        "params": {"ms": 3000}},
            {"method": "snapshot",    "params": {"root_ref": "...", "max_depth": 4}}
        ])
    """
    client = await _ensure_connected()
    result = await client.call("batch", {"steps": steps})

    results = result.get("results", [])
    completed = result.get("completed", 0)
    failed_at = result.get("failed_at")
    total = len(steps)

    header = f"Batch: {completed}/{total} steps completed"
    if failed_at is not None:
        header += f", failed at step {failed_at}"
    lines = [header]

    for i, r in enumerate(results):
        method = steps[i].get("method", "?") if i < len(steps) else "?"
        if not r.get("ok"):
            lines.append(f"  [{i}] {method}: ERROR — {r.get('error', '?')}")
            continue

        res = r.get("result", {})
        if not isinstance(res, dict):
            lines.append(f"  [{i}] {method}: OK")
            continue

        # Format result compactly, inlining useful content
        if "tree" in res:
            tree_lines = res["tree"].splitlines()
            lines.append(
                f"  [{i}] {method}: {res.get('widget_count', '?')} widgets "
                f"(gen {res.get('generation', '?')})"
            )
            for tl in tree_lines[:40]:  # cap inline tree at 40 lines
                lines.append(f"    {tl}")
            if len(tree_lines) > 40:
                lines.append(f"    ... ({len(tree_lines) - 40} more lines)")
        elif "widgets" in res:
            lines.append(f"  [{i}] {method}: {res.get('count', 0)} widget(s) found")
            for w in res.get("widgets", []):
                name = f' "{w["objectName"]}"' if w.get("objectName") else ""
                lines.append(f"    - {w['class']}{name} [ref={w['ref']}]")
        elif "text" in res:
            preview = res["text"][:200].replace("\n", "\\n")
            lines.append(
                f"  [{i}] {method}: {res.get('length', '?')} chars — {preview}"
                + ("..." if res.get("length", 0) > 200 else "")
            )
        elif "width" in res and "height" in res and "image" in res:
            # Screenshot: return size only, not the base64 blob
            lines.append(f"  [{i}] {method}: screenshot {res['width']}x{res['height']}")
        elif "waited_ms" in res:
            lines.append(f"  [{i}] {method}: waited {res['waited_ms']}ms")
        elif "ok" in res:
            lines.append(f"  [{i}] {method}: {'OK' if res['ok'] else 'FAIL'}")
        else:
            summary = ", ".join(f"{k}={v!r}" for k, v in list(res.items())[:4])
            lines.append(f"  [{i}] {method}: {summary}")

    return "\n".join(lines)


# --- Application State ---


@mcp.tool()
async def qt_list_windows(skip_hidden: bool = True) -> str:
    """List all top-level windows and their types."""
    client = await _ensure_connected()
    params = {}
    if skip_hidden:
        params["skip_hidden"] = skip_hidden
    result = await client.call("list_windows", params)
    lines = []
    for w in result.get("windows", []):
        vis = "" if w.get("visible") else " [hidden]"
        lines.append(f'- {w["class"]} "{w.get("objectName", "")}" {w["size"]}{vis}')
    return "\n".join(lines) or "(no windows)"


@mcp.tool()
async def qt_object_tree(
    root_ref: str | None = None, max_depth: int = DEFAULT_SNAPSHOT_DEPTH
) -> str:
    """Get the full QObject parent-child tree (not just visible widgets).

    Args:
        root_ref: Starting ref. Defaults to QApplication root.
        max_depth: Maximum traversal depth.
    """
    client = await _ensure_connected()
    params = {"max_depth": max_depth}
    if root_ref:
        params["root_ref"] = root_ref
    result = await client.call("object_tree", params)
    count = result.get("count", 0)
    tree = result.get("tree", "")
    return f"Objects: {count}\n\n{tree}"


@mcp.tool()
async def qt_active_popup() -> str:
    """Check for active popup or modal dialog widgets."""
    client = await _ensure_connected()
    result = await client.call("active_popup")
    parts = []
    if result.get("popup"):
        p = result["popup"]
        parts.append(f'Popup: {p["class"]} "{p.get("objectName", "")}" {p["size"]}')
    if result.get("modal"):
        m = result["modal"]
        parts.append(f'Modal: {m["class"]} "{m.get("objectName", "")}" {m["size"]}')
    return "\n".join(parts) or "No active popup or modal."


@mcp.tool()
async def qt_menu_items(ref: str) -> str:
    """Get actions from a QMenu widget.

    Args:
        ref: Ref to a QMenu widget.
    """
    client = await _ensure_connected()
    result = await client.call("menu_items", {"ref": ref})
    actions = result.get("actions", [])
    if not actions:
        return "(empty menu)"
    lines = [f"Menu actions ({len(actions)}):"]
    for a in actions:
        if a.get("separator"):
            lines.append("  ---")
            continue
        flags = []
        if not a.get("enabled", True):
            flags.append("disabled")
        if a.get("checked"):
            flags.append("checked")
        suffix = f" [{', '.join(flags)}]" if flags else ""
        lines.append(f"  - {a['text']}{suffix}")
    return "\n".join(lines)


# --- Diagnostics ---


@mcp.tool()
async def qt_messages(
    level: str = "info",
) -> str:
    """Returns all console messages

    Args:
        level: Level of the console messages to return. Each level includes the messages
            of more severe levels. Defaults to "info".
    """
    client = await _ensure_connected()
    result = await client.call("qt_messages", {"level": level})
    messages = result.get("messages", [])
    if not messages:
        return "(no Qt messages captured)"
    lines = [f"Qt messages ({len(messages)}):"]
    for m in messages:
        lines.append(f"  [{m['level'].upper()}] {m['message']}")
    return "\n".join(lines)


@mcp.tool()
async def qt_thread_check() -> str:
    """Check thread affinity of all QObjects to detect threading issues.

    Reports which threads own QObjects, flags QWidget subclasses on non-GUI
    threads (the #1 cause of GUI freezes), and lists QThread instances.
    """
    client = await _ensure_connected()
    result = await client.call("thread_check", {})
    lines = [f"GUI thread: {result['gui_thread']}"]
    lines.append(f"\nThreads ({len(result['threads'])}):")
    for t in result["threads"]:
        lines.append(
            f"  - {t['name']} (id={t['id']}): "
            f"{t['object_count']} objects, {t['widget_count']} widgets"
        )
    if result.get("warnings"):
        lines.append(f"\nWARNINGS ({len(result['warnings'])}):")
        for w in result["warnings"]:
            lines.append(f'  - {w["class"]} "{w["object_name"]}" on thread {w["thread_name"]}')
    else:
        lines.append("\nNo threading issues detected.")
    if result.get("qthreads"):
        lines.append(f"\nQThread instances ({len(result['qthreads'])}):")
        for q in result["qthreads"]:
            status = "running" if q["running"] else ("finished" if q["finished"] else "not started")
            lines.append(f"  - {q['object_name'] or '(unnamed)'}: {status}")
    return "\n".join(lines)


@mcp.tool()
async def qt_signals(ref: str) -> str:
    """Inspect signal connections on a QObject.

    For a given widget/object, enumerates all signals and reports which are
    connected and how many receivers each has. Useful for debugging "nothing
    happens when I click" problems.

    Args:
        ref: Widget ref from qt_snapshot (e.g., 'w5').
    """
    client = await _ensure_connected()
    result = await client.call("signals", {"ref": ref})
    signals = result.get("signals", [])
    if not signals:
        return f"No signals found on {result.get('class', '?')}"
    lines = [f"Signals on {result.get('class', '?')} ({len(signals)}):"]
    for s in signals:
        connected = "connected" if s["connected"] else "not connected"
        lines.append(f"  - {s['signature']}: {connected} ({s['receiver_count']} receivers)")
    return "\n".join(lines)


@mcp.tool()
async def qt_layout_check() -> str:
    """Detect layout issues in the visible widget tree.

    Scans all visible widgets and reports problems like:
    - zero_size: Visible widget with 0x0 geometry (collapsed)
    - no_layout: Container with visible children but no layout manager
    - smaller_than_hint: Widget smaller than its sizeHint (content likely clipped)
    - text_truncated: Text content wider than widget width
    - overlapping_siblings: Sibling widgets with intersecting geometries
    """
    client = await _ensure_connected()
    result = await client.call("layout_check", {})
    issues = result.get("issues", [])
    scanned = result.get("scanned", 0)
    if not issues:
        return f"No layout issues detected ({scanned} widgets scanned)."
    lines = [f"Layout issues ({len(issues)}, {scanned} widgets scanned):"]
    for issue in issues:
        severity = issue["severity"].upper()
        lines.append(
            f"  [{severity}] {issue['type']}: {issue['widget_class']} "
            f'"{issue.get("object_name", "")}" [ref={issue["ref"]}] — {issue["detail"]}'
        )
    return "\n".join(lines)


# --- QGraphicsScene ---


@mcp.tool()
async def qt_scene_snapshot(ref: str) -> str:
    """Get all items in a QGraphicsScene.

    Args:
        ref: Ref to a QGraphicsView widget.
    """
    client = await _ensure_connected()
    result = await client.call("scene_snapshot", {"ref": ref})
    items = result.get("items", [])
    if not items:
        return "(empty scene)"
    lines = [f"Scene items ({len(items)}):"]
    for i, item in enumerate(items):
        pos = item.get("pos", [0, 0])
        bounds = item.get("bounds", [0, 0])
        vis = "" if item.get("visible", True) else " [hidden]"
        text = f' "{item["text"]}"' if "text" in item else ""
        lines.append(
            f"  [{i}] {item['class']}{text} pos=({pos[0]:.0f},{pos[1]:.0f}) "
            f"size=({bounds[0]:.0f}x{bounds[1]:.0f}) z={item.get('z', 0)}{vis}"
        )
    return "\n".join(lines)


# --- VTK/3D ---


@mcp.tool()
async def qt_vtk_scene_info(ref: str) -> str:
    """Get VTK scene state from a PyVista/VTK widget.

    Args:
        ref: Ref to a widget containing a VTK render window.
    """
    client = await _ensure_connected()
    result = await client.call("vtk_scene_info", {"ref": ref})

    lines = []
    if result.get("camera"):
        cam = result["camera"]
        lines.append(f"Camera position: {cam.get('position')}")
        lines.append(f"Camera focal point: {cam.get('focal_point')}")
        lines.append(f"Camera view up: {cam.get('view_up')}")

    lines.append(f"Background: {result.get('background')}")
    lines.append(f"Window size: {result.get('size')}")

    actors = result.get("actors", [])
    lines.append(f"\nActors ({len(actors)}):")
    for a in actors:
        vis = "visible" if a.get("visibility") else "hidden"
        lines.append(f"  - {a.get('class', '?')} [{vis}] bounds={a.get('bounds')}")
        if "points" in a:
            lines.append(f"    data: {a['points']} points, {a['cells']} cells")

    return "\n".join(lines)


@mcp.tool()
async def qt_vtk_screenshot(ref: str) -> list:
    """Capture a VTK render window to an image.

    Args:
        ref: Ref to a widget containing a VTK render window.
    """
    client = await _ensure_connected()
    result = await client.call("vtk_screenshot", {"ref": ref})
    return [
        ImageContent(type="image", data=result["image"], mimeType="image/png"),
        TextContent(type="text", text=f"Size: {result['width']}x{result['height']}"),
    ]
