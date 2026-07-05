# Review handoff: composition-engine structured splices implementation

**To:** the implementer agent for the `composition-engine-structured-splices` worktree
(`/Users/MAC/.config/superpowers/worktrees/Claude-patch/composition-engine-structured-splices`, commits `0fc4ba2..ad73ef4`)
**From:** review session 2026-07-04 (9 finder angles + 3 adversarial verifiers + first-hand diff read + full suite run)
**Plan reviewed against:** `docs/superpowers/plans/2026-07-04-composition-engine-structured-splices.md`
**Spec:** `docs/superpowers/specs/2026-07-03-composition-engine-structured-splices-design.md` (amended 2026-07-04)

## Verdict

**High-quality, plan-compliant implementation.** All 12 tasks map to commits and match required semantics; spec validation rules 1–7, anchor-evidence disjointness, structured error codes, and all three pre-handoff review fixes (stable inserter-first role order; conflict pre-pass before the postcondition heuristic; seamHint rejected on legacy ops) are correctly in place. Legacy `replace_exact`/`replace_between` resolution verified byte-identical to main. `bun_graph.py`/`macho.py`/`repack.py` untouched. Suite: 408 passed, 1 skipped. You also caught and closed a hole the plan left open (`contextSha256` without context markers on insertions) — good catch, keep it.

**Four required changes before merge** (one is yours, three are plan-originated defects you faithfully implemented — attribution below is about where the bug came from, not about fault; fix all four). Then a set of recommended cleanups and one benchmarked nice-to-have.

**Attribution summary:** R1 is the only implementer-attributable issue. R2–R4 and most cleanups originate in the plan/spec text itself and shipped because you (correctly) followed it.

---

## Required changes

### R1 — Revert commit `7fbc201` (hotrod-dragons package) — scope violation *(implementer-attributable)*

`packages/hotrod-dragons/` (README, patch.json, 5 payloads, preview.png) is a real UI patch package committed into an engine branch whose plan says: "Do NOT migrate any real package." Root cause understood and verified: `tests/test_reference_packages.py` on main hard-lists `packages/hotrod-dragons` in `PACKAGE_DIRS`, but that package was never committed to main — it exists only as untracked WIP in the primary working copy, so every clean worktree of main starts red on that test. The right move was to report it as pre-existing red (exactly as the plan does for `test_dvd_cursor_goblin.py`), not to commit a copy of someone else's uncommitted package to make the test pass.

**Fix:** `git revert 7fbc201` (or rebase it out). Note the resulting expected-red of `test_reference_packages.py` in your final report, alongside the dvd-cursor-goblin exclusion. Do not modify `test_reference_packages.py` in this branch — the main-repo mismatch is being handled separately (see "Not your problem" below).

### R2 — Scope the composition-sensitive postcondition check *(plan-originated defect)*

`src/claude_monkey/builder_v15.py:548–564`. `shared_anchors` flattens every module's shared insertion points into ONE `set[str]` and then substring-matches it against EVERY selected package's postconditions, ignoring `PlannedModuleOperation.module_path` and `AssertionV2.module_path` — both of which carry the data needed to scope it. Confirmed failure mode: as soon as builds have multiple modules or more packages (the footer-drawers stack is the named near-term case), a legitimate build hard-fails with `postcondition_composition_sensitive` because an unrelated postcondition happens to contain a short shared-anchor substring (e.g. `}`) from a different module. False-positive fail-closed — safe, but it will burn debugging time precisely in the composition scenarios this engine exists for.

