# capybara-onsen generator (example)

Illustrative source pipeline that generated the `capybara-onsen` patch package.
**The shipped package under `packages/capybara-onsen/` is the canonical artifact.**
Re-running this pipeline is for learning/tinkering only — it is not part of the
build, it is not covered by tests, and it is not guaranteed to reproduce the
shipped package byte-for-byte (its `SOURCE` binary pin and `packages/` output
target reflect the state of this pipeline on 2026-07-03, not necessarily the
package's current pin).

## What it does

Paints a twilight Japanese onsen scene (two capybaras, kakei water spout,
stone lantern, 16-phase water/steam animation) as half-block (`▀`) ANSI art,
bakes it into compact numeric run-data, and emits a `patch.json` +
`payloads/*.js` operation set that inserts the scene into a pinned Claude
Code `cli.js` module.

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
4. **`generate_package.py`** — reads `onsen-data.json`, reads a locally
   installed clean Claude Code 2.1.199 binary, verifies its sha256, locates
   and patches the `cli.js` module in-memory (via `claude_monkey.macho` /
   `claude_monkey.bun_graph` from this repo's `src/`), and writes
   `patch.json` + `payloads/*.js` — targeting `packages/capybara-onsen/`.
5. **`capture_frame.py`** — optional verification tool: boots a *locally
   built, codesigned* patched binary in a PTY, captures its real ANSI
   output, and rasterizes it back to a PNG so the baked art can be checked
   against an actual terminal render. Not part of the generation pipeline
   proper.

## How to run

From this directory:

```bash
python3 compile.py                 # paint_scene.py + water_sim.py -> onsen-data.json (self-contained)
python3 generate_package.py        # onsen-data.json -> patch.json + payloads/ (needs step below)
```

`compile.py` (and transitively `paint_scene.py`/`water_sim.py`) is fully
self-contained — standard library only, no external binaries required beyond
macOS `sips` for the optional preview PNG.

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
`packages/capybara-onsen/patch.json` and `packages/capybara-onsen/payloads/`.
Since that package has since been re-pinned to a newer Claude Code version,
re-running this script will overwrite it with stale 2.1.199-targeted output.
Don't run it against a checkout where you want to keep the current shipped
package intact — copy this directory elsewhere first if you just want to
explore it.

`capture_frame.py` needs a locally built, codesigned patched binary placed at
`build/claude` next to the script (not shipped in this repo).

## Dependencies

Standard library only (`hashlib`, `json`, `math`, `pathlib`, `subprocess`,
`pty`, `re`, `select`, `signal`, `struct`, `fcntl`, `termios`, `time`) plus
this repo's own `claude_monkey.macho` / `claude_monkey.bun_graph` modules.
No PIL/Pillow or other third-party packages. PNG preview generation shells
out to macOS `sips` (macOS-only).

## Verified

`compile.py` was run from this directory and reproduced `onsen-data.json`
byte-for-byte identical to the version that generated the shipped package.
`paint_scene.py`'s preview-PNG path and `python -m py_compile` on every
script here both pass. `generate_package.py` was also test-run once during
curation (its sha256 self-checks passed against the local 2.1.199 binary and
it reproduced the expected patched-module hash) — the resulting stale output
was then reverted out of `packages/capybara-onsen/` immediately, since that
package has since moved on to a newer Claude Code pin. See the caution above
before running it yourself.
