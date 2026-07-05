# Demo Matrix Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local demo matrix runner that turns curated demo recipes into existing `record_demo.py` runs, extracts checkpoint frames, writes summaries, and publishes only from reviewed summaries.

**Architecture:** Keep `record_demo.py` as the single-demo executor. Add `run_demo_matrix.py` for matrix parsing, validation, config materialization, recorder invocation, checkpoint extraction, summary writing, and reviewed publish-from-summary. Add `demo_matrix.json` as a local curated recipe list and `test_demo_matrix.py` for unit coverage without Ghostty or ffmpeg.

**Tech Stack:** Python 3 standard library, JSON, `unittest`, existing `.development/demo-recorder/record_demo.py`, ffmpeg only through controlled subprocess calls for checkpoint extraction.

---

## Execution notes

- Work in `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder`.
- Do not edit `/Users/MAC/Documents/Claude-patch` main checkout for this implementation.
- Do not edit `packages/**`, `src/**`, package payloads, or build artifacts.
- `.development/demo-recorder/**` is local tooling; it may be ignored by git. The durable tracked artifact for this workflow is the design spec and this plan.
- Do not run real screen recording unless the user confirms the screen is privacy-safe and Ghostty is prepared.
- Recording-time publishing is forbidden. Public copy only happens through `--publish-from-summary` after human review.

## File structure

**Create:**
- `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recorder/run_demo_matrix.py` — CLI and implementation for matrix orchestration.
- `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recorder/demo_matrix.json` — initial curated matrix.
- `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recorder/tests/test_demo_matrix.py` — unit tests for parsing, validation, materialization, summaries, checkpoints, and publish-from-summary.

**Modify:**
- `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recorder/README.md` — add matrix usage, privacy, skipped package notes, and publish-from-summary workflow.

**Read only:**
- `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recorder/record_demo.py` — import as a module; do not duplicate its Ghostty/ffmpeg recorder logic.
- `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/docs/superpowers/specs/2026-07-04-demo-matrix-runner-design.md` — source of truth for behavior.

---

### Task 1: Add matrix parser, dataclasses, and validation

**Files:**
- Create: `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recorder/run_demo_matrix.py`
- Create: `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recorder/tests/test_demo_matrix.py`

- [ ] **Step 1: Create failing parser and validation tests**

Create `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recorder/tests/test_demo_matrix.py` with this initial content:

