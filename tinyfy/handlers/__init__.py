from __future__ import annotations

from pathlib import Path
from typing import Callable

from tinyfy.common import Options
from tinyfy.handlers import generic, image, media, office, pdf

Handler = Callable[[Path, Path, Options], Path]

_SMART: list[tuple[set[str], Handler]] = [
    (image.EXTS, image.run),
    (pdf.EXTS, pdf.run),
    (media.EXTS, media.run),
    (office.EXTS, office.run),
]


def pick(src: Path, opts: Options, smart_only: bool = False) -> Handler | None:
    """Pick a handler by extension. smart_only: return None instead of falling back to lossless."""
    if src.is_dir() or opts.lossless:
        return generic.run
    ext = src.suffix.lower()
    for exts, handler in _SMART:
        if ext in exts:
            return handler
    return None if smart_only else generic.run
