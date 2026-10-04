"""Office/ODF/EPUB (zip containers): recompress embedded images and re-zip at maximum level."""

from __future__ import annotations

import zipfile
from pathlib import Path, PurePosixPath

from tinyfy.common import Options, Skip
from tinyfy.handlers import image

EXTS = {".docx", ".xlsx", ".pptx", ".odt", ".ods", ".odp", ".epub"}

MIN_IMAGE_BYTES = 20 * 1024


def run(src: Path, tmp: Path, opts: Options) -> Path:
    out = tmp / src.name
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zout:
        infos = zin.infolist()
        # ODF/EPUB require 'mimetype' to be the first entry, stored uncompressed
        infos.sort(key=lambda i: i.filename != "mimetype")
        for info in infos:
            data = zin.read(info)
            if info.filename == "mimetype":
                zout.writestr(info, data, compress_type=zipfile.ZIP_STORED)
                continue
            ext = PurePosixPath(info.filename).suffix.lower()
            if ext in image.EXTS and ext not in (".bmp", ".tif", ".tiff") and len(data) >= MIN_IMAGE_BYTES:
                try:
                    smaller = image.compress_bytes(data, ext, opts)
                    if len(smaller) < len(data):
                        data = smaller
                except Skip:
                    pass
                except Exception:
                    pass  # unreadable image: keep it as is
            zout.writestr(info.filename, data, compress_type=zipfile.ZIP_DEFLATED)
    return out
