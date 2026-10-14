#!/usr/bin/env python3
"""Sort videos, images, and GIFs by resolution and categorize by aspect ratio."""

from __future__ import annotations

import argparse
import json
import shutil
import struct
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

IMAGE_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".jpe",
    ".jfif",
    ".png",
    ".apng",
    ".bmp",
    ".tif",
    ".tiff",
    ".webp",
    ".avif",
    ".heic",
    ".heif",
}

GIF_EXTENSIONS = {".gif"}

MEDIA_EXTENSIONS = VIDEO_EXTENSIONS | IMAGE_EXTENSIONS | GIF_EXTENSIONS

# ffprobe reports a single-frame JPEG as ~1/25s. Longer than this is a real duration.
SYNTHETIC_STILL_DURATION = 0.15

SQUARE_TOLERANCE = 0.05

# EXIF orientations that display with width and height swapped.
SWAPPED_ORIENTATIONS = {5, 6, 7, 8}


class Category(str, Enum):
    WIDESCREEN = "widescreen"
    SQUARE = "square"
    VERTICAL = "vertical"


class MediaKind(str, Enum):
    VIDEO = "video"
    IMAGE = "image"
    GIF = "gif"


@dataclass(frozen=True)
class MediaInfo:
    path: Path
    width: int
    height: int
    duration_seconds: float
    estimated_size_bytes: int
    size_source: str
    kind: MediaKind
    frame_count: int
    animated: bool

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
    if seconds < 1:
        return f"{seconds:.2f}s"
    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m {secs}s"
    if minutes:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def format_timing(item: MediaInfo) -> str:
    if item.kind is not MediaKind.VIDEO and not item.animated:
        return "still"

    timing = human_duration(item.duration_seconds)
    if item.kind is MediaKind.VIDEO:
        return timing

    if item.frame_count > 1:
        if item.duration_seconds > 0:
            return f"{timing} · {item.frame_count} frames"
        return f"{item.frame_count} frames"
    if item.duration_seconds <= 0:
        return "animated"
    return timing


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