```python
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "run_demo_matrix.py"
spec = importlib.util.spec_from_file_location("run_demo_matrix", MODULE_PATH)
run_demo_matrix = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = run_demo_matrix
spec.loader.exec_module(run_demo_matrix)


def write_json(path: Path, data: dict) -> Path:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def make_binary(tmp_path: Path, name: str = "claude") -> Path:
    binary = tmp_path / name
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    binary.chmod(0o755)
    return binary


def base_matrix(tmp_path: Path) -> dict:
    binary = make_binary(tmp_path)
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


class DemoMatrixParserTests(unittest.TestCase):
    def test_parse_matrix_accepts_valid_enabled_recipe(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            matrix = run_demo_matrix.parse_matrix(write_json(tmp_path / "matrix.json", base_matrix(tmp_path)))
            self.assertEqual(matrix.version, 1)
            self.assertEqual(matrix.recipes[0].id, "demo-one")
            self.assertTrue(matrix.recipes[0].enabled)

    def test_parse_matrix_rejects_duplicate_recipe_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            data = base_matrix(tmp_path)
            data["recipes"].append(dict(data["recipes"][0]))
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "duplicate recipe id"):
                run_demo_matrix.parse_matrix(write_json(tmp_path / "matrix.json", data))

    def test_parse_matrix_rejects_unknown_recipe_keys(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            data = base_matrix(tmp_path)
            data["recipes"][0]["surprise"] = True
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "unknown recipe keys"):
                run_demo_matrix.parse_matrix(write_json(tmp_path / "matrix.json", data))

    def test_parse_matrix_rejects_enabled_missing_binary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            data = base_matrix(tmp_path)
            data["recipes"][0]["binary"] = str(tmp_path / "missing")
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "binary does not exist"):
                run_demo_matrix.parse_matrix(write_json(tmp_path / "matrix.json", data))

    def test_parse_matrix_rejects_publish_path_outside_assets_demos(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            data = base_matrix(tmp_path)
            data["recipes"][0]["publishGif"] = str(tmp_path / "public.gif")
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "publishGif must be under"):
                run_demo_matrix.parse_matrix(write_json(tmp_path / "matrix.json", data))

    def test_parse_matrix_allows_disabled_placeholder_without_binary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            data = base_matrix(tmp_path)
            data["recipes"][0] = {
                "id": "future-demo",
                "enabled": False,
                "category": "drawer",
                "purpose": "Future drawer demo.",
                "disabledReason": "Preferred reviewed stack artifact has not been selected.",
                "events": [],
            }
            matrix = run_demo_matrix.parse_matrix(write_json(tmp_path / "matrix.json", data))
            self.assertFalse(matrix.recipes[0].enabled)
            self.assertEqual(matrix.recipes[0].disabled_reason, "Preferred reviewed stack artifact has not been selected.")

    def test_parse_matrix_rejects_checkpoint_at_recording_end(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            data = base_matrix(tmp_path)
            data["recipes"][0]["recording"] = {"recordSeconds": 3}
            data["recipes"][0]["checkpoints"] = [{"name": "bad", "atSeconds": 3}]
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "checkpoint time"):
                run_demo_matrix.parse_matrix(write_json(tmp_path / "matrix.json", data))

    def test_parse_matrix_rejects_duplicate_checkpoint_names(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            data = base_matrix(tmp_path)
            data["recipes"][0]["checkpoints"] = [
                {"name": "open", "atSeconds": 3},
                {"name": "open", "atSeconds": 4},
            ]
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "duplicate checkpoint"):
                run_demo_matrix.parse_matrix(write_json(tmp_path / "matrix.json", data))

    def test_parse_matrix_rejects_wait_schedule_too_close_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            data = base_matrix(tmp_path)
            data["recipes"][0]["recording"] = {"recordSeconds": 3}
            data["recipes"][0]["events"] = [
                {"type": "wait", "seconds": 2.5},
                {"type": "key", "key": "ctrl-c"},
            ]
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "wait schedule"):
                run_demo_matrix.parse_matrix(write_json(tmp_path / "matrix.json", data))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests and verify they fail because the runner does not exist**

Run:

```bash
cd /Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder
python3 -m unittest discover -s .development/demo-recorder/tests -p 'test_demo_matrix.py'
```

Expected: import/setup failure mentioning `run_demo_matrix.py` does not exist or cannot be loaded.

- [ ] **Step 3: Create minimal parser implementation**

Create `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recorder/run_demo_matrix.py` with:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path("/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder")
DEMO_RECORDER_DIR = ROOT / ".development" / "demo-recorder"
DEFAULT_MATRIX = DEMO_RECORDER_DIR / "demo_matrix.json"
DEFAULT_MATRIX_RECORDINGS_DIR = ROOT / ".development" / "demo-recordings" / "matrix"
EVENT_MARGIN_SECONDS = 1.0
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
ALLOWED_RECIPE_KEYS = {
    "id",
    "demoName",
    "enabled",
    "category",
    "purpose",
    "disabledReason",
    "app",
    "screen",
    "cwd",
    "binary",
    "args",
    "recording",
    "events",
    "checkpoints",
    "publishGif",
    "leaveProcessRunning",
}


class MatrixError(RuntimeError):
    pass


@dataclass(frozen=True)
class Checkpoint:
    name: str
    at_seconds: float


@dataclass(frozen=True)
class Recipe:
    id: str
    demo_name: str | None
    enabled: bool
    category: str
    purpose: str
    disabled_reason: str | None
    app: dict[str, Any]
    screen: dict[str, Any]
    cwd: Path | None
    binary: Path | None
    args: tuple[str, ...] | None
    recording: dict[str, Any]
    events: tuple[dict[str, Any], ...]
    checkpoints: tuple[Checkpoint, ...]
    publish_gif: Path | None
    leave_process_running: bool


@dataclass(frozen=True)
class Matrix:
    version: int
    defaults: dict[str, Any]
    recipes: tuple[Recipe, ...]


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MatrixError(f"matrix not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise MatrixError(f"invalid JSON in {path}: {exc}") from exc


def require_dict(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise MatrixError(f"{label} must be an object")
    return value


def require_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise MatrixError(f"{label} must be a non-empty string")
    return value


def optional_path(value: Any, label: str) -> Path | None:
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise MatrixError(f"{label} must be a non-empty string when present")
    return Path(value).expanduser()


def ensure_safe_id(value: str, label: str) -> None:
    if not SAFE_ID_RE.match(value):
        raise MatrixError(f"{label} is not path-safe: {value!r}")


def merged_recording(defaults: dict[str, Any], recipe_raw: dict[str, Any]) -> dict[str, Any]:
    default_recording = require_dict(defaults.get("recording", {}), "defaults.recording")
    recipe_recording = require_dict(recipe_raw.get("recording", {}), "recipe.recording")
    return {**default_recording, **recipe_recording}


def record_seconds_for(defaults: dict[str, Any], recipe_raw: dict[str, Any]) -> float:
    recording = merged_recording(defaults, recipe_raw)
    value = recording.get("recordSeconds")
    if not isinstance(value, (int, float)) or value <= 0:
        raise MatrixError("recording.recordSeconds must be a positive number")
    return float(value)


def parse_checkpoints(raw: Any, *, record_seconds: float) -> tuple[Checkpoint, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise MatrixError("checkpoints must be an array")
    checkpoints: list[Checkpoint] = []
    seen: set[str] = set()
    for index, item in enumerate(raw):
        obj = require_dict(item, f"checkpoint {index}")
        name = require_string(obj.get("name"), f"checkpoint {index}.name")
        ensure_safe_id(name, f"checkpoint {index}.name")
        if name in seen:
            raise MatrixError(f"duplicate checkpoint name: {name}")
        seen.add(name)
        at_seconds = obj.get("atSeconds")
        if not isinstance(at_seconds, (int, float)) or at_seconds < 0 or float(at_seconds) >= record_seconds:
            raise MatrixError(f"checkpoint time must be >= 0 and < recordSeconds for {name}")
        checkpoints.append(Checkpoint(name=name, at_seconds=float(at_seconds)))
    return tuple(checkpoints)


def validate_events(events: tuple[dict[str, Any], ...], *, record_seconds: float, leave_process_running: bool) -> None:
    total_wait = 0.0
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            raise MatrixError(f"event {index} must be an object")
        if event.get("type") == "wait":
            seconds = event.get("seconds")
            if not isinstance(seconds, (int, float)) or seconds < 0:
                raise MatrixError(f"event {index} wait.seconds must be non-negative")
            total_wait += float(seconds)
    if total_wait + EVENT_MARGIN_SECONDS >= record_seconds and not leave_process_running:
        raise MatrixError("wait schedule must leave EVENT_MARGIN_SECONDS before recording end")
    if events and not leave_process_running:
        last = events[-1]
        if last.get("type") != "key" or last.get("key") != "ctrl-c":
            raise MatrixError("recipes that leave the shell clean must end with ctrl-c")


def validate_publish_path(path: Path | None, *, recipe_id: str) -> None:
    if path is None:
        return
    allowed_root = (ROOT / "assets" / "demos").resolve()
    resolved = path.resolve()
    if allowed_root != resolved and allowed_root not in resolved.parents:
        raise MatrixError(f"recipe {recipe_id} publishGif must be under {allowed_root}: {path}")


def parse_recipe(raw: dict[str, Any], *, defaults: dict[str, Any]) -> Recipe:
    unknown = set(raw) - ALLOWED_RECIPE_KEYS
    if unknown:
        raise MatrixError(f"unknown recipe keys: {', '.join(sorted(unknown))}")
    recipe_id = require_string(raw.get("id"), "recipe.id")
    ensure_safe_id(recipe_id, "recipe.id")
    enabled = bool(raw.get("enabled", False))
    category = require_string(raw.get("category"), f"recipe {recipe_id}.category")
    purpose = require_string(raw.get("purpose"), f"recipe {recipe_id}.purpose")
    disabled_reason = raw.get("disabledReason")
    if disabled_reason is not None:
        disabled_reason = require_string(disabled_reason, f"recipe {recipe_id}.disabledReason")
    binary = optional_path(raw.get("binary"), f"recipe {recipe_id}.binary")
    if enabled:
        if binary is None:
            raise MatrixError(f"recipe {recipe_id} binary is required when enabled")
        if not binary.exists() or not binary.is_file():
            raise MatrixError(f"recipe {recipe_id} binary does not exist or is not a file: {binary}")
    elif binary is None and not disabled_reason:
        raise MatrixError(f"recipe {recipe_id} disabledReason is required when disabled recipe omits binary")

    record_seconds = record_seconds_for(defaults, raw)
    events_raw = raw.get("events", [])
    if not isinstance(events_raw, list) or not all(isinstance(event, dict) for event in events_raw):
        raise MatrixError(f"recipe {recipe_id}.events must be an array of objects")
    events = tuple(events_raw)
    leave_process_running = bool(raw.get("leaveProcessRunning", False))
    validate_events(events, record_seconds=record_seconds, leave_process_running=leave_process_running)
    checkpoints = parse_checkpoints(raw.get("checkpoints", []), record_seconds=record_seconds)

    args_raw = raw.get("args")
    args = None
    if args_raw is not None:
        if not isinstance(args_raw, list) or not all(isinstance(arg, str) for arg in args_raw):
            raise MatrixError(f"recipe {recipe_id}.args must be an array of strings")
        args = tuple(args_raw)

    publish_gif = optional_path(raw.get("publishGif"), f"recipe {recipe_id}.publishGif")
    validate_publish_path(publish_gif, recipe_id=recipe_id)

    return Recipe(
        id=recipe_id,
        demo_name=raw.get("demoName") if isinstance(raw.get("demoName"), str) else None,
        enabled=enabled,
        category=category,
        purpose=purpose,
        disabled_reason=disabled_reason,
        app=require_dict(raw.get("app", {}), f"recipe {recipe_id}.app"),
        screen=require_dict(raw.get("screen", {}), f"recipe {recipe_id}.screen"),
        cwd=optional_path(raw.get("cwd"), f"recipe {recipe_id}.cwd"),
        binary=binary,
        args=args,
        recording=require_dict(raw.get("recording", {}), f"recipe {recipe_id}.recording"),
        events=events,
        checkpoints=checkpoints,
        publish_gif=publish_gif,
        leave_process_running=leave_process_running,
    )


def parse_matrix(path: Path) -> Matrix:
    raw = load_json(path)
    if raw.get("version") != 1:
        raise MatrixError("matrix version must be 1")
    defaults = require_dict(raw.get("defaults"), "defaults")
    recipes_raw = raw.get("recipes")
    if not isinstance(recipes_raw, list):
        raise MatrixError("recipes must be an array")
    recipes: list[Recipe] = []
    seen: set[str] = set()
    for item in recipes_raw:
        recipe = parse_recipe(require_dict(item, "recipe"), defaults=defaults)
        if recipe.id in seen:
            raise MatrixError(f"duplicate recipe id: {recipe.id}")
        seen.add(recipe.id)
        recipes.append(recipe)
    return Matrix(version=1, defaults=defaults, recipes=tuple(recipes))
```

