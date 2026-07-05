# Demo Recorder Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Ghostty + AppleScript/System Events + ffmpeg demo recorder that can run a patched Claude binary, record a selected screen, drive timed keystrokes, and produce a reviewed GIF artifact.

**Architecture:** A self-contained Python driver under `.development/demo-recorder/` reads JSON demo configs, validates tools/screens/crops/command paths, launches and focuses Ghostty, sends structured key events through AppleScript, records the selected AVFoundation screen with ffmpeg, converts to GIF with palette generation, and keeps all raw output under `.development/demo-recordings/`. Public `assets/demos/` output is gated behind explicit `publish.enabled` or `--publish`.

**Tech Stack:** Python 3 standard library, macOS `osascript`/System Events, Ghostty (`com.mitchellh.ghostty`), `ffmpeg`/`ffprobe`, JSON configs, local ignored `.development/` artifacts.

---

## File structure

**Create:**
- `/Users/MAC/Documents/Claude-patch/.development/demo-recorder/record_demo.py` — main Python driver and CLI.
- `/Users/MAC/Documents/Claude-patch/.development/demo-recorder/configs/hotrod-dragons-2.1.201-wrap-comparison.json` — initial demo config for the requested binary.
- `/Users/MAC/Documents/Claude-patch/.development/demo-recorder/tests/test_record_demo.py` — local unit tests for config parsing, shell quoting, crop validation, ffmpeg filter construction, and event parsing.
- `/Users/MAC/Documents/Claude-patch/.development/demo-recorder/README.md` — short local usage guide and permission notes.

**Modify:**
- None in tracked package/build code.

**Do not modify:**
- `/Users/MAC/Documents/Claude-patch/packages/**`
- `/Users/MAC/Documents/Claude-patch/src/**`
- existing build artifacts except by running the new recorder into `.development/demo-recordings/`

---

### Task 1: Scaffold recorder files and sample config

**Files:**
- Create: `/Users/MAC/Documents/Claude-patch/.development/demo-recorder/record_demo.py`
- Create: `/Users/MAC/Documents/Claude-patch/.development/demo-recorder/configs/hotrod-dragons-2.1.201-wrap-comparison.json`
- Create: `/Users/MAC/Documents/Claude-patch/.development/demo-recorder/README.md`

- [ ] **Step 1: Create directories**

Run:

```bash
cd /Users/MAC/Documents/Claude-patch
mkdir -p .development/demo-recorder/configs .development/demo-recorder/tests .development/demo-recordings
```

Expected: directories exist and remain ignored by git.

- [ ] **Step 2: Write initial `record_demo.py` CLI skeleton**

Create `/Users/MAC/Documents/Claude-patch/.development/demo-recorder/record_demo.py` with this exact initial content:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path("/Users/MAC/Documents/Claude-patch")
DEFAULT_RECORDINGS_DIR = ROOT / ".development" / "demo-recordings"
GHOSTTY_BUNDLE_ID = "com.mitchellh.ghostty"


class RecorderError(RuntimeError):
    pass


@dataclass(frozen=True)
class AppConfig:
    name: str
    bundle_id: str
    leave_open_at_end: bool


@dataclass(frozen=True)
class ScreenConfig:
    avfoundation_device: str
    label: str
    crop: str | None
    fps: int
    scale_width: int


@dataclass(frozen=True)
class CommandConfig:
    cwd: Path
    path: Path
    args: tuple[str, ...]


@dataclass(frozen=True)
class RecordingConfig:
    start: str
    post_launch_wait_seconds: float
    record_seconds: float


@dataclass(frozen=True)
class PublishConfig:
    enabled: bool
    output_gif: Path | None


@dataclass(frozen=True)
class DemoConfig:
    demo_name: str
    app: AppConfig
    screen: ScreenConfig
    command: CommandConfig
    recording: RecordingConfig
    events: tuple[dict[str, Any], ...]
    publish: PublishConfig


