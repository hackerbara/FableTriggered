# Schema Unification, Re-Pin & Generator Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One public manifest format (package-model, `schemaVersion: 1` + `kind`), all 9 ship packages re-pinned to the latest local Claude Code binary, art-package generators regenerating the live packages byte-for-byte — and the current schema/build-semantics test failures resolved along the way.

**Architecture:** The builder (`builder_v15.py`) currently accepts three manifest generations via a fragile dispatch. We make package-model the only format, migrate the 5 remaining flat-v2 manifests, delete the dead legacy loader, then re-pin every ship package against the newest binary — with `capybara-onsen`/`hotrod-dragons` re-pinned *through* their generators in `examples/` so generator output ≡ shipped package from now on (enforced by a parity test).

**Tech Stack:** Python 3.11+/uv, pytest. No new dependencies.

**Runbook context:** This implements tasks 1.4, 1.5, 1.3b, and 1.2 of `docs/superpowers/plans/2026-07-04-harnessmonkey-launch-runbook.md`. Read its "Locked decisions" first. Do NOT rename anything (`claude_monkey`, `hotrod-dragons`, etc.) — the Phase-2 rename sweep owns that.

## Global Constraints

- Public manifest format: `schemaVersion: 1` with `kind` REQUIRED (`patch`/`prompt`/`option`). Flat-v2 and legacy-v1 cease to exist.
- Cut packages (`dvd-cursor-*` ×3, `reminder-suppression`) get NO migration/re-pin work. If runbook task 1.1 hasn't deleted them yet when you start, skip them everywhere below.
- Ship set for re-pin (9): `capybara-onsen`, `hotrod-dragons`, `fable-fallback`, `hidden-context-drawer`, `normal-channel-hidden-context`, `reminders-manager`, `upstream-attachment-suppression`, `thinking-text-drawer`, `footer-drawers`.
- Suite must be green (minus tests belonging to un-deleted cut packages) at every commit.
- Manual-smoke gate is BYPASSED by product decision (see `builder_v15.py:709-717` comment). Tests asserting `manual_smoke_pending` are wrong, not the builder.
- Never hand-edit `packages/capybara-onsen/**` or `packages/hotrod-dragons/**` payloads after Task 6 — regenerate via `examples/`.

## Current state (verified 2026-07-04, ~17:00)

Manifest census (`packages/*/patch.json`):

| Format | Packages |
|---|---|
| package-model (`schemaVersion:1`+`kind`) — already done | `fable-fallback`, `normal-channel-hidden-context`, `thinking-text-drawer`, `upstream-attachment-suppression` (+ cut `reminder-suppression`) |
| flat-v2 (`schemaVersion:2`) — **to migrate** | `capybara-onsen`, `hotrod-dragons`, `footer-drawers`, `hidden-context-drawer`, `reminders-manager` (+ 3 cut `dvd-cursor-*`) |

Pins: v2 ship packages are on `2.1.201`; the package-model ones declare `compatibility.claudeVersions` (thinking-text-drawer: `2.1.201`) — verify each in Task 5. `normal-channel-hidden-context` historically carried a dual pin (2.1.198+2.1.199 targets in one manifest) — confirm its current targets and collapse to one during Task 5.

Failing tests (15 total; `uv run pytest -q` baseline `b1d87de`):
- `tests/test_footer_drawers_package.py` (8) — mostly `assert report.status == "manual_smoke_pending"` vs actual `"verified"`: stale expectations vs the manual-smoke-bypass decision → fix in Task 0.
- `tests/test_footer_drawers_faithful_spike_port.py` (3) — triage in Task 0 (same suspicion).
- `tests/test_reference_packages.py` (2), `tests/test_reminders_manager.py` (1) — triage in Task 0; schema-shape assertions get properly rewritten in Task 4.
- `tests/test_dvd_cursor_goblin.py` (1) — cut package, out of scope, dies with runbook 1.1.

---

### Task 0: Reconcile stale test expectations with merged reality