- [ ] **Step 4: Run tests and verify parser tests pass**

Run:

```bash
cd /Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder
python3 -m unittest discover -s .development/demo-recorder/tests -p 'test_demo_matrix.py'
```

Expected: parser tests pass, including duplicate-id, missing-binary, publish-path, checkpoint, and event-duration validation.

---

### Task 2: Add config materialization and the initial matrix file

**Files:**
- Modify: `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recorder/run_demo_matrix.py`
- Modify: `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recorder/tests/test_demo_matrix.py`
- Create: `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recorder/demo_matrix.json`

- [ ] **Step 1: Add failing materialization tests**

Append these methods inside `DemoMatrixParserTests` before the `if __name__ == "__main__"` block in `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recorder/tests/test_demo_matrix.py`:

```python
    def test_materialize_recorder_config_maps_recipe_to_record_demo_shape(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            matrix = run_demo_matrix.parse_matrix(write_json(tmp_path / "matrix.json", base_matrix(tmp_path)))
            config = run_demo_matrix.materialize_recorder_config(matrix, matrix.recipes[0])
            self.assertEqual(config["demoName"], "demo-one")
            self.assertEqual(config["command"]["cwd"], str(tmp_path))
            self.assertEqual(config["command"]["path"], str(matrix.recipes[0].binary))
            self.assertEqual(config["command"]["args"], ["--dangerously-skip-permissions"])
            self.assertFalse(config["publish"]["enabled"])
            self.assertEqual(config["publish"]["outputGif"], str(run_demo_matrix.ROOT / "assets" / "demos" / "demo-one.gif"))

    def test_materialize_recorder_config_deep_merges_recording_override(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            data = base_matrix(tmp_path)
            data["recipes"][0]["recording"] = {"recordSeconds": 20}
            data["recipes"][0]["checkpoints"] = [{"name": "final", "atSeconds": 4}]
            matrix = run_demo_matrix.parse_matrix(write_json(tmp_path / "matrix.json", data))
            config = run_demo_matrix.materialize_recorder_config(matrix, matrix.recipes[0])
            self.assertEqual(config["recording"]["start"], "afterLaunchSettle")
            self.assertEqual(config["recording"]["postLaunchWaitSeconds"], 5)
            self.assertEqual(config["recording"]["recordSeconds"], 20)

    def test_write_generated_config_round_trips_through_record_demo_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            matrix = run_demo_matrix.parse_matrix(write_json(tmp_path / "matrix.json", base_matrix(tmp_path)))
            output = tmp_path / "generated" / "demo-one.json"
            run_demo_matrix.write_generated_config(matrix, matrix.recipes[0], output)
            loaded = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(loaded["demoName"], "demo-one")
            self.assertEqual(loaded["events"][-1], {"type": "key", "key": "ctrl-c"})
```

