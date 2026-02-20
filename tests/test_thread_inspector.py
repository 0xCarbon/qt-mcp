"""Tests for the ThreadInspector module."""

from PySide6.QtCore import QThread

from qt_mcp.probe.thread_inspector import ThreadInspector


def test_thread_check_basic(qapp, sample_window):
    inspector = ThreadInspector()
    result = inspector.thread_check()

    assert result["gui_thread"] is not None
    assert len(result["threads"]) >= 1

    # The main thread should have objects
    main = result["threads"][0]
    assert main["object_count"] > 0

    # No warnings expected — all widgets should be on GUI thread
    assert result["warnings"] == []


def test_thread_check_finds_qthread(qapp, sample_window):
    inspector = ThreadInspector()
    result = inspector.thread_check()

    # sample_app creates a WorkerThread
    names = [q["object_name"] for q in result["qthreads"]]
    assert "WorkerThread" in names

    worker = next(q for q in result["qthreads"] if q["object_name"] == "WorkerThread")
    assert worker["running"] is False
    assert worker["finished"] is False


def test_thread_check_no_app(qapp):
    """Thread check with no visible windows still works."""
    inspector = ThreadInspector()
    result = inspector.thread_check()
    assert "gui_thread" in result
    assert isinstance(result["threads"], list)


def test_thread_check_counts_widgets(qapp, sample_window):
    inspector = ThreadInspector()
    result = inspector.thread_check()

    # Find the main/GUI thread entry
    total_widgets = sum(t["widget_count"] for t in result["threads"])
    assert total_widgets > 0


def test_thread_check_running_qthread(qapp, sample_window):
    """Start a QThread and verify it shows as running."""
    thread = QThread(sample_window)
    thread.setObjectName("TestRunningThread")
    thread.start()
    qapp.processEvents()

    inspector = ThreadInspector()
    result = inspector.thread_check()

    running = [q for q in result["qthreads"] if q["object_name"] == "TestRunningThread"]
    assert len(running) == 1
    assert running[0]["running"] is True

    thread.quit()
    thread.wait(1000)
