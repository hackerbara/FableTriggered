# Demo Recorder Design

Date: 2026-07-04  
Status: revised draft after value/code collaborator review  
Workspace: `/Users/MAC/Documents/Claude-patch`  
Scope: design only; do not implement from this document until an implementation plan is approved.

## Purpose

Create a local, repeatable demo recorder for ClaudeMonkey package GIFs. The recorder lets the user prepare a clean Ghostty window/screen once, then run a scripted capture: launch/focus Ghostty, run a selected patched Claude binary, record a selected screen, drive the interaction with timed keystrokes, and convert the result into an eyeballable GIF.

This is not a regression-verification harness. It is native-pixel demo tooling for visual review and README/GitHub assets.

## Why native screen capture

Rich ClaudeMonkey visual packages are not ordinary terminal text. Hotrod Dragons and Capybara Onsen render truecolor half-block pixel art through Claude Code’s `ink-raw-ansi` direct-draw path; drawer packages require live footer navigation and overlay rendering. A terminal-replay pipeline can preserve ANSI bytes, but the README-quality artifact should come from the actual terminal renderer when visual fidelity matters.

The recorder therefore uses:

- **Ghostty** as the native terminal renderer;
- **AppleScript/System Events** as the button presser;
- **ffmpeg/AVFoundation** as the camera;
- **ffmpeg palette generation** as the GIF encoder.

## Current local display evidence

`ffmpeg -f avfoundation -list_devices true -i ""` exposes:

- `[2] Capture screen 0`
- `[3] Capture screen 1`

`system_profiler SPDisplaysDataType` and `NSScreen` report:

| Recorder screen | Display | Logical frame | Physical/rendered backing | Notes |
|---|---|---:|---:|---|
| screen 0 | DELL U2715H | `2048x1152` | `4096x2304` | Main display; effectively 16:9 |
| screen 1 | Built-in Color LCD | `1512x982` | `3024x1964` | Laptop display; roughly 3:2 |

The recorder must enumerate screens/devices at runtime and print the observed values before capture. Device indices may change, so saved configs must record both the requested device index and the observed raw-frame dimensions.

## Goals

1. Produce repeatable local demo artifacts without manual key pressing.
2. Capture native terminal pixels for truecolor half-block art, footer drawers, overlays, and animation.
3. Support both pure visual demos and interactive footer/drawer demos.
4. Make screen choice, crop rectangle, timings, command path/args, and key events explicit per demo.
5. Keep raw recordings and intermediate artifacts under ignored `.development/` paths.
6. Publish to `assets/demos/` only behind an explicit publish gate.
7. Fail safely on missing tools, permissions, focus drift, invalid crop, or command-launch problems.

## Non-goals

- No live Claude binary patching.
- No installing asciinema, agg, vhs, gifski, or global tools.
- No login automation, account setup, network/auth workaround, or prompt submission.
- No editing package code or build artifacts.
- No automated claim that a visual demo is correct; the output is for human eyeball review.
- No replacement for the future xterm/Playwright harness.

## Architecture

```text
JSON demo config
  -> Python recorder driver
     -> preflight tools/permissions/screen/crop
     -> open/focus Ghostty by bundle id
     -> assert frontmost app before key batches
     -> paste shell-quoted command and press Return
     -> start ffmpeg bounded screen recording
     -> send structured timed key events through AppleScript/System Events
     -> cleanup/trap ffmpeg and optional target process interruption
     -> convert raw recording to GIF via ffmpeg palette workflow
     -> write .development artifacts; optionally publish reviewed GIF
```

The first implementation should be a Python driver, not a shell script, because Python can parse JSON config, shell-quote paths/args safely, run subprocesses, and track cleanup state more reliably than a sourced shell config.

## Config format

Use JSON. Avoid `eval` or shell-sourced config files.

Example:

```json
{
  "demoName": "hotrod-dragons-2.1.201-wrap-comparison",
  "app": {
    "name": "Ghostty",
    "bundleId": "com.mitchellh.ghostty",
    "requireNotRunningAtStart": false,
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
    {"type": "wait", "seconds": 2},
    {"type": "key", "key": "down"},
    {"type": "wait", "seconds": 1},
    {"type": "key", "key": "return"},
    {"type": "wait", "seconds": 3},
    {"type": "text", "text": "x"}
  ],
  "publish": {
    "enabled": false,
    "outputGif": "/Users/MAC/Documents/Claude-patch/assets/demos/hotrod-dragons.gif"
  }
}
```

### Command handling