- [ ] **Step 2: Run tests and verify materialization tests fail**

Run:

```bash
cd /Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder
python3 -m unittest discover -s .development/demo-recorder/tests -p 'test_demo_matrix.py'
```

Expected: failures mention missing `materialize_recorder_config` and `write_generated_config`.

- [ ] **Step 3: Add record_demo import and materialization helpers**

Append this code to `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recorder/run_demo_matrix.py` after `parse_matrix`:

```python

def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(result.get(key), dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def materialize_recorder_config(matrix: Matrix, recipe: Recipe) -> dict[str, Any]:
    defaults = matrix.defaults
    app = deep_merge(require_dict(defaults.get("app"), "defaults.app"), recipe.app)
    screen = deep_merge(require_dict(defaults.get("screen"), "defaults.screen"), recipe.screen)
    recording = deep_merge(require_dict(defaults.get("recording"), "defaults.recording"), recipe.recording)
    cwd = recipe.cwd or optional_path(defaults.get("cwd"), "defaults.cwd")
    if cwd is None:
        raise MatrixError(f"recipe {recipe.id} has no cwd and defaults.cwd is missing")
    if recipe.binary is None:
        raise MatrixError(f"recipe {recipe.id} has no binary to materialize")
    args = list(recipe.args if recipe.args is not None else tuple(defaults.get("args", [])))
    if not all(isinstance(arg, str) for arg in args):
        raise MatrixError("materialized command args must be strings")
    return {
        "demoName": recipe.demo_name or recipe.id,
        "app": app,
        "screen": screen,
        "command": {
            "cwd": str(cwd),
            "path": str(recipe.binary),
            "args": args,
        },
        "recording": recording,
        "events": list(recipe.events),
        "publish": {
            "enabled": False,
            "outputGif": str(recipe.publish_gif) if recipe.publish_gif else None,
        },
    }


def load_record_demo_module() -> Any:
    module_path = DEMO_RECORDER_DIR / "record_demo.py"
    spec = importlib.util.spec_from_file_location("record_demo_for_matrix", module_path)
    if spec is None or spec.loader is None:
        raise MatrixError(f"could not load record_demo module from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def validate_with_record_demo(config_path: Path) -> None:
    record_demo = load_record_demo_module()
    config = record_demo.parse_config(config_path)
    record_demo.validate_config(config)


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_generated_config(matrix: Matrix, recipe: Recipe, output: Path) -> dict[str, Any]:
    config = materialize_recorder_config(matrix, recipe)
    write_json(output, config)
    validate_with_record_demo(output)
    return config
```

- [ ] **Step 4: Run tests and verify materialization tests pass**

Run:

```bash
cd /Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder
python3 -m unittest discover -s .development/demo-recorder/tests -p 'test_demo_matrix.py'
```

Expected: all tests in `test_demo_matrix.py` pass.

- [ ] **Step 5: Create the initial matrix file**

Create `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recorder/demo_matrix.json` with:

```json
{
  "version": 1,
  "defaults": {
    "app": {
      "name": "Ghostty",
      "bundleId": "com.mitchellh.ghostty",
      "leaveOpenAtEnd": true,
      "launchMode": "reuseRunning"
    },
    "screen": {
      "avfoundationDevice": "2",
      "label": "screen-0-dell",
      "crop": null,
      "fps": 12,
      "scaleWidth": 960
    },
    "cwd": "/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder",
    "args": ["--dangerously-skip-permissions"],
    "recording": {
      "start": "afterLaunchSettle",
      "postLaunchWaitSeconds": 5,
      "recordSeconds": 18
    }
  },
  "recipes": [
    {
      "id": "hotrod-dragons-2.1.201-wrap-comparison",
      "enabled": true,
      "category": "visual",
      "purpose": "Show the rich Hotrod Dragons terminal frame.",
      "binary": "/Users/MAC/Documents/Claude-patch/.development/claude-monkey-builds/hotrod-dragons-2.1.201-wrap-comparison/claude",
      "recording": {
        "recordSeconds": 14
      },
      "events": [
        {"type": "wait", "seconds": 10},
        {"type": "key", "key": "ctrl-c"}
      ],
      "checkpoints": [
        {"name": "final", "atSeconds": 8}
      ],
      "publishGif": "/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/assets/demos/hotrod-dragons.gif"
    },
    {
      "id": "hidden-context-plus-hotrod-dragons-open-close",
      "demoName": "hidden-context-plus-hotrod-dragons-2.1.199-open-drawer",
      "enabled": true,
      "category": "stack",
      "purpose": "Show Hotrod Dragons plus Hidden Context drawer opening and closing.",
      "binary": "/Users/MAC/Documents/Claude-patch/.development/claude-monkey-builds/hidden-context-plus-hotrod-dragons-2.1.199/claude",
      "recording": {
        "recordSeconds": 20
      },
      "events": [
        {"type": "wait", "seconds": 2},
        {"type": "key", "key": "down"},
        {"type": "wait", "seconds": 0.7},
        {"type": "key", "key": "down"},
        {"type": "wait", "seconds": 5},
        {"type": "key", "key": "x"},
        {"type": "wait", "seconds": 5},
        {"type": "key", "key": "ctrl-c"}
      ],
      "checkpoints": [
        {"name": "open", "atSeconds": 5},
        {"name": "closed", "atSeconds": 10}
      ],
      "publishGif": "/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/assets/demos/hidden-context-plus-hotrod-dragons-open-close.gif"
    },
    {
      "id": "capybara-onsen",
      "enabled": false,
      "category": "visual",
      "purpose": "Future Capybara Onsen visual frame demo.",
      "disabledReason": "Preferred reviewed artifact and framing have not been selected.",
      "events": []
    },
    {
      "id": "hidden-context-drawer-open-close",
      "enabled": false,
      "category": "drawer",
      "purpose": "Future standalone Hidden Context drawer open-close demo.",
      "disabledReason": "Preferred standalone drawer artifact and deterministic open-close sequence have not been selected.",
      "events": []
    },
    {
      "id": "reminders-manager-open-close",
      "enabled": false,
      "category": "drawer",
      "purpose": "Future Reminders Manager drawer demo.",
      "disabledReason": "Preferred reviewed stack artifact and deterministic key path have not been selected.",
      "events": []
    },
    {
      "id": "thinking-text-drawer-open-close",
      "enabled": false,
      "category": "drawer",
      "purpose": "Future Thinking Text drawer empty/open-state demo.",
      "disabledReason": "Preferred reviewed stack artifact and deterministic empty-state/open key path have not been selected.",
      "events": []
    }
  ]
}
```

