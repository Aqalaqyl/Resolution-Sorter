"""Classification and size-estimation helpers."""

from __future__ import annotations

import enum


class Orientation(enum.Enum):
    """The three orientation buckets videos are sorted into."""

    WIDESCREEN = "widescreen"
    SQUARE = "square"
    VERTICAL = "vertical"

    @property
    def folder(self) -> str:
        return self.value


# Default tolerance: treat anything within +/-10% of a 1:1 ratio as "square".
DEFAULT_SQUARE_TOLERANCE = 0.10


def classify(
    width: int,
    height: int,
    square_tolerance: float = DEFAULT_SQUARE_TOLERANCE,
) -> Orientation:
    """Classify a frame size into a :class:`Orientation`.

    A video is *square* when its aspect ratio is within ``square_tolerance`` of
    1:1, *widescreen* when wider than it is tall, and *vertical* otherwise.
    """
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be positive")

    ratio = width / height
    if abs(ratio - 1.0) <= square_tolerance:
        return Orientation.SQUARE
    if ratio > 1.0:
        return Orientation.WIDESCREEN
    return Orientation.VERTICAL


# Common heights mapped to friendly labels for optional resolution sub-folders.
_RESOLUTION_TIERS: list[tuple[int, str]] = [
    (4320, "8K"),
    (2160, "4K"),
    (1440, "1440p"),
    (1080, "1080p"),
    (720, "720p"),
    (480, "480p"),
    (360, "360p"),
    (240, "240p"),
]


def resolution_label(width: int, height: int) -> str:
    """Return a friendly resolution label (e.g. ``1080p``).

    Uses the smaller dimension so vertical clips are labelled consistently with
    their landscape counterparts (a 1080x1920 phone video is still "1080p").
    """
    shortest = min(width, height)
    for threshold, label in _RESOLUTION_TIERS:
        if shortest >= threshold:
            return label
    return f"{shortest}p"


def estimate_size_bytes(bitrate_bps: int, duration_seconds: float) -> int:
    """Estimate a file's size from its bitrate and duration.

    Useful as a fallback when the on-disk size is unavailable (e.g. probing a
    network stream). ``bitrate`` is in bits/second.
    """
    if bitrate_bps <= 0 or duration_seconds <= 0:
        return 0
    return int(bitrate_bps * duration_seconds / 8)


def human_readable_size(num_bytes: float) -> str:
    """Format a byte count as a human-readable string (e.g. ``1.5 GB``)."""
    if num_bytes < 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    size = float(num_bytes)
    for unit in units:
        if size < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"


def human_readable_duration(seconds: float) -> str:
    """Format a duration in seconds as ``H:MM:SS`` or ``M:SS``."""
    if seconds <= 0:
        return "0:00"
    total = int(round(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"
