# capybara-onsen generator (example)

`generate_package.py` is the authoritative regeneration interface for the
current shipped `packages/capybara-onsen/` package. It emits the checked-in
package byte-for-byte (excluding any hand-captured `preview.png`) and is covered
by `tests/test_generator_parity.py`.

The other scripts in this directory preserve the lower-level scene source that
led to the package: deterministic water/steam animation, hand-authored onsen
scene grids, compact RLE art data, and optional terminal-frame capture tooling.
They remain useful for learning and future art work, but package regeneration
must go through `generate_package.py` so the shipped artifact and generator stay
in parity.

## What it does

Paints a twilight Japanese onsen scene (two capybaras, kakei water spout,
stone lantern, 16-phase water/steam animation) as half-block (`▀`) ANSI art and
ships it as a Claude Code patch package.

## Script order

1. **`water_sim.py`** — pure, deterministic per-phase animation functions
   (stream, impact spray, ripple, steam, ear flick). No file I/O.
2. **`paint_scene.py`** — hand-authored static scene grids (sky, moon, rocks,
   bamboo, lantern, capybaras) for the left/right walls; composites in
   `water_sim` per phase. `python paint_scene.py` writes a PNG preview
   (`onsen-scene-preview.png`) via macOS `sips`.
3. **`compile.py`** — imports `paint_scene`, RLE-encodes every static/animated/
   pool band into `[topColorIdx, botColorIdx, width]` runs, and writes
   `onsen-data.json` next to itself.
4. **`generate_package.py`** — emits the current shipped package. By default it
   targets `packages/capybara-onsen/` and is an idempotent no-op when that live
   package is already current. Set `HM_GENERATE_OUT` to write the generated
   package to a separate directory for parity checks or review.
5. **`capture_frame.py`** — optional verification tool: boots a *locally built,
   codesigned* patched binary in a PTY, captures its real ANSI output, and
   rasterizes it back to a PNG so the baked art can be checked against an actual
   terminal render. Not part of the generation pipeline proper.

## How to run

From this directory:

```bash
python3 compile.py
HM_GENERATE_OUT=/tmp/capybara-onsen python3 generate_package.py
python3 generate_package.py
```

`HM_GENERATE_OUT` is the safe path for tests and experimentation: it writes a
fresh package tree somewhere other than `packages/capybara-onsen/`. Without
`HM_GENERATE_OUT`, the script targets the live package path and refuses to
copy-delete from itself, so ordinary default invocation is safe and idempotent.

`compile.py` (and transitively `paint_scene.py`/`water_sim.py`) is fully
self-contained — standard library only, no external binaries required beyond
macOS `sips` for the optional preview PNG.

`capture_frame.py` needs a locally built, codesigned patched binary placed at
`build/claude` next to the script (not shipped in this repo).

## Dependencies

Standard library only (`json`, `math`, `pathlib`, `subprocess`, `pty`, `re`,
`select`, `signal`, `struct`, `fcntl`, `termios`, `time`, plus the small file
copy helpers in `generate_package.py`). PNG preview generation shells out to
macOS `sips` (macOS-only).

## Verified

`generate_package.py` is exercised by `tests/test_generator_parity.py`, which
runs the generator with `HM_GENERATE_OUT` and compares the emitted package files
against `packages/capybara-onsen/` byte-for-byte. The lower-level scene scripts
remain preserved as source material for future art edits.