- [ ] **Step 6: Validate the real matrix file with the parser**

Run:

```bash
cd /Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder
python3 - <<'PY'
import importlib.util
from pathlib import Path
module_path = Path('.development/demo-recorder/run_demo_matrix.py')
spec = importlib.util.spec_from_file_location('run_demo_matrix', module_path)
mod = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(mod)
matrix = mod.parse_matrix(Path('.development/demo-recorder/demo_matrix.json'))
print(len(matrix.recipes), [recipe.id for recipe in matrix.recipes if recipe.enabled])
PY
```

Expected output includes:

```text
6 ['hotrod-dragons-2.1.201-wrap-comparison', 'hidden-context-plus-hotrod-dragons-open-close']
```

---

### Task 3: Add CLI list and dry-run commands

**Files:**
- Modify: `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recorder/run_demo_matrix.py`
- Modify: `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recorder/tests/test_demo_matrix.py`

- [ ] **Step 1: Add failing CLI planning tests**

Append these tests inside `DemoMatrixParserTests`:

```python
    def test_select_recipe_rejects_disabled_without_include_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            data = base_matrix(tmp_path)
            data["recipes"][0]["enabled"] = False
            data["recipes"][0]["disabledReason"] = "Manual only."
            matrix = run_demo_matrix.parse_matrix(write_json(tmp_path / "matrix.json", data))
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "disabled"):
                run_demo_matrix.select_recipe(matrix, "demo-one", include_disabled=False)

    def test_select_recipe_allows_disabled_with_include_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            data = base_matrix(tmp_path)
            data["recipes"][0]["enabled"] = False
            data["recipes"][0]["disabledReason"] = "Manual only."
            matrix = run_demo_matrix.parse_matrix(write_json(tmp_path / "matrix.json", data))
            recipe = run_demo_matrix.select_recipe(matrix, "demo-one", include_disabled=True)
            self.assertEqual(recipe.id, "demo-one")

    def test_list_rows_include_binary_existence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            matrix = run_demo_matrix.parse_matrix(write_json(tmp_path / "matrix.json", base_matrix(tmp_path)))
            rows = run_demo_matrix.list_rows(matrix)
            self.assertEqual(rows[0]["id"], "demo-one")
            self.assertEqual(rows[0]["binaryExists"], True)
```

- [ ] **Step 2: Run tests and verify missing helpers fail**

Run:

```bash
cd /Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder
python3 -m unittest discover -s .development/demo-recorder/tests -p 'test_demo_matrix.py'
```

Expected: failures mention missing `select_recipe` and `list_rows`.

- [ ] **Step 3: Add selection/list helpers and CLI parser**

Append this code to `run_demo_matrix.py`:

```python

def select_recipe(matrix: Matrix, recipe_id: str, *, include_disabled: bool) -> Recipe:
    for recipe in matrix.recipes:
        if recipe.id == recipe_id:
            if recipe.enabled or include_disabled:
                return recipe
            raise MatrixError(f"recipe is disabled: {recipe_id}")
    raise MatrixError(f"unknown recipe id: {recipe_id}")


def enabled_recipes(matrix: Matrix) -> tuple[Recipe, ...]:
    return tuple(recipe for recipe in matrix.recipes if recipe.enabled)


def list_rows(matrix: Matrix) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for recipe in matrix.recipes:
        rows.append(
            {
                "id": recipe.id,
                "enabled": recipe.enabled,
                "category": recipe.category,
                "purpose": recipe.purpose,
                "binaryExists": bool(recipe.binary and recipe.binary.exists() and recipe.binary.is_file()),
                "disabledReason": recipe.disabled_reason,
            }
        )
    return rows


def print_list(matrix: Matrix) -> None:
    for row in list_rows(matrix):
        state = "enabled" if row["enabled"] else "disabled"
        binary = "binary:yes" if row["binaryExists"] else "binary:no"
        reason = f" disabledReason={row['disabledReason']}" if row.get("disabledReason") else ""
        print(f"{row['id']}\t{state}\t{row['category']}\t{binary}\t{row['purpose']}{reason}")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run curated ClaudeMonkey demo recorder recipes")
    parser.add_argument("--matrix", type=Path, default=DEFAULT_MATRIX, help="Path to demo_matrix.json")
    parser.add_argument("--list", action="store_true", help="List matrix recipes")
    parser.add_argument("--id", dest="recipe_id", help="Run or dry-run one recipe id")
    parser.add_argument("--include-disabled", action="store_true", help="Allow --id to select a disabled recipe")
    parser.add_argument("--all-enabled", action="store_true", help="Run all enabled recipes in matrix order")
    parser.add_argument("--dry-run", action="store_true", help="Validate and print generated recorder configs without recording")
    parser.add_argument("--publish-from-summary", type=Path, help="Copy one reviewed recipe GIF from a matrix summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        matrix = parse_matrix(args.matrix)
        if args.list:
            print_list(matrix)
            return 0
        if args.dry_run:
            if args.recipe_id:
                recipe = select_recipe(matrix, args.recipe_id, include_disabled=args.include_disabled)
                print(json.dumps(materialize_recorder_config(matrix, recipe), indent=2, sort_keys=True))
                return 0
            if args.all_enabled:
                configs = [materialize_recorder_config(matrix, recipe) for recipe in enabled_recipes(matrix)]
                print(json.dumps(configs, indent=2, sort_keys=True))
                return 0
            raise MatrixError("--dry-run requires --id or --all-enabled")
        raise MatrixError("v1 CLI currently supports --list and --dry-run in this task; recording is added later")
    except MatrixError as exc:
        print(f"demo-matrix: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests**

Run:

```bash
cd /Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder
python3 -m unittest discover -s .development/demo-recorder/tests -p 'test_demo_matrix.py'
```

Expected: all `test_demo_matrix.py` tests pass.

- [ ] **Step 5: Run list command against real matrix**

Run:

```bash
cd /Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder
python3 .development/demo-recorder/run_demo_matrix.py --list
```

Expected: output includes enabled rows for `hotrod-dragons-2.1.201-wrap-comparison` and `hidden-context-plus-hotrod-dragons-open-close`, and disabled placeholder rows for Capybara, Hidden Context standalone, Reminders, and Thinking.

- [ ] **Step 6: Run dry-run for the combined recipe**

Run:

```bash
cd /Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder
python3 .development/demo-recorder/run_demo_matrix.py \
  --dry-run \
  --id hidden-context-plus-hotrod-dragons-open-close
