"""Tests for the qt_messages (Qt warning capture) feature."""

import pytest

from qt_mcp.probe import Probe


@pytest.fixture()
def probe(qapp):
    """Create a Probe, yield it, and clean up."""
    p = Probe(qapp, port=0)
    assert p.start()
    qapp.processEvents()
    yield p
    p._rpc._server.close()
    p.setParent(None)
    p.deleteLater()
    qapp.processEvents()


def test_message_capture(qapp, probe):
    """Probe captures Qt messages emitted via qWarning."""
    from PySide6.QtCore import qWarning

    qWarning("test warning message")
    qapp.processEvents()

    result = probe._get_messages(level="warning")
    assert result["count"] >= 1
    msgs = [m["message"] for m in result["messages"]]
    assert any("test warning message" in m for m in msgs)

    # Buffer should be cleared after retrieval
    result2 = probe._get_messages()
    assert result2["count"] == 0


def test_message_level_filter(qapp, probe):
    """Level filter should exclude lower-severity messages."""
    from PySide6.QtCore import qDebug, qWarning

    qDebug("debug msg")
    qWarning("warning msg")
    qapp.processEvents()

    # Only get warnings and above
    result = probe._get_messages(level="warning")
    levels = [m["level"] for m in result["messages"]]
    assert "debug" not in levels
    assert "warning" in levels


def test_message_buffer_limit(qapp, probe):
    """Buffer should not exceed MESSAGE_BUFFER_MAX."""
    from PySide6.QtCore import qWarning

    from qt_mcp.probe import MESSAGE_BUFFER_MAX

    for i in range(MESSAGE_BUFFER_MAX + 100):
        qWarning(f"msg {i}")
    qapp.processEvents()

    # Buffer should be capped
    assert len(probe._messages) <= MESSAGE_BUFFER_MAX


def test_message_via_dispatch(qapp, probe):
    """The qt_messages RPC method should work via dispatch."""
    from PySide6.QtCore import qWarning

    qWarning("dispatch test")
    qapp.processEvents()

    result = probe._dispatch("qt_messages", {"level": "warning"})
    assert result["count"] >= 1
