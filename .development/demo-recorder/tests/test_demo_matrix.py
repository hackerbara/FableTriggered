import json
import math
import importlib.util
import contextlib
import io
import sys
import tempfile
from unittest import mock
import unittest
from pathlib import Path

DEMO_RECORDER_DIR = Path(__file__).resolve().parents[1]
if str(DEMO_RECORDER_DIR) not in sys.path:
    sys.path.insert(0, str(DEMO_RECORDER_DIR))

import run_demo_matrix


class DemoMatrixParserTests(unittest.TestCase):
    def write_matrix(self, tmp_path: Path, data: dict) -> Path:
        path = tmp_path / "demo_matrix.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def base_matrix(self, tmp_path: Path) -> dict:
        binary = tmp_path / "claude-fixture"
        binary.write_text("#!/bin/sh\n", encoding="utf-8")
        return {
            "version": 1,
            "defaults": {
                "app": {
                    "name": "Ghostty",
                    "bundleId": "com.mitchellh.ghostty",
                    "leaveOpenAtEnd": True,
                    "launchMode": "reuseRunning",
                },
                "screen": {
                    "avfoundationDevice": "2",
                    "label": "screen-0-dell",
                    "crop": None,
                    "fps": 12,
                    "scaleWidth": 960,
                },
                "cwd": str(tmp_path),
                "args": ["--dangerously-skip-permissions"],
                "recording": {
                    "start": "afterLaunchSettle",
                    "postLaunchWaitSeconds": 5,
                    "recordSeconds": 18,
                },
            },
            "recipes": [
                {
                    "id": "demo-one",
                    "enabled": True,
                    "category": "visual",
                    "purpose": "Exercise a visual demo.",
                    "binary": str(binary),
                    "events": [
                        {"type": "wait", "seconds": 2},
                        {"type": "key", "key": "ctrl-c"},
                    ],
                    "checkpoints": [{"name": "final", "atSeconds": 3}],
                    "publishGif": str(run_demo_matrix.ROOT / "assets" / "demos" / "demo-one.gif"),
                }
            ],
        }

    def assert_matrix_error(self, data: dict, pattern: str) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, pattern):
                run_demo_matrix.parse_matrix(self.write_matrix(tmp_path, data))

    def call_main(self, argv: list[str]) -> tuple[int, str, str]:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = run_demo_matrix.main(argv)
        return status, stdout.getvalue(), stderr.getvalue()

    def test_default_hidden_context_recipe_uses_down_return_x_sequence(self) -> None:
        matrix = run_demo_matrix.parse_matrix(run_demo_matrix.DEFAULT_MATRIX)
        recipe = run_demo_matrix.select_recipe(
            matrix, "hidden-context-plus-hotrod-dragons-open-close", include_disabled=False
        )
        key_events = [event["key"] for event in recipe.events if event.get("type") == "key"]
        self.assertEqual(key_events[:3], ["down", "return", "x"])
        self.assertNotIn("escape", key_events)

    def test_valid_enabled_recipe_parses(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            matrix = run_demo_matrix.parse_matrix(self.write_matrix(tmp_path, self.base_matrix(tmp_path)))

        self.assertEqual(matrix.version, 1)
        self.assertEqual(len(matrix.recipes), 1)
        recipe = matrix.recipes[0]
        self.assertEqual(recipe.id, "demo-one")
        self.assertTrue(recipe.enabled)
        self.assertEqual(recipe.cwd, Path(temp))
        self.assertEqual(recipe.checkpoints[0], run_demo_matrix.Checkpoint(name="final", at_seconds=3.0))

    def test_root_is_derived_from_module_location_not_hardcoded_worktree_path(self) -> None:
        expected_root = Path(__file__).resolve().parents[3]
        module_root = Path(run_demo_matrix.__file__).resolve().parents[2]
        self.assertEqual(module_root, expected_root)
        self.assertEqual(run_demo_matrix.ROOT, expected_root)

        source = Path(run_demo_matrix.__file__).read_text(encoding="utf-8")
        self.assertNotIn("/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder", source)

    def test_module_loads_with_exec_module_without_sys_modules_registration(self) -> None:
        module_path = DEMO_RECORDER_DIR / "run_demo_matrix.py"
        spec = importlib.util.spec_from_file_location("run_demo_matrix_exec_module_regression", module_path)
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        self.assertEqual(module.ROOT, Path(__file__).resolve().parents[3])

    def test_event_validation_delegates_to_record_demo(self) -> None:
        source = Path(run_demo_matrix.__file__).read_text(encoding="utf-8")
        self.assertIn("record_demo.validate_events(events)", source)
        self.assertNotIn("ALLOWED_KEY_EVENTS", source)

    def test_invalid_version_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            data = self.base_matrix(tmp_path)
            data["version"] = 2
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "version must be 1"):
                run_demo_matrix.parse_matrix(self.write_matrix(tmp_path, data))

    def test_missing_or_invalid_defaults_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            missing = self.base_matrix(tmp_path)
            missing.pop("defaults")
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "defaults must be an object"):
                run_demo_matrix.parse_matrix(self.write_matrix(tmp_path, missing))

            invalid = self.base_matrix(tmp_path)
            invalid["defaults"] = []
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "defaults must be an object"):
                run_demo_matrix.parse_matrix(self.write_matrix(tmp_path, invalid))

    def test_invalid_recipes_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            non_array = self.base_matrix(tmp_path)
            non_array["recipes"] = {}
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "recipes must be an array"):
                run_demo_matrix.parse_matrix(self.write_matrix(tmp_path, non_array))

            non_object_item = self.base_matrix(tmp_path)
            non_object_item["recipes"] = ["not-object"]
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "recipe 0 must be an object"):
                run_demo_matrix.parse_matrix(self.write_matrix(tmp_path, non_object_item))

    def test_duplicate_recipe_ids_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            data = self.base_matrix(tmp_path)
            data["recipes"].append(dict(data["recipes"][0]))
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "duplicate recipe id"):
                run_demo_matrix.parse_matrix(self.write_matrix(tmp_path, data))

    def test_unknown_recipe_keys_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            data = self.base_matrix(tmp_path)
            data["recipes"][0]["surprise"] = True
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "unknown recipe keys"):
                run_demo_matrix.parse_matrix(self.write_matrix(tmp_path, data))

    def test_unsafe_recipe_id_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            data = self.base_matrix(tmp_path)
            data["recipes"][0]["id"] = "../escape"
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "recipe.id is not path-safe"):
                run_demo_matrix.parse_matrix(self.write_matrix(tmp_path, data))

    def test_enabled_missing_binary_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            data = self.base_matrix(tmp_path)
            data["recipes"][0].pop("binary")
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "binary is required"):
                run_demo_matrix.parse_matrix(self.write_matrix(tmp_path, data))

    def test_publish_gif_outside_root_assets_demos_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            data = self.base_matrix(tmp_path)
            data["recipes"][0]["publishGif"] = str(tmp_path / "public.gif")
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "publishGif must be under"):
                run_demo_matrix.parse_matrix(self.write_matrix(tmp_path, data))

    def test_disabled_placeholder_without_binary_allowed_only_with_disabled_reason(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            data = self.base_matrix(tmp_path)
            recipe = data["recipes"][0]
            recipe["enabled"] = False
            recipe["events"] = []
            recipe.pop("binary")
            recipe["disabledReason"] = "Reviewed artifact has not been selected."
            matrix = run_demo_matrix.parse_matrix(self.write_matrix(tmp_path, data))
            self.assertFalse(matrix.recipes[0].enabled)
            self.assertEqual(matrix.recipes[0].events, ())
            self.assertEqual(matrix.recipes[0].disabled_reason, "Reviewed artifact has not been selected.")

            recipe.pop("disabledReason")
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "disabledReason is required"):
                run_demo_matrix.parse_matrix(self.write_matrix(tmp_path, data))

    def test_checkpoint_at_record_seconds_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            data = self.base_matrix(tmp_path)
            data["recipes"][0]["recording"] = {"recordSeconds": 3}
            data["recipes"][0]["events"] = [
                {"type": "wait", "seconds": 1},
                {"type": "key", "key": "ctrl-c"},
            ]
            data["recipes"][0]["checkpoints"] = [{"name": "bad", "atSeconds": 3}]
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "checkpoint time"):
                run_demo_matrix.parse_matrix(self.write_matrix(tmp_path, data))

    def test_duplicate_checkpoint_names_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            data = self.base_matrix(tmp_path)
            data["recipes"][0]["checkpoints"] = [
                {"name": "same", "atSeconds": 1},
                {"name": "same", "atSeconds": 2},
            ]
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "duplicate checkpoint"):
                run_demo_matrix.parse_matrix(self.write_matrix(tmp_path, data))

    def test_unsafe_checkpoint_name_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            data = self.base_matrix(tmp_path)
            data["recipes"][0]["checkpoints"] = [{"name": "../frame", "atSeconds": 1}]
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "checkpoint 0.name is not path-safe"):
                run_demo_matrix.parse_matrix(self.write_matrix(tmp_path, data))

    def test_cumulative_wait_schedule_too_close_to_end_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            data = self.base_matrix(tmp_path)
            data["recipes"][0]["recording"] = {"recordSeconds": 3}
            data["recipes"][0]["events"] = [
                {"type": "wait", "seconds": 2.5},
                {"type": "key", "key": "ctrl-c"},
            ]
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "wait schedule"):
                run_demo_matrix.parse_matrix(self.write_matrix(tmp_path, data))

    def test_record_seconds_must_be_finite(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            data = self.base_matrix(tmp_path)
            data["recipes"][0]["recording"] = {"recordSeconds": math.nan}
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "recording.recordSeconds must be a finite"):
                run_demo_matrix.parse_matrix(self.write_matrix(tmp_path, data))

    def test_wait_seconds_must_be_finite(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            data = self.base_matrix(tmp_path)
            data["recipes"][0]["events"] = [
                {"type": "wait", "seconds": math.inf},
                {"type": "key", "key": "ctrl-c"},
            ]
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "wait.seconds must be finite"):
                run_demo_matrix.parse_matrix(self.write_matrix(tmp_path, data))

    def test_checkpoint_at_seconds_must_be_finite(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            data = self.base_matrix(tmp_path)
            data["recipes"][0]["checkpoints"] = [{"name": "final", "atSeconds": math.inf}]
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "checkpoint time must be finite"):
                run_demo_matrix.parse_matrix(self.write_matrix(tmp_path, data))

    def test_enabled_recipe_requires_nonempty_events_ending_in_ctrl_c_unless_left_running(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            empty_events = self.base_matrix(tmp_path)
            empty_events["recipes"][0]["events"] = []
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "must define events ending with ctrl-c"):
                run_demo_matrix.parse_matrix(self.write_matrix(tmp_path, empty_events))

            missing_final_ctrl_c = self.base_matrix(tmp_path)
            missing_final_ctrl_c["recipes"][0]["events"] = [
                {"type": "wait", "seconds": 1},
                {"type": "key", "key": "return"},
            ]
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "must define events ending with ctrl-c"):
                run_demo_matrix.parse_matrix(self.write_matrix(tmp_path, missing_final_ctrl_c))

    def test_leave_process_running_allows_long_wait_schedule_and_no_ctrl_c(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            data = self.base_matrix(tmp_path)
            data["recipes"][0]["leaveProcessRunning"] = True
            data["recipes"][0]["recording"] = {"recordSeconds": 3}
            data["recipes"][0]["events"] = [{"type": "wait", "seconds": 3}]
            data["recipes"][0]["checkpoints"] = [{"name": "final", "atSeconds": 1}]
            matrix = run_demo_matrix.parse_matrix(self.write_matrix(tmp_path, data))
            self.assertTrue(matrix.recipes[0].leave_process_running)

    def test_enabled_recipe_rejects_missing_or_non_directory_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            missing = self.base_matrix(tmp_path)
            missing["defaults"]["cwd"] = str(tmp_path / "missing")
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "cwd does not exist or is not a directory"):
                run_demo_matrix.parse_matrix(self.write_matrix(tmp_path, missing))

            not_directory_path = tmp_path / "not-directory"
            not_directory_path.write_text("not a directory", encoding="utf-8")
            not_directory = self.base_matrix(tmp_path)
            not_directory["recipes"][0]["cwd"] = str(not_directory_path)
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "cwd does not exist or is not a directory"):
                run_demo_matrix.parse_matrix(self.write_matrix(tmp_path, not_directory))

    def test_event_validation_matches_record_demo_supported_shapes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)

            escape_key = self.base_matrix(tmp_path)
            escape_key["recipes"][0]["events"] = [
                {"type": "key", "key": "escape"},
                {"type": "key", "key": "ctrl-c"},
            ]
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "escape is intentionally unsupported"):
                run_demo_matrix.parse_matrix(self.write_matrix(tmp_path, escape_key))

            unsupported_key = self.base_matrix(tmp_path)
            unsupported_key["recipes"][0]["events"] = [
                {"type": "key", "key": "space"},
                {"type": "key", "key": "ctrl-c"},
            ]
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "unsupported key"):
                run_demo_matrix.parse_matrix(self.write_matrix(tmp_path, unsupported_key))

            unsupported_type = self.base_matrix(tmp_path)
            unsupported_type["recipes"][0]["events"] = [
                {"type": "click", "x": 1, "y": 1},
                {"type": "key", "key": "ctrl-c"},
            ]
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "unsupported type"):
                run_demo_matrix.parse_matrix(self.write_matrix(tmp_path, unsupported_type))

            invalid_text = self.base_matrix(tmp_path)
            invalid_text["recipes"][0]["events"] = [
                {"type": "text", "text": 123},
                {"type": "key", "key": "ctrl-c"},
            ]
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "text.text must be a string"):
                run_demo_matrix.parse_matrix(self.write_matrix(tmp_path, invalid_text))

            invalid_paste = self.base_matrix(tmp_path)
            invalid_paste["recipes"][0]["events"] = [
                {"type": "paste", "text": None},
                {"type": "key", "key": "ctrl-c"},
            ]
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "paste.text must be a string"):
                run_demo_matrix.parse_matrix(self.write_matrix(tmp_path, invalid_paste))

            invalid_wait = self.base_matrix(tmp_path)
            invalid_wait["recipes"][0]["events"] = [
                {"type": "wait", "seconds": -1},
                {"type": "key", "key": "ctrl-c"},
            ]
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "wait.seconds must be a non-negative number"):
                run_demo_matrix.parse_matrix(self.write_matrix(tmp_path, invalid_wait))

    def test_materialize_recorder_config_maps_recipe_to_record_demo_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            matrix = run_demo_matrix.parse_matrix(self.write_matrix(tmp_path, self.base_matrix(tmp_path)))
            recipe = matrix.recipes[0]
            config = run_demo_matrix.materialize_recorder_config(matrix, recipe)

        self.assertEqual(config["demoName"], "demo-one")
        self.assertEqual(config["command"]["cwd"], str(tmp_path))
        self.assertEqual(config["command"]["path"], str(recipe.binary))
        self.assertEqual(config["command"]["args"], ["--dangerously-skip-permissions"])
        self.assertFalse(config["publish"]["enabled"])
        self.assertTrue(config["preparedGhostty"]["requireAlreadyRunning"])
        self.assertTrue(config["preparedGhostty"]["requireSingleWindowIfDetectable"])
        self.assertEqual(
            config["publish"]["outputGif"],
            str(run_demo_matrix.ROOT / "assets" / "demos" / "demo-one.gif"),
        )

    def test_materialize_recorder_config_deep_merges_recording_override(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            data = self.base_matrix(tmp_path)
            data["recipes"][0]["recording"] = {"recordSeconds": 20}
            data["recipes"][0]["checkpoints"] = [{"name": "final", "atSeconds": 4}]
            matrix = run_demo_matrix.parse_matrix(self.write_matrix(tmp_path, data))
            config = run_demo_matrix.materialize_recorder_config(matrix, matrix.recipes[0])

        self.assertEqual(config["recording"]["start"], "afterLaunchSettle")
        self.assertEqual(config["recording"]["postLaunchWaitSeconds"], 5)
        self.assertEqual(config["recording"]["recordSeconds"], 20)

    def test_write_generated_config_round_trips_through_record_demo_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            matrix = run_demo_matrix.parse_matrix(self.write_matrix(tmp_path, self.base_matrix(tmp_path)))
            output = tmp_path / "generated" / "demo-one.json"
            run_demo_matrix.write_generated_config(matrix, matrix.recipes[0], output)
            loaded = json.loads(output.read_text(encoding="utf-8"))
            record_demo = run_demo_matrix.load_record_demo_module()
            parsed = record_demo.parse_config(output)
            record_demo.validate_config(parsed)

        self.assertEqual(loaded["demoName"], "demo-one")
        self.assertEqual(loaded["events"][-1], {"type": "key", "key": "ctrl-c"})

    def test_load_record_demo_module_cache_is_keyed_by_adjacent_record_demo_path(self) -> None:
        original_dir = getattr(run_demo_matrix, "DEMO_RECORDER_DIR", DEMO_RECORDER_DIR)
        try:
            with tempfile.TemporaryDirectory() as temp:
                tmp_path = Path(temp)
                first_dir = tmp_path / "first"
                second_dir = tmp_path / "second"
                first_dir.mkdir()
                second_dir.mkdir()
                for directory, marker in ((first_dir, "first"), (second_dir, "second")):
                    (directory / "record_demo.py").write_text(
                        "\n".join(
                            [
                                "class RecorderError(RuntimeError):",
                                "    pass",
                                f"MARKER = {marker!r}",
                                "def validate_events(events):",
                                "    return None",
                                "def parse_config(path):",
                                "    return object()",
                                "def validate_config(config):",
                                "    return None",
                            ]
                        )
                        + "\n",
                        encoding="utf-8",
                    )

                run_demo_matrix.DEMO_RECORDER_DIR = first_dir
                first = run_demo_matrix.load_record_demo_module()
                run_demo_matrix.DEMO_RECORDER_DIR = second_dir
                second = run_demo_matrix.load_record_demo_module()

            self.assertIsNot(first, second)
            self.assertEqual(first.MARKER, "first")
            self.assertEqual(second.MARKER, "second")
            self.assertEqual(Path(first.__file__).resolve(), (first_dir / "record_demo.py").resolve())
            self.assertEqual(Path(second.__file__).resolve(), (second_dir / "record_demo.py").resolve())
        finally:
            run_demo_matrix.DEMO_RECORDER_DIR = original_dir

    def test_load_record_demo_module_removes_failed_import_from_sys_modules(self) -> None:
        original_dir = getattr(run_demo_matrix, "DEMO_RECORDER_DIR", DEMO_RECORDER_DIR)
        try:
            with tempfile.TemporaryDirectory() as temp:
                tmp_path = Path(temp)
                bad_dir = tmp_path / "bad"
                bad_dir.mkdir()
                bad_path = bad_dir / "record_demo.py"
                bad_path.write_text("raise RuntimeError('boom during import')\n", encoding="utf-8")
                run_demo_matrix.DEMO_RECORDER_DIR = bad_dir

                with self.assertRaisesRegex(RuntimeError, "boom during import"):
                    run_demo_matrix.load_record_demo_module()

                leaked = [
                    name
                    for name, module in sys.modules.items()
                    if getattr(module, "__file__", None) and Path(module.__file__).resolve() == bad_path.resolve()
                ]
            self.assertEqual(leaked, [])
        finally:
            run_demo_matrix.DEMO_RECORDER_DIR = original_dir

    def test_select_recipe_rejects_disabled_without_include_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            data = self.base_matrix(tmp_path)
            data["recipes"][0]["enabled"] = False
            data["recipes"][0]["disabledReason"] = "Manual only."
            matrix = run_demo_matrix.parse_matrix(self.write_matrix(tmp_path, data))

            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "disabled"):
                run_demo_matrix.select_recipe(matrix, "demo-one", include_disabled=False)

    def test_select_recipe_allows_disabled_with_include_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            data = self.base_matrix(tmp_path)
            data["recipes"][0]["enabled"] = False
            data["recipes"][0]["disabledReason"] = "Manual only."
            matrix = run_demo_matrix.parse_matrix(self.write_matrix(tmp_path, data))
            recipe = run_demo_matrix.select_recipe(matrix, "demo-one", include_disabled=True)

        self.assertEqual(recipe.id, "demo-one")

    def test_list_rows_include_recipe_display_fields_and_binary_existence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            data = self.base_matrix(tmp_path)
            data["recipes"].append(
                {
                    "id": "future-demo",
                    "enabled": False,
                    "category": "drawer",
                    "purpose": "Future drawer demo.",
                    "disabledReason": "Manual only.",
                    "events": [],
                }
            )
            matrix = run_demo_matrix.parse_matrix(self.write_matrix(tmp_path, data))
            rows = run_demo_matrix.list_rows(matrix)

        self.assertEqual(
            rows[0],
            {
                "id": "demo-one",
                "enabled": True,
                "category": "visual",
                "purpose": "Exercise a visual demo.",
                "binaryExists": True,
                "disabledReason": None,
            },
        )
        self.assertEqual(rows[1]["id"], "future-demo")
        self.assertEqual(rows[1]["binaryExists"], False)
        self.assertEqual(rows[1]["disabledReason"], "Manual only.")

    def test_print_list_emits_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            matrix = run_demo_matrix.parse_matrix(self.write_matrix(tmp_path, self.base_matrix(tmp_path)))
            buffer = io.StringIO()
            with contextlib.redirect_stdout(buffer):
                run_demo_matrix.print_list(matrix)

        self.assertIn("demo-one", buffer.getvalue())
        self.assertIn("binary:yes", buffer.getvalue())

    def test_main_list_and_dry_run_modes_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            matrix_path = self.write_matrix(tmp_path, self.base_matrix(tmp_path))
            status, stdout, stderr = self.call_main(
                ["--matrix", str(matrix_path), "--list", "--dry-run", "--id", "demo-one"]
            )

        self.assertNotEqual(status, 0)
        self.assertEqual(stdout, "")
        self.assertIn("conflicting", stderr)

    def test_main_list_and_id_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            matrix_path = self.write_matrix(tmp_path, self.base_matrix(tmp_path))
            status, stdout, stderr = self.call_main(["--matrix", str(matrix_path), "--list", "--id", "demo-one"])

        self.assertEqual(status, 2)
        self.assertEqual(stdout, "")
        self.assertIn("conflicting", stderr)
        self.assertIn("--list", stderr)
        self.assertIn("--id", stderr)

    def test_main_list_and_all_enabled_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            matrix_path = self.write_matrix(tmp_path, self.base_matrix(tmp_path))
            status, stdout, stderr = self.call_main(["--matrix", str(matrix_path), "--list", "--all-enabled"])

        self.assertEqual(status, 2)
        self.assertEqual(stdout, "")
        self.assertIn("conflicting", stderr)
        self.assertIn("--list", stderr)
        self.assertIn("--all-enabled", stderr)

    def test_main_dry_run_id_and_all_enabled_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            matrix_path = self.write_matrix(tmp_path, self.base_matrix(tmp_path))
            status, stdout, stderr = self.call_main(
                ["--matrix", str(matrix_path), "--dry-run", "--id", "demo-one", "--all-enabled"]
            )

        self.assertEqual(status, 2)
        self.assertEqual(stdout, "")
        self.assertIn("conflicting", stderr)

    def test_main_list_and_publish_from_summary_modes_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            matrix_path = self.write_matrix(tmp_path, self.base_matrix(tmp_path))
            status, stdout, stderr = self.call_main(
                ["--matrix", str(matrix_path), "--list", "--publish-from-summary", str(tmp_path / "summary.json")]
            )

        self.assertNotEqual(status, 0)
        self.assertEqual(stdout, "")
        self.assertIn("conflicting", stderr)

    def test_main_dry_run_validates_config_with_record_demo_before_printing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            data = self.base_matrix(tmp_path)
            data["recipes"][0]["app"] = {"launchMode": "invalid-launch-mode"}
            matrix_path = self.write_matrix(tmp_path, data)
            status, stdout, stderr = self.call_main(["--matrix", str(matrix_path), "--dry-run", "--id", "demo-one"])

        self.assertEqual(status, 2)
        self.assertEqual(stdout, "")
        self.assertIn("app.launchMode", stderr)

    def test_main_list_still_prints_recipes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            matrix_path = self.write_matrix(tmp_path, self.base_matrix(tmp_path))
            status, stdout, stderr = self.call_main(["--matrix", str(matrix_path), "--list"])

        self.assertEqual(status, 0)
        self.assertIn("demo-one", stdout)
        self.assertEqual(stderr, "")

    def test_main_dry_run_still_prints_validated_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            matrix_path = self.write_matrix(tmp_path, self.base_matrix(tmp_path))
            status, stdout, stderr = self.call_main(["--matrix", str(matrix_path), "--dry-run", "--id", "demo-one"])

        self.assertEqual(status, 0)
        loaded = json.loads(stdout)
        self.assertEqual(loaded["demoName"], "demo-one")
        self.assertFalse(loaded["publish"]["enabled"])
        self.assertEqual(stderr, "")


    def test_default_matrix_recordings_dir_uses_spec_layout(self) -> None:
        self.assertEqual(
            run_demo_matrix.DEFAULT_MATRIX_RECORDINGS_DIR,
            run_demo_matrix.ROOT / ".development" / "demo-recordings" / "matrix",
        )

    def test_summary_record_includes_recording_and_publish_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            raw = tmp_path / "raw.mov"
            gif = tmp_path / "demo.gif"
            published = tmp_path / "published.gif"
            metadata = {
                "runDir": str(tmp_path),
                "raw": str(raw),
                "gif": str(gif),
                "published": str(published),
                "calibration": {"ok": True},
                "recordingStatus": "recorded",
                "launchVerified": True,
                "launch": {"verified": True, "runId": "run-123"},
                "reviewStatus": "needs-human-review",
            }
            generated_config = tmp_path / "generated" / "demo-one.json"
            checkpoints = {"final": tmp_path / "checkpoints" / "final.png"}
            matrix = run_demo_matrix.parse_matrix(self.write_matrix(tmp_path, self.base_matrix(tmp_path)))
            record = run_demo_matrix.summary_record(matrix.recipes[0], generated_config, metadata, checkpoints)

        self.assertEqual(record["id"], "demo-one")
        self.assertEqual(record["status"], "recorded")
        self.assertEqual(record["generatedConfig"], str(generated_config))
        self.assertEqual(record["runDir"], str(tmp_path))
        self.assertEqual(record["raw"], str(raw))
        self.assertEqual(record["gif"], str(gif))
        self.assertEqual(record["published"], str(published))
        self.assertEqual(record["recordingStatus"], "recorded")
        self.assertEqual(record["launchStatus"], "verified")
        self.assertTrue(record["launchVerified"])
        self.assertEqual(record["reviewStatus"], "needs-human-review")
        self.assertTrue(record["needsReview"])
        self.assertEqual(record["publishStatus"], "published")
        self.assertEqual(record["publishGif"], str(run_demo_matrix.ROOT / "assets" / "demos" / "demo-one.gif"))
        self.assertEqual(record["checkpoints"], {"final": str(checkpoints["final"])})

    def test_checkpoint_argv_builds_ffmpeg_single_frame_command(self) -> None:
        raw = Path("/tmp/raw.mov")
        output = Path("/tmp/frame.png")
        self.assertEqual(
            run_demo_matrix.checkpoint_argv(raw, output, 1.25),
            ["ffmpeg", "-y", "-ss", "1.25", "-i", str(raw), "-frames:v", "1", str(output)],
        )

    def test_extract_checkpoint_rejects_failed_subprocess_and_missing_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            raw = tmp_path / "raw.mov"
            raw.write_bytes(b"raw")
            output = tmp_path / "checkpoint.png"
            failed = subprocess_result(returncode=1, stderr="ffmpeg failed")
            with mock.patch.object(run_demo_matrix.subprocess, "run", return_value=failed):
                with self.assertRaisesRegex(run_demo_matrix.MatrixError, "checkpoint extraction failed"):
                    run_demo_matrix.extract_checkpoint(raw, output, 2)

            ok = subprocess_result(returncode=0)
            with mock.patch.object(run_demo_matrix.subprocess, "run", return_value=ok):
                with self.assertRaisesRegex(run_demo_matrix.MatrixError, "missing or empty"):
                    run_demo_matrix.extract_checkpoint(raw, output, 2)

    def test_extract_checkpoint_returns_output_when_subprocess_creates_frame(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            raw = tmp_path / "raw.mov"
            raw.write_bytes(b"raw")
            output = tmp_path / "checkpoint.png"

            def fake_run(argv, **kwargs):
                output.write_bytes(b"png")
                return subprocess_result(returncode=0)

            with mock.patch.object(run_demo_matrix.subprocess, "run", side_effect=fake_run) as run_mock:
                result = run_demo_matrix.extract_checkpoint(raw, output, 2)

        self.assertEqual(result, output)
        run_mock.assert_called_once()

    def test_run_recipe_writes_config_invokes_record_demo_and_extracts_checkpoints(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            matrix = run_demo_matrix.parse_matrix(self.write_matrix(tmp_path, self.base_matrix(tmp_path)))
            recipe = matrix.recipes[0]
            batch_dir = tmp_path / "batch"
            raw = tmp_path / "recording" / "raw.mov"
            gif = tmp_path / "recording" / "demo.gif"
            raw.parent.mkdir()
            raw.write_bytes(b"raw")
            gif.write_bytes(b"gif")
            fake_module = mock.Mock()
            parsed = object()
            fake_module.parse_config.return_value = parsed
            fake_module.validate_config.return_value = None
            fake_module.run_recording.return_value = {
                "runDir": str(raw.parent),
                "raw": str(raw),
                "gif": str(gif),
                "published": None,
                "launchVerified": True,
                "launch": {"verified": True, "runId": "demo-one-test"},
                "reviewStatus": "needs-human-review",
            }

            with mock.patch.object(run_demo_matrix, "load_record_demo_module", return_value=fake_module), mock.patch.object(
                run_demo_matrix, "extract_checkpoint", return_value=batch_dir / "checkpoints" / "demo-one-final.png"
            ) as extract_mock:
                record = run_demo_matrix.run_recipe(matrix, recipe, batch_dir)

            generated_config = batch_dir / "generated-configs" / "demo-one.json"
            self.assertTrue(generated_config.exists())
            loaded = json.loads(generated_config.read_text(encoding="utf-8"))
            self.assertEqual(loaded["demoName"], "demo-one")
            self.assertFalse(loaded["publish"]["enabled"])
            fake_module.run_recording.assert_called_once_with(parsed, generated_config, cli_publish=False)
            extract_mock.assert_called_once_with(raw, batch_dir / "checkpoints" / "demo-one-final.png", 3.0)
            self.assertGreaterEqual(fake_module.parse_config.call_count, 1)
            self.assertGreaterEqual(fake_module.validate_config.call_count, 1)
            self.assertEqual(record["id"], "demo-one")
            self.assertEqual(record["status"], "recorded")
            self.assertEqual(record["generatedConfig"], str(generated_config))
            self.assertEqual(record["checkpoints"], {"final": str(batch_dir / "checkpoints" / "demo-one-final.png")})

    def test_write_batch_summary_writes_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            matrix_path = tmp_path / "demo_matrix.json"
            matrix_path.write_text("{}", encoding="utf-8")
            records = [{"id": "demo-one", "status": "passed", "gif": str(tmp_path / "demo.gif")}]
            summary_path = run_demo_matrix.write_batch_summary(tmp_path / "batch", matrix_path, records)
            markdown_path = summary_path.with_suffix(".md")

            self.assertEqual(summary_path.name, "summary.json")
            self.assertTrue(summary_path.exists())
            self.assertTrue(markdown_path.exists())
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary["matrix"], str(matrix_path))
            self.assertEqual(summary["records"], records)
            self.assertIn("demo-one", markdown_path.read_text(encoding="utf-8"))

    def test_main_records_one_recipe_without_publishing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            matrix_path = self.write_matrix(tmp_path, self.base_matrix(tmp_path))
            fixed_batch = tmp_path / "batch"
            fake_record = {"id": "demo-one", "status": "recorded", "recordingStatus": "recorded", "launchStatus": "verified", "reviewStatus": "needs-human-review", "gif": str(tmp_path / "demo.gif"), "publishGif": str(tmp_path / "pub.gif")}
            with mock.patch.object(run_demo_matrix, "make_matrix_run_dir", return_value=fixed_batch), mock.patch.object(
                run_demo_matrix, "run_recipe", return_value=fake_record
            ) as run_mock:
                status, stdout, stderr = self.call_main(["--matrix", str(matrix_path), "--id", "demo-one"])

            self.assertEqual(status, 0)
            self.assertEqual(stderr, "")
            self.assertIn("Privacy reminder", stdout)
            loaded = load_json_from_stdout(stdout)
            self.assertEqual(loaded["batchDir"], str(fixed_batch))
            self.assertEqual(loaded["records"], [fake_record])
            self.assertTrue((fixed_batch / "matrix.snapshot.json").exists())
            self.assertTrue((fixed_batch / "summary.json").exists())
            run_mock.assert_called_once()

    def test_main_records_all_enabled_without_real_recording(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            data = self.base_matrix(tmp_path)
            second = dict(data["recipes"][0])
            second["id"] = "demo-two"
            second["publishGif"] = str(run_demo_matrix.ROOT / "assets" / "demos" / "demo-two.gif")
            data["recipes"].append(second)
            data["recipes"].append(
                {
                    "id": "disabled-demo",
                    "enabled": False,
                    "category": "future",
                    "purpose": "Disabled recipe is not recorded.",
                    "disabledReason": "Not selected.",
                    "events": [],
                }
            )
            matrix_path = self.write_matrix(tmp_path, data)
            fixed_batch = tmp_path / "batch"

            def fake_run_recipe(matrix, recipe, batch_dir):
                return {"id": recipe.id, "status": "recorded", "recordingStatus": "recorded", "launchStatus": "verified", "reviewStatus": "needs-human-review", "gif": str(tmp_path / f"{recipe.id}.gif")}

            with mock.patch.object(run_demo_matrix, "make_matrix_run_dir", return_value=fixed_batch), mock.patch.object(
                run_demo_matrix, "run_recipe", side_effect=fake_run_recipe
            ) as run_mock:
                status, stdout, stderr = self.call_main(["--matrix", str(matrix_path), "--all-enabled"])

            self.assertEqual(status, 0)
            self.assertEqual(stderr, "")
            self.assertIn("Privacy reminder", stdout)
            loaded = load_json_from_stdout(stdout)
            self.assertEqual([record["id"] for record in loaded["records"]], ["demo-one", "demo-two"])
            self.assertEqual([call.args[1].id for call in run_mock.call_args_list], ["demo-one", "demo-two"])
            self.assertTrue((fixed_batch / "summary.json").exists())
            summary = json.loads((fixed_batch / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual([record["id"] for record in summary["records"]], ["demo-one", "demo-two"])

    def test_publish_from_summary_copies_reviewed_gif(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            gif = tmp_path / "reviewed.gif"
            gif.write_bytes(b"gif")
            publish = run_demo_matrix.ROOT / "assets" / "demos" / "test-demo-matrix-reviewed.gif"
            summary = tmp_path / "summary.json"
            summary.write_text(
                json.dumps({"records": [{"id": "demo-one", "status": "recorded", "reviewStatus": "approved", "launchVerified": True, "gif": str(gif), "publishGif": str(publish)}]}),
                encoding="utf-8",
            )

            try:
                result = run_demo_matrix.publish_from_summary(summary, "demo-one")
                self.assertEqual(result, publish)
                self.assertEqual(publish.read_bytes(), b"gif")
            finally:
                publish.unlink(missing_ok=True)

    def test_publish_from_summary_rejects_publish_gif_outside_assets_demos(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            gif = tmp_path / "reviewed.gif"
            gif.write_bytes(b"gif")
            publish = tmp_path / "publish" / "demo.gif"
            summary = tmp_path / "summary.json"
            summary.write_text(
                json.dumps({"records": [{"id": "demo-one", "status": "recorded", "reviewStatus": "approved", "launchVerified": True, "gif": str(gif), "publishGif": str(publish)}]}),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "publishGif must be under"):
                run_demo_matrix.publish_from_summary(summary, "demo-one")

    def test_publish_from_summary_rejects_missing_recipe(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            summary = Path(temp) / "summary.json"
            summary.write_text(json.dumps({"records": []}), encoding="utf-8")
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "recipe not found"):
                run_demo_matrix.publish_from_summary(summary, "demo-one")

    def test_publish_from_summary_rejects_non_passed_record(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            summary = Path(temp) / "summary.json"
            summary.write_text(json.dumps({"records": [{"id": "demo-one", "status": "recorded", "reviewStatus": "needs-human-review", "launchVerified": True}]}), encoding="utf-8")
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "not review approved"):
                run_demo_matrix.publish_from_summary(summary, "demo-one")

    def test_publish_from_summary_rejects_unverified_launch_even_if_approved(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            gif = tmp_path / "reviewed.gif"
            gif.write_bytes(b"gif")
            publish = run_demo_matrix.ROOT / "assets" / "demos" / "test-demo-matrix-unverified.gif"
            summary = tmp_path / "summary.json"
            summary.write_text(
                json.dumps({"records": [{"id": "demo-one", "status": "recorded", "reviewStatus": "approved", "launchVerified": False, "gif": str(gif), "publishGif": str(publish)}]}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "verified launch"):
                run_demo_matrix.publish_from_summary(summary, "demo-one")

    def test_publish_from_summary_rejects_missing_gif(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            publish = tmp_path / "publish" / "demo.gif"
            summary = tmp_path / "summary.json"
            summary.write_text(
                json.dumps({"records": [{"id": "demo-one", "status": "recorded", "reviewStatus": "approved", "launchVerified": True, "gif": str(tmp_path / "missing.gif"), "publishGif": str(publish)}]}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "gif is missing"):
                run_demo_matrix.publish_from_summary(summary, "demo-one")

    def test_publish_from_summary_rejects_missing_publish_gif(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            gif = tmp_path / "reviewed.gif"
            gif.write_bytes(b"gif")
            summary = tmp_path / "summary.json"
            summary.write_text(
                json.dumps({"records": [{"id": "demo-one", "status": "recorded", "reviewStatus": "approved", "launchVerified": True, "gif": str(gif)}]}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "publishGif"):
                run_demo_matrix.publish_from_summary(summary, "demo-one")

    def test_main_publish_from_summary_requires_id_and_prints_published_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            gif = tmp_path / "reviewed.gif"
            gif.write_bytes(b"gif")
            publish = run_demo_matrix.ROOT / "assets" / "demos" / "test-demo-matrix-cli-reviewed.gif"
            summary = tmp_path / "summary.json"
            summary.write_text(
                json.dumps({"records": [{"id": "demo-one", "status": "recorded", "reviewStatus": "approved", "launchVerified": True, "gif": str(gif), "publishGif": str(publish)}]}),
                encoding="utf-8",
            )

            missing_status, missing_stdout, missing_stderr = self.call_main(["--publish-from-summary", str(summary)])
            try:
                status, stdout, stderr = self.call_main(["--publish-from-summary", str(summary), "--id", "demo-one"])
                copied = publish.read_bytes()
            finally:
                publish.unlink(missing_ok=True)

            self.assertEqual(missing_status, 2)
            self.assertEqual(missing_stdout, "")
            self.assertIn("requires --id", missing_stderr)
            self.assertEqual(status, 0)
            self.assertEqual(stderr, "")
            self.assertEqual(json.loads(stdout), {"published": str(publish)})
            self.assertEqual(copied, b"gif")

    def test_main_publish_from_summary_id_and_all_enabled_conflict_is_publish_specific(self) -> None:
        status, stdout, stderr = self.call_main(
            ["--publish-from-summary", "/tmp/summary.json", "--id", "demo-one", "--all-enabled"]
        )

        self.assertEqual(status, 2)
        self.assertEqual(stdout, "")
        self.assertIn("publishes exactly one --id", stderr)
        self.assertNotIn("conflicting recording targets", stderr)

if __name__ == "__main__":
    unittest.main()


def load_json_from_stdout(stdout: str):
    start = stdout.find("{")
    if start == -1:
        raise AssertionError(f"stdout did not contain a JSON object: {stdout!r}")
    return json.loads(stdout[start:])


def subprocess_result(*, returncode: int, stdout: str = "", stderr: str = ""):
    return run_demo_matrix.subprocess.CompletedProcess(["ffmpeg"], returncode, stdout=stdout, stderr=stderr)
