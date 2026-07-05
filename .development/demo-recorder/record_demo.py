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
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path("/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder")
DEFAULT_RECORDINGS_DIR = ROOT / ".development" / "demo-recordings"
GHOSTTY_BUNDLE_ID = "com.mitchellh.ghostty"


class RecorderError(RuntimeError):
    pass


@dataclass(frozen=True)
class AppConfig:
    name: str
    bundle_id: str
    leave_open_at_end: bool
    launch_mode: str


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
class PreparedGhosttyConfig:
    require_already_running: bool
    require_single_window_if_detectable: bool
    allow_multiple_windows: bool
    assume_clean_shell_prompt: bool


@dataclass(frozen=True)
class DemoConfig:
    demo_name: str
    app: AppConfig
    screen: ScreenConfig
    command: CommandConfig
    recording: RecordingConfig
    events: tuple[dict[str, Any], ...]
    publish: PublishConfig
    prepared_ghostty: PreparedGhosttyConfig


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
    prepared_raw = raw.get("preparedGhostty", {})
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
    if not isinstance(prepared_raw, dict):
        raise RecorderError("preparedGhostty must be an object")
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
            launch_mode=str(app_raw.get("launchMode", "reuseRunning")),
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
        prepared_ghostty=PreparedGhosttyConfig(
            require_already_running=bool(prepared_raw.get("requireAlreadyRunning", True)),
            require_single_window_if_detectable=bool(prepared_raw.get("requireSingleWindowIfDetectable", True)),
            allow_multiple_windows=bool(prepared_raw.get("allowMultipleWindows", False)),
            assume_clean_shell_prompt=bool(prepared_raw.get("assumeCleanShellPrompt", True)),
        ),
    )

def shell_command(command: CommandConfig, *, run_id: str | None = None) -> str:
    parts = [shlex.quote(str(command.path)), *[shlex.quote(arg) for arg in command.args]]
    env = f"DEMO_RECORDER_RUN_ID={shlex.quote(run_id)} " if run_id else ""
    return f"cd {shlex.quote(str(command.cwd))} && " + env + " ".join(parts)

def validate_config(config: DemoConfig) -> None:
    if not config.command.cwd.exists() or not config.command.cwd.is_dir():
        raise RecorderError(f"command.cwd does not exist or is not a directory: {config.command.cwd}")
    if not config.command.path.exists() or not config.command.path.is_file():
        raise RecorderError(f"command.path does not exist or is not a file: {config.command.path}")
    if config.app.launch_mode not in {"reuseRunning", "openOrReuse"}:
        raise RecorderError("app.launchMode must be reuseRunning or openOrReuse")
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
    allowed_keys = {"down", "up", "left", "right", "return", "x", "ctrl-c"}
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


def applescript_string(value: str) -> str:
    return '"' + value.replace('\\', '\\\\').replace('"', '\"') + '"'


def applescript_app_is_running(bundle_id: str) -> str:
    return (
        'tell application "System Events" to exists '
        f'(first application process whose bundle identifier is {applescript_string(bundle_id)})'
    )


def app_is_running(bundle_id: str) -> bool:
    return run_osascript(applescript_app_is_running(bundle_id)).strip().lower() == "true"


def applescript_window_count(bundle_id: str) -> str:
    quoted = applescript_string(bundle_id)
    return (
        'tell application "System Events"\n'
        f'  set matches to application processes whose bundle identifier is {quoted}\n'
        '  if (count of matches) is 0 then return -1\n'
        '  return count of windows of item 1 of matches\n'
        'end tell'
    )

def app_window_count(bundle_id: str) -> int | None:
    try:
        raw = run_osascript(applescript_window_count(bundle_id)).strip()
        count = int(raw)
    except Exception:
        return None
    return count if count >= 0 else None


def assert_prepared_ghostty(config: DemoConfig) -> None:
    if not config.prepared_ghostty.require_single_window_if_detectable:
        return
    count = app_window_count(config.app.bundle_id)
    if count is None:
        return
    if count > 1 and not config.prepared_ghostty.allow_multiple_windows:
        raise RecorderError(
            f"{config.app.name} has {count} detectable windows; prepared mode requires one. "
            "Quit unrelated Ghostty windows or set preparedGhostty.allowMultipleWindows=true."
        )

def focus_running_app(bundle_id: str) -> None:
    run_osascript(
        'tell application "System Events" to set frontmost of '
        f'(first application process whose bundle identifier is {applescript_string(bundle_id)}) to true'
    )


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
        "x": 'keystroke "x"',
        "ctrl-c": 'keystroke "c" using control down',
    }
    if key not in mapping:
        raise RecorderError(f"unsupported key for AppleScript event: {key!r}")
    return f'tell application "System Events" to {mapping[key]}'