The config must split executable path from args:

- `command.path` is an absolute path to verify with `stat`.
- `command.args` is an array of literal arguments.
- `command.cwd` is an absolute working directory.

The driver constructs a terminal command using shell-safe quoting:

```text
cd <quoted cwd> && <quoted command.path> <quoted args...>
```

The resolved command is written to `config.snapshot.json` for audit. The driver must not accept arbitrary shell fragments unless a future config field explicitly opts into shell mode with a warning.

## Key/event model

Use structured JSON events, not a semicolon mini-language.

Supported v1 events:

| Event | Meaning |
|---|---|
| `{ "type": "wait", "seconds": N }` | sleep |
| `{ "type": "key", "key": "down" }` | ArrowDown |
| `{ "type": "key", "key": "up" }` | ArrowUp |
| `{ "type": "key", "key": "left" }` | ArrowLeft |
| `{ "type": "key", "key": "right" }` | ArrowRight |
| `{ "type": "key", "key": "return" }` | Return |
| `{ "type": "key", "key": "ctrl-c" }` | interrupt, only after frontmost Ghostty assertion |
| `{ "type": "text", "text": "x" }` | type literal text |
| `{ "type": "paste", "text": "..." }` | paste literal text; avoid secrets |

For Hidden Context drawer demos, use `x` to close. Do not send Escape.

## AppleScript/System Events driver

The driver should generate small AppleScript snippets for each action. It must assert focus before any non-wait event.

Frontmost assertion:

```applescript
tell application "System Events"
  set frontBundle to bundle identifier of first application process whose frontmost is true
end tell
```

If `frontBundle` is not `com.mitchellh.ghostty`, stop before sending keys.

Example key mappings:

| Logical key | AppleScript action |
|---|---|
| `down` | `key code 125` |
| `up` | `key code 126` |
| `left` | `key code 123` |
| `right` | `key code 124` |
| `return` | `key code 36` |
| `ctrl-c` | `keystroke "c" using control down` |
| `text: x` | `keystroke "x"` |

Prefer paste+Return for the full launch command rather than slow typing. The implementation can place text on the clipboard only if it snapshots/restores the prior clipboard where practical, or it can use `System Events` keystroke for short safe strings. Clipboard handling should be logged because it touches user desktop state.

## Ghostty focus/window protocol

V1 should be conservative:

1. Open Ghostty by bundle id or app path.
2. Activate Ghostty.
3. Poll until the frontmost bundle id is `com.mitchellh.ghostty` or timeout.
4. Do not assume the selected screen is correct; print a reminder and rely on the user's prepared Ghostty restoration.
5. Paste/run the command only after frontmost assertion passes.
6. Assert frontmost Ghostty again before every key/text/paste event.
7. Do not close Ghostty by default; leave it open for inspection.

Optional later improvement: a dedicated Ghostty profile/window title/session launcher if Ghostty exposes a reliable CLI or AppleScript surface for that on this machine.

## Recording flow

A v1 run should do this:

1. Load and validate JSON config.
2. Create timestamped run directory under `.development/demo-recordings/<demoName>/`.
3. Verify `ffmpeg`, `ffprobe`, `osascript`, and target command path exist.
4. Enumerate AVFoundation devices and NSScreen dimensions; write them to run metadata.
5. Validate crop, if provided, against a preflight sample's actual raw-frame dimensions.
6. Open/focus Ghostty and assert frontmost app.
7. Paste/run the shell-quoted command in Ghostty.
8. Wait `postLaunchWaitSeconds`.
9. Start a bounded `ffmpeg` recording for `recordSeconds`.
10. Run structured events while recording, asserting frontmost Ghostty before each non-wait event.
11. Wait for recording completion.
12. Convert raw recording to GIF with palette generation.
13. Write logs and config snapshot.
14. If `publish.enabled` is true, require preflight/review checks and copy the reviewed GIF to `assets/demos/`.

`recording.start` may later support `beforeLaunch`, but v1 can implement only `afterLaunchSettle` unless a demo requires startup capture.

## ffmpeg strategy

Capture selected screen:

```bash
ffmpeg -y   -f avfoundation   -framerate 30   -i "${DEVICE}:none"   -t "${RECORD_SECONDS}"   raw.mov
```

Probe actual dimensions:

```bash
ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of json raw.mov
```

Convert with palette workflow:

