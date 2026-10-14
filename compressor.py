"""Image compression logic — independent of the GUI."""

import io
import re
import shutil
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageOps

RASTER_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".avif"}
COPY_THROUGH_EXTS = {".svg"}  # vector formats we don't raster-compress, just preserve
SUPPORTED_EXTS = RASTER_EXTS | COPY_THROUGH_EXTS
OUTPUT_DIR_NAME = "compressed"

# Pillow format name -> output file extension
FORMAT_EXT = {"JPEG": ".jpg", "PNG": ".png", "WEBP": ".webp", "AVIF": ".avif"}
MIN_QUALITY = 5  # floor when searching for a target file size


@dataclass
class Options:
    quality: int = 80          # 1–100, upper bound when a target size is set
    out_format: str = "keep"   # keep | jpeg | png | webp | avif
    target_kb: int = 0         # 0 = no size target; otherwise aim under this many KB
    max_width: int = 0         # 0 means no resizing
    max_height: int = 0
    strip_metadata: bool = True
    seo_rename: bool = False   # slugify output filenames (My Photo (1).JPG -> my-photo-1.jpg)


def slugify(stem: str) -> str:
    """Turn a filename stem into an SEO-friendly slug."""
    s = unicodedata.normalize("NFKC", stem).lower()
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"[^\w\-]", "", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s or "image"


@dataclass
class Result:
    path: Path
    output: Path | None
    original_size: int
    compressed_size: int
    error: str | None = None

    @property
    def saved(self) -> int:
        return self.original_size - self.compressed_size


def collect_images(paths: list[str]) -> tuple[list[Path], list[Path]]:
    """Split a list of files/folders into supported images and skipped files."""
    images: list[Path] = []
    skipped: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file() and OUTPUT_DIR_NAME not in f.parts:
                    if f.suffix.lower() in SUPPORTED_EXTS:
                        images.append(f)
                    else:
                        skipped.append(f)
        elif p.is_file():
            if p.suffix.lower() in SUPPORTED_EXTS:
                images.append(p)
            else:
                skipped.append(p)
    # Deduplicate while preserving order
    seen: set[Path] = set()
    unique = []
    for f in images:
        if f not in seen:
            seen.add(f)
            unique.append(f)
    return unique, skipped


def _resize(img: Image.Image, max_w: int, max_h: int) -> Image.Image:
    if max_w <= 0 and max_h <= 0:
        return img
    w, h = img.size
    scale = min(
        (max_w / w) if max_w > 0 else 1.0,
        (max_h / h) if max_h > 0 else 1.0,
    )
    if scale >= 1.0:
        return img
    return img.resize((max(1, round(w * scale)), max(1, round(h * scale))), Image.LANCZOS)


def _output_format(src_ext: str, out_format: str) -> str:
    """Resolve the Pillow format name for this file."""
    if out_format == "keep":
        return {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG",
                "webp": "WEBP", "avif": "AVIF"}[src_ext.lstrip(".")]
    return {"jpeg": "JPEG", "png": "PNG", "webp": "WEBP", "avif": "AVIF"}[out_format]


def _prepare_mode(img: Image.Image, fmt: str) -> Image.Image:
    if fmt == "JPEG":
        if img.mode != "RGB":
            return img.convert("RGB")
    elif img.mode in ("P", "CMYK"):
        has_alpha = "transparency" in img.info or img.mode == "P"
        return img.convert("RGBA" if has_alpha else "RGB")
    return img


def _encode(img: Image.Image, fmt: str, quality: int, meta: dict) -> bytes:
    buf = io.BytesIO()
    kwargs: dict = dict(meta)
    if fmt == "JPEG":
        kwargs.update(quality=quality, optimize=True, progressive=True)
    elif fmt == "WEBP":
        kwargs.update(quality=quality, method=6)
    elif fmt == "AVIF":
        kwargs.update(quality=quality, speed=6)
    else:  # PNG — quality doesn't apply
        kwargs.update(optimize=True)
    img.save(buf, format=fmt, **kwargs)
    return buf.getvalue()


def compress_one(src: Path, opts: Options) -> Result:
    original_size = src.stat().st_size
    ext = src.suffix.lower()
    try:
        stem = slugify(src.stem) if opts.seo_rename else src.stem

        if ext in COPY_THROUGH_EXTS:
            out_dir = src.parent / OUTPUT_DIR_NAME
            out_dir.mkdir(exist_ok=True)
            out_path = out_dir / (stem + ext)
            shutil.copy2(src, out_path)
            return Result(src, out_path, original_size, out_path.stat().st_size)

        with Image.open(src) as opened:
            # Bake EXIF rotation into the pixels (it's lost once metadata is stripped)
            img = ImageOps.exif_transpose(opened)
            img = _resize(img, opts.max_width, opts.max_height)

            fmt = _output_format(ext, opts.out_format)
            img = _prepare_mode(img, fmt)

            meta: dict = {}
            if not opts.strip_metadata:
                if opened.info.get("exif"):
                    meta["exif"] = opened.info["exif"]
                if opened.info.get("icc_profile"):
                    meta["icc_profile"] = opened.info["icc_profile"]

            data = _encode(img, fmt, opts.quality, meta)

            # Size target: search for the highest quality that fits (lossy formats only)
            target = opts.target_kb * 1024
            if target and fmt in ("JPEG", "WEBP", "AVIF") and len(data) > target:
                lo, hi = MIN_QUALITY, opts.quality
                best = None
                while lo <= hi:
                    mid = (lo + hi) // 2
                    attempt = _encode(img, fmt, mid, meta)
                    if len(attempt) <= target:
                        best = attempt
                        lo = mid + 1
                    else:
                        hi = mid - 1
                data = best if best is not None else _encode(img, fmt, MIN_QUALITY, meta)

            out_dir = src.parent / OUTPUT_DIR_NAME
            out_dir.mkdir(exist_ok=True)
            out_path = out_dir / (stem + FORMAT_EXT[fmt])
            out_path.write_bytes(data)

        return Result(src, out_path, original_size, len(data))
    except Exception as e:  # a single failure shouldn't stop the whole batch
        return Result(src, None, original_size, original_size, error=str(e))


def compress_all(files: list[Path], opts: Options, progress=None) -> list[Result]:
    """Compress files sequentially, reporting progress via progress(i, total, result)."""
    results = []
    total = len(files)
    for i, f in enumerate(files, 1):
        r = compress_one(f, opts)
        results.append(r)
        if progress:
            progress(i, total, r)
    return results


def format_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return f"{n} B"
