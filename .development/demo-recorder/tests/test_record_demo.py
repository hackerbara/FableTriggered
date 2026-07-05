from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "record_demo.py"
spec = importlib.util.spec_from_file_location("record_demo", MODULE_PATH)
record_demo = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = record_demo
spec.loader.exec_module(record_demo)


def base_config(tmp_path: Path) -> dict:
    target = tmp_path / "claude fake"
    target.write_text("#!/bin/sh\n", encoding="utf-8")
    target.chmod(0o755)
    cwd = tmp_path / "work dir"
    cwd.mkdir()
    return {
        "demoName": "demo",
        "app": {"name": "Ghostty", "bundleId": "com.mitchellh.ghostty", "leaveOpenAtEnd": True},
        "screen": {"avfoundationDevice": "2", "label": "screen", "crop": None, "fps": 12, "scaleWidth": 960},
        "command": {"cwd": str(cwd), "path": str(target), "args": ["--flag", "value with spaces"]},
        "recording": {"start": "afterLaunchSettle", "postLaunchWaitSeconds": 1, "recordSeconds": 2},
        "events": [{"type": "wait", "seconds": 1}, {"type": "key", "key": "ctrl-c"}],
        "publish": {"enabled": False, "outputGif": str(tmp_path / "out.gif")},
    }


