"""Discovery, planning and execution of the sorting operation."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator, Optional

from .categorize import (
    Orientation,
    classify,
    estimate_size_bytes,
    resolution_label,
)
from .probe import VideoInfo, probe_video

# Container extensions we attempt to probe. ffprobe is the real authority on
# whether a file is a video; this set just avoids probing obvious non-videos.
VIDEO_EXTENSIONS = {
    ".mp4", ".m4v", ".mov", ".mkv", ".webm", ".avi", ".wmv", ".flv",
    ".mpg", ".mpeg", ".ts", ".m2ts", ".mts", ".3gp", ".3g2", ".ogv",
    ".vob", ".f4v", ".divx", ".asf", ".rm", ".rmvb",
}


@dataclass(frozen=True)
class PlannedMove:
    """A single planned relocation of a video file."""

    info: VideoInfo
    orientation: Orientation
    destination: Path

    @property
    def estimated_size(self) -> int:
        """Best-effort size: the real file size, falling back to a bitrate
        estimate when the on-disk size is unknown."""
        if self.info.file_size > 0:
            return self.info.file_size
        return estimate_size_bytes(self.info.bitrate, self.info.duration)


@dataclass
class SortResult:
    """Outcome of a sort run, for reporting."""

    planned: list[PlannedMove] = field(default_factory=list)
    skipped: list[tuple[Path, str]] = field(default_factory=list)
    completed: list[PlannedMove] = field(default_factory=list)
    errors: list[tuple[Path, str]] = field(default_factory=list)

    def category_counts(self) -> dict[Orientation, int]:
        counts = {o: 0 for o in Orientation}
        for move in self.planned:
            counts[move.orientation] += 1
        return counts

    def category_sizes(self) -> dict[Orientation, int]:
        sizes = {o: 0 for o in Orientation}
        for move in self.planned:
            sizes[move.orientation] += move.estimated_size
        return sizes

    def total_size(self) -> int:
        return sum(move.estimated_size for move in self.planned)


def find_videos(source: Path, recursive: bool = False) -> Iterator[Path]:
    """Yield candidate video files under ``source``."""
    source = Path(source)
    if source.is_file():
        if source.suffix.lower() in VIDEO_EXTENSIONS:
            yield source
        return

    iterator: Iterable[Path] = (
        source.rglob("*") if recursive else source.iterdir()
    )
    for entry in sorted(iterator):
        if entry.is_file() and entry.suffix.lower() in VIDEO_EXTENSIONS:
            yield entry


def _unique_destination(destination: Path) -> Path:
    """Avoid clobbering an existing file by appending ``_1``, ``_2`` ..."""
    if not destination.exists():
        return destination
    stem, suffix, parent = destination.stem, destination.suffix, destination.parent
    counter = 1
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def build_plan(
    source: Path,
    output: Path,
    *,
    recursive: bool = False,
    square_tolerance: float = 0.10,
    by_resolution: bool = False,
) -> SortResult:
    """Probe every candidate video and compute where it should go."""
    result = SortResult()
    output = Path(output)

    for video_path in find_videos(source, recursive=recursive):
        info: Optional[VideoInfo] = probe_video(video_path)
        if info is None:
            result.skipped.append((video_path, "not a readable video"))
            continue

        orientation = classify(info.width, info.height, square_tolerance)
        target_dir = output / orientation.folder
        if by_resolution:
            target_dir = target_dir / resolution_label(info.width, info.height)

        destination = target_dir / video_path.name
        result.planned.append(PlannedMove(info, orientation, destination))

    return result


def execute_plan(
    result: SortResult,
    *,
    move: bool = False,
    dry_run: bool = False,
    overwrite: bool = False,
) -> SortResult:
    """Carry out the planned moves/copies, mutating ``result`` with outcomes."""
    for plan in result.planned:
        destination = plan.destination
        try:
            if dry_run:
                result.completed.append(plan)
                continue

            destination.parent.mkdir(parents=True, exist_ok=True)
            if not overwrite:
                destination = _unique_destination(destination)

            source_path = plan.info.path
            if source_path.resolve() == destination.resolve():
                # Already in place; nothing to do.
                result.completed.append(plan)
                continue

            if move:
                shutil.move(str(source_path), str(destination))
            else:
                shutil.copy2(str(source_path), str(destination))

            result.completed.append(
                PlannedMove(plan.info, plan.orientation, destination)
            )
        except (OSError, shutil.Error) as exc:
            result.errors.append((plan.info.path, str(exc)))

    return result