def send_key(config: DemoConfig, key: str) -> None:
    open_and_focus_app(config)
    assert_frontmost_bundle(config.app.bundle_id)
    run_osascript(applescript_for_key(key))


def send_text(config: DemoConfig, text: str) -> None:
    open_and_focus_app(config)
    assert_frontmost_bundle(config.app.bundle_id)
    escaped = text.replace('\\', '\\\\').replace('"', '\"')
    run_osascript(f'tell application "System Events" to keystroke "{escaped}"')


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


def open_and_focus_app(config: DemoConfig, *, timeout_seconds: float = 10.0) -> None:
    running = app_is_running(config.app.bundle_id)
    if config.prepared_ghostty.require_already_running and not running:
        raise RecorderError(
            f"{config.app.name} ({config.app.bundle_id}) is not running; prepared Ghostty mode requires you to "
            "open one clean shell prompt on the selected screen before recording"
        )
    if config.app.launch_mode == "openOrReuse" and not running:
        subprocess.run(["open", "-b", config.app.bundle_id], check=False)
    elif not running:
        raise RecorderError(
            f"{config.app.name} ({config.app.bundle_id}) is not running; "
            "open and prepare the window first or set app.launchMode=openOrReuse"
        )

    deadline = time.time() + timeout_seconds
    last = ""
    while time.time() < deadline:
        try:
            focus_running_app(config.app.bundle_id)
            last = frontmost_bundle()
        except RecorderError:
            last = ""
        if last == config.app.bundle_id:
            assert_prepared_ghostty(config)
            return
        time.sleep(0.25)
    raise RecorderError(f"failed to focus {config.app.bundle_id}; last frontmost bundle={last!r}")

