# Resolution-Sorter

Sort a folder of videos by **resolution and orientation**. Resolution-Sorter
probes every video, estimates its size, and files it into one of three
categories:

| Category       | Shape          | Typical examples                         |
| -------------- | -------------- | ---------------------------------------- |
| **widescreen** | wider than tall | movies, YouTube, 16:9 / 21:9 footage    |
| **square**     | ~1:1 (±10%)     | Instagram posts, 1:1 social clips        |
| **vertical**   | taller than wide | phone videos, Reels, TikTok, Stories    |

It can optionally nest a resolution sub-folder (`1080p`, `4K`, …) inside each
category, and prints a per-category size report.

```
sorted/
├── widescreen/
│   ├── 4K/4k_landscape.mkv
│   └── 1080p/movie_landscape.mp4
├── square/
│   └── 720p/insta_square.mov
└── vertical/
    └── 1080p/phone_portrait.mp4
```

## Requirements

- **Python 3.9+**
- **FFmpeg** (the `ffprobe` executable specifically) on your `PATH`.
  - Debian/Ubuntu: `sudo apt install ffmpeg`
  - macOS: `brew install ffmpeg`
  - Windows: <https://ffmpeg.org/download.html>

There are **no third-party Python dependencies** — only the standard library.

## Installation

Run it directly from a clone:

```bash
python -m resolution_sorter --help
```

…or install it so the `resolution-sorter` command is available everywhere:

```bash
pip install .
resolution-sorter --help
```

## Usage

```bash
# Copy videos from ./clips into ./clips/sorted, grouped by orientation
resolution-sorter ./clips

# Preview what would happen without touching any files
resolution-sorter ./clips --dry-run --verbose

# Move (not copy) into a chosen output folder, scanning sub-directories
resolution-sorter ./clips -o ./organized --move --recursive

# Add a resolution sub-folder (1080p, 4K, ...) inside each category
resolution-sorter ./clips --by-resolution

# Write a machine-readable JSON report
resolution-sorter ./clips --report report.json
```

### Example output

```
============================================================
Resolution-Sorter report
============================================================
  ▭ widescreen     2 file(s)      83.8 KB
  ▢ square         1 file(s)      25.6 KB
  ▯ vertical       1 file(s)      23.0 KB
------------------------------------------------------------
  Copied 4 video(s), 132.4 KB total
```

## Options

| Option                 | Description                                                        |
| ---------------------- | ------------------------------------------------------------------ |
| `source`               | Directory (or single file) containing videos to sort.              |
| `-o, --output DIR`     | Destination directory (default: a `sorted/` folder in the source). |
| `--move` / `--copy`    | Move files or copy them (copy is the default).                     |
| `-r, --recursive`      | Recurse into sub-directories of the source.                        |
| `-n, --dry-run`        | Show the plan without modifying anything.                          |
| `--by-resolution`      | Add a resolution sub-folder inside each category.                  |
| `--square-tolerance T` | How close to 1:1 counts as square (default `0.10`, i.e. ±10%).     |
| `--overwrite`          | Overwrite existing destination files (otherwise auto-renamed).     |
| `--report PATH`        | Write a JSON report to `PATH`.                                     |
| `-v, --verbose`        | Print a line for every video processed.                            |

## How it works

1. **Discover** – walk the source folder for known video extensions
   (`.mp4`, `.mov`, `.mkv`, `.webm`, `.avi`, …).
2. **Probe** – call `ffprobe` to read each file's width, height, duration,
   bitrate and codec.
3. **Classify** – compare the aspect ratio to decide widescreen / square /
   vertical (square = within `--square-tolerance` of 1:1).
4. **Estimate size** – use the real file size, falling back to
   `bitrate × duration` when the on-disk size is unavailable.
5. **Sort** – copy or move each file into its category folder, auto-renaming on
   collisions so nothing is overwritten by accident.

## Library use

The core pieces are importable:

```python
from resolution_sorter import probe_video, classify

info = probe_video("clip.mp4")
print(info.width, info.height, classify(info.width, info.height))
```

## Development & tests

```bash
pip install pytest
pytest
```

The suite includes pure unit tests plus an end-to-end test that generates real
videos with `ffmpeg` (automatically skipped if FFmpeg is not installed).

## License

MIT