**Fix shape:**
1. Scope per module: only compare an assertion against shared anchors of the module named by `assertion.module_path` (binary assertions: compare against all modules' shared anchors — they genuinely span).
2. Preferably expose the grouping from `module_patch` (e.g. a `shared_insertion_points(planned) -> dict[int, list[PlannedModuleOperation]]` helper used by both `check_planned_conflicts` and the builder) instead of re-deriving it — this also resolves the duplicated-grouping cleanup (C2 below) at the root.
3. Add a test: two modules (fixtures_bun has `MODULE_0` and `MODULE_1`), shared insertion point in module 0, an unrelated package postcondition on module 1 whose value contains the anchor text → build must PASS.

### R3 — Pin `expectedStartMarkerCount`/`expectedEndMarkerCount` to 1 for context-bearing op types *(plan-originated gap; CONFIRMED with repro)*

`src/claude_monkey/manifest_v2.py` `_validate_operation_shape` pins `expectedAnchorCount`/`expectedSubExactCount` to 1 but not the marker counts. Verified mechanically: an `insert_after` with `expectedStartMarkerCount: 2` on a module with two marker occurrences passes validation, then `_resolve_context` count-checks 2==2 and silently resolves the FIRST occurrence — the op can anchor in the wrong context block with zero error. (Inherited `replace_between` semantics — but the new types should not repeat it.) A scan of every shipping `packages/*/patch.json` found zero ops declaring marker counts ≠ 1, so pinning is non-breaking.

**Fix shape:** in `_validate_operation_shape`, for `insert_before`/`insert_after`-with-markers and `replace_substring_within`, require both expected marker counts == 1 with the same "(other values unsupported)" error style. Leave `replace_between` untouched in this branch (behavior-freeze constraint); flag it for a follow-up. Add parse tests for both rejected cases.

### R4 — Fail closed on duplicate `manifest.id` across selected packages *(plan-originated gap; CONFIRMED)*

`src/claude_monkey/builder_v15.py` `_select_packages` (~447–484) never enforces id uniqueness, and the legacy `patch.json` path has NO id-vs-folder check anywhere (`load_manifest_v2_dict` doesn't know the folder; `id_must_match_folder` exists only on the v3 envelope path). `cli.py`'s `_enabled_package_dirs` (~874) does no dedup. Consequences: `enabled_ids` set-collapse can mask `requiresPackages`/`conflictsWithPackages` checks, and `insertion_evidence` keyed `(packageId, opId)` silently overwrites across two same-id packages with non-overlapping ops and reused opId strings — misattributed `finalOffset`/`insertionVerified` in a report whose whole point is per-op evidence. Realistic path: a forked/copy-pasted package whose author changed anchors but not the id.

**Fix shape:** in `_select_packages`, track `seen_ids: set[str]`; on repeat, `_write_failed(..., f"duplicate_package_id:{manifest.id}:{package_dir.name}", ...)` before appending. One builder test: same fixture package under two dir names → build fails with that code.

---

## Recommended cleanups (do in this branch; all small)

- **C1 — Delete the `_check_overlaps` shim** (`builder_v15.py:353–357`). `ModulePatchError` subclasses `ValueError` (module_patch.py:9), so the try/except translation is a literal no-op; the outer handler stringifies either identically. Call `check_planned_conflicts(planned)` directly. *(Plan-originated.)*
- **C2 — Single source for shared-point grouping** — falls out of R2's fix shape. *(Plan-originated.)*
- **C3 — Derive `kind` from `op_type`** instead of storing parallel state on `PlannedModuleOperation` (or centralize the mapping in one function used by all three `_resolve_operation` return sites). All conflict logic keys off `kind`; a future op type that sets one but not the other silently skips validation branches. *(Plan-originated design choice — improve it.)*
- **C4 — Drop the `_render_order` alias** (module_patch.py) — one-line wrapper around the public `planned_operation_render_order`; use the public name at all four sort sites. *(Implementer artifact, trivial.)*
- **C5 — Reuse `optional_string_list`** for the pre-existing inline `requireWithinRange` check in `parse_operation` — same file, same logic, added 60 lines apart.
- **C6 — Reject non-default `expectedAnchorCount`/`expectedSubExactCount` on legacy op types** in `_validate_operation_shape`'s else-branch (currently a typo like `"expectedAnchorCount": 2` on `replace_exact` parses silently and is ignored).
- **C7 (optional) — Consolidate test helpers**: `write_insertion_package`/`write_package`/`write_fixture_package` are three near-identical manifest writers, and `runner`/`successful_runner` are byte-identical — a shared helper in `tests/fixtures_bun.py` or `conftest.py` would do. *(The plan itself authored these duplicates; your call whether to fold now or leave.)*

## Nice-to-have (benchmarked; not urgent)

- **N1 — Bounded marker scans in `_resolve_context`**: the `tail = module[start+len:]` slice copies up to ~18.6MB, and `_count` + `find` double-scan the module per marker. Measured cost: ~2–4ms per 10-op build vs ~7ms for one sha256 pass — real, marginal. **Trap in the obvious fix:** `bytes.count(needle, start)` counts NON-overlapping matches while the hand-rolled `_count` counts OVERLAPPING ones (`b"aa"` in `b"aaaa"`: 3 vs 2) — a silent semantic change to expected-count validation. Safe fix: add a `start` parameter to `_count` (loop from `pos=start`) and drop the slice. Doing this also naturally de-duplicates `_resolve_context` vs the `replace_between` branch (see "Deliberately NOT changed" below before touching that).

## Deliberately NOT changed — do not "fix" these

- **`replace_between` branch duplicating `_resolve_context` logic**: the plan explicitly froze the legacy branch verbatim to guarantee byte-identical behavior (verified against main). Factor a shared locator only in a follow-up with the legacy behavior locked by tests, not in this branch.
- **Subspan ops' context markers not conflict-checked** (`evidence_spans` empty for `subspan_replacement`): per the amended spec, evidence disjointness applies to insertions only — your implementation is spec-compliant. The review surfaced a real scenario (another package `replace_exact`s a subspan op's marker text elsewhere, silently invalidating the disambiguation the markers provided) — this is now an **open spec question** for the spec owner, not something to implement unilaterally.
- **Double conflict-checking** (per-package inside `plan_module_operations` + cross-package builder pre-pass): intentional layering — the inner call guards single-package authoring, the outer guards composition. Microseconds at real op counts. Leave it.

## Not your problem (main-repo issues surfaced by this review)

- Main is red on clean checkouts: `tests/test_reference_packages.py` hard-lists `packages/hotrod-dragons`, which was never committed to main. Being resolved on main separately — either committing the WIP package properly or guarding the test. Don't touch it from this branch.

## Verification recipe (run before returning the branch)

```bash
cd /Users/MAC/.config/superpowers/worktrees/Claude-patch/composition-engine-structured-splices
uv run --with pytest python -m pytest tests/ -q --ignore=tests/test_dvd_cursor_goblin.py
# expect: all green EXCEPT tests/test_reference_packages.py hotrod-dragons cases
# (pre-existing main breakage, becomes visible again after the R1 revert — note it, don't fix it)
```

Plus new tests required by R2 (two-module false-positive case), R3 (two parse rejections), R4 (duplicate-id build failure).

---

*Process note, for calibration rather than criticism: the implementation itself was faithful and careful — commit `a77d963`'s self-review hardening pass and the `contextSha256`-requires-markers catch were both genuinely good. The one process miss was R1: when a pre-existing red test blocks you and the plan says its cause is out of scope, surface the blocker in your report instead of importing content to silence it.*
