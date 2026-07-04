# Thinking Text Drawer Design

Status: approved for implementation planning after user review
Date: 2026-07-03
Project: ClaudeMonkey / Claude Code binary patch package
Target family: Claude Code 2.1.201 first, with exact binary identity validation

## 2026-07-04 smoke correction

Manual smoke showed that derived progress/marker rows make the drawer noisy and
misleading. The drawer must show actual captured thinking text only: structured
thinking, live raw `thinking_delta.thinking` text, and cancel-salvaged thinking.
Redacted-only, signature-only, and thinking-token estimate-only events must not
create drawer rows. Internal merge state may use live/final concepts, but visible
drawer headers must not expose `provisional`, `final`, or progress copy.

## Goal

Create a new ClaudeMonkey patch package modeled on `hidden-context-drawer`, but for thinking text.

The drawer is a pop-up layer the user can open whenever. It must not change the main chat setup, normal chat rendering, request assembly, JSONL history, or model-visible context. Its job is to surface as much raw/structured thinking text as the harness already has or receives.

“Open whenever” is a hard product invariant: the Thinking footer target must be available in interactive footer mode even when no thinking has been captured yet. The empty drawer state is `No thinking captured yet`. Flash/unread state indicates new captured thinking, but availability must not depend on Ctrl-O, transcript mode, or a `frame.visible` gate.

## Product principle

The drawer should prefer real text over derived progress.

Priority order:

1. Structured thinking blocks that Ctrl-O transcript mode can already show.
2. Live raw `thinking_delta.thinking` chunks, when the stream exposes them.
3. Virtual/cancel-salvaged thinking blocks created from in-flight thinking text.
4. Redacted/signature/estimated-token events are not thinking text and must not create drawer rows.

Estimated thinking-token, signature, and redacted-only events are not the product. They may remain stock internal events, but this drawer must not render them as rows.

## Existing evidence

The live binary is Claude Code `2.1.201`. The existing `hidden-context-drawer` package targets `2.1.199`, and its exact anchors do not carry forward to `2.1.201`; a new thinking drawer package needs fresh anchors.

Relevant observed seams in `2.1.201`:

- Ctrl-O is `app:toggleTranscript`.
- Transcript/verbose rendering includes assistant content blocks with `type: "thinking"`.
- Normal mode suppresses `thinking` and `redacted_thinking` blocks unless transcript/verbose is active.
- The thinking renderer displays `param.thinking`.
- Streaming handlers process `content_block_delta` with `delta.type === "thinking_delta"`; if `delta.thinking` is present, that is the earliest raw text source found so far.
- Claude Code also creates `system/thinking_tokens` estimate events from thinking deltas. Those are not raw text and must not be shown as Thinking drawer rows.
- On cancel, the app may create a virtual thinking block from in-flight `_t?.thinking` when thinking had started.

## Architecture

The package has three layers.

### 1. Drawer UI layer

Reuse the hidden-context drawer pattern:

- footer selectable item;
- open/selected state;
- bottom overlay drawer;
- scroll state;
- x-only close behavior;
- availability/flash indicator;
- no Escape close unless a future design explicitly changes the drawer interaction model.

The drawer title should be ` Thinking `. The footer label can be `Thinking`.

Unlike `hidden-context-drawer`, the Thinking footer item is always available while the interactive footer is active. Captured entries affect unread/flash text and counts, not whether the drawer can be opened.

### 2. Thinking frame layer

Maintain a global display frame, for example `__CODEX_THINKING_TEXT_DRAWER_FRAME_V1__`.

The frame should contain ordered entries with fields like:

- `key`
- `source`: `live`, `structured`, or `salvaged` for drawer-visible entries
- `timestamp` / turn time where available
- `messageId` / request ID / block index where available
- `text`
- `charCount`
- `lines` for drawer rendering
- internal merge status when useful, but not as visible drawer copy

The frame is display-only state. It is not written back into messages, JSONL, prompt context, or API payloads.

### 3. Collector layer

Feed the frame from multiple seams:

- **Canonical structured source:** scan assistant message content blocks for `{ type: "thinking", thinking: ... }`, matching what Ctrl-O can reveal.
- **Live source:** append `thinking_delta.thinking` chunks while streaming, before they are summarized into progress estimates.
- **Salvage source:** capture virtual thinking blocks created from in-flight `_t?.thinking` on cancellation/interruption.
- **Non-text events:** preserve stock handling for `redacted_thinking`, `thinking_signature`, and `system/thinking_tokens`, but do not create Thinking drawer rows from them.

Structured collection must run at a parent assistant-message/content-list seam that sees assistant content blocks before normal-mode rendering suppresses `thinking` and `redacted_thinking`. Do not rely on the thinking renderer as the only collection source. The collector must update display-only frame state whether or not Ctrl-O is active.

## Data flow

### During streaming

When a thinking block starts, create or update an internal live entry if the stream exposes enough identity to do so.

When `content_block_delta.thinking_delta.thinking` arrives, append that raw text immediately to the active live entry.

When only `estimated_tokens` arrives, do not create a drawer row; token estimates are not thinking text.

When redacted thinking appears, do not create a drawer row; a redaction marker is not captured thinking text.

### When assistant content lands

