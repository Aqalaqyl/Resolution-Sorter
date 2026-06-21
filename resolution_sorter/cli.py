"""Command-line interface for Resolution-Sorter."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional, Sequence

from . import __version__
from .categorize import DEFAULT_SQUARE_TOLERANCE
from .probe import ffprobe_available
from .report import (
    format_detail_lines,
    format_text_report,
    write_json_report,
)
from .sorter import build_plan, execute_plan


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="resolution-sorter",
        description=(
            "Sort videos by resolution: estimate their size and group them "
            "into widescreen, square and vertical categories."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  resolution-sorter ./clips\n"
            "  resolution-sorter ./clips -o ./sorted --move --recursive\n"
            "  resolution-sorter ./clips --by-resolution --report report.json\n"
        ),
    )
    parser.add_argument(
        "source",
        type=Path,
        help="Directory (or single file) containing videos to sort.",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Destination directory for the sorted folders "
        "(default: a 'sorted' folder inside the source directory).",
    )

    op_group = parser.add_mutually_exclusive_group()
    op_group.add_argument(
        "--move",
        action="store_true",
        help="Move files instead of copying them.",
    )
    op_group.add_argument(
        "--copy",
        action="store_true",
        help="Copy files (default behaviour).",
    )

    parser.add_argument(
        "-r",
        "--recursive",
        action="store_true",
        help="Search sub-directories of the source recursively.",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="Show what would happen without touching any files.",
    )
    parser.add_argument(
        "--by-resolution",
        action="store_true",
        help="Add a resolution sub-folder (e.g. 1080p) inside each category.",
    )
    parser.add_argument(
        "--square-tolerance",
        type=float,
        default=DEFAULT_SQUARE_TOLERANCE,
        metavar="T",
        help="How close to 1:1 an aspect ratio must be to count as square "
        f"(default: {DEFAULT_SQUARE_TOLERANCE}, i.e. +/-10%%).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing files at the destination instead of "
        "auto-renaming.",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        metavar="PATH",
        help="Write a JSON report to PATH.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Print a line for every video processed.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not ffprobe_available():
        print(
            "Error: 'ffprobe' was not found on your PATH.\n"
            "Resolution-Sorter relies on FFmpeg. Install it and try again:\n"
            "  - Debian/Ubuntu: sudo apt install ffmpeg\n"
            "  - macOS:         brew install ffmpeg\n"
            "  - Windows:       https://ffmpeg.org/download.html",
            file=sys.stderr,
        )
        return 2

    source: Path = args.source
    if not source.exists():
        print(f"Error: source path does not exist: {source}", file=sys.stderr)
        return 2

    if args.square_tolerance < 0:
        print("Error: --square-tolerance must be >= 0", file=sys.stderr)
        return 2

    if args.output is not None:
        output = args.output
    elif source.is_dir():
        output = source / "sorted"
    else:
        output = source.parent / "sorted"

    move = args.move  # --copy is the default when neither is given

    result = build_plan(
        source,
        output,
        recursive=args.recursive,
        square_tolerance=args.square_tolerance,
        by_resolution=args.by_resolution,
    )

    if args.verbose and result.planned:
        print("Planned actions:")
        for line in format_detail_lines(result):
            print(line)
        print()

    execute_plan(
        result,
        move=move,
        dry_run=args.dry_run,
        overwrite=args.overwrite,
    )

    print(format_text_report(result, dry_run=args.dry_run, move=move))

    if args.report is not None:
        write_json_report(result, args.report, dry_run=args.dry_run, move=move)
        print(f"\nJSON report written to {args.report}")

    if result.errors:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
