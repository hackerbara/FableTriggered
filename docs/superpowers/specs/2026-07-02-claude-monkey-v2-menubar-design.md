# ClaudeMonkey v2 menu bar design and runbook

Date: 2026-07-02
Status: approved full V2 design direction on current main; implementation not started
Project: ClaudeMonkey
Scope: full V2 macOS menu bar companion on current main

## 1. Product position

ClaudeMonkey v2 is a full macOS menu bar companion over the Python CLI/core. It is not a second patch manager and must not duplicate binary-patching, prompt-injection, signing, shim, manifest, Bun graph, or repack logic.

The V2 app exists to make the common safe operations visible and quick:

- See current ClaudeMonkey status.
- Pick the active prompt profile.
- Toggle desired patch state.
- Rebuild/apply staged patch changes with confirmation.
- Install or uninstall the managed shim.
- Handle protected-path install/restore through a narrow elevation flow.
- Open logs, state folders, and build reports.

The implementation should optimize for a proper source-first macOS utility: real menu-bar icon, complete status/actions, protected-path UX, and clear recovery paths. It does not need notarized distribution to be V2, but core install/permissions behavior is part of V2.

Current main is the build-mechanism baseline. V2 is a UI/control surface over that baseline. V2 calls the CLI and reads JSON status/reports; it must never parse Bun graphs, patch binaries, or know module-coordinate patching details.

## 2. CLI/core contracts V2 depends on

Current main includes the Bun graph-aware repack path as the internal build mechanism. V2 depends only on these strategy-agnostic CLI/core behaviors:

- State directory: `~/.claude-monkey/`.
- Patch package directory: `~/.claude-patches/`.
- Active profile state in `~/.claude-monkey/config.json`.
- Default install mode is a managed `claude` shim plus copied patched binary/current symlink.
- The official Claude binary is never mutated in the normal path.
- `enable` and `disable` mutate desired patch state and imply rebuild-required when desired state differs from active build state.
- `set-prompt` and `clear-prompt` update prompt config and take effect on the next Claude launch.
- `build` creates a copied patched binary through whatever current build strategy the CLI/core owns, verifies/signs/smokes it, writes `build-report.json`, and activates `~/.claude-monkey/current` only on success.
- `install-shim` and `uninstall-shim` own shim installation/removal and handle rollback.

V2 must not branch on whether a build used `slot`, `repack`, `auto`, or another future strategy. It may display strategy details if the CLI/report provides them, but build success, active patches, rebuild-required, and errors come from generic status/report fields.

V2 should ask the CLI/core for machine-readable state. If the current CLI/core does not already expose these commands, V2 implementation should add them before building the UI:

```bash
claude-monkey status --json
claude-monkey list-patches --json
claude-monkey list-prompts --json
claude-monkey enable <patch-id> --json
claude-monkey disable <patch-id> --json
claude-monkey set-prompt <source-path-or-content> --id <prompt-id> --from-file --json
claude-monkey clear-prompt --json
claude-monkey build --json
claude-monkey build --json --dry-run
claude-monkey install-shim --target <selected-target> --json
claude-monkey install-shim --target <selected-target> --json --dry-run
claude-monkey uninstall-shim --target <selected-target> --json
claude-monkey uninstall-shim --target <selected-target> --json --dry-run
claude-monkey uninstall-shim --record <install-record> --json
claude-monkey uninstall-shim --record <install-record> --json --dry-run
```

The implementation plan should treat JSON CLI output as a required seam before V2 is usable. JSON mode is additive: existing human CLI output and tests must keep working unless a separately tested migration explicitly changes them.

V2 must augment the current parser and handlers. It must not replace rich existing flags or simplify behavior for `build`, `set-prompt`, `install-shim`, `uninstall-shim`, `rollback`, or `use-official`.

### Required JSON contracts

