# Demo Matrix Runner Design

Date: 2026-07-04
Status: revised draft after collaborator review
Workspace: `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder`
Scope: design only; implementation should follow an approved plan.

## Purpose

Build a small local runner around the existing demo recorder so ClaudeMonkey demo GIFs can be generated from a curated internal matrix instead of one hand-written recorder config at a time.

The existing primitive, `.development/demo-recorder/record_demo.py`, is good at running one scripted Ghostty capture. The missing layer is orchestration: which patched binaries should be demonstrated, which interaction sequence proves the feature, what output name should be used, and which demos are safe to run in a batch after the user prepares the desktop.

The matrix runner is local demo infrastructure, not package metadata and not a correctness harness.

## Current evidence

The local recorder already exists under:

```text
.development/demo-recorder/
  record_demo.py
  README.md
  configs/
  tests/test_record_demo.py
```

Known working recorder behaviors from the current worktree:

- unit tests cover config parsing, event validation, focus behavior, and the explicit `x` close key;
- `record_demo.py` can reuse a prepared Ghostty window via `app.launchMode: "reuseRunning"`;
- the old stacked Hotrod Dragons + Hidden Context artifact can be recorded end-to-end;
- the successful combined demo sequence is `down`, `down`, hold open, `x`, hold closed, `ctrl-c`;
- cleanup must use the Ghostty tty/process protocol rather than global process guessing.

The currently enumerated package directories are:

| Package | Demo relevance |
|---|---|
| `hotrod-dragons` | record by default; visual frame package |
| `capybara-onsen` | candidate; record once a preferred reviewed artifact is selected; visual frame package |
| `hidden-context-drawer` | candidate; record once a preferred reviewed artifact and deterministic open/close sequence are selected |
| `reminders-manager` | candidate; record when the drawer can be opened in a deterministic prepared session |
| `thinking-text-drawer` | candidate; record empty/open state once a preferred reviewed stack artifact and deterministic empty-state/open key path are selected |
| `normal-channel-hidden-context` | optional/manual; transcript-rendering demo, not a drawer |
| `fable-fallback` | skip by default; behavior visibility is not a rich UI demo |
| `reminder-suppression` | skip by default; suppression behavior is not directly visible |
| `upstream-attachment-suppression` | skip by default; suppression behavior is not directly visible |

## Design decision: do not change package schema

Do not add demo fields to `packages/*/patch.json` for v1.

Reasons:

1. Demo recording depends on local desktop state: Ghostty zoom, screen device index, crop, privacy readiness, and macOS permissions.
2. Demo recipes often target built artifacts or stacks, not one package in isolation.
3. Some packages have no useful visual demo even though they are valid patch packages.
4. The schema should describe patch/build behavior; demo capture is presentation workflow metadata.
5. Keeping the matrix local avoids creating stale public package promises around one user's display setup.

If demo recipes later need to ship publicly, add a separate `demos/` registry or manifest after the local workflow proves stable. Do not burden the patch schema now.

## Architecture

```text
curated demo matrix JSON
  -> run_demo_matrix.py
     -> list/select enabled recipes
     -> validate recipe and target artifact paths
     -> materialize temporary record_demo.py config
     -> run record_demo.py once per selected recipe
     -> extract optional checkpoint frames
     -> write per-run summary JSON/Markdown
     -> never publish during recording; publish only from reviewed summary
```

`record_demo.py` remains the single-demo executor. The new runner does not duplicate Ghostty, AppleScript, ffmpeg, GIF conversion, crop validation, or frontmost-app logic.

The runner owns only batch orchestration and recipe-to-config translation.

## Files

Create or modify only local demo-recorder files in this worktree:

```text
.development/demo-recorder/
  demo_matrix.json              # curated internal recipe list
  run_demo_matrix.py            # matrix orchestration CLI
  README.md                     # add batch usage notes
  tests/test_demo_matrix.py     # unit tests for recipe parsing/planning
```

