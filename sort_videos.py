#!/usr/bin/env python3
"""Sort videos by resolution and categorize by aspect ratio."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


VIDEO_EXTENSIONS = {
    ".mp4",
    ".mkv",
    ".avi",
    ".mov",
    ".wmv",
    ".flv",
    ".webm",
    ".m4v",
    ".mpeg",
    ".mpg",
    ".3gp",
    ".ts",
    ".mts",
    ".m2ts",
}

SQUARE_TOLERANCE = 0.05


class Category(str, Enum):
    WIDESCREEN = "widescreen"
    SQUARE = "square"
    VERTICAL = "vertical"


@dataclass(frozen=True)
class VideoInfo:
    path: Path
    width: int
    height: int
    duration_seconds: float
    estimated_size_bytes: int
    size_source: str

    @property
    def resolution(self) -> int:
        return self.width * self.height

    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height if self.height else 0.0

    @property
    def category(self) -> Category:
        ratio = self.aspect_ratio
        if abs(ratio - 1.0) <= SQUARE_TOLERANCE:
            return Category.SQUARE
        if ratio > 1.0:
            return Category.WIDESCREEN
        return Category.VERTICAL

    def format_size(self) -> str:
        return human_size(self.estimated_size_bytes)


def human_size(num_bytes: int) -> str:
    units = ("B", "KB", "MB", "GB", "TB")
    size = float(num_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{num_bytes} B"


def human_duration(seconds: float) -> str:
    if seconds <= 0:
        return "unknown"
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def run_ffprobe(path: Path) -> dict:
    cmd = [
        "ffprobe",
        "-v",
        "quiet",
        "-print_format",
        "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or f"ffprobe failed for {path}")
    return json.loads(result.stdout)


def parse_float(value: str | None, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def parse_int(value: str | None, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def pick_video_stream(streams: list[dict]) -> dict | None:
    for stream in streams:
        if stream.get("codec_type") == "video":
            return stream
    return None


def estimate_size_bytes(
    path: Path,
    width: int,
    height: int,
    duration_seconds: float,
    fmt: dict,
    stream: dict,
) -> tuple[int, str]:
    file_size = path.stat().st_size
    if file_size > 0:
        return file_size, "file"

    format_size = parse_int(fmt.get("size"))
    if format_size > 0:
        return format_size, "format metadata"

    bit_rate = parse_int(stream.get("bit_rate"))
    if bit_rate <= 0:
        bit_rate = parse_int(fmt.get("bit_rate"))

    if bit_rate > 0 and duration_seconds > 0:
        estimated = int(bit_rate * duration_seconds / 8)
        return estimated, "bitrate x duration"

    pixels = width * height
    if pixels > 0 and duration_seconds > 0:
        # Rough fallback: ~0.12 bits per pixel per second for compressed video.
        estimated = int(pixels * duration_seconds * 0.12 / 8)
        return max(estimated, 1), "resolution heuristic"

    return file_size, "unavailable"


def analyze_video(path: Path) -> VideoInfo:
    probe = run_ffprobe(path)
    stream = pick_video_stream(probe.get("streams", []))
    if not stream:
        raise RuntimeError(f"No video stream found in {path}")

    width = parse_int(stream.get("width"))
    height = parse_int(stream.get("height"))
    if width <= 0 or height <= 0:
        raise RuntimeError(f"Invalid dimensions for {path}: {width}x{height}")

    fmt = probe.get("format", {})
    duration_seconds = parse_float(fmt.get("duration"))
    if duration_seconds <= 0:
        duration_seconds = parse_float(stream.get("duration"))

    estimated_size, size_source = estimate_size_bytes(
        path, width, height, duration_seconds, fmt, stream
    )

    return VideoInfo(
        path=path,
        width=width,
        height=height,
        duration_seconds=duration_seconds,
        estimated_size_bytes=estimated_size,
        size_source=size_source,
    )


def discover_videos(root: Path, recursive: bool) -> list[Path]:
    if root.is_file():
        return [root] if root.suffix.lower() in VIDEO_EXTENSIONS else []

    pattern = "**/*" if recursive else "*"
    videos = [
        path
        for path in root.glob(pattern)
        if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS
    ]
    return sorted(videos)


def sort_videos(videos: list[VideoInfo]) -> dict[Category, list[VideoInfo]]:
    grouped: dict[Category, list[VideoInfo]] = {
        Category.WIDESCREEN: [],
        Category.SQUARE: [],
        Category.VERTICAL: [],
    }
    for video in videos:
        grouped[video.category].append(video)

    for category in grouped:
        grouped[category].sort(
            key=lambda item: (item.resolution, item.estimated_size_bytes, item.path.name),
            reverse=True,
        )
    return grouped


def copy_or_move_videos(
    grouped: dict[Category, list[VideoInfo]],
    output_dir: Path,
    move: bool,
) -> None:
    for category, videos in grouped.items():
        category_dir = output_dir / category.value
        category_dir.mkdir(parents=True, exist_ok=True)
        for video in videos:
            destination = category_dir / video.path.name
            if destination.resolve() == video.path.resolve():
                continue
            if destination.exists():
                raise FileExistsError(f"Destination already exists: {destination}")
            if move:
                shutil.move(str(video.path), destination)
            else:
                shutil.copy2(video.path, destination)


def print_report(grouped: dict[Category, list[VideoInfo]]) -> None:
    total_videos = sum(len(videos) for videos in grouped.values())
    total_size = sum(video.estimated_size_bytes for videos in grouped.values() for video in videos)

    print(f"Found {total_videos} video(s), estimated total size {human_size(total_size)}\n")

    for category in Category:
        videos = grouped[category]
        category_size = sum(video.estimated_size_bytes for video in videos)
        print(f"=== {category.value.upper()} ({len(videos)}) — {human_size(category_size)} ===")
        if not videos:
            print("  (none)")
            print()
            continue

        for index, video in enumerate(videos, start=1):
            print(
                f"  {index:>2}. {video.path.name}\n"
                f"      {video.width}x{video.height} | "
                f"aspect {video.aspect_ratio:.2f} | "
                f"{human_duration(video.duration_seconds)} | "
                f"{video.format_size()} ({video.size_source})"
            )
        print()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze videos, estimate their size, sort by resolution, "
            "and group into widescreen, square, and vertical categories."
        )
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Video file or directory containing videos",
    )
    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Search directories recursively",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Copy or move sorted videos into category subfolders",
    )
    parser.add_argument(
        "--move",
        action="store_true",
        help="Move files instead of copying when --output is used",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not args.input.exists():
        print(f"Error: path does not exist: {args.input}", file=sys.stderr)
        return 1

    if shutil.which("ffprobe") is None:
        print("Error: ffprobe is required but was not found on PATH.", file=sys.stderr)
        return 1

    videos_paths = discover_videos(args.input, args.recursive)
    if not videos_paths:
        print("No supported video files found.")
        return 0

    analyzed: list[VideoInfo] = []
    errors: list[str] = []
    for path in videos_paths:
        try:
            analyzed.append(analyze_video(path))
        except (RuntimeError, json.JSONDecodeError, OSError) as exc:
            errors.append(f"{path}: {exc}")

    if not analyzed:
        print("Could not analyze any videos.", file=sys.stderr)
        for message in errors:
            print(message, file=sys.stderr)
        return 1

    grouped = sort_videos(analyzed)
    print_report(grouped)

    if args.output:
        copy_or_move_videos(grouped, args.output, args.move)
        action = "Moved" if args.move else "Copied"
        print(f"{action} videos into {args.output.resolve()}")

    if errors:
        print("Warnings:", file=sys.stderr)
        for message in errors:
            print(message, file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