The exact CLI/core implementation can add fields, but V2 needs these required shapes before any `rumps` UI code depends on them.

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
  "activePatchSet": "/Users/example/.claude-monkey/patchsets/2.1.198/default",
  "currentClaudePath": "/Users/example/.claude-monkey/current",
  "shimTargetPath": "/usr/local/bin/claude",
  "installRecordPath": "/Users/example/.claude-monkey/shims/usr-local-bin-claude.json",
  "buildStrategy": "repack",
  "lastBuildStrategy": "repack",
  "changedModules": [],
  "repackSummary": null,
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

If `rebuildRequired` is true and no higher-priority state applies, `status` should be `rebuild_required`. V2 may recompute that precedence defensively, but the CLI/core should emit a non-contradictory status.

`unknown` is not a competing positive state. Use it only when the CLI/core or menu cannot classify the state.

`lastError` must use the same shape as command-envelope `error`: either `null` or `{"message": string, "code": string | null}`.

Status must derive active state from `config.activePatchSet` and the latest available `build-report.json` when present:

- `desiredPatchIds` comes from the active profile's enabled patch IDs.
- `activePatchIds` comes from the active build report's enabled patches, changed patch IDs, or equivalent strategy-agnostic field.
- `activePatchSet` mirrors the active configured patch-set path or identifier.
- `latestBuildReportPath` points at the active/latest report used for active-state derivation when available.
- `currentClaudePath` points at the CLI/core's current executable or symlink target when known.
- `shimTargetPath` points at the active/recorded shim target when known.
- `installRecordPath` points at the CLI/core install record used for restore/uninstall when known.
- `rebuildRequired` is true when desired patch IDs, prompt/build-relevant state, source identity, or current build report state differ enough that the CLI/core would require a rebuild.

The menu bar must not treat `activePatchIds: []` as a harmless placeholder. Empty active patches mean either a real active build with no patches, no active build, or a status error; `status`, `activePatchSet`, `latestBuildReportPath`, and `lastError` must disambiguate.

Strategy/repack fields are optional and forward-compatible:

```json
{
  "buildStrategy": "slot | repack | auto | unknown",
  "lastBuildStrategy": "slot | repack | auto | unknown",
  "changedModules": [
    {"path": "/$bunfs/root/src/entrypoints/cli.js", "operationCount": 1}
  ],
  "repackSummary": {
    "changedModuleCount": 1,
    "growthBytes": 16384
  }
}
```

Missing strategy/repack fields must not break the menu. V2 may display them in status/report details, but must not branch behavior on them.

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

Mutating commands such as `enable --json`, `disable --json`, `set-prompt ... --json`, `clear-prompt --json`, `build --json`, `install-shim --target <selected-target> --json`, and `uninstall-shim --target <selected-target>|--record <install-record> --json` should return a command result envelope:

