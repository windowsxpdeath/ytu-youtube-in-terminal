"""Pure formatting, sanitising, and validation helpers used by ytu."""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

_VIDEO_ID_RE = re.compile(r"[A-Za-z0-9_-]{11}")

# Strip ANSI CSI/OSC sequences and the remaining C0/C1 control characters. Video
# titles are untrusted input and must never be able to control the terminal.
_CSI_RE = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
_OSC_RE = re.compile(r"\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)")
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")


def is_valid_video_id(video_id: str) -> bool:
    """Return whether *video_id* has YouTube's 11-character ID shape."""
    return bool(video_id) and bool(_VIDEO_ID_RE.fullmatch(video_id))


def sanitize_text(text: Optional[str]) -> str:
    """Remove terminal escapes, controls, and layout-breaking whitespace."""
    if not text:
        return ""
    cleaned = _CSI_RE.sub("", text)
    cleaned = _OSC_RE.sub("", cleaned)
    cleaned = _CONTROL_RE.sub("", cleaned)
    cleaned = cleaned.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    return cleaned.strip()


def _character_width(character: str) -> int:
    """Best-effort terminal cell width without a third-party dependency."""
    if not character or unicodedata.combining(character):
        return 0
    return 2 if unicodedata.east_asian_width(character) in ("W", "F") else 1


def display_width(text: str) -> int:
    """Return the approximate number of terminal cells occupied by *text*."""
    return sum(_character_width(character) for character in text)


def truncate_display(text: str, width: int) -> str:
    """Truncate text to a terminal-cell width and append an ellipsis."""
    if width <= 0:
        return ""
    if display_width(text) <= width:
        return text
    if width == 1:
        return "…"

    limit = width - 1
    used = 0
    output = []
    for character in text:
        character_width = _character_width(character)
        if used + character_width > limit:
            break
        output.append(character)
        used += character_width
    return "".join(output).rstrip() + "…"


def fit_text(text: str, width: int, align: str = "left") -> str:
    """Truncate and pad text to exactly *width* terminal cells."""
    fitted = truncate_display(text, width)
    padding = max(0, width - display_width(fitted))
    if align == "right":
        return (" " * padding) + fitted
    if align == "center":
        left = padding // 2
        return (" " * left) + fitted + (" " * (padding - left))
    return fitted + (" " * padding)


def truncate(text: str, width: int) -> str:
    """Backward-compatible alias for display-aware truncation."""
    return truncate_display(text, width)


def format_duration(seconds: Optional[float]) -> str:
    """Format duration as M:SS/H:MM:SS; unknown durations are labelled LIVE."""
    if seconds is None:
        return "LIVE"
    try:
        total = int(seconds)
    except (TypeError, ValueError, OverflowError):
        return "--:--"
    if total < 0:
        return "--:--"

    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"
