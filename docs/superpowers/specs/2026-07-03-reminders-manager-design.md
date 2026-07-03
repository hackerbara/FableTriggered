# Reminders Manager — Design

Runtime toggle panel for suppressed reminder/accounting attachment families, as a second footer drawer alongside Hidden Context.

**Status:** Draft. Footer-seam anchors are provisional until the `hidden-context-drawer` 2.1.199 port lands (in progress by another agent); they will be filled in against that package's final claimed ranges.

## Purpose

`upstream-attachment-suppression` blocks seven recurring reminder/accounting attachment families unconditionally at build time. This package replaces that static behavior with a runtime-managed deny set plus a footer drawer UI ("Reminders") so families can be unblocked or re-blocked while a session is running.

- All families **blocked by default** at session start (identical to current suppression behavior).
- Toggling a family **on** stops suppressing it from the next attachment-generation cycle onward. Previously suppressed occurrences are not retroactively delivered.
- Toggling **off** resumes suppression from the next cycle.
- State is **session-only**. No persistence. Restart returns to all-blocked.

## Package shape

Normal ClaudeMonkey V1.5 schema-v2 package: `packages/reminders-manager/`.

- Anchored on **stock Claude Code 2.1.199** (`sha256 e3cb61ab…`), like every other package in this repo.
- Stacks with other enabled packages in a single `build_patchset_v15` build. Composition requirement: **all splice ranges disjoint from the ported `hidden-context-drawer` ranges** (and from `fable-fallback`, `normal-channel-hidden-context` if enabled). Install either package alone or both together; the profile's `enabledPatches` list drives the stack.
- **Conflicts with (supersedes) `upstream-attachment-suppression`**: both own the `ug`/`Hze` seams. Documented in both READMEs, same pattern as the existing drawer/normal-channel conflict note.

## Families

Seven rows, mapping generator labels and attachment object types:

| Row label | Generator label (`ug`) | Attachment type (`Hze`) |
|---|---|---|
| todo reminders | `todo_reminders` | `todo_reminder` |
| task reminders | — | `task_reminder` |
| tool search usage | `tool_search_usage_reminder` | `tool_search_usage_reminder` |
| token usage | `token_usage` | `token_usage` |
| total tokens | `total_tokens_reminder` | `total_tokens_reminder` |
| budget (USD) | `budget_usd` | `budget_usd` |
| output token usage | `output_token_usage` | `output_token_usage` |

## Components

### 1. Runtime deny state

`globalThis.__CODEX_REMINDERS_MANAGER_V1__` — an object `{ deny: { <family>: boolean } }` initialized with all seven families `true` (denied). Defined with an init guard (`??=` pattern) in whichever splice evaluates first; both the deny seams and the UI read/mutate the same object. Missing/undefined state falls back to default-deny (fail closed — a broken UI never un-suppresses by accident, and never crashes the attachment path).

### 2. Deny seams (functional half)

Same two splices as `upstream-attachment-suppression`, re-authored:

- **`ug(e,t)` label gate** — `__codexRMDenyLabel(e)` looks up the label's family in the runtime deny object; denied → return `[]` before the generator and its compute-duration telemetry run.
- **`Hze(...)` object filter** — `__codexRMDenyAttachment(e)` filters denied attachment objects before `tengu_attachments` telemetry and `li(...)` row construction.

Identical structure to the UAS payloads except the hardcoded boolean chains become runtime lookups. Everything UAS intentionally leaves intact (safety, permission, hook, file-state, plan-mode, team, memory, diagnostics, queued-command, user file references) stays intact.

### 3. Footer target (UI half) — anchors provisional

A `reminders` footer target following the exact pattern the hidden-context drawer established:

- Entry in the footer targets list, after `hiddenContext` — arrow down past Hidden Context reaches Reminders.
- Availability-bar segment (`Reminders`), selection flag, selected-state hook.
- Keyboard: up/down moves the row cursor inside the open drawer, **enter/space toggles the row**, `x` closes (x-only close, matching the drawer's convention). Opening via footer openSelected, same as Hidden Context.
- Open-state global: `globalThis.__CODEX_REMINDERS_DRAWER_OPEN_V1__`.

**Anchor constraint:** every splice here must claim exact substrings disjoint from the ported drawer's ranges (e.g., where the port claims `case"tmux"…case"frame"` in the footer switch, this package anchors on a different, non-overlapping case range; where the port claims the targets-array construction, this package anchors downstream of it). The final anchor table is written after the port lands, verified by building both packages together (`_check_overlaps` is the enforcement).

### 4. Drawer UI

Bottom overlay rendered as a `UXl`-sibling panel, visual language matching Hidden Context:

```
┌ Reminders ──────────────────────────── x closes ┐
│ [~] all reminders                                │
│ ─────────────────────────────                    │
│ [x] todo reminders                               │
│ [ ] task reminders                               │
│ [ ] tool search usage                            │
│ [ ] token usage                                  │
│ [ ] total tokens                                 │
│ [ ] budget (USD)                                 │
│ [ ] output token usage                           │
└──────────────────────────────────────────────────┘
```

- `[x]` = enabled (not suppressed), `[ ]` = blocked (default). Checkbox ON means the reminder runs.
- **Master row** at top: `[ ]` all blocked, `[x]` all enabled, `[~]` mixed. Enter on master: if any family is blocked → enable all; else block all.
- Selected row highlighted (same selected-row treatment as the drawer's header/selection styling).
- Toggles take effect on the next attachment cycle; no confirmation step.

## Error handling

- Deny helpers null-guard the global and fall back to default-deny; the attachment pipeline can never throw because of this package.
- Toggle handler mutates the deny object and bumps a version counter in the same global so the drawer re-renders through the existing refresh interval pattern (`Yc(…,100)`), matching how the ported drawer refreshes.

## Testing

- `tests/test_reminders_manager.py` following the repo's package-test pattern: manifest integrity (payload sha256/lengths, marker counts against the stock module), build success against stock 2.1.199 **alone** and **together with the ported hidden-context-drawer** (composition is a tested invariant, not an assumption), postconditions for the deny helpers and drawer globals.
- `manualSmoke.required: true` — TUI: arrow down past Hidden Context to Reminders, open, toggle `todo reminders` on, confirm a todo reminder attachment appears on a following turn, toggle off, confirm it stops, x closes.

## Out of scope

- Persistence of toggle state across sessions.
- Retroactive delivery of reminders suppressed earlier in the session.
- Transcript sanitation of historical sessions.
- Any change to families UAS doesn't already suppress.

## To fill in after the drawer port lands

1. Final anchor table for the footer/UI splices (exact strings, oldRangeSha256, lengths), chosen in the gaps left by the port's claimed ranges.
2. Stock 2.1.199 module `contentSha256`/`contentLength` entries (known: module sha `e30c857c…`, length 18593981).
3. Whether the port's ranges need to shrink anywhere to leave an in-scope anchor gap — coordinated edit, we control both packages.
