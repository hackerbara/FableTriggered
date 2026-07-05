# Demo Recorder Review Feedback

Date: 2026-07-04
Worktree: `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder`
Reviewed handoff: `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/docs/superpowers/handoffs/2026-07-04-demo-recorder-smoke-handoff.md`
Status: feedback for next implementation pass; do not treat current smoke artifact as publishable.

## Executive summary

The matrix runner is a useful orchestration layer, and the recorder has the right broad ingredients: JSON configs, Ghostty, System Events, ffmpeg screen capture, palette GIF conversion, checkpoint extraction, and a publish gate.

The current failure is not timing and not the matrix runner. The current failure is the launch contract.

The implementation sends a shell command by clipboard paste plus Return into the frontmost Ghostty app. It verifies only that Ghostty is frontmost. It does not verify that the active Ghostty surface is the prepared shell prompt, and the smoke artifact shows that the command landed in stale terminal state rather than producing the intended Claude UI demo.

For V1, we do **not** need to solve arbitrary multi-window terminal control. The acceptable V1 contract is:

> The user manually prepares a clean Ghostty environment before recording. Ghostty is the only Ghostty app/session intended for recording, it is on the selected screen, it is at a shell prompt, and it is safe to record. The recorder may rely on that contract, but it must make the contract explicit, perform cheap guardrails, and fail loudly when the evidence contradicts it.

Under that contract, the next implementation should make the recorder a reliable button-presser for one prepared Ghostty, not a general desktop automation harness.

## What was reviewed

Primary files reviewed:

- `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recorder/record_demo.py`
- `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recorder/run_demo_matrix.py`
- `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recorder/demo_matrix.json`
- `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recorder/README.md`
- `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recorder/tests/test_record_demo.py`
- `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recorder/tests/test_demo_matrix.py`
- `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/docs/superpowers/handoffs/2026-07-04-demo-recorder-smoke-handoff.md`

Smoke artifacts reviewed:

- `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recordings/hidden-context-plus-hotrod-dragons-2.1.199-open-drawer/20260704-151730/demo.gif`
- `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recordings/hidden-context-plus-hotrod-dragons-2.1.199-open-drawer/20260704-151730/raw.mov`
- `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recordings/matrix/20260704-151730/summary.json`
- `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recordings/matrix/20260704-151730/checkpoints/hidden-context-plus-hotrod-dragons-open-close-open.png`
- `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recordings/matrix/20260704-151730/checkpoints/hidden-context-plus-hotrod-dragons-open-close-closed.png`

Verification run during review:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s .development/demo-recorder/tests -p 'test_*.py'
```

Result:

```text
Ran 78 tests in 0.090s
OK
```

This test result means the current unit tests pass. It does **not** mean the recorder satisfies the launch/demo contract.

## Current smoke result

The smoke command was:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 .development/demo-recorder/run_demo_matrix.py \
  --id hidden-context-plus-hotrod-dragons-open-close
```

The generated config resolved this launch command:

```bash
cd /Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder && /Users/MAC/Documents/Claude-patch/.development/claude-monkey-builds/hidden-context-plus-hotrod-dragons-2.1.199/claude --dangerously-skip-permissions
```

The raw capture and GIF were successfully produced as media files:

- raw movie: 4096x2304, about 20 seconds
- GIF: 960x540, about 20 seconds

But the checkpoint frames show a Ghostty shell/history view, not the intended Claude UI. That means the smoke produced media, but not the demo.

The smoke should be considered **failed for demo correctness** even though the matrix summary says `status: passed`.

## Major finding: `status: passed` is currently too broad

`run_demo_matrix.py` sets summary records to `status: passed` once `record_demo.run_recording()` returns metadata and the raw/GIF/checkpoint files exist.

That is useful for media production, but misleading for demo correctness.

The runner currently proves:

- a generated recorder config was written;
- `record_demo.py` returned metadata;
- raw video exists and is non-empty;
- GIF exists and is non-empty;
- checkpoint PNGs exist and are non-empty.

The runner does not prove:

- the command was accepted by a clean shell prompt;
- the intended Claude binary launched;
- the UI was visible before recording events started;
- the drawer opened;
- the drawer closed;
- the final GIF is safe or suitable for publishing.

Recommended change:

- Rename or split status fields so the summary cannot imply visual/demo success.
- Suggested fields:
  - `recordingStatus`: `passed` / `failed`
  - `launchStatus`: `verified` / `unverified` / `failed`
  - `reviewStatus`: `needs-human-review` / `approved` / `rejected`
  - `publishStatus`: `not-published` / `published`
