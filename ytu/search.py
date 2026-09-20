"""YouTube search via `yt-dlp` as a subprocess.

Deliberately *not* using the `yt_dlp` Python package: shelling out to the
system `yt-dlp` binary keeps ytu's own dependency list at zero and means
ytu automatically benefits whenever the user updates yt-dlp (which,
given how often YouTube changes its internals, is often).

We use `--flat-playlist` so this step is cheap: yt-dlp only parses the
YouTube search results page and does not visit each individual video
page. That page already includes id/title/duration, so this is enough
for the picker UI — we don't pay for full extraction (format lists,
stream URLs, etc.) until the user has actually picked something and
mpv/yt-dlp resolve *that one* video.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from typing import List, Optional

from .utils import is_valid_video_id, sanitize_text

# Overall wall-clock budget for the search subprocess. If yt-dlp hangs
# (dead network, YouTube stalling, etc.) we'd rather fail with a clear
# message than leave the user staring at a frozen terminal.
SEARCH_TIMEOUT_SECONDS = 20

# Passed to yt-dlp itself as --socket-timeout, so individual HTTP(S)
# requests give up well before our own subprocess-level timeout fires.
SOCKET_TIMEOUT_SECONDS = 10


class SearchError(Exception):
    """A known, user-facing search failure (as opposed to a bug)."""


@dataclass(frozen=True)
class VideoResult:
    video_id: str
    title: str
    duration: Optional[float]  # seconds; None for livestreams/unknown


def yt_dlp_path() -> Optional[str]:
    """Return the path to the yt-dlp binary, or None if not on PATH."""
    return shutil.which("yt-dlp")


def get_yt_dlp_version(binary: Optional[str] = None) -> Optional[str]:
    """Best-effort `yt-dlp --version`, used only for informational output."""
    binary = binary or yt_dlp_path()
    if not binary:
        return None
    try:
        proc = subprocess.run(
            [binary, "--version"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def search(query: str, count: int) -> List[VideoResult]:
    """Search YouTube for `query` and return up to `count` results.

    Raises SearchError with a human-readable message on any failure
    (missing binary, timeout, network error, no results, ...). Never
    raises a raw subprocess/JSON exception to the caller.
    """
    query = (query or "").strip()
    if not query:
        raise SearchError("empty search query")

    binary = yt_dlp_path()
    if binary is None:
        raise SearchError(
            "yt-dlp not found in PATH. Install it and try again "
            "(see https://github.com/yt-dlp/yt-dlp#installation)."
        )

    # ytsearchN:QUERY is yt-dlp's own pseudo-URL syntax for "search
    # YouTube and return N results". It's passed as a single argv
    # element (never through a shell), so there's no injection risk
    # from special characters in the query.
    search_spec = f"ytsearch{count}:{query}"

    cmd = [
        binary,
        search_spec,
        "--flat-playlist",
        "--dump-json",
        "--no-warnings",
        "--ignore-config",  # don't let the user's/system's yt-dlp config
                             # change behaviour under us
        "--socket-timeout", str(SOCKET_TIMEOUT_SECONDS),
    ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=SEARCH_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError:
        # Race condition: binary disappeared between which() and run().
        raise SearchError("yt-dlp not found in PATH.")
    except subprocess.TimeoutExpired:
        raise SearchError(
            f"search timed out after {SEARCH_TIMEOUT_SECONDS}s. "
            "Check your internet connection and try again."
        )

    if proc.returncode != 0:
        stderr_lines = [l.strip() for l in (proc.stderr or "").splitlines() if l.strip()]
        detail = stderr_lines[-1] if stderr_lines else f"exit code {proc.returncode}"
        raise SearchError(f"yt-dlp failed: {detail}")

    results: List[VideoResult] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            # We don't trust yt-dlp's stdout to be perfectly well-formed
            # in every version/edge case; skip garbage lines rather than
            # crash the whole search.
            continue

        if not isinstance(entry, dict):
            continue

        raw_id = entry.get("id")
        if not raw_id or not is_valid_video_id(str(raw_id)):
            # Don't trust arbitrary data from search results: if it
            # doesn't look like a real video ID, drop it rather than
            # ever building a URL from it.
            continue

        title = sanitize_text(str(entry.get("title") or "(untitled)"))

        duration = entry.get("duration")
        if not isinstance(duration, (int, float)):
            duration = None

        results.append(VideoResult(video_id=str(raw_id), title=title, duration=duration))

    if not results:
        raise SearchError(f'no results found for "{query}".')

    return results
