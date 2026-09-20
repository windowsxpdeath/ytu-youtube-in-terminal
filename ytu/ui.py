"""Small dependency-free terminal UI for ytu.

The UI deliberately uses only ANSI colours and Unicode box drawing.  Colour is
turned off automatically when output is redirected, when TERM=dumb, or when
NO_COLOR is set.  Search result text is sanitized before it reaches this
module, so titles cannot inject terminal control sequences.
"""

from __future__ import annotations

import os
import shutil
import sys
from typing import Optional, Sequence, TextIO

from .search import VideoResult
from .utils import fit_text, format_duration, sanitize_text, truncate_display

_RESET = "\x1b[0m"
_BOLD = "1"
_DIM = "2"
_RED = "31"
_GREEN = "32"
_YELLOW = "33"
_BLUE = "34"
_MAGENTA = "35"
_CYAN = "36"
_WHITE = "97"


def _stream_supports_color(stream: TextIO, mode: str) -> bool:
    if mode == "always":
        return True
    if mode == "never":
        return False
    if os.environ.get("NO_COLOR") is not None or os.environ.get("TERM") == "dumb":
        return False
    return bool(getattr(stream, "isatty", lambda: False)())


class TerminalUI:
    """Render ytu's compact TUI and interactive picker."""

    def __init__(
        self,
        color_mode: str = "auto",
        stream: TextIO = sys.stdout,
        error_stream: TextIO = sys.stderr,
    ) -> None:
        self.stream = stream
        self.error_stream = error_stream
        self.color_mode = color_mode
        self.color = _stream_supports_color(stream, color_mode)

        columns = shutil.get_terminal_size(fallback=(80, 24)).columns
        # Keep the picker readable on large screens and usable on narrow ones.
        self.width = max(24, min(96, columns))
        self.inner_width = self.width - 2

    def _style(self, text: str, *codes: str) -> str:
        if not self.color or not codes:
            return text
        return f"\x1b[{';'.join(codes)}m{text}{_RESET}"

    def _print(self, *parts: str, stream: Optional[TextIO] = None, end: str = "\n") -> None:
        print("".join(parts), file=stream or self.stream, end=end, flush=True)

    def _border(self, left: str, fill: str, right: str) -> None:
        line = left + (fill * self.inner_width) + right
        self._print(self._style(line, _CYAN, _DIM))

    def _boxed_text(self, text: str, *codes: str) -> None:
        safe = truncate_display(sanitize_text(text), max(1, self.inner_width - 2))
        content = fit_text(f" {safe}", self.inner_width)
        self._print(
            self._style("│", _CYAN, _DIM),
            self._style(content, *codes),
            self._style("│", _CYAN, _DIM),
        )

    def banner(self, quality_label: str) -> None:
        self._print()
        self._border("╭", "─", "╮")

        logo = " Y T U "
        left = max(0, (self.inner_width - len(logo)) // 2)
        right = self.inner_width - left - len(logo)
        self._print(
            self._style("│", _CYAN, _DIM),
            " " * left,
            self._style(logo, _BOLD, _MAGENTA),
            " " * right,
            self._style("│", _CYAN, _DIM),
        )
        self._boxed_text("YouTube search · instant mpv streaming", _WHITE)
        self._boxed_text(f"QUALITY  {quality_label}", _BOLD, _YELLOW)
        self._border("╰", "─", "╯")

        # A two-colour rail gives the interface a TUI-like visual anchor.
        rail_width = max(1, min(30, self.width - 8))
        first = rail_width // 2
        self._print(
            "  ",
            self._style("━" * first, _MAGENTA),
            self._style("━" * (rail_width - first), _CYAN),
        )

    def activity(self, name: str, detail: str) -> None:
        safe_name = sanitize_text(name).upper()
        safe_detail = truncate_display(sanitize_text(detail), max(1, self.width - len(safe_name) - 8))
        self._print(
            self._style("◆", _MAGENTA, _BOLD),
            " ",
            self._style(safe_name, _BOLD, _CYAN),
            self._style("  ─  ", _DIM),
            safe_detail,
        )

    def results(self, results: Sequence[VideoResult], query: str) -> None:
        query_text = truncate_display(sanitize_text(query), max(1, self.inner_width - 13))
        self._print()
        self._border("╭", "─", "╮")
        self._boxed_text(f"RESULTS  {query_text}", _BOLD, _MAGENTA)
        self._border("├", "─", "┤")

        left_width = 5                         # " 01  "
        right_width = 11                       # "  01:23:45 "
        title_width = max(1, self.inner_width - left_width - right_width)

        header_left = " #   "
        header_title = fit_text("VIDEO", title_width)
        header_right = fit_text("TIME", right_width, align="right")
        self._print(
            self._style("│", _CYAN, _DIM),
            self._style(header_left, _BOLD, _CYAN),
            self._style(header_title, _BOLD, _WHITE),
            self._style(header_right, _BOLD, _YELLOW),
            self._style("│", _CYAN, _DIM),
        )
        self._border("├", "─", "┤")

        for index, result in enumerate(results, start=1):
            title = fit_text(sanitize_text(result.title), title_width)
            duration = format_duration(result.duration)
            left = f" {index:02d}  "
            right = fit_text(duration, right_width - 1, align="right") + " "
            number_color = _MAGENTA if index % 2 else _CYAN
            self._print(
                self._style("│", _CYAN, _DIM),
                self._style(left, _BOLD, number_color),
                self._style(title, _WHITE),
                self._style(right, _YELLOW),
                self._style("│", _CYAN, _DIM),
            )

        self._border("╰", "─", "╯")

    def prompt_choice(self, count: int) -> int:
        while True:
            prompt = "".join(
                (
                    self._style("╰─", _CYAN, _DIM),
                    " ",
                    self._style(f"Select video [1-{count}]", _BOLD, _WHITE),
                    self._style("  › ", _MAGENTA, _BOLD),
                )
            )
            raw = input(prompt).strip()
            if raw.isdigit() and 1 <= int(raw) <= count:
                return int(raw)
            self.warning(f"Enter a number from 1 to {count}.")

    def warning(self, message: str) -> None:
        safe = sanitize_text(message)
        self._print(
            self._style("▲", _YELLOW, _BOLD),
            " ",
            self._style(safe, _YELLOW),
            stream=self.error_stream,
        )

    def error(self, message: str) -> None:
        safe = sanitize_text(message)
        self._print(
            self._style("✗", _RED, _BOLD),
            " ",
            self._style(safe, _RED),
            stream=self.error_stream,
        )

    def success(self, message: str) -> None:
        safe = sanitize_text(message)
        self._print(
            self._style("✓", _GREEN, _BOLD),
            " ",
            self._style(safe, _GREEN),
        )
