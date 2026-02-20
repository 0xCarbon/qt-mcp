"""Tests for the Interactor module."""

import re

import pytest
from PySide6.QtWidgets import QLabel, QLineEdit, QTextEdit

WAIT_TIMEOUT_SHORT_MS = 200
_REF_PATTERN = re.compile(r"\[ref=([^\]]+)\]")


def _snapshot_and_find_ref(introspector, name):
    """Take snapshot and find ref for widget with given objectName."""
    tree = introspector.snapshot()["tree"]
    for row in tree.splitlines():
        if name not in row:
            continue
        match = _REF_PATTERN.search(row)
        if match:
            return match.group(1)
    raise ValueError(f"Widget '{name}' not found in snapshot")


def test_click_button(qapp, sample_window, introspector, interactor):
    btn_ref = _snapshot_and_find_ref(introspector, "IncrementButton")
    label = sample_window.findChild(QLabel, "CounterLabel")
    assert label.text() == "Count: 0"

    interactor.click(btn_ref)
    assert label.text() == "Count: 1"

    interactor.click(btn_ref)
    assert label.text() == "Count: 2"


def test_type_text(qapp, sample_window, introspector, interactor):
    edit_ref = _snapshot_and_find_ref(introspector, "SearchField")
    edit = sample_window.findChild(QLineEdit, "SearchField")

    interactor.type_text(edit_ref, "hello world")
    assert edit.text() == "hello world"


def test_type_text_clear_first(qapp, sample_window, introspector, interactor):
    edit_ref = _snapshot_and_find_ref(introspector, "SearchField")
    edit = sample_window.findChild(QLineEdit, "SearchField")

    interactor.type_text(edit_ref, "old text")
    assert edit.text() == "old text"

    interactor.type_text(edit_ref, "new text", clear_first=True)
    assert edit.text() == "new text"


def test_key_press(qapp, sample_window, introspector, interactor):
    edit_ref = _snapshot_and_find_ref(introspector, "SearchField")
    edit = sample_window.findChild(QLineEdit, "SearchField")

    interactor.type_text(edit_ref, "abc")
    interactor.key_press("Backspace", ref=edit_ref)
    assert edit.text() == "ab"


def test_click_unknown_ref(qapp, sample_window, introspector, interactor):
    introspector.snapshot()
    with pytest.raises(ValueError, match="not found"):
        interactor.click("w9999")


def test_set_property(qapp, sample_window, introspector, interactor):
    edit_ref = _snapshot_and_find_ref(introspector, "SearchField")
    result = interactor.set_property(edit_ref, "placeholderText", "New placeholder")
    assert result["ok"]
    edit = sample_window.findChild(QLineEdit, "SearchField")
    assert edit.placeholderText() == "New placeholder"


def test_invoke_slot_with_args(qapp, sample_window, introspector, interactor):
    edit_ref = _snapshot_and_find_ref(introspector, "SearchField")
    edit = sample_window.findChild(QLineEdit, "SearchField")

    result = interactor.invoke_slot(edit_ref, "setText", args=["via invoke"])
    assert result["ok"]
    assert edit.text() == "via invoke"


def test_wait_for_widget_visible(qapp, sample_window, interactor):
    result = interactor.wait_for(
        condition="widget_visible",
        object_name="MainWindow",
        timeout_ms=1000,
    )
    assert result["ok"] is True
    assert result["elapsed_ms"] >= 0


def test_wait_for_timeout(qapp, sample_window, interactor):
    with pytest.raises(TimeoutError, match="Timed out"):
        interactor.wait_for(
            condition="widget_visible",
            object_name="NonexistentWidget",
            timeout_ms=WAIT_TIMEOUT_SHORT_MS,
        )


# --- get_text tests ---


