"""Human-readable and JSON reporting for sort runs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .categorize import Orientation, human_readable_duration, human_readable_size
from .sorter import SortResult


def _icon(orientation: Orientation) -> str:
    return {
        Orientation.WIDESCREEN: "▭",
        Orientation.SQUARE: "▢",
        Orientation.VERTICAL: "▯",
    }[orientation]


def format_text_report(result: SortResult, *, dry_run: bool, move: bool) -> str:
    """Build a readable summary of the planned/performed work."""
    lines: list[str] = []
    verb = "Would sort" if dry_run else ("Moved" if move else "Copied")

    counts = result.category_counts()
    sizes = result.category_sizes()
    total = len(result.planned)

    lines.append("=" * 60)
    lines.append("Resolution-Sorter report")
    lines.append("=" * 60)

    if total == 0:
        lines.append("No videos found to sort.")
    else:
        for orientation in Orientation:
            count = counts[orientation]
            size = human_readable_size(sizes[orientation])
            lines.append(
                f"  {_icon(orientation)} {orientation.value:<11} "
                f"{count:>4} file(s)   {size:>10}"
            )
        lines.append("-" * 60)
        lines.append(
            f"  {verb} {total} video(s), "
            f"{human_readable_size(result.total_size())} total"
        )

    if result.skipped:
        lines.append("")
        lines.append(f"Skipped {len(result.skipped)} non-video / unreadable file(s):")
        for path, reason in result.skipped:
            lines.append(f"  - {path.name}: {reason}")

    if result.errors:
        lines.append("")
        lines.append(f"Encountered {len(result.errors)} error(s):")
        for path, reason in result.errors:
            lines.append(f"  ! {path.name}: {reason}")

    return "\n".join(lines)


def format_detail_lines(result: SortResult) -> list[str]:
    """One line per planned video, for verbose output."""
    lines: list[str] = []
    for plan in result.planned:
        info = plan.info
        lines.append(
            f"  {info.path.name}  "
            f"[{info.width}x{info.height}, "
            f"{human_readable_size(plan.estimated_size)}, "
            f"{human_readable_duration(info.duration)}]  "
            f"-> {plan.orientation.value}/"
        )
    return lines


def build_json_report(result: SortResult, *, dry_run: bool, move: bool) -> dict:
    """Build a machine-readable representation of the run."""
    counts = result.category_counts()
    sizes = result.category_sizes()
    return {
        "dry_run": dry_run,
        "operation": "move" if move else "copy",
        "summary": {
            "total": len(result.planned),
            "total_size_bytes": result.total_size(),
            "categories": {
                orientation.value: {
                    "count": counts[orientation],
                    "size_bytes": sizes[orientation],
                }
                for orientation in Orientation
            },
        },
        "videos": [
            {
                "source": str(plan.info.path),
                "destination": str(plan.destination),
                "orientation": plan.orientation.value,
                "width": plan.info.width,
                "height": plan.info.height,
                "aspect_ratio": round(plan.info.aspect_ratio, 4),
                "size_bytes": plan.estimated_size,
                "duration_seconds": round(plan.info.duration, 3),
                "codec": plan.info.codec,
            }
            for plan in result.planned
        ],
        "skipped": [
            {"path": str(path), "reason": reason}
            for path, reason in result.skipped
        ],
        "errors": [
            {"path": str(path), "reason": reason}
            for path, reason in result.errors
        ],
    }


def write_json_report(result: SortResult, destination: Path, *, dry_run: bool, move: bool) -> None:
    payload = build_json_report(result, dry_run=dry_run, move=move)
    Path(destination).write_text(json.dumps(payload, indent=2), encoding="utf-8")