```bash
ffmpeg -y -i raw.mov   -vf "<optional crop>,fps=<fps>,scale=<scaleWidth>:-1:flags=lanczos,palettegen=stats_mode=diff"   palette.png

ffmpeg -y -i raw.mov -i palette.png   -lavfi "<optional crop>,fps=<fps>,scale=<scaleWidth>:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle"   demo.gif
```

The implementation should tune palette/dither only after visual review; crisp terminal readability beats minimum file size.

## Preflight and calibration

V1 should include a preflight/calibration mode before publishing:

1. Record a 1-2 second sample of the selected screen.
2. Verify the sample file is non-empty.
3. Extract one PNG frame.
4. Run `ffprobe` and print actual video dimensions.
5. If crop is configured, validate `x + w <= width` and `y + h <= height`.
6. Optionally run ffmpeg `blackdetect` or a simple frame-size/non-black check to catch missing Screen Recording permission.
7. Write `calibration.png` and `calibration.json` into the run directory.

A public publish should require either a recent successful calibration or an explicit `--skip-calibration` flag.

## Cleanup and traps

The implementation must track subprocesses and clean up on failure:

- bound every ffmpeg recording by `recordSeconds`;
- store the ffmpeg PID;
- on `INT`, `TERM`, or unhandled exception, terminate ffmpeg if still running;
- write separate statuses for config validation, Ghostty focus, launch command, recording, event script, conversion, and publish;
- send final `ctrl-c` only if configured and only after frontmost Ghostty assertion passes;
- do not send cleanup keys to an unknown frontmost app.

## Privacy and publish gate

Default output is development-only:

```text
.development/demo-recordings/<demoName>/<timestamp>/
  raw.mov
  calibration.png
  palette.png
  demo.gif
  recorder.log
  config.snapshot.json
  metadata.json
```

Public output is opt-in:

```text
assets/demos/<demo-name>.gif
```

Before publish, print a checklist:

- notifications disabled or hidden;
- wrong windows/desktops not visible;
- no secrets/account data visible;
- crop reviewed;
- GIF visually approved;
- output path is intentional.

The script may copy to `assets/demos/` only when `publish.enabled` or a `--publish` flag is set. Raw `.mov` files must remain ignored under `.development/`.

## Initial demo candidates

1. `hotrod-dragons-2.1.201-wrap-comparison`
   - Path: `/Users/MAC/Documents/Claude-patch/.development/claude-monkey-builds/hotrod-dragons-2.1.201-wrap-comparison/claude`
   - Args: `--dangerously-skip-permissions`
   - Purpose: rich-art native terminal demo.
   - Events: likely wait-only plus optional `ctrl-c` after recording.

2. `hidden-context-drawer`
   - Path: choose the current drawer-enabled binary when version/build is selected.
   - Purpose: footer interaction demo.
   - Events: `down`, `return`, optional scroll, `x`; no Escape.

3. future combined visual + drawer build
   - Purpose: show rich art and functional footer drawer in one native capture.

## Resolved design decisions after review

- Use JSON config instead of shell-sourced variables.
- Split command path and args.
- Use a Python driver for quoting, subprocess cleanup, and structured events.
- Assert frontmost Ghostty before sending each non-wait event.
- Default to `.development/` output only; publish requires explicit opt-in.
- Treat crop calibration as first-class before README publication.

## Open questions before implementation plan

1. Should v1 implement only `afterLaunchSettle` recording, or also `beforeLaunch`?
   - Proposed v1: implement only `afterLaunchSettle`.
2. Should v1 require Ghostty to be already quit before launch?
   - Proposed v1: no, but warn if multiple Ghostty windows exist and rely on frontmost assertion.
3. Should v1 use clipboard paste for the launch command?
   - Proposed v1: yes, with clipboard snapshot/restore if feasible and a log entry.

## Definition of done for implementation

- A Python demo recorder exists under `.development/demo-recorder/` or `.development/scripts/`.
- A sample JSON config exists for `hotrod-dragons-2.1.201-wrap-comparison`.
- The driver enumerates/prints AVFoundation devices and NSScreen dimensions.
- The driver validates command path, cwd, tools, crop, and output paths.
- The driver launches/focuses Ghostty and asserts frontmost bundle id before key events.
- The driver can paste/run the target command and send `wait`, `down`, `up`, `return`, `x`, and `ctrl-c` events.
- The driver records a selected screen with ffmpeg and creates a GIF via palette generation.
- Calibration artifacts are written and crop bounds are validated.
- Raw artifacts remain under `.development/demo-recordings/`.
- Public `assets/demos/` output happens only with explicit publish opt-in.
- No tracked package/build files are modified by recorder runs.
