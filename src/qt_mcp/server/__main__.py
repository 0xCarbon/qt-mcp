"""Entry point: python -m qt_mcp.server"""

from qt_mcp.server.mcp_server import mcp


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
