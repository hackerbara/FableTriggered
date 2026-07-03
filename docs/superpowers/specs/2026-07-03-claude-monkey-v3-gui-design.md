# ClaudeMonkey v3 GUI — Design

**Date:** 2026-07-03
**Status:** Draft for review (revised after adversarial sub-agent review)
**Supersedes:** the v2 rumps menu bar UI (merged in `1782e79`), and §16
(menu bar integration) + refresh-cadence decisions of
`2026-07-02-claude-monkey-v3-enhancements-design.md`.
**Depends on:** `2026-07-02-claude-monkey-v3-enhancements-design.md` §§2–15
(package model, option packages, unified storage, CLI surface, status schema).
That spec is **implementation phase 1** and needs its own plan; this GUI is
**phase 2** and builds against phase 1's final CLI surface.

## Goal

Replace the v2 rumps menu bar (menus + `rumps.alert()` dialog chains) with a
cross-platform-ready Qt UI, still written entirely in Python:

1. A **manager window** for settings and content management, complementing a
   slimmer tray menu.
2. A **single progress window** that owns each long-running operation —
   confirm, live stage progress, and result all in one window. No dialog
   parades.
3. A real **icon**: generated monochrome template glyph for the tray,
   full-color for the window.
4. Content installation: add/remove **patch, prompt, and option packages**
   from the UI via file pickers, backed by new kind-specific CLI commands.

## Decisions (from brainstorming)

| Decision | Choice |
|---|---|
| Window role | Complements the menu; quick actions stay in tray menu |
| Progress view | Stage checklist + collapsible live log, confirm/result in same window |
| Progress scope | Long ops only (build, install-shim, uninstall-shim); quick ops are silent |
| Long-op ownership | A progress window is **always** open and owns the op, regardless of trigger |
| Shim menu item | "Install shim…" appears in tray menu **only when shim is not installed**; uninstall lives only in the window |
| Icon | Generated monkey glyph: template PNG for tray, full-color for window/about |
| Toolkit | **PySide6 (Qt)** — replaces rumps; cross-platform (macOS menu bar + Windows tray) with one event loop |
| Add vs activate | Adding any package never activates/enables it; activation is a separate click |
| Sequencing | Package model (old V3 spec) implemented first; GUI targets its final CLI |

### Why PySide6

- Windows support is a real goal. `QSystemTrayIcon` + `QMainWindow` +
  progress widgets in one framework and one event loop on both platforms — no
  main-loop coexistence hacks (the failure mode of rumps+pywebview or
  rumps+Tk combinations).
- Still pure-Python source distribution: PySide6 ships prebuilt wheels from
  PyPI; `pip install` pulls compiled Qt per-platform. No build step in this
  repo, ever.
- LGPLv3 as a normal pip dependency imposes nothing on this project's license
  (PyQt6 is GPL-or-commercial; not used).
- Note: the **patching engine** (Mach-O, codesign, shim paths) remains
  macOS-only. Windows engine support is explicitly out of scope; this design
  only ensures the UI layer will not need a rewrite for it.

### macOS Dock-icon suppression (explicit)

Qt has no public API to hide a pip-installed console-script app from the
Dock/Cmd-Tab, and app bundling (which would allow `LSUIElement`) is out of
scope. The v2 code already solves this with a runtime AppKit call —
`NSApplication.setActivationPolicy_(NSApplicationActivationPolicyAccessory)`
(`menubar.py:294-310`). The Qt app keeps exactly that mechanism:
`gui/app.py` performs the same call at startup on macOS, wrapped in
try/except so a missing framework degrades to a visible Dock icon rather
than a crash. Consequently **`pyobjc-framework-Cocoa` remains a macOS-only
GUI dependency** (`; sys_platform == "darwin"` marker) — PySide6 replaces
rumps, not pyobjc. On Windows no equivalent is needed (tray apps have no
Dock analog).

## Architecture

One Qt process replaces the rumps process. `claude-monkey-menubar` entry
point (`pyproject.toml`) targets the new app. `menubar.py` (rumps rendering)
is deleted — it is a self-contained GUI process nobody imports. Its pure
helpers move as follows:

- `command_for_*` argv builders → `gui/commands.py` (rewritten for the
  phase-1 CLI surface).
- `build_menu_labels`, `patch_menu_label`, `install_target_menu_label`,
  `default_install_target`, install-target selection state →
  `gui/window_model.py`.
