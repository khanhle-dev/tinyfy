"""Video and audio through ffmpeg."""

from __future__ import annotations

from pathlib import Path

from tinyfy.common import Options, need_tool, run as run_cmd

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".wmv", ".flv", ".webm", ".m4v", ".mpg", ".mpeg", ".3gp", ".ts"}
AUDIO_EXTS = {".mp3", ".wav", ".flac", ".aiff", ".aif", ".m4a", ".aac", ".ogg", ".opus", ".wma"}
EXTS = VIDEO_EXTS | AUDIO_EXTS

CRF = {
    "h264": {"low": 23, "medium": 26, "high": 30},
    "h265": {"low": 26, "medium": 28, "high": 32},
}
VIDEO_AUDIO_BITRATE = {"low": "160k", "medium": "128k", "high": "96k"}
AUDIO_BITRATE = {"low": "192k", "medium": "128k", "high": "96k"}
OPUS_BITRATE = {"low": "128k", "medium": "96k", "high": "64k"}


def _ffmpeg(args: list[str]) -> None:
    run_cmd([need_tool("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", *args])


def run(src: Path, tmp: Path, opts: Options) -> Path:
    if src.suffix.lower() in VIDEO_EXTS:
        return _video(src, tmp, opts)
    return _audio(src, tmp, opts)


def _video(src: Path, tmp: Path, opts: Options) -> Path:
    out = tmp / (src.stem + ".mp4")
    # yuv420p needs even dimensions
    vf = "scale=trunc(iw/2)*2:trunc(ih/2)*2"
    if opts.max_dim:
        d = opts.max_dim
        vf = f"scale='min(iw,{d})':'min(ih,{d})':force_original_aspect_ratio=decrease," + vf
    codec = ["-c:v", "libx264", "-preset", "slow"]
    if opts.video_codec == "h265":
        codec = ["-c:v", "libx265", "-preset", "medium", "-tag:v", "hvc1", "-x265-params", "log-level=error"]
    _ffmpeg([
        "-i", str(src),
        "-map", "0:v:0", "-map", "0:a?", "-map_metadata", "0",
        *codec, "-crf", str(CRF[opts.video_codec][opts.level]), "-pix_fmt", "yuv420p", "-vf", vf,
        "-c:a", "aac", "-b:a", VIDEO_AUDIO_BITRATE[opts.level],
        "-movflags", "+faststart", str(out),
    ])
    return out


def _audio(src: Path, tmp: Path, opts: Options) -> Path:
    ext = src.suffix.lower()
    lvl = opts.level
    if ext in (".wav", ".aiff", ".aif", ".flac") and lvl == "low":
        out, codec = tmp / (src.stem + ".flac"), ["-c:a", "flac", "-compression_level", "12"]
    elif ext in (".m4a", ".aac"):
        out, codec = tmp / (src.stem + ".m4a"), ["-c:a", "aac", "-b:a", AUDIO_BITRATE[lvl]]
    elif ext in (".ogg", ".opus"):
        out, codec = tmp / src.name, ["-c:a", "libopus", "-b:a", OPUS_BITRATE[lvl]]
    else:
        # mp3 is the most compatible; wav/flac at medium/high also become mp3
        out, codec = tmp / (src.stem + ".mp3"), ["-c:a", "libmp3lame", "-b:a", AUDIO_BITRATE[lvl]]
    _ffmpeg(["-i", str(src), "-map", "0:a:0", "-map_metadata", "0", *codec, str(out)])
    return out
