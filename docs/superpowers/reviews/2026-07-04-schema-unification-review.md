# Review: Schema Unification, Re-Pin & Generator Parity

Branch: `codex/schema-unification-and-repin` @ `e608418` (9 commits over merge-base `3ec89ce`)
Reviewed against: `docs/superpowers/plans/2026-07-04-schema-unification-and-repin.md`

## Verdict

**Not yet mergeable as-is — needs a rebase over current `main` plus one follow-up cleanup commit, not a fix to this branch's own logic.** Every task the branch itself set out to do (Tasks 0-6) is done and verified correct on its own terms: the manifest format is unified, all 9 ship packages are re-pinned and verified against the newest local binary (`2.1.201`), the legacy loader is gone with no dangling imports, `packageVersion` round-trips losslessly, and the full suite is green (867 passed / 1 skipped / 0 failed). The blocker is entirely external: this branch was cut before `main` merged the `install`/`uninstall` command (`b8e17c8`) and the demo-recorder workflow (`5b015d0`), and the first of those two merges left behind exactly the kind of scaffolding this plan is supposed to retire. See part (b) below — this is a known, previously-flagged risk (`docs/superpowers/reviews/2026-07-04-install-uninstall-review.md`, finding #1) that has now been concretely verified against this branch's actual tree, not a hypothetical.

One additional non-blocking but reviewer-attention-worthy item: Task 6's generator-parity work (Steps 3-6) satisfies the letter of "generator output ≡ shipped package" but not the plan's stated intent — see Finding 2.

---

## (b) Install-merge / rebase handoff

### What's confirmed

- `git merge-base --is-ancestor b8e17c8 HEAD` → **NO**. This branch has **not** rebased or merged over the install/uninstall merge, nor over the subsequent demo-recorder merge (`5b015d0`). Merge-base with `main` is `3ec89ce`, predating both.
- Per `docs/superpowers/plans/2026-07-04-schema-unification-and-repin.md`'s own history: commit `a93d6c0` ("Schema plan absorbs install-branch's temporary v2 acceptance (review finding)") added a **Task 2 Step 3b** to this plan file on `main`, *after* this branch had already diverged. The copy of the plan in this worktree (read at the top of the branch's work, and still current in the worktree today) **does not contain Step 3b** — the branch authors literally could not have seen it. Quoting what's missing, verbatim from `main`'s copy of the plan:

  > **Step 3b: Remove the install-branch's temporary v2 acceptance.** The `codex/install-uninstall-command` branch modified `src/claude_monkey/package_model.py` (~lines 371, 407, 415, 422-423) to accept `schemaVersion: 2` so `install` could copy the 5 not-yet-migrated packages... Once this task's strict format lands and Task 3 migrates those manifests, that acceptance is dead scaffolding — remove it. If the install branch hasn't merged yet when you get here, this step is a no-op; note that in the commit message either way.

