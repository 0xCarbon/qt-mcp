# qt-mcp

[![PyPI](https://img.shields.io/pypi/v/qt-mcp)](https://pypi.org/project/qt-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/qt-mcp)](https://pypi.org/project/qt-mcp/)
[![CI](https://github.com/0xCarbon/qt-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/0xCarbon/qt-mcp/actions/workflows/ci.yml)
[![Security](https://github.com/0xCarbon/qt-mcp/actions/workflows/security.yml/badge.svg)](https://github.com/0xCarbon/qt-mcp/actions/workflows/security.yml)
[![License](https://img.shields.io/badge/license-MIT%20OR%20Apache--2.0-blue.svg)](LICENSE-MIT)

MCP (Model Context Protocol) server for inspecting, debugging, and interacting with Qt/PySide6 desktop applications — like Playwright MCP, but for desktop Qt apps.

## Overview

qt-mcp gives AI coding agents full visibility into running PySide6 applications:

- **Widget tree snapshots** — structured accessibility-like view of the entire UI
- **Property inspection** — read all Qt properties on any widget
- **Interaction** — click buttons, type text, press keys
- **Screenshots** — capture any widget or full window as PNG
- **QGraphicsScene inspection** — enumerate and inspect scene items
- **VTK/PyVista support** — inspect 3D scenes and capture renders

## Architecture

```
┌─────────────────────────────────────────────┐
│  Target PySide6 Application                 │
│  ┌───────────────────────────────────────┐  │
│  │  qt-mcp Probe (in-process)           │  │
│  │  • QObject tree traversal            │  │
│  │  • Property read/write               │  │
│  │  • Widget.grab() screenshots         │  │
│  │  • Event injection (click/type)      │  │
│  │  Listens on: localhost:9142          │  │
│  └───────────────────────────────────────┘  │
└──────────────────┬──────────────────────────┘
                   │ JSON-RPC over TCP
┌──────────────────┴──────────────────────────┐
│  qt-mcp MCP Server (separate process)       │
│  • Speaks MCP protocol (stdio) to Claude    │
│  • Translates tool calls → probe RPCs       │
└─────────────────────────────────────────────┘
```

## Installation

```bash
# Install with uv
uv add qt-mcp

# Or install from source
git clone https://github.com/0xCarbon/qt-mcp.git
cd qt-mcp
uv sync --extra dev
```

## Quick Start

### 1. Instrument your app

Add the probe to your PySide6 application:

```python
# Option A: Environment variable (preferred)
# QT_MCP_PROBE=1 python -m your_app

# Option B: Explicit init
from qt_mcp.probe import install
install()  # call after QApplication is created
```

### 2. Configure Claude Code

Add to your MCP settings:

```json
{
  "mcpServers": {
    "qt-mcp": {
      "command": "uvx",
      "args": ["qt-mcp"]
    }
  }
}
```

### 3. Use from Claude

Claude can now see and interact with your Qt app:

> "Take a snapshot of the running application"
> "Click the 'Apply' button"
> "Type 'hello' into the search field"
> "Show me a screenshot of the 3D view"

## MCP Tools

| Tool | Description |
|------|-------------|
| `qt_snapshot` | Capture the full widget tree as a structured snapshot |
| `qt_screenshot` | Take a screenshot of a widget or full window |
| `qt_widget_details` | Get detailed properties of a specific widget |
| `qt_click` | Click a widget (left/right/middle button, modifiers) |
| `qt_type` | Type text into a widget |
| `qt_key_press` | Send a key event (Return, Escape, Ctrl+S, etc.) |
| `qt_set_property` | Set a Qt property on a widget |
| `qt_invoke_slot` | Invoke a slot/method on a QObject |
| `qt_list_windows` | List all top-level windows |
| `qt_object_tree` | Get the full QObject parent-child tree |
| `qt_scene_snapshot` | Get all items in a QGraphicsScene |
| `qt_vtk_scene_info` | Get VTK scene state (camera, actors) |
| `qt_vtk_screenshot` | Capture a VTK render window |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `QT_MCP_PROBE` | unset | Set to `1` to auto-activate the probe |
| `QT_MCP_PORT` | `9142` | Probe TCP listen port |
| `QT_MCP_HOST` | `localhost` | Probe TCP host (MCP server side) |

## Development

```bash
# Install dev dependencies
uv sync --extra dev

# Run tests
uv run pytest -v

# Format
uv run ruff format src/ tests/

# Lint
uv run ruff check src/ tests/

# Security audit
uv run pip-audit --progress-spinner off
gitleaks detect --source . --config .gitleaks.toml
```

## Troubleshooting

### Probe not connecting
- Ensure the probe is installed in the target app (check for `qt_mcp_probe` in `QApplication.children()`)
- Verify the port matches between probe and MCP server (`QT_MCP_PORT`)
- Check that nothing else is using port 9142

### Wayland issues
- `QWidget.grab()` works from inside the process on both X11 and Wayland
- External screenshot tools may require portal authorization on Wayland

### OpenGL widgets
- `QOpenGLWidget.grab()` requires a real display server (X11/Wayland)
- With offscreen platform, grab() returns a valid pixmap but without GL content
- Standard widgets and QGraphicsView work fine offscreen

## License

Licensed under either of:

- Apache License, Version 2.0 ([LICENSE-APACHE](LICENSE-APACHE) or <https://www.apache.org/licenses/LICENSE-2.0>)
- MIT license ([LICENSE-MIT](LICENSE-MIT) or <https://opensource.org/licenses/MIT>)

at your option.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development workflow and contribution requirements.

## Code of Conduct

See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Security

See [SECURITY.md](SECURITY.md) to report vulnerabilities.
