# Hotrod Dragons

Two heraldic, fire-breathing serpentine dragons flank the Claude Code terminal —
high-def half-block pixel art with an 8-phase baked flame animation, breathed from
each dragon's open maw toward the center of the screen.

![preview](preview.png)

## What it does

- Renders a **left and right dragon** in the 32-cell gutters around the conversation
  view. Each dragon: horned head with an open toothy maw, coiling serpentine body with
  a dorsal frill, claws, and a tail that flows into the bottom corner.
- A **flame plume** issues from each maw (real 8-frame animation: climbing white-hot
  licks, drifting embers), the two plumes crowning together at the top-center.
- Mirrors into the composer flanks so the dragon body reaches the very bottom corners.

## How it works (rendering)

The art is drawn through the bundled renderer's **native `ink-raw-ansi` direct-draw
node**, not per-cell React Boxes. At module-eval time the helper assembles the whole
wall into pre-baked ANSI strings (`▀` half-blocks, `fg`=top subpixel / `bg`=bottom
subpixel → 2× vertical resolution, full truecolor per subpixel). Per 95 ms tick only
the two fire strings swap; the renderer's cell differ + synchronized-update mode 2026
handle the rest, flicker-free.

- **Mojibake-safe** (v1 lesson): payloads contain **no literal `▀` or ESC bytes** — the
  runtime produces both via `String.fromCharCode(9600)` / `(27)`. Art data is embedded
  as pure numeric run arrays.
- **Truecolor primary; 256-color fallback** at runtime via a 6×6×6 cube map (no palette
  table dependency — surrounding boxes use literal `rgb(...)`).
- Only the fire region re-renders each tick; static dragon geometry is assembled once.

## Target

- Claude Code **2.1.199**, `darwin/arm64` (Bun standalone macho64).
- Module: `/$bunfs/root/src/entrypoints/cli.js`.
- Pinned by whole-binary SHA-256, whole-module SHA-256/length, and per-operation
  old-range SHA-256/length.

## Operations (seams)

All five are `replace_exact` inserts/replacements (non-overlapping):

1. `…-scene-helpers-before-v8o` — defines the scene components + embeds baked art data.
2. `…-fullscreen-scene-pe` — mounts the dragons in the fullscreen conversation view.
3. `…-composer-flank-ue` — continues the dragon tail into the composer flanks.
4. `…-composer-parent-le` — dark background on the bottom chrome parent.
5. `…-fallback-scene-v` — mounts the dragons in the non-fullscreen fallback path.

## Manual smoke

`manualSmoke.required = true`. It's purely visual TUI art, so automated sign/smoke
gates pass but activation is intentionally gated on interactive confirmation in a
truecolor terminal (Ghostty/iTerm2/WezTerm/kitty/alacritty).

## Compatibility

- Independent of the theme tables (uses literal colors), so no palette seam.
- Shares the `pe`/`ue`/`le`/`V` app-shell seams in `cli.js`. It composes with packages
  that don't touch those exact anchors; the builder's byte-range overlap check
  (`patch_conflict:…`) will catch any real conflict at build time.

## Build

```bash
cd /Users/MAC/Documents/Claude-patch
PYTHONPATH=src python3 -m claude_monkey build \
  --source /Users/MAC/.local/share/claude/versions/2.1.199 \
  --package hotrod-dragons \
  --output-dir .development/claude-monkey-builds/hotrod-dragons \
  --source-version 2.1.199 \
  --source-version-output "2.1.199 (Claude Code)" \
  --platform darwin --arch arm64
```

Report `status` will be `manual_smoke_pending` with `automatedStatus: passed`. Run the
produced `…/hotrod-dragons/claude` in a truecolor terminal to confirm, then activate.
