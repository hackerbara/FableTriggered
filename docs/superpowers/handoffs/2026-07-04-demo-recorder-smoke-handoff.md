# Demo Recorder Smoke Handoff

Date: 2026-07-04
Worktree: `/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder`
Context: Hidden Context + Hotrod Dragons demo smoke run.

## Current implementation

The matrix runner is in:

```text
/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recorder/run_demo_matrix.py
```

It materializes a single-recorder config and calls the existing recorder:

```text
/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recorder/record_demo.py
```

The real smoke command that was run was:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 .development/demo-recorder/run_demo_matrix.py \
  --id hidden-context-plus-hotrod-dragons-open-close
```

The generated config for that run is:

```text
/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recordings/matrix/20260704-151730/generated-configs/hidden-context-plus-hotrod-dragons-open-close.json
```

It resolved this command:

```bash
cd /Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder && /Users/MAC/Documents/Claude-patch/.development/claude-monkey-builds/hidden-context-plus-hotrod-dragons-2.1.199/claude --dangerously-skip-permissions
```

## What the recorder currently does

`record_demo.py` does not spawn the Claude binary directly as a child process.

Current launch path:

1. Focus Ghostty by bundle id (`com.mitchellh.ghostty`).
2. Check only that the frontmost application bundle is Ghostty.
3. Put the resolved shell command on the clipboard.
4. Send `cmd-v` to Ghostty.
5. Send Return.
6. Start recording and send scripted keys later.

Current event path is similar: before each key event it focuses Ghostty and checks the frontmost bundle, then sends AppleScript key events.

## Smoke result

The smoke produced files and exited successfully from the runner's perspective.

Primary artifacts:

```text
/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recordings/hidden-context-plus-hotrod-dragons-2.1.199-open-drawer/20260704-151730/demo.gif
/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recordings/hidden-context-plus-hotrod-dragons-2.1.199-open-drawer/20260704-151730/raw.mov
/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recordings/matrix/20260704-151730/summary.json
/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recordings/matrix/20260704-151730/checkpoints/hidden-context-plus-hotrod-dragons-open-close-open.png
/Users/MAC/.config/superpowers/worktrees/Claude-patch/demo-recorder/.development/demo-recordings/matrix/20260704-151730/checkpoints/hidden-context-plus-hotrod-dragons-open-close-closed.png
```

The runner reported `status: passed`, but that only means the recorder produced a raw movie, GIF, metadata, and checkpoint PNGs. It does not prove the command actually launched in the intended terminal prompt or that the UI sequence did what the demo intended.

## Observed problem

The user observed that the command appeared to be pasted into the existing Ghostty/Claude context rather than being run as a shell command in a prepared prompt.

That is plausible under the current implementation.

The current focus check is too coarse: it verifies only that Ghostty is the frontmost app. It does not verify:

- which Ghostty window/tab/split is active;
- which tty is attached to that Ghostty surface;
- whether the active terminal is at a shell prompt;
- whether an existing Claude TUI is currently reading input;
- whether the pasted command was accepted by a shell;
- whether the intended Claude binary became a child process of the prepared Ghostty shell.

There is also no terminal clear/reset step and no post-launch process verification tied to the prepared Ghostty tty.

## Why this matters

The recorder can create a good-looking GIF while failing the actual launch contract. Screen capture success is not the same as interaction correctness.

The design currently treats Ghostty focus as enough. For this workflow it is not enough.

## Likely root cause

The launch mechanism is clipboard-paste-plus-Return into whatever Ghostty input target is active. If the active target is an existing Claude session instead of a clean shell prompt, the resolved shell command becomes text entered into that session.

This is not a matrix-runner issue by itself. It is a recorder launch/readiness contract issue in `record_demo.py`.

## Current cleanup/process state note

A later process scan showed multiple Claude-related processes across unrelated worktrees/sessions, so global `grep claude` matching is unsafe.

The safe cleanup protocol remains:

```bash
ps -o pid=,ppid=,pgid=,tty=,stat=,command= -t <prepared-tty>
```

Then kill only the Claude process group parented under the prepared Ghostty shell for that tty. Do not kill by broad process name.

## Questions for design agent

1. Should the recorder stop pasting launch commands and instead spawn the binary under a controlled PTY/process that Ghostty attaches to?
2. If Ghostty must remain the launcher, what exact readiness check proves the active input target is a clean shell prompt?
3. Should a recipe declare the expected tty/window identity before recording starts?
4. Should launch success require process-tree evidence: intended binary path, expected cwd, expected args, parented under the prepared Ghostty tty?
5. Should the recorder fail if Ghostty is frontmost but the active terminal contains a running Claude TUI?
6. Should the script clear/reset the terminal before paste, or is that still insufficient without prompt/process verification?

## Non-goals for this handoff

- This document does not propose a final fix.
- This document does not claim the smoke was a valid demo.
- This document does not claim the existing recorder launch path is safe enough.
