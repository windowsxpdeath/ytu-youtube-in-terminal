"""Launch mpv with a safe yt-dlp format preset."""

from __future__ import annotations

import shutil
import subprocess
from typing import Dict, List, Optional

from .utils import is_valid_video_id

# Values accepted by `-q/--quality`.  The dedicated -low/-high switches use
# the same internal presets, which keeps command construction in one place.
QUALITY_CHOICES = (
    "144",
    "240",
    "360",
    "480",
    "720",
    "1080",
    "1440",
    "2160",
    "audio",
    "low",
    "high",
    "best",  # compatibility with ytu 1.x
)

_NUMERIC_QUALITIES = ("144", "240", "360", "480", "720", "1080", "1440", "2160")

_QUALITY_FORMATS: Dict[str, str] = {
    # Lowest separate video/audio streams, falling back to the worst combined
    # format.  This is the data-saver preset requested for unreliable links.
    "low": "worstvideo+worstaudio/worst",
    # Explicit best-quality selector. `bestvideo*` also permits a combined
    # stream when a video-only format is unavailable.
    "high": "bestvideo*+bestaudio/best",
    "best": "bestvideo*+bestaudio/best",
    "audio": "bestaudio/best",
}
for _height in _NUMERIC_QUALITIES:
    _QUALITY_FORMATS[_height] = (
        f"bestvideo[height<=?{_height}]+bestaudio/"
        f"best[height<=?{_height}]"
    )


class PlayerError(Exception):
    """A known, user-facing playback failure."""


def mpv_path() -> Optional[str]:
    """Return the mpv executable path, if available."""
    return shutil.which("mpv")


def build_watch_url(video_id: str) -> str:
    """Build a watch URL only after validating the untrusted video ID."""
    if not is_valid_video_id(video_id):
        raise PlayerError("refusing to play: invalid YouTube video ID.")
    return f"https://www.youtube.com/watch?v={video_id}"


def quality_label(quality: str) -> str:
    """Return a short human-readable label for the TUI."""
    if quality == "low":
        return "LOW · data saver"
    if quality in ("high", "best"):
        return "HIGH · best available"
    if quality == "audio":
        return "AUDIO ONLY"
    return f"{quality}p max"


def build_mpv_command(binary: str, video_id: str, quality: str) -> List[str]:
    """Build the subprocess argv; kept pure so presets are easy to test."""
    if quality not in _QUALITY_FORMATS:
        raise PlayerError(f"unknown quality preset: {quality}")

    url = build_watch_url(video_id)
    cmd = [
        binary,
        "--ytdl=yes",
        f"--ytdl-format={_QUALITY_FORMATS[quality]}",
    ]
    if quality == "audio":
        cmd.append("--no-video")
    cmd.extend(["--", url])
    return cmd


def play(video_id: str, quality: str = "high") -> int:
    """Stream one video in mpv and return mpv's exit status."""
    binary = mpv_path()
    if binary is None:
        raise PlayerError("mpv not found in PATH. Install it and try again.")

    command = build_mpv_command(binary, video_id, quality)
    try:
        process = subprocess.run(command, check=False)
    except FileNotFoundError:
        raise PlayerError("mpv not found in PATH.")
    except OSError as exc:
        raise PlayerError(f"could not launch mpv: {exc}")
    return process.returncode