def parse_float(value: object, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def parse_int(value: object, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def pick_video_stream(streams: list[dict]) -> dict | None:
    for stream in streams:
        if stream.get("codec_type") == "video":
            return stream
    return None


def media_kind(path: Path) -> MediaKind:
    suffix = path.suffix.lower()
    if suffix in GIF_EXTENSIONS:
        return MediaKind.GIF
    if suffix in IMAGE_EXTENSIONS:
        return MediaKind.IMAGE
    return MediaKind.VIDEO


def _tiff_orientation(data: bytes) -> int | None:
    """Read the EXIF Orientation tag from a TIFF header."""
    if len(data) < 8:
        return None
    if data[:2] == b"II":
        endian = "<"
    elif data[:2] == b"MM":
        endian = ">"
    else:
        return None
    if struct.unpack_from(endian + "H", data, 2)[0] != 42:
        return None

    offset = struct.unpack_from(endian + "I", data, 4)[0]
    for _ in range(8):
        if offset <= 0 or offset + 2 > len(data):
            return None
        count = struct.unpack_from(endian + "H", data, offset)[0]
        offset += 2
        for _ in range(count):
            if offset + 12 > len(data):
                return None
            tag, field_type, count = struct.unpack_from(endian + "HHI", data, offset)
            if tag == 0x0112 and field_type == 3 and count == 1:
                value = struct.unpack_from(endian + "H", data, offset + 8)[0]
                if 1 <= value <= 8:
                    return value
            offset += 12
        if offset + 4 > len(data):
            return None
        offset = struct.unpack_from(endian + "I", data, offset)[0]
    return None


def _jpeg_orientation(path: Path) -> int | None:
    with path.open("rb") as handle:
        if handle.read(2) != b"\xff\xd8":
            return None
        while True:
            marker = handle.read(1)
            if marker != b"\xff":
                return None
            code = handle.read(1)
            while code == b"\xff":
                code = handle.read(1)
            if not code:
                return None
            value = code[0]
            if value in {0xD8, 0xD9} or value == 0x01 or 0xD0 <= value <= 0xD7:
                continue
            length_bytes = handle.read(2)
            if len(length_bytes) < 2:
                return None
            segment_length = int.from_bytes(length_bytes, "big")
            if segment_length < 2:
                return None
            payload_length = segment_length - 2
            if value == 0xDA:  # start of scan; orientation would already have appeared
                return None
            if value == 0xE1:
                payload = handle.read(payload_length)
                if len(payload) < payload_length:
                    return None
                if len(payload) >= 6 and payload[:4].lower() == b"exif" and payload[4:6] == b"\x00\x00":
                    orientation = _tiff_orientation(payload[6:])
                    if orientation:
                        return orientation
                continue
            handle.seek(payload_length, 1)


def _png_orientation(path: Path) -> int | None:
    with path.open("rb") as handle:
        if handle.read(8) != b"\x89PNG\r\n\x1a\n":
            return None
        while True:
            header = handle.read(8)
            if len(header) < 8:
                return None
            length = int.from_bytes(header[:4], "big")
            chunk_type = header[4:8]
            if chunk_type == b"eXIf":
                return _tiff_orientation(handle.read(length))
            if chunk_type in {b"IDAT", b"IEND"}:
                return None
            handle.seek(length + 4, 1)


def _tiff_file_orientation(path: Path) -> int | None:
    with path.open("rb") as handle:
        header = handle.read(8)
        if len(header) < 8 or header[:2] not in {b"II", b"MM"}:
            return None
        endian = "<" if header[:2] == b"II" else ">"
        offset = struct.unpack_from(endian + "I", header, 4)[0]
        # Orientation lives in the first IFD. Read a bounded window around it.
        handle.seek(0)
        window_end = max(offset + 65536, 65536)
        data = handle.read(window_end)
    return _tiff_orientation(data)


def _vp8_size(payload: bytes) -> tuple[int, int] | None:
    start = payload.find(b"\x9d\x01\x2a")
    if start < 0 or start + 7 > len(payload):
        return None
    width = int.from_bytes(payload[start + 3 : start + 5], "little") & 0x3FFF
    height = int.from_bytes(payload[start + 5 : start + 7], "little") & 0x3FFF
    if width <= 0 or height <= 0:
        return None
    return width, height


def _vp8l_size(payload: bytes) -> tuple[int, int] | None:
    if len(payload) < 5 or payload[0] != 0x2F:
        return None
    bits = int.from_bytes(payload[1:5], "little")
    width = (bits & 0x3FFF) + 1
    height = ((bits >> 14) & 0x3FFF) + 1
    if width <= 0 or height <= 0:
        return None
    return width, height


@dataclass(frozen=True)
class WebpDetails:
    width: int | None = None
    height: int | None = None
    animated: bool = False
    orientation: int | None = None


def read_webp_details(path: Path) -> WebpDetails:
    """Read canvas size, animation flag, and EXIF orientation from a WebP file.

    This ffmpeg build cannot decode animated WebP, so ffprobe reports 0x0 for
    those files. The VP8X header still carries the canvas size.
    """
    width: int | None = None
    height: int | None = None
    animated = False
    orientation: int | None = None
    exif_expected = False

    with path.open("rb") as handle:
        header = handle.read(12)
        if len(header) < 12 or header[:4] != b"RIFF" or header[8:12] != b"WEBP":
            return WebpDetails()

        while True:
            chunk_header = handle.read(8)
            if len(chunk_header) < 8:
                break
            tag = chunk_header[:4]
            size = int.from_bytes(chunk_header[4:], "little")
            if tag == b"VP8X" and size >= 10:
                payload = handle.read(size)
                if len(payload) < 10:
                    break
                flags = payload[0]
                animated = bool(flags & 0x02)
                exif_expected = bool(flags & 0x08)
                width = int.from_bytes(payload[4:7], "little") + 1
                height = int.from_bytes(payload[7:10], "little") + 1
                if not exif_expected:
                    break
            elif tag == b"EXIF":
                payload = handle.read(size)
                blob = payload[6:] if payload.startswith(b"Exif\x00\x00") else payload
                orientation = _tiff_orientation(blob)
                break
            elif tag in {b"VP8 ", b"VP8L"} and width is None:
                prefix = handle.read(min(size, 32))
                remaining = size - len(prefix)
                if remaining > 0:
                    handle.seek(remaining, 1)
                size_pair = _vp8_size(prefix) if tag == b"VP8 " else _vp8l_size(prefix)
                if size_pair:
                    width, height = size_pair
                if not exif_expected:
                    break
            else:
                handle.seek(size, 1)
            if size % 2 == 1:
                handle.seek(1, 1)

    return WebpDetails(width=width, height=height, animated=animated, orientation=orientation)


def read_orientation(path: Path) -> int | None:
    suffix = path.suffix.lower()
    try:
        if suffix in {".jpg", ".jpeg", ".jpe", ".jfif"}:
            return _jpeg_orientation(path)
        if suffix in {".png", ".apng"}:
            return _png_orientation(path)
        if suffix in {".tif", ".tiff"}:
            return _tiff_file_orientation(path)
    except OSError:
        return None
    return None


def apply_orientation(width: int, height: int, orientation: int | None) -> tuple[int, int]:
    if orientation in SWAPPED_ORIENTATIONS:
        return height, width
    return width, height


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


def gif_is_animated(frame_count: int, duration_seconds: float) -> bool:
    if frame_count > 1:
        return True
    if frame_count == 1:
        return False
    return duration_seconds > SYNTHETIC_STILL_DURATION


def image_is_animated(
    path: Path,
    fmt: dict,
    frame_count: int,
    duration_seconds: float,
    webp_animated: bool,
) -> bool:
    if webp_animated or frame_count > 1:
        return True
    format_name = str(fmt.get("format_name") or "").split(",")[0]
    if format_name == "apng":
        return True
    # A still JPEG is reported as one synthetic frame (~0.04s). Animated AVIF
    # and similar containers report a longer duration when frame count is absent.
    if path.suffix.lower() in {".avif", ".webp"} and frame_count != 1:
        return duration_seconds > SYNTHETIC_STILL_DURATION
    return False


def analyze_media(path: Path) -> MediaInfo:
    probe = run_ffprobe(path)
    stream = pick_video_stream(probe.get("streams", []))
    if not stream:
        raise RuntimeError(f"No visual stream found in {path}")

    width = parse_int(stream.get("width"))
    height = parse_int(stream.get("height"))
    kind = media_kind(path)
    webp = WebpDetails()
    if path.suffix.lower() == ".webp":
        webp = read_webp_details(path)
        if width <= 0 or height <= 0:
            width = webp.width or 0
            height = webp.height or 0

    if kind is MediaKind.VIDEO:
        orientation = None
    elif path.suffix.lower() == ".webp":
        orientation = webp.orientation
    else:
        orientation = read_orientation(path)
    width, height = apply_orientation(width, height, orientation)

    if width <= 0 or height <= 0:
        raise RuntimeError(f"Invalid dimensions for {path}: {width}x{height}")

    fmt = probe.get("format", {})
    duration_seconds = parse_float(fmt.get("duration"))
    if duration_seconds <= 0:
        duration_seconds = parse_float(stream.get("duration"))
    frame_count = parse_int(stream.get("nb_frames"))

    if kind is MediaKind.GIF:
        animated = gif_is_animated(frame_count, duration_seconds)
    elif kind is MediaKind.IMAGE:
        animated = image_is_animated(path, fmt, frame_count, duration_seconds, webp.animated)
    else:
        animated = False

    # Still images have no meaningful duration. ffprobe invents ~1/25s for a JPEG.
    if kind is not MediaKind.VIDEO and not animated:
        duration_seconds = 0.0

    estimated_size, size_source = estimate_size_bytes(
        path, width, height, duration_seconds, fmt, stream
    )

    return MediaInfo(
        path=path,
        width=width,
        height=height,
        duration_seconds=duration_seconds,
        estimated_size_bytes=estimated_size,
        size_source=size_source,
        kind=kind,
        frame_count=frame_count,
        animated=animated,
    )


def discover_media(root: Path, recursive: bool) -> list[Path]:
    if root.is_file():
        return [root] if root.suffix.lower() in MEDIA_EXTENSIONS else []

    pattern = "**/*" if recursive else "*"
    media = [
        path
        for path in root.glob(pattern)
        if path.is_file() and path.suffix.lower() in MEDIA_EXTENSIONS
    ]
    return sorted(media)


def group_media(items: list[MediaInfo]) -> dict[Category, list[MediaInfo]]:
    grouped: dict[Category, list[MediaInfo]] = {
        Category.WIDESCREEN: [],
        Category.SQUARE: [],
        Category.VERTICAL: [],
    }
    for item in items:
        grouped[item.category].append(item)

    for category in grouped:
        grouped[category].sort(
            key=lambda item: (item.resolution, item.estimated_size_bytes, item.path.name),
            reverse=True,
        )
    return grouped


def copy_or_move_media(
    grouped: dict[Category, list[MediaInfo]],
    output_dir: Path,
    move: bool,
) -> None:
    for category, items in grouped.items():
        category_dir = output_dir / category.value
        category_dir.mkdir(parents=True, exist_ok=True)
        for item in items:
            destination = category_dir / item.path.name
            if destination.resolve() == item.path.resolve():
                continue
            if destination.exists():
                raise FileExistsError(f"Destination already exists: {destination}")
            if move:
                shutil.move(str(item.path), destination)
            else:
                shutil.copy2(item.path, destination)


def _kind_summary(items: list[MediaInfo]) -> str:
    counts = {kind: 0 for kind in MediaKind}
    for item in items:
        counts[item.kind] += 1
    present = [kind for kind, count in counts.items() if count]
    if len(present) == 1:
        kind = present[0]
        return f"{counts[kind]} {kind.value}(s)"

    parts = [f"{counts[kind]} {kind.value}(s)" for kind in MediaKind if counts[kind]]
    total = len(items)
    noun = "file" if total == 1 else "files"
    return f"{total} {noun} ({', '.join(parts)})"


def print_report(grouped: dict[Category, list[MediaInfo]]) -> None:
    items = [item for group in grouped.values() for item in group]
    total_size = sum(item.estimated_size_bytes for item in items)

    print(f"Found {_kind_summary(items)}, estimated total size {human_size(total_size)}\n")

    for category in Category:
        group = grouped[category]
        category_size = sum(item.estimated_size_bytes for item in group)
        print(f"=== {category.value.upper()} ({len(group)}) — {human_size(category_size)} ===")
        if not group:
            print("  (none)")
            print()
            continue

        for index, item in enumerate(group, start=1):
            print(
                f"  {index:>2}. {item.path.name}\n"
                f"      {item.kind.value} | "
                f"{item.width}x{item.height} | "
                f"aspect {item.aspect_ratio:.2f} | "
                f"{format_timing(item)} | "
                f"{item.format_size()} ({item.size_source})"
            )
        print()
    sys.stdout.flush()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Analyze videos, images, and GIFs, estimate their size, sort by resolution, "
            "and group into widescreen, square, and vertical categories."
        )
    )
    parser.add_argument(
        "input",
        type=Path,
        help="Media file or directory containing videos, images, or GIFs",
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
        help="Copy or move sorted files into category subfolders",
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

    media_paths = discover_media(args.input, args.recursive)
    if not media_paths:
        print("No supported video, image, or GIF files found.")
        return 0

    analyzed: list[MediaInfo] = []
    errors: list[str] = []
    for path in media_paths:
        try:
            analyzed.append(analyze_media(path))
        except (RuntimeError, json.JSONDecodeError, OSError) as exc:
            errors.append(f"{path}: {exc}")

    if not analyzed:
        print("Could not analyze any files.", file=sys.stderr)
        for message in errors:
            print(message, file=sys.stderr)
        return 1

    grouped = group_media(analyzed)
    print_report(grouped)

    if args.output:
        copy_or_move_media(grouped, args.output, args.move)
        action = "Moved" if args.move else "Copied"
        print(f"{action} files into {args.output.resolve()}")

    if errors:
        print("Warnings:", file=sys.stderr)
        for message in errors:
            print(message, file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
