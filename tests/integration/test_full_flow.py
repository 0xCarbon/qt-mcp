"""Integration test: probe + sample app, simulating what an MCP client would do."""

import json
import re
import socket
import threading
import time

import pytest

READ_CHUNK_SIZE = 65536
SNAPSHOT_DEPTH = 10
CLIENT_START_DELAY_SEC = 0.3
EVENT_LOOP_POLL_SEC = 0.01
CLICK_SETTLE_SEC = 0.5
TYPE_SETTLE_SEC = 0.1
FLOW_TIMEOUT_SEC = 10
FLOW_JOIN_TIMEOUT_SEC = 3
LIST_TIMEOUT_SEC = 5
LIST_JOIN_TIMEOUT_SEC = 2

_REF_PATTERN = re.compile(r"\[ref=([^\]]+)\]")
pytestmark = pytest.mark.requires_socket


def _rpc_call(port, method, params=None, request_id=1, timeout=5):
    with socket.create_connection(("localhost", port), timeout=timeout) as conn:
        req = {"jsonrpc": "2.0", "method": method, "params": params or {}, "id": request_id}
        conn.sendall(json.dumps(req).encode("utf-8") + b"\n")
        data = conn.recv(READ_CHUNK_SIZE)
    return json.loads(data.strip())


def _find_ref_in_tree(tree_text, widget_name):
    """Parse snapshot tree text to find ref for a named widget."""
    for row in tree_text.splitlines():
        if widget_name not in row:
            continue
        match = _REF_PATTERN.search(row)
        if match:
            return match.group(1)
    return None


class TestFullFlow:
    """Simulate an MCP client: snapshot, click a button, verify the change."""

    def test_snapshot_click_verify(self, qapp, sample_window):
        from qt_mcp.probe import install

        probe = install(port=0)
        assert probe is not None
        port = probe.port()

        results = {}

        def client_flow():
            time.sleep(CLIENT_START_DELAY_SEC)
            try:
                resp = _rpc_call(port, "snapshot", {"max_depth": SNAPSHOT_DEPTH}, request_id=1)
                tree = resp["result"]["tree"]
                results["tree"] = tree

                btn_ref = _find_ref_in_tree(tree, "IncrementButton")
                counter_ref = _find_ref_in_tree(tree, "CounterLabel")
                assert btn_ref is not None, "IncrementButton not found"
                assert counter_ref is not None, "CounterLabel not found"
                results["btn_ref"] = btn_ref
                results["counter_ref"] = counter_ref

                resp = _rpc_call(port, "widget_details", {"ref": counter_ref}, request_id=2)
                results["initial_details"] = resp["result"]

                resp = _rpc_call(port, "click", {"ref": btn_ref}, request_id=3)
                results["click_result"] = resp["result"]

                time.sleep(CLICK_SETTLE_SEC)

                resp = _rpc_call(port, "snapshot", {"max_depth": SNAPSHOT_DEPTH}, request_id=4)
                results["tree_after"] = resp["result"]["tree"]

                resp = _rpc_call(port, "screenshot", {"full_window": True}, request_id=5)
                results["screenshot"] = resp["result"]

                gv_ref = _find_ref_in_tree(results["tree_after"], "TestGraphicsView")
                if gv_ref:
                    resp = _rpc_call(port, "scene_snapshot", {"ref": gv_ref}, request_id=6)
                    results["scene"] = resp["result"]

                results["ok"] = True

            except Exception as exc:
                results["error"] = str(exc)

        t = threading.Thread(target=client_flow)
        t.start()

        deadline = time.time() + FLOW_TIMEOUT_SEC
        while t.is_alive() and time.time() < deadline:
            qapp.processEvents()
            time.sleep(EVENT_LOOP_POLL_SEC)
        t.join(timeout=FLOW_JOIN_TIMEOUT_SEC)

        # Verify results
        assert results.get("ok"), f"Client flow failed: {results.get('error')}"

        # Verify snapshot contained key widgets
        assert "MainWindow" in results["tree"]
        assert "IncrementButton" in results["tree"]
        assert "CounterLabel" in results["tree"]

        # Verify click worked
        assert results["click_result"]["ok"] is True

        # Verify counter changed in the second snapshot
        assert "Count: 1" in results["tree_after"]

        # Verify screenshot
        assert results["screenshot"]["width"] > 0
        assert len(results["screenshot"]["image"]) > 100  # base64 PNG

        # Verify scene inspection
        if "scene" in results:
            items = results["scene"]["items"]
            assert len(items) == 3

    def test_type_and_read_back(self, qapp, sample_window):
        """Type text into search field and read it back."""
        from qt_mcp.probe import install

        probe = install(port=0)
        port = probe.port()

        results = {}

        def client_flow():
            time.sleep(CLIENT_START_DELAY_SEC)
            try:
                resp = _rpc_call(port, "snapshot", {"max_depth": SNAPSHOT_DEPTH}, request_id=1)
                tree = resp["result"]["tree"]
                edit_ref = _find_ref_in_tree(tree, "SearchField")
                assert edit_ref, "SearchField not found"

                resp = _rpc_call(
                    port,
                    "type_text",
                    {"ref": edit_ref, "text": "test query"},
                    request_id=2,
                )
                assert resp["result"]["ok"]

                time.sleep(TYPE_SETTLE_SEC)
                resp = _rpc_call(port, "widget_details", {"ref": edit_ref}, request_id=3)
                results["details"] = resp["result"]
                results["ok"] = True

            except Exception as exc:
                results["error"] = str(exc)

        t = threading.Thread(target=client_flow)
        t.start()

        deadline = time.time() + FLOW_TIMEOUT_SEC
        while t.is_alive() and time.time() < deadline:
            qapp.processEvents()
            time.sleep(EVENT_LOOP_POLL_SEC)
        t.join(timeout=FLOW_JOIN_TIMEOUT_SEC)

        assert results.get("ok"), f"Failed: {results.get('error')}"
        props = results["details"].get("properties", {})
        assert props.get("text") == "test query"

    def test_list_windows(self, qapp, sample_window):
        """List windows via RPC."""
        from qt_mcp.probe import install

        probe = install(port=0)
        port = probe.port()

        results = {}

        def client_flow():
            time.sleep(CLIENT_START_DELAY_SEC)
            try:
                resp = _rpc_call(port, "list_windows", {}, request_id=1)
                results["windows"] = resp["result"]["windows"]
                results["ok"] = True
            except Exception as exc:
                results["error"] = str(exc)

        t = threading.Thread(target=client_flow)
        t.start()

        deadline = time.time() + LIST_TIMEOUT_SEC
        while t.is_alive() and time.time() < deadline:
            qapp.processEvents()
            time.sleep(EVENT_LOOP_POLL_SEC)
        t.join(timeout=LIST_JOIN_TIMEOUT_SEC)

        assert results.get("ok"), f"Failed: {results.get('error')}"
        windows = results["windows"]
        assert any(w["objectName"] == "MainWindow" for w in windows)
