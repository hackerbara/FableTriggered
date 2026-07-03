# Upstream attachment suppression design

Date: 2026-07-02  
Workspace: `/Users/MAC/Documents/Claude-patch`  
Target first: Claude Code `2.1.199` on macOS arm64  
Status: superseding design for `reminder-suppression`

## Decision summary

The previous `reminder-suppression` package patches attachment-to-model-message renderers. That is too late for the product goal.

The corrected goal is stronger:

> Selected annoying attachment records should never become transcript rows, never enter request assembly, never render in chat, and never appear in the Hidden Context drawer.

This design supersedes `packages/reminder-suppression` with an upstream suppression package that prevents selected attachment generators from producing objects at all, then keeps a second guard before Claude Code wraps any remaining attachment object as a `{ type: "attachment", attachment: ... }` record.

## Evidence from the current binary

Current live `claude` is `2.1.199 (Claude Code)` at:

```text
/Users/MAC/.local/share/claude/versions/2.1.199
sha256 e3cb61abc8a2ec7b98976cee1ffdde5a3fa755c9990bc8d688cd89290e0dcec0
size 232155536
```

The current attachment lifecycle in the extracted main module is:

```text
W9l(...)  computes attachment objects through ug(label, generator)
ug(...)   can log generator label/count/size telemetry after computing attachments
Hze(...)  awaits W9l, logs active attachment types, then yields li(c,o)
li(e,...) returns { attachment:e, type:"attachment", uuid, timestamp }
lxc(..., K, ...) appends K after the user message in the turn message list
zsr(...) later converts persisted attachment rows into model-visible messages
Jur(...) later hides selected attachment rows from transcript rendering
```

The row-construction seam is upstream of `li()`:

```js
async function*Hze(e,t,n,r,o,s,i,a){
  let l=await W9l(e,t,n,r,s,i,a);
  if(l.length===0)return;
  G("tengu_attachments",{attachment_types:l.map((c)=>c.type)});
  for(let c of l)yield li(c,o)
}
```

Filtering inside `zsr(...)`, `Jur(...)`, the normal-channel projection, or the Hidden Context drawer is too late because a transcript attachment record can already exist.

Filtering only inside `Hze(...)` is also not strict enough for the literal "never anywhere" invariant because `ug(...)` may already have computed denied attachments and emitted aggregate telemetry. The primary seam must therefore be before denied generator execution, with `Hze(...)` retained as a fail-closed row-construction guard.

## Scope

In scope:

- Create a new V1.5 graph-repack package that supersedes `reminder-suppression`.
- Target Claude Code `2.1.199` first.
- Add a tiny deny predicate near the attachment helpers.
- Suppress denied `ug(label, generator)` labels before their generators run or their aggregate telemetry fires.
- Filter the `W9l(...)` attachment-object array before `Hze(...)` logs active attachment types or wraps items with `li(...)`.
- Ensure denied objects do not become transcript rows, model request messages, chat rows, normal-channel projected rows, or Hidden Context drawer entries.
- Ensure denied objects are not counted in attachment generator telemetry.
- Add tests that prove the package targets the upstream seam, not `zsr(...)` or render-only paths.

Out of scope:

- Mutating existing session JSONL to remove old rows.
- Hiding rows after they are created.
- Changing request assembly for rows that already exist in historical transcripts.
- Suppressing safety, permission, file-state, hook, plan-mode, team, memory, diagnostics, or user-provided context unless separately approved.
- Reworking the Hidden Context drawer UI.

## Suppression policy

Initial denylist should match the existing narrow reminder-suppression intent:

```text
todo_reminder
task_reminder
tool_search_usage_reminder
token_usage
total_tokens_reminder
budget_usd
output_token_usage
```

These are recurring nudge/accounting reminders. They are not user content, tool results, file-state protection, hook context, or safety/permission context.

At the generator-label level, the matching denylist is:

```text
todo_reminders
tool_search_usage_reminder
total_tokens_reminder
token_usage
budget_usd
output_token_usage
```

