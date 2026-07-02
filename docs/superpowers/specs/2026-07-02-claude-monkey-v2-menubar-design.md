# ClaudeMonkey v2 menu bar design and runbook

Date: 2026-07-02
Status: approved design direction; adversarial review fixes incorporated; implementation not started
Project: ClaudeMonkey
Scope: v2 fast-follow menu bar companion after the v1 Python CLI/core lands

## 1. Product position

ClaudeMonkey v2 is a thin, optional macOS menu bar companion over the v1 Python CLI/core. It is not a second patch manager and must not duplicate binary-patching, prompt-injection, signing, shim, or manifest logic.

The v2 app exists to make the common safe operations visible and quick:

- See current ClaudeMonkey status.
- Pick the active prompt profile.
- Toggle desired patch state.
- Rebuild/apply staged patch changes with confirmation.
- Install or uninstall the managed shim.
- Open logs, state folders, and build reports.

The implementation should optimize for source-first local utility, not polished app distribution. A developer/user should be able to run it from source while v1 continues to own the real product spine.

## 2. V1 contracts v2 depends on

V2 assumes v1 has landed these stable CLI/core behaviors:

- State directory: `~/.claude-monkey/`.
- Patch package directory: `~/.claude-patches/`.
- Active profile state in `~/.claude-monkey/config.json`.
- Default install mode is a managed `claude` shim plus copied patched binary symlink.
- The official Claude binary is never mutated in the normal path.
- `enable` and `disable` mutate desired patch state and imply rebuild-required when desired state differs from active build state.
- `set-prompt` and `clear-prompt` update prompt config and take effect on the next Claude launch.
- `build` creates a copied patched binary, verifies/signs/smokes it, writes `build-report.json`, and activates `~/.claude-monkey/current` only on success.
- `install-shim` and `uninstall-shim` own shim installation/removal and handle rollback.

V2 should ask v1 for machine-readable state. If v1 does not already expose these commands, v2 implementation should add them before building the UI:

```bash
claude-monkey status --json
claude-monkey list-patches --json
claude-monkey list-prompts --json
claude-monkey enable <patch-id> --json
claude-monkey disable <patch-id> --json
claude-monkey set-prompt <prompt-id> --json
claude-monkey clear-prompt --json
claude-monkey build --json
claude-monkey build --json --dry-run
claude-monkey install-shim --json
claude-monkey install-shim --json --dry-run
claude-monkey uninstall-shim --json
claude-monkey uninstall-shim --json --dry-run
```

The menu bar may tolerate early text output during a spike, but the implementation plan should treat JSON CLI output as a required seam before a usable MVP.

### Minimal JSON contracts

The exact v1 implementation can add fields, but v2 needs these minimum shapes before any `rumps` UI code depends on them.

`claude-monkey status --json`:

```json
{
  "schemaVersion": 1,
  "status": "rebuild_required",
  "sourceClaudeVersion": "2.1.198",
  "sourceClaudePath": "/path/to/official/claude",
  "installMode": "shim",
  "shimInstalled": true,
  "activeProfile": "default",
  "activePrompt": "research",
  "desiredPatchIds": ["fable-fallback", "reminder-suppression"],
  "activePatchIds": ["fable-fallback"],
  "rebuildRequired": true,
  "latestBuildReportPath": "/Users/example/.claude-monkey/versions/2.1.198/patchsets/example/build-report.json",
  "stateDir": "/Users/example/.claude-monkey",
  "logsDir": "/Users/example/.claude-monkey/logs",
  "lastError": null
}
```

Allowed `status` values:

```text
ok
rebuild_required
error
not_installed
unknown
```

Status precedence:

```text
error > not_installed > rebuild_required > ok > unknown
```

If `rebuildRequired` is true and no higher-priority state applies, `status` should be `rebuild_required`. V2 may recompute that precedence defensively, but v1 should emit a non-contradictory status.

`unknown` is not a competing positive state. Use it only when v1 or v2 cannot classify the state.

`lastError` must use the same shape as command-envelope `error`: either `null` or `{"message": string, "code": string | null}`.

`claude-monkey list-patches --json`:

```json
{
  "schemaVersion": 1,
  "patches": [
    {
      "id": "fable-fallback",
      "label": "Fable fallback visibility",
      "desiredEnabled": true,
      "activeEnabled": true,
      "available": true,
      "compatibilityStatus": "compatible"
    }
  ]
}
```

Allowed `compatibilityStatus` values:

```text
compatible
version_mismatch
sha_mismatch
conflict
unknown
```

`claude-monkey list-prompts --json`:

```json
{
  "schemaVersion": 1,
  "prompts": [
    {
      "id": "research",
      "label": "Research",
      "active": true,
      "mode": "append",
      "sourcePath": "/Users/example/.claude-monkey/prompts/research.md"
    }
  ]
}
```

Mutating commands such as `enable --json`, `disable --json`, `set-prompt --json`, `clear-prompt --json`, `build --json`, `install-shim --json`, and `uninstall-shim --json` should return a command result envelope:

```json
{
  "schemaVersion": 1,
  "ok": true,
  "status": "ok",
  "summary": "Build activated",
  "reportPath": "/Users/example/.claude-monkey/versions/2.1.198/patchsets/example/build-report.json",
  "dryRun": false,
  "plannedActions": [],
  "error": null
}
```

`error` must be either `null` or this object shape:

```json
{
  "message": "Short human-readable failure",
  "code": "optional_machine_code"
}
```

Envelope invariants:

- `ok: true` requires `error: null`.
- `ok: false` requires `error.message` to be a non-empty string. `error.code` may be `null`.
- `reportPath` is optional and may be `null`; it is primarily meaningful for build/build-like failures. V2 should refresh state and use `status.latestBuildReportPath` for persistent report discovery.
- `dryRun` is required for `build`, `install-shim`, and `uninstall-shim` result envelopes; it should be `true` when the command was invoked with `--dry-run`, otherwise `false`.
- `plannedActions` is required for `--dry-run` result envelopes and should list concise strings for the changes that would have happened. It may be an empty list for non-dry-run or simple config mutations.

If `ok` is `false`, V2 should display `error.message` and offer logs/report access rather than trying to interpret every builder failure. `error.code` is for tests, logs, and future branching.

Dry-run semantics for `build`, `install-shim`, and `uninstall-shim`:

- Must not activate a build, install a shim, uninstall a shim, alter symlinks, or write protected locations.
- Must return the same result envelope shape as the real command.
- Must set `dryRun: true`.
- Must include `plannedActions`, even if the result is a failure discovered during preflight.
- May write temporary diagnostic data under the active state directory only if v1 already treats that as safe diagnostic output; it must not change active profile, active patch set, current symlink, or shim install state.

## 3. Chosen implementation approach

Use `rumps` for the v2 MVP.

Rationale:

- `rumps` is designed for simple macOS status bar apps that control console programs or launch separate commands.
- It can create a real menu bar app with a proper icon while keeping the implementation in Python.
- It exposes menu items, checked states, alerts, notifications, and timers without direct PyObjC ceremony.
- It keeps the app source-first and thin over the v1 Python CLI/core.

Fallback:

- If `rumps` proves too brittle on current macOS/Python, fall back to a direct PyObjC `NSStatusItem` implementation.
- Swift/AppKit is a later fallback only if Python menu bar approaches fail. Even in Swift, the app must still shell out to the CLI/core rather than reimplementing product logic.

## 4. Menu bar icon requirements

The v2 app should be an icon-only menu bar item, not a text title.

Required asset:

```text
assets/claude-monkey-menubar-template.png
```

Recommended optional state variants:

```text
assets/claude-monkey-menubar-template.png          # normal / OK
assets/claude-monkey-menubar-dirty-template.png    # rebuild required
assets/claude-monkey-menubar-error-template.png    # last refresh or command failed
```

Icon rules:

- Use a monochrome template-style PNG suitable for macOS menu bars.
- Configure template mode so the icon adapts to light and dark menu bars.
- Keep the status item icon-only; do not show persistent text like `ClaudeMonkey` in the menu bar.
- Communicate detailed state inside the opened menu, not in the menu bar title.
- If state-specific icon variants are not ready for the first spike, ship one template icon and represent OK/rebuild/error in the top status menu item.

Visual direction:

- A small monkey head, monkey face, or monkey/wrench silhouette is enough.
- The icon should be legible at menu bar size before it is cute.
- Do not spend v2 time on a full app icon set unless packaging becomes part of the task.

`rumps` wiring requirement:

```python
app = rumps.App(
    name="ClaudeMonkey",
    title=None,
    icon=str(icon_path),
    template=True,
    quit_button=None,
)
```

The implementation can wrap this in a class, but the visible status item should be icon-only. If `title=None` falls back to text in the installed `rumps` version, use the nearest supported `rumps` pattern that leaves no persistent `ClaudeMonkey` text in the menu bar and keep the manual smoke test for that behavior.

Because `quit_button=None` disables the default rumps quit item, the explicit `Quit` menu item must call `rumps.quit_application()`.

