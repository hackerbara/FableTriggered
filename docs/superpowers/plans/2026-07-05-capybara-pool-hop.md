# Capybara Pool-Hop Trigger Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When an assistant response contains a trigger phrase, the right-wall onsen capybara hops into the pool, soaks ~20s with only eyes/ears above the waterline (ears still flick), then climbs back out; retriggers queue extra soaks.

**Architecture:** Pure-data art additions (submerged 16-phase loop + 6-frame jump-in/out one-shots) baked by the existing paint/compile pipeline into `onsen-data.json`; a small JS state machine in payload 01 driven by the existing 180ms tick; one new 9th `replace_exact` op that injects a guarded hook call before the transcript-item `switch(n.type)` so `__coOnAssistantText(n)` can scan assistant text.

**Tech Stack:** Python 3 stdlib (generator pipeline), minified JS payloads, pytest, claude-monkey builder (`src/claude_monkey/`).

**Spec:** `docs/superpowers/specs/2026-07-05-capybara-pool-hop-design.md`

## Global Constraints

- Target binary: Claude Code **2.1.201** darwin/arm64 at `~/.local/share/claude/versions/2.1.201` (present on this machine — parity/validate tests will NOT skip).
- **v8 rule:** rows 0–55 (subrows) of every composed right-wall frame must be byte-identical to `static_right()`; all new art stays in subrows 56–99. `compile.py:_check_v8_rule` enforces this.
- **Mojibake rule:** payloads must contain no literal `▀` (U+2580) and no literal ESC byte; only `String.fromCharCode(9600)` / `String.fromCharCode(27)`.
- **Determinism:** all paint/sim functions are pure functions of (phase/frame, geometry). No `random`, no wall-clock in Python. The 20s timing lives only in runtime JS (tick counting, 111 ticks × 180ms ≈ 20s).
- **Byte parity:** `tests/test_generator_parity.py` requires `generate_package.py` to reproduce `packages/capybara-onsen/` byte-for-byte. Never hand-edit `packages/capybara-onsen/`; always regenerate.
- All work happens in `examples/capybara-onsen-generator/`, `packages/capybara-onsen/` (generated), and `tests/`. Do not touch `src/claude_monkey/` or other packages.
- Run tests with `python3 -m pytest <file> -v` from the repo root.

## Key facts (verified against the real 2.1.201 module — do not re-derive)

- The transcript-item render function is `function mDm(e){...}`; it destructures `{message:n,...}=e` and switches on `n.type`. The statement `S=_===void 0?!1:_;` immediately precedes `switch(n.type){` and occurs **exactly once** in the whole module (offset 10180002). Statements are legal at that point; they are NOT legal between `switch(n.type){` and the first `case`.
- fable-fallback's op claims bytes [10181133, 10182706) (its `startMarker` is `case"assistant":{let A;if(t[20]!==r.firstTextBlockUuidByMessageID`). Our anchor span [10180002, 10180020) ends 1113 bytes before that — no overlap, both packages co-build.
- Assistant text blocks: `n.message.content` is an array of blocks (`{type:"text",text:"..."}`); message id is `n.message.id`.
- The emitter (`examples/art_package_emitter.py`) emits ops from `VERSION_FRAGILE_ANCHORS` entries in list order; payload files are named `payloads/{index:02d}-{op_prefix}-{slug}-{version_slug}.js`. Op 9 → `payloads/09-capy-onsen-assistant-text-hook-2-1-201.js`.
- The only runtime state today is `[ph,setPh]` advanced by `setInterval(()=>setPh((p)=>(p+1)%__coPhases),180)` inside `__CodexCapyOnsenMainWindowV4`. `tests/test_capybara_onsen.py` greps the literal `"%__coPhases),180)"` — that marker changes in Task 4 and the test must be updated in the same commit.
- Geometry: grid 32×100 subrows; `WATERLINE = 84`; dry capybara body `CAPY_R_BODY` at origin `(1, 68)` (subrows 68–79); ears via absolute-coordinate `EAR_POSES` at y65–67; shelf rock at y80–83 x1–21; `pool()` overwrites y84+ with water everywhere. Head drawn over shelf rows reads as "in front of the shelf" — correct occlusion.

---

### Task 1: water_sim — soak ripple + splash pure functions

**Files:**
- Modify: `examples/capybara-onsen-generator/water_sim.py`
- Create: `tests/test_pool_hop_scene.py`

