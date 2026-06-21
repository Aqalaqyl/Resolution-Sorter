import pytest

from resolution_sorter.categorize import (
    Orientation,
    classify,
    estimate_size_bytes,
    human_readable_duration,
    human_readable_size,
    resolution_label,
)


@pytest.mark.parametrize(
    "width,height,expected",
    [
        (1920, 1080, Orientation.WIDESCREEN),
        (3840, 2160, Orientation.WIDESCREEN),
        (1280, 720, Orientation.WIDESCREEN),
        (1080, 1920, Orientation.VERTICAL),
        (720, 1280, Orientation.VERTICAL),
        (1080, 1080, Orientation.SQUARE),
        (500, 500, Orientation.SQUARE),
        (1000, 1050, Orientation.SQUARE),  # within 10% tolerance
    ],
)
def test_classify(width, height, expected):
    assert classify(width, height) == expected


def test_classify_tolerance_boundary():
    # 1090x1000 -> ratio 1.09, comfortably within the +/-10% edge => square.
    assert classify(1090, 1000) == Orientation.SQUARE
    # Clearly outside the tolerance becomes widescreen.
    assert classify(1200, 1000) == Orientation.WIDESCREEN
    # A custom, wider tolerance pulls a 1.1 ratio back into "square".
    assert classify(1100, 1000, square_tolerance=0.15) == Orientation.SQUARE


def test_classify_zero_tolerance():
    assert classify(1000, 1000, square_tolerance=0.0) == Orientation.SQUARE
    assert classify(1001, 1000, square_tolerance=0.0) == Orientation.WIDESCREEN


def test_classify_invalid():
    with pytest.raises(ValueError):
        classify(0, 100)
    with pytest.raises(ValueError):
        classify(100, -1)


@pytest.mark.parametrize(
    "width,height,label",
    [
        (1920, 1080, "1080p"),
        (1080, 1920, "1080p"),
        (3840, 2160, "4K"),
        (1280, 720, "720p"),
        (640, 480, "480p"),
        (100, 100, "100p"),
    ],
)
def test_resolution_label(width, height, label):
    assert resolution_label(width, height) == label


def test_estimate_size_bytes():
    # 8 Mbps for 10 seconds = 10 MB.
    assert estimate_size_bytes(8_000_000, 10) == 10_000_000
    assert estimate_size_bytes(0, 10) == 0
    assert estimate_size_bytes(8_000_000, 0) == 0


def test_human_readable_size():
    assert human_readable_size(512) == "512 B"
    assert human_readable_size(1536) == "1.5 KB"
    assert human_readable_size(1024 * 1024) == "1.0 MB"
    assert human_readable_size(0) == "0 B"


def test_human_readable_duration():
    assert human_readable_duration(0) == "0:00"
    assert human_readable_duration(65) == "1:05"
    assert human_readable_duration(3661) == "1:01:01"