```

Expected: JSON includes:

```json
"demoName": "hidden-context-plus-hotrod-dragons-2.1.199-open-drawer"
```

and the events include `down`, `down`, `x`, and final `ctrl-c`.

---

### Task 4: Add recording orchestration, generated configs, summaries, and checkpoint frames

**Files:**
- Modify: `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recorder/run_demo_matrix.py`
- Modify: `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recorder/tests/test_demo_matrix.py`

- [ ] **Step 1: Add failing summary/checkpoint tests**

Append these tests inside `DemoMatrixParserTests`:

```python
    def test_summary_record_from_metadata_includes_paths_and_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            matrix = run_demo_matrix.parse_matrix(write_json(tmp_path / "matrix.json", base_matrix(tmp_path)))
            recipe = matrix.recipes[0]
            metadata = {
                "runDir": str(tmp_path / "run"),
                "raw": str(tmp_path / "run" / "raw.mov"),
                "gif": str(tmp_path / "run" / "demo.gif"),
                "published": None,
            }
            checkpoints = {"final": str(tmp_path / "checkpoint.png")}
            record = run_demo_matrix.summary_record(recipe, tmp_path / "generated.json", metadata, checkpoints)
            self.assertEqual(record["id"], "demo-one")
            self.assertEqual(record["status"], "passed")
            self.assertEqual(record["gif"], metadata["gif"])
            self.assertEqual(record["checkpoints"], checkpoints)

    def test_extract_checkpoint_builds_ffmpeg_command(self) -> None:
        raw = Path("/tmp/raw.mov")
        out = Path("/tmp/checkpoint.png")
        argv = run_demo_matrix.checkpoint_argv(raw, out, 3.5)
        self.assertEqual(argv[:4], ["ffmpeg", "-y", "-ss", "3.5"])
        self.assertEqual(argv[-2:], ["1", str(out)])
```

- [ ] **Step 2: Run tests and verify missing helpers fail**

Run:

```bash
cd /Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder
python3 -m unittest discover -s .development/demo-recorder/tests -p 'test_demo_matrix.py'
```

Expected: failures mention missing `summary_record` and `checkpoint_argv`.

- [ ] **Step 3: Add run directory, checkpoint, summary, and recorder invocation helpers**

Append this code above `build_arg_parser()` in `run_demo_matrix.py`:

```python

def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def make_matrix_run_dir(base: Path = DEFAULT_MATRIX_RECORDINGS_DIR) -> Path:
    run_dir = base / timestamp()
    run_dir.mkdir(parents=True, exist_ok=False)
    (run_dir / "generated-configs").mkdir()
    (run_dir / "checkpoints").mkdir()
    return run_dir


def checkpoint_argv(raw: Path, output: Path, at_seconds: float) -> list[str]:
    return ["ffmpeg", "-y", "-ss", str(at_seconds), "-i", str(raw), "-frames:v", "1", str(output)]