**Interfaces:**
- Produces: `water_sim.soak_ripple_cells(phase: int, cx: int, y: int) -> list[tuple[int,int,str]]` and `water_sim.splash_cells(step: int, cx: int, y: int) -> list[tuple[int,int,str]]`. Both pure. Task 2 consumes them.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pool_hop_scene.py`:

```python
"""Scene-level tests for the capybara pool-hop feature (pure Python, no binary)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GEN = ROOT / "examples" / "capybara-onsen-generator"
if str(GEN) not in sys.path:
    sys.path.insert(0, str(GEN))

import water_sim as ws  # noqa: E402


def test_soak_ripple_is_deterministic_and_phase_varying():
    a = ws.soak_ripple_cells(3, 9, 84)
    b = ws.soak_ripple_cells(3, 9, 84)
    assert a == b
    assert ws.soak_ripple_cells(0, 9, 84) != ws.soak_ripple_cells(2, 9, 84)


def test_soak_ripple_stays_on_the_surface_row():
    for p in range(16):
        cells = ws.soak_ripple_cells(p, 9, 84)
        assert cells, f"phase {p}: empty ripple"
        assert all(y == 84 for _, y, _ in cells)
        assert all(ch in ("F", "V") for _, _, ch in cells)


def test_splash_cells_deterministic_and_bounded():
    assert ws.splash_cells(3, 9, 84) == ws.splash_cells(3, 9, 84)
    assert ws.splash_cells(0, 9, 84) == []
    for step in range(6):
        for x, y, ch in ws.splash_cells(step, 9, 84):
            assert 56 <= y <= 85, f"splash leaked to subrow {y}"
            assert ch in ("U", "u", "F")
    assert len(ws.splash_cells(4, 9, 84)) > len(ws.splash_cells(1, 9, 84))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_pool_hop_scene.py -v`
Expected: FAIL with `AttributeError: module 'water_sim' has no attribute 'soak_ripple_cells'`

- [ ] **Step 3: Implement the functions**

In `examples/capybara-onsen-generator/water_sim.py`, add after `ear_pose` (line 83), before the asserts block:

```python
def soak_ripple_cells(phase, cx, y):
    """Concentric surface ripple around the soaking head. Pure in (phase, cx, y)."""
    p = phase % CYCLE
    r = 2 + (p % 4)
    cells = []
    for dx in (-r, r):
        cells.append((cx + dx, y, 'F' if p % 2 else 'V'))
    if p >= 4:
        for dx in (-(r + 2), r + 2):
            cells.append((cx + dx, y, 'V'))
    return cells


def splash_cells(step, cx, y):
    """One-shot splash burst for the jump transitions. step 0 = no splash;
    larger steps = wider/taller burst. Pure in (step, cx, y)."""
    if step <= 0:
        return []
    spread = min(step + 1, 5)
    cells = []
    for k in range(-spread, spread + 1):
        yy = y - 1 - (spread - abs(k)) // 2
        ch = 'u' if abs(k) <= 1 else ('U' if k % 2 else 'F')
        cells.append((cx + k, yy, ch))
    return cells
```

Extend the module-level asserts block at the bottom (keep the existing five asserts; add):

```python
assert soak_ripple_cells(5, 9, 84) == soak_ripple_cells(5, 9, 84)
assert soak_ripple_cells(0, 9, 84) != soak_ripple_cells(2, 9, 84)
assert splash_cells(0, 9, 84) == []
assert all(56 <= y <= 85 for _, y, _ in splash_cells(5, 9, 84))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_pool_hop_scene.py -v`
Expected: 3 tests PASS

- [ ] **Step 5: Commit**

```bash
git add examples/capybara-onsen-generator/water_sim.py tests/test_pool_hop_scene.py
git commit -m "feat: soak ripple and splash sim functions for pool-hop"
```

---

### Task 2: paint_scene — submerged pose and jump transition frames

**Files:**
- Modify: `examples/capybara-onsen-generator/paint_scene.py`
- Test: `tests/test_pool_hop_scene.py` (extend)

**Interfaces:**
- Consumes: `ws.soak_ripple_cells`, `ws.splash_cells`, `ws.ear_pose` from Task 1.
- Produces (Task 3 consumes): `paint_scene.TRANS_FRAMES = 6`, `paint_scene.compose_right_submerged(phase: int) -> list[str]` (100 row-strings), `paint_scene.compose_right_jump_in(frame: int) -> list[str]`, `paint_scene.compose_right_jump_out(frame: int) -> list[str]`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_pool_hop_scene.py`:

```python
import paint_scene as scene  # noqa: E402


def _static_right():
    return scene.static_right()


def test_submerged_frames_static_band_and_determinism():
    static_rows = _static_right()
    assert scene.compose_right_submerged(0) == scene.compose_right_submerged(0)
    frames = [scene.compose_right_submerged(p) for p in range(scene.PHASES)]
    for p, frame in enumerate(frames):
        assert len(frame) == scene.H
        for r in range(56):
            assert frame[r] == static_rows[r], f"v8 leak: phase {p} row {r}"
    assert len({tuple(f) for f in frames}) >= 2, "submerged loop has no motion"


def test_submerged_pose_shows_eyes_and_ears_above_water_only():
    frame = scene.compose_right_submerged(0)
    assert "E" in frame[83], "eyes missing just above the waterline"
    ear_rows = "".join(frame[79] + frame[80] + frame[81])
    assert "c" in ear_rows, "ears missing above the waterline"
    # the dry body must be gone: its eye row was y71
    assert "E" not in frame[71]
    # nothing but water/ripple chars on the surface row left of the rock column
    assert all(ch in "WVvF" for ch in frame[84][0:22])


def test_submerged_ears_still_wiggle():
    rest = scene.compose_right_submerged(0)
    flick = scene.compose_right_submerged(7)
    wiggle_band = [rest[r] != flick[r] for r in range(78, 83)]
    assert any(wiggle_band), "ear flick not visible in submerged pose"


def test_jump_frames_shape_and_static_band():
    static_rows = _static_right()
    for compose in (scene.compose_right_jump_in, scene.compose_right_jump_out):
        frames = [compose(f) for f in range(scene.TRANS_FRAMES)]
        assert compose(0) == compose(0)
        assert len(frames) == 6
        for i, frame in enumerate(frames):
            assert len(frame) == scene.H
            for r in range(56):
                assert frame[r] == static_rows[r], f"v8 leak: frame {i} row {r}"
        assert len({tuple(f) for f in frames}) >= 4, "transition barely animates"


def test_jump_in_starts_dry_and_ends_submerged():
    first = scene.compose_right_jump_in(0)
    last = scene.compose_right_jump_in(scene.TRANS_FRAMES - 1)
    assert "E" in first[73] or "E" in first[71], "frame 0 should show the body on the shelf"
    assert "E" in last[83], "last frame should show the soak pose"
    assert "E" not in last[71]


def test_jump_out_ends_in_rest_pose():
    last = scene.compose_right_jump_out(scene.TRANS_FRAMES - 1)
    rest = scene.compose_right(0)
    assert last == rest, "jump-out must land exactly on the phase-0 rest frame"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_pool_hop_scene.py -v`
Expected: Task 1 tests PASS; new tests FAIL with `AttributeError: ... 'compose_right_submerged'`

- [ ] **Step 3: Implement in paint_scene.py**

Add after the `EAR_POSES`/`capy_right` block (around line 330):

```python
# --- pool-hop: submerged pose + jump transitions (all inside the anim band) ---

TRANS_FRAMES = 6

CAPY_R_SOAK = [        # crown + eyes just proud of the water (WATERLINE=84)
    ".cCCCCCCCc.",     # y82 crown
    "cCEACCCAECc",     # y83 eyes at the surface
]
CAPY_R_SOAK_ORIGIN = (4, 82)

EAR_POSES_SOAK = {     # absolute (x, y) cells; same flick rhythm as EAR_POSES
    0: [(7, 80), (7, 81), (11, 80), (11, 81)],
    1: [(7, 79), (7, 80), (11, 79), (11, 80)],
    2: [(6, 79), (7, 80), (12, 79), (11, 80)],
}

JUMP_FRAMES_IN = [     # (body_origin | None for soak pose, splash_step)
    ((1, 70), 0),      # crouch on the shelf
    ((2, 64), 0),      # spring
    ((3, 68), 1),      # arc out over the water
    ((4, 76), 3),      # impact -- body clipped at the waterline
    (None, 4),         # under: soak pose + big burst
    (None, 2),         # settle: soak pose + fading burst
]
JUMP_FRAMES_OUT = [
    (None, 1),         # gather
    ((4, 76), 3),      # burst upward
    ((3, 68), 2),      # arc back to the shelf
    ((2, 64), 0),      # apex
    ((1, 70), 0),      # land crouch
    ((1, 68), 0),      # settle into the rest pose
]


def stamp_clip(g, ox, oy, rows, y_max):
    """stamp(), but skip every subrow at or below y_max (waterline clipping)."""
    for r, line in enumerate(rows):
        if oy + r >= y_max:
            break
        for c, ch in enumerate(line):
            if ch != '.':
                put(g, ox + c, oy + r, ch)


def capy_right_soak(g, pose):
    stamp(g, *CAPY_R_SOAK_ORIGIN, CAPY_R_SOAK)
    for x, y in EAR_POSES_SOAK[pose]:
        put(g, x, y, 'c')


def _capy_right_at(g, ox, oy):
    """The dry body mask stamped at an arbitrary origin, clipped at the
    waterline, with rest-pose ears shifted by the same offset."""
    stamp_clip(g, ox, oy, CAPY_R_BODY, WATERLINE)
    dx, dy = ox - CAPY_R_ORIGIN[0], oy - CAPY_R_ORIGIN[1]
    for x, y in EAR_POSES[0]:
        if y + dy < WATERLINE:
            put(g, x + dx, y + dy, 'c')


def _base_right_grid_no_capy():
    g = fresh()
    sky(g, 'R')
    bamboo(g, 'R')
    rocks_right(g)
    lantern(g)
    pool(g, 'R')
    yuzu_right(g)
    return g


def compose_right_submerged(phase):
    g = _base_right_grid_no_capy()
    capy_right_soak(g, ws.ear_pose(phase))
    _overlay_on_water(g, ws.soak_ripple_cells(phase, 9, WATERLINE))
    _overlay(g, ws.steam_cells(phase, STEAM_SEEDS_R, WATERLINE - 1, STEAM_CEIL))
    return [''.join(r) for r in g]


def _compose_right_jump(table, frame):
    origin, splash = table[frame]
    g = _base_right_grid_no_capy()
    if origin is None:
        capy_right_soak(g, 0)
        _overlay_on_water(g, ws.soak_ripple_cells(frame, 9, WATERLINE))
    else:
        _capy_right_at(g, *origin)
    _overlay(g, ws.splash_cells(splash, 9, WATERLINE))
    _overlay(g, ws.steam_cells(frame, STEAM_SEEDS_R, WATERLINE - 1, STEAM_CEIL))
    return [''.join(r) for r in g]


def compose_right_jump_in(frame):
    return _compose_right_jump(JUMP_FRAMES_IN, frame)


def compose_right_jump_out(frame):
    return _compose_right_jump(JUMP_FRAMES_OUT, frame)
```

Notes for the implementer:
- `sky`, `bamboo`, `rocks_right`, `lantern`, `pool`, `yuzu_right`, `stamp`, `put`, `_overlay`, `_overlay_on_water`, `STEAM_SEEDS_R`, `STEAM_CEIL`, `ws` all already exist in this file — match the call order used by `compose_right` (line ~412).
- `test_jump_out_ends_in_rest_pose` requires the final out-frame to equal `compose_right(0)` exactly. `compose_right(0)` draws the dry capybara AND steam at phase 0. The last `JUMP_FRAMES_OUT` entry is `((1, 68), 0)` with `frame=5`, whose steam is `steam_cells(5, ...)`, which differs from phase 0 steam. Fix inside `_compose_right_jump`: for the final out-frame, delegate: in `compose_right_jump_out`, `if frame == TRANS_FRAMES - 1: return compose_right(0)`. Also note `_capy_right_at(g, 1, 68)` draws rest ears while `compose_right(0)` uses `ws.ear_pose(0) == 0` — same pose, consistent. Keep the delegation; it guarantees a seamless splice back to the loop.
- If any test fails on art details (eye char not at the asserted row), adjust the mask/origins — the asserts encode the pose contract (eyes at y83, ears y79–81, dry body gone, waterline clean).

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_pool_hop_scene.py -v`
Expected: all PASS

- [ ] **Step 5: Regression-check the untouched dry loop**

Run: `python3 -m pytest tests/test_pool_hop_scene.py -v && python3 examples/capybara-onsen-generator/compile.py`
Expected: tests PASS; compile.py prints its normal summary (`palette ... phases 16 ...`) with no assertion errors. Delete the generated file afterwards: `rm examples/capybara-onsen-generator/onsen-data.json`

- [ ] **Step 6: (Optional but encouraged) eyeball the poses**

`python3 examples/capybara-onsen-generator/paint_scene.py` writes `onsen-scene-preview.png` (macOS sips). This previews the DRY scene only; for the new poses, a quick throwaway script printing `compose_right_submerged(0)` rows 78–90 as text is enough to sanity-check shape. Do not commit throwaway scripts or PNGs.

- [ ] **Step 7: Commit**

```bash
git add examples/capybara-onsen-generator/paint_scene.py tests/test_pool_hop_scene.py
git commit -m "feat: submerged soak pose and jump-in/out transition frames"
```

---

### Task 3: compile.py — bake the new arrays into onsen-data.json

**Files:**
- Modify: `examples/capybara-onsen-generator/compile.py`
- Test: `tests/test_pool_hop_scene.py` (extend)

**Interfaces:**
- Consumes: Task 2's `compose_right_submerged`, `compose_right_jump_in`, `compose_right_jump_out`, `TRANS_FRAMES`.
- Produces (Task 4 consumes): three new `onsen-data.json` keys — `animRSub` (16 × 22 cellrows of `[fg,bg,count]` runs), `transInR` (6 × 22), `transOutR` (6 × 22) — same shapes/encoding as `animR`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_pool_hop_scene.py`:

```python
import importlib
import json


def test_compile_emits_pool_hop_arrays(tmp_path, monkeypatch):
    compile_mod = importlib.import_module("compile")
    monkeypatch.setattr(compile_mod, "OUT", tmp_path)
    compile_mod.main()
    data = json.loads((tmp_path / "onsen-data.json").read_text())
    assert data["phases"] == 16
    for key, count in (("animRSub", 16), ("transInR", 6), ("transOutR", 6)):
        assert key in data, f"missing {key}"
        assert len(data[key]) == count
        for frame in data[key]:
            assert len(frame) == data["animCellRows"]
            for cellrow in frame:
                assert sum(run[2] for run in cellrow) == data["w"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_pool_hop_scene.py::test_compile_emits_pool_hop_arrays -v`
Expected: FAIL with `KeyError`/assert on `'animRSub'`

- [ ] **Step 3: Extend compile.py main()**

In `main()`, after the existing `frames_l`/`frames_r` loop block (the `for wall, static_rows, frames in ...` checks, ends ~line 117), add:

```python
    # pool-hop frame sets: submerged idle loop + one-shot jump transitions
    assert scene.TRANS_FRAMES == 6, f'expected TRANS_FRAMES == 6, got {scene.TRANS_FRAMES}'
    frames_r_sub = [scene.compose_right_submerged(p) for p in range(scene.PHASES)]
    frames_r_in = [scene.compose_right_jump_in(f) for f in range(scene.TRANS_FRAMES)]
    frames_r_out = [scene.compose_right_jump_out(f) for f in range(scene.TRANS_FRAMES)]
    assert frames_r_sub[0] == scene.compose_right_submerged(0), 'compose_right_submerged not deterministic'
    for label, frames in (('submerged', frames_r_sub), ('jump_in', frames_r_in), ('jump_out', frames_r_out)):
        for i, frame in enumerate(frames):
            assert len(frame) == H, f'{label}[{i}]: expected {H} rows, got {len(frame)}'
            _check_v8_rule(f'right/{label}', static_r, i, frame)
            _check_chars(f'{label}({i})', frame)
    assert len({tuple(f) for f in frames_r_sub}) >= 2, 'submerged loop has no motion'
```

Then extend the `data` dict (lines 138–145) with three keys after `'animR': anim_r_runs,`:

```python
        'animRSub': [band_runs(frames_r_sub[p], STATIC_CELL_ROWS, CELL_ROWS) for p in range(scene.PHASES)],
        'transInR': [band_runs(frames_r_in[f], STATIC_CELL_ROWS, CELL_ROWS) for f in range(scene.TRANS_FRAMES)],
        'transOutR': [band_runs(frames_r_out[f], STATIC_CELL_ROWS, CELL_ROWS) for f in range(scene.TRANS_FRAMES)],
```

- [ ] **Step 4: Run the full scene test file**

Run: `python3 -m pytest tests/test_pool_hop_scene.py -v`
Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add examples/capybara-onsen-generator/compile.py tests/test_pool_hop_scene.py
git commit -m "feat: bake submerged and transition frame arrays into onsen data"
```

---

### Task 4: generate_package.py — trigger constant, runtime state machine, 9th op; regenerate package; update package tests

This is the largest task. Everything lands in one task because the template, the regenerated package, and the package tests must change in the same commit to keep parity green.

**Files:**
- Modify: `examples/capybara-onsen-generator/generate_package.py`
- Regenerate: `packages/capybara-onsen/` (patch.json + payloads + README — via the generator, never by hand)
- Modify: `tests/test_capybara_onsen.py`

**Interfaces:**
- Consumes: Task 3's `animRSub`/`transInR`/`transOutR` data keys.
- Produces: package op `capy-onsen-assistant-text-hook-2-1-201`; JS names `__coTriggers`, `__coSoak`, `__coSoakHoldTicks`, `__coOnAssistantText(n)`, `__coSoakTick()`, `__coRightAnim(ph)`, `__coAnimRSub`, `__coTransInR`, `__coTransOutR`.

- [ ] **Step 1: Write the failing test updates**

In `tests/test_capybara_onsen.py`:

(a) Extend the expected op-id list (currently 8 entries, lines ~50–60) with a 9th entry at the end:

```python
        "capy-onsen-assistant-text-hook-2-1-201",
```

(b) In the payload-markers test, REPLACE the line

```python
    assert "%__coPhases),180)" in joined               # water/steam animation tick, 180ms
```

with:

```python
    assert "%__coPhases)},180)" in joined              # tick: soak state machine + phase advance
    assert "function __coOnAssistantText" in joined
    assert "function __coSoakTick" in joined
    assert "function __coRightAnim" in joined
    assert "__coAnimRSub" in joined
    assert "__coTransInR" in joined
    assert "__coTransOutR" in joined
    assert "__coSoakHoldTicks=111" in joined
    assert "hopping in the pool" in joined
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_capybara_onsen.py -v`
Expected: FAIL on the op-id list (8 != 9) and on the new markers.

- [ ] **Step 3: Edit generate_package.py — trigger constant**

Near the top (after imports, before `VERSION_FRAGILE_ANCHORS`), add:

```python
# Trigger phrases for the pool-hop scene change. Case-insensitive substring
# match against assistant message text. Edit here and regenerate.
TRIGGER_PHRASES = [
    "hopping in the pool",
    "hop in the pool",
    "hopping into the pool",
]
```

The helper template (next step) contains the token `__TRIGGERS__`; substitute it where `CONFIG` is built so the emitter stays untouched:

```python
import json as _json
HELPER_TEMPLATE = HELPER_TEMPLATE.replace("__TRIGGERS__", _json.dumps(TRIGGER_PHRASES))
```

(Adapt to the file's actual structure: the template string is assigned once and referenced by `CONFIG["helper_template"]` — perform the `.replace(...)` before `CONFIG` is constructed. Note `__DATA__` substitution happens later inside the emitter; only `__TRIGGERS__` is substituted here.)

- [ ] **Step 4: Edit HELPER_TEMPLATE — new arrays + state machine**

All template edits below are inside the single-line JS helper template string. Keep everything minified-style (no newlines beyond what the template already uses, no literal `▀`/ESC).

(a) After the existing anim-array assembly

```js
let __coAnimL=[],__coAnimR=[];for(let p=0;p<__coPhases;p++){__coAnimL.push(__coAssemble(__coData.animL[p],__coClipColsV7,0));__coAnimR.push(__coAssemble(__coData.animR[p],0,__coClipColsV7))}
```

append:

```js
let __coAnimRSub=[],__coTransInR=[],__coTransOutR=[];for(let p=0;p<__coData.animRSub.length;p++)__coAnimRSub.push(__coAssemble(__coData.animRSub[p],0,__coClipColsV7));for(let f=0;f<__coData.transInR.length;f++)__coTransInR.push(__coAssemble(__coData.transInR[f],0,__coClipColsV7));for(let f=0;f<__coData.transOutR.length;f++)__coTransOutR.push(__coAssemble(__coData.transOutR[f],0,__coClipColsV7));
let __coTriggers=__TRIGGERS__.map((s)=>s.toLowerCase());
let __coSoak={queue:0,mode:0,frame:0,hold:0,seen:new Map()};
let __coSoakHoldTicks=111;
function __coOnAssistantText(n){try{let m=n&&n.message,id=m&&m.id,c=m&&m.content;if(!id||!Array.isArray(c))return;let txt="";for(let i=0;i<c.length;i++){let b=c[i];if(b&&b.type==="text"&&typeof b.text==="string")txt+="\n"+b.text}txt=txt.toLowerCase();let count=0;for(let i=0;i<__coTriggers.length;i++){let t=__coTriggers[i],from=0;if(!t)continue;for(;;){let at=txt.indexOf(t,from);if(at<0)break;count++;from=at+t.length}}let prev=__coSoak.seen.get(id)||0;if(count>prev){__coSoak.queue+=count-prev;__coSoak.seen.set(id,count)}}catch(e){}}
function __coSoakTick(){let s=__coSoak;if(s.mode===0){if(s.queue>0){s.queue--;s.mode=1;s.frame=0}}else if(s.mode===1){if(++s.frame>=__coTransInR.length){s.mode=2;s.hold=__coSoakHoldTicks}}else if(s.mode===2){if(--s.hold<=0){s.mode=3;s.frame=0}}else if(++s.frame>=__coTransOutR.length){s.mode=0;s.frame=0}}
function __coRightAnim(ph){let s=__coSoak;if(s.mode===1)return __coTransInR[Math.min(s.frame,__coTransInR.length-1)];if(s.mode===2)return __coAnimRSub[ph];if(s.mode===3)return __coTransOutR[Math.min(s.frame,__coTransOutR.length-1)];return __coAnimR[ph]}
```

Semantics locked by the spec: `mode` 0=dry, 1=jumpIn, 2=soak, 3=jumpOut. Queue consumed on hop-in; retriggers during a soak queue further complete cycles. 111 ticks × 180ms ≈ 20.0s. The `seen` Map keys on `n.message.id` and stores the max occurrence count, so streaming growth enqueues only the delta and re-renders enqueue nothing.

(b) Change the wall components to take a resolved frame string instead of (array, index). Replace:

```js
function __coWall(staticStr,animStrs,ph,key){return Xd.jsxs(B,{flexShrink:0,flexDirection:"column",backgroundColor:"rgb(10,12,26)",children:[__coRawNode(staticStr,__coStaticRows,key+"-static"),__coRawNode(animStrs[ph],__coAnimRows,key+"-anim")]},key)}
function __coSideWallV4(staticStr,animStrs,ph,height,key){let sw=__coW;return Xd.jsx(B,{width:sw,flexShrink:0,flexGrow:0,height:height,overflow:"hidden",flexDirection:"column",justifyContent:"flex-end",backgroundColor:"rgb(10,12,26)",children:__coWall(staticStr,animStrs,ph,key+"-wall")},key)}
```

with:

```js
function __coWall(staticStr,animStr,key){return Xd.jsxs(B,{flexShrink:0,flexDirection:"column",backgroundColor:"rgb(10,12,26)",children:[__coRawNode(staticStr,__coStaticRows,key+"-static"),__coRawNode(animStr,__coAnimRows,key+"-anim")]},key)}
function __coSideWallV4(staticStr,animStr,height,key){let sw=__coW;return Xd.jsx(B,{width:sw,flexShrink:0,flexGrow:0,height:height,overflow:"hidden",flexDirection:"column",justifyContent:"flex-end",backgroundColor:"rgb(10,12,26)",children:__coWall(staticStr,animStr,key+"-wall")},key)}
```

Then update EVERY `__coSideWallV4(` call site in the template (grep the template for all of them — the main window has two, and check `__CodexCapyOnsenFallbackWindowV4` for more):
- left wall: `__coSideWallV4(__coStaticL,__coAnimL[ph],n,"codex-capy-onsen-v4-left")`
- right wall: `__coSideWallV4(__coStaticR,__coRightAnim(ph),n,"codex-capy-onsen-v6-right-responsive")`
- any fallback-window call sites: same transformation (`__coAnimL[ph]` / `__coRightAnim(ph)` with their existing height/key args).

(c) Change the tick in `__CodexCapyOnsenMainWindowV4`. Replace:

```js
A_.useEffect(()=>{let tk=setInterval(()=>setPh((p)=>(p+1)%__coPhases),180);return()=>clearInterval(tk)},[])
```

with:

```js
A_.useEffect(()=>{let tk=setInterval(()=>{__coSoakTick();setPh((p)=>(p+1)%__coPhases)},180);return()=>clearInterval(tk)},[])
```

(If the fallback window has its own interval, apply the same change there — but only ONE component's interval should call `__coSoakTick()` if both can mount simultaneously; check the template: if fallback and main window are mutually exclusive mounts, both may call it safely. If unsure, leave the fallback interval as pure phase advance — the soak machine then only runs in the main window, which is the normal path.)

- [ ] **Step 5: Add the 9th anchor entry**

Append to `VERSION_FRAGILE_ANCHORS` (LAST entry, so it becomes op/payload 09):

```python
{
    'slug': 'assistant-text-hook',
    'label': 'Feed assistant message text to the pool-hop trigger before the transcript-item switch',
    'exact': 'S=_===void 0?!1:_;',
    'replacement': 'S=_===void 0?!1:_;n.type==="assistant"&&typeof __coOnAssistantText==="function"&&__coOnAssistantText(n);',
    'requireWithinRange': ['S=_===void 0?!1:_;'],
    'knownBehaviorChange': 'Scans assistant message text for pool-hop trigger phrases; scene-only side effect, message rendering unchanged.',
},
```

The emitter verifies anchor uniqueness against the real module at generation time (SystemExit if not exactly 1 occurrence) — this is the guard that the anchor still holds on 2.1.201.

- [ ] **Step 6: Update the package README text**

`CONFIG["extra_files"]["README.md"]` contains the shipped package README. Add a short section documenting the trigger: phrases live in `TRIGGER_PHRASES` in the generator; behavior (hop in, ~20s soak, hop out, queued retriggers); and that op 09 is the text hook.

- [ ] **Step 7: Regenerate the package**

```bash
python3 examples/capybara-onsen-generator/generate_package.py \
  --source ~/.local/share/claude/versions/2.1.201 \
  --source-version 2.1.201 \
  --source-version-output "2.1.201 (Claude Code)"
```

Expected output: wrote `packages/capybara-onsen`, 9 operations. `git status` should show modified `patch.json`, modified payload 01, new payload 09 (and README). Payloads 02–08 must be byte-identical (only 01 and 09 change) — if others changed, something is wrong; investigate before committing.

- [ ] **Step 8: Run the package + parity + scene tests**

Run: `python3 -m pytest tests/test_capybara_onsen.py tests/test_generator_parity.py tests/test_pool_hop_scene.py -v`
Expected: ALL PASS (the live 2.1.201 binary is present, so validate_package and parity run for real).

- [ ] **Step 9: Commit**

```bash
git add examples/capybara-onsen-generator/generate_package.py packages/capybara-onsen tests/test_capybara_onsen.py
git commit -m "feat: pool-hop trigger — assistant-text hook op, soak state machine, baked variants"
```

---

### Task 5: non-overlap regression test vs fable-fallback

**Files:**
- Create: `tests/test_pool_hop_conflicts.py`

**Interfaces:**
- Consumes: `packages/capybara-onsen/patch.json` (op 09 from Task 4), `packages/fable-fallback/patch.json`.

- [ ] **Step 1: Write the test**

```python
"""The pool-hop text hook must never overlap fable-fallback's claimed range.

