# Hotrod v11 — High-Definition Scene Rendering (Design)

**Date:** 2026-07-02
**Status:** Draft — user away; design decisions made autonomously per standing goal, flagged inline with (DECISION).
**Predecessor:** v10 authored sprite (`.development/artifacts/build-hotrod-authored-sprite-v10.py`)

## Problem

v10 renders the castle/dragon/flame scene at **1 terminal cell = 1 pixel** (32×50 per side wall) using background-only Boxes. Result is chunky: staircase diagonals, blob shapes, 4-color flicker animation. Goal: dramatically higher perceived resolution and animation quality while staying inside the bundled Ink-derived renderer and remaining console-friendly.

## Key findings that shape the design

(Verified against `claude-2.1.199-hotrod-authored-sprite-v10-module0.js`; offsets are py string indices.)

1. **The renderer has a native direct-draw primitive.** `"ink-raw-ansi"` host nodes carry a pre-composed ANSI string (`rawText`) with caller-declared `rawWidth`/`rawHeight`. Paint path (offset 3954784): `t.write(c,d,rawText)` — blitted into the output buffer at node position, bypassing text width measurement entirely (measure func returns declared dims, offset ~3850131).
2. **Width safety:** live text measurement is `Bun.stringWidth(s,{ambiguousIsNarrow:!0})` — half-blocks/shades (EAW-ambiguous) measure width 1. Raw-ansi nodes don't even hit this path.
3. **fg+bg simultaneously supported** (`Bct`, offset 3654589) and **sub-cell glyphs already ship in the stock UI** (splash banner `xBe` mixes `█▄▀░▒▓` with per-row colors; clawd mascot uses quadrant blocks; braille spinner). Glyph rendering is proven in this exact binary.
4. **Frame pipeline is a bespoke double-buffered cell differ** (`Aoo`), 16ms throttle, minimal SGR deltas, synchronized-update mode 2026 wrapped per frame with **Ghostty allowlisted** (`_$()`, offset 3687690). Flicker-free multi-cell updates are structurally guaranteed.
5. **Lineage lessons (v1→v10):** never paste literal glyphs into patched source (v1 mojibake failure — generate via `String.fromCharCode`); no raw string children outside `<Text>` (Ink crash — smoke test needles exist); only fire cells may depend on the animation phase (v8 rule); RLE/element-count discipline (v9/v10).
6. **Target terminal:** Ghostty, truecolor, native block-element rendering (no font gaps). ANSI fallback path must survive on lesser terminals.

## Approach

### Chosen: build-time-baked half-block frames on raw-ansi nodes (DECISION)

**Resolution:** 32 cells wide × 100 vertical subpixels per side wall via `▀` (U+2580, runtime-generated as `String.fromCharCode(9600)`): each cell shows fg=top subpixel over bg=bottom subpixel. 2× vertical resolution vs v10, full truecolor per subpixel, no per-cell color-count constraint.

**Pipeline:**

1. **Painter (Python, build-time)** — authors the scene at 32×100 as letter-coded masks (prototype: `.development/highdef-v11-20260702/paint_scene_v11.py`; letters = v10 semantics + extensions). Deterministic (no `random`), preview PNG emitted for visual iteration.
2. **Flame simulator (Python, build-time)** — generates **8 phase variants** of the fire region (top 58 subpixel rows) as real frame animation (edge jitter + ramp advection + white-lick movement), replacing v10's 4-color per-cell flicker. Phases loop; deterministic.
3. **ANSI compiler (Python, build-time)** — converts mask rows (pairs of subpixel rows → one cell row) into pre-composed SGR strings: `\x1b[38;2;R;G;Bm\x1b[48;2;R;G;Bm▀…` with minimal SGR deltas (only emit fg/bg changes between runs), `\x1b[39;49m` termination per row. Left wall + mirrored right wall both baked. Output: compact JS string tables.
4. **Runtime helper (injected JS)** — per wall, **two raw-ansi nodes**: static region (`rawText` constant — satisfies v8 static rule structurally) and fire region (`rawText` swapped from an 8-entry table on the existing 95ms tick). Emitted as host elements: `zd.jsx("ink-raw-ansi",{rawText,rawWidth:32,rawHeight:N})` inside absolutely-positioned Boxes at the same anchors v10 uses. Element count: ~6 nodes total (vs ~1,600 Boxes worst-case for Box-RLE at this resolution).
5. **Console fallback (DECISION):** the helper gates on truecolor (`bt.level>=3` — chalk instance, offset 1034690). When below truecolor, mount the **v10 Box path unchanged** (32×50, palette-named colors with existing `ansi:` fallbacks). Raw baked truecolor strings are never shown to 16/256-color terminals.
6. **Bottom castle chrome** — same compiler applied to the tower mask (32×16 subpixels → 8 cell rows); static only.

