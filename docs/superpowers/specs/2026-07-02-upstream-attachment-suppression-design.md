# Upstream attachment suppression design

Date: 2026-07-02  
Workspace: `/Users/MAC/Documents/Claude-patch`  
Target first: Claude Code `2.1.199` on macOS arm64  
Status: superseding design for `reminder-suppression`

## Decision summary

The previous `reminder-suppression` package patches attachment-to-model-message renderers. That is too late for the product goal.

The corrected goal is stronger:

> Selected annoying attachment records should never become transcript rows, never enter request assembly, never render in chat, and never appear in the Hidden Context drawer.

This design supersedes `packages/reminder-suppression` with an upstream suppression package that filters selected attachment objects before Claude Code wraps them as `{ type: "attachment", attachment: ... }` records.

## Evidence from the current binary

Current live `claude` is `2.1.199 (Claude Code)` at:

```text
/Users/MAC/.local/share/claude/versions/2.1.199
sha256 e3cb61abc8a2ec7b98976cee1ffdde5a3fa755c9990bc8d688cd89290e0dcec0
size 232155536
```

The current attachment lifecycle in the extracted main module is:

```text
W9l(...)  computes attachment objects
Hze(...)  awaits W9l, logs attachment types, then yields li(c,o)
li(e,...) returns { attachment:e, type:"attachment", uuid, timestamp }
lxc(..., K, ...) appends K after the user message in the turn message list
zsr(...) later converts persisted attachment rows into model-visible messages
Jur(...) later hides selected attachment rows from transcript rendering
```

The important seam is therefore upstream of `li()`:

```js
async function*Hze(e,t,n,r,o,s,i,a){
  let l=await W9l(e,t,n,r,s,i,a);
  if(l.length===0)return;
  G("tengu_attachments",{attachment_types:l.map((c)=>c.type)});
  for(let c of l)yield li(c,o)
}
```

Filtering inside `zsr(...)`, `Jur(...)`, the normal-channel projection, or the Hidden Context drawer is too late because a transcript attachment record can already exist.

## Scope

In scope:

- Create a new V1.5 graph-repack package that supersedes `reminder-suppression`.
- Target Claude Code `2.1.199` first.
- Add a tiny deny predicate near the attachment helpers.
- Filter the `W9l(...)` attachment-object array before `Hze(...)` logs or wraps items with `li(...)`.
- Ensure denied objects do not become transcript rows, model request messages, chat rows, normal-channel projected rows, or Hidden Context drawer entries.
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

The old `packages/reminder-suppression` remains as historical/deprecated until removed or clearly marked superseded.

### Patch seam

Patch the `Hze(...)` region. The replacement should preserve the original call to `W9l(...)`, but filter the resulting array before telemetry and row construction.

Conceptual replacement:

```js
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

async function*Hze(e,t,n,r,o,s,i,a){
  let l = await W9l(e,t,n,r,s,i,a);
  l = l.filter((c) => !__codexUASDropAttachment(c));
  if (l.length === 0) return;
  G("tengu_attachments", { attachment_types: l.map((c) => c.type) });
  for (let c of l) yield li(c,o);
}
```

Minified payloads can inline the predicate, but the package should still contain a distinctive marker such as `__codexUASDropAttachment` for validation and future audit.

### Why this seam

Filtering at `Hze(...)` is earlier than `li(...)`, which is where transcript attachment rows are created. That gives the invariant we actually need:

```text
suppressed attachment object
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

If any denied family bypasses `Hze(...)`, add a second upstream guard at that direct creation site. Do not fall back to renderer suppression.

## Tests and verification

### Static package tests

Add or update `tests/test_reference_packages.py` to verify:

- the new package validates against the live/current `2.1.199` source identity;
- payload contains `__codexUASDropAttachment` or equivalent marker;
- payload filters before `yield li(c,o)`;
- payload does not patch `zsr(...)`, `Jur(...)`, normal-channel projection, or Hidden Context drawer code;
- denied type strings are present in the upstream predicate;
- kept safety/file/hook/plan type strings are not present in the deny predicate.

### Fixture behavior test

Extract/evaluate the helper predicate and assert:

- denylist types return true;
- `hook_additional_context`, `hook_blocking_error`, `edited_text_file`, `critical_system_reminder`, `plan_mode`, `memory_update`, `diagnostics`, and `queued_command` return false.

If feasible, run a small transformed-module fixture test around `Hze(...)` logic to prove denied objects are filtered before `li` is called.

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

## Compatibility with other packages

- Compatible in principle with `normal-channel-hidden-context`: suppressed rows never exist, so normal-channel has nothing to project for them.
- Compatible in principle with future Hidden Context drawer ports: suppressed rows never exist, so the drawer has nothing to show for them.
- Potential merge conflict with packages that replace the same `Hze(...)` snippet. V1.5 should report conflict rather than silently merge ambiguous replacements.
- Supersedes `reminder-suppression`; do not run both unless the package manager allows it and tests prove it is harmless.

## Migration note

The README should say clearly:

- `reminder-suppression` was a renderer/model-conversion suppression attempt and is deprecated.
- `upstream-attachment-suppression` is the correct package for “never put these rows anywhere.”
- Historical transcripts are not rewritten. The package affects future attachment generation only.
