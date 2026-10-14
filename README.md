# Clickout Media Image Compressor

A macOS desktop app for batch-compressing images for the web, with SEO-friendly defaults.

## Run

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python app.py
```

If you get an error that tkinter is missing (Homebrew Python): `brew install python-tk@3.14`

## Features

- Drag & drop files or folders (folders are searched recursively)
- Output formats: Original, WebP, AVIF, JPG, PNG
- Target file size: 50 / 100 / 200 / 300 KB — quality is lowered automatically to fit
- Max width presets: 800 / 1200 / 1920 / 2560 px (aspect ratio preserved)
- Quality slider (upper bound when a target size is set)
- Strip metadata (EXIF)
- SEO filenames: `My Photo (1).JPG` → `my-photo-1.webp`
- One-click **SEO Preset**: WebP · ≤100 KB · max 1920 px · strip metadata · SEO filenames
- SVG files are copied through unchanged
- Output goes into a `compressed/` folder next to each original — originals are never touched

## Target size guide

| Image type | Target |
|---|---|
| Thumbnails | ≤ 50 KB |
| Content images | ≤ 100 KB |
| Hero images | ≤ 200 KB |

## Files

- `app.py` — GUI
- `widgets.py` — rounded pill buttons, segmented controls, toggles, slider (Canvas-based)
- `compressor.py` — compression logic, independent of the GUI
