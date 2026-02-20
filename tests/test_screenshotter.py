"""Tests for the Screenshotter module."""

import base64
import re

_REF_PATTERN = re.compile(r"\[ref=([^\]]+)\]")


def _snapshot_and_find_ref(introspector, name):
    tree = introspector.snapshot()["tree"]
    for row in tree.splitlines():
        if name not in row:
            continue
        match = _REF_PATTERN.search(row)
        if match:
            return match.group(1)
    raise ValueError(f"Widget '{name}' not found in snapshot")


def test_screenshot_full_window(qapp, sample_window, introspector, screenshotter):
    introspector.snapshot()  # populate registry
    result = screenshotter.screenshot(full_window=True)
    assert result["width"] > 0
    assert result["height"] > 0
    png_bytes = base64.b64decode(result["image"])
    assert png_bytes[:4] == b"\x89PNG"


def test_screenshot_specific_widget(qapp, sample_window, introspector, screenshotter):
    ref = _snapshot_and_find_ref(introspector, "SearchField")
    result = screenshotter.screenshot(ref=ref)
    assert result["width"] > 0
    assert result["height"] > 0
    png_bytes = base64.b64decode(result["image"])
    assert png_bytes[:4] == b"\x89PNG"


def test_screenshot_graphics_view(qapp, sample_window, introspector, screenshotter):
    ref = _snapshot_and_find_ref(introspector, "TestGraphicsView")
    result = screenshotter.screenshot(ref=ref)
    assert result["width"] > 0
    assert result["height"] > 0


def test_screenshot_with_max_size(qapp, sample_window, introspector, screenshotter):
    introspector.snapshot()
    result = screenshotter.screenshot(full_window=True, max_width=100, max_height=100)
    assert result["width"] <= 100
    assert result["height"] <= 100
    assert result["format"] == "png"


def test_screenshot_jpeg_format(qapp, sample_window, introspector, screenshotter):
    introspector.snapshot()
    result = screenshotter.screenshot(full_window=True, format="jpeg")
    assert result["format"] == "jpeg"
    img_bytes = base64.b64decode(result["image"])
    assert img_bytes[:2] == b"\xff\xd8"