**Files:**
- Modify: `tests/test_footer_drawers_package.py`
- Modify: `tests/test_footer_drawers_faithful_spike_port.py`
- Modify: `tests/test_reference_packages.py`
- Modify: `tests/test_reminders_manager.py`

**Interfaces:**
- Produces: a green baseline (only the dvd-goblin failure remaining) that Tasks 1-6 build on.

- [ ] **Step 1: Enumerate the failures with reasons**

Run: `uv run pytest tests/test_footer_drawers_package.py tests/test_footer_drawers_faithful_spike_port.py tests/test_reference_packages.py tests/test_reminders_manager.py -q 2>&1 | grep -A6 "^_____"`

- [ ] **Step 2: Classify each failure using these decision rules**

1. Assertion expects `status == "manual_smoke_pending"` or `activationBlockers` containing `manual_smoke_pending` → **stale expectation.** The build now reports `status == "verified"`, `manualSmoke == {"required": True, "status": "bypassed", "reason": <str|None>}`, `activationEligible == True` (see `builder_v15.py:709-733`). Update the assertion to the new contract — and keep asserting `manualSmoke["required"] is True` so the "this package wants manual smoke" signal stays tested.
2. Assertion about manifest dict shape (`schemaVersion`, field names) failing on a package listed as package-model in the census above → **stale schema expectation.** Patch minimally here; Task 4 rewrites these properly. Do not migrate any manifest in this task.
3. Anything else (op anchoring, payload content) → genuine regression: fix the TEST only if the packaged content is verifiably intentional (check `git log -2 --oneline -- <package-dir>`); otherwise STOP and report to the user before touching it.

- [ ] **Step 3: Apply the fixes**
- [ ] **Step 4: Verify**

Run: `uv run pytest -q`
Expected: `1 failed` (only `tests/test_dvd_cursor_goblin.py`), everything else passes.

- [ ] **Step 5: Commit**

```bash
git add tests/test_footer_drawers_package.py tests/test_footer_drawers_faithful_spike_port.py tests/test_reference_packages.py tests/test_reminders_manager.py
git commit -m "test: reconcile expectations with manual-smoke bypass and merged packages"
```

---

### Task 1: Make package-model manifests lossless (add `packageVersion`)

The v3→builder conversion hardcodes `"packageVersion": "0.0.0"` (`builder_v15.py:85`) because `PackageManifest` has no version field. Add it.

**Files:**
- Modify: `src/claude_monkey/package_model.py` (TOP_LEVEL_FIELDS ~line 21, `PackageManifest` ~line 109, loader `load_package_manifest`)
- Modify: `src/claude_monkey/builder_v15.py:76-89` (`_v3_manifest_as_v2_dict`)
- Test: `tests/test_package_model_v3.py`

**Interfaces:**
- Produces: `PackageManifest.package_version: str` (default `"0.0.0"` when absent); manifest key `packageVersion` accepted at top level; `_v3_manifest_as_v2_dict` passes it through.

- [ ] **Step 1: Write the failing test** (in `tests/test_package_model_v3.py`, following its existing fixture style — read the file first)

```python
def test_package_version_round_trips(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "patch.json").write_text(json.dumps({
        "schemaVersion": 1, "kind": "patch", "id": "x", "label": "X",
        "description": "d", "packageVersion": "1.2.3",
        "patch": {"engine": "bun_graph_repack", "targets": []},
    }))
    manifest = load_package_manifest(pkg, PackageKind.PATCH)
    assert manifest.package_version == "1.2.3"
```

- [ ] **Step 2: Run it — expect FAIL** (`unexpected field: packageVersion` or `AttributeError: package_version`)
- [ ] **Step 3: Implement** — add `"packageVersion"` to `TOP_LEVEL_FIELDS`; add `package_version: str = "0.0.0"` to `PackageManifest`; parse it (optional string, default `"0.0.0"`) in the loader; in `_v3_manifest_as_v2_dict` replace `"packageVersion": "0.0.0"` with `"packageVersion": manifest.package_version`.
- [ ] **Step 4: Run — expect PASS**, plus `uv run pytest tests/test_package_model_v3.py tests/test_builder_v15.py -q` green.
- [ ] **Step 5: Commit** — `git commit -m "feat: packageVersion field on package-model manifests (lossless build conversion)"`