`todo_reminders` covers both `todo_reminder` and `task_reminder` outputs because the current generator chooses between the TodoWrite reminder and task-tool reminder families.

Explicitly keep:

```text
hook_success
hook_additional_context
hook_blocking_error
hook_stopped_continuation
command_permissions
agent_mention
critical_system_reminder
edited_text_file
opened_file_in_ide
plan_mode
plan_mode_exit
plan_mode_reentry
auto_mode
auto_mode_exit
team_context
memory_update
mcp_instructions_delta
deferred_tools_delta
diagnostics
lsp_diagnostics
queued_command
file / pdf / directory references
```

The denylist should be implemented as a small named predicate so future additions are deliberate and testable.

## Architecture

### New package

Create a new package, for example:

```text
packages/upstream-attachment-suppression/
  README.md
  patch.json
  payloads/filter-before-li-2.1.199.js
```

The implementation must mark `packages/reminder-suppression` as superseded in its README so users do not install the older too-late package by mistake.

### Patch seam

Patch two nearby attachment-generation seams:

1. `ug(label, generator)`: primary pre-compute suppression. Denied labels return `[]` before the generator runs and before `tengu_attachment_compute_duration` telemetry can record label/count/size for denied families.
2. `Hze(...)`: row-construction safety guard. Denied attachment types are filtered out before `tengu_attachments` and before `li(c,o)` creates transcript rows.

The `Hze(...)` guard is not the primary privacy boundary; it is the belt after the upstream generator gate.

Conceptual replacement:

```js
function __codexUASDropLabel(e){
  return e === "todo_reminders" ||
    e === "tool_search_usage_reminder" ||
    e === "total_tokens_reminder" ||
    e === "token_usage" ||
    e === "budget_usd" ||
    e === "output_token_usage";
}

function __codexUASDropAttachment(e){
  return e && (
    e.type === "todo_reminder" ||
    e.type === "task_reminder" ||
    e.type === "tool_search_usage_reminder" ||
    e.type === "token_usage" ||
    e.type === "total_tokens_reminder" ||
    e.type === "budget_usd" ||
    e.type === "output_token_usage"
  );
}

async function ug(e,t){
  if (__codexUASDropLabel(e)) return [];
  let n = Date.now();
  // preserve original ug body
}

async function*Hze(e,t,n,r,o,s,i,a){
  let l = await W9l(e,t,n,r,s,i,a);
  l = l.filter((c) => !__codexUASDropAttachment(c));
  if (l.length === 0) return;
  G("tengu_attachments", { attachment_types: l.map((c) => c.type) });
  for (let c of l) yield li(c,o);
}
```

Minified payloads can inline the predicates, but the package should still contain distinctive markers such as `__codexUASDropLabel` and `__codexUASDropAttachment` for validation and future audit.

### Why this seam

Filtering at `ug(...)` is earlier than denied attachment-object computation. Filtering again at `Hze(...)` is earlier than `li(...)`, which is where transcript attachment rows are created. Together they give the invariant we actually need:

```text
denied generator label
  -> generator not called
  -> no denied attachment object
  -> no attachment generator count/size telemetry for the denied family
  -> Hze guard catches any denied object that appears through an unexpected path
  -> not logged as active attachment telemetry
  -> not wrapped by li()
  -> no {type:"attachment"} row
  -> no JSONL transcript row
  -> no zsr model conversion
  -> no Jur/render projection
  -> no Hidden Context drawer entry
```

### Direct `li(...)` audit

Before implementation finishes, audit direct `li(...)` call sites. Known direct emissions include hook stopped continuation and command permission cases. The package must prove no denied reminder family is emitted through a direct `li({ type: ... })` path that bypasses `Hze(...)`.

This is a hard precondition, not an optional inspection. The test suite must fail closed if a supported target contains a direct denied-family `li({type:"todo_reminder"...})`, `li({type:"task_reminder"...})`, or equivalent call outside the approved `ug(...)`/`Hze(...)` path.

