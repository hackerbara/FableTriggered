# ClaudeMonkey v2 menu bar design and runbook

Date: 2026-07-02
Status: approved design direction; implementation not started
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
claude-monkey build --json
claude-monkey install-shim --json
claude-monkey uninstall-shim --json
```

The menu bar may tolerate early text output during a spike, but the implementation plan should treat JSON CLI output as a required seam before a usable MVP.

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

## 5. MVP menu structure

Target menu:

```text
[icon-only status item]
────────────────
ClaudeMonkey: OK / Rebuild Required / Error
Claude Code: 2.1.198
Prompt: research
Patches: 2 enabled
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
  -> run one claude-monkey command via subprocess
  -> capture stdout, stderr, exit code
  -> refresh MenuState
  -> show alert only for failures, protected operations, or build summaries
```

## 7. Action behavior

### Prompt picker

Clicking a prompt profile calls:

```bash
claude-monkey set-prompt <prompt-id>
```

Clicking `none` calls:

```bash
claude-monkey clear-prompt
```

Expected UX:

- Update checkmark immediately after a successful refresh.
- Show a small informational alert or notification: `Prompt will apply on next Claude launch.`
- Do not rebuild binary patchsets for prompt-only changes.

### Patch enable/disable submenu

Clicking a patch calls one of:

```bash
claude-monkey enable <patch-id>
claude-monkey disable <patch-id>
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

- Show a running/busy menu state if practical.
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

### Open report and folders

Use macOS `open` through subprocess:

```bash
open <latest-build-report-path>
open ~/.claude-monkey
```

If the latest report path is missing, show an alert instead of failing silently.

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

Error UI rules:

- Set top status line to `ClaudeMonkey: Error`.
- Use the error icon variant if available.
- Preserve the last known good menu where possible, but mark it stale.
- Include `Open state folder` and `Refresh` even in error state.
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

- CLI JSON parsing into `MenuState`.
- Menu state derivation: OK, rebuild-required, error, not-installed.
- Prompt click maps to the correct CLI command.
- Patch click maps to `enable` or `disable`, not `build`.
- Rebuild confirmation maps to `build --json`.
- Open report handles missing report paths.
- Command failures preserve enough stderr for the user.

Manual smoke tests on macOS:

1. Launch from source with the icon asset present.
2. Verify the menu bar shows an icon only, not text.
3. Verify the icon is visible in light and dark menu bar appearances.
4. Toggle a patch and confirm the menu shows rebuild-required without building.
5. Click `Rebuild / Apply…`, cancel, and confirm no command runs.
6. Click `Rebuild / Apply…`, confirm, and verify v1 handles build/activation.
7. Select a prompt and verify the menu says it applies on next Claude launch.
8. Open the build report and state folder.
9. Simulate CLI failure and verify the menu enters error state with Refresh still available.

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

1. Add or confirm v1 JSON command contracts.
2. Add the menu bar icon asset under `assets/`.
3. Add `claude_monkey.menubar_state` for parsing JSON and deriving UI state.
4. Add `claude_monkey.menubar_commands` for subprocess execution and logging.
5. Add `claude_monkey.menubar` as the rumps app entrypoint.
6. Build the static menu with status, prompt, patch, rebuild, install/uninstall, open, refresh, and quit items.
7. Wire prompt and patch clicks to CLI commands.
8. Wire rebuild/install/uninstall confirmation flows.
9. Add unit tests for state and command mapping.
10. Run the manual macOS smoke checklist.

Stop after a working source-run menu bar MVP. Do not expand into packaging polish until the thin companion proves useful.