---

### Task 2: Package-model becomes the ONLY accepted format

**Files:**
- Modify: `src/claude_monkey/builder_v15.py:92-107` (`load_manifest_v2`)
- Test: `tests/test_builder_v15.py`

**Interfaces:**
- Produces: `load_manifest_v2(package_dir)` → parses via `load_package_manifest` ONLY; any `patch.json` with `schemaVersion != 1` or missing `kind` raises `ManifestV2Error("unsupported_manifest_format: expected schemaVersion 1 with kind")`. (`ManifestV2` remains the internal representation — flat-v2 stops being a *file* format, not an in-memory one.)

- [ ] **Step 1: Failing tests**

```python
def test_flat_v2_manifest_rejected(tmp_path):
    pkg = tmp_path / "pkg"; pkg.mkdir()
    (pkg / "patch.json").write_text(json.dumps({
        "schemaVersion": 2, "id": "x", "name": "X", "description": "d",
        "packageVersion": "0.0.1", "targets": [],
    }))
    with pytest.raises(ManifestV2Error, match="unsupported_manifest_format"):
        load_manifest_v2(pkg)

def test_schema_one_without_kind_rejected(tmp_path):
    pkg = tmp_path / "pkg"; pkg.mkdir()
    (pkg / "patch.json").write_text(json.dumps({"schemaVersion": 1, "id": "x"}))
    with pytest.raises(ManifestV2Error, match="unsupported_manifest_format"):
        load_manifest_v2(pkg)
```

- [ ] **Step 2: Run — expect FAIL** (currently both parse or raise differently)
- [ ] **Step 3: Implement** — in `load_manifest_v2`, delete the `schemaVersion == 2 or (schemaVersion == 1 and "kind" not in data)` branch; validate `data.get("schemaVersion") == 1 and "kind" in data`, else raise the error above; always route through `_v3_manifest_as_v2_dict`.
- [ ] **Step 4: Run the suite.** EXPECTED COLLATERAL: every test building the 5 not-yet-migrated packages now fails — that's Task 3's cue, not a bug. Verify the two new tests pass and failures are exactly the un-migrated-package builds. **Do not commit yet** — Task 3 lands atomically with this.

---

### Task 3: Migrate the 5 flat-v2 manifests

**Files:**
- Create: `.development/migrate_v2_to_package_model.py` (one-shot, stays local — `.development/` is gitignored)
- Modify: `packages/{capybara-onsen,hotrod-dragons,footer-drawers,hidden-context-drawer,reminders-manager}/patch.json`

**Interfaces:**
- Consumes: Task 2's strict loader.
- Produces: all ship manifests in package-model form.

- [ ] **Step 1: Write the converter.** Mapping (flat-v2 → package-model):

```python
new = {
    "schemaVersion": 1,
    "kind": "patch",
    "id": old["id"],
    "label": old["name"],                      # v2 "name" → v3 "label"
    "description": old["description"],
    "packageVersion": old.get("packageVersion", "0.0.0"),
    "compatibility": {"claudeVersions": sorted({
        t["sourceIdentity"]["claudeVersion"] for t in old["targets"]})},
    "patch": {"engine": "bun_graph_repack", "targets": old["targets"]},
}
for key in ("requiresPackages", "conflictsWithPackages"):
    if old.get(key): new[key] = old[key]
```