No `packages/**`, `src/**`, or build artifact files are part of this design.

The implementation plan may choose to keep these files ignored under `.development/`, matching the existing recorder. This is acceptable because the matrix encodes local paths and desktop assumptions. The tracked design spec is the durable project knowledge.

## Matrix format

Use JSON for the same reasons as the single-recorder config: strict parsing, no shell `eval`, easy test fixtures.

Top level:

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
  "recipes": []
}
```

Recipe shape:

```json
{
  "id": "hidden-context-plus-hotrod-dragons-open-close",
  "enabled": true,
  "category": "stack",
  "purpose": "Show Hotrod Dragons plus Hidden Context drawer open and close.",
  "cwd": "/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder",
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
}
```

The runner merges `defaults` with each recipe to materialize a standard `record_demo.py` config. Recipe fields override defaults only in known locations: `app`, `screen`, `args`, `recording`, `events`, `cwd`, `binary`, and `publishGif`.

### Materialization contract

The generated single-recorder config is not inferred loosely from stdout or shell conventions. It is built by this explicit mapping:

- `demoName = recipe.demoName ?? recipe.id`
- `app = defaults.app` deep-merged with `recipe.app ?? {}`
- `screen = defaults.screen` deep-merged with `recipe.screen ?? {}`
- `command.cwd = recipe.cwd ?? defaults.cwd`
- `command.path = recipe.binary`
- `command.args = recipe.args ?? defaults.args ?? []`
- `recording = defaults.recording` deep-merged with `recipe.recording ?? {}`
- `events = recipe.events`
- `publish.enabled = false`
- `publish.outputGif = recipe.publishGif ?? null`

The runner must validate the generated recorder config with `record_demo.parse_config()` and `record_demo.validate_config()` before recording. Unknown matrix keys should fail validation so typos do not silently alter demos.

## Initial recipe set

V1 matrix should include only recipes with a known artifact path or an intentional disabled placeholder.

Enabled recipes:

1. `hotrod-dragons-2.1.201-wrap-comparison`
   - Binary: `/Users/MAC/Documents/Claude-patch/.development/claude-monkey-builds/hotrod-dragons-2.1.201-wrap-comparison/claude`
   - Purpose: show the rich Hotrod Dragons frame.
   - Events: wait, then `ctrl-c`.

2. `hidden-context-plus-hotrod-dragons-open-close`
   - Binary: `/Users/MAC/Documents/Claude-patch/.development/claude-monkey-builds/hidden-context-plus-hotrod-dragons-2.1.199/claude`
   - Purpose: show rich art plus Hidden Context drawer opening and closing.
   - Events: `down`, `down`, hold, `x`, hold, `ctrl-c`.

Disabled placeholders:

1. `capybara-onsen`
   - Disabled until the preferred reviewed artifact and framing are selected. Local spike artifacts may exist, but they are not yet chosen for the curated demo matrix.

2. `hidden-context-drawer-open-close`
   - Disabled until the preferred standalone drawer artifact and deterministic open/close event sequence are selected.

3. `reminders-manager-open-close`
   - Disabled until a preferred reviewed stack artifact and deterministic key path are selected.

4. `thinking-text-drawer-open-close`
   - Disabled until a preferred reviewed stack artifact and deterministic empty-state/open key path are selected.

Skipped packages should be documented in the matrix file or README, not encoded as enabled recipes.

## CLI

Recommended commands:

```bash
python3 .development/demo-recorder/run_demo_matrix.py --list
python3 .development/demo-recorder/run_demo_matrix.py --id hidden-context-plus-hotrod-dragons-open-close
python3 .development/demo-recorder/run_demo_matrix.py --all-enabled
python3 .development/demo-recorder/run_demo_matrix.py --publish-from-summary .development/demo-recordings/matrix/20260704-130000/summary.json --id hidden-context-plus-hotrod-dragons-open-close
```

Behavior:

- `--list` prints recipe id, enabled state, category, purpose, and whether the binary currently exists.
- `--id` runs exactly one recipe by id, even if disabled only when `--include-disabled` is supplied.
- `--all-enabled` runs enabled recipes in matrix order.
- V1 must not publish during recording. `publishGif` is recorded as an intended destination only.
- `--dry-run` validates and prints the generated `record_demo.py` config without recording.
- `--stop-on-failure` is the default for `--all-enabled`; a future `--continue-on-failure` may be added after the first implementation.
- `--publish-from-summary <summary.json> --id <recipe-id>` copies an already-reviewed GIF from a completed summary to `publishGif`.
- `--publish-from-summary` must publish one reviewed recipe at a time; it is rejected for batch/all-enabled publishing.

## Execution contract

The matrix runner should import `record_demo.py` as a module and call `parse_config()`, `validate_config()`, and `run_recording()` so it receives the metadata dictionary directly. It must not parse recorder stdout as a single JSON object, because the current CLI prints a pre-run command object and final metadata separately.

If subprocess isolation is chosen instead during implementation, the runner must define and test a robust final-metadata extraction rule and verify that the referenced `metadata.json`, `raw.mov`, and `demo.gif` exist. Importing is the preferred v1 path because it avoids depending on incidental CLI stdout shape.

`record_demo.py` publish should not be invoked from matrix recording runs. The generated config always sets `publish.enabled = false`; matrix publishing is the separate `--publish-from-summary` path after human review.

## Output layout

The runner should write batch-level artifacts under the same ignored output root:

```text
.development/demo-recordings/matrix/<timestamp>/
  matrix.snapshot.json
  summary.json
  summary.md
  generated-configs/
    <recipe-id>.json
  checkpoints/
    <recipe-id>-open.png
    <recipe-id>-closed.png
