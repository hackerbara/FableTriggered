# hotrod-dragons generator (example)

`generate_package.py` is the authoritative regeneration interface for the
current shipped `packages/hotrod-dragons/` package. It emits the checked-in
package byte-for-byte (excluding any hand-captured `preview.png`) and is covered
by `tests/test_generator_parity.py`.

The other scripts in this directory preserve the lower-level scene source from
the final "v13" iteration: full-height serpentine dragons, mouth-anchored flame
animation, compact RLE art data, and optional terminal-frame capture tooling.
They remain useful for learning and future art work, but package regeneration
must go through `generate_package.py` so the shipped artifact and generator stay
in parity.

This is the **curated final version** of a multi-iteration development process
(v11 → v12 → v13). Only the v13 scripts — the ones the original package emitter
consumed — are included here. Earlier iterations (`dragon_v12.py`,
`paint_scene_v11.py`/`v12.py`, `flame_sim_v11.py`, `compile_v11.py`/`v12.py`,
`prototype_upscale.py`, `measure_offset.py`) were left behind as design-process
debris; they are not part of the pipeline that produced the shipped package.

## What it does

Paints two heraldic fire-breathing dragons (full-height serpentine body,
mouth-anchored flame plume, 8-phase baked fire animation) as half-block (`▀`)
ANSI art and ships it as a Claude Code patch package.

## Script order

1. **`dragon_v13.py`** — hand-authored full-height serpentine dragon body +
   head grid (left wall; mirrored at runtime for the right wall). No animation;
   the dragon itself is static.
2. **`paint_scene_v13.py`** — imports `dragon_v13`, adds the animated
   mouth-anchored flame plume (8 phases) and composites dragon + fire per phase;
   also provides `tower_layer()` (the composer-flank continuation of the
   dragon's lower body). `python dragon_v13.py` / `python paint_scene_v13.py`
   each write their own PNG preview via macOS `sips`.
3. **`compile_v13.py`** — imports `paint_scene_v13`, RLE-encodes the static
   (dragon body) band, the 8 fire-phase bands, and the tower band into
   `[topColorIdx, botColorIdx, width]` runs, and writes `v11-data.json` next to
   itself (filename kept from the v11 baseline schema the later iterations reuse
   unchanged).
4. **`generate_package.py`** — emits the current shipped package. By default it
   targets `packages/hotrod-dragons/` and is an idempotent no-op when that live
   package is already current. Set `HM_GENERATE_OUT` to write the generated
   package to a separate directory for parity checks or review.
5. **`capture_frame.py`** — optional verification tool: boots a *locally built,
   codesigned* patched binary in a PTY, captures its real ANSI output, and
   rasterizes it back to a PNG so the baked art can be checked against an actual
   terminal render. Not part of the generation pipeline proper; note its `BIN`
   path and dimensions were written for the original v11 build and were never
   updated for v13 — treat it as illustrative of the technique rather than a
   ready-to-run v13 verifier.

## How to run

From this directory:

```bash
python3 compile_v13.py
HM_GENERATE_OUT=/tmp/hotrod-dragons python3 generate_package.py
python3 generate_package.py
```

`HM_GENERATE_OUT` is the safe path for tests and experimentation: it writes a
fresh package tree somewhere other than `packages/hotrod-dragons/`. Without
`HM_GENERATE_OUT`, the script targets the live package path and refuses to
copy-delete from itself, so ordinary default invocation is safe and idempotent.

`compile_v13.py` (and transitively `dragon_v13.py`/`paint_scene_v13.py`) is
fully self-contained — standard library only, no external binaries required
beyond macOS `sips` for the optional preview PNGs.

`capture_frame.py` needs a locally built, codesigned patched binary placed at
`build/claude` next to the script (not shipped in this repo), and its
`ROWS`/`COLS` were tuned for the v11 build's terminal size.

## Dependencies

Standard library only (`json`, `math`, `pathlib`, `subprocess`, `pty`, `re`,
`select`, `signal`, `struct`, `fcntl`, `termios`, `time`, plus the small file
copy helpers in `generate_package.py`). PNG preview generation shells out to
macOS `sips` (macOS-only).

## Verified

`generate_package.py` is exercised by `tests/test_generator_parity.py`, which
runs the generator with `HM_GENERATE_OUT` and compares the emitted package files
against `packages/hotrod-dragons/` byte-for-byte. The lower-level scene scripts
remain preserved as source material for future art edits.