def load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise RecorderError(f"config not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise RecorderError(f"invalid JSON in {path}: {exc}") from exc


def require_string(obj: dict[str, Any], key: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value:
        raise RecorderError(f"missing or invalid string field: {key}")
    return value


def require_number(obj: dict[str, Any], key: str) -> float:
    value = obj.get(key)
    if not isinstance(value, (int, float)):
        raise RecorderError(f"missing or invalid numeric field: {key}")
    return float(value)


def parse_config(path: Path) -> DemoConfig:
    raw = load_json(path)
    app_raw = raw.get("app")
    screen_raw = raw.get("screen")
    command_raw = raw.get("command")
    recording_raw = raw.get("recording")
    publish_raw = raw.get("publish", {})
    events_raw = raw.get("events", [])
    if not isinstance(app_raw, dict):
        raise RecorderError("missing app object")
    if not isinstance(screen_raw, dict):
        raise RecorderError("missing screen object")
    if not isinstance(command_raw, dict):
        raise RecorderError("missing command object")
    if not isinstance(recording_raw, dict):
        raise RecorderError("missing recording object")
    if not isinstance(publish_raw, dict):
        raise RecorderError("publish must be an object")
    if not isinstance(events_raw, list):
        raise RecorderError("events must be an array")

    crop = screen_raw.get("crop")
    if crop is not None and not isinstance(crop, str):
        raise RecorderError("screen.crop must be null or a crop string")

    args = command_raw.get("args", [])
    if not isinstance(args, list) or not all(isinstance(arg, str) for arg in args):
        raise RecorderError("command.args must be an array of strings")

    output_gif_raw = publish_raw.get("outputGif")
    output_gif = Path(output_gif_raw).expanduser() if isinstance(output_gif_raw, str) and output_gif_raw else None

    return DemoConfig(
        demo_name=require_string(raw, "demoName"),
        app=AppConfig(
            name=require_string(app_raw, "name"),
            bundle_id=require_string(app_raw, "bundleId"),
            leave_open_at_end=bool(app_raw.get("leaveOpenAtEnd", True)),
        ),
        screen=ScreenConfig(
            avfoundation_device=require_string(screen_raw, "avfoundationDevice"),
            label=require_string(screen_raw, "label"),
            crop=crop,
            fps=int(require_number(screen_raw, "fps")),
            scale_width=int(require_number(screen_raw, "scaleWidth")),
        ),
        command=CommandConfig(
            cwd=Path(require_string(command_raw, "cwd")).expanduser(),
            path=Path(require_string(command_raw, "path")).expanduser(),
            args=tuple(args),
        ),
        recording=RecordingConfig(
            start=require_string(recording_raw, "start"),
            post_launch_wait_seconds=require_number(recording_raw, "postLaunchWaitSeconds"),
            record_seconds=require_number(recording_raw, "recordSeconds"),
        ),
        events=tuple(events_raw),
        publish=PublishConfig(
            enabled=bool(publish_raw.get("enabled", False)),
            output_gif=output_gif,
        ),
    )


def shell_command(command: CommandConfig) -> str:
    parts = [shlex.quote(str(command.path)), *[shlex.quote(arg) for arg in command.args]]
    return f"cd {shlex.quote(str(command.cwd))} && " + " ".join(parts)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Record a Ghostty-hosted ClaudeMonkey demo")
    parser.add_argument("--config", required=True, type=Path, help="Path to demo JSON config")
    parser.add_argument("--dry-run", action="store_true", help="Validate config and print derived command without launching")
    parser.add_argument("--calibrate", action="store_true", help="Run a short screen capture calibration")
    parser.add_argument("--publish", action="store_true", help="Allow copying reviewed GIF to publish.outputGif")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)
    try:
        config = parse_config(args.config)
        resolved = shell_command(config.command)
        print(json.dumps({"demoName": config.demo_name, "resolvedCommand": resolved}, indent=2))
        if args.dry_run:
            return 0
        raise RecorderError("implementation continues in later tasks; use --dry-run for this scaffold")
    except RecorderError as exc:
        print(f"record-demo: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Make the script executable**

Run:

```bash
chmod +x /Users/MAC/Documents/Claude-patch/.development/demo-recorder/record_demo.py
```

Expected: command exits 0.

- [ ] **Step 4: Create the sample hotrod config**

Create `/Users/MAC/Documents/Claude-patch/.development/demo-recorder/configs/hotrod-dragons-2.1.201-wrap-comparison.json` with:

```json
{
  "demoName": "hotrod-dragons-2.1.201-wrap-comparison",
  "app": {
    "name": "Ghostty",
    "bundleId": "com.mitchellh.ghostty",
    "leaveOpenAtEnd": true
  },
  "screen": {
    "avfoundationDevice": "2",
    "label": "screen-0-dell",
    "crop": null,
    "fps": 12,
    "scaleWidth": 960
  },
  "command": {
    "cwd": "/Users/MAC/Documents/Claude-patch",
    "path": "/Users/MAC/Documents/Claude-patch/.development/claude-monkey-builds/hotrod-dragons-2.1.201-wrap-comparison/claude",
    "args": ["--dangerously-skip-permissions"]
  },
  "recording": {
    "start": "afterLaunchSettle",
    "postLaunchWaitSeconds": 5,
    "recordSeconds": 14
  },
  "events": [
    {"type": "wait", "seconds": 10},
    {"type": "key", "key": "ctrl-c"}
  ],
  "publish": {
    "enabled": false,
    "outputGif": "/Users/MAC/Documents/Claude-patch/assets/demos/hotrod-dragons.gif"
  }
}
```

- [ ] **Step 5: Create README**

Create `/Users/MAC/Documents/Claude-patch/.development/demo-recorder/README.md` with:

```markdown
# Demo Recorder

Local-only demo recorder for ClaudeMonkey GIFs. It launches Ghostty, runs a configured patched Claude binary, records a selected macOS screen with ffmpeg, sends timed keystrokes through AppleScript/System Events, and creates a GIF for human review.

## Safety

Raw screen recordings can contain private UI. The recorder writes raw artifacts under `.development/demo-recordings/`. Public copies to `assets/demos/` require explicit publish opt-in.

## First dry run

```bash
cd /Users/MAC/Documents/Claude-patch
python3 .development/demo-recorder/record_demo.py \
  --config .development/demo-recorder/configs/hotrod-dragons-2.1.201-wrap-comparison.json \
  --dry-run
```

## Permissions

macOS may require Screen Recording permission for the terminal process running `ffmpeg` and Accessibility permission for the process running `osascript`/System Events.
```

- [ ] **Step 6: Run dry-run scaffold**

Run:

```bash
cd /Users/MAC/Documents/Claude-patch
python3 .development/demo-recorder/record_demo.py \
  --config .development/demo-recorder/configs/hotrod-dragons-2.1.201-wrap-comparison.json \
  --dry-run
```

Expected: JSON prints `demoName` and a `resolvedCommand` containing the quoted target binary and `--dangerously-skip-permissions`. Exit code 0.

---

### Task 2: Add validation tests and config validation

**Files:**
- Modify: `/Users/MAC/Documents/Claude-patch/.development/demo-recorder/record_demo.py`
- Create: `/Users/MAC/Documents/Claude-patch/.development/demo-recorder/tests/test_record_demo.py`

- [ ] **Step 1: Write local unit tests**

Create `/Users/MAC/Documents/Claude-patch/.development/demo-recorder/tests/test_record_demo.py` with:

```python
from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "record_demo.py"
spec = importlib.util.spec_from_file_location("record_demo", MODULE_PATH)
record_demo = importlib.util.module_from_spec(spec)
assert spec and spec.loader
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
    import json
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_parse_config_and_shell_command_quote_spaces(tmp_path: Path) -> None:
    cfg = record_demo.parse_config(write_config(tmp_path, base_config(tmp_path)))
    command = record_demo.shell_command(cfg.command)
    assert "cd " in command
    assert "'value with spaces'" in command
    assert "'claude fake'" in command


def test_validate_config_rejects_missing_target(tmp_path: Path) -> None:
    data = base_config(tmp_path)
    data["command"]["path"] = str(tmp_path / "missing")
    cfg = record_demo.parse_config(write_config(tmp_path, data))
    try:
        record_demo.validate_config(cfg)
    except record_demo.RecorderError as exc:
        assert "command.path does not exist" in str(exc)
    else:
        raise AssertionError("expected RecorderError")


def test_validate_crop_accepts_bounds() -> None:
    assert record_demo.validate_crop("crop=100:80:10:20", width=200, height=160) == (100, 80, 10, 20)


def test_validate_crop_rejects_out_of_bounds() -> None:
    try:
        record_demo.validate_crop("crop=100:80:150:20", width=200, height=160)
    except record_demo.RecorderError as exc:
        assert "crop exceeds frame bounds" in str(exc)
    else:
        raise AssertionError("expected RecorderError")


def test_ffmpeg_filters_without_crop() -> None:
    vf, lavfi = record_demo.build_gif_filters(crop=None, fps=12, scale_width=960)
    assert vf == "fps=12,scale=960:-1:flags=lanczos,palettegen=stats_mode=diff"
    assert lavfi == "fps=12,scale=960:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle"


def test_ffmpeg_filters_with_crop() -> None:
    vf, lavfi = record_demo.build_gif_filters(crop="crop=100:80:10:20", fps=8, scale_width=640)
    assert vf.startswith("crop=100:80:10:20,fps=8")
    assert lavfi.startswith("crop=100:80:10:20,fps=8")


def test_validate_events_rejects_escape() -> None:
    try:
        record_demo.validate_events([{"type": "key", "key": "escape"}])
    except record_demo.RecorderError as exc:
        assert "escape is intentionally unsupported" in str(exc)
    else:
        raise AssertionError("expected RecorderError")
```

- [ ] **Step 2: Run tests and confirm missing functions fail**

Run:

```bash
cd /Users/MAC/Documents/Claude-patch
python3 -m unittest discover -s .development/demo-recorder/tests -p 'test_*.py'
```

Expected: failures mention missing `validate_config`, `validate_crop`, `build_gif_filters`, or `validate_events`.

- [ ] **Step 3: Add validation helpers to `record_demo.py`**

Append these functions after `shell_command` in `/Users/MAC/Documents/Claude-patch/.development/demo-recorder/record_demo.py`:

```python
def validate_config(config: DemoConfig) -> None:
    if not config.command.cwd.exists() or not config.command.cwd.is_dir():
        raise RecorderError(f"command.cwd does not exist or is not a directory: {config.command.cwd}")
    if not config.command.path.exists() or not config.command.path.is_file():
        raise RecorderError(f"command.path does not exist or is not a file: {config.command.path}")
    if config.recording.start != "afterLaunchSettle":
        raise RecorderError("v1 supports recording.start=afterLaunchSettle only")
    if config.recording.record_seconds <= 0:
        raise RecorderError("recording.recordSeconds must be positive")
    if config.recording.post_launch_wait_seconds < 0:
        raise RecorderError("recording.postLaunchWaitSeconds must be non-negative")
    if config.screen.fps <= 0:
        raise RecorderError("screen.fps must be positive")
    if config.screen.scale_width <= 0:
        raise RecorderError("screen.scaleWidth must be positive")
    validate_events(config.events)


def validate_events(events: tuple[dict[str, Any], ...] | list[dict[str, Any]]) -> None:
    allowed_keys = {"down", "up", "left", "right", "return", "ctrl-c"}
    for index, event in enumerate(events):
        if not isinstance(event, dict):
            raise RecorderError(f"event {index} must be an object")
        event_type = event.get("type")
        if event_type == "wait":
            seconds = event.get("seconds")
            if not isinstance(seconds, (int, float)) or seconds < 0:
                raise RecorderError(f"event {index} wait.seconds must be a non-negative number")
        elif event_type == "key":
            key = event.get("key")
            if key == "escape":
                raise RecorderError("escape is intentionally unsupported for recorder key events")
            if key not in allowed_keys:
                raise RecorderError(f"event {index} has unsupported key: {key!r}")
        elif event_type in {"text", "paste"}:
            text = event.get("text")
            if not isinstance(text, str):
                raise RecorderError(f"event {index} {event_type}.text must be a string")
        else:
            raise RecorderError(f"event {index} has unsupported type: {event_type!r}")


def validate_crop(crop: str, *, width: int, height: int) -> tuple[int, int, int, int]:
    prefix = "crop="
    if not crop.startswith(prefix):
        raise RecorderError("crop must use format crop=w:h:x:y")
    pieces = crop[len(prefix):].split(":")
    if len(pieces) != 4:
        raise RecorderError("crop must use format crop=w:h:x:y")
    try:
        w, h, x, y = [int(piece) for piece in pieces]
    except ValueError as exc:
        raise RecorderError("crop values must be integers") from exc
    if w <= 0 or h <= 0 or x < 0 or y < 0:
        raise RecorderError("crop width/height must be positive and x/y non-negative")
    if x + w > width or y + h > height:
        raise RecorderError(f"crop exceeds frame bounds: crop={w}x{h}+{x}+{y}, frame={width}x{height}")
    return w, h, x, y


def build_gif_filters(*, crop: str | None, fps: int, scale_width: int) -> tuple[str, str]:
    base = f"fps={fps},scale={scale_width}:-1:flags=lanczos"
    if crop:
        base = f"{crop},{base}"
    palette_filter = f"{base},palettegen=stats_mode=diff"
    gif_filter = f"{base}[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle"
    return palette_filter, gif_filter
```

- [ ] **Step 4: Call `validate_config` in `main`**

In `/Users/MAC/Documents/Claude-patch/.development/demo-recorder/record_demo.py`, change:

```python
        config = parse_config(args.config)
        resolved = shell_command(config.command)
```

to:

```python
        config = parse_config(args.config)
        validate_config(config)
        resolved = shell_command(config.command)
```

- [ ] **Step 5: Run unit tests**

Run:

```bash
cd /Users/MAC/Documents/Claude-patch
python3 -m unittest discover -s .development/demo-recorder/tests -p 'test_*.py'
```

Expected: all tests pass.

- [ ] **Step 6: Run config dry-run**

Run:

```bash
cd /Users/MAC/Documents/Claude-patch
python3 .development/demo-recorder/record_demo.py \
  --config .development/demo-recorder/configs/hotrod-dragons-2.1.201-wrap-comparison.json \
  --dry-run
```

Expected: exit 0 and JSON output. If the target binary is missing, stop and report the exact missing path rather than changing the plan.

---

### Task 3: Add AppleScript focus and event driver

**Files:**
- Modify: `/Users/MAC/Documents/Claude-patch/.development/demo-recorder/record_demo.py`
- Modify: `/Users/MAC/Documents/Claude-patch/.development/demo-recorder/tests/test_record_demo.py`

- [ ] **Step 1: Add tests for AppleScript snippets**

Append to `/Users/MAC/Documents/Claude-patch/.development/demo-recorder/tests/test_record_demo.py`:

```python
def test_key_action_script_contains_expected_key_code() -> None:
    script = record_demo.applescript_for_key("down")
    assert "key code 125" in script


def test_key_action_script_rejects_escape() -> None:
    try:
        record_demo.applescript_for_key("escape")
    except record_demo.RecorderError as exc:
        assert "unsupported key" in str(exc)
    else:
        raise AssertionError("expected RecorderError")


def test_frontmost_assertion_mentions_bundle() -> None:
    script = record_demo.applescript_frontmost_bundle()
    assert "frontmost is true" in script
    assert "bundle identifier" in script
```

- [ ] **Step 2: Run tests and confirm they fail**

Run:

```bash
cd /Users/MAC/Documents/Claude-patch
python3 -m unittest discover -s .development/demo-recorder/tests -p 'test_*.py'
```

Expected: failures mention missing `applescript_for_key` and `applescript_frontmost_bundle`.

- [ ] **Step 3: Add AppleScript helpers**

Append after `build_gif_filters` in `record_demo.py`:

```python
def run_command(argv: list[str], *, check: bool = True, capture: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        check=check,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
    )


def run_osascript(script: str) -> str:
    try:
        result = run_command(["osascript", "-e", script], check=True, capture=True)
    except subprocess.CalledProcessError as exc:
        stderr = exc.stderr.strip() if exc.stderr else str(exc)
        raise RecorderError(f"osascript failed: {stderr}") from exc
    return result.stdout.strip()


def applescript_frontmost_bundle() -> str:
    return 'tell application "System Events" to get bundle identifier of first application process whose frontmost is true'


def frontmost_bundle() -> str:
    return run_osascript(applescript_frontmost_bundle())


def assert_frontmost_bundle(expected_bundle_id: str) -> None:
    actual = frontmost_bundle()
    if actual != expected_bundle_id:
        raise RecorderError(f"frontmost app is {actual!r}, expected {expected_bundle_id!r}; refusing to send keys")


def applescript_for_key(key: str) -> str:
    mapping = {
        "down": "key code 125",
        "up": "key code 126",
        "left": "key code 123",
        "right": "key code 124",
        "return": "key code 36",
        "ctrl-c": 'keystroke "c" using control down',
    }
    if key not in mapping:
        raise RecorderError(f"unsupported key for AppleScript event: {key!r}")
    return f'tell application "System Events" to {mapping[key]}'


def send_key(config: DemoConfig, key: str) -> None:
    assert_frontmost_bundle(config.app.bundle_id)
    run_osascript(applescript_for_key(key))


def send_text(config: DemoConfig, text: str) -> None:
    assert_frontmost_bundle(config.app.bundle_id)
    escaped = text.replace('\\', '\\\\').replace('"', '\\"')
    run_osascript(f'tell application "System Events" to keystroke "{escaped}"')
```

- [ ] **Step 4: Add event runner**

Append after `send_text`:

```python
def run_events(config: DemoConfig) -> None:
    for event in config.events:
        event_type = event["type"]
        if event_type == "wait":
            time.sleep(float(event["seconds"]))
        elif event_type == "key":
            send_key(config, str(event["key"]))
        elif event_type == "text":
            send_text(config, str(event["text"]))
        elif event_type == "paste":
            paste_text(config, str(event["text"]))
        else:
            raise RecorderError(f"unsupported event during run: {event_type!r}")
```

This references `paste_text`, which is implemented in Task 4 before live event execution. Do not call `run_events` from `main` until Task 4 is complete.

- [ ] **Step 5: Run unit tests**

Run:

```bash
cd /Users/MAC/Documents/Claude-patch
python3 -m unittest discover -s .development/demo-recorder/tests -p 'test_*.py'
```

Expected: all tests pass because `run_events` is not executed by tests.

- [ ] **Step 6: Manual focus probe without sending keys**

Run:

```bash
osascript -e 'tell application "System Events" to get bundle identifier of first application process whose frontmost is true'
```

Expected: prints a bundle identifier. If macOS prompts for Accessibility permission, grant it to the terminal/Codex host you are using, then rerun.

---

### Task 4: Add Ghostty launch/focus and safe paste/run command

**Files:**
- Modify: `/Users/MAC/Documents/Claude-patch/.development/demo-recorder/record_demo.py`
- Modify: `/Users/MAC/Documents/Claude-patch/.development/demo-recorder/tests/test_record_demo.py`

- [ ] **Step 1: Add tests for launch command construction**

Append to `test_record_demo.py`:

```python
def test_build_launch_command_uses_cd_and_exec_path(tmp_path: Path) -> None:
    cfg = record_demo.parse_config(write_config(tmp_path, base_config(tmp_path)))
    command = record_demo.shell_command(cfg.command)
    assert command.startswith("cd ")
    assert "&&" in command
    assert "--flag" in command
```

- [ ] **Step 2: Add Ghostty and clipboard helpers**

Append after `run_events` in `record_demo.py`:

```python
def open_and_focus_app(config: DemoConfig, *, timeout_seconds: float = 10.0) -> None:
    subprocess.run(["open", "-b", config.app.bundle_id], check=False)
    deadline = time.time() + timeout_seconds
    last = ""
    while time.time() < deadline:
        subprocess.run(["osascript", "-e", f'tell application id "{config.app.bundle_id}" to activate'], check=False)
        try:
            last = frontmost_bundle()
        except RecorderError:
            last = ""
        if last == config.app.bundle_id:
            return
        time.sleep(0.25)
    raise RecorderError(f"failed to focus {config.app.bundle_id}; last frontmost bundle={last!r}")


def get_clipboard() -> str:
    result = subprocess.run(["pbpaste"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return result.stdout if result.returncode == 0 else ""


def set_clipboard(text: str) -> None:
    subprocess.run(["pbcopy"], input=text, text=True, check=True)


def paste_text(config: DemoConfig, text: str) -> None:
    assert_frontmost_bundle(config.app.bundle_id)
    old_clipboard = get_clipboard()
    try:
        set_clipboard(text)
        run_osascript('tell application "System Events" to keystroke "v" using command down')
    finally:
        set_clipboard(old_clipboard)


def paste_and_return(config: DemoConfig, text: str) -> None:
    paste_text(config, text)
    send_key(config, "return")


def launch_demo_command(config: DemoConfig) -> str:
    resolved = shell_command(config.command)
    open_and_focus_app(config)
    paste_and_return(config, resolved)
    return resolved
```

- [ ] **Step 3: Run unit tests**

Run:

```bash
cd /Users/MAC/Documents/Claude-patch
python3 -m unittest discover -s .development/demo-recorder/tests -p 'test_*.py'
```

Expected: all tests pass.

- [ ] **Step 4: Manual dry-run focus check**

With Ghostty closed or open, run:

```bash
open -b com.mitchellh.ghostty
sleep 2
osascript -e 'tell application id "com.mitchellh.ghostty" to activate'
osascript -e 'tell application "System Events" to get bundle identifier of first application process whose frontmost is true'
```

Expected: final line is `com.mitchellh.ghostty`. If not, stop and report focus behavior before continuing.

---

### Task 5: Add screen enumeration, calibration, and crop validation

**Files:**
- Modify: `/Users/MAC/Documents/Claude-patch/.development/demo-recorder/record_demo.py`
- Modify: `/Users/MAC/Documents/Claude-patch/.development/demo-recorder/README.md`

- [ ] **Step 1: Add run directory and metadata helpers**

Append to `record_demo.py` after `launch_demo_command`:

```python
def timestamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def make_run_dir(config: DemoConfig) -> Path:
    run_dir = DEFAULT_RECORDINGS_DIR / config.demo_name / timestamp()
    run_dir.mkdir(parents=True, exist_ok=False)
    return run_dir


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def tool_path(name: str) -> str:
    found = shutil.which(name)
    if not found:
        raise RecorderError(f"required tool not found on PATH: {name}")
    return found


def preflight_tools() -> dict[str, str]:
    return {name: tool_path(name) for name in ["ffmpeg", "ffprobe", "osascript", "open", "pbcopy", "pbpaste"]}
```

- [ ] **Step 2: Add screen enumeration helpers**

Append to `record_demo.py`:

```python
def list_avfoundation_devices() -> str:
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-f", "avfoundation", "-list_devices", "true", "-i", ""],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return result.stderr


def list_nsscreens() -> str:
    swift = (
        'import AppKit; '
        'for (i,s) in NSScreen.screens.enumerated(){ '
        'let f=s.frame; let v=s.visibleFrame; '
        'print("screen \\(i): frame=\\(Int(f.origin.x)),\\(Int(f.origin.y)) \\(Int(f.width))x\\(Int(f.height)) visible=\\(Int(v.origin.x)),\\(Int(v.origin.y)) \\(Int(v.width))x\\(Int(v.height)) scale=\\(s.backingScaleFactor)") '
        '}'
    )
    result = subprocess.run(["swift", "-e", swift], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return result.stdout if result.returncode == 0 else result.stderr
```

- [ ] **Step 3: Add ffprobe dimensions and calibration capture**

Append to `record_demo.py`:

```python
def ffprobe_dimensions(video: Path) -> tuple[int, int]:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height", "-of", "json", str(video)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=True,
    )
    data = json.loads(result.stdout)
    streams = data.get("streams", [])
    if not streams:
        raise RecorderError(f"ffprobe found no video stream in {video}")
    width = int(streams[0]["width"])
    height = int(streams[0]["height"])
    return width, height


def run_calibration(config: DemoConfig, run_dir: Path) -> dict[str, Any]:
    sample = run_dir / "calibration.mov"
    frame = run_dir / "calibration.png"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "avfoundation",
            "-framerate", "10",
            "-i", f"{config.screen.avfoundation_device}:none",
            "-t", "1",
            str(sample),
        ],
        check=True,
    )
    if not sample.exists() or sample.stat().st_size == 0:
        raise RecorderError("calibration movie was not created or is empty")
    width, height = ffprobe_dimensions(sample)
    subprocess.run(["ffmpeg", "-y", "-i", str(sample), "-frames:v", "1", str(frame)], check=True)
    if config.screen.crop:
        validate_crop(config.screen.crop, width=width, height=height)
    data = {"sample": str(sample), "frame": str(frame), "width": width, "height": height, "crop": config.screen.crop}
    write_json(run_dir / "calibration.json", data)
    return data
```

- [ ] **Step 4: Wire `--calibrate` in `main`**

In `main`, after printing dry-run JSON and before the scaffold error, replace:

```python
        if args.dry_run:
            return 0
        raise RecorderError("implementation continues in later tasks; use --dry-run for this scaffold")
```

with:

```python
        if args.dry_run:
            return 0
        preflight_tools()
        run_dir = make_run_dir(config)
        write_json(run_dir / "config.snapshot.json", {"configPath": str(args.config), "resolvedCommand": resolved})
        (run_dir / "avfoundation-devices.txt").write_text(list_avfoundation_devices(), encoding="utf-8")
        (run_dir / "nsscreens.txt").write_text(list_nsscreens(), encoding="utf-8")
        if args.calibrate:
            data = run_calibration(config, run_dir)
            print(json.dumps({"runDir": str(run_dir), "calibration": data}, indent=2))
            return 0
        raise RecorderError("recording run is implemented in the next task; use --calibrate or --dry-run now")
```

- [ ] **Step 5: Run unit tests**

Run:

```bash
cd /Users/MAC/Documents/Claude-patch
python3 -m unittest discover -s .development/demo-recorder/tests -p 'test_*.py'
```

Expected: all tests pass.

- [ ] **Step 6: Run calibration**

Run only after ensuring the selected screen contains no private content you do not want recorded:

```bash
cd /Users/MAC/Documents/Claude-patch
python3 .development/demo-recorder/record_demo.py \
  --config .development/demo-recorder/configs/hotrod-dragons-2.1.201-wrap-comparison.json \
  --calibrate
```

Expected: prints a run directory and calibration dimensions. The run directory contains `calibration.mov`, `calibration.png`, `calibration.json`, `avfoundation-devices.txt`, and `nsscreens.txt`. If macOS asks for Screen Recording permission, grant it and rerun.

- [ ] **Step 7: Update README with calibration command**

Append to `/Users/MAC/Documents/Claude-patch/.development/demo-recorder/README.md`:

```markdown
## Calibration

Before publishing a GIF, run calibration:

```bash
python3 .development/demo-recorder/record_demo.py \
  --config .development/demo-recorder/configs/hotrod-dragons-2.1.201-wrap-comparison.json \
  --calibrate
```

Open the generated `calibration.png` in the run directory. If the image shows the wrong display or private UI, fix the screen/Ghostty setup before recording.
```

---

### Task 6: Add bounded recording, event execution, GIF conversion, and publish gate

**Files:**
- Modify: `/Users/MAC/Documents/Claude-patch/.development/demo-recorder/record_demo.py`
- Modify: `/Users/MAC/Documents/Claude-patch/.development/demo-recorder/README.md`

- [ ] **Step 1: Add recording and conversion helpers**

Append to `record_demo.py`:

```python
def record_screen(config: DemoConfig, run_dir: Path) -> Path:
    raw = run_dir / "raw.mov"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "avfoundation",
            "-framerate", "30",
            "-i", f"{config.screen.avfoundation_device}:none",
            "-t", str(config.recording.record_seconds),
            str(raw),
        ],
        check=True,
    )
    if not raw.exists() or raw.stat().st_size == 0:
        raise RecorderError("raw recording was not created or is empty")
    return raw


def convert_to_gif(config: DemoConfig, raw: Path, run_dir: Path) -> Path:
    width, height = ffprobe_dimensions(raw)
    if config.screen.crop:
        validate_crop(config.screen.crop, width=width, height=height)
    palette_filter, gif_filter = build_gif_filters(crop=config.screen.crop, fps=config.screen.fps, scale_width=config.screen.scale_width)
    palette = run_dir / "palette.png"
    gif = run_dir / "demo.gif"
    subprocess.run(["ffmpeg", "-y", "-i", str(raw), "-vf", palette_filter, str(palette)], check=True)
    subprocess.run(["ffmpeg", "-y", "-i", str(raw), "-i", str(palette), "-lavfi", gif_filter, str(gif)], check=True)
    if not gif.exists() or gif.stat().st_size == 0:
        raise RecorderError("GIF was not created or is empty")
    return gif
```

- [ ] **Step 2: Add concurrent event execution during recording**

Add import near the top of `record_demo.py`:

```python
import threading
```

Append to `record_demo.py`:

```python
def record_screen_while_events(config: DemoConfig, run_dir: Path) -> Path:
    raw = run_dir / "raw.mov"
    event_error: list[BaseException] = []

    def event_worker() -> None:
        try:
            run_events(config)
        except BaseException as exc:
            event_error.append(exc)

    process = subprocess.Popen(
        [
            "ffmpeg", "-y",
            "-f", "avfoundation",
            "-framerate", "30",
            "-i", f"{config.screen.avfoundation_device}:none",
            "-t", str(config.recording.record_seconds),
            str(raw),
        ]
    )
    worker = threading.Thread(target=event_worker, daemon=True)
    worker.start()
    try:
        returncode = process.wait(timeout=config.recording.record_seconds + 20)
    except BaseException:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        raise
    worker.join(timeout=5)
    if event_error:
        raise RecorderError(f"event script failed: {event_error[0]}")
    if returncode != 0:
        raise RecorderError(f"ffmpeg recording failed with exit code {returncode}")
    if not raw.exists() or raw.stat().st_size == 0:
        raise RecorderError("raw recording was not created or is empty")
    return raw
```

- [ ] **Step 3: Add publish helper**

Append to `record_demo.py`:

```python
def publish_gif(config: DemoConfig, gif: Path, *, cli_publish: bool) -> Path | None:
    if not (config.publish.enabled or cli_publish):
        return None
    if config.publish.output_gif is None:
        raise RecorderError("publish requested but publish.outputGif is missing")
    output = config.publish.output_gif
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(gif, output)
    return output
```

- [ ] **Step 4: Add full `run_recording` helper**

Append to `record_demo.py`:

```python
def run_recording(config: DemoConfig, config_path: Path, *, cli_publish: bool) -> dict[str, Any]:
    preflight_tools()
    run_dir = make_run_dir(config)
    resolved = shell_command(config.command)
    write_json(run_dir / "config.snapshot.json", {"configPath": str(config_path), "resolvedCommand": resolved})
    (run_dir / "avfoundation-devices.txt").write_text(list_avfoundation_devices(), encoding="utf-8")
    (run_dir / "nsscreens.txt").write_text(list_nsscreens(), encoding="utf-8")
    calibration = run_calibration(config, run_dir)
    launch_demo_command(config)
    time.sleep(config.recording.post_launch_wait_seconds)
    raw = record_screen_while_events(config, run_dir)
    gif = convert_to_gif(config, raw, run_dir)
    published = publish_gif(config, gif, cli_publish=cli_publish)
    metadata = {
        "runDir": str(run_dir),
        "raw": str(raw),
        "gif": str(gif),
        "published": str(published) if published else None,
        "calibration": calibration,
    }
    write_json(run_dir / "metadata.json", metadata)
    return metadata
```

- [ ] **Step 5: Wire recording mode in `main`**

In `main`, replace:

```python
        preflight_tools()
        run_dir = make_run_dir(config)
        write_json(run_dir / "config.snapshot.json", {"configPath": str(args.config), "resolvedCommand": resolved})
        (run_dir / "avfoundation-devices.txt").write_text(list_avfoundation_devices(), encoding="utf-8")
        (run_dir / "nsscreens.txt").write_text(list_nsscreens(), encoding="utf-8")
        if args.calibrate:
            data = run_calibration(config, run_dir)
            print(json.dumps({"runDir": str(run_dir), "calibration": data}, indent=2))
            return 0
        raise RecorderError("recording run is implemented in the next task; use --calibrate or --dry-run now")
```

with:

```python
        preflight_tools()
        if args.calibrate:
            run_dir = make_run_dir(config)
            write_json(run_dir / "config.snapshot.json", {"configPath": str(args.config), "resolvedCommand": resolved})
            (run_dir / "avfoundation-devices.txt").write_text(list_avfoundation_devices(), encoding="utf-8")
            (run_dir / "nsscreens.txt").write_text(list_nsscreens(), encoding="utf-8")
            data = run_calibration(config, run_dir)
            print(json.dumps({"runDir": str(run_dir), "calibration": data}, indent=2))
            return 0
        metadata = run_recording(config, args.config, cli_publish=args.publish)
        print(json.dumps(metadata, indent=2))
        return 0
```

- [ ] **Step 6: Run unit tests**

Run:

```bash
cd /Users/MAC/Documents/Claude-patch
python3 -m unittest discover -s .development/demo-recorder/tests -p 'test_*.py'
```

Expected: all tests pass.

- [ ] **Step 7: Run a full local recording smoke**

Prepare Ghostty on the intended screen with no private content visible. Then run:

```bash
cd /Users/MAC/Documents/Claude-patch
python3 .development/demo-recorder/record_demo.py \
  --config .development/demo-recorder/configs/hotrod-dragons-2.1.201-wrap-comparison.json
```

Expected: JSON output includes `runDir`, `raw`, and `gif`. The `gif` path is under `.development/demo-recordings/.../demo.gif`. Ghostty may remain open. If focus assertion fails, do not weaken the assertion; report the exact frontmost app from the error.

- [ ] **Step 8: Inspect the GIF manually**

Open the generated GIF:

```bash
open "$(python3 - <<'PY'
import json, pathlib
base = pathlib.Path('/Users/MAC/Documents/Claude-patch/.development/demo-recordings/hotrod-dragons-2.1.201-wrap-comparison')
latest = sorted(base.iterdir())[-1]
print(latest / 'demo.gif')
PY
)"
```

Expected: user can eyeball whether the terminal art looks acceptable. Do not publish automatically.

- [ ] **Step 9: Update README with full run command and publish gate**

Append to README:

```markdown
## Full recording

Prepare Ghostty on the intended screen, then run:

```bash
python3 .development/demo-recorder/record_demo.py \
  --config .development/demo-recorder/configs/hotrod-dragons-2.1.201-wrap-comparison.json
```

The reviewed GIF is written under `.development/demo-recordings/<demo>/<timestamp>/demo.gif`.

## Publish

Only publish after opening and reviewing the GIF:

```bash
python3 .development/demo-recorder/record_demo.py \
  --config .development/demo-recorder/configs/hotrod-dragons-2.1.201-wrap-comparison.json \
  --publish
```

Before publishing, confirm notifications are hidden, no private UI is visible, the crop is correct, and the output path is intentional.
```

---

### Task 7: Final verification and implementation report

**Files:**
- Read: `/Users/MAC/Documents/Claude-patch/.development/demo-recorder/record_demo.py`
- Read: `/Users/MAC/Documents/Claude-patch/.development/demo-recorder/configs/hotrod-dragons-2.1.201-wrap-comparison.json`
- Read: `/Users/MAC/Documents/Claude-patch/.development/demo-recorder/README.md`

- [ ] **Step 1: Run local tests**

Run:

```bash
cd /Users/MAC/Documents/Claude-patch
python3 -m unittest discover -s .development/demo-recorder/tests -p 'test_*.py'
```

Expected: all tests pass.

- [ ] **Step 2: Run dry-run**

Run:

```bash
cd /Users/MAC/Documents/Claude-patch
python3 .development/demo-recorder/record_demo.py \
  --config .development/demo-recorder/configs/hotrod-dragons-2.1.201-wrap-comparison.json \
  --dry-run
```

Expected: exit 0 with resolved command JSON.

- [ ] **Step 3: Run calibration or report why not**

Run if screen recording permission and screen privacy conditions are ready:

```bash
cd /Users/MAC/Documents/Claude-patch
python3 .development/demo-recorder/record_demo.py \
  --config .development/demo-recorder/configs/hotrod-dragons-2.1.201-wrap-comparison.json \
  --calibrate
```

Expected: calibration artifacts exist. If macOS permission blocks this, report the permission blocker and exact command attempted.

- [ ] **Step 4: Run full recording only with user-ready screen**

Run only after the user has prepared Ghostty/screen and agrees to screen recording:

```bash
cd /Users/MAC/Documents/Claude-patch
python3 .development/demo-recorder/record_demo.py \
  --config .development/demo-recorder/configs/hotrod-dragons-2.1.201-wrap-comparison.json
```

Expected: `.development/demo-recordings/hotrod-dragons-2.1.201-wrap-comparison/<timestamp>/demo.gif` exists.

- [ ] **Step 5: Verify no tracked package/build files changed**

Run:

```bash
cd /Users/MAC/Documents/Claude-patch
git status --short
```

Expected: the plan/spec docs may be modified, and ignored `.development/` files do not appear. No package/source/build files should be modified by recorder runs.

- [ ] **Step 6: Report results**

Final implementation report should include:

```text
Implemented local demo recorder under .development/demo-recorder/.
Verified:
- unit tests: <pass/fail command output>
- dry-run: <pass/fail>
- calibration: <artifact path or permission blocker>
- full recording: <artifact path or not run because user/screen not ready>
Residual risk:
- visual quality requires human eyeball review
- Ghostty focus/window restoration depends on prepared desktop state
```

Do not claim the GIF is README-ready until the user has opened and approved it.

---

## Self-review against spec

- Native Ghostty + AppleScript + ffmpeg flow: covered by Tasks 3, 4, 6.
- JSON config and split command path/args: covered by Tasks 1 and 2.
- Frontmost Ghostty assertions: covered by Task 3 and used by Task 4/6 event flow.
- Screen enumeration and crop validation: covered by Task 5.
- Calibration before publish: covered by Tasks 5 and 6.
- Cleanup/bounded recording: covered by Task 6 with bounded ffmpeg process and terminate/kill path.
- Privacy and publish gate: covered by Task 6 and README updates.
- Sample hotrod config for requested binary: covered by Task 1.
- No tracked package/build code changes: covered by file structure and Task 7.
