from __future__ import annotations

import io
import unittest
from unittest.mock import patch

from ytu.cli import build_parser, resolve_quality
from ytu.player import PlayerError, build_mpv_command, quality_label
from ytu.search import VideoResult
from ytu.ui import TerminalUI
from ytu.utils import (
    display_width,
    fit_text,
    format_duration,
    is_valid_video_id,
    sanitize_text,
    truncate_display,
)


class CliTests(unittest.TestCase):
    def parse_quality(self, *arguments: str) -> str:
        args = build_parser().parse_args([*arguments, "query"])
        return resolve_quality(args)

    def test_quality_switches(self) -> None:
        self.assertEqual(self.parse_quality("-q", "480"), "480")
        self.assertEqual(self.parse_quality("-q", "1080"), "1080")
        self.assertEqual(self.parse_quality("-low"), "low")
        self.assertEqual(self.parse_quality("--low"), "low")
        self.assertEqual(self.parse_quality("-high"), "high")
        self.assertEqual(self.parse_quality(), "high")


class PlayerTests(unittest.TestCase):
    def test_numeric_quality_command(self) -> None:
        command = build_mpv_command("/usr/bin/mpv", "dQw4w9WgXcQ", "480")
        self.assertEqual(command[0], "/usr/bin/mpv")
        self.assertIn("height<=?480", command[2])
        self.assertEqual(command[-2], "--")
        self.assertTrue(command[-1].endswith("dQw4w9WgXcQ"))

    def test_low_and_high_are_real_presets(self) -> None:
        low = build_mpv_command("mpv", "dQw4w9WgXcQ", "low")
        high = build_mpv_command("mpv", "dQw4w9WgXcQ", "high")
        self.assertIn("worstvideo+worstaudio/worst", low[2])
        self.assertIn("bestvideo*+bestaudio/best", high[2])
        self.assertEqual(quality_label("low"), "LOW · data saver")

    def test_audio_disables_video(self) -> None:
        command = build_mpv_command("mpv", "dQw4w9WgXcQ", "audio")
        self.assertIn("--no-video", command)

    def test_invalid_id_is_rejected(self) -> None:
        with self.assertRaises(PlayerError):
            build_mpv_command("mpv", "$(bad-id)", "high")


class FormattingTests(unittest.TestCase):
    def test_untrusted_ansi_and_c1_controls_are_removed(self) -> None:
        self.assertEqual(
            sanitize_text("hello\x1b[31m red\x9b31m\nnext"),
            "hello red31m next",
        )

    def test_video_id_must_match_all_eleven_characters(self) -> None:
        self.assertTrue(is_valid_video_id("dQw4w9WgXcQ"))
        self.assertFalse(is_valid_video_id("dQw4w9WgXcQ\n"))

    def test_infinite_duration_is_safe(self) -> None:
        self.assertEqual(format_duration(float("inf")), "--:--")

    def test_wide_text_fits_terminal_cells(self) -> None:
        value = fit_text(truncate_display("音楽プレイリスト", 9), 9)
        self.assertEqual(display_width(value), 9)

    @patch("ytu.ui.shutil.get_terminal_size")
    def test_result_table_has_frames_without_color(self, terminal_size) -> None:
        terminal_size.return_value.columns = 70
        output = io.StringIO()
        errors = io.StringIO()
        ui = TerminalUI("never", output, errors)
        ui.results([VideoResult("dQw4w9WgXcQ", "Example", 123)], "demo")
        rendered = output.getvalue()
        self.assertIn("╭", rendered)
        self.assertIn("Example", rendered)
        self.assertNotIn("\x1b[", rendered)


if __name__ == "__main__":
    unittest.main()