### Alternatives considered

- **A. Text-run half-blocks** (zd.jsx(v,{color,backgroundColor,children:"▀".repeat(n)}) RLE per row): proven pattern (v3 did braille this way), theme-integrated, but ~10–16 spans × 100 wall-rows of React elements re-reconciled per fire tick. Viable fallback if raw-ansi surprises; the compiler's mask data feeds either backend. Kept as contingency, not primary.
- **B. Quadrant/sextant chooser** (2×2 or 2×3 subpixels/cell, 2 colors/cell, error-minimizing glyph choice à la chafa): more horizontal resolution but adds a lossy chooser and Ghostty-skewed font assumptions (sextants). Deferred to v12 as an *edge-refinement pass* on top of the half-block base.
- **C. Kitty graphics protocol** (real pixel images; Ghostty supports it): true high-def but fights the cell differ (images are not cells), needs placement/eviction management on resize/scroll, and is a per-terminal protocol fork. Explicitly out of scope for v11; worth a dedicated spike later.
- **D. Hooking the frame flush (`Yno`)/Output compositor directly:** maximal power, but `ink-raw-ansi` already provides sanctioned direct-draw with layout integration; patching the differ risks corrupting the style-interning pool. Rejected while raw-ansi suffices.

## Animation & performance rules

- Fire tick stays 95ms (v10 cadence). Per tick, React swaps one string prop on 2 nodes; the cell differ emits only changed cells, inside a mode-2026 synchronized update.
- Static regions: zero phase dependency (enforced by verify script, v8-style chunk assertion).
- Dragon eye glint (2-subpixel `E` cells) may join the fire table later; v11 keeps dragon fully static.

## Compatibility

- **Truecolor terminals (Ghostty, iTerm2, WezTerm, kitty, alacritty):** full baked-frame path.
- **256/16-color terminals:** v10 Box path via the level gate — identical to today's shipped behavior.
- **No new palette keys required** for the baked path (colors are literal SGR). v10's palette injection is retained unchanged for the fallback path and user-slab tint.

## Verification plan

- **Build script** (`build-hotrod-highdef-v11.py`): sha-pinned source + module, `replace_once` anchors (same five v10 anchors), required-marker list (raw-ansi usage, phase table, level gate, `String.fromCharCode(9600)`), forbidden-marker list (literal `▀…` bytes in helper, `zd.jsx(v`, `Math.sin` in helper, `firePhase` in static chunk, v10 helper names).
- **Verify script** (`verify-hotrod-highdef-v11-binary.py`): re-extract module from output binary, assert all markers, assert static/fire chunk separation, assert baked strings contain `\x1b[38;2;` + `\x1b[48;2;` pairs and end rows with reset.
- **PTY smoke** (pattern of `smoke-hotrod-pty-startup.py`): spawn binary in PTY (truecolor env), assert no Ink text-node crash needles, assert art SGR signature appears in output; second run with `FORCE_COLOR=1` level<3 env to exercise the fallback gate.
- **Sign:** `codesign --force --sign -` + strict verify (builder_v15 helpers).
- **Human smoke test:** binary staged at `.development/artifacts/claude-2.1.199-hotrod-highdef-v11`, run manually in Ghostty.

## Open items

- Confirm `Output.write` parses SGR in rawText into per-cell styles for the differ (third research pass in flight; the exported `Ansi` component's existence implies yes — it renders colored embedded output today).
- Right-wall mirroring is baked at build time (glyph `▀` is orientation-symmetric per subpixel; only colors mirror).
- Module size delta ~100–150KB from 8-phase tables; repack alignment handled (16KB padding fix already in `claude_monkey.repack`).
