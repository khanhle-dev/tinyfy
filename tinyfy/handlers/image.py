"""Images: re-encode JPEG/WebP by quality, optimize PNG (lossy at high), BMP -> PNG, TIFF -> deflate."""

from __future__ import annotations

import io
from pathlib import Path

from tinyfy.common import Options, Skip

EXTS = {".jpg", ".jpeg", ".jfif", ".png", ".webp", ".bmp", ".tif", ".tiff"}

QUALITY = {"low": 85, "medium": 75, "high": 60}


def _pil():
    try:
        from PIL import Image, ImageOps
    except ImportError:
        raise Skip("install Pillow (pip install Pillow) to compress images")
    return Image, ImageOps


def compress_bytes(data: bytes, ext: str, opts: Options) -> bytes:
    """Compress an image in memory, keeping its format. Used for single files and images inside Office files."""
    Image, ImageOps = _pil()
    ext = ext.lower()
    with Image.open(io.BytesIO(data)) as src:
        if getattr(src, "n_frames", 1) > 1:
            raise Skip("animated/multi-page image")
        icc = src.info.get("icc_profile")
        im = ImageOps.exif_transpose(src)
        if opts.max_dim:
            im.thumbnail((opts.max_dim, opts.max_dim), Image.LANCZOS)

        out = io.BytesIO()
        q = QUALITY[opts.level]
        if ext in (".jpg", ".jpeg", ".jfif"):
            if im.mode not in ("RGB", "L"):
                im = im.convert("RGB")
            im.save(out, "JPEG", quality=q, optimize=True, progressive=True, icc_profile=icc)
        elif ext == ".webp":
            im.save(out, "WEBP", quality=q, method=6, icc_profile=icc)
        elif ext in (".png", ".bmp"):
            if opts.level == "high" and im.mode not in ("P", "L", "1"):
                if im.mode not in ("RGB", "RGBA"):
                    im = im.convert("RGBA")
                im = im.quantize(256, method=Image.Quantize.FASTOCTREE)
            im.save(out, "PNG", optimize=True, icc_profile=icc)
        elif ext in (".tif", ".tiff"):
            im.save(out, "TIFF", compression="tiff_adobe_deflate", icc_profile=icc)
        else:
            raise Skip(f"unsupported image type {ext}")
        return out.getvalue()


def run(src: Path, tmp: Path, opts: Options) -> Path:
    ext = src.suffix.lower()
    # BMP is uncompressed -> save as PNG (lossless at low/medium)
    out = tmp / (src.stem + ".png" if ext == ".bmp" else src.name)
    out.write_bytes(compress_bytes(src.read_bytes(), ext, opts))
    return out
