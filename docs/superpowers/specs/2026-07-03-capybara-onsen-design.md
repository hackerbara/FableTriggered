# Capybara Onsen — Calming Scene Package (Design)

**Date:** 2026-07-03
**Status:** Approved by user (conversation, 2026-07-03 evening) — implementation may iterate on art freely; final gate is interactive eyeball smoke.
**Sibling:** `packages/hotrod-dragons` (same seams, mutually exclusive at build time)

## Goal

A calming counterpart to Hotrod Dragons: a twilight Japanese onsen scene with two
capybaras soaking in the terminal's bottom corners. Minimal motion — "alive but
sleepy." Same rendering skeleton as the dragons (build-time-baked half-block
truecolor art on `ink-raw-ansi` nodes at the five app-shell seams of Claude Code
2.1.199), new art, new palette, water/steam animation instead of fire.

## Composition (one continuous scene, NOT a strict mirror)

**Left wall (32 cells wide):**
- Top: deep indigo dusk sky, pale moon, bamboo-grove silhouettes leaning inward.
- Mid: dark slate rocks stepping down; a **bamboo kakei spout** jutting out.
- Bottom corner: teal steaming pool; capybara soaking to its chin, eyes
  half-closed; a **thin clear-blue stream pours steadily from the spout onto its
  head**, with a small splash-ripple at impact.
- A floating yuzu (2–3 cells of warm orange accent).

**Right wall (32 cells wide):**
- Sky continues across (shared horizon so it reads as one scene behind the UI).
- A **stone lantern (tōrō)** with warm amber glow — the scene's light source,
  rim-lighting both capybaras.
- Bottom corner: second capybara, dry, resting on a rock shelf at pool edge;
  **ears flick occasionally**.
- Steam wisps rising off the water on both walls.

**Composer flanks** continue the pool water into the very bottom corners (same
trick as the dragon tails). **Chrome parent** gets the dark indigo blend.

## Palette

Warm-on-cool: deep indigo sky → slate rock → warm teal water (lit from the
lantern side) → capybara warm brown with amber rim light → near-white clear blue
stream → pale steam → single yuzu-orange accent. Literal truecolor SGR with the
existing 6×6×6 256-color fallback cube. No theme/palette seam dependency.

## Animation — lazy 180 ms tick (vs dragons' 95 ms)

Three small baked animated regions; all other cells phase-independent (v8 rule):

1. **Spout stream + splash** (left): 8-phase continuous flow — gentle shimmer /
   undulation in the stream, pulsing splash ripple. Always moving, gently.
2. **Ear flick** (right): 16-phase loop, ears move in only ~3 phases → a flick
   roughly every 3 s, otherwise perfectly still.
3. **Steam wisps** (both walls): slow 8-phase rise sharing the tick.

## Pipeline (mirrors highdef v11/v13 exactly)

New `.development/capy-onsen-20260703/`:
- `paint_scene.py` — letter-coded masks at 32-cell × subpixel resolution,
  deterministic, emits preview PNGs for visual iteration.
- `water_sim.py` — replaces `flame_sim_v11`: stream undulation, splash ripple,
  steam advection, ear pose variants.
- `compile.py` — same half-block ANSI baker: `▀` via `String.fromCharCode(9600)`,
  ESC via `String.fromCharCode(27)`, minimal SGR deltas, per-row reset.
- `generate_package.py` — emits `packages/capybara-onsen/`: `patch.json` +
  5 payloads + README + preview.png.

**Mojibake rules (v1 lesson, non-negotiable):** payloads contain no literal `▀`
and no literal ESC bytes; art data embedded as numeric run arrays only.

## Package

`packages/capybara-onsen`, schemaVersion 2, target Claude Code **2.1.199**
darwin/arm64 (same sourceIdentity pins as hotrod-dragons), module
`/$bunfs/root/src/entrypoints/cli.js`, five `replace_exact` operations at the
same anchors (`V8o` helpers-insert, `pe` fullscreen, `ue` composer flank, `le`
chrome parent, `V` fallback). Mutually exclusive with hotrod-dragons — the
builder's byte-range overlap check rejects co-application; one scene active per
build.

## Verification

- `tests/test_capybara_onsen.py` mirroring the three hotrod-dragons tests:
  1. manifest shape + source/module pins,
  2. payload hash match + mojibake safety + scene-contract markers
     (scene function name, `"ink-raw-ansi"`, runtime charCode generation,
     animation tick marker),
  3. live-source validation via `builder_v15.validate_package` (skips if the
     local 2.1.199 source is absent).
- Build via `claude_monkey build`; automated gates must pass.
- `manualSmoke.required = true` — activation gated on interactive confirmation
  in a truecolor terminal (purely visual TUI art).

## Non-goals

- No kitty-graphics / sextant experiments (v12+ territory).
- No coexistence with hotrod-dragons in a single binary.
- No theming integration; colors are literal.
