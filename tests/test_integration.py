"""End-to-end test that probes real videos generated with ffmpeg.

Skipped automatically when ffmpeg/ffprobe are not installed.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from resolution_sorter.categorize import Orientation
from resolution_sorter.probe import ffprobe_available, probe_video
from resolution_sorter.sorter import build_plan, execute_plan

pytestmark = pytest.mark.skipif(
    not (ffprobe_available() and shutil.which("ffmpeg")),
    reason="ffmpeg/ffprobe not installed",
)


def _make_real_video(path: Path, width: int, height: int, seconds: int = 1) -> None:
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"testsrc=size={width}x{height}:rate=15:duration={seconds}",
        "-pix_fmt",
        "yuv420p",
        str(path),
    ]
    subprocess.run(cmd, capture_output=True, check=True)


def test_probe_real_video(tmp_path):
    video = tmp_path / "clip.mp4"
    _make_real_video(video, 1280, 720)

    info = probe_video(video)
    assert info is not None
    assert info.width == 1280
    assert info.height == 720
    assert info.file_size > 0
    assert info.duration > 0


def test_full_sort(tmp_path):
    src = tmp_path / "in"
    src.mkdir()
    _make_real_video(src / "landscape.mp4", 1280, 720)
    _make_real_video(src / "portrait.mp4", 720, 1280)
    _make_real_video(src / "box.mp4", 600, 600)
    (src / "readme.txt").write_text("not a video")

    out = tmp_path / "out"
    result = build_plan(src, out)
    execute_plan(result, move=False, dry_run=False)

    assert (out / "widescreen" / "landscape.mp4").exists()
    assert (out / "vertical" / "portrait.mp4").exists()
    assert (out / "square" / "box.mp4").exists()

    counts = result.category_counts()
    assert counts[Orientation.WIDESCREEN] == 1
    assert counts[Orientation.VERTICAL] == 1
    assert counts[Orientation.SQUARE] == 1
    assert result.total_size() > 0
    assert not result.errors