```json
{
  "schemaVersion": 1,
  "ok": true,
  "status": "ok",
  "summary": "Build activated",
  "reportPath": "/Users/example/.claude-monkey/versions/2.1.198/patchsets/example/build-report.json",
  "targetPath": null,
  "authorizationRequired": false,
  "authorizationMethod": null,
  "buildStrategy": "repack",
  "changedModules": [],
  "repackSummary": null,
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
- `targetPath`, `authorizationRequired`, and `authorizationMethod` are required for install/uninstall result envelopes. `authorizationMethod` may be `null`, `macos_gui`, `sudo`, or `not_available`.
- `buildStrategy`, `changedModules`, and `repackSummary` are optional display metadata. V2 should parse them tolerantly and ignore unknown nested fields.
- `dryRun` is required for `build`, `install-shim`, and `uninstall-shim` result envelopes; it should be `true` when the command was invoked with `--dry-run`, otherwise `false`.
- `plannedActions` is required for `--dry-run` result envelopes and should list concise strings for the changes that would have happened. It may be an empty list for non-dry-run or simple config mutations.

If `ok` is `false`, V2 should display `error.message` and offer logs/report access rather than trying to interpret every builder failure. `error.code` is for tests, logs, and future branching.

Dry-run semantics for `build`, `install-shim`, and `uninstall-shim`:

- Must not activate a build, install a shim, uninstall a shim, alter symlinks, or write protected locations.
- Must return the same result envelope shape as the real command.
- Must set `dryRun: true`.
- Must include `plannedActions`, even if the result is a failure discovered during preflight.
- `build --dry-run` must not claim verified applicability unless it actually performed source/package discovery and preflight. If it only prepared a planning envelope, its summary/planned actions must say so plainly.
- If current main supports richer planning, `build --dry-run` may include planned strategy, planned modules, changed modules, and repack summary. V2 may show these as preflight detail, but must not depend on dry-run proving visual correctness.
- May write temporary diagnostic data under the active state directory only if the CLI/core already treats that as safe diagnostic output; it must not change active profile, active patch set, current symlink, or shim install state.

## 3. Chosen implementation approach

Use `rumps` for V2.

Rationale:

- `rumps` is designed for simple macOS status bar apps that control console programs or launch separate commands.
- It can create a real menu bar app with a proper icon while keeping the implementation in Python.
- It exposes menu items, checked states, alerts, notifications, and timers without direct PyObjC ceremony.
- It keeps the app source-first and CLI-owned instead of turning the menu bar into a second implementation.

Fallback:

- If `rumps` proves too brittle on current macOS/Python, fall back to a direct PyObjC `NSStatusItem` implementation.
- Swift/AppKit is a fallback only if Python menu bar approaches fail. Even in Swift, the app must still shell out to the CLI/core rather than reimplementing product logic.

## 4. Menu bar icon requirements

The V2 app should be an icon-only menu bar item, not a text title.

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
- If state-specific icon variants are not part of the source-run deliverable, ship one template icon and represent OK/rebuild/error in the top status menu item.

Visual direction:

- A small monkey head, monkey face, or monkey/wrench silhouette is enough.
- The icon should be legible at menu bar size before it is cute.
- Do not spend V2 time on a full app icon set unless packaging becomes part of the task.

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

## 5. V2 menu structure

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
Install target…
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
- `Install target…` should show the currently selected target, allow choosing/editing a target, and identify whether it appears user-writable or protected.
- `Open build report` should open the latest active or failed report if one exists; otherwise it should show a small alert.
- `Open logs folder` should reveal `~/.claude-monkey/logs/` in Finder, creating it if the menu bar log path is initialized.
- `Open state folder` should reveal `~/.claude-monkey/` in Finder.

## 6. Data flow

The menu bar app maintains an in-memory `MenuState` derived entirely from CLI JSON output.

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

The exact JSON shape can differ if the CLI/core already has a better model. The invariant is that V2 should consume one clear state object and should not infer active patch state by scraping filenames or symlinks when the CLI can report it.

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

Clicking an existing prompt profile calls the current `set-prompt` shape with the profile source path and id:

```bash
claude-monkey set-prompt <source-path> --id <prompt-id> --from-file --json
```

Clicking `none` calls:

```bash
claude-monkey clear-prompt --json
```

Expected UX:

- Update checkmark immediately after a successful refresh.
- Show a small informational alert or notification: `Prompt will apply on next Claude launch.`
- Do not rebuild binary patchsets for prompt-only changes.
- V2 uses prompt IDs and source paths returned by `list-prompts --json`; arbitrary one-off prompt paths remain CLI-only unless this V2 implementation explicitly adds a file-picker flow.

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
- Never activate a failed build in the UI. Activation is solely CLI/core builder responsibility.

### Install/uninstall shim

Clicking install or uninstall should show confirmation because it changes the user's `claude` command path.

Commands:

```bash
claude-monkey install-shim --target <selected-target> --json
claude-monkey install-shim --target <selected-target> --json --dry-run
claude-monkey uninstall-shim --target <selected-target> --json
claude-monkey uninstall-shim --target <selected-target> --json --dry-run
claude-monkey uninstall-shim --record <install-record> --json
claude-monkey uninstall-shim --record <install-record> --json --dry-run
```

Target rules:

- V2 must carry an explicit selected install target.
- The default offered target may be `~/.claude-monkey/bin/claude` because it is user-writable and useful for PATH-first installs.
- If an existing install record or current `claude` discovery identifies another target, V2 should show that target and allow the user to keep it.
- V2 must allow protected/global targets such as a managed system/user bin location when the user explicitly selects them.
- V2 must run `install-shim --target <selected-target> --json --dry-run` before confirmation so the user can see planned actions and whether elevation is expected from the CLI/core, not from a menu-only guess.
- `uninstall-shim` should prefer the recorded install record when available, otherwise use the selected target; if neither is known, the UI must ask before running. It must dry-run the chosen uninstall command before confirmation.

Permissions rules:

- Do not run the menu bar process as root.
- User-writable targets run without elevation.
- Protected targets are in scope for V2 and must use a narrow elevation path for the protected install/restore operation only.
- The preferred macOS UX is GUI authorization for the single protected operation, with terminal `sudo` fallback if GUI authorization is unavailable.
- V2 should display the CLI/core authorization prompt/result and log the command outcome; it must not invent a second install transaction format.
- V2 must preserve rollback/restore evidence and never silently overwrite an unrelated target without the CLI/core's transaction checks.

Protected-target command contract:

- `install-shim --target <protected> --json --dry-run` should return `authorizationRequired: true`, `authorizationMethod`, `targetPath`, and planned actions without writing the target.
- `install-shim --target <protected> --json` may trigger the narrow CLI/core authorization path for that single target write.
- `uninstall-shim --target <protected> --json --dry-run` should report whether restore authorization is required.
- `uninstall-shim --target <protected> --json` may trigger the narrow CLI/core authorization path for that single restore/delete operation.
- If authorization is unavailable or denied, the command should fail with `ok: false`, `error.code: "authorization_required"` or `"authorization_denied"`, and no partial install/restore should be reported as success.

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

The build pipeline's authoritative evidence remains `build-report.json` from the CLI/core.

The menu should expose `Open logs folder` as a first-class action. The logs folder is for menu bar command-runner evidence and UI failures; it is not a replacement for build reports.

## 10. Packaging and launch stance

V2 source run command:

```bash
python3 -m claude_monkey.menubar
```

Recommended dependencies once implementation begins:

```text
rumps
PyObjC, as required by rumps on modern Python environments
```

Packaging is not required for the source-first V2 delivery. If packaging becomes necessary, use `py2app` with `LSUIElement=True` so ClaudeMonkey behaves as a background menu bar utility without a Dock icon.

Do not build login-item automation in V2 unless explicitly requested. A manual launch command is acceptable for source-first V2, but the menu bar behavior itself must be complete.

## 11. Testing and verification plan

Unit tests should cover the non-UI boundaries first:

- Current-main JSON contract parsing for `status`, `list-patches`, `list-prompts`, and command result envelopes.
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

1. Run the Current-main contract acceptance checklist below.
2. Launch from source with the icon asset present.
3. Verify the menu bar shows an icon only, not text.
4. Verify the icon is visible in light and dark menu bar appearances.
5. Toggle a patch and confirm the menu shows rebuild-required without building.
6. Click `Rebuild / Apply…`, cancel, and confirm no command runs.
7. Click `Rebuild / Apply…`, confirm, and verify the CLI/core handles build/activation.
8. Select a prompt and verify the menu says it applies on next Claude launch.
9. Choose the managed user install target and verify install/uninstall call the CLI with `--target`.
10. Choose a protected target in a safe test environment and verify V2 shows the authorization-required path without running the menu process as root.
11. Open the build report, logs folder, and state folder.
12. Simulate CLI failure and verify the menu enters error state with Refresh and logs access still available.

Current-main contract acceptance checklist before any menu UI work:

Run this against current `main` with the graph-aware repack baseline present. Use one disposable fixture environment for all config-mutating contract checks. Seed or point that fixture at known patch packages and prompt profiles, then run `list-patches` and `list-prompts` in the same fixture before selecting IDs for mutation commands. Do not mutate the user's real active profile just to prove the menu contract.

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
HOME="$TMP_HOME" claude-monkey set-prompt <known-prompt-source-path-from-fixture-list> --id <known-prompt-id-from-fixture-list> --from-file --json
HOME="$TMP_HOME" claude-monkey clear-prompt --json
HOME="$TMP_HOME" claude-monkey build --json --dry-run
HOME="$TMP_HOME" claude-monkey install-shim --target "$TMP_HOME/.claude-monkey/bin/claude" --json --dry-run
HOME="$TMP_HOME" claude-monkey install-shim --target "$TMP_HOME/.claude-monkey/bin/claude" --json
HOME="$TMP_HOME" claude-monkey uninstall-shim --target "$TMP_HOME/.claude-monkey/bin/claude" --json --dry-run
HOME="$TMP_HOME" claude-monkey uninstall-shim --target "$TMP_HOME/.claude-monkey/bin/claude" --json
HOME="$TMP_HOME" claude-monkey uninstall-shim --record <known-install-record-from-fixture> --json --dry-run
# Also run at least one protected-target dry-run or authorization-path test in an environment where it is safe.
```

