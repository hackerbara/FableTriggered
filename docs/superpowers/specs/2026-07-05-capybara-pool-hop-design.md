# Capybara Pool-Hop Trigger (Design)

**Date:** 2026-07-05
**Status:** Approved by user (conversation, 2026-07-05).
**Extends:** `packages/capybara-onsen` (see `2026-07-03-capybara-onsen-design.md`)
**Target:** Claude Code 2.1.201 darwin/arm64 (current package pins)

## Goal

When an assistant response contains a trigger phrase (default: "hopping in the
pool" and close variants), the right-wall capybara hops off his rock shelf into
the pool, soaks with only eyes and ears above the waterline (ears still flick),
and climbs back out after ~20 seconds. Two parts, both in this spec:

1. **Detection** — a runtime hook that scans assistant message text for a
   configurable phrase list.
2. **Scene change** — jump-in transition, timed submerged pose, jump-out
   transition, driven by the existing animation clock.

## Decisions (user-confirmed)

- **Phrase list is a generator constant.** A clearly-marked list constant in
  `generate_package.py`, baked into the payload data. Case-insensitive
  substring match. Changing phrases = edit constant, regenerate, rebuild. No
  runtime/env configuration surface.
- **Short transition with splash**, not a hard cut: ~6 baked jump-in frames
  (crouch, mid-air, splash, settle) and ~6 jump-out frames (reverse, sharing
  art where possible).
- **Retriggers queue.** A phrase occurrence while he is already soaking queues
  another full soak: he climbs out, then hops back in for another ~20 s. Each
  occurrence queues one soak (two phrases in one message = two soaks).
- **Detection hook is capybara-onsen's own adjacent anchor** (not a
  fable-fallback piggyback, not the streaming emitter). The package stays
  self-contained and co-builds with fable-fallback.

## Detection hook

One new operation in `packages/capybara-onsen/patch.json` (9 total):

- Anchored adjacent to the assistant-message render switch in
  `/$bunfs/root/src/entrypoints/cli.js` — the same render function
  fable-fallback patches, but at a point where the transcript item is in scope
  and the claimed byte range does **not** overlap fable-fallback's
  `replace_between` claim (`case"assistant":{let A;...` → `case"user":`). The
  builder's `check_planned_conflicts` must pass with both packages enabled.
- Injects a guarded one-liner: when the item is an assistant message, call
  `__coOnAssistantText(text, messageId)` with the joined text-block content.
  The helper is defined in payload 01 (same module scope, module-eval order is
  irrelevant because the call only runs during renders).
- **Streaming dedup:** `__coOnAssistantText` tracks the highest trigger-phrase
  occurrence count seen per message ID. New occurrences enqueue
  `(count - seen)` soaks; re-renders of unchanged text enqueue nothing.
- The anchor joins the `VERSION_FRAGILE_ANCHORS` block in
  `generate_package.py` with its own hash/length pins.

## Runtime state machine (payload 01)

Module-scope mutable state: `{queue, state, frame, soakUntil}` with states
`dry → jumpIn → soak → jumpOut → dry`.

- Driven entirely by the **existing** 180 ms / 16-phase interval in
  `__CodexCapyOnsenMainWindowV4`. No new timers, no new effects.
- Tick logic: `dry` + `queue > 0` → decrement queue, enter `jumpIn`; advance
  one transition frame per tick (~6 frames ≈ 1.1 s); on last frame enter
  `soak` with `soakUntil = now + 20000`; when `now >= soakUntil` enter
  `jumpOut`; on last frame return to `dry` and re-check the queue.
- The right-wall renderer indexes the baked string array for the current
  state: `animR[ph]` (dry, unchanged), `transInR[frame]`, `animRSub[ph]`
  (soak), `transOutR[frame]`. Left wall, static bands, pool flanks, and all
  other operations are untouched.
- Responsive collapse (right gutter hidden at width ≤ 140) is unaffected: the
  state machine still advances; there is simply nothing to draw.

## Art & data (generator pipeline)

All new art lives inside the existing animated band (subrows 56–99); the
static band and the v8 byte-identical rule are untouched.

- `paint_scene.py`: submerged pose — eyes and ear tops just above the
  waterline (subrow 84), small ripple ring; an ear-wiggle offset table at the
  new anchor position; ~6 jump-in and ~6 jump-out transition frames.
- `water_sim.py`: pure, deterministic per-phase functions for the submerged
  ear flick (same "flick roughly every 3 s, otherwise still" feel) and soak
  ripple. No randomness, no wall-clock — the 20 s window lives only in the
  runtime JS.
- `compile.py`: RLE-encode the new arrays into `onsen-data.json`:
  `animRSub` (16 phases), `transInR`, `transOutR` (one-shot frame lists).
  Existing purity/determinism asserts extend to the new composer functions.
  Estimated payload growth ~40–60 KB (no size limit in the build tooling).
- `generate_package.py`: `TRIGGER_PHRASES` constant (clearly marked, near
  `VERSION_FRAGILE_ANCHORS`); helper template gains the state machine,
  `__coOnAssistantText`, and the new arrays; emits the 9th operation and its
  payload file. Package remains byte-reproducible from the pinned binary.

## Mojibake & purity rules (unchanged, non-negotiable)

- No literal `▀` or ESC bytes in any payload — runtime
  `String.fromCharCode(9600)` / `(27)` only.
- Frame data is a pure function of phase/frame index; all timing state is
  runtime JS.

## Testing & verification

- `tests/test_capybara_onsen.py`:
  - manifest test: expected op-id list grows to 9; new op keeps hash/length
    pins (op type may be an insertion/exact op — assertion updated to match).
  - payload test: new scene-contract markers (`__coOnAssistantText`, submerged
    array name, state-machine marker) + mojibake scan covers the new payload.
  - live-source validation (`validate_package`) must pass against the local
    2.1.201 binary **with fable-fallback's ops planned alongside** to prove
    no range conflict.
- `tests/test_generator_parity.py`: regenerate `packages/capybara-onsen/`
  byte-for-byte; generator changes and package changes land together.
- New `compile.py` asserts: submerged frames deterministic, distinct phases
  ≥ 2, static band still byte-identical across phases; transition frame counts
  match the runtime constants.
- Unit tests for the dedup/queue logic shape (occurrence counting per message
  ID) at the generator level where practical.
- Manual gate (`manualSmoke.required = true`): interactive truecolor smoke —
  have the agent say the trigger phrase; verify hop-in, ~20 s soak with ear
  wiggle at the waterline, hop-out, and a queued second soak on retrigger.

## Non-goals

- No runtime/env phrase configuration.
- No change to the left wall, hotrod-dragons compatibility status, or the
  five original app-shell seams' behavior.
- No detection of user messages or tool output — assistant response text only.