- Do not allow `--publish-from-summary` unless the record has a human-reviewed approval marker or the command explicitly requires a review override.

For V1, a simple version is acceptable:

```json
{
  "status": "recorded",
  "needsReview": true,
  "launchVerified": true,
  "published": null
}
```

Avoid calling a record `passed` unless the thing that passed is named precisely.

## Major finding: current launch path is unsafe for automation

The current recorder launch path is:

1. focus Ghostty by bundle id;
2. assert the frontmost application bundle is Ghostty;
3. put the resolved shell command on the clipboard;
4. send `cmd-v`;
5. send Return;
6. later send scripted events to the same frontmost app class.

That only proves the frontmost app is Ghostty. It does not prove the active terminal is the prepared prompt.

This is the line between “button presser” and “wishy-washy paste automation.” The code presses buttons, but the launch target is not specific enough.

## Accepted V1 launch contract

The next implementation may use this explicit contract instead of building a live harness:

### User responsibilities before running recorder

The user will:

1. Quit unrelated Ghostty windows/sessions.
2. Launch Ghostty manually.
3. Put Ghostty on the intended display at the intended size/fullscreen state.
4. Set font/zoom/theme exactly as desired.
5. Ensure the active Ghostty surface is a clean shell prompt, not an existing Claude TUI.
6. Ensure the selected screen is safe to record.
7. Then run the recorder from Codex/terminal.

This is acceptable. The recorder does not need to discover or repair arbitrary stale terminal state.

### Recorder responsibilities under that contract

The recorder should still:

1. Print the launch contract before a real run.
2. Refuse to run unless Ghostty is already running when using `reuseRunning` / prepared mode.
3. Refuse or warn loudly if multiple Ghostty windows are detectable through System Events/accessibility.
4. Focus Ghostty and assert the frontmost bundle before launch.
5. Paste the command only after that assertion.
6. Record the launch command and run id in metadata.
7. Verify after launch that the intended Claude process appears.
8. Only then wait/record/send demo events.
9. Mark the output as needing human visual review.

The key difference: the recorder can rely on the prepared prompt, but it should not silently convert a bad prepared prompt into a “passed” run.

## Recommended launch verification

Add a per-run id and post-launch process check.

Suggested approach:

1. Generate a run id, for example `demo-recorder-YYYYMMDD-HHMMSS-<short-random>`.
2. Include it in the launch command as an environment variable:

   ```bash
   cd <cwd> && DEMO_RECORDER_RUN_ID=<run-id> <binary> <args...>
   ```

3. Record the exact resolved command in `config.snapshot.json`.
4. After paste+Return, wait a short configurable interval.
5. Scan processes for the intended binary path and/or run id.
6. If no matching process is found, fail before recording events.

This does not perfectly prove the terminal prompt was clean, but it catches the important failure: the intended binary did not launch.

If environment scanning is unreliable on macOS, use a simpler but still useful check:

- record launch start time;
- scan `ps` for the exact binary path and expected args;
- prefer processes started after launch start if start time is available;
- if multiple matches exist, report ambiguity and fail unless an explicit override is provided.

Do not use global `grep claude` cleanup or broad matching. The handoff was right about this.

## Recommended prepared-Ghostty guardrails

Add a dedicated launch mode whose name makes the contract explicit:

```json
"launchMode": "reuseSinglePreparedGhostty"
```

or, if keeping the existing field values, add:

```json
"preparedGhostty": {
  "requireAlreadyRunning": true,
  "requireSingleWindowIfDetectable": true,
  "assumeCleanShellPrompt": true
}
```

Behavior:

- If Ghostty is not running: fail with setup instructions.
- If frontmost bundle cannot become `com.mitchellh.ghostty`: fail.
- If multiple Ghostty windows are detectable: fail or require `allowMultipleWindows: true`.
- If launch process verification fails: fail before recording.
- If launch process verification is skipped: mark `launchVerified: false` and do not call the run passed.

Do not try to silently fix by sending arbitrary cleanup keys. `ctrl-c`, `ctrl-u`, `clear`, or `reset` can be useful in manual setup, but they are not proof that the active target is a shell prompt. If implemented, make them an explicit optional pre-launch sequence, not a hidden repair.

## Event sequence feedback

The Hidden Context demo intent from the user was:

1. launch Claude;
2. show the normal UI with hidden context available in the status/footer area;
3. arrow down to Hidden Context;
4. press Enter to open the drawer;
5. show drawer;
6. press `x` to close;
7. show closed state.

Current recipe uses:

```json
[
  {"type": "wait", "seconds": 2},
  {"type": "key", "key": "down"},
  {"type": "wait", "seconds": 0.7},
  {"type": "key", "key": "down"},
  {"type": "wait", "seconds": 5},
  {"type": "key", "key": "x"},
  {"type": "wait", "seconds": 5},
  {"type": "key", "key": "ctrl-c"}
]
```

If the actual footer interaction is “down selects, Enter opens,” then the recipe should use `return` for open. If the patched binary intentionally opens on the second Down, document that as package-specific behavior in the matrix recipe. Do not leave this ambiguous.

Keep `x` as the close affordance. Do not use Escape for this demo.

## Artifact/privacy feedback

The smoke artifacts should not be published. The checkpoint frames contain prior terminal history and private-looking URL/token material. This happened because the selected Ghostty surface was stale.

Recommended change:

- Treat checkpoint extraction as part of the privacy review surface.
- Put a clear warning in `summary.md`:

  > This summary proves media files were generated. It does not approve publication. Open the GIF and checkpoint PNGs before publishing.

- Consider adding `reviewNotes` or `privacyReview` fields to summaries.
- Do not publish from any summary generated before the launch contract fix.

## Test feedback

The 78 unit tests passing is useful but currently incomplete. The tests mostly validate parser behavior, file existence behavior, and that the current focus/paste functions call the expected mocked helpers.

Add tests that encode the new contract:

1. `launch_demo_command` includes a run id in metadata or command environment.
2. recorder fails if prepared Ghostty mode is used and Ghostty is not already running.
3. recorder fails if multiple Ghostty windows are reported and the config requires a single prepared window.
4. recorder fails before recording when post-launch process verification does not find the intended binary.
5. matrix summary distinguishes media-recorded from launch-verified/review-approved.
6. publish-from-summary refuses records that are not explicitly reviewed/approved, or at least refuses records with `launchVerified: false`.
7. Hidden Context recipe uses the documented open key (`return` or intentionally documented second `down`).

Do not add tests that merely preserve the current flawed behavior as the desired behavior.

## Suggested next implementation slice

Make the next pass small and targeted. Do not expand the matrix runner or add more recipes until the launch contract is fixed.

### Slice A: Prepared Ghostty contract

- Update README with exact manual prep checklist.
- Add config field or launch mode for single prepared Ghostty.
- Print the contract at run start.
- Add System Events window-count check if reliable; otherwise document that only frontmost bundle can be verified and process verification is the real guardrail.

### Slice B: Launch process verification

- Generate a run id.
- Include the run id or exact launch metadata in the command path/environment.
- Add `verify_launch_process(config, run_id, launched_at)`.
- Fail before recording if the intended binary is not found.
- Write verification result into metadata.

### Slice C: Summary semantics

- Replace broad `status: passed` with precise statuses.
- Mark all new recordings as needing human review.
- Make publish-from-summary require the new status fields.

### Slice D: Hidden Context recipe correction

- Confirm whether drawer open should be `return` or second `down` for the target binary.
- Encode that in the matrix recipe and README notes.
- Keep `x` close.

### Slice E: Re-smoke only after user prep

Run the smoke only when the user has confirmed:

- only the intended Ghostty is open;
- it is on the desired screen;
- it is at a clean shell prompt;
- the selected display is privacy-safe.

Then inspect checkpoint frames before calling the run usable.

## Non-goals for the next pass

Do not build a full live harness yet.

Do not try to automate account login, prompt submission, or arbitrary Claude session recovery.

Do not solve multi-window/multi-tab Ghostty control in V1.

Do not publish any generated GIF without human visual review.

Do not add more demo recipes before the launch/session contract is fixed.

## Acceptance criteria for the next pass

The next pass is acceptable when:

1. The README clearly states the prepared-Ghostty contract.
2. The recorder fails loudly if Ghostty is not running in prepared mode.
3. The recorder focuses Ghostty and asserts frontmost before launch and before each event.
4. The recorder performs post-launch process verification for the intended binary, or records `launchVerified: false` and refuses to call the run passed.
5. The matrix summary no longer implies visual correctness from file existence alone.
6. The Hidden Context recipe’s open/close keys match the intended UI behavior and are documented.
7. A new smoke captures actual Claude UI, not a shell history screen.
8. Checkpoint PNGs are reviewed before any publish step.

## Final recommendation

Proceed with the prepared-single-Ghostty contract. That is a good V1 boundary.

But make that contract explicit in code and metadata. The recorder may rely on the user preparing the one Ghostty correctly; it may not pretend that frontmost-bundle plus media files proves the demo worked.