Scan assistant messages for structured `thinking` blocks at a content-list seam before the normal renderer decides whether transcript/verbose mode is active. These blocks are canonical because they are what Ctrl-O transcript mode already knows how to render, but collection must not be Ctrl-O-gated.

For each structured block:

- if it matches a live entry, replace/merge that entry internally;
- otherwise add it as a final structured entry.

### On cancel/interruption

If the app creates a virtual thinking block from in-flight thinking text, capture it as a salvaged entry. Label it as interrupted/salvaged rather than canonical final thinking.

## Dedupe and merge policy

Prefer stable IDs when available:

- message UUID;
- content block index;
- request ID;
- stream/block ID;
- session ID.

If live chunks lack a stable ID, use a per-active-stream key.

When final structured text arrives:

- merge live and structured entries only when stable identity matches, or when exactly one active live entry exists for the same turn and normalized structured text contains the normalized live text;
- on merge, preserve provenance, for example `sources: ["live", "structured"]`;
- if identity is absent, ambiguous, or text disagrees, preserve both entries with source labels;
- do not use fuzzy or Levenshtein-style “close match” dedupe.

Never silently discard unique thinking text.

## UI behavior

The drawer is an overlay layer only.

It must not:

- change normal chat rendering;
- make thinking blocks visible in the main chat;
- alter Ctrl-O transcript behavior;
- inject rows into the transcript list;
- mutate request or persistence data.

Entries should show:

- source label;
- optional timestamp/turn label;
- character count;
- wrapped thinking text when available.

They should not show progress-only, signature-only, redacted-only, or estimate-only rows.

If there are no entries, the drawer renders `No thinking captured yet`.

Display order should be most-recent turn first, matching the hidden-context drawer style. Within a turn, live text may appear before structured text arrives; once structured text arrives, the canonical structured text should be preferred internally without exposing progress/finality status as drawer copy.

## Failure handling

- If no raw or structured/salvaged text is available, render `No thinking captured yet`.
- If only token estimates exist, do not create drawer rows.
- If only redacted thinking exists, do not create drawer rows and do not fabricate content.
- If live and final text disagree, keep both with source labels.
- If a required anchor is missing in the target binary, package validation must fail closed.
- If the live stream seam proves too risky for the first implementation, the package can ship a structured-only first slice only with explicit user approval during planning.

## Package strategy

This should be a new package, not a modification of `hidden-context-drawer`.

Package name: `thinking-text-drawer`.

It should reuse payload patterns from `packages/hidden-context-drawer`, but with fresh 2.1.201 anchors and helper names, for example:

- `__codexTTD...` helper prefix;
- `__CODEX_THINKING_TEXT_DRAWER_FRAME_V1__` global frame;
- target module `/$bunfs/root/src/entrypoints/cli.js`;
- exact source identity for Claude Code 2.1.201.

All 2.1.199 `hidden-context-drawer` exact anchors miss against Claude Code 2.1.201, so fresh anchors are not optional.

Because the shared footer-drawer framework is not yet ready, this package should initially own its drawer seams directly rather than depending on an unimplemented composition framework.

The initial `thinking-text-drawer` package is a standalone direct footer/overlay seam owner. It is expected to conflict with any other direct footer drawer package targeting the same Claude Code source until structured splices or a reviewed footer-drawer framework exists. Do not claim compatibility with a future `hidden-context-drawer` or `reminders-manager` port unless a build matrix proves non-overlap.

## Testing plan

### Static validation

- `claude_monkey inspect-binary` confirms target identity.
- Package validation resolves all operations against the target binary.
- Postconditions verify helper globals, footer label, drawer title, close behavior, and collector hooks.
- Existing `hidden-context-drawer` package files remain untouched.
- Tests verify x-only drawer close behavior: no Escape close path, no Escape copy, `footer:clearSelection` does not close Thinking, and `footer:close` does.

### Fixture tests

Add package-level tests for collector helpers where feasible:

- structured `thinking` block becomes a drawer entry;
- live `thinking_delta.thinking` chunks append immediately;
- final structured thinking replaces matching live text;
- mismatched live/final text preserves both entries;
- redacted-only, signature-only, and estimate-only events do not create drawer rows;
- empty thinking strings do not create noisy rows.
- long thinking text is preserved in captured frame data; rendering may viewport/wrap/cap displayed lines, but stored captured text is not silently truncated unless the UI labels truncation explicitly.

### Manual smoke

Against a copied patched binary:

1. Run a prompt/model configuration selected to produce Ctrl-O-visible thinking.
2. Verify the drawer can be opened without Ctrl-O.
3. Verify thinking text appears in the drawer as a pop-up layer.
4. Verify Ctrl-O still works and still shows transcript thinking.
5. Verify normal chat remains unchanged.
6. Verify no JSONL/request/context mutation occurs with before/after transcript or request-state checks, not package validation alone.
7. If possible, observe whether live text appears before final assistant text.

## Out of scope

- Changing main chat rendering.
- Making thinking always visible in normal transcript rows.
- Changing Ctrl-O transcript behavior.
- Changing thinking request parameters such as `thinking.display` unless a later package explicitly targets that.
- Recovering raw text that the harness never receives.
- Shared multi-drawer composition framework extraction.
