"""tinyfy — compress any file, locally. Installed as `tiny` (and `tinyfy`).

    tiny photo.jpg video.mov report.pdf
    tiny -l high --max-dim 1920 photos/ --each
    tiny project/ -f zst                 # pack a folder -> project.tar.zst
    tiny report.pdf -o out/small.pdf     # write to an exact file
    tiny -x project.tar.zst              # extract
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from tinyfy import __version__
from tinyfy.common import LEVELS, Options, Skip, human, path_size
from tinyfy.handlers import generic, pick

FORMATS = ("xz", "gz", "zst", "zip")


@dataclass
class Task:
    src: Path
    out_dir: Path
    mirror: bool = False      # always leave a file in out_dir (copy the original if it can't be shrunk)
    smart_only: bool = False  # --each: never turn unknown files into .xz
    out_file: Path | None = None  # -o points at an exact file


@dataclass
class Result:
    src: Path
    status: str            # ok | copied | skip | error
    before: int = 0
    after: int = 0
    out: Path | None = None
    note: str = ""


def _prog_name() -> str:
    name = Path(sys.argv[0]).stem
    return name if name in ("tiny", "tinyfy") else "tiny"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog=_prog_name(),
        description="Compress any file: images, PDFs, video, audio, Office documents, folders and everything else.",
        epilog=__doc__.split("\n", 2)[2],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("paths", nargs="+", type=Path, help="files or folders to compress")
    p.add_argument("-l", "--level", choices=LEVELS, default="medium",
                   help="compression level: low (best quality), medium (default), high (smallest)")
    p.add_argument("-o", "--output",
                   help="output file (e.g. out/small.pdf) or output folder (e.g. out/ or an existing folder); "
                        "default: next to the original with a .min suffix")
    p.add_argument("-f", "--format", dest="fmt", choices=FORMATS,
                   help="lossless format for other files/folders "
                        "(default: taken from the -o extension if given, otherwise xz)")
    p.add_argument("--lossless", action="store_true",
                   help="lossless only: keep every byte, output is .xz/.zst/...")
    p.add_argument("--each", action="store_true",
                   help="for folders: compress each file inside instead of packing, into <name>.min/")
    p.add_argument("--max-dim", type=int, metavar="PX", help="downscale images/videos so the longest side is <= PX")
    p.add_argument("--codec", dest="video_codec", choices=("h264", "h265"), default="h264",
                   help="video codec (h265 is smaller but slower and less compatible)")
    p.add_argument("--in-place", action="store_true", help="replace the original (only when the result is smaller)")
    p.add_argument("--force", action="store_true", help="keep the result even if it is not smaller")
    p.add_argument("-j", "--jobs", type=int, default=min(4, os.cpu_count() or 1), help="files to process in parallel")
    p.add_argument("-x", "--extract", action="store_true", help="extract .xz/.gz/.zst/.bz2/.zip/.tar.* files")
    p.add_argument("-V", "--version", action="version", version=f"%(prog)s {__version__}")
    return p


def output_file(args: argparse.Namespace, parser: argparse.ArgumentParser) -> Path | None:
    """-o is a file if it has an extension, doesn't end with '/' and isn't an existing folder."""
    raw = args.output
    args.output = Path(raw) if raw else None
    out = args.output
    if out is None or raw.endswith(("/", os.sep)) or out.is_dir() or not out.suffix:
        return None
    if len(args.paths) != 1 or args.each:
        parser.error("when -o is a file, exactly one input is allowed (and no --each)")
    if args.in_place:
        parser.error("-o cannot be combined with --in-place")
    return out


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    out_file = output_file(args, parser)
    if args.extract:
        return _extract(args, out_file)

    fmt = args.fmt
    if fmt is None and out_file is not None:
        # -o project.tar.zst / log.gz -> take the format from the extension
        fmt = {".tgz": "gz", ".tzst": "zst"}.get(out_file.suffix.lower(), out_file.suffix.lower().lstrip("."))
    opts = Options(level=args.level, max_dim=args.max_dim, video_codec=args.video_codec,
                   fmt=fmt if fmt in FORMATS else "xz", lossless=args.lossless)
    tasks: list[Task] = []
    missing = False
    for p in args.paths:
        if not p.exists():
            print(f"✗ not found: {p}", file=sys.stderr)
            missing = True
            continue
        if p.is_dir() and args.each:
            root = args.output or p.parent / f"{p.name}.min"
            if args.in_place:
                root = p
            for f in sorted(p.rglob("*")):
                if f.is_file():
                    tasks.append(Task(f, root / f.relative_to(p).parent, mirror=not args.in_place, smart_only=True))
        else:
            tasks.append(Task(p, args.output or p.parent, out_file=out_file))

    if not tasks:
        return 1

    def work(t: Task) -> Result:
        r = process(t, opts, in_place=args.in_place and not t.src.is_dir(), force=args.force)
        report(r)
        return r

    with ThreadPoolExecutor(max(1, args.jobs)) as pool:
        results = list(pool.map(work, tasks))
    summary(results)
    return 1 if missing or any(r.status == "error" for r in results) else 0


def process(t: Task, opts: Options, in_place: bool, force: bool) -> Result:
    src = t.src
    before = path_size(src)
    res = Result(src, "error", before=before)
    try:
        handler = pick(src, opts, smart_only=t.smart_only)
        if handler is None:
            raise Skip("no dedicated compressor for this type")
        with tempfile.TemporaryDirectory(prefix="tinyfy-") as tmp:
            produced = handler(src, Path(tmp), opts)
            after = produced.stat().st_size
            if after >= before and not force:
                raise Skip(f"result is not smaller ({human(after)})")
            dest = t.out_file or _destination(src, produced.name, t.out_dir, in_place)
            if dest.is_dir():
                raise IsADirectoryError(f"{dest} is a folder, refusing to overwrite it")
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(produced, dest)  # overwrites a previous result
            if in_place and dest != src:
                src.unlink()  # extension changed (e.g. .mov -> .mp4): remove the original
        res.status, res.after, res.out = "ok", after, dest
    except Skip as e:
        res.status, res.after, res.note = "skip", before, str(e)
        if t.mirror:
            dest = t.out_dir / src.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            res.status, res.out = "copied", dest
    except Exception as e:  # noqa: BLE001 — one bad file must not stop the whole run
        res.note = f"{type(e).__name__}: {e}"
    return res


def _destination(src: Path, name: str, out_dir: Path, in_place: bool) -> Path:
    if in_place:
        return src.with_name(name)
    dest = out_dir / name
    if dest.resolve() == src.resolve():
        # same folder, same name -> insert .min before the extension
        stem, dot, ext = name.rpartition(".")
        dest = out_dir / (f"{stem}.min.{ext}" if dot else f"{name}.min")
    return dest


def report(r: Result) -> None:
    if r.status == "ok":
        saved = 100 * (1 - r.after / r.before) if r.before else 0
        print(f"✓ {r.src}  {human(r.before)} → {human(r.after)}  (-{saved:.0f}%)  ⇒ {r.out}")
    elif r.status == "copied":
        print(f"= {r.src}  copied unchanged ({r.note})")
    elif r.status == "skip":
        print(f"- {r.src}  skipped: {r.note}")
    else:
        print(f"✗ {r.src}  error: {r.note}", file=sys.stderr)


def summary(results: list[Result]) -> None:
    if len(results) < 2:
        return
    before = sum(r.before for r in results if r.status in ("ok", "copied"))
    after = sum(r.after for r in results if r.status in ("ok", "copied"))
    counts = {s: sum(r.status == s for r in results) for s in ("ok", "copied", "skip", "error")}
    saved = 100 * (1 - after / before) if before else 0
    print(f"\nTotal: {counts['ok']} compressed, {counts['copied'] + counts['skip']} unchanged/skipped, "
          f"{counts['error']} failed — {human(before)} → {human(after)} (-{saved:.0f}%)")


def _extract(args: argparse.Namespace, out_file: Path | None) -> int:
    code = 0
    for p in args.paths:
        try:
            if out_file:
                out = generic.extract(p, out_file.parent, out_file)
            else:
                out = generic.extract(p, args.output or p.parent)
            print(f"✓ {p} ⇒ {out}")
        except Exception as e:  # noqa: BLE001
            print(f"✗ {p}  error: {e}", file=sys.stderr)
            code = 1
    return code


if __name__ == "__main__":
    raise SystemExit(main())
