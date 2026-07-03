# Reminders Manager — Design

Runtime toggle panel for suppressed reminder/accounting attachment families, as a second footer drawer alongside Hidden Context.

**Status:** Draft. The `hidden-context-drawer` 2.1.199 port has landed (v0.1.12, stock-anchored, source sha `e3cb61ab…`). Composition mechanisms below are verified against the stock 2.1.199 module bytes and the port's claimed ranges; the exact anchor table (final substrings, sha256, lengths) is implementation-plan work.

## Purpose

`upstream-attachment-suppression` blocks seven recurring reminder/accounting attachment families unconditionally at build time. This package is the runtime-managed alternative: the same deny set, plus a footer drawer UI ("Reminders") so families can be unblocked or re-blocked while a session is running. (UAS itself stays maintained as the static all-off option; see Package shape.)

- All families **blocked by default** at session start (identical to current suppression behavior).
- Toggling a family **on** stops suppressing it from the next attachment-generation cycle onward. Previously suppressed occurrences are not retroactively delivered.
- Toggling **off** resumes suppression from the next cycle.
- State is **session-only**: it lives in `globalThis` and lasts for the OS process lifetime. No persistence; restarting the process returns to all-blocked. A `/resume` within a still-running process keeps the current toggle state.

## Package shape

Normal ClaudeMonkey V1.5 schema-v2 package: `packages/reminders-manager/`.

- Anchored on **stock Claude Code 2.1.199** (`sha256 e3cb61ab…`), like every other package in this repo.
- Stacks with other enabled packages in a single `build_patchset_v15` build. Composition requirement: **all splice ranges disjoint from the ported `hidden-context-drawer` ranges** (and from `fable-fallback`, `normal-channel-hidden-context` if enabled). Install either package alone or both together; the profile's `enabledPatches` list drives the stack.
- **Separate package from `upstream-attachment-suppression`, which stays maintained.** UAS remains the static all-off option; `reminders-manager` is the runtime-toggle drawer option. They **conflict** (both own the `ug`/`Hze` seams), so a profile enables one or the other, never both — documented in both READMEs, same pattern as the existing drawer/normal-channel conflict note. This package does not deprecate or replace UAS.

## Families

Seven rows, mapping generator labels and attachment object types:

| Row label | Generator label (`ug`) | Attachment type (`Hze`) |
|---|---|---|
| todo reminders | `todo_reminders` (shared) | `todo_reminder` |
| task reminders | `todo_reminders` (shared) | `task_reminder` |
| tool search usage | `tool_search_usage_reminder` | `tool_search_usage_reminder` |
| token usage | `token_usage` | `token_usage` |
| total tokens | `total_tokens_reminder` | `total_tokens_reminder` |
| budget (USD) | `budget_usd` | `budget_usd` |
| output token usage | `output_token_usage` | `output_token_usage` |

**Shared-label semantics (verified in stock 2.1.199):** `ug("todo_reminders", f)` where `f = () => Av() ? N4m(…) : L4m(…)` — one generator label produces both `todo_reminder` and `task_reminder` attachment types. The label gate therefore denies `todo_reminders` **iff both rows are denied**; when only one row is denied, the generator runs and the `Hze` object filter drops just the denied type. Exact per-row suppression parity is preserved.

## Components

### 1. Runtime deny state

`globalThis.__CODEX_REMINDERS_MANAGER_V1__` — an object `{ deny: { <family>: boolean }, version: number }` initialized with all seven families `true` (denied). The init guard (`??=` pattern) is **duplicated in every splice that reads the state** — deny seams *and* UI splices — because `ug`/`Hze` bodies only run when an attachment cycle fires: the drawer can open before any cycle has run, and must still render the true all-blocked default rather than reading `undefined`. Missing/undefined state falls back to default-deny everywhere (fail closed — a broken UI never un-suppresses by accident, and never crashes the attachment path).

### 2. Deny seams (functional half)

Same two splices as `upstream-attachment-suppression`, re-authored:

- **`ug(e,t)` label gate** — `__codexRMDenyLabel(e)` looks up the label's family in the runtime deny object; denied → return `[]` before the generator and its compute-duration telemetry run. For the shared `todo_reminders` label: gate iff **both** todo and task rows are denied (see Families).
- **`Hze(...)` object filter** — `__codexRMDenyAttachment(e)` filters denied attachment objects (per-type, so todo/task split correctly) before `tengu_attachments` telemetry and `li(...)` row construction.

Identical structure to the UAS payloads except the hardcoded boolean chains become runtime lookups. Everything UAS intentionally leaves intact (safety, permission, hook, file-state, plan-mode, team, memory, diagnostics, queued-command, user file references) stays intact.

### 3. Footer target (UI half) — verified seam mechanisms

A `reminders` footer target alongside the drawer's `hiddenContext` target. The drawer port (v0.1.12) claims tight expressions, not whole regions — each mechanism below anchors on **verified-unclaimed stock text**, so both packages install independently and stack. All quoted anchors were checked against the stock 2.1.199 module dump (`.development/tmp-module0-2.1.199.js`, sha `e30c857c…`) and against the port's claimed ranges in `packages/hidden-context-drawer/patch.json`.

