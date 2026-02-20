"""Tests for RefRegistry."""

import pytest

from qt_mcp.probe.ref_registry import RefRegistry


def test_register_and_resolve():
    reg = RefRegistry()
    obj = object()
    ref = reg.register(obj)
    assert ref == "w1"
    assert reg.resolve(ref) is obj


def test_idempotent_register():
    reg = RefRegistry()
    obj = object()
    ref1 = reg.register(obj)
    ref2 = reg.register(obj)
    assert ref1 == ref2
    assert len(reg) == 1


def test_different_prefix():
    reg = RefRegistry()
    obj = object()
    ref = reg.register(obj, prefix="i")
    assert ref == "i1"


def test_clear():
    reg = RefRegistry()
    reg.register(object())
    reg.register(object())
    assert len(reg) == 2
    reg.clear()
    assert len(reg) == 0


def test_resolve_unknown():
    reg = RefRegistry()
    assert reg.resolve("w999") is None


def test_sequential_numbering():
    reg = RefRegistry()
    refs = [reg.register(object()) for _ in range(5)]
    assert refs == ["w1", "w2", "w3", "w4", "w5"]


def test_generation_increments_on_clear():
    reg = RefRegistry()
    assert reg.generation == 0
    reg.clear()
    assert reg.generation == 1
    reg.clear()
    assert reg.generation == 2


def test_resolve_or_raise_found():
    reg = RefRegistry()
    obj = object()
    ref = reg.register(obj)
    assert reg.resolve_or_raise(ref) is obj


def test_resolve_or_raise_not_found():
    reg = RefRegistry()
    with pytest.raises(ValueError, match="Ref w999 not found"):
        reg.resolve_or_raise("w999")