```

Each `record_demo.py` invocation still writes its normal per-demo run directory. The matrix `summary.json` links to those run directories and GIF paths.

Summary record per recipe:

```json
{
  "id": "hidden-context-plus-hotrod-dragons-open-close",
  "status": "passed",
  "generatedConfig": "/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recordings/matrix/20260704-130000/generated-configs/hidden-context-plus-hotrod-dragons-open-close.json",
  "runDir": "/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recordings/hidden-context-plus-hotrod-dragons-2.1.199-open-drawer/20260704-124911",
  "gif": "/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recordings/hidden-context-plus-hotrod-dragons-2.1.199-open-drawer/20260704-124911/demo.gif",
  "checkpoints": {
    "open": "/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recordings/matrix/20260704-130000/checkpoints/hidden-context-plus-hotrod-dragons-open-close-open.png",
    "closed": "/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recordings/matrix/20260704-130000/checkpoints/hidden-context-plus-hotrod-dragons-open-close-closed.png"
  }
}
```

## Checkpoint frames

Checkpoint frames are evidence for human review, not automated visual assertions.

For each configured checkpoint, run ffmpeg against the raw recording produced by `record_demo.py`:

```bash
ffmpeg -y -ss <atSeconds> -i raw.mov -frames:v 1 checkpoint.png
```

The runner must fail a recipe if a configured checkpoint cannot be extracted. It must not claim that a drawer is semantically open or closed from pixels alone in v1. The human review loop remains responsible for visual correctness.

## Ghostty and process safety

The matrix runner must not invent a broader close protocol.

It should rely on `record_demo.py` for key events and on the established Ghostty tty cleanup protocol when manual cleanup is needed:

1. inspect the specific Ghostty tty with `ps -o pid=,ppid=,pgid=,tty=,stat=,command= -t <tty>`;
2. identify only processes spawned under the prepared Ghostty shell;
3. signal only that child process group;
4. verify Ghostty remains alive and only login/shell remain.

V1 may document this as an operator protocol rather than automate tty cleanup, because safely discovering the exact prepared Ghostty tty is a separate desktop-integration problem. If automation is added later, it must be tied to an explicitly configured tty or to recorder-owned process evidence, not global `grep claude` matching.

## Privacy and batching

`--all-enabled` is allowed only after the user has prepared the screen. The runner should print a privacy reminder before any non-dry-run batch:

- selected screen is safe to record;
- notifications are hidden;
- Ghostty is on the intended screen and zoom level;
- no private windows are visible;
- the run may record multiple demos without further prompts.

The runner does not need an interactive confirmation prompt before local recording if the user invoked it directly in a trusted local shell, but the warning should appear in logs and stdout. This does not authorize publishing; public copy remains a separate reviewed `--publish-from-summary` step.

## Validation rules

The runner must validate before launching any recording:

- matrix `version` is `1`;
- recipe ids are unique and shell/path safe for filenames;
- enabled recipe binaries exist and are files;
- `cwd` exists and is a directory;
- event objects use only event types supported by `record_demo.py`;
- checkpoint times are non-negative and strictly less than recipe `recordSeconds`;
- checkpoint names are unique and path-safe;
- cumulative explicit wait seconds plus `EVENT_MARGIN_SECONDS` must be strictly less than `recording.recordSeconds`;
- recipes intended to leave the shell clean end with `ctrl-c` before recording ends;
- recipes that intentionally leave the process running set `leaveProcessRunning: true` and run only in explicit single-recipe/manual mode;
- publish paths are under the workspace `assets/demos/`;
- disabled recipes may omit binary paths only if they include a `disabledReason`.

## Error handling

For a single recipe:

- validation failure exits non-zero before recording;
- recorder failure exits non-zero and records the exception message plus stdout/stderr when the subprocess fallback path was used;
- missing GIF/raw output after a zero exit is treated as failure;
- checkpoint extraction failure is treated as failure;
- publish failure is treated as failure only during the separate `--publish-from-summary` path.

For `--all-enabled`, stop on the first failure in v1. This is safer while the matrix is young and demos touch shared desktop state.

## Testing strategy

Unit tests should cover the runner without invoking Ghostty or ffmpeg:

- parse matrix defaults and recipes;
- reject duplicate recipe ids;
- reject unknown recipe keys;
- reject enabled recipes with missing binaries;
- allow disabled placeholders with `disabledReason`;
- merge defaults into a valid `record_demo.py` config using the materialization contract;
- validate checkpoint bounds and unique checkpoint names;
- validate cumulative event timing;
- reject recording-time publish attempts;
- call/import the recorder through the execution contract without parsing CLI stdout;
- create a summary record from a fake recorder metadata JSON.

Integration tests should remain manual for v1 because screen recording and Ghostty focus require local desktop state.

## Documentation

Update `.development/demo-recorder/README.md` with:

- matrix list/run commands;
- the privacy preflight reminder;
- how to add a new recipe;
- which packages are intentionally skipped;
- how to inspect generated GIFs and checkpoint frames;
- how the separate reviewed publish-from-summary flow works;
- the Ghostty tty cleanup protocol.

## Definition of done for implementation

- `run_demo_matrix.py` exists under `.development/demo-recorder/`.
- `demo_matrix.json` contains the initial enabled recipes and disabled placeholders.
- Unit tests for matrix parsing/planning pass.
- `--list` reports all recipes and binary existence.
- `--dry-run --id hotrod-dragons-2.1.201-wrap-comparison` emits a valid generated recorder config.
- `--dry-run --id hidden-context-plus-hotrod-dragons-open-close` emits the proven open/close event sequence.
- Recording runs never copy public assets directly; `--publish-from-summary` handles one reviewed recipe at a time.
- A real run can generate at least the combined open/close GIF and checkpoint frames after the user confirms the screen is safe.
- No package schema, package payloads, source files, or build artifacts are modified.