- `refuse_root_menu_process` → `gui/app.py` startup guard.
- `alert_for_result`, `AlertPlan`, `REBUILD_CONFIRMATION_BODY` are
  **retired, not ported** — the alert-plan mechanism is exactly the dialog
  parade this design eliminates; the progress window's confirm/result phases
  replace it.

### Survives (unchanged or extended)

- `menubar_state.py` — pure state parsing; extended for phase-1 status
  schema (options, risk warnings, compatibility dimensions).
- `menubar_install.py` — install planning.
- `menubar_commands.py` (`CommandRunner`) — survives; gains streaming
  (see Progress protocol).
- The single-mutating-command lock and root refusal.

### New package: `src/claude_monkey/gui/`

```
gui/
  app.py              # QApplication + tray + activation policy + wiring; entry point
  tray.py             # tray menu construction (thin, renders view-model)
  settings_window.py  # manager window (thin, renders view-model)
  progress_dialog.py  # confirm → progress → result, one window
  window_model.py     # pure view-models: menu/window composition, enable/check state
  progress_model.py   # pure state machine: stage events in → checklist state out
  commands.py         # pure argv builders
  icons.py            # loads generated assets, sets template/mask mode
```

Discipline mirrors v2: everything decidable is decided in pure-Python models
with unit tests; Qt files only render and forward clicks. The GUI never
touches managed files directly — every mutation goes through the CLI with
`--json`, keeping behavior contract-tested.

### Event flow

The v2 0.25s timer-drain poll is replaced by Qt signals. Worker threads run
commands via `CommandRunner`; a small `QObject` bridge emits signals
(queued connections, thread-safe) for results and progress events.