def test_get_text_line_edit(qapp, sample_window, introspector, interactor):
    edit_ref = _snapshot_and_find_ref(introspector, "SearchField")
    edit = sample_window.findChild(QLineEdit, "SearchField")
    edit.setText("hello test")
    qapp.processEvents()

    result = interactor.get_text(edit_ref)
    assert result["text"] == "hello test"
    assert result["length"] == 10


def test_get_text_label(qapp, sample_window, introspector, interactor):
    ref = _snapshot_and_find_ref(introspector, "CounterLabel")
    result = interactor.get_text(ref)
    assert result["text"] == "Count: 0"


def test_get_text_unsupported(qapp, sample_window, introspector, interactor):
    ref = _snapshot_and_find_ref(introspector, "LeftPanel")
    with pytest.raises(ValueError, match="does not support text extraction"):
        interactor.get_text(ref)


def test_get_text_text_edit(qapp, registry, interactor):
    editor = QTextEdit()
    expected_text = "line one\nline two"
    editor.setPlainText(expected_text)
    ref = registry.register(editor, prefix="w")

    result = interactor.get_text(ref)
    assert result["text"] == expected_text
    assert result["length"] == len(expected_text)
    assert result["line_count"] == 2

    editor.deleteLater()
    qapp.processEvents()


# --- trigger_action tests ---


def test_trigger_action_by_text(qapp, registry, interactor):
    from PySide6.QtWidgets import QMenu

    triggered = []
    menu = QMenu("Test")
    menu.addAction("Open")
    save = menu.addAction("Save")
    save.triggered.connect(lambda: triggered.append("Save"))

    ref = registry.register(menu, prefix="w")
    result = interactor.trigger_action(ref, action_text="Save")
    assert result["ok"] is True
    assert triggered == ["Save"]

    menu.deleteLater()
    qapp.processEvents()


def test_trigger_action_by_index(qapp, registry, interactor):
    from PySide6.QtWidgets import QMenu

    triggered = []
    menu = QMenu("Test")
    open_act = menu.addAction("Open")
    open_act.triggered.connect(lambda: triggered.append("Open"))
    menu.addAction("Save")

    ref = registry.register(menu, prefix="w")
    interactor.trigger_action(ref, action_index=0)
    assert triggered == ["Open"]

    menu.deleteLater()
    qapp.processEvents()


def test_trigger_action_ampersand_stripping(qapp, registry, interactor):
    from PySide6.QtWidgets import QMenu

    triggered = []
    menu = QMenu("Test")
    act = menu.addAction("&Save")
    act.triggered.connect(lambda: triggered.append("Save"))

    ref = registry.register(menu, prefix="w")
    interactor.trigger_action(ref, action_text="Save")
    assert triggered == ["Save"]

    menu.deleteLater()
    qapp.processEvents()


def test_trigger_action_disabled(qapp, registry, interactor):
    from PySide6.QtWidgets import QMenu

    menu = QMenu("Test")
    act = menu.addAction("Save")
    act.setEnabled(False)

    ref = registry.register(menu, prefix="w")
    with pytest.raises(ValueError, match="disabled"):
        interactor.trigger_action(ref, action_text="Save")

    menu.deleteLater()
    qapp.processEvents()


def test_trigger_action_not_found(qapp, registry, interactor):
    from PySide6.QtWidgets import QMenu

    menu = QMenu("Test")
    menu.addAction("Open")

    ref = registry.register(menu, prefix="w")
    with pytest.raises(ValueError, match="No action matching"):
        interactor.trigger_action(ref, action_text="Nonexistent")

    menu.deleteLater()
    qapp.processEvents()


def test_trigger_action_requires_exactly_one_selector(qapp, registry, interactor):
    from PySide6.QtWidgets import QMenu

    menu = QMenu("Test")
    menu.addAction("Open")

    ref = registry.register(menu, prefix="w")
    with pytest.raises(ValueError, match="exactly one"):
        interactor.trigger_action(ref, action_text="Open", action_index=0)

    menu.deleteLater()
    qapp.processEvents()
