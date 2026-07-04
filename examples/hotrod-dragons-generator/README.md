# hotrod-dragons generator (example)

Illustrative source pipeline that generated the `hotrod-dragons` patch
package (final "v13" iteration). **The shipped package under
`packages/hotrod-dragons/` is the canonical artifact.** Re-running this
pipeline is for learning/tinkering only — it is not part of the build, it
is not covered by tests, and it is not guaranteed to reproduce the shipped
package byte-for-byte (its `SOURCE` binary pin and `packages/` output target
reflect the state of this pipeline on 2026-07-02, not necessarily the
package's current pin).

This is the **curated final version** of a multi-iteration development
process (v11 → v12 → v13). Only the v13 scripts — the ones the original
`generate_package.py` actually consumed — are included here. Earlier
iterations (`dragon_v12.py`, `paint_scene_v11.py`/`v12.py`, `flame_sim_v11.py`,
`compile_v11.py`/`v12.py`, `prototype_upscale.py`, `measure_offset.py`) were
left behind as design-process debris; they are not part of the pipeline that
produced the shipped package.

## What it does

Paints two heraldic fire-breathing dragons (full-height serpentine body,
mouth-anchored flame plume, 8-phase baked fire animation) as half-block
(`▀`) ANSI art, bakes it into compact numeric run-data, and emits a
`patch.json` + `payloads/*.js` operation set that inserts the scene into a
pinned Claude Code `cli.js` module.

## Script order

1. **`dragon_v13.py`** — hand-authored full-height serpentine dragon body +
   head grid (left wall; mirrored at runtime for the right wall). No
   animation; the dragon itself is static.
2. **`paint_scene_v13.py`** — imports `dragon_v13`, adds the animated
   mouth-anchored flame plume (8 phases) and composites dragon + fire per
   phase; also provides `tower_layer()` (the composer-flank continuation of
   the dragon's lower body). `python dragon_v13.py` / `python
   paint_scene_v13.py` each write their own PNG preview via macOS `sips`.
3. **`compile_v13.py`** — imports `paint_scene_v13`, RLE-encodes the static
   (dragon body) band, the 8 fire-phase bands, and the tower band into
   `[topColorIdx, botColorIdx, width]` runs, and writes `v11-data.json`
   next to itself (filename kept from the v11 baseline schema the later
   iterations reuse unchanged).
4. **`generate_package.py`** — reads `v11-data.json`, reads a locally
   installed clean Claude Code 2.1.199 binary, verifies its sha256, locates
   and patches the `cli.js` module in-memory (via `claude_monkey.macho` /
   `claude_monkey.bun_graph` from this repo's `src/`), and writes
   `patch.json` + `payloads/*.js` — targeting `packages/hotrod-dragons/`.
5. **`capture_frame.py`** — optional verification tool: boots a *locally
   built, codesigned* patched binary in a PTY, captures its real ANSI
   output, and rasterizes it back to a PNG so the baked art can be checked
   against an actual terminal render. Not part of the generation pipeline
   proper; note its `BIN` path and dimensions were written for the original
   v11 build and were never updated for v13 — treat it as illustrative of
   the technique rather than a ready-to-run v13 verifier.

## How to run

From this directory:

```bash
python3 compile_v13.py             # dragon_v13.py + paint_scene_v13.py -> v11-data.json (self-contained)
python3 generate_package.py        # v11-data.json -> patch.json + payloads/ (needs step below)
```

`compile_v13.py` (and transitively `dragon_v13.py`/`paint_scene_v13.py`) is
fully self-contained — standard library only, no external binaries required
beyond macOS `sips` for the optional preview PNGs.

`generate_package.py` additionally requires a local install of the exact
pinned Claude Code build it targets:

```
~/.local/share/claude/versions/2.1.199
sha256: e3cb61abc8a2ec7b98976cee1ffdde5a3fa755c9990bc8d688cd89290e0dcec0
```

If that binary isn't present at that path, `generate_package.py` will fail
its sha256 assertion — this is expected and by design (the pipeline refuses
to patch anything but the exact byte-identical module it was verified
against). It also imports `claude_monkey.macho` / `claude_monkey.bun_graph`
from this repo's `src/`, resolved repo-relatively from the script's own
location.

**Caution:** `generate_package.py` writes directly into
`packages/hotrod-dragons/patch.json` and `packages/hotrod-dragons/payloads/`.
Since that package has since been re-pinned to a newer Claude Code version,
re-running this script would overwrite it with stale 2.1.199-targeted
output. Don't run it against a checkout where you want to keep the current
shipped package intact — copy this directory elsewhere first if you just
want to explore it. **This script was not run during curation** (see
verification note below).

`capture_frame.py` needs a locally built, codesigned patched binary placed
at `build/claude` next to the script (not shipped in this repo), and its
`ROWS`/`COLS` were tuned for the v11 build's terminal size.

## Dependencies

Standard library only (`hashlib`, `json`, `math`, `pathlib`, `subprocess`,
`pty`, `re`, `select`, `signal`, `struct`, `fcntl`, `termios`, `time`) plus
this repo's own `claude_monkey.macho` / `claude_monkey.bun_graph` modules.
No PIL/Pillow or other third-party packages. PNG preview generation shells
out to macOS `sips` (macOS-only).

## Verified

`compile_v13.py` was run from this directory and reproduced `v11-data.json`
byte-for-byte identical to the version that generated the shipped package.
`dragon_v13.py` and `paint_scene_v13.py`'s preview-PNG paths and `python -m
py_compile` on every script here all pass. `generate_package.py` was **not**
run during curation — unlike the capybara-onsen example, it was left
untouched to avoid any risk of writing into `packages/hotrod-dragons/`; its
logic is otherwise identical in shape to the capybara-onsen
`generate_package.py`, which *was* verified end-to-end.
