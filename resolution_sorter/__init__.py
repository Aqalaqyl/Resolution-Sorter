"""Resolution-Sorter: sort videos by resolution and orientation.

Public API re-exports for convenient importing:

    from resolution_sorter import probe_video, classify, Orientation
"""

from .probe import VideoInfo, probe_video, ffprobe_available
from .categorize import (
    Orientation,
    classify,
    human_readable_size,
    estimate_size_bytes,
    resolution_label,
)

__all__ = [
    "VideoInfo",
    "probe_video",
    "ffprobe_available",
    "Orientation",
    "classify",
    "human_readable_size",
    "estimate_size_bytes",
    "resolution_label",
]

__version__ = "1.0.0"
