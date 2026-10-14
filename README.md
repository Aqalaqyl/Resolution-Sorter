# Resolution-Sorter

Analyze videos, images, and GIFs, estimate their size, sort by resolution, and group them into **widescreen**, **square**, and **vertical** categories.

## Requirements

- Python 3.10+
- [ffmpeg](https://ffmpeg.org/) (uses `ffprobe` for metadata)

## Usage

Analyze media in a directory:

```bash
python3 sort_videos.py /path/to/media
```

Search recursively:

```bash
python3 sort_videos.py /path/to/media -r
```

Copy sorted files into category folders:

```bash
python3 sort_videos.py /path/to/media -o ./sorted
```

Move instead of copy:

```bash
python3 sort_videos.py /path/to/media -o ./sorted --move
```

## Supported files

| Kind | Extensions |
|------|------------|
| Video | `.mp4`, `.mkv`, `.avi`, `.mov`, `.wmv`, `.flv`, `.webm`, `.m4v`, `.mpeg`, `.mpg`, `.3gp`, `.ts`, `.mts`, `.m2ts` |
| Image | `.jpg`, `.jpeg`, `.png`, `.bmp`, `.tif`, `.tiff`, `.webp`, `.avif`, `.heic`, `.heif`, `.apng` |
| GIF | `.gif` (still and animated) |

JPEG, PNG, TIFF, and WebP files are categorized using display dimensions. EXIF orientation is applied, so a portrait photo stored as a landscape JPEG is grouped as vertical.

Animated GIFs keep their duration and frame count. Still images are labeled `still` instead of the short duration ffprobe invents for a single frame. Animated WebP files are sized from the file header when ffprobe cannot decode the animation.

## Categories

| Category | Rule |
|----------|------|
| **Widescreen** | Width is greater than height (aspect ratio > 1.05) |
| **Square** | Width and height are nearly equal (aspect ratio within ±5% of 1:1) |
| **Vertical** | Height is greater than width (aspect ratio < 0.95) |

Files within each category are sorted by total pixel count (resolution), highest first.

## Size estimation

The tool estimates file size using the best available source:

1. Actual file size on disk
2. Size from container metadata
3. Bitrate × duration
4. Resolution-based heuristic (fallback)

Still images use the size on disk. They do not have a playback duration, so the bitrate and resolution fallbacks are not used for them.

## Example output

```
Found 5 files (2 video(s), 2 image(s), 1 gif(s)), estimated total size 156.78 KB

=== WIDESCREEN (3) — 132.09 KB ===
   1. widescreen.mp4
      video | 1920x1080 | aspect 1.78 | 2s | 87.65 KB (file)
   2. photo.jpg
      image | 1920x1080 | aspect 1.78 | still | 33.33 KB (file)
   3. anim.gif
      gif | 640x360 | aspect 1.78 | 1s · 10 frames | 11.11 KB (file)

=== SQUARE (1) — 12.34 KB ===
   1. square.png
      image | 1080x1080 | aspect 1.00 | still | 12.34 KB (file)

=== VERTICAL (1) — 12.35 KB ===
   1. portrait.jpg
      image | 1080x1920 | aspect 0.56 | still | 12.35 KB (file)
```
