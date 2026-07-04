# Thinking Text Drawer Design

Status: approved for implementation planning after user review
Date: 2026-07-03
Project: ClaudeMonkey / Claude Code binary patch package
Target family: Claude Code 2.1.201 first, with exact binary identity validation

## Goal

Create a new ClaudeMonkey patch package modeled on `hidden-context-drawer`, but for thinking text.

The drawer is a pop-up layer the user can open whenever. It must not change the main chat setup, normal chat rendering, request assembly, JSONL history, or model-visible context. Its job is to surface as much raw/structured thinking text as the harness already has or receives.

## Product principle

The drawer should prefer real text over derived progress.

Priority order:

1. Structured thinking blocks that Ctrl-O transcript mode can already show.
2. Live raw `thinking_delta.thinking` chunks, when the stream exposes them.
3. Virtual/cancel-salvaged thinking blocks created from in-flight thinking text.
4. Redacted/signature/estimated-token evidence only as secondary markers.

Estimated thinking-token events are not the product. They are useful only when no raw or structured text exists.

## Existing evidence

The live binary is Claude Code `2.1.201`. The existing `hidden-context-drawer` package targets `2.1.199`, and its exact anchors do not carry forward to `2.1.201`; a new thinking drawer package needs fresh anchors.

Relevant observed seams in `2.1.201`:

- Ctrl-O is `app:toggleTranscript`.
- Transcript/verbose rendering includes assistant content blocks with `type: "thinking"`.
- Normal mode suppresses `thinking` and `redacted_thinking` blocks unless transcript/verbose is active.
- The thinking renderer displays `param.thinking`.
- Streaming handlers process `content_block_delta` with `delta.type === "thinking_delta"`; if `delta.thinking` is present, that is the earliest raw text source found so far.
- Claude Code also creates `system/thinking_tokens` estimate events from thinking deltas. Those are not raw text, but can be shown as secondary progress evidence.
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

### 2. Thinking frame layer

Maintain a global display frame, for example `__CODEX_THINKING_TEXT_DRAWER_FRAME_V1__`.

The frame should contain ordered entries with fields like:

- `key`
- `source`: `live`, `structured`, `salvaged`, `redacted`, or `estimate`
- `timestamp` / turn time where available
- `messageId` / request ID / block index where available
- `text`
- `charCount`
- `estimatedTokens` / `estimatedTokensDelta` where applicable
- `lines` for drawer rendering
- `status`: `provisional`, `final`, or `secondary`

The frame is display-only state. It is not written back into messages, JSONL, prompt context, or API payloads.

### 3. Collector layer

Feed the frame from multiple seams:

- **Canonical structured source:** scan assistant message content blocks for `{ type: "thinking", thinking: ... }`, matching what Ctrl-O can reveal.
- **Live source:** append `thinking_delta.thinking` chunks while streaming, before they are summarized into progress estimates.
- **Salvage source:** capture virtual thinking blocks created from in-flight `_t?.thinking` on cancellation/interruption.
- **Secondary evidence source:** record `redacted_thinking`, `thinking_signature`, and `system/thinking_tokens` as markers when raw text is not present.

## Data flow

### During streaming

When a thinking block starts, create or update a provisional live entry if the stream exposes enough identity to do so.

When `content_block_delta.thinking_delta.thinking` arrives, append that raw text immediately to the active provisional entry.

When only `estimated_tokens` arrives, update a secondary estimate entry rather than pretending text exists.

When redacted thinking appears, show a compact marker that a redacted thinking block exists.

### When assistant content lands

Scan assistant messages for structured `thinking` blocks. These are canonical because they are what Ctrl-O transcript mode already knows how to render.

For each structured block:

- if it matches a provisional live entry, replace or finalize that entry;
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

If live chunks lack a stable ID, use a provisional per-active-stream key.

When final structured text arrives:

- if it starts with, contains, or closely matches the provisional text, replace the provisional entry with the structured final entry;
- if the texts disagree, preserve both entries and label them clearly (`live partial`, `structured final`).

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
- character count and/or estimated token count;
- wrapped thinking text when available;
- compact secondary rows for redacted or estimate-only evidence.

Display order should be most-recent turn first, matching the hidden-context drawer style. Within a turn, in-progress live text may appear before finalization; once structured text arrives, the final/canonical entry should be preferred.

## Failure handling

- If no raw or structured text is available, the drawer may show estimate/redaction evidence only if present.
- If only token estimates exist, label them as estimates and do not call them raw thinking.
- If only redacted thinking exists, show redacted markers and do not fabricate content.
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

Because the shared footer-drawer framework is not yet ready, this package should initially own its drawer seams directly rather than depending on an unimplemented composition framework.

## Testing plan

### Static validation

- `claude_monkey inspect-binary` confirms target identity.
- Package validation resolves all operations against the target binary.
- Postconditions verify helper globals, footer label, drawer title, close behavior, and collector hooks.
- Existing `hidden-context-drawer` package files remain untouched.

### Fixture tests

Add package-level tests for collector helpers where feasible:

- structured `thinking` block becomes a drawer entry;
- live `thinking_delta.thinking` chunks append immediately;
- final structured thinking replaces matching provisional live text;
- mismatched live/final text preserves both entries;
- redacted-only and estimate-only events produce secondary rows;
- empty thinking strings do not create noisy rows.

### Manual smoke

Against a copied patched binary:

1. Run a prompt/model configuration selected to produce Ctrl-O-visible thinking.
2. Verify the drawer can be opened without Ctrl-O.
3. Verify thinking text appears in the drawer as a pop-up layer.
4. Verify Ctrl-O still works and still shows transcript thinking.
5. Verify normal chat remains unchanged.
6. Verify no JSONL/request/context mutation occurs.
7. If possible, observe whether live text appears before final assistant text.

## Out of scope

- Changing main chat rendering.
- Making thinking always visible in normal transcript rows.
- Changing Ctrl-O transcript behavior.
- Changing thinking request parameters such as `thinking.display` unless a later package explicitly targets that.
- Recovering raw text that the harness never receives.
- Shared multi-drawer composition framework extraction.
