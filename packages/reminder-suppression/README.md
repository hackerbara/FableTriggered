# Reminder suppression (superseded)

This package is superseded by `packages/upstream-attachment-suppression`.

`reminder-suppression` patched selected renderer/model-conversion cases after attachment records could already exist. That was useful as an early experiment, but it is too late for the stronger invariant: selected recurring reminder/accounting families should never become transcript rows, never enter request assembly, never render in chat, and never appear in the Hidden Context drawer.

Use `packages/upstream-attachment-suppression` for Claude Code `2.1.199`. That package gates denied attachment generator labels before generator execution and filters denied attachment objects before `li(...)` row construction.

This package remains in the repository as historical/reference material for Claude Code `2.1.198`. Do not install it together with `upstream-attachment-suppression` unless a future compatibility test explicitly proves the combination is harmless for a specific Claude Code version.
