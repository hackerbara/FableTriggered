# Upstream attachment suppression

Suppresses selected recurring reminder/accounting attachment families before they become Claude Code transcript rows.

This is a ClaudeMonkey V1.5 schema-v2 package. It targets `/$bunfs/root/src/entrypoints/cli.js` in Bun module coordinates and relies on the Bun graph repack engine for positive-growth module splices.

## Target

- Claude Code `2.1.199 (Claude Code)`
- macOS arm64
- Source SHA-256: `e3cb61abc8a2ec7b98976cee1ffdde5a3fa755c9990bc8d688cd89290e0dcec0`

## What it suppresses

The package denies these generator labels before their generators run:

- `todo_reminders`
- `tool_search_usage_reminder`
- `total_tokens_reminder`
- `token_usage`
- `budget_usd`
- `output_token_usage`

It also filters these attachment object types before `li(...)` can wrap them as transcript rows:

- `todo_reminder`
- `task_reminder`
- `tool_search_usage_reminder`
- `token_usage`
- `total_tokens_reminder`
- `budget_usd`
- `output_token_usage`

## What it does not suppress

The package intentionally leaves safety, permission, hook, file-state, plan/auto-mode, team, memory, diagnostics, queued command, and user-provided file reference families intact.

## Why this supersedes reminder-suppression

`packages/reminder-suppression` patched selected renderer/model-conversion cases after attachment records could already exist. That is too late for the invariant this package targets.

This package patches upstream generation and row construction:

1. `ug(label, generator)` returns `[]` for denied labels before the generator runs and before `tengu_attachment_compute_duration` telemetry can record denied families.
2. `Hze(...)` filters denied attachment objects before `tengu_attachments` telemetry and before `li(c,o)` creates transcript rows.

Historical transcripts are not rewritten. Existing denied rows remain in old session JSONL unless a separate transcript sanitation tool is explicitly built and run.