## 5. MVP menu structure

Target menu with example values shown:

```text
[icon-only status item]
────────────────
ClaudeMonkey: <OK / Rebuild Required / Error>
Claude Code: <version>
Prompt: <prompt-id or none>
Patches: <enabled-count> enabled
────────────────
Prompts
  ✓ research
    default
    none
────────────────
Patches
  ✓ fable-fallback
  ✓ reminder-suppression
────────────────
Rebuild / Apply…
Install shim…
Uninstall shim…
Open build report
Open logs folder
Open state folder
Refresh
Quit
```

Notes:

- The first four lines are status/readout items. They can be disabled menu items.
- `Prompts` is a submenu populated from `list-prompts --json`.
- `Patches` is a submenu populated from `list-patches --json`.
- Prompt and patch items should use checked state rather than duplicating the current value in labels.
- `Rebuild / Apply…` should remain visible in all states. When no rebuild is required, it can still allow a deliberate rebuild; when rebuild is required, it is the primary call to action.
- `Open build report` should open the latest active or failed report if one exists; otherwise it should show a small alert.
- `Open logs folder` should reveal `~/.claude-monkey/logs/` in Finder, creating it if the menu bar log path is initialized.
- `Open state folder` should reveal `~/.claude-monkey/` in Finder.

## 6. Data flow

The menu bar app maintains an in-memory `MenuState` derived entirely from v1 CLI JSON output.

Suggested state fields:

```json
{
  "status": "ok | rebuild_required | error | not_installed | unknown",
  "sourceClaudeVersion": "2.1.198",
  "sourceClaudePath": "/path/to/official/claude",
  "installMode": "shim",
  "shimInstalled": true,
  "activeProfile": "default",
  "activePrompt": "research",
  "desiredPatchIds": ["fable-fallback", "reminder-suppression"],
  "activePatchIds": ["fable-fallback"],
  "rebuildRequired": true,
  "latestBuildReportPath": "/Users/.../.claude-monkey/.../build-report.json",
  "lastError": null
}
```

The exact JSON shape can differ if v1 already has a better model. The invariant is that v2 should consume one clear state object and should not infer active patch state by scraping filenames or symlinks when the CLI can report it.

Refresh flow:

```text
menu opens or Refresh clicked
  -> run claude-monkey status --json
  -> run list-patches --json and list-prompts --json if not included in status
  -> build MenuState
  -> rebuild rumps menu
  -> update icon variant
```

Command flow:

```text
user clicks menu item
  -> confirm if action is destructive/protected/slow
  -> enqueue one claude-monkey command through the serialized command runner
  -> capture stdout, stderr, exit code
  -> refresh MenuState
  -> show alert only for failures, protected operations, or build summaries
```

Command runner constraints:

- Use argv-list subprocess calls with `shell=False`; never concatenate patch IDs, prompt IDs, or paths into shell strings.
- Bound captured stdout and stderr in memory and logs. The UI needs concise summaries, not unbounded process output.
- Serialize mutating commands. Only one of `enable`, `disable`, `set-prompt`, `clear-prompt`, `build`, `install-shim`, or `uninstall-shim` may run at a time.
- Run slow commands such as `build`, `install-shim`, and `uninstall-shim` off the `rumps` menu callback path so the menu bar app does not freeze.
- Worker threads may run subprocesses and write command results to a queue, but menu mutation, icon updates, and alerts must happen through a `rumps`/AppKit-safe app-loop handoff. A simple implementation can use a short-interval `rumps.Timer` to drain the result queue and update UI from the app loop.
- The worker result queue should be a testable boundary: worker code posts command results only; the app-loop drain method mutates `MenuState`, menu items, icons, and alerts.
- While a slow command is running, disable other mutating menu items, show a busy/running status item inside the menu, and refresh state after completion.
- Keep read-only refresh commands safe to run on demand, but avoid overlapping refreshes with mutating command completion refreshes.

## 7. Action behavior

### Prompt picker

Clicking a prompt profile calls:

```bash
claude-monkey set-prompt <prompt-id> --json
```

Clicking `none` calls:

```bash
claude-monkey clear-prompt --json
```

Expected UX:

- Update checkmark immediately after a successful refresh.
- Show a small informational alert or notification: `Prompt will apply on next Claude launch.`
- Do not rebuild binary patchsets for prompt-only changes.
- V2 only passes prompt IDs returned by `list-prompts --json`; arbitrary prompt paths remain CLI-only and are not part of the v2 menu MVP.

### Patch enable/disable submenu

Clicking a patch calls one of:

```bash
claude-monkey enable <patch-id> --json
claude-monkey disable <patch-id> --json
```

Expected UX:

- Treat this as desired-state staging only.
- Do not auto-build after a toggle.
- Refresh menu state and show rebuild-required state.
- Keep toggles fast and reversible until `Rebuild / Apply…` is clicked.

### Rebuild / Apply

Clicking `Rebuild / Apply…` should show a confirmation dialog.

Minimum confirmation copy:

```text
Rebuild ClaudeMonkey patched binary?

This will build a copied Claude Code binary from the selected patches, verify it, sign it, smoke-test it, and activate it only if the build succeeds. The official Claude binary will not be modified.
```

If confirmed:

```bash
claude-monkey build --json
```

Expected UX:

- Show a running/busy menu state.
- Disable other mutating menu items while build is running.
- On success, show summary with active patch set and report path.
- On failure, show error summary and offer to open the build report/log.
- Never activate a failed build in the UI. Activation is solely v1 builder responsibility.

### Install/uninstall shim

Clicking install or uninstall should show confirmation because it changes the user's `claude` command path.

Commands:

```bash
claude-monkey install-shim --json
claude-monkey uninstall-shim --json
```

Permissions rules:

- Do not run the menu bar process as root.
- Prefer user-writable shim locations for the MVP.
- If v1 needs elevation for a protected install/restore operation, v2 should call a narrow v1 elevation path for that operation only.
- V2 should display v1's authorization prompt/result rather than inventing a second permissions model.

### Open report, logs, and folders

Use macOS `open` through argv-list subprocess calls. Expand paths before invoking `open`; with `shell=False`, `~` will not expand. Prefer `stateDir`, `logsDir`, and `latestBuildReportPath` from `status --json`.

```bash
open "$LATEST_BUILD_REPORT_PATH"
open "$LOGS_DIR"
open "$STATE_DIR"
```

If the latest report path is missing, show an alert instead of failing silently.

If the logs directory is missing, create `~/.claude-monkey/logs/` when the menu bar logger initializes. If creation fails, show an alert with the path and keep `Open state folder` available.

## 8. Error handling

V2 should make errors visible but not scary unless safety is at risk.

Error categories:

- CLI missing or import failure.
- State JSON parse failure.
- Patch list/prompt list unavailable.
- Build failed.
- Shim install/uninstall failed.
- Permission denied.
- No active build report.
- Logs directory unavailable.

Error UI rules:

- Set top status line to `ClaudeMonkey: Error`.
- Use the error icon variant if available.
- Preserve the last known good menu where possible, but mark it stale.
- Include `Open state folder` and `Refresh` even in error state.
- Include `Open logs folder` when the logs directory exists or can be created.
- Show concise alerts for command failures with an option/path to inspect logs or reports.
- Do not hide rebuild-required or failed-build states behind a green-looking icon.

## 9. Logging

V2 should write a small menu bar log only for UI/command-runner events, not duplicate build reports.

Suggested path:

```text
~/.claude-monkey/logs/menubar.log
```

Log entries should include:

- timestamp
- command name and argv without secrets
- exit code
- short stderr summary
- state refresh failures

The build pipeline's authoritative evidence remains `build-report.json` from v1.

The menu should expose `Open logs folder` as a first-class action. The logs folder is for menu bar command-runner evidence and UI failures; it is not a replacement for build reports.

## 10. Packaging and launch stance

V2 MVP source run command:

```bash
python3 -m claude_monkey.menubar
```

Recommended dependencies once implementation begins:

```text
rumps
PyObjC, as required by rumps on modern Python environments
```

Packaging is not required for the first MVP. If packaging becomes necessary, use `py2app` with `LSUIElement=True` so ClaudeMonkey behaves as a background menu bar utility without a Dock icon.

Do not build login-item automation in v2 unless explicitly requested. A manual launch command is enough for the fast-follow MVP.

## 11. Testing and verification plan

Unit tests should cover the non-UI boundaries first:

- V1 JSON contract parsing for `status`, `list-patches`, `list-prompts`, and command result envelopes.
- CLI JSON parsing into `MenuState`.
- Menu state derivation: OK, rebuild-required, error, not-installed.
- Prompt click maps to the correct CLI command.
- Patch click maps to `enable` or `disable`, not `build`.
- Rebuild confirmation maps to `build --json`.
- Open report handles missing report paths.
- Open logs folder uses the logs directory, not the build report path.
- Command failures preserve enough stderr for the user.
- Mutating command runner serializes commands and refuses concurrent mutation.
- Slow command execution does not run directly on the menu callback path.
- Worker code posts results to a queue, and only the app-loop drain path mutates menu state, menu items, icons, or alerts.
- Subprocess calls use argv lists with `shell=False`.