Refresh cadence (supersedes old-V3 §16's "no manual refresh"): refresh on
window/menu open, after every mutating command, and on a 10-minute timer —
**plus** a manual Refresh item kept as a visible escape hatch for stale
state.

### Dependencies

`[gui]` extra: `PySide6` + `pyobjc-framework-Cocoa ; sys_platform == "darwin"`
(rumps removed). `[dev]` gains `Pillow` and `pytest-qt`.

## Tray menu

```
ClaudeMonkey: active (v15)        ← status lines, disabled
Claude Code: 2.1.199
─────────────────────────
Open ClaudeMonkey…                ← raises the manager window (singleton)
─────────────────────────
Prompts        ▸                  ← quick activate toggles
Patches        ▸                  ← quick enable/disable toggles
Options        ▸                  ← quick enable/disable; high-risk → confirm dialog
Rebuild / Apply…                  ← opens progress window, which owns the op
Install shim…                     ← ONLY when shim not installed; opens progress flow
─────────────────────────
Refresh
Quit
```

- Leaves the menu (window-only): install target selection, uninstall shim,
  open report/logs/state folders, add/remove packages.
- Tray "Install shim…" opens the progress window pre-populated with the
  shared selected-target state held in `window_model.py` (initialized via
  `default_install_target`, edited on the window's Install page) — tray and
  window read the same model and cannot disagree.
- Patch items keep compatibility-aware enable/disable (v2
  `patch_menu_item_enabled` logic moves to `window_model.py`, shared by menu
  and window). Option items show a risk badge; enabling a
  `requiresConfirmation` option shows a confirm dialog, then calls
  `enable-option <id> --confirm --json`.
- While a long op runs: menu shows `Running: <name>`, mutating items disable
  — driven by the same shared model. The menu mirrors busy state; the
  progress window owns the op.

## Manager window

Singleton `QMainWindow`; sidebar navigation (list + stacked pages). Closing
the window never quits the app; the tray keeps running.

- **Overview** — status, Claude Code version, active prompt, active patch
  set, enabled options count + high-risk warnings, "Rebuild / Apply" button,
  last build summary + "Open report".
- **Patches** — table: checkbox, label, compatibility status/message (full
  text, no menu-label cramming). Toggle = `enable-patch`/`disable-patch`
  (quick op). "Add Patch Package…" and "Remove" (rules below).
- **Prompts** — list, "none" first, radio behavior; source shown. Clicking
  activates (`set-prompt <id> --json`). "Add Prompt…" adds without
  activating.
- **Options** — table: checkbox, label, risk badge, compatibility.
  Toggle = `enable-option`/`disable-option`; `requiresConfirmation` options
  confirm first, then `--confirm`. "Add Option Package…" and "Remove".
- **Install** — install target picker (`install_target_choices` + real
  file-browse button, replacing the clipboard hack), shim status
  ("Installed at <path>" / "Not installed"), Install/Uninstall buttons →
  progress flow.
- **Logs & Reports** — open build report / logs folder / state folder;
  read-only tail of the GUI log (filename stays `menubar.log` for
  continuity with existing logs and tooling; the name is historical, kept
  deliberately).

Quick-op failures render as a dismissible inline banner in the relevant page
(no modals) and log to `menubar.log`.

## Content installation

Storage and validation follow the phase-1 package model: everything lives
under `~/.claude-monkey/{patches,prompts,options}/<id>/` with the common
manifest envelope (old-V3 §§2–3). `~/.claude-patches` does not appear in
this design.

New kind-specific CLI commands (matching phase 1's kind-specific
convention):

- **`add-patch <dir> --json`**, **`add-option <dir> --json`**,
  **`add-prompt <path> --json`** — validate **before** copy: manifest
  parses, `kind` matches, payload/source files exist, package-local path
  rules hold (old-V3 §3.1). Destination directory is
  `~/.claude-monkey/<kind-bucket>/<manifest.id>` — **the manifest `id` is
  authoritative**; if the source folder's basename differs, the copy is
  renamed to `manifest.id` and the result payload carries a warning. The
  collision check runs against discovered ids of the same kind. Adding never
  activates or enables anything.
  - `add-prompt` also accepts a bare `.md`/text file and scaffolds a minimal
    prompt package around it (id derived from filename, `mode: append`,
    overridable via `--id`/`--name`), so users don't hand-write manifests
    for the common case.
- **`remove-patch <id>`**, **`remove-prompt <id>`**,
  **`remove-option <id>`** (`--json`) — only for packages under
  `~/.claude-monkey`; refusal rule is **profile-referenced, not
  build-referenced**: refuse iff the id is referenced by the active launch
  profile (`id in desiredPatchIds`, or it is the active prompt, or it is in
  the enabled options list). A patch that is still baked into the current
  binary (`activePatchIds`) but no longer desired **may** be removed — the
  built binary is a static artifact; the protection exists to keep the
  *next* build/launch from failing on a missing package.

UI: "Add …" opens a folder picker (file picker for bare prompt files);
"Remove" enables per the rule above, with the refusal reason shown inline
when disabled. Add/remove are quick ops: inline banner on failure, list
refresh on success.

## Progress window + CLI progress protocol

### Producer-side design (the part that needs real refactoring)

Progress events must be **produced** by code that is a single monolithic
function today. This is deliberate new design, not instrumentation of
existing seams:

- **Builder:** `BuildRequestV15` gains an optional
  `on_event: Callable[[ProgressEvent], None]` (default `None` → zero
  behavior change). `build_patchset_v15` calls it at real transition points.
  The stage table is a module-level constant in `builder_v15.py` — the
  single source of truth the CLI uses to emit the `plan` event, so the GUI
  checklist can never drift from the builder. Stages follow the **actual
  execution order** of `build_patchset_v15` (source read → patch/module
  resolution with interleaved assertions → repack+write → sign → post-sign
  inspection → smoke → activate):

  `resolve` → `repack` → `sign` → `inspect` → `smoke` → `activate`

  (No fictitious "copy" stage; verification that happens inside patch
  resolution is part of `resolve`; `inspect` is the post-sign inspection,
  which genuinely runs *after* signing.)
- **Shim transactions:** `install_shim_transaction` /
  `restore_install_transaction` gain the same optional `on_event` and emit
  three stages: `preflight` → `record` → `swap`. Today's CLI `--dry-run`
  `plannedActions` is a single-element human-readable list and is **not** a
  stage source; it remains confirm-phase display text only.

### CLI protocol

`build`, `install-shim`, `uninstall-shim` gain `--progress`. With the flag,
the command emits one JSON object per line on **stderr** as it runs. The
final result JSON on **stdout** is byte-identical to today — existing
contract tests pass untouched. Because v2's `run_json` already treats stderr
purely as an error-text fallback when stdout parses, mixed human-readable
stderr prints remain harmless; the streaming reader treats unparseable lines
as raw log lines.

```json
{"event":"plan","stages":[{"id":"resolve","label":"Resolve patches"},{"id":"repack","label":"Repack binary"}]}
{"event":"stage","id":"resolve","status":"running"}
{"event":"stage","id":"resolve","status":"done"}
{"event":"log","stage":"smoke","line":"smoke: version output ok"}
{"event":"stage","id":"smoke","status":"failed","message":"smoke test exited 1"}
```

- `plan` first; the GUI renders the stage list from it — no hardcoded stage
  names in the GUI.
- Stage `status` values: `running`, `done`, `failed`, `skipped`.

### Window flow (one window, three phases in place)

1. **Confirm** — shows what will happen (dry-run output for shim ops; patch
   set for rebuild) + primary action button + Cancel. Replaces pre-flight
   alerts.
2. **Running** — checklist from `plan`, spinner on the running stage,
   collapsible details pane streaming `log` lines.
3. **Result** — success summary, or the failed stage highlighted with its
   message; contextual buttons (Open report / Open logs). Window persists
   until closed. No follow-on alerts, ever.

### Cancel semantics (explicit)

- `run_streaming` launches the CLI with `start_new_session=True`; Cancel
  sends `SIGTERM` to the **process group** (`os.killpg`), escalating to
  `SIGKILL` after a grace timeout — so nested children (codesign, smoke-test
  claude process) die with the parent.
- **Build:** cancel-safe at every stage — activation is the final atomic
  step; a killed build leaves at worst an unactivated partial artifact
  directory that the next build overwrites.
- **Shim install/uninstall on an authorization-required target:** the
  privileged path blocks on an OS authorization prompt
  (`authorization.py:59-88`, osascript) and a kill mid-`swap` would bypass
  the transaction's own exception cleanup. Therefore **Cancel is disabled
  for the entire duration of an authorization-required transaction**, not
  just the swap instant. For user-writable targets, Cancel stays enabled
  through `preflight`/`record` and disables at `swap`.

### Plumbing

`CommandRunner.run_streaming(name, args)` — `Popen`
(`start_new_session=True`), a reader thread on stderr parsing JSONL, posting
events via the Qt signal bridge. Unparseable lines pass through as raw log
lines (stray prints cannot crash the stream). `progress_model.py` is a pure
state machine, unit-testable without Qt or subprocesses.

## Icon

`scripts/generate_icons.py` (Pillow, in `[dev]`) generates committed assets:

- **Tray:** monochrome monkey-face glyph, 18×18 + 36×36 (@2x) PNG.
  Qt `QIcon.setIsMask(True)` → macOS template behavior (auto light/dark);
  same glyph renders as-is in the Windows tray.
- **Window/About:** full-color 128/256/512.

Generated output is deterministic and committed; end users never need
Pillow.

## Error handling

- Unparseable progress line → raw log line (never crashes the stream).
- Command dies with no final stdout JSON → progress window marks the last
  running stage failed, shows captured stderr tail; same synthetic-error
  payload shape `CommandRunner.run_json` builds today.
- State refresh failure → window shows disconnected banner + Retry; tray
  falls back to minimal error menu (ported `render_error_menu` behavior).
- Quick-op failure → inline banner, dismissible, logged.
- Root refusal and single-instance guard enforced at startup. (v2 has no
  single-instance mechanism — this is **new**: a `QLocalServer` named socket;
  a second launch messages the first to raise its window and exits.)

## Testing

- **Pure models** (`progress_model`, `window_model`, `commands`) — unit
  tests, no Qt. From `test_menubar_app_model.py`: tests for
  `build_menu_labels` / `patch_menu_label` / `install_target_menu_label` /
  `default_install_target` / `command_for_*` port to the new model modules;
  tests for `alert_for_result` / `AlertPlan` / `REBUILD_CONFIRMATION_BODY`
  are **retired with the mechanism** they exercise.
- **CLI contracts** — `add-*`/`remove-*` commands and the `--progress`
  event stream get contract tests in the `test_cli_json_contracts.py` style,
  including "stdout byte-identical when `--progress` is on" and "plan event
  matches the builder stage table".
- **Builder/transaction instrumentation** — unit tests that `on_event`
  fires in stage-table order on success, emits `failed` with the right stage
  on each induced failure class, and that `on_event=None` changes nothing.
- **Qt layer** — `pytest-qt` on `QT_QPA_PLATFORM=offscreen` (CI-safe):
  window constructs, pages populate from fake state, progress dialog
  transitions phases from synthetic events.
- **`run_streaming`** — fake subprocess emitting event lines mixed with
  garbage lines; process-group kill behavior.

## Out of scope

- Windows patching engine (PE, signing, shim paths) — separate future spec.
- App bundling (PyInstaller/Briefcase) — pip source install remains primary.
- Add-and-activate-in-one-step UI affordances.
- Linux tray support (Qt makes it likely-cheap, but untested/unclaimed
  here).
- Package-model implementation itself — that is phase 1, specified in
  `2026-07-02-claude-monkey-v3-enhancements-design.md`.