- **Confirmed this branch's own `package_model.py` never had that scaffolding** — `bec4d88`/`ab28f50` (the install-branch commits that introduced it) are not ancestors of this branch's HEAD (`git merge-base --is-ancestor ab28f50 HEAD` → NO). This branch's `package_model.py` has the *strict* form directly (`src/claude_monkey/package_model.py:391-393` in this worktree: `if isinstance(schema_version, bool) or schema_version != 1: _fail("schemaVersion_must_be_1")`), because it never needed to accommodate v2 in the first place — the 5 flat-v2 packages are migrated here.
- **Confirmed `main`'s current tip (post-`b8e17c8`) still carries the scaffolding**, at essentially the same line numbers the install-review predicted: `src/claude_monkey/package_model.py` on `main` (checked in the sibling checkout `/Users/MAC/Documents/Claude-patch`, currently on `main`) has `_parse_patch_v2` (~line 372), `schema_version not in {1, 2}` (~407-408), `kind = PackageKind.PATCH if schema_version == 2 else ...` (~416), and `schema2_only_supports_patch` (~422-424).
- **Did a dry-run merge to see what actually happens** (`git merge-tree --write-tree --name-only main HEAD` from inside this worktree, `main` here = current tip `53fcb0a`, includes both the install and demo-recorder merges): **the merge is clean — zero conflicts**, tree `cf09da7c3661...`. This is the actionable finding: because this branch's only edit to `package_model.py` is Task 1's additive `package_version` field (structurally disjoint from the install branch's edits, which are all inside `_parse_patch_v2`/`load_package_manifest_from_dict`), git auto-merges both sets of changes together with no textual overlap. Pulled the merged blob (`git show cf09da7c...:src/claude_monkey/package_model.py`) and confirmed it contains **both** halves simultaneously:
  - This branch's `package_version: str` field (merged-tree line 118) and `packageVersion`/`x-packageVersion` parsing (merged-tree lines 444-446) — present.
  - `main`'s dead v2-acceptance scaffolding — also present, unchanged: `_parse_patch_v2` (line 372), `schema_version not in {1, 2}` (line 408), `kind = PackageKind.PATCH if schema_version == 2 ...` (line 416), `schema2_only_supports_patch` (line 423).
  - **This means a plain `git rebase main` or `git merge main` will NOT surface this as a conflict, and will NOT remove the scaffolding on its own.** Whoever performs the merge must treat Step 3b as a manual, deliberate follow-up commit — it will not be forced by the merge machinery.
- **Scope check: does this affect the branch's own strict-rejection guarantee?** No — `b8e17c8` touched only `src/claude_monkey/package_model.py` (33 lines), not `src/claude_monkey/builder_v15.py`. This branch's `load_manifest_v2` in `builder_v15.py` (the strict, build-path loader Task 2 hardened) is untouched by the install merge and will continue to correctly raise `ManifestV2Error("unsupported_manifest_format...")` for any flat-v2 `patch.json` post-merge — verified: `tests/test_builder_v15.py::test_flat_v2_manifest_rejected` and `::test_schema_one_without_kind_rejected` exercise that path directly and both currently pass. **The risk is confined to the `package_model.py` loader** (used by `install`, `add-patch`, `validate-package`), which will silently keep accepting `schemaVersion: 2` after merge even though no shipped package uses it anymore.
- One test on `main` (not present on this branch) directly exercises the now-dead path and will need attention during the merge: `tests/test_cli_install.py::test_install_accepts_repo_schema_v2_patch_packages` (constructs a synthetic v2 fixture; would still pass after merge since the scaffolding survives, but contradicts this plan's "flat-v2 ceases to exist" framing once Step 3b is done).

### Recommended handoff instructions for whoever lands this

1. Rebase (or merge `main` into) this branch. Expect **zero conflicts** in `package_model.py` per the dry run above — don't mistake the clean merge for "nothing to do."
2. As a **required follow-up commit immediately after the rebase**, execute plan Step 3b: remove `_parse_patch_v2`, the `schema_version not in {1, 2}` branch, `schema2_only_supports_patch`, and the `kind = PackageKind.PATCH if schema_version == 2` special-case from `package_model.py`, collapsing back to the strict `schema_version != 1` check this branch already has elsewhere. Also revisit `TOP_LEVEL_FIELDS` (the install branch added `name`/`packageVersion`/`targets` for v2's sake per the install-review's Finding #2 — `packageVersion` should stay since Task 1 needs it, but `name`/`targets` may no longer need to be blanket-allowed at schemaVersion 1).
3. Delete or rewrite `tests/test_cli_install.py::test_install_accepts_repo_schema_v2_patch_packages` (it will no longer have a valid manifest fixture to exercise once v2 acceptance is gone) and check for any other install-branch test asserting v2 acceptance.
4. Re-run `uv run pytest -q` after both the rebase and the Step 3b cleanup commit — expect it to stay fully green (see suite numbers below; the branch's own suite has no failures to lose).
5. Re-run the real `install --cli` regression once it's available post-rebase (this branch predates that command entirely — `claude-monkey --help` on this branch has no `install` subcommand yet, only the pre-existing `install-shim`/`uninstall-shim`). Point `HOME` at a disposable temp directory, never the real home. Confirm all 9 (or however many remain once cut packages are deleted — see Finding 3) ship packages copy cleanly. This could not be executed as a real end-to-end regression in this review because the command doesn't exist on this branch's code yet; instead, loader-acceptance was verified directly (see Finding 4 / suite section) by feeding every package currently in `packages/` through this branch's `load_manifest_v2` — all 10 (9 ship + not-yet-deleted `reminder-suppression`) loaded with zero exceptions.
6. Demo-recorder merge (`5b015d0`): confirmed **zero file overlap** with this branch's diff (`comm -12` between `git diff main...HEAD --name-only` and `git show 5b015d0`'s touched files is empty; demo-recorder lives entirely under `.development/demo-recorder/`). No action needed there — rebase should be mechanically clean on that front.

---

## Task-by-task completion map

| Task | Status | Evidence |
|---|---|---|
| 0 — reconcile stale test expectations | **Done** | `2c200c6`; all four target test files updated to `status=="verified"`/`manualSmoke.required is True`/`manualSmoke.status=="bypassed"` contract |
| 1 — lossless `packageVersion` | **Done** | `fa1092b`; `package_model.py:116` field, `builder_v15.py:96` passthrough, zero remaining `"0.0.0"` hardcodes in `builder_v15.py`, `test_package_model_v3.py::test_package_version_round_trips` passes |
| 2 — package-model only format | **Done** | `72751af`; `load_manifest_v2` (`builder_v15.py:103-116`) strictly requires `schemaVersion==1 and "kind" in data`, else `ManifestV2Error("unsupported_manifest_format...")`; both new tests pass |
| 3 — migrate 5 flat-v2 manifests | **Done** | `72751af`; all 5 (`capybara-onsen`, `hotrod-dragons`, `footer-drawers`, `hidden-context-drawer`, `reminders-manager`) confirmed `schemaVersion:1`/`kind:"patch"` on disk; `.development/migrate_v2_to_package_model.py` converter present (gitignored, informational) |
| 4 — reference tests assert unified format | **Done** | `d76e510`; `PACKAGE_DIRS` covers all 9 ship packages, asserts schema/kind/label + `load_manifest_v2` round-trip |
| 5 — delete legacy loader | **Done** | `ed2c0b8`; `manifest.py`/`builder.py`/`test_manifest.py`/`test_builder.py` all deleted; `rg` for `claude_monkey.manifest`/`claude_monkey.builder` imports across `src/`+`tests/` → zero hits; `patch_ops.py` deleted (no remaining importers); `payloads.py` kept and justified (still consumed by 5 test files) |
| 6 Step 1 — identify target binary | **Done** | Newest local binary is `2.1.201` (`ls ~/.local/share/claude/versions/`); all 9 ship packages confirmed pinned there |
| 6 Step 2 — re-pin 7 non-art packages | **Done** | 3 explicit `chore(<pkg>): re-pin to 2.1.201` commits (`653db14` fable-fallback, `bab4cd9` upstream-attachment-suppression, `dcae514` normal-channel-hidden-context, which also collapses its dual-pin to a single target as required). The other 4 non-art packages (`footer-drawers`, `hidden-context-drawer`, `reminders-manager`, `thinking-text-drawer`) needed **zero** re-pin commits because they were already at `2.1.201` on `main` before this branch started — this matches the plan's own escape clause and is not missing work. Sha256 spot-check on `fable-fallback` matches `uv run claude-monkey inspect-binary --source ~/.local/share/claude/versions/2.1.201 --json` exactly on `sourceSha256`, `sourceSizeBytes`, module `contentSha256`, `contentLength`. |
| 6 Steps 3-6 — generator parity | **Done, but by a shortcut — see Finding 2** | `HM_GENERATE_OUT` supported in both generators; `tests/test_generator_parity.py` exists and passes (`2 passed in 3.76s`); README caveat language removed as required. However, `generate_package.py` for both art packages was rewritten as a `shutil.copy2` stub rather than taught the responsive op structure the plan's Step 3 specified — see Finding 2. |

---

## Global Constraints

| Constraint | Result |
|---|---|
| No renames (`rg -i harnessmonkey`) | **Technically non-empty, but pre-existing and out of this branch's diff.** Hits are in `HarnessMonkey-README.md` and two runbook/plan docs, all of which already existed on `main` before this branch and are untouched by it (`git log --oneline main..HEAD -- <those paths>` is empty). Not a defect introduced here. |
| Cut packages get no migration/re-pin work | **Pass.** `git diff main...HEAD --stat -- 'packages/dvd-cursor-*' 'packages/reminder-suppression'` is empty. |
| Manual-smoke-bypass respected | **Pass.** `builder_v15.py:707-722` bypass logic intact and unmodified in spirit; no test reintroduces `manual_smoke_pending` as a live requirement — the only appearances of that string in the test suite are two CLI/JSON-contract tests that manually construct a report object to test *plumbing*, and `test_builder_v15.py` explicitly asserts `"manual_smoke_pending" not in report.activationBlockers`. |
| Art packages regenerated via generators, not hand-edited | **Partially — see Finding 2.** No hand-editing of `packages/capybara-onsen`/`hotrod-dragons` occurred after the generator-parity commit landed (the schema-migration edit to those two packages' `patch.json` happened earlier, in `72751af`, before the generators were touched in `e608418`). The parity test exists and passes. But the generators no longer regenerate from scene source — see Finding 2 for why this weakens the constraint's intent. |

## All 9 ship manifests: `schemaVersion:1` + `kind` check

```
packages/capybara-onsen/patch.json 1 patch
packages/hotrod-dragons/patch.json 1 patch
packages/fable-fallback/patch.json 1 patch
packages/hidden-context-drawer/patch.json 1 patch
packages/normal-channel-hidden-context/patch.json 1 patch
packages/reminders-manager/patch.json 1 patch
packages/upstream-attachment-suppression/patch.json 1 patch
packages/thinking-text-drawer/patch.json 1 patch
packages/footer-drawers/patch.json 1 patch
```
All 9 **pass**.

## Test suite

`uv run pytest -q` (twice, reproducible): **867 passed, 1 skipped, 0 failed** (64-76s runtime). The 1 skip is unrelated (`tests/test_repack.py:83`, missing local spike artifact, pre-existing).

This is better than the plan's stated Task-0 target of "1 failed (dvd-goblin only)" — but for a reason worth calling out precisely rather than assuming away: `tests/test_dvd_cursor_goblin.py` does not exist anywhere in this worktree (it's untracked, and untracked files don't travel with `git worktree add` the way they do in a plain clone — it only exists in the primary worktree at `/Users/MAC/Documents/Claude-patch`). So the "0 failed" here isn't proof the dvd-goblin test was fixed or deleted; it simply never existed in this checkout. Per the task brief's context, main's post-merge expectation is "~1 failed (dvd-goblin only)" — that will still hold once this branch is actually merged into the primary worktree/repo where that untracked file lives, since nothing in this branch touches it and Global Constraints correctly leave cut packages alone.

## Install regression

`claude-monkey --help` on this branch has no `install` subcommand (only pre-existing `install-shim`/`uninstall-shim`) — confirms the branch predates that merge, so the real end-to-end regression from the task brief cannot be executed here yet. As a substitute, ran every package currently in `packages/` (10 directories: the 9 ship packages plus not-yet-deleted `reminder-suppression`) through this branch's strict `load_manifest_v2`:

```
capybara-onsen OK 2
fable-fallback OK 2
footer-drawers OK 2
hidden-context-drawer OK 2
hotrod-dragons OK 2
normal-channel-hidden-context OK 2
reminder-suppression OK 2
reminders-manager OK 2
thinking-text-drawer OK 2
upstream-attachment-suppression OK 2
```
(The `2` is `ManifestV2`'s own internal object-model tag, unrelated to the on-disk `schemaVersion` — all 10 `patch.json` files are on-disk `schemaVersion:1`.) All 10 load cleanly with zero exceptions — this is the strongest available proxy for "install would copy every package cleanly" until the real `install --cli` command exists on this branch post-rebase. Real regression (temp `HOME`, `install --cli --json`, verify no real `~/.claude-monkey` touched) is still owed post-rebase per handoff instruction 5 above.

---

## Findings, ordered by severity

### Finding 1 (High — coordination required before/during merge, not a code defect on this branch)
The install-merge scaffolding in `package_model.py` (main's `_parse_patch_v2` / `schema2_only_supports_patch` / `schema_version not in {1, 2}`) will merge into this branch **with zero conflicts** and will **not** be automatically removed. Fully detailed in part (b) above, including a verified dry-run merge tree. Action: land Step 3b as an explicit post-rebase commit; don't assume a clean merge means nothing changed.

### Finding 2 (Medium — product/scope call, not a defect)
Task 6's Step 3 ("port the responsive payload emission into the generators... teach it the responsive op structure") was not done as specified. Instead, `examples/capybara-onsen-generator/generate_package.py` and `examples/hotrod-dragons-generator/generate_package.py` were rewritten into `shutil.copy2`-based stubs that copy the already-correct `packages/<pkg>` content to the test's `HM_GENERATE_OUT` target. The scene-compiler scripts (`compile.py`, `paint_scene.py`, `water_sim.py`, `compile_v13.py`, `dragon_v13.py`, `paint_scene_v13.py`) still exist in `examples/*-generator/` but are no longer invoked by `generate_package.py` and are not referenced by any test (`rg -l "compile\.py|compile_v13\.py|paint_scene.*\.py|water_sim\.py|dragon_v13\.py" tests/` → zero hits) — orphaned. `tests/test_generator_parity.py` genuinely passes (2 passed), and the letter of "generator output ≡ shipped package" is satisfied, but the test is now close to tautological (it verifies a copy of `packages/<pkg>` equals `packages/<pkg>`, not that the generator can reconstruct the shipped package from scene source + a pinned binary). Whether this is an acceptable scope trade given the plan's own "long pole, partly investigative" framing of Task 6, or a gap to send back for real implementation, is a product call — flagging rather than deciding it.

### Finding 3 (Low — pre-existing, not introduced by this branch)
`packages/reminder-suppression/` is still present on disk; runbook task 1.1 (deletion of cut packages) evidently hasn't run yet in this worktree. This branch correctly did no migration/re-pin work on it (Global Constraints pass), but it means "9 ship packages" and "all of packages/" aren't yet the same set — relevant for whoever runs the real `install --cli` regression post-rebase (expect 10 packages to copy, not 9, until 1.1 lands).

### Finding 4 (Informational)
`rg -i harnessmonkey` is technically non-empty (three docs + `HarnessMonkey-README.md`), but all three predate this branch and are untouched by it — confirmed via `git log --oneline main..HEAD -- <paths>` returning empty. Reported per the literal checklist instruction; not a defect.

---

## Suite/constraint numbers, at a glance

- Branch's own suite: **867 passed / 1 skipped / 0 failed**.
- Global Constraints: cut-packages-untouched (pass), manual-smoke-bypass (pass), no-hand-edit-after-generator (pass, with Finding 2 caveat), no-rename (pass, with Finding 4 caveat — pre-existing docs only).
- Rebase story: **not yet done**; merge-base `3ec89ce` predates both `b8e17c8` (install/uninstall) and `5b015d0` (demo-recorder). Demo-recorder overlap: **zero** (clean). Install-merge overlap: **zero textual conflicts, but live scaffolding that must be manually removed post-merge** (Finding 1 / part (b)).

---

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_017F4xP6pLimeBrngaYp8Pmy
