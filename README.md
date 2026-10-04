# tinyfy

Compress any file from the command line, entirely on your machine. Each file type gets the method that suits it best:

| Type | Extensions | How |
| --- | --- | --- |
| Images | jpg, png, webp, bmp, tiff | Re-encode with Pillow, optimize PNG (palette reduction at `high`), BMP → PNG |
| PDF | pdf | Ghostscript (`/printer`, `/ebook`, `/screen`) |
| Video | mp4, mov, mkv, avi, webm, ... | ffmpeg → MP4 H.264 (or H.265 with `--codec h265`) |
| Audio | mp3, wav, flac, m4a, ogg, ... | ffmpeg (wav/flac → FLAC at `low`, MP3 otherwise) |
| Office | docx, xlsx, pptx, odt, epub, ... | Recompress embedded images and re-zip at maximum level |
| Everything else | any file or folder | Lossless: xz (default), gz, zst, zip; folders → `tar.*` |

If the compressed result is **not smaller** than the original, the original is kept (unless you pass `--force`).
Originals are never overwritten unless you pass `--in-place`.

## Installation

```bash
pipx install tinyfy        # recommended
pip install tinyfy         # or inside a virtualenv
```

This installs the `tiny` command (`tinyfy` also works as an alias).

Requires Python 3.10+. Images and lossless compression work out of the box. Other formats need these programs on your `PATH`:

| Program | Needed for | Debian/Ubuntu | macOS | Windows |
| --- | --- | --- | --- | --- |
| ffmpeg | video, audio | `sudo apt install ffmpeg` | `brew install ffmpeg` | `winget install Gyan.FFmpeg` |
| Ghostscript | PDF | `sudo apt install ghostscript` | `brew install ghostscript` | installer from [ghostscript.com](https://ghostscript.com/releases/gsdnld.html) |
| zstd | `-f zst` | `sudo apt install zstd` | `brew install zstd` | release from [facebook/zstd](https://github.com/facebook/zstd/releases) |

If a program is missing, files that need it are skipped with a message; everything else still runs.

## Usage

```bash
tiny photo.jpg video.mov report.pdf           # → photo.min.jpg, video.mp4, report.min.pdf
tiny -l high --max-dim 1920 *.jpg -o small/   # stronger compression, downscale, save into small/
tiny report.pdf -o out/small.pdf              # write to an exact file
tiny project/                                 # pack a folder → project.tar.xz
tiny project/ -o project.tar.zst              # format taken from the extension
tiny photos/ --each                           # compress each file → photos.min/ (same structure)
tiny report.docx --lossless                   # keep every byte → report.docx.xz
tiny -x project.tar.zst                       # extract
```

### Options

| Option | Description |
| --- | --- |
| `-l, --level low\|medium\|high` | `low` keeps the best quality, `high` gives the smallest files. Default: `medium`. |
| `-o PATH` | A path with an extension (`out/small.pdf`, `project.tar.zst`) is written as that exact file. A path ending in `/`, or an existing folder, is used as the output folder. |
| `-f xz\|gz\|zst\|zip` | Lossless format for other files and folders. Defaults to the `-o` extension, otherwise `xz`. |
| `--lossless` | Use lossless compression for every file, so the original can be restored byte for byte. |
| `--each` | For folders: compress each file inside instead of packing them into one archive. Files without a dedicated compressor are copied unchanged. |
| `--max-dim PX` | Downscale images and videos so the longest side is at most `PX`. |
| `--codec h264\|h265` | Video codec. H.265 is smaller but slower to encode and less widely supported. |
| `--in-place` | Replace the original when the result is smaller. |
| `--force` | Keep the result even when it is not smaller. |
| `-j N` | Number of files processed in parallel. |
| `-x, --extract` | Extract `.xz`, `.gz`, `.zst`, `.bz2`, `.zip` and `.tar.*` files. |

Re-running a command overwrites the previous output.

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/python -m unittest discover tests
```

## License

MIT