Manual smoke tests on macOS:

1. Run the V1 contract acceptance checklist below.
2. Launch from source with the icon asset present.
3. Verify the menu bar shows an icon only, not text.
4. Verify the icon is visible in light and dark menu bar appearances.
5. Toggle a patch and confirm the menu shows rebuild-required without building.
6. Click `Rebuild / Apply…`, cancel, and confirm no command runs.
7. Click `Rebuild / Apply…`, confirm, and verify v1 handles build/activation.
8. Select a prompt and verify the menu says it applies on next Claude launch.
9. Open the build report, logs folder, and state folder.
10. Simulate CLI failure and verify the menu enters error state with Refresh and logs access still available.

V1 contract acceptance checklist before any menu UI work:

Use one disposable fixture environment for all config-mutating contract checks. Seed or point that fixture at known patch packages and prompt profiles, then run `list-patches` and `list-prompts` in the same fixture before selecting IDs for mutation commands. Do not mutate the user's real active profile just to prove the menu contract.

```bash
TMP_HOME="$(mktemp -d)"
mkdir -p "$TMP_HOME/.claude-patches" "$TMP_HOME/.claude-monkey/prompts"
# Seed or symlink known fixture patch packages into "$TMP_HOME/.claude-patches".
# Seed or write at least one known prompt profile under "$TMP_HOME/.claude-monkey/prompts".
HOME="$TMP_HOME" claude-monkey status --json
HOME="$TMP_HOME" claude-monkey list-patches --json
HOME="$TMP_HOME" claude-monkey list-prompts --json
HOME="$TMP_HOME" claude-monkey enable <known-patch-id-from-fixture-list> --json
HOME="$TMP_HOME" claude-monkey disable <known-patch-id-from-fixture-list> --json
HOME="$TMP_HOME" claude-monkey set-prompt <known-prompt-id-from-fixture-list> --json
HOME="$TMP_HOME" claude-monkey clear-prompt --json
claude-monkey build --json --dry-run
claude-monkey install-shim --json --dry-run
claude-monkey uninstall-shim --json --dry-run
```

Acceptance criteria:

- Each command exits successfully in a normal configured environment, except the `HOME="$TMP_HOME" ...` commands use disposable fixture state and the build/install commands must use dry-run if a real mutation would be unsafe during contract testing.
- JSON parses without fallback text scraping.
- Status output includes state directory, logs directory, prompt state, desired patch state, active patch state, rebuild-required state, and latest report path if one exists.
- Patch output includes every patch ID, display label, desired enabled state, active enabled state, availability, and compatibility status.
- Prompt output includes every prompt ID, display label, active state, mode, and source path.
- Command result envelopes for all mutating commands consistently expose `ok`, `summary`, and `error`, where `error` is either `null` or an object with `message` and `code`.
- Dry-run result envelopes expose `dryRun: true` and `plannedActions`.
- The CLI/core, not the menu bar app, owns all config mutation, build activation, shim installation, authorization, and rollback behavior.

## 12. Non-goals for v2

V2 should not include:

- Version drift automation.
- Candidate compatibility builds beyond what v1 already exposes.
- A full Preferences window.
- Patch manifest editing.
- Prompt file editing.
- Remote patch registry browsing.
- Auto-update.
- Login item management.
- Swift rewrite.
- Full app packaging or notarization.
- Any direct byte editing, signing, or activation logic in the menu bar layer.

## 13. Implementation sequence after v1 lands

1. Pass the V1 contract acceptance checklist with real JSON output or add the missing v1 JSON seams first.
2. Add the menu bar icon asset under `assets/`.
3. Add `claude_monkey.menubar_state` for parsing JSON and deriving UI state.
4. Add `claude_monkey.menubar_commands` for safe argv-list subprocess execution, serialization, background slow-command handling, and menu bar logging.
5. Add `claude_monkey.menubar` as the `rumps` app entrypoint with icon-only status item wiring.
6. Build the static menu with status, prompt, patch, rebuild, install/uninstall, open report, open logs, open state folder, refresh, and quit items.
7. Wire prompt and patch clicks to CLI commands.
8. Wire rebuild/install/uninstall confirmation flows.
9. Add unit tests for state, command mapping, command serialization, safe subprocess invocation, and logs/report open behavior.
10. Run the manual macOS smoke checklist.

Stop after a working source-run menu bar MVP. Do not expand into packaging polish until the thin companion proves useful.