Acceptance criteria:

- Each command exits successfully in a normal configured environment. Config mutations and user-writable shim install/uninstall run in disposable fixture state; protected-target checks use dry-run or a safe authorization test environment unless deliberately exercising real authorization.
- JSON parses without fallback text scraping.
- Status output includes state directory, logs directory, prompt state, desired patch state, active patch state derived from active patch set/build report evidence, rebuild-required state, current Claude path, shim target/install record when known, and latest report path if one exists.
- Patch output includes every patch ID, display label, desired enabled state, active enabled state, availability, and compatibility status.
- Prompt output includes every prompt ID, display label, active state, mode, and source path.
- Command result envelopes for all mutating commands consistently expose `ok`, `summary`, and `error`, where `error` is either `null` or an object with `message` and `code`.
- Dry-run result envelopes expose `dryRun: true` and `plannedActions`.
- Strategy/repack fields are optional and tolerated when present; their absence does not break the menu.
- Install/uninstall JSON contract covers user-writable and protected targets, including the authorization-required failure/planning shape for protected targets.
- The CLI/core, not the menu bar app, owns all config mutation, build activation, shim installation, authorization, and rollback behavior.

## 12. Non-goals for V2

V2 should not include:

- Version drift automation.
- Candidate compatibility builds beyond what the CLI/core already exposes.
- A full Preferences window.
- Patch manifest editing.
- Prompt file editing.
- Remote patch registry browsing.
- Auto-update.
- Login item management.
- Swift rewrite.
- Full app packaging or notarization.
- Any direct byte editing, signing, or activation logic in the menu bar layer.

## 13. Implementation sequence on current main

1. Pass the Current-main contract acceptance checklist with real JSON output or add the missing CLI JSON seams first.
2. Add the menu bar icon asset under `assets/`.
3. Add `claude_monkey.menubar_state` for parsing JSON and deriving UI state.
4. Add `claude_monkey.menubar_commands` for safe argv-list subprocess execution, serialization, background slow-command handling, and menu bar logging.
5. Add `claude_monkey.menubar` as the `rumps` app entrypoint with icon-only status item wiring.
6. Build the static menu with status, prompt, patch, rebuild, install/uninstall, open report, open logs, open state folder, refresh, and quit items.
7. Wire prompt and patch clicks to CLI commands.
8. Wire rebuild/install/uninstall confirmation flows.
9. Add unit tests for state, command mapping, command serialization, safe subprocess invocation, and logs/report open behavior.
10. Run the manual macOS smoke checklist, including protected-target authorization or its safe test double.

Stop after a complete source-run V2 menu bar. Do not add unrelated registry, auto-update, or version-drift automation unless explicitly requested.
