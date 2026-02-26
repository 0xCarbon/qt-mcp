"""Tests for the Probe._batch execution and the 'batch' RPC method."""

from __future__ import annotations

import json
import socket
import threading
import time

import pytest

pytestmark = pytest.mark.requires_socket

CLIENT_START_DELAY_SEC = 0.3
EVENT_LOOP_POLL_SEC = 0.01
TIMEOUT_SEC = 10
JOIN_SEC = 3


def _rpc(port, method, params=None, req_id=1):
    with socket.create_connection(("localhost", port), timeout=5) as s:
        req = {"jsonrpc": "2.0", "method": method, "params": params or {}, "id": req_id}
        s.sendall(json.dumps(req).encode() + b"\n")
        return json.loads(s.recv(65536).strip())


def _run_client(port, fn):
    """Run fn(port) in a thread, pump events in main thread, return results dict."""
    results = {}

    def _worker():
        time.sleep(CLIENT_START_DELAY_SEC)
        try:
            fn(port, results)
        except Exception as exc:
            results["error"] = str(exc)

    t = threading.Thread(target=_worker)
    t.start()
    from PySide6.QtWidgets import QApplication

    deadline = time.time() + TIMEOUT_SEC
    app = QApplication.instance()
    while t.is_alive() and time.time() < deadline:
        app.processEvents()
        time.sleep(EVENT_LOOP_POLL_SEC)
    t.join(JOIN_SEC)
    return results


# --- helpers ---


def _install_and_get_port(qapp):
    from qt_mcp.probe import install

    probe = install(port=0)
    assert probe is not None
    return probe.port()


# --- tests ---


def test_batch_sequential_click_and_read(qapp, sample_window):
    port = _install_and_get_port(qapp)

    def _client(port, out):
        # Snapshot to get refs
        snap = _rpc(port, "snapshot", {"max_depth": 10}, req_id=1)
        tree = snap["result"]["tree"]

        btn_ref = next(
            (
                __import__("re").search(r"\[ref=(\w+)\]", row).group(1)
                for row in tree.splitlines()
                if "IncrementButton" in row
            ),
            None,
        )
        label_ref = next(
            (
                __import__("re").search(r"\[ref=(\w+)\]", row).group(1)
                for row in tree.splitlines()
                if "CounterLabel" in row
            ),
            None,
        )
        assert btn_ref and label_ref

        # Batch: click button twice, then read label text
        resp = _rpc(
            port,
            "batch",
            {
                "steps": [
                    {"method": "click", "params": {"ref": btn_ref}},
                    {"method": "click", "params": {"ref": btn_ref}},
                    {"method": "get_text", "params": {"ref": label_ref}},
                ]
            },
            req_id=2,
        )
        out["batch"] = resp["result"]

    results = _run_client(port, _client)
    assert "error" not in results, results.get("error")
    batch = results["batch"]
    assert batch["completed"] == 3
    assert batch["failed_at"] is None
    # Third step is get_text — should read "Count: 2"
    assert batch["results"][2]["ok"]
    assert batch["results"][2]["result"]["text"] == "Count: 2"


def test_batch_wait_step(qapp, sample_window):
    port = _install_and_get_port(qapp)

    def _client(port, out):
        t0 = time.monotonic()
        resp = _rpc(
            port,
            "batch",
            {"steps": [{"method": "wait", "params": {"ms": 200}}]},
            req_id=1,
        )
        elapsed = time.monotonic() - t0
        out["resp"] = resp["result"]
        out["elapsed"] = elapsed

    results = _run_client(port, _client)
    assert "error" not in results, results.get("error")
    assert results["resp"]["completed"] == 1
    assert results["resp"]["results"][0]["result"]["waited_ms"] == 200
    assert results["elapsed"] >= 0.15  # at least 150ms


def test_batch_stops_on_error(qapp, sample_window):
    port = _install_and_get_port(qapp)

    def _client(port, out):
        resp = _rpc(
            port,
            "batch",
            {
                "steps": [
                    {"method": "ping", "params": {}},
                    {"method": "click", "params": {"ref": "nonexistent_ref"}},
                    {"method": "ping", "params": {}},  # should NOT execute
                ]
            },
            req_id=1,
        )
        out["resp"] = resp["result"]

    results = _run_client(port, _client)
    assert "error" not in results, results.get("error")
    batch = results["resp"]
    # Step 0 (ping) succeeds, step 1 (bad click) fails, step 2 never runs
    assert batch["completed"] == 1
    assert batch["failed_at"] == 1
    assert len(batch["results"]) == 2
    assert batch["results"][0]["ok"]
    assert not batch["results"][1]["ok"]
    assert "nonexistent_ref" in batch["results"][1]["error"]


def test_batch_nested_batch_rejected(qapp, sample_window):
    port = _install_and_get_port(qapp)

    def _client(port, out):
        resp = _rpc(
            port,
            "batch",
            {"steps": [{"method": "batch", "params": {"steps": []}}]},
            req_id=1,
        )
        out["resp"] = resp["result"]

    results = _run_client(port, _client)
    assert "error" not in results, results.get("error")
    batch = results["resp"]
    assert batch["failed_at"] == 0
    assert "Nested batch" in batch["results"][0]["error"]


def test_batch_snapshot_inline(qapp, sample_window):
    port = _install_and_get_port(qapp)

    def _client(port, out):
        resp = _rpc(
            port,
            "batch",
            {"steps": [{"method": "snapshot", "params": {"max_depth": 4}}]},
            req_id=1,
        )
        out["resp"] = resp["result"]

    results = _run_client(port, _client)
    assert "error" not in results, results.get("error")
    batch = results["resp"]
    assert batch["completed"] == 1
    tree_result = batch["results"][0]["result"]
    assert "tree" in tree_result
    assert "MainWindow" in tree_result["tree"]


def test_batch_find_widget_inline(qapp, sample_window):
    port = _install_and_get_port(qapp)

    def _client(port, out):
        resp = _rpc(
            port,
            "batch",
            {
                "steps": [
                    {
                        "method": "find_widget",
                        "params": {"object_name": "IncrementButton"},
                    }
                ]
            },
            req_id=1,
        )
        out["resp"] = resp["result"]

    results = _run_client(port, _client)
    assert "error" not in results, results.get("error")
    batch = results["resp"]
    assert batch["completed"] == 1
    fw_result = batch["results"][0]["result"]
    assert fw_result["count"] >= 1
    assert fw_result["widgets"][0]["objectName"] == "IncrementButton"


def test_batch_wait_ms_between_steps(qapp, sample_window):
    """wait_ms field pauses between steps."""
    port = _install_and_get_port(qapp)

    def _client(port, out):
        t0 = time.monotonic()
        _rpc(
            port,
            "batch",
            {
                "steps": [
                    {"method": "ping", "params": {}, "wait_ms": 150},
                    {"method": "ping", "params": {}},
                ]
            },
            req_id=1,
        )
        out["elapsed"] = time.monotonic() - t0

    results = _run_client(port, _client)
    assert "error" not in results, results.get("error")
    assert results["elapsed"] >= 0.1
