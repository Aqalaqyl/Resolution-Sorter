from pathlib import Path

import pytest

from resolution_sorter import sorter
from resolution_sorter.categorize import Orientation
from resolution_sorter.probe import VideoInfo
from resolution_sorter.sorter import build_plan, execute_plan, find_videos


def _make_video(path: Path, size: int = 1024) -> Path:
    path.write_bytes(b"\0" * size)
    return path


def test_find_videos_non_recursive(tmp_path):
    _make_video(tmp_path / "a.mp4")
    _make_video(tmp_path / "b.mov")
    _make_video(tmp_path / "notes.txt")
    sub = tmp_path / "sub"
    sub.mkdir()
    _make_video(sub / "c.mkv")

    found = list(find_videos(tmp_path, recursive=False))
    names = {p.name for p in found}
    assert names == {"a.mp4", "b.mov"}


def test_find_videos_recursive(tmp_path):
    _make_video(tmp_path / "a.mp4")
    sub = tmp_path / "sub"
    sub.mkdir()
    _make_video(sub / "c.mkv")

    found = {p.name for p in find_videos(tmp_path, recursive=True)}
    assert found == {"a.mp4", "c.mkv"}


@pytest.fixture
def fake_probe(monkeypatch):
    """Patch probe_video to return deterministic metadata based on filename.

    Filenames encode dimensions: ``wide``, ``tall``, ``square`` map to fixed
    resolutions; ``bad`` returns None (unreadable).
    """
    table = {
        "wide": (1920, 1080),
        "tall": (1080, 1920),
        "square": (1080, 1080),
    }

    def _fake(path: Path):
        key = path.stem
        if key == "bad":
            return None
        width, height = table.get(key, (1280, 720))
        return VideoInfo(
            path=path,
            width=width,
            height=height,
            file_size=path.stat().st_size if path.exists() else 1000,
            duration=10.0,
            bitrate=8_000_000,
            codec="h264",
        )

    monkeypatch.setattr(sorter, "probe_video", _fake)
    return _fake


def test_build_plan_categories(tmp_path, fake_probe):
    src = tmp_path / "in"
    src.mkdir()
    _make_video(src / "wide.mp4")
    _make_video(src / "tall.mp4")
    _make_video(src / "square.mp4")
    _make_video(src / "bad.mp4")

    out = tmp_path / "out"
    result = build_plan(src, out)

    assert len(result.planned) == 3
    assert len(result.skipped) == 1
    counts = result.category_counts()
    assert counts[Orientation.WIDESCREEN] == 1
    assert counts[Orientation.VERTICAL] == 1
    assert counts[Orientation.SQUARE] == 1

    dests = {p.orientation: p.destination for p in result.planned}
    assert dests[Orientation.WIDESCREEN] == out / "widescreen" / "wide.mp4"
    assert dests[Orientation.VERTICAL] == out / "vertical" / "tall.mp4"
    assert dests[Orientation.SQUARE] == out / "square" / "square.mp4"


def test_build_plan_by_resolution(tmp_path, fake_probe):
    src = tmp_path / "in"
    src.mkdir()
    _make_video(src / "wide.mp4")

    out = tmp_path / "out"
    result = build_plan(src, out, by_resolution=True)
    plan = result.planned[0]
    assert plan.destination == out / "widescreen" / "1080p" / "wide.mp4"


def test_execute_plan_copy(tmp_path, fake_probe):
    src = tmp_path / "in"
    src.mkdir()
    _make_video(src / "wide.mp4")
    out = tmp_path / "out"

    result = build_plan(src, out)
    execute_plan(result, move=False, dry_run=False)

    assert (out / "widescreen" / "wide.mp4").exists()
    assert (src / "wide.mp4").exists()  # original kept when copying
    assert not result.errors


def test_execute_plan_move(tmp_path, fake_probe):
    src = tmp_path / "in"
    src.mkdir()
    _make_video(src / "tall.mp4")
    out = tmp_path / "out"

    result = build_plan(src, out)
    execute_plan(result, move=True, dry_run=False)

    assert (out / "vertical" / "tall.mp4").exists()
    assert not (src / "tall.mp4").exists()  # original removed when moving


def test_execute_plan_dry_run(tmp_path, fake_probe):
    src = tmp_path / "in"
    src.mkdir()
    _make_video(src / "wide.mp4")
    out = tmp_path / "out"

    result = build_plan(src, out)
    execute_plan(result, move=True, dry_run=True)

    assert not out.exists()  # nothing created
    assert (src / "wide.mp4").exists()
    assert len(result.completed) == 1


def test_execute_plan_no_clobber(tmp_path, fake_probe):
    src = tmp_path / "in"
    src.mkdir()
    _make_video(src / "wide.mp4")
    out = tmp_path / "out"
    target_dir = out / "widescreen"
    target_dir.mkdir(parents=True)
    _make_video(target_dir / "wide.mp4")  # pre-existing file

    result = build_plan(src, out)
    execute_plan(result, move=False, dry_run=False, overwrite=False)

    assert (target_dir / "wide.mp4").exists()
    assert (target_dir / "wide_1.mp4").exists()  # auto-renamed copy


def test_total_size(tmp_path, fake_probe):
    src = tmp_path / "in"
    src.mkdir()
    _make_video(src / "wide.mp4", size=2048)
    out = tmp_path / "out"

    result = build_plan(src, out)
    assert result.total_size() == 2048
