# GIF capture prompt (paste-ready, consolidated)

Paste everything inside the fence to the capture agent (Codex). Supersedes the earlier chat versions — amendments and the capy workaround are folded in.

```
Context: this repo (/Users/MAC/Documents/Claude-patch) is "HarnessMonkey",
a patch manager for Claude Code, about to launch publicly. The canonical
README is HarnessMonkey-README.md — its package table references demo GIFs
that don't exist yet. Your job: produce them using the demo-recorder
tooling that already exists in this repo.

Tooling (already merged, read these first):
- .development/demo-recorder/README.md, record_demo.py, run_demo_matrix.py,
  demo_matrix.json, configs/
- Design + plan docs: docs/superpowers/specs/2026-07-04-demo-recorder-design.md
  and docs/superpowers/plans/2026-07-04-demo-recorder.md
- It drives Ghostty via AppleScript, runs a patched claude binary, screen-
  records via ffmpeg/AVFoundation, converts to GIF via palette generation.
  Recordings land in .development/demo-recordings/ (gitignored); ONLY
  reviewed, explicitly published output goes to assets/demos/.

Deliverables — 9 GIFs in assets/demos/ with EXACTLY these filenames
(they're the README's image contract). IMPORTANT: filenames use the
packages' FINAL public names; the package directories still have old
names (the rename lands in a separate cutover tree). Map:

  capyclaude.gif            ← header shot: capybara-onsen scene framing a
                              real session (the money shot, take care)
  capybara-onsen.gif        ← packages/capybara-onsen
  heraldic-dragons.gif      ← packages/hotrod-dragons
  fable-fallback.gif        ← packages/fable-fallback
  drawer-dock.gif           ← packages/footer-drawers — ENSEMBLE shot:
                              all three drawers enabled on the dock,
                              flipping between them
  hidden-context-drawer.gif ← packages/hidden-context-drawer
  hidden-context-inline.gif ← packages/normal-channel-hidden-context
  thinking-drawer.gif       ← packages/thinking-text-drawer
  reminders-drawer.gif      ← packages/reminders-manager

  (NO gif for upstream-attachment-suppression/mute-reminders — no visible
  UI; its README table cell is intentionally blank.)

Build-combination constraints (patches conflict, so you need multiple
builds, not one):
- hidden-context-drawer CONFLICTS with normal-channel-hidden-context
- reminders-manager CONFLICTS with upstream-attachment-suppression
- the three drawer patches (hidden-context-drawer, thinking-text-drawer,
  reminders-manager) each REQUIRE footer-drawers enabled alongside
  (enable-patch auto-selects it now)
- capybara-onsen and hotrod-dragons CONFLICT with each other (same
  anchors) — one art scene per build

NOTE: an earlier capy+drawer Enter-to-open bug is FIXED (commit ba59b0f) —
composing the capy scene with drawers is fully supported. The header shot
(capyclaude.gif) may include opening a drawer inside the capy frame if it
reads well — that combination is the product's best single image. Keep the
individual drawer GIFs art-free for clean frames.

The maintainer has all packages loaded in ~/.claude-monkey/patches —
coordinate with them on which build is active per recording session
(enable-patch / build --activate per combo).

Quality bar: truecolor terminal (Ghostty), keep each GIF short (a few
seconds of loop-worthy motion), watch total size — palette/fps tune
before publishing; these clone with the repo. Do NOT commit anything to
assets/demos/ without the maintainer eyeballing every GIF first — they
must also check no GIF captures unrelated personal screen content
(hard gate; this machine has had one near-miss already tonight).
Do NOT modify packages/**, src/**, or tests/**.

When done: leave the reviewed GIFs in assets/demos/ in THIS repo. A
separate cutover tree (~/Documents/harnessmonkey) will receive copies
before the public push — not your concern.
```