Preserve any other top-level v2 keys by printing them and STOPPING for review (don't silently drop unknown fields).

- [ ] **Step 2: Run it on the 5 packages; spot-check one diff by eye** (`git diff packages/footer-drawers/patch.json`).
- [ ] **Step 3: Verify** — `uv run pytest -q`: back to the Task-0 baseline (only dvd-goblin failing). Also `uv run claude-monkey validate-package packages/footer-drawers` succeeds.
- [ ] **Step 4: Commit Tasks 2+3 together** — `git commit -m "feat!: package-model is the only manifest format; migrate remaining packages"`

---

### Task 4: Reference tests assert the unified format

**Files:**
- Modify: `tests/test_reference_packages.py` (PACKAGE_DIRS ~lines 15-21; schema assertions ~lines 38-43)

- [ ] **Step 1:** Extend `PACKAGE_DIRS` to all 9 ship packages (census list above; drop `reminder-suppression` if still listed).
- [ ] **Step 2:** Replace `manifest.schema_version == 2` assertions: load each `patch.json` raw and assert `data["schemaVersion"] == 1`, `data["kind"] == "patch"`, `"label" in data`, plus `load_manifest_v2(pkg_dir)` succeeds (proving builder compatibility).
- [ ] **Step 3:** `uv run pytest tests/test_reference_packages.py -q` → green. Full suite → Task-0 baseline.
- [ ] **Step 4: Commit** — `git commit -m "test: reference contract covers all 9 ship packages on unified schema"`

---

### Task 5: Delete the legacy loader (runbook 1.2)

**Files:**
- Delete: `src/claude_monkey/manifest.py`, `src/claude_monkey/builder.py`
- Delete (after verifying they ONLY exercise the deleted modules — read imports first): `tests/test_manifest.py`, `tests/test_builder.py`, and the legacy-only parts of `tests/test_patch_ops.py`, `tests/test_payloads.py`
- Possibly delete: `src/claude_monkey/patch_ops.py`, `src/claude_monkey/payloads.py` — ONLY if `rg -l "patch_ops|payloads" src/ --type py` shows no non-legacy consumers.

- [ ] **Step 1:** `rg -n "from claude_monkey import manifest|from claude_monkey.manifest import|import claude_monkey.manifest|from claude_monkey.builder import|from claude_monkey import builder\b" src/ tests/` — confirm consumers are tests-only. If ANY `src/` module imports them, STOP and report.
- [ ] **Step 2:** Delete files; run `uv run pytest -q` (Task-0 baseline) and `uv run claude-monkey list-patches` (still works).
- [ ] **Step 3: Commit** — `git commit -m "refactor: delete legacy v1 manifest/builder path"`

---

### Task 6: Re-pin all 9 packages to the latest binary; generator parity for the art packages

This is the long pole and partly investigative. Work the non-art packages first, art packages last.

**Files:**
- Modify: `packages/*/patch.json` + payload files for the 7 non-art packages (as anchoring requires)
- Modify: `examples/capybara-onsen-generator/*`, `examples/hotrod-dragons-generator/*`
- Create: `tests/test_generator_parity.py`
- Modify: `examples/*/README.md` (drop the "output may not byte-match" language)

**Known unknowns — read before starting:**
1. *How far has the binary moved past 2.1.201?* Ops use exact sha256 + `replace_exact`/`insert_after` anchors; a minified-identifier reshuffle means re-authoring, not re-hashing. Budget grows accordingly.
2. *Generator staleness is structural:* the example generators emit the pre-responsive fullscreen scene (one payload set), while live packages have the responsive frame + gutter/breakpoint payloads (`78f2b2c`, `3364d04` — split/renamed payloads like `02-capy-onsen-center-columns-a-2-1-201.js`). Porting means teaching `generate_package.py` (and possibly `compile*.py`) the responsive op structure — diff the live `patch.json` targets against what the generator emits to scope it.
3. *DANGER:* `examples/*/generate_package.py` writes DIRECTLY into `packages/<pkg>/` (this overwrote capy once already — see example READMEs). Run only when you intend to regenerate, and `git diff` immediately after.

- [ ] **Step 1: Identify the target binary**

```bash
ls ~/.local/share/claude/versions/ | sort -V | tail -3
claude --version
uv run claude-monkey inspect-binary "$(which claude)" --json
```
The re-pin target is the newest local version. Record version + sha256. If it's still 2.1.201, Tasks 6.2-6.3 collapse to verification-only for the packages already pinned there.

- [ ] **Step 2: Re-pin the 7 non-art packages** — for each of `fable-fallback`, `hidden-context-drawer`, `normal-channel-hidden-context`, `reminders-manager`, `upstream-attachment-suppression`, `thinking-text-drawer`, `footer-drawers`: update every target's `sourceIdentity` (claudeVersion, versionOutput, sha256, sizeBytes) and module `content_sha256`/`content_length` to the new binary (`inspect-binary` gives module hashes); collapse `normal-channel-hidden-context` to a single target while there; build:

```bash
uv run claude-monkey build --help   # check real flag names first — do not trust this plan's guess
uv run claude-monkey build <flags selecting only this package> # output under .development/repin-check
```
Anchoring failure ⇒ locate the moved code in the new module (`rg` the anchor text in the extracted bundle), re-author the op, document what moved in the commit message. One commit per package: `git commit -m "chore(<pkg>): re-pin to <version>"`.

- [ ] **Step 3: Port responsive structure into the generators.** For each art package: `python3 -c "import json; ..."`-diff the live `patch.json` target ops vs generator-emitted ops (op ids, types, anchors, payload refs); port the responsive payload emission into `examples/<pkg>-generator/generate_package.py` (+ upstream `compile*.py` if scene data changed); update the generator's `SOURCE`/pin constants to the Step-1 binary.
- [ ] **Step 4: Regenerate both art packages** via the generators; `git diff packages/capybara-onsen packages/hotrod-dragons` — review op structure matches live-plus-new-pin intent; build both against the binary as in Step 2.
- [ ] **Step 5: Parity test** (`tests/test_generator_parity.py`):

```python
import os, subprocess, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
CASES = [("capybara-onsen", "capybara-onsen-generator"),
         ("hotrod-dragons", "hotrod-dragons-generator")]

@pytest.mark.parametrize("pkg,gen", CASES)
def test_generator_regenerates_live_package(pkg, gen, tmp_path, monkeypatch):
    """Generator output must byte-match packages/<pkg> (user decision 2026-07-04)."""
    out = tmp_path / pkg
    env_target = {"HM_GENERATE_OUT": str(out)}  # generator must honor this env
    subprocess.run([sys.executable, ROOT / "examples" / gen / "generate_package.py"],
                   check=True, env={**os.environ, **env_target})
    live = ROOT / "packages" / pkg
    gen_files = {p.relative_to(out): p.read_bytes() for p in out.rglob("*") if p.is_file()}
    live_files = {p.relative_to(live): p.read_bytes() for p in live.rglob("*") if p.is_file()
                  if p.name != "preview.png"}  # preview is hand-captured, not generated
    assert gen_files == live_files
```

Requires adding `HM_GENERATE_OUT` env-override support to both `generate_package.py` scripts (default stays `packages/<pkg>` for intentional regeneration) — this also de-fangs unknown #3 for test runs.
- [ ] **Step 6:** Update both example READMEs: generators are now authoritative; remove "may not byte-match"; document `HM_GENERATE_OUT`.
- [ ] **Step 7:** Full suite green (Task-0 baseline); commit — `git commit -m "feat: re-pin art packages via generators; enforce generator parity"`

---

## Self-review notes

- Task 2/3 land atomically (suite would be red between them).
- `packageVersion` semantics unchanged for existing package-model manifests (default `"0.0.0"` matches today's hardcode).
- The `manifest_v2.py` module is NOT deleted — it's the internal target representation. Only file-format acceptance narrows.
- After this plan, runbook 1.4/1.5/1.3b/1.2 check off; 1.1 (cuts) and 1.7/1.7a remain in Phase 1.
