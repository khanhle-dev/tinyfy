"""PDF: rewrite through Ghostscript, downsampling embedded images by level."""

from __future__ import annotations

from pathlib import Path

from tinyfy.common import Options, need_tool, run as run_cmd

EXTS = {".pdf"}

PRESET = {"low": "/printer", "medium": "/ebook", "high": "/screen"}


def run(src: Path, tmp: Path, opts: Options) -> Path:
    gs = need_tool("gs", "gswin64c", "gswin32c")
    out = tmp / src.name
    run_cmd([
        gs, "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.5",
        f"-dPDFSETTINGS={PRESET[opts.level]}",
        "-dDetectDuplicateImages=true", "-dCompressFonts=true", "-dSubsetFonts=true",
        "-dNOPAUSE", "-dBATCH", "-dQUIET", "-dSAFER",
        f"-sOutputFile={out}", str(src),
    ])
    return out
