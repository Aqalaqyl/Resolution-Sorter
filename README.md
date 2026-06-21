# Resolution-Sorter

Analyze video files, estimate their size, sort by resolution, and group them into **widescreen**, **square**, and **vertical** categories.

## Requirements

- Python 3.10+
- [ffmpeg](https://ffmpeg.org/) (uses `ffprobe` for metadata)

## Usage

Analyze videos in a directory:

```bash
python3 sort_videos.py /path/to/videos
```

Search recursively:

```bash
python3 sort_videos.py /path/to/videos -r
```

Copy sorted videos into category folders:

```bash
python3 sort_videos.py /path/to/videos -o ./sorted
```

Move instead of copy:

```bash
python3 sort_videos.py /path/to/videos -o ./sorted --move
```

## Categories

| Category | Rule |
|----------|------|
| **Widescreen** | Width is greater than height (aspect ratio > 1.05) |
| **Square** | Width and height are nearly equal (aspect ratio within ±5% of 1:1) |
| **Vertical** | Height is greater than width (aspect ratio < 0.95) |

Videos within each category are sorted by total pixel count (resolution), highest first.

## Size estimation

The tool estimates file size using the best available source:

1. Actual file size on disk
2. Size from container metadata
3. Bitrate × duration
4. Resolution-based heuristic (fallback)

## Example output

```
Found 4 video(s), estimated total size 123.45 KB

=== WIDESCREEN (2) — 98.76 KB ===
   1. widescreen.mp4
      1920x1080 | aspect 1.78 | 2s | 87.65 KB (file)
   2. widescreen_small.mp4
      1280x720 | aspect 1.78 | 1s | 11.11 KB (file)

=== SQUARE (1) — 12.34 KB ===
   1. square.mp4
      1080x1080 | aspect 1.00 | 2s | 12.34 KB (file)

=== VERTICAL (1) — 12.35 KB ===
   1. vertical.mp4
      1080x1920 | aspect 0.56 | 2s | 12.35 KB (file)
```
