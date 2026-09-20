"""Command-line interface for ytu."""

from __future__ import annotations

import argparse
import shutil
import sys
import time
from typing import Optional, Sequence

from . import __version__
from .player import PlayerError, QUALITY_CHOICES, mpv_path, play, quality_label
from .search import SearchError, get_yt_dlp_version, search, yt_dlp_path
from .ui import TerminalUI
from .utils import sanitize_text, truncate_display

DEFAULT_COUNT = 10
MIN_COUNT = 1
MAX_COUNT = 50


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ytu",
        description="Search YouTube in a colourful terminal picker and stream with mpv.",
        epilog=(
            "examples:\n"
            '  ytu "death note opening"\n'
            '  ytu -q 480 "some talk"\n'
            '  ytu -q 1080 "nature documentary"\n'
            '  ytu -low "music for coding"\n'
            '  ytu -high "cinematic trailer"\n'
            '  ytu -q audio "podcast episode"\n'
            "  ytu --check\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "query",
        nargs="*",
        help='search query, for example: ytu "death note opening"',
    )
    parser.add_argument(
        "-n",
        "--count",
        type=int,
        default=DEFAULT_COUNT,
        metavar="N",
        help=f"results to show (default: {DEFAULT_COUNT}, max: {MAX_COUNT})",
    )

    quality = parser.add_mutually_exclusive_group()
    quality.add_argument(
        "-q",
        "--quality",
        choices=QUALITY_CHOICES,
        metavar="QUALITY",
        help="maximum resolution: 480, 1080, etc.; also audio, low, or high",
    )
    quality.add_argument(
        "-low",
        "--low",
        action="store_true",
        help="data-saver mode: request the lowest available playable quality",
    )
    quality.add_argument(
        "-high",
        "--high",
        action="store_true",
        help="request the best available video and audio quality (default)",
    )

    parser.add_argument(
        "--check",
        action="store_true",
        help="check that yt-dlp and mpv are installed, then exit",
    )
    parser.add_argument(
        "--timing",
        action="store_true",
        help="print search and player timings to stderr",
    )

    color = parser.add_mutually_exclusive_group()
    color.add_argument(
        "--color",
        dest="color_mode",
        action="store_const",
        const="always",
        help="force ANSI colours even when output is redirected",
    )
    color.add_argument(
        "--no-color",
        dest="color_mode",
        action="store_const",
        const="never",
        help="disable ANSI colours (the TUI layout remains enabled)",
    )
    parser.set_defaults(color_mode="auto")

    parser.add_argument(
        "--version",
        action="version",
        version=f"ytu {__version__}",
    )
    return parser


def resolve_quality(args: argparse.Namespace) -> str:
    """Resolve mutually-exclusive CLI switches to one player preset."""
    if args.low:
        return "low"
    if args.high:
        return "high"
    if args.quality:
        return "high" if args.quality == "best" else args.quality
    return "high"


def cmd_check(ui: TerminalUI) -> int:
    """Report whether runtime dependencies are available."""
    ytdlp_binary = yt_dlp_path()
    mpv_binary = mpv_path()

    ui.banner("SYSTEM CHECK")
    ui.activity("yt-dlp", ytdlp_binary or "not found")
    ui.activity("mpv", mpv_binary or "not found")
    ok = bool(ytdlp_binary and mpv_binary)

    if ytdlp_binary:
        version = get_yt_dlp_version(ytdlp_binary)
        if version:
            ui.activity("version", version)
        if shutil.which("deno") is None:
            ui.warning(
                "No JavaScript runtime found. If YouTube extraction fails, install deno."
            )

    if not ytdlp_binary:
        ui.error("yt-dlp is missing. Install it with your package manager or pipx.")
    if not mpv_binary:
        ui.error("mpv is missing. Install it with your package manager.")
    if ok:
        ui.success("Everything is ready.")
    return 0 if ok else 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    ui = TerminalUI(args.color_mode)

    if args.check:
        return cmd_check(ui)

    if not args.query:
        parser.error('a search query is required, e.g. ytu "death note opening"')
    if not MIN_COUNT <= args.count <= MAX_COUNT:
        parser.error(f"-n/--count must be between {MIN_COUNT} and {MAX_COUNT}")

    query = " ".join(args.query).strip()
    selected_quality = resolve_quality(args)
    label = quality_label(selected_quality)

    ui.banner(label)
    ui.activity("search", f'"{query}"')

    search_started = time.perf_counter()
    try:
        results = search(query, args.count)
    except SearchError as exc:
        ui.error(f"Search failed: {exc}")
        return 1
    except KeyboardInterrupt:
        ui.warning("Cancelled.")
        return 130
    search_finished = time.perf_counter()

    if args.timing:
        print(
            f"[timing] search: {search_finished - search_started:.2f}s",
            file=sys.stderr,
        )

    ui.results(results, query)
    try:
        choice = ui.prompt_choice(len(results))
    except KeyboardInterrupt:
        ui.warning("Cancelled.")
        return 130
    except EOFError:
        ui.warning("No input (EOF). Nothing to play.")
        return 130

    selected = results[choice - 1]
    title = truncate_display(sanitize_text(selected.title), 55)
    ui.activity("play", f"{title} · {label}")

    play_started = time.perf_counter()
    try:
        exit_code = play(selected.video_id, selected_quality)
    except PlayerError as exc:
        ui.error(f"Playback failed: {exc}")
        return 1
    except KeyboardInterrupt:
        ui.warning("Playback interrupted.")
        return 130
    play_finished = time.perf_counter()

    if args.timing:
        print(
            f"[timing] mpv (start to exit): {play_finished - play_started:.2f}s",
            file=sys.stderr,
        )

    if exit_code != 0:
        ui.error(
            f"mpv exited with code {exit_code}. Try updating yt-dlp if playback failed."
        )
        return exit_code

    ui.success("Playback finished.")
    return 0
