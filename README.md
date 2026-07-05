# FableTriggered - Claude Code Fable downgrade message visibility patch

![FableTriggered screenshot](assets/fabletriggered-screenshot.jpeg)

## What is this?

An instruction file that tells a coding agent how to monkey-patch a local version of Claude Code to show an indicator in the session `/resume` list if the session had a security-classifier downgrade message, and then to unhide that downgrade message in the resumed chat.

## Why would I want this?

The safety classifiers for Fable from Anthropic are quite hyperactive (even before the predictable but deeply unfortunate US government intervention), and you will likely get downgraded to Opus frequently. When this happens, it's visible mid-session to the user, but the Claude Code harness currently hides it on resume, providing no indicator a session was part Fable, part Opus.

This seems less than ideal for a variety of practical and/or ideological reasons that you can probably imagine for yourself.

## How does it work?

You point your preferred local coding agent at the instruction file. The actual refusal message is in the transcript history, it's just not rendered by the Claude Code harness by default. Implementation work tested with Codex; likely would be refused by Claude itself.

## Patch instruction files

- [`claude-fable-fallback-patch.md`](claude-fable-fallback-patch.md) - shows Fable fallback events in resumed history and `/resume`.
- [`claude-reminder-suppression-patch.md`](claude-reminder-suppression-patch.md) - suppresses selected recurring reminder attachments in a copied Claude Code binary.

## ClaudeMonkey packages

See [CLAUDEMONKEY.md](CLAUDEMONKEY.md) for the full package catalog, install instructions, and how to build your own.

- [`packages/fable-fallback`](packages/fable-fallback) - graph-repack package for Fable fallback visibility and `/resume` marking.
- [`packages/hidden-context-drawer`](packages/hidden-context-drawer) - graph-repack package that adds the footer Hidden Context drawer for model-visible hidden attachment context.
- [`packages/normal-channel-hidden-context`](packages/normal-channel-hidden-context) - graph-repack package that projects selected hidden model-visible attachment context into the normal transcript as warning rows.
- [`packages/reminder-suppression`](packages/reminder-suppression) - graph-repack package for suppressing selected recurring reminder renderers.

## ClaudeMonkey manager app (GUI)

ClaudeMonkey also ships a small tray/menu-bar app so you don't have to drive the `claude-monkey` CLI by hand.

**Launching it:** install the `gui` extra (`pip install -e ".[gui]"`, which pulls in PySide6 and, on macOS, `pyobjc-framework-Cocoa`), then run `claude-monkey-menubar`. That command name is historical - the app underneath it is a PySide6 tray icon plus a manager window now, not the old `rumps` menu bar (that code is gone).

**Manager window:** click the tray icon to open it. It's a sidebar over six pages: Overview (status, active prompt/patch set, high-risk option warnings, the rebuild button, and the update notice below), Patches, Prompts, Options, Install, and Logs & Reports (a tail of the log plus buttons to open the report/logs/state folders).

**Long operations:** Rebuild / Apply, Install shim, and Uninstall shim each open one progress dialog - confirm, then watch it run, with cancel available unless the step needs elevated permission mid-run. Only one of these runs at a time, whether you trigger it from the tray or the window. Quicker actions (toggling a patch or option, picking a prompt, adding/removing a package) run in the background without a dialog; a failure just shows as an inline banner on the page you triggered it from.

**If an official Claude update clobbers the shim:** when Anthropic's own installer replaces the `claude` command that ClaudeMonkey had wired up, the Overview page shows a notice - something like "Claude 2.1.201 available - shim repair needed" - with a "Repair shim…" button (also available from the tray). Repairing asks for confirmation, then runs in the background (no progress dialog for this one) and puts the new Claude behind the ClaudeMonkey shim again. Afterward the notice becomes informational only ("...rebuild to roll out"), since rolling the newly detected build into your patched binary is still a manual `Rebuild / Apply` for now - one-click rollout isn't wired up yet. You can dismiss a notice; it comes back if Claude changes again later.

Everything the GUI does - status refreshes, toggles, rebuilds, shim install/repair - goes through the same `claude-monkey` CLI (using its `--json` output) that you can also run yourself; the app doesn't reimplement any of that logic.

## Is this a good idea?

Maybe not? Hard to say. Maybe Anthropic will chime in.

It's just a small bit of JavaScript patching into the resume metadata and message display. I tried to include some sanity about installing it, but this will surely be brittle with updates. So, idk, rerun with your agent if it breaks and watch memory leaks maybe?

No warranty; have fun, don't die, etc. etc.

<3 Hackerbara
