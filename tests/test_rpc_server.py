"""Tests for the JSON-RPC server + Probe install/dispatch."""

import json
import socket
import threading
import time

import pytest

from qt_mcp.probe.rpc_server import ERROR_INVALID_REQUEST

READ_BUFFER_SIZE = 4096
pytestmark = pytest.mark.requires_socket


def _send_rpc(port, method, params=None, request_id=1, timeout=5):
    """Send a JSON-RPC request via TCP and return the parsed response."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect(("localhost", port))
    req = {"jsonrpc": "2.0", "method": method, "params": params or {}, "id": request_id}
    s.sendall(json.dumps(req).encode("utf-8") + b"\n")
    data = s.recv(READ_BUFFER_SIZE)
    s.close()
    return json.loads(data.strip())


def _send_raw(port, payload, timeout=5):
    """Send raw line-delimited payload and parse response."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    s.connect(("localhost", port))
    s.sendall(payload + b"\n")
    data = s.recv(READ_BUFFER_SIZE)
    s.close()
    return json.loads(data.strip())


def test_probe_install_and_ping(qapp, sample_window):
    """Install probe and verify ping/pong over JSON-RPC."""
    from qt_mcp.probe import install

    probe = install(port=0)  # port=0 lets OS pick a free port
    assert probe is not None
    port = probe.port()
    assert port > 0

    # Run client in thread (offscreen QPA needs processEvents)
    result = {}

    def client():
        time.sleep(0.3)
        try:
            result["resp"] = _send_rpc(port, "ping")
        except Exception as e:
            result["error"] = str(e)

    t = threading.Thread(target=client)
    t.start()

    deadline = time.time() + 5
    while t.is_alive() and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.01)
    t.join(timeout=2)

    assert "error" not in result, result.get("error")
    assert result["resp"]["result"] == "pong"


def test_probe_idempotent(qapp, sample_window):
    """Second install() returns the same probe."""
    from qt_mcp.probe import install

    p1 = install(port=0)
    p2 = install()
    assert p1 is p2


def test_probe_snapshot_rpc(qapp, sample_window):
    """Probe responds to snapshot request with widget tree."""
    from qt_mcp.probe import install

    probe = install(port=0)
    port = probe.port()

    result = {}

    def client():
        time.sleep(0.3)
        try:
            result["resp"] = _send_rpc(port, "snapshot", {"max_depth": 5})
        except Exception as e:
            result["error"] = str(e)

    t = threading.Thread(target=client)
    t.start()

    deadline = time.time() + 5
    while t.is_alive() and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.01)
    t.join(timeout=2)

    assert "error" not in result, result.get("error")
    snapshot = result["resp"]["result"]
    assert snapshot["widget_count"] > 0
    assert "MainWindow" in snapshot["tree"]


def test_probe_unknown_method(qapp, sample_window):
    """Probe returns error for unknown methods."""
    from qt_mcp.probe import install

    probe = install(port=0)
    port = probe.port()

    result = {}

    def client():
        time.sleep(0.3)
        try:
            result["resp"] = _send_rpc(port, "nonexistent_method")
        except Exception as e:
            result["error"] = str(e)

    t = threading.Thread(target=client)
    t.start()

    deadline = time.time() + 5
    while t.is_alive() and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.01)
    t.join(timeout=2)

    assert "error" not in result, result.get("error")
    assert "error" in result["resp"]
    assert "Unknown method" in result["resp"]["error"]["message"]


def test_probe_invalid_non_object_payload(qapp, sample_window):
    """Probe returns Invalid Request for non-object JSON payload."""
    from qt_mcp.probe import install

    probe = install(port=0)
    port = probe.port()

    result = {}

    def client():
        time.sleep(0.3)
        try:
            result["resp"] = _send_raw(port, b"[]")
        except Exception as e:
            result["error"] = str(e)

    t = threading.Thread(target=client)
    t.start()

    deadline = time.time() + 5
    while t.is_alive() and time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.01)
    t.join(timeout=2)

    assert "error" not in result, result.get("error")
    assert "error" in result["resp"]
    assert result["resp"]["error"]["code"] == ERROR_INVALID_REQUEST
    assert result["resp"]["id"] is None
