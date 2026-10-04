"""Lossless compression for any file/folder: xz, gz, zst, zip (folders -> tar.*)."""

from __future__ import annotations

import gzip
import lzma
import shutil
import tarfile
import zipfile
from pathlib import Path

from tinyfy.common import Options, Skip, need_tool, run as run_cmd

# Already compressed; compressing again gains almost nothing
ALREADY_COMPRESSED = {
    ".zip", ".gz", ".tgz", ".xz", ".txz", ".bz2", ".zst", ".7z", ".rar", ".lz4", ".br", ".lzma",
    ".gif", ".heic", ".heif", ".avif", ".jxl", ".apk", ".jar", ".dmg", ".whl",
}

XZ_PRESET = {"low": 3, "medium": 6, "high": 9 | lzma.PRESET_EXTREME}
GZ_LEVEL = {"low": 6, "medium": 9, "high": 9}
ZST_LEVEL = {"low": 3, "medium": 12, "high": 19}
ZIP_LEVEL = {"low": 6, "medium": 9, "high": 9}

CHUNK = 1 << 20


def run(src: Path, tmp: Path, opts: Options) -> Path:
    if src.is_dir():
        return _dir(src, tmp, opts)
    if src.suffix.lower() in ALREADY_COMPRESSED:
        raise Skip("already compressed")
    return _file(src, tmp, opts)


def _file(src: Path, tmp: Path, opts: Options) -> Path:
    fmt, lvl = opts.fmt, opts.level
    out = tmp / f"{src.name}.{fmt}"
    if fmt == "xz":
        with src.open("rb") as fi, lzma.open(out, "wb", preset=XZ_PRESET[lvl]) as fo:
            shutil.copyfileobj(fi, fo, CHUNK)
    elif fmt == "gz":
        with src.open("rb") as fi, gzip.open(out, "wb", compresslevel=GZ_LEVEL[lvl]) as fo:
            shutil.copyfileobj(fi, fo, CHUNK)
    elif fmt == "zst":
        _zstd(src, out, lvl)
    elif fmt == "zip":
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=ZIP_LEVEL[lvl]) as z:
            z.write(src, src.name)
    else:
        raise ValueError(fmt)
    return out


def _dir(src: Path, tmp: Path, opts: Options) -> Path:
    fmt, lvl = opts.fmt, opts.level
    if fmt == "zip":
        out = tmp / f"{src.name}.zip"
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=ZIP_LEVEL[lvl]) as z:
            for f in sorted(src.rglob("*")):
                z.write(f, f.relative_to(src.parent))
        return out
    out = tmp / f"{src.name}.tar.{fmt}"
    if fmt == "xz":
        with tarfile.open(out, "w:xz", preset=XZ_PRESET[lvl]) as t:
            t.add(src, src.name)
    elif fmt == "gz":
        with tarfile.open(out, "w:gz", compresslevel=GZ_LEVEL[lvl]) as t:
            t.add(src, src.name)
    elif fmt == "zst":
        plain = tmp / f"{src.name}.tar"
        with tarfile.open(plain, "w") as t:
            t.add(src, src.name)
        _zstd(plain, out, lvl)
        plain.unlink()
    else:
        raise ValueError(fmt)
    return out


def _zstd(src: Path, out: Path, lvl: str) -> None:
    zstd = need_tool("zstd")
    run_cmd([zstd, "-q", "-f", "-T0", "--long=27", f"-{ZST_LEVEL[lvl]}", str(src), "-o", str(out)])


# ---------- extraction ----------

def extract(src: Path, dest: Path, out_file: Path | None = None) -> Path:
    """Extract into folder dest (overwriting existing files). out_file: exact target for .xz/.gz/.zst/.bz2."""
    name = src.name.lower()
    dest.mkdir(parents=True, exist_ok=True)
    is_archive = name.endswith((".tar.zst", ".tzst")) or tarfile.is_tarfile(src) or zipfile.is_zipfile(src)
    if out_file and is_archive:
        raise Skip("this archive holds multiple files, -o must be a folder")
    if name.endswith((".tar.zst", ".tzst")):
        zstd = need_tool("zstd")
        plain = dest / (src.name.rsplit(".", 1)[0] + ".tmp.tar")
        run_cmd([zstd, "-d", "-q", "-f", "--long=31", str(src), "-o", str(plain)])
        try:
            _untar(plain, dest)
        finally:
            plain.unlink()
        return dest
    if tarfile.is_tarfile(src):
        _untar(src, dest)
        return dest
    if zipfile.is_zipfile(src):
        with zipfile.ZipFile(src) as z:
            z.extractall(dest)
        return dest
    out = out_file or dest / src.name.rsplit(".", 1)[0]
    if out.is_dir():
        raise IsADirectoryError(f"{out} is a folder, refusing to overwrite it")
    if name.endswith(".zst"):
        run_cmd([need_tool("zstd"), "-d", "-q", "-f", "--long=31", str(src), "-o", str(out)])
        return out
    opener = {".xz": lzma.open, ".lzma": lzma.open, ".gz": gzip.open}.get(src.suffix.lower())
    if opener is None:
        import bz2
        if src.suffix.lower() != ".bz2":
            raise Skip("unrecognized compression format")
        opener = bz2.open
    with opener(src, "rb") as fi, out.open("wb") as fo:
        shutil.copyfileobj(fi, fo, CHUNK)
    return out


def _untar(src: Path, dest: Path) -> None:
    with tarfile.open(src) as t:
        try:
            t.extractall(dest, filter="data")
        except TypeError:  # Python < 3.10.12 has no filter argument
            t.extractall(dest)