def get_clipboard() -> str:
    result = subprocess.run(["pbpaste"], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return result.stdout if result.returncode == 0 else ""


def set_clipboard(text: str) -> None:
    subprocess.run(["pbcopy"], input=text, text=True, check=True)


def paste_text(config: DemoConfig, text: str) -> None:
    open_and_focus_app(config)
    assert_frontmost_bundle(config.app.bundle_id)
    set_clipboard(text)
    if get_clipboard() != text:
        raise RecorderError("clipboard verification failed after pbcopy; refusing to paste stale clipboard")
    run_osascript('tell application "System Events" to keystroke "v" using command down')


def paste_and_return(config: DemoConfig, text: str) -> None:
    paste_text(config, text)
    send_key(config, "return")


def launch_demo_command(config: DemoConfig, *, run_id: str) -> str:
    resolved = shell_command(config.command, run_id=run_id)
    open_and_focus_app(config)
    paste_and_return(config, resolved)
    return resolved

def make_run_id(config: DemoConfig) -> str:
    return f"demo-recorder-{config.demo_name}-{timestamp()}-{uuid.uuid4().hex[:8]}"


def print_launch_contract(config: DemoConfig, *, run_id: str) -> None:
    print(
        "Prepared Ghostty contract:\n"
        f"- run id: {run_id}\n"
        f"- app: {config.app.name} ({config.app.bundle_id}) must already be on screen {config.screen.label}\n"
        "- active Ghostty surface must be a clean shell prompt, safe to record\n"
        "- unrelated Ghostty windows/sessions should be closed\n"
        "- recorder will paste the command, verify the launched process, then record",
        file=sys.stderr,
    )

def process_table() -> str:
    result = subprocess.run(
        ["ps", "-ww", "-axo", "pid=,command="],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise RecorderError(f"ps failed while verifying launch: {result.stderr.strip() or result.returncode}")
    return result.stdout


def matching_launch_processes(config: DemoConfig) -> list[dict[str, Any]]:
    table = process_table()
    expected_binary = str(config.command.path)
    expected_args = list(config.command.args)
    matches: list[dict[str, Any]] = []
    own_pid = os.getpid()
    for line in table.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        pieces = stripped.split(maxsplit=1)
        if len(pieces) != 2 or not pieces[0].isdigit():
            continue
        pid = int(pieces[0])
        command = pieces[1]
        if pid == own_pid:
            continue
        if expected_binary not in command:
            continue
        if not all(arg in command for arg in expected_args):
            continue
        matches.append({"pid": pid, "command": command})
    return matches


def verify_launch_process(
    config: DemoConfig,
    *,
    run_id: str,
    launched_at: float,
    prelaunch_pids: set[int] | None = None,
) -> dict[str, Any]:
    prelaunch_pids = prelaunch_pids or set()
    matches = matching_launch_processes(config)
    new_matches = [match for match in matches if int(match["pid"]) not in prelaunch_pids]
    result: dict[str, Any] = {
        "runId": run_id,
        "verified": False,
        "expectedBinary": str(config.command.path),
        "expectedArgs": list(config.command.args),
        "launchedAt": launched_at,
        "prelaunchPids": sorted(prelaunch_pids),
        "matchCount": len(matches),
        "newMatchCount": len(new_matches),
        "matches": matches,
        "newMatches": new_matches,
    }
    if len(new_matches) == 1:
        result.update({"verified": True, "matchedPid": new_matches[0]["pid"], "matchedCommand": new_matches[0]["command"]})
        return result
    if not new_matches:
        raise RecorderError(f"launch verification failed: no new process found for {config.command.path}")
    raise RecorderError(f"launch verification ambiguous: {len(new_matches)} new matching processes found for {config.command.path}")

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
    return {name: tool_path(name) for name in ["ffmpeg", "ffprobe", "osascript", "open", "pbcopy", "pbpaste", "ps"]}

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
        r'print("screen \(i): frame=\(Int(f.origin.x)),\(Int(f.origin.y)) \(Int(f.width))x\(Int(f.height)) visible=\(Int(v.origin.x)),\(Int(v.origin.y)) \(Int(v.width))x\(Int(v.height)) scale=\(s.backingScaleFactor)") '
        '}'
    )
    result = subprocess.run(["swift", "-e", swift], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return result.stdout if result.returncode == 0 else result.stderr


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
    try:
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
            timeout=15,
        )
    except subprocess.TimeoutExpired as exc:
        raise RecorderError(
            "calibration ffmpeg timed out; macOS screen capture may be blocked for this host. "
            "Check Screen Recording permission, or verify `screencapture -x /tmp/test.png` works."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise RecorderError(f"calibration ffmpeg failed with exit code {exc.returncode}") from exc
    if not sample.exists() or sample.stat().st_size == 0:
        raise RecorderError("calibration movie was not created or is empty")
    width, height = ffprobe_dimensions(sample)
    subprocess.run(["ffmpeg", "-y", "-i", str(sample), "-frames:v", "1", str(frame)], check=True)
    if config.screen.crop:
        validate_crop(config.screen.crop, width=width, height=height)
    data = {"sample": str(sample), "frame": str(frame), "width": width, "height": height, "crop": config.screen.crop}
    write_json(run_dir / "calibration.json", data)
    return data


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

def publish_gif(config: DemoConfig, gif: Path, *, cli_publish: bool) -> Path | None:
    if not (config.publish.enabled or cli_publish):
        return None
    if config.publish.output_gif is None:
        raise RecorderError("publish requested but publish.outputGif is missing")
    output = config.publish.output_gif
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(gif, output)
    return output


def run_recording(config: DemoConfig, config_path: Path, *, cli_publish: bool) -> dict[str, Any]:
    preflight_tools()
    run_id = make_run_id(config)
    print_launch_contract(config, run_id=run_id)
    run_dir = make_run_dir(config)
    resolved = shell_command(config.command, run_id=run_id)
    write_json(run_dir / "config.snapshot.json", {"configPath": str(config_path), "resolvedCommand": resolved, "runId": run_id})
    (run_dir / "avfoundation-devices.txt").write_text(list_avfoundation_devices(), encoding="utf-8")
    (run_dir / "nsscreens.txt").write_text(list_nsscreens(), encoding="utf-8")
    calibration = run_calibration(config, run_dir)
    prelaunch_pids = {int(match["pid"]) for match in matching_launch_processes(config)}
    launched_at = time.time()
    launch_demo_command(config, run_id=run_id)
    time.sleep(config.recording.post_launch_wait_seconds)
    launch = verify_launch_process(config, run_id=run_id, launched_at=launched_at, prelaunch_pids=prelaunch_pids)
    write_json(run_dir / "launch-verification.json", launch)
    raw = record_screen_while_events(config, run_dir)
    gif = convert_to_gif(config, raw, run_dir)
    published = publish_gif(config, gif, cli_publish=cli_publish)
    metadata = {
        "runId": run_id,
        "runDir": str(run_dir),
        "raw": str(raw),
        "gif": str(gif),
        "published": str(published) if published else None,
        "calibration": calibration,
        "launch": launch,
        "recordingStatus": "recorded",
        "launchVerified": bool(launch.get("verified")),
        "reviewStatus": "needs-human-review",
        "needsReview": True,
        "publishStatus": "published" if published else "not-published",
    }
    write_json(run_dir / "metadata.json", metadata)
    return metadata

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
        validate_config(config)
        resolved = shell_command(config.command)
        print(json.dumps({"demoName": config.demo_name, "resolvedCommand": resolved}, indent=2))
        if args.dry_run:
            return 0
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
    except RecorderError as exc:
        print(f"record-demo: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