def write_config(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


class RecordDemoTests(unittest.TestCase):

    def test_root_is_derived_from_module_location_not_hardcoded_worktree_path(self) -> None:
        expected_root = Path(__file__).resolve().parents[3]
        module_root = Path(record_demo.__file__).resolve().parents[2]
        self.assertEqual(module_root, expected_root)
        self.assertEqual(record_demo.ROOT, expected_root)

        source = Path(record_demo.__file__).read_text(encoding="utf-8")
        self.assertNotIn("/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder", source)

    def test_parse_config_and_shell_command_quote_spaces(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            cfg = record_demo.parse_config(write_config(tmp_path, base_config(tmp_path)))
            command = record_demo.shell_command(cfg.command)
            self.assertIn("cd ", command)
            self.assertIn("'value with spaces'", command)
            self.assertIn("claude fake", command)

    def test_validate_config_rejects_missing_target(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            data = base_config(tmp_path)
            data["command"]["path"] = str(tmp_path / "missing")
            cfg = record_demo.parse_config(write_config(tmp_path, data))
            with self.assertRaisesRegex(record_demo.RecorderError, "command.path does not exist"):
                record_demo.validate_config(cfg)

    def test_validate_crop_accepts_bounds(self) -> None:
        self.assertEqual(record_demo.validate_crop("crop=100:80:10:20", width=200, height=160), (100, 80, 10, 20))

    def test_validate_crop_rejects_out_of_bounds(self) -> None:
        with self.assertRaisesRegex(record_demo.RecorderError, "crop exceeds frame bounds"):
            record_demo.validate_crop("crop=100:80:150:20", width=200, height=160)

    def test_ffmpeg_filters_without_crop(self) -> None:
        vf, lavfi = record_demo.build_gif_filters(crop=None, fps=12, scale_width=960)
        self.assertEqual(vf, "fps=12,scale=960:-1:flags=lanczos,palettegen=stats_mode=diff")
        self.assertEqual(lavfi, "fps=12,scale=960:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle")

    def test_ffmpeg_filters_with_crop(self) -> None:
        vf, lavfi = record_demo.build_gif_filters(crop="crop=100:80:10:20", fps=8, scale_width=640)
        self.assertTrue(vf.startswith("crop=100:80:10:20,fps=8"))
        self.assertTrue(lavfi.startswith("crop=100:80:10:20,fps=8"))

    def test_validate_events_rejects_escape(self) -> None:
        with self.assertRaisesRegex(record_demo.RecorderError, "escape is intentionally unsupported"):
            record_demo.validate_events([{"type": "key", "key": "escape"}])

    def test_key_action_script_contains_expected_key_code(self) -> None:
        script = record_demo.applescript_for_key("down")
        self.assertIn("key code 125", script)

    def test_key_action_script_rejects_escape(self) -> None:
        with self.assertRaisesRegex(record_demo.RecorderError, "unsupported key"):
            record_demo.applescript_for_key("escape")

    def test_frontmost_assertion_mentions_bundle(self) -> None:
        script = record_demo.applescript_frontmost_bundle()
        self.assertIn("frontmost is true", script)
        self.assertIn("bundle identifier", script)

    def test_build_launch_command_uses_cd_and_exec_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            cfg = record_demo.parse_config(write_config(tmp_path, base_config(tmp_path)))
            command = record_demo.shell_command(cfg.command)
            self.assertTrue(command.startswith("cd "))
            self.assertIn("&&", command)
            self.assertIn("--flag", command)

    def test_parse_config_defaults_to_reuse_running_launch_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            cfg = record_demo.parse_config(write_config(tmp_path, base_config(tmp_path)))
            self.assertEqual(cfg.app.launch_mode, "reuseRunning")

    def test_open_and_focus_app_reuse_running_does_not_call_open(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            cfg = record_demo.parse_config(write_config(tmp_path, base_config(tmp_path)))
            with (
                mock.patch.object(record_demo, "app_is_running", return_value=True),
                mock.patch.object(record_demo, "frontmost_bundle", return_value=cfg.app.bundle_id),
                mock.patch.object(record_demo.subprocess, "run") as run_mock,
            ):
                record_demo.open_and_focus_app(cfg, timeout_seconds=0.01)
            self.assertNotIn(mock.call(["open", "-b", cfg.app.bundle_id], check=False), run_mock.mock_calls)

    def test_open_and_focus_app_reuse_running_fails_if_app_is_not_running(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            cfg = record_demo.parse_config(write_config(tmp_path, base_config(tmp_path)))
            with mock.patch.object(record_demo, "app_is_running", return_value=False):
                with self.assertRaisesRegex(record_demo.RecorderError, "is not running"):
                    record_demo.open_and_focus_app(cfg, timeout_seconds=0.01)

    def test_open_and_focus_app_open_or_reuse_keeps_explicit_launch_escape_hatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            data = base_config(tmp_path)
            data["app"]["launchMode"] = "openOrReuse"
            data["preparedGhostty"] = {"requireAlreadyRunning": False}
            cfg = record_demo.parse_config(write_config(tmp_path, data))
            with (
                mock.patch.object(record_demo, "frontmost_bundle", return_value=cfg.app.bundle_id),
                mock.patch.object(record_demo.subprocess, "run") as run_mock,
            ):
                record_demo.open_and_focus_app(cfg, timeout_seconds=0.01)
            self.assertIn(mock.call(["open", "-b", cfg.app.bundle_id], check=False), run_mock.mock_calls)

    def test_run_calibration_reports_ffmpeg_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            cfg = record_demo.parse_config(write_config(tmp_path, base_config(tmp_path)))
            with mock.patch.object(
                record_demo.subprocess,
                "run",
                side_effect=subprocess.TimeoutExpired(["ffmpeg"], timeout=15),
            ):
                with self.assertRaisesRegex(record_demo.RecorderError, "calibration ffmpeg timed out"):
                    record_demo.run_calibration(cfg, tmp_path)

    def test_send_key_refocuses_before_asserting_frontmost(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            cfg = record_demo.parse_config(write_config(tmp_path, base_config(tmp_path)))
            with (
                mock.patch.object(record_demo, "open_and_focus_app") as focus_mock,
                mock.patch.object(record_demo, "assert_frontmost_bundle") as assert_mock,
                mock.patch.object(record_demo, "run_osascript") as osascript_mock,
            ):
                record_demo.send_key(cfg, "down")
            focus_mock.assert_called_once_with(cfg)
            assert_mock.assert_called_once_with(cfg.app.bundle_id)
            self.assertIn("key code 125", osascript_mock.call_args.args[0])

    def test_paste_text_sets_and_verifies_clipboard_without_restoring_old_value(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            cfg = record_demo.parse_config(write_config(tmp_path, base_config(tmp_path)))
            with (
                mock.patch.object(record_demo, "open_and_focus_app") as focus_mock,
                mock.patch.object(record_demo, "assert_frontmost_bundle") as assert_mock,
                mock.patch.object(record_demo, "set_clipboard") as set_clipboard_mock,
                mock.patch.object(record_demo, "get_clipboard", return_value="hello") as get_clipboard_mock,
                mock.patch.object(record_demo, "run_osascript") as osascript_mock,
            ):
                record_demo.paste_text(cfg, "hello")
            focus_mock.assert_called_once_with(cfg)
            assert_mock.assert_called_once_with(cfg.app.bundle_id)
            set_clipboard_mock.assert_called_once_with("hello")
            get_clipboard_mock.assert_called_once_with()
            self.assertIn("keystroke \"v\" using command down", osascript_mock.call_args.args[0])

    def test_paste_text_fails_if_clipboard_does_not_contain_requested_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            cfg = record_demo.parse_config(write_config(tmp_path, base_config(tmp_path)))
            with (
                mock.patch.object(record_demo, "open_and_focus_app"),
                mock.patch.object(record_demo, "assert_frontmost_bundle"),
                mock.patch.object(record_demo, "set_clipboard"),
                mock.patch.object(record_demo, "get_clipboard", return_value="old"),
                mock.patch.object(record_demo, "run_osascript") as osascript_mock,
            ):
                with self.assertRaisesRegex(record_demo.RecorderError, "clipboard verification failed"):
                    record_demo.paste_text(cfg, "hello")
            osascript_mock.assert_not_called()

    def test_validate_events_accepts_x_close_key(self) -> None:
        record_demo.validate_events([{"type": "key", "key": "x"}])

    def test_key_action_script_contains_expected_x_close_keystroke(self) -> None:
        script = record_demo.applescript_for_key("x")
        self.assertIn('keystroke "x"', script)

    def test_prepared_ghostty_defaults_require_single_existing_window(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            cfg = record_demo.parse_config(write_config(tmp_path, base_config(tmp_path)))
        self.assertTrue(cfg.prepared_ghostty.require_already_running)
        self.assertTrue(cfg.prepared_ghostty.require_single_window_if_detectable)
        self.assertFalse(cfg.prepared_ghostty.allow_multiple_windows)

    def test_open_and_focus_app_rejects_multiple_detectable_ghostty_windows(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            cfg = record_demo.parse_config(write_config(tmp_path, base_config(tmp_path)))
            with (
                mock.patch.object(record_demo, "app_is_running", return_value=True),
                mock.patch.object(record_demo, "focus_running_app"),
                mock.patch.object(record_demo, "frontmost_bundle", return_value=cfg.app.bundle_id),
                mock.patch.object(record_demo, "app_window_count", return_value=2),
            ):
                with self.assertRaisesRegex(record_demo.RecorderError, "requires one"):
                    record_demo.open_and_focus_app(cfg, timeout_seconds=0.01)

    def test_shell_command_can_include_run_id_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            cfg = record_demo.parse_config(write_config(tmp_path, base_config(tmp_path)))
            command = record_demo.shell_command(cfg.command, run_id="run-123")
        self.assertIn("DEMO_RECORDER_RUN_ID=run-123", command)
        self.assertIn("claude fake", command)

    def test_verify_launch_process_requires_expected_binary_and_args(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            cfg = record_demo.parse_config(write_config(tmp_path, base_config(tmp_path)))
            table = f"123 {cfg.command.path} --flag value with spaces\n"
            with mock.patch.object(record_demo, "process_table", return_value=table):
                launch = record_demo.verify_launch_process(cfg, run_id="run-123", launched_at=1.0)
            self.assertTrue(launch["verified"])
            self.assertEqual(launch["matchedPid"], 123)

            with mock.patch.object(record_demo, "process_table", return_value="123 /usr/bin/false\n"):
                with self.assertRaisesRegex(record_demo.RecorderError, "no new process found"):
                    record_demo.verify_launch_process(cfg, run_id="run-123", launched_at=1.0)

if __name__ == "__main__":
    unittest.main()
