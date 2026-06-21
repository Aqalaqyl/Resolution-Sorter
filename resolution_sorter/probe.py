"""Wrapper around ``ffprobe`` to extract video metadata.

The heavy lifting of reading a container's resolution, duration and bitrate is
delegated to ``ffprobe`` (part of FFmpeg) because it understands virtually every
video format. We only parse its JSON output here.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class VideoInfo:
    """Metadata describing a single video file."""

    path: Path
    width: int
    height: int
    file_size: int
    duration: float = 0.0
    bitrate: int = 0
    codec: str = ""

    @property
    def pixels(self) -> int:
        return self.width * self.height

    @property
    def aspect_ratio(self) -> float:
        """Width-to-height ratio. Returns 0.0 when height is unknown."""
        return self.width / self.height if self.height else 0.0


@lru_cache(maxsize=1)
def ffprobe_available() -> bool:
    """Return True when an ``ffprobe`` executable is on the PATH."""
    return shutil.which("ffprobe") is not None


def _run_ffprobe(path: Path) -> Optional[dict]:
    """Invoke ffprobe and return its parsed JSON, or None on failure."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-print_format",
        "json",
        "-show_streams",
        "-show_format",
        str(path),
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return None


def _first_video_stream(streams: list[dict]) -> Optional[dict]:
    for stream in streams:
        if stream.get("codec_type") == "video":
            # Skip cover-art / attached pictures which masquerade as video.
            if stream.get("disposition", {}).get("attached_pic"):
                continue
            return stream
    return None


def probe_video(path: Path) -> Optional[VideoInfo]:
    """Probe ``path`` and return :class:`VideoInfo`, or None if it is not a
    readable video (no decodable video stream / ffprobe failure)."""
    if not ffprobe_available():
        raise RuntimeError(
            "ffprobe was not found on PATH. Install FFmpeg to use Resolution-Sorter."
        )

    path = Path(path)
    data = _run_ffprobe(path)
    if not data:
        return None

    stream = _first_video_stream(data.get("streams", []))
    if stream is None:
        return None

    try:
        width = int(stream.get("width") or 0)
        height = int(stream.get("height") or 0)
    except (TypeError, ValueError):
        return None

    if width <= 0 or height <= 0:
        return None

    fmt = data.get("format", {})

    try:
        file_size = int(fmt.get("size") or path.stat().st_size)
    except (TypeError, ValueError, OSError):
        file_size = 0

    def _to_float(value: object) -> float:
        try:
            return float(value)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0.0

    def _to_int(value: object) -> int:
        try:
            return int(float(value))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0

    duration = _to_float(fmt.get("duration")) or _to_float(stream.get("duration"))
    bitrate = _to_int(fmt.get("bit_rate")) or _to_int(stream.get("bit_rate"))
    codec = str(stream.get("codec_name") or "")

    return VideoInfo(
        path=path,
        width=width,
        height=height,
        file_size=file_size,
        duration=duration,
        bitrate=bitrate,
        codec=codec,
    )