Byte-level regression: resolves both packages' claims in the real 2.1.201
module and asserts ordering. Complements builder-level check_planned_conflicts.
"""
import json
from pathlib import Path

import pytest

from tests.claude_binary import claude_version_path

ROOT = Path(__file__).resolve().parents[1]
LIVE_SOURCE = claude_version_path("2.1.201")
MODULE = "/$bunfs/root/src/entrypoints/cli.js"


def _module_text() -> str:
    import sys
    sys.path.insert(0, str(ROOT / "examples"))
    from art_package_emitter import module_content  # reuse the generator's extractor
    source_bytes = LIVE_SOURCE.read_bytes()
    return module_content(source_bytes, MODULE)


def test_hook_anchor_sits_strictly_before_fable_fallback_claim():
    if not LIVE_SOURCE.exists():
        pytest.skip(f"local Claude Code 2.1.201 source missing: {LIVE_SOURCE}")
    module = _module_text()

    capy = json.loads((ROOT / "packages/capybara-onsen/patch.json").read_text())
    capy_ops = capy["patch"]["targets"][0]["modules"][0]["operations"]
    hook = next(op for op in capy_ops if op["opId"].startswith("capy-onsen-assistant-text-hook"))
    anchor = hook["exact"]
    assert module.count(anchor) == 1, "hook anchor no longer unique in module"
    hook_end = module.find(anchor) + len(anchor)

    fable = json.loads((ROOT / "packages/fable-fallback/patch.json").read_text())
    fable_ops = fable["patch"]["targets"][0]["modules"][0]["operations"]
    banner = next(op for op in fable_ops if op["type"] == "replace_between")
    start_marker = banner["startMarker"]
    assert module.count(start_marker) == 1, "fable-fallback start marker no longer unique"
    fable_start = module.find(start_marker)

    assert hook_end <= fable_start, (
        f"pool-hop hook range end {hook_end} overlaps fable-fallback claim start {fable_start}"
    )
```

Adapt `module_content`'s exact signature to what `examples/art_package_emitter.py` actually exposes (the generator calls it to decode the module from binary bytes); if it is a private helper with a different name/signature, mirror the few lines it uses (`inspect_binary_bytes` → `find_macho_layout` → `parse_bun_section`) rather than duplicating logic elsewhere.

- [ ] **Step 2: Run it**

Run: `python3 -m pytest tests/test_pool_hop_conflicts.py -v`
Expected: PASS (binary present).

- [ ] **Step 3: Commit**

```bash
git add tests/test_pool_hop_conflicts.py
git commit -m "test: pool-hop hook must not overlap fable-fallback claimed range"
```

---

### Task 6: full-suite verification + build + manual smoke handoff

**Files:** none new (verification only)

- [ ] **Step 1: Full test suite**

Run: `python3 -m pytest tests/ -v`
Expected: everything green (pre-existing unrelated failures, if any, must be listed explicitly in the report — do not fix them here).

- [ ] **Step 2: Lint**

Run: `ruff check examples/capybara-onsen-generator tests` (the repo has `.ruff_cache`, so ruff is in use)
Expected: clean, or fix new-code findings only.

- [ ] **Step 3: Build a patched binary**

Copy the regenerated package into the claude-monkey state dir and build (see CLAUDEMONKEY.md):

```bash
cp -R packages/capybara-onsen ~/.claude-monkey/patches/
claude-monkey build
claude-monkey status --json
```

Expected: build succeeds with capybara-onsen (9 ops) planned alongside the other enabled packages — the builder's `check_planned_conflicts` passing WITH fable-fallback enabled is the end-to-end proof of non-overlap. If hotrod-dragons is staged, the known mutual exclusivity with capybara-onsen applies exactly as before this feature — resolve the same way the user already does.

- [ ] **Step 4: Manual smoke (USER GATE — do not claim done)**

`manualSmoke.required = true`. Report to the user that the build is ready and ask them to verify in a truecolor terminal:
1. Scene renders normally (dry capybara, ear flicks).
2. Ask the patched Claude to say "hopping in the pool" → capybara hops in with splash.
3. Soak pose: only eyes/ears above the waterline, ears still flick; lasts ~20s.
4. He climbs back out and resumes the rest pose seamlessly.
5. Say the phrase twice in one response → after the first soak he climbs out and hops back in.

Do NOT mark the feature complete until the user confirms the smoke pass.