If any denied family bypasses `Hze(...)`, add a second upstream guard at that direct creation site. Do not fall back to renderer suppression.

### Coverage matrix

The implementation plan must preserve this matrix and attach a static or fixture proof to each row:

| Path | Denied families possible? | Required proof |
|---|---:|---|
| Regular prompt path | Yes | `ug(...)` label gate plus `Hze(...)` fixture |
| Slash-command pre-expansion path | Yes, because attachments are precomputed and passed into command processing | `Hze(...)` fixture and static call-site proof |
| Queued command path | Keep `queued_command`; denied reminders still flow through `W9l(...)` | label gate proves denied reminder generators do not run |
| Main-agent loop / post-tool turns | Yes | same `Hze(...)` call-site proof around the loop that yields attachments |
| Subagent/background turns | Possibly, depending on context options | source grep showing they route through `Hze(...)` or an explicit no-denied-family proof |
| Historical sessions | Already-created rows may exist | out of scope unless a separate transcript sanitation tool is approved |

## Tests and verification

### Static package tests

Add or update `tests/test_reference_packages.py` to verify:

- the new package validates against the live/current `2.1.199` source identity;
- payload contains `__codexUASDropLabel` and `__codexUASDropAttachment` or equivalent markers;
- payload gates denied generator labels before `let n=Date.now()` in `ug(...)`;
- payload filters before `yield li(c,o)`;
- payload does not patch `zsr(...)`, `Jur(...)`, normal-channel projection, or Hidden Context drawer code;
- denied label strings and denied type strings are present in the upstream predicates;
- kept safety/file/hook/plan type strings are not present in the deny predicate.
- no direct denied-family `li({ type: ... })` construction exists outside the approved guarded path for the target module.

### Fixture behavior test

Extract/evaluate the helper predicate and assert:

- denied generator labels return true;
- denylist types return true;
- `hook_additional_context`, `hook_blocking_error`, `edited_text_file`, `critical_system_reminder`, `plan_mode`, `memory_update`, `diagnostics`, and `queued_command` return false.

Run a mandatory transformed-function fixture test around `ug(...)` and `Hze(...)` logic:

- stub a denied generator and assert it is not called;
- spy on `G(...)` and assert denied families are not included in `tengu_attachment_compute_duration` or `tengu_attachments`;
- stub `W9l(...)` to return mixed denied/kept attachments;
- spy on `li(...)` and assert denied objects are never wrapped or yielded;
- assert kept attachment objects still pass through.

### Build verification

For a copied binary build:

```text
validate-package upstream-attachment-suppression against 2.1.199
build copied binary through ClaudeMonkey V1.5
inspect graph validation
codesign verify
--version
--help
```

Manual smoke is lower priority than for UI patches because this is not visual, but at least one controlled run should confirm ordinary prompting still works and no denied attachment rows are newly written for a scenario that previously produced them.

The controlled run should capture the session JSONL path before and after the scenario and grep/assert that no new rows contain the denied attachment types.

## Compatibility with other packages

- Compatible in principle with `normal-channel-hidden-context` for future rows: suppressed rows never exist after this package is active, so normal-channel has nothing new to project for them.
- Compatible in principle with future Hidden Context drawer ports for future rows: suppressed rows never exist after this package is active, so the drawer has nothing new to show for them.
- Potential merge conflict with packages that replace the same `Hze(...)` snippet. V1.5 should report conflict rather than silently merge ambiguous replacements.
- Supersedes `reminder-suppression`; do not run both unless the package manager allows it and tests prove it is harmless.

## Migration note

The README should say clearly:

- `reminder-suppression` was a renderer/model-conversion suppression attempt and is deprecated.
- `upstream-attachment-suppression` is the correct package for “never put these rows anywhere.”
- Historical transcripts are not rewritten. The package affects future attachment generation only. Existing denied rows remain in old JSONL unless the user separately approves a transcript sanitation/migration tool.
