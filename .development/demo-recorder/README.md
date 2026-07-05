# Demo Recorder

Local-only demo recorder for ClaudeMonkey GIFs. It reuses a prepared Ghostty window by default, runs a configured patched Claude binary, records a selected macOS screen with ffmpeg, sends timed keystrokes through AppleScript/System Events, and creates a GIF for human review.

## Safety

Raw screen recordings can contain private UI. The recorder writes raw artifacts under `.development/demo-recordings/`. Public copies to `assets/demos/` require explicit publish opt-in.

## Prepared Ghostty contract

V1 is a button-presser for one user-prepared Ghostty, not a general terminal automation harness. Before a real run, the user must:

1. Quit unrelated Ghostty windows/sessions.
2. Launch Ghostty manually.
3. Put Ghostty on the intended display at the intended size/fullscreen state.
4. Set font/zoom/theme exactly as desired.
5. Ensure the active Ghostty surface is a clean shell prompt, not an existing Claude TUI or stale shell history.
6. Ensure the selected screen is safe to record.
7. Then run the recorder from Codex/terminal.

By default, configs use `app.launchMode: "reuseRunning"` plus `preparedGhostty.requireAlreadyRunning: true`. The recorder focuses Ghostty, fails if Ghostty is not running, fails if multiple Ghostty windows are detectable, pastes a command tagged with `DEMO_RECORDER_RUN_ID`, verifies that the intended binary process appears, and only then records events.

Use `app.launchMode: "openOrReuse"` only when a cold launch is acceptable, and set `preparedGhostty.requireAlreadyRunning: false` if you deliberately want to bypass prepared mode.

## First dry run

```bash
cd /Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder
python3 .development/demo-recorder/record_demo.py \
  --config .development/demo-recorder/configs/hotrod-dragons-2.1.201-wrap-comparison.json \
  --dry-run
```

## Permissions

macOS may require Screen Recording permission for the host process running `ffmpeg` and Accessibility permission for the process running `osascript`/System Events. If calibration times out or `screencapture -x /tmp/test.png` says it could not create an image from the display, grant Screen Recording permission to the Codex/terminal host and rerun calibration.


## Calibration

Before publishing a GIF, run calibration:

```bash
python3 .development/demo-recorder/record_demo.py \
  --config .development/demo-recorder/configs/hotrod-dragons-2.1.201-wrap-comparison.json \
  --calibrate
```

Open the generated `calibration.png` in the run directory. If the image shows the wrong display or private UI, fix the screen/Ghostty setup before recording.


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

Recording runs never copy public assets. Matrix summaries distinguish media recording from launch verification and human review. A generated summary is not publishable until a human opens the GIF and checkpoint frames, then marks that recipe with `reviewStatus: "approved"` while leaving `launchVerified: true` intact.

The Markdown summary includes this warning:

> This summary proves media files were generated. It does not approve publication. Open the GIF and checkpoint PNGs before publishing.

After approval, publish one recipe from a summary:

```bash
python3 .development/demo-recorder/run_demo_matrix.py \
  --publish-from-summary .development/demo-recordings/matrix/<timestamp>/summary.json \
  --id hidden-context-plus-hotrod-dragons-open-close
```

Do not publish from `--all-enabled` as a blind batch. Publish one reviewed recipe at a time. `--publish-from-summary` refuses records that are not review-approved or whose launch was not verified.

### Adding a recipe

Add a recipe to `demo_matrix.json` only when the binary path and event sequence are known. Use `enabled: false` with `disabledReason` for placeholders. Keep display-specific values in the matrix; do not add demo fields to `packages/*/patch.json`.

For the Hidden Context drawer stack recipe, the documented open/close sequence is: Down selects Hidden Context, Return opens the drawer, `x` closes it. Escape is intentionally not used for this demo.

### Packages intentionally skipped by default

`fable-fallback`, `reminder-suppression`, and `upstream-attachment-suppression` are not rich UI demos by default. They can get manual recipes later if a visual story is worth recording.

### Ghostty cleanup protocol

If a recording leaves Claude running, inspect the prepared Ghostty tty before killing anything:

```bash
ps -o pid=,ppid=,pgid=,tty=,stat=,command= -t ttys010
```

Kill only the Claude process group that is parented under the prepared Ghostty shell, then verify Ghostty remains alive and only login/zsh remain. Do not use global `grep claude` process matching.