def extract_checkpoint(raw: Path, output: Path, at_seconds: float) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(checkpoint_argv(raw, output, at_seconds), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if result.returncode != 0:
        raise MatrixError(f"checkpoint extraction failed for {output}: {result.stderr.strip()}")
    if not output.exists() or output.stat().st_size == 0:
        raise MatrixError(f"checkpoint was not created or is empty: {output}")


def summary_record(recipe: Recipe, generated_config: Path, metadata: dict[str, Any], checkpoints: dict[str, str]) -> dict[str, Any]:
    return {
        "id": recipe.id,
        "status": "passed",
        "generatedConfig": str(generated_config),
        "runDir": str(metadata["runDir"]),
        "raw": str(metadata["raw"]),
        "gif": str(metadata["gif"]),
        "published": metadata.get("published"),
        "checkpoints": checkpoints,
        "publishGif": str(recipe.publish_gif) if recipe.publish_gif else None,
    }


def write_summary_markdown(path: Path, records: list[dict[str, Any]]) -> None:
    lines = ["# Demo Matrix Summary", ""]
    for record in records:
        lines.append(f"## {record['id']}")
        lines.append("")
        lines.append(f"- status: `{record['status']}`")
        lines.append(f"- gif: `{record.get('gif')}`")
        lines.append(f"- runDir: `{record.get('runDir')}`")
        if record.get("checkpoints"):
            lines.append("- checkpoints:")
            for name, checkpoint_path in record["checkpoints"].items():
                lines.append(f"  - {name}: `{checkpoint_path}`")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def run_recipe(matrix: Matrix, recipe: Recipe, batch_dir: Path) -> dict[str, Any]:
    generated_config = batch_dir / "generated-configs" / f"{recipe.id}.json"
    write_generated_config(matrix, recipe, generated_config)
    record_demo = load_record_demo_module()
    parsed = record_demo.parse_config(generated_config)
    record_demo.validate_config(parsed)
    metadata = record_demo.run_recording(parsed, generated_config, cli_publish=False)
    raw = Path(metadata["raw"])
    gif = Path(metadata["gif"])
    if not raw.exists() or raw.stat().st_size == 0:
        raise MatrixError(f"raw recording missing after recorder success: {raw}")
    if not gif.exists() or gif.stat().st_size == 0:
        raise MatrixError(f"gif missing after recorder success: {gif}")
    checkpoint_paths: dict[str, str] = {}
    for checkpoint in recipe.checkpoints:
        output = batch_dir / "checkpoints" / f"{recipe.id}-{checkpoint.name}.png"
        extract_checkpoint(raw, output, checkpoint.at_seconds)
        checkpoint_paths[checkpoint.name] = str(output)
    return summary_record(recipe, generated_config, metadata, checkpoint_paths)


def write_batch_summary(batch_dir: Path, matrix_path: Path, records: list[dict[str, Any]]) -> None:
    write_json(batch_dir / "summary.json", {"matrix": str(matrix_path), "records": records})
    write_summary_markdown(batch_dir / "summary.md", records)
```

- [ ] **Step 4: Update CLI main to run recipes**

In `main()` in `run_demo_matrix.py`, replace:

```python
        raise MatrixError("v1 CLI currently supports --list and --dry-run in this task; recording is added later")
```

with:

```python
        if args.recipe_id:
            print("Privacy reminder: selected screen must be safe to record; notifications hidden; Ghostty prepared.")
            batch_dir = make_matrix_run_dir()
            recipe = select_recipe(matrix, args.recipe_id, include_disabled=args.include_disabled)
            record = run_recipe(matrix, recipe, batch_dir)
            write_json(batch_dir / "matrix.snapshot.json", load_json(args.matrix))
            write_batch_summary(batch_dir, args.matrix, [record])
            print(json.dumps({"batchDir": str(batch_dir), "records": [record]}, indent=2, sort_keys=True))
            return 0
        if args.all_enabled:
            print("Privacy reminder: selected screen must be safe to record; notifications hidden; Ghostty prepared for every enabled recipe.")
            batch_dir = make_matrix_run_dir()
            write_json(batch_dir / "matrix.snapshot.json", load_json(args.matrix))
            records = []
            for recipe in enabled_recipes(matrix):
                records.append(run_recipe(matrix, recipe, batch_dir))
            write_batch_summary(batch_dir, args.matrix, records)
            print(json.dumps({"batchDir": str(batch_dir), "records": records}, indent=2, sort_keys=True))
            return 0
        raise MatrixError("choose --list, --dry-run, --id, --all-enabled, or --publish-from-summary")
```

- [ ] **Step 5: Run unit tests**

Run:

```bash
cd /Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder
python3 -m unittest discover -s .development/demo-recorder/tests -p 'test_demo_matrix.py'
```

Expected: all matrix tests pass.

- [ ] **Step 6: Run full local tests including existing recorder tests**

Run:

```bash
cd /Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder
python3 -m unittest discover -s .development/demo-recorder/tests -p 'test_*.py'
```

Expected: existing `record_demo.py` tests and new matrix tests pass.

- [ ] **Step 7: Do not run real recording yet**

Stop here unless the user confirms a privacy-safe prepared Ghostty screen. Report that the real `--id` and `--all-enabled` recording commands exist but were not run because they record the display.

---

### Task 5: Add reviewed publish-from-summary

**Files:**
- Modify: `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recorder/run_demo_matrix.py`
- Modify: `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recorder/tests/test_demo_matrix.py`

- [ ] **Step 1: Add failing publish-from-summary tests**

Append these tests inside `DemoMatrixParserTests`:

```python
    def test_publish_from_summary_copies_reviewed_gif(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            gif = tmp_path / "run" / "demo.gif"
            gif.parent.mkdir()
            gif.write_bytes(b"GIF89a")
            output = tmp_path / "assets" / "demos" / "demo.gif"
            summary = {
                "records": [
                    {
                        "id": "demo-one",
                        "status": "passed",
                        "gif": str(gif),
                        "publishGif": str(output),
                    }
                ]
            }
            summary_path = write_json(tmp_path / "summary.json", summary)
            result = run_demo_matrix.publish_from_summary(summary_path, "demo-one")
            self.assertEqual(result, output)
            self.assertEqual(output.read_bytes(), b"GIF89a")

    def test_publish_from_summary_rejects_missing_recipe(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            tmp_path = Path(temp)
            summary_path = write_json(tmp_path / "summary.json", {"records": []})
            with self.assertRaisesRegex(run_demo_matrix.MatrixError, "recipe not found"):
                run_demo_matrix.publish_from_summary(summary_path, "missing")
```

- [ ] **Step 2: Run tests and verify publish helper is missing**

Run:

```bash
cd /Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder
python3 -m unittest discover -s .development/demo-recorder/tests -p 'test_demo_matrix.py'
```

Expected: failures mention missing `publish_from_summary`.

- [ ] **Step 3: Add publish-from-summary helper**

Append this code above `build_arg_parser()` in `run_demo_matrix.py`:

```python

def publish_from_summary(summary_path: Path, recipe_id: str) -> Path:
    summary = load_json(summary_path)
    records = summary.get("records")
    if not isinstance(records, list):
        raise MatrixError("summary.records must be an array")
    for record in records:
        if not isinstance(record, dict):
            continue
        if record.get("id") != recipe_id:
            continue
        if record.get("status") != "passed":
            raise MatrixError(f"cannot publish non-passed recipe: {recipe_id}")
        gif = optional_path(record.get("gif"), "record.gif")
        output = optional_path(record.get("publishGif"), "record.publishGif")
        if gif is None or not gif.exists() or not gif.is_file():
            raise MatrixError(f"reviewed gif missing: {gif}")
        if output is None:
            raise MatrixError(f"recipe has no publishGif: {recipe_id}")
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(gif, output)
        return output
    raise MatrixError(f"recipe not found in summary: {recipe_id}")
```

- [ ] **Step 4: Wire publish-from-summary in CLI main**

In `main()` after `matrix = parse_matrix(args.matrix)`, insert:

```python
        if args.publish_from_summary:
            if not args.recipe_id:
                raise MatrixError("--publish-from-summary requires --id")
            output = publish_from_summary(args.publish_from_summary, args.recipe_id)
            print(json.dumps({"published": str(output)}, indent=2, sort_keys=True))
            return 0
```

- [ ] **Step 5: Run tests**

Run:

```bash
cd /Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder
python3 -m unittest discover -s .development/demo-recorder/tests -p 'test_demo_matrix.py'
```

Expected: all matrix tests pass.

- [ ] **Step 6: Run full local tests**

Run:

```bash
cd /Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder
python3 -m unittest discover -s .development/demo-recorder/tests -p 'test_*.py'
```

Expected: all recorder and matrix tests pass.

---

### Task 6: Update README and final verification

**Files:**
- Modify: `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recorder/README.md`
- Read: `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recorder/run_demo_matrix.py`
- Read: `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recorder/demo_matrix.json`
- Read: `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recorder/tests/test_demo_matrix.py`

- [ ] **Step 1: Append matrix runner documentation to README**

Append this content to `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recorder/README.md`:

````markdown
## Demo matrix runner

`run_demo_matrix.py` runs curated local demo recipes from `demo_matrix.json`. It is an orchestration layer around `record_demo.py`; it does not patch binaries, discover packages automatically, or publish during recording.

List recipes:

```bash
python3 .development/demo-recorder/run_demo_matrix.py --list
```

Dry-run one recipe and inspect the generated recorder config:

```bash
python3 .development/demo-recorder/run_demo_matrix.py \
  --dry-run \
  --id hidden-context-plus-hotrod-dragons-open-close
```

Run one recipe only after the selected screen is safe to record and Ghostty is prepared:

```bash
python3 .development/demo-recorder/run_demo_matrix.py \
  --id hidden-context-plus-hotrod-dragons-open-close
```

Run all enabled recipes only after preparing the desktop for a batch capture:

```bash
python3 .development/demo-recorder/run_demo_matrix.py --all-enabled
```

The runner writes batch summaries under:

```text
.development/demo-recordings/matrix/<timestamp>/
```

### Reviewed publish flow

Recording runs never copy public assets. After opening and reviewing the generated GIF and checkpoint frames, publish one recipe from a summary:

```bash
python3 .development/demo-recorder/run_demo_matrix.py \
  --publish-from-summary .development/demo-recordings/matrix/<timestamp>/summary.json \
  --id hidden-context-plus-hotrod-dragons-open-close
```

Do not publish from `--all-enabled` as a blind batch. Publish one reviewed recipe at a time.

### Adding a recipe

Add a recipe to `demo_matrix.json` only when the binary path and event sequence are known. Use `enabled: false` with `disabledReason` for placeholders. Keep display-specific values in the matrix; do not add demo fields to `packages/*/patch.json`.

### Packages intentionally skipped by default

`fable-fallback`, `reminder-suppression`, and `upstream-attachment-suppression` are not rich UI demos by default. They can get manual recipes later if a visual story is worth recording.

### Ghostty cleanup protocol

If a recording leaves Claude running, inspect the prepared Ghostty tty before killing anything:

```bash
ps -o pid=,ppid=,pgid=,tty=,stat=,command= -t ttys010
```

Kill only the Claude process group that is parented under the prepared Ghostty shell, then verify Ghostty remains alive and only login/zsh remain. Do not use global `grep claude` process matching.
````

- [ ] **Step 2: Run full test suite**

Run:

```bash
cd /Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder
python3 -m unittest discover -s .development/demo-recorder/tests -p 'test_*.py'
```

Expected: all tests pass.

- [ ] **Step 3: Run matrix list**

Run:

```bash
cd /Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder
python3 .development/demo-recorder/run_demo_matrix.py --list
```

Expected: all six recipes are listed; two are enabled; four are disabled with reasons.

- [ ] **Step 4: Run dry-run for Hotrod Dragons**

Run:

```bash
cd /Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder
python3 .development/demo-recorder/run_demo_matrix.py \
  --dry-run \
  --id hotrod-dragons-2.1.201-wrap-comparison
```

Expected: generated JSON contains:

```json
"path": "/Users/MAC/Documents/Claude-patch/.development/claude-monkey-builds/hotrod-dragons-2.1.201-wrap-comparison/claude"
```

and `publish.enabled` is `false`.

- [ ] **Step 5: Run dry-run for combined open/close demo**

Run:

```bash
cd /Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder
python3 .development/demo-recorder/run_demo_matrix.py \
  --dry-run \
  --id hidden-context-plus-hotrod-dragons-open-close
```

Expected: generated JSON contains:

```json
{"type": "key", "key": "down"}
{"type": "key", "key": "down"}
{"type": "key", "key": "x"}
{"type": "key", "key": "ctrl-c"}
```

and `publish.enabled` is `false`.

- [ ] **Step 6: Run publish-from-summary helper unit path only**

Do not publish any real GIF unless the user has reviewed it. The unit tests already cover copying from a synthetic summary. Report that real publish-from-summary was not run.

- [ ] **Step 7: Check worktree status**

Run:

```bash
cd /Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder
git status --short --untracked-files=all
```

Expected: no `packages/**`, `src/**`, build artifacts, or main-checkout files are modified. New/modified files are limited to:

```text
docs/superpowers/specs/2026-07-04-demo-matrix-runner-design.md
docs/superpowers/plans/2026-07-04-demo-matrix-runner.md
.development/demo-recorder/run_demo_matrix.py
.development/demo-recorder/demo_matrix.json
.development/demo-recorder/tests/test_demo_matrix.py
.development/demo-recorder/README.md
```

Some `.development/**` files may not appear in `git status` if ignored.

- [ ] **Step 8: Final report**

Report:

```text
Implemented demo matrix runner in the demo-recorder worktree.
Verified:
- tests: <exact unittest result>
- list: <brief output summary>
- dry-run hotrod: <pass/fail>
- dry-run combined open/close: <pass/fail>
Not run:
- real recording, unless user confirmed safe screen
- real publish-from-summary, unless user reviewed a GIF and requested publish
Residual risk:
- visual correctness remains human-reviewed
- Ghostty screen/zoom restoration remains desktop-state dependent
```