| Concern | Drawer's claim | Reminders' disjoint anchor (verified unclaimed) |
|---|---|---|
| Footer targets list | full `ji=Ro.useMemo(...)` statement (op 03) | anchor downstream of the drawer's range, where the targets list is consumed; append `"reminders"` after `"hiddenContext"` via the same globals pattern the drawer's payload uses for its own entry |
| Selection flag | `let qb=…,Ap=Du==="frame";function Sf` claimed to the last byte (op 10) | **no flag op at all** — reminders checks `Du==="reminders"` inline at its own splice sites |
| Availability bar | entire 1988-byte bar function body (op 16) | `le=[...[]]` — unique in stock, *upstream* of the drawer's claimed range; reminders pushes its segment into the arrays the claimed function already renders |
| openSelected switch | `case"tmux":break;…case"frame":{…}` (op 13, starts exactly at `case"tmux"`) | the unclaimed `case"workflows"` tail immediately before `case"tmux"` — insert `case"reminders":…` there |
| Up/down/enter keys | function *bodies* of `By`/`Jk` (op 12) | the footer actions map — `"footer:up":By,"footer:down":Jk` — a single unclaimed site; wrap the entries: reminders-drawer-open routes to its row cursor, else falls through to stock/drawer behavior |
| Bottom overlay render | full `qnc()` body (op 15) | its **caller sites** — two unclaimed memo-init expressions `ce=zd.jsx(qnc,{})` / `Q=zd.jsx(qnc,{})`; render the reminders panel as its own sibling function there, reusing the port's poll/memo *pattern* (`Zc(()=>n(Date.now()),100)`), not its function |

- Arrow down past Hidden Context reaches Reminders; open via footer openSelected.
- In the open drawer: up/down moves the row cursor, **enter/space toggles the row**, `x` closes (x-only, matching the drawer's convention).
- Open-state global: `globalThis.__CODEX_REMINDERS_DRAWER_OPEN_V1__`.
- The final anchor table (exact substrings, `oldRangeSha256`, lengths) is written in the implementation plan; `_check_overlaps` in a stacked build is the mechanical enforcement of the disjointness claimed above.

**General slice-model limit (for future package pairs, not this one):** the narrow-slice approach binds only when two packages must rewrite the *same single expression* with no upstream/downstream data path around it. Every seam here had one; a future pair that doesn't will need a coordinated payload (one package rendering the other's state via a null-guarded global), which is the pattern to check first.

### 4. Drawer UI

Bottom overlay rendered as a sibling panel at the `qnc()` caller sites (see seam table), visual language matching Hidden Context:

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
- Note: the hidden-context drawer is a read-only viewer (up/down scrolls, x closes). The row cursor + enter/space toggle + tri-state master is **net-new interaction** for this drawer family — it reuses the port's overlay/poll/close patterns but its keyboard model has no smoke-tested precedent, hence the fuller manual smoke below.

## Error handling

- Deny helpers null-guard the global and fall back to default-deny; the attachment pipeline can never throw because of this package.
- Toggle handler mutates the deny object and bumps `version` in the same global; the reminders panel re-renders through its own 100ms poll/memo function (same pattern as the port's `Zc(()=>n(Date.now()),100)` in payload 15, separate function).
- Because the bar anchor (`le=[...[]]`) is upstream of the bar function, the pushed segment renders under stock *or* drawer-patched downstream code — standalone install needs no drawer present.

## Testing

- `tests/test_reminders_manager.py` following the repo's package-test pattern: manifest integrity (payload sha256/lengths, marker counts against the stock module), postconditions for the deny helpers and drawer globals.
- Composition builds are tested invariants, not assumptions:
  1. `reminders-manager` alone against stock 2.1.199;
  2. stacked with `hidden-context-drawer` (v0.1.12);
  3. stacked with `normal-channel-hidden-context` (its 2.1.199 target claims the `Jur` seam — disjoint from both the deny seams and every UI anchor above);
  4. stacked with `upstream-attachment-suppression` **must fail** with `patch_conflict` on the `ug`/`Hze` ranges (the documented conflict, asserted).
- `manualSmoke.required: true` — TUI: open Reminders before any attachment cycle and confirm all rows render blocked (init-guard check); arrow down past Hidden Context to Reminders, toggle `todo reminders` on, confirm a todo reminder appears on a following turn; toggle off, confirm it stops; master row cycles all-on/all-off; x closes; with both drawers installed, verify Hidden Context still opens/scrolls/closes unchanged.

## Out of scope

- Persistence of toggle state across sessions.
- Retroactive delivery of reminders suppressed earlier in the session.
- Transcript sanitation of historical sessions.
- Any change to families UAS doesn't already suppress.

## Deferred to the implementation plan

1. Final anchor table: exact substrings, `oldRangeSha256`, lengths for each op in the seam table above (module identity: sha `e30c857c…`, length 18593981).
2. Row-cursor state placement (component state vs. the manager global) and drawer height/scroll if the 8 rows plus header exceed the overlay budget on short terminals.
3. UI copy/labels final pass.
