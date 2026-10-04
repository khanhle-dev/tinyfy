"""Shared types and helpers used by the CLI and all handlers."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

LEVELS = ("low", "medium", "high")


@dataclass(frozen=True)
class Options:
    level: str = "medium"          # low = best quality, high = smallest
    max_dim: int | None = None     # longest side (px) for images/videos
    video_codec: str = "h264"      # h264 | h265
    fmt: str = "xz"                # lossless format: xz | gz | zst | zip
    lossless: bool = False         # lossless compression only


class Skip(Exception):
    """The file should not or cannot be compressed (already compressed, missing tool, ...)."""


def need_tool(name: str, *alternatives: str) -> str:
    """Find an external program, trying alternative names (e.g. Ghostscript is gswin64c on Windows)."""
    for candidate in (name, *alternatives):
        path = shutil.which(candidate)
        if path:
            return path
    raise Skip(f"install '{name}' to compress this file type")


def run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout).strip().splitlines()
        raise RuntimeError(msg[-1] if msg else f"{Path(cmd[0]).name} failed (exit code {proc.returncode})")


def path_size(path: Path) -> int:
    if path.is_dir():
        return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return path.stat().st_size


def human(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024:
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"
