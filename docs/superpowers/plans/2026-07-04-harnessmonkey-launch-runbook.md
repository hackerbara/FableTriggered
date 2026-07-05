# HarnessMonkey Launch Runbook

**Date:** 2026-07-04
**Status:** approved design, execution in progress
**Goal:** Ship this project publicly as **harnessmonkey** (one word, everywhere) — a fresh repo at `github.com/hackerbara/harnessmonkey`, single clean commit, 9 packages locked to the latest Claude Code version, on the unified package-model schema. This repo (`Claude-patch` / FableTriggered) stays as the private historical dev archive; the cutover happens by copying into a clean new folder at the rename step.

## Locked decisions

| Decision | Value |
|---|---|
| Project name | `harnessmonkey` — dist name, Python import, CLI command, `~/.harnessmonkey` state dir, "HarnessMonkey" display form |
| Install story | clone + `uv sync` + `uv run harnessmonkey …` (source-first). PyPI holds a name-claim stub only (`0.0.1`), no release discipline for v1 |
| Manifest schema | Package-model format (`package_model.py`), `schemaVersion: 1`, `kind` **required**. This is "v1" of the public format. Flat-v2 files and the legacy loader never existed publicly |
| Repo contents | Ship everything real: `src/`, `packages/` (final 9), `examples/` (art generators), `tests/`, `assets/` (**filtered** — see 2.1), `HarnessMonkey-README.md` **ships as `README.md`**, `pyproject.toml`, `uv.lock`, `.gitignore`, `LICENSE`. Exclude dev process: `docs/superpowers/`, `.claude/`, `CLAUDEMONKEY.md`, old `README.md` (FableTriggered), `.development/`, egg-info, root patch-instruction notes (`claude-fable-fallback-patch.md`, `claude-reminder-suppression-patch.md`), and `assets/fabletriggered-screenshot.jpeg` (**leaks an unrelated private project's `/resume` screen — must not ship**) |
| Cutover mechanism | Clean new folder; copy ship-set in; rename there; `git init`; single commit; push to new repo |

### Final package set and names (signed off)

| Ships as | Was | Notes |
|---|---|---|
| `capybara-onsen` | (same) | art patch; generator ships in `examples/` |
| `heraldic-dragons` | `hotrod-dragons` | art patch; generator ships in `examples/` |
| `fable-fallback` | (same) | the origin story |
| `hidden-context-drawer` | (same) | depends on drawer-dock |
| `hidden-context-inline` | `normal-channel-hidden-context` | conflicts with hidden-context-drawer |
| `reminders-drawer` | `reminders-manager` | depends on drawer-dock; conflicts with mute-reminders |
| `mute-reminders` | `upstream-attachment-suppression` | static suppression of the 7 attachment families |
| `thinking-drawer` | `thinking-text-drawer` | depends on drawer-dock |
| `drawer-dock` | `footer-drawers` | shared drawer framework (lands via G1) |

**Cut (never ship):** `dvd-cursor-goblin`, `dvd-cursor-real-art-spike`, `dvd-cursor-terminal-art-spike` (+ their 3 test files), `reminder-suppression` (superseded 2.1.198 predecessor of mute-reminders).

## Gates (in flight, user-driven)

- [x] **G1 — footer-drawers lands.** ✅ Merged 2026-07-04 as `70c467d` (user landed it with port fix `fde46cc`). Note: it merged mid-flight against agent 1.6's working-tree edits — conflict resolution on the two drawer test files handled under 1.6.
- [x] **G2 — GUI rework lands.** ✅ User merged it directly 2026-07-04 (`a982f08`, + dialog fix `da9f7b3`, dedup refactor `5f2effc`). PySide6 GUI, menubar.py retired, script repointed. *(Original rebase notes below kept for the record.)* `codex/claude-monkey-v3-gui` (canonical; `-sr1`/`-t16`/`-t17` are confirmed strict-subset earlier iterations). 41 commits behind main → **must rebase onto main after G1**, then land. Its `packages/` copies are stale — take main's/G1's for every package. **The branch is a full menubar replacement, not an addition** — its deletions and pyproject changes are intentional and must survive the rebase: deletes `src/claude_monkey/menubar.py` (rumps retired), repoints the menubar console script to `claude_monkey.gui.app:main`, swaps the `gui` extra from `rumps` to `PySide6>=6.7` (+ `pytest-qt`, `Pillow` dev deps), deletes `assets/claude-monkey-menubar-template.png`, adds `monkey-color-*.png` / `monkey-tray-*.png` assets (these ship).
- [x] **G3 — demo recorder tool ready.** ✅ Merged 2026-07-04 (`5b015d0`): `record_demo.py` + `run_demo_matrix.py` + configs under `.development/demo-recorder/` (local tooling, stays out of the ship set by design).

## Phase 1 — Content & cuts (after G1 + G2; old repo; system stays green after each step)

> **Implementation plans exist for the meat of this phase:** tasks 1.2/1.3b/1.4/1.5 → `docs/superpowers/plans/2026-07-04-schema-unification-and-repin.md` (also absorbs the current schema/build-semantics test failures as its Task 0); task 1.7a → `docs/superpowers/plans/2026-07-04-install-uninstall-command.md`.

- [ ] 1.1 Delete the 4 cut packages + `tests/test_dvd_cursor_*.py`, **and in the same change** remove `reminder-suppression` from `tests/test_reference_packages.py` `PACKAGE_DIRS` (it hardcodes the cut package's path — the suite fails otherwise); run full test suite.
- [ ] 1.2 Delete the dead legacy loader path (`src/claude_monkey/manifest.py`, `builder.py`, and their orphaned helpers/tests — verify unreachable from `cli.py` first; survey says only tests import them).
- [x] 1.3 Create `examples/` with curated generators: `.development/capy-onsen-20260703/` and `.development/highdef-v11-20260702/` pipelines (paint/sim/compile/generate_package + a short README each). ✅ Done, commit `7ff5781`.
- [ ] 1.3b **Generator parity (user decision 2026-07-04, supersedes the earlier "examples only, may not match" stance):** the example generators must regenerate the live packages exactly. They're currently two generations stale — the responsive-frame (`78f2b2c`) and gutter/breakpoint (`3364d04`) work was applied directly to package payloads (incl. `-2-1-199.js` → `-2-1-201.js` payload renames) without updating the generators, which still emit the old fullscreen 2.1.199 scene. Fix during 1.5: port the responsive payload structure into both `generate_package.py` scripts, regenerate the packages *through* them at the new pin, and add a parity test (generator output ≡ `packages/` content, run as part of the suite). Also rewrite the "output may not byte-match" language in both example READMEs.
- [ ] 1.4 **Schema unification:** make package-model the only public format — `kind` required; remove the `schemaVersion:1`-without-`kind` compat dispatch (`builder_v15.py:103-105`); fix the lossy v3→internal conversion (hardcoded `packageVersion "0.0.0"`, `builder_v15.py:85`); migrate all 9 manifests; extend `tests/test_reference_packages.py` to cover all 9 (it currently checks a stale list of 5).
- [ ] 1.5 **Re-pin all 9 packages to the latest Claude Code binary** — determine latest at execution time (do not assume 2.1.201); re-verify each patch against it; fix `normal-channel-hidden-context`'s dual-pin (2.1.198 + 2.1.199 in one manifest). This is per-package verification work, potentially re-authoring ops that no longer anchor. **For `capybara-onsen` and `hotrod-dragons`, the re-pin goes THROUGH the updated generators (1.3b)** — never hand-edit those payloads again; regenerate them.
- [x] 1.6 Parameterize `/Users/MAC` paths in test files. ✅ Done, commit `52f0f8b` (helper `tests/claude_binary.py`).
- [x] 1.7a ✅ **Done** — merged `b8e17c8` (verified by review agent: all constraints pass, +10 tests, zero regressions; review doc on the branch). NOTE: its temporary `schemaVersion: 2` acceptance in `package_model.py` must be removed by the schema branch (plan Task 2 Step 3b). **`install` / `uninstall` commands (user decision 2026-07-04 — the install story leads with the GUI/menubar manager):** `harnessmonkey install` = create state dir, copy every repo package into `~/.harnessmonkey/patches/` (disabled, via the existing `add_package` validation path, per-package report), write + `launchctl` load a LaunchAgent (`com.hackerbara.harnessmonkey.plist` → the venv's `harnessmonkey-gui`) so the manager appears now and returns at login, print next steps ("click the menubar icon → Install to set up your shim"). `--cli` variant skips the LaunchAgent (state dir + packages only). `harnessmonkey uninstall` unloads + removes the plist (leaves state dir and shim; `uninstall-shim` handles that). **GUI deps (PySide6/pyobjc) move from `--extra gui` to default dependencies** so plain `uv sync` suffices. Shim install remains an in-GUI step. CLI tests included. Resolution stays state-dir-only (`test_no_repo_package_source_v3.py` guards this deliberately — install copies; the repo never becomes a live source).
- [ ] 1.7 **Package doc scrub:** rewrite the "Build pipeline" sections in `capybara-onsen`, `hotrod-dragons`, `hidden-context-drawer`, `reminders-manager` READMEs — they currently give `cd /Users/MAC/Documents/Claude-patch` + `.development/` rebuild commands that are dead in the public repo; point them at `examples/` instead. Remove cut-package cross-references from surviving docs: the "Why this supersedes reminder-suppression" section in `upstream-attachment-suppression/README.md:44-46`, the compat mention in `hidden-context-drawer/README.md:22`, and the `reminder-suppression` fixture strings in `tests/test_config_v3.py:28,41`.

## Phase 2 — Cutover & rename (new clean folder)

- [ ] 2.1 Create the clean folder (e.g. `~/Documents/harnessmonkey`); copy ship-set per the repo-contents table. Explicit copy manifest, reviewed before proceeding.
- [ ] 2.2 Project rename in the new tree — **grep-driven, not file-list-driven**: the old name appears in 20+ ship-set files beyond the obvious ones. Anchor points: `pyproject.toml` (`name = "harnessmonkey"`, scripts `harnessmonkey` / `harnessmonkey-gui` — the old script name says "menubar" but post-G2 it launches a Qt app; veto if `-menubar` preferred); `src/claude_monkey/` → `src/harnessmonkey/` + all imports; `~/.claude-monkey` → `~/.harnessmonkey`; `OWNER_MARKER` in `install.py:14` **and its unlinked duplicate literal in `source_discovery.py:78`** (make the latter import the constant); the GUI package's own branding (`settings_window.py` window title, `tray.py` label, `gui/app.py` single-instance key, already-running message, state-dir literals, and the **`python -m claude_monkey` subprocess invocation that hard-breaks post-rename**, `window_model.py` state-dir literals); **~18 test files that assert on the literal strings** (`test_cli.py:21`, `test_authorization.py:38`, `test_cli_json_contracts.py` owner fields, etc. — the rename is done when `rg -i 'claude.?monkey'` over the new tree returns zero). Fresh `uv sync` regenerates `uv.lock` under the new name; egg-info gitignored.
- [ ] 2.3 Package renames per table: directory names, `patch.json` ids/labels, payload refs, `requiresPackages`/`conflictsWithPackages` cross-refs, per-package test files and READMEs.
- [ ] 2.4 Full test suite green in the new tree; `uv run harnessmonkey doctor` works.
- [ ] 2.5 Add MIT `LICENSE` (copyright holder: hackerbara) and a `license` field in `pyproject.toml`.

## Phase 3 — README & demos (after Phase 2 + G3)

- [x] 3.1 Finalize README text. ✅ Done 2026-07-04: install section is GUI-led (clone → `uv sync` → `harnessmonkey install`, per 1.7a), lessanxious link, doctor/rollback/use-official troubleshooting. All text TKs resolved.
- [x] 3.2 Rebuild the package table. ✅ Done: 9 rows, final names, `assets/demos/<final-name>.gif` per row.
- [ ] 3.3 Record demos with the G3 recorder: 9 package GIFs + header GIF (`capyclaude.gif`); copy reviewed output into `assets/demos/`; verify every README image resolves.
- [ ] 3.4 Sweep for remaining TKs; anything Claude can't fill gets flagged to the user explicitly.

## Phase 4 — Publish

- [ ] 4.1 PyPI: **stubs built and ready** at `.development/pypi-stub/{harnessmonkey,harness-monkey}/dist/` (0.0.1, MIT, pointing at the GitHub repo). User has the account; publish with an API token: `cd .development/pypi-stub/harnessmonkey && uv publish --token <pypi-token>` (repeat in `harness-monkey/` for the pointer claim). Names verified free on PyPI 2026-07-04.
- [ ] 4.2 Final hygiene sweep in the new tree: zero `/Users/MAC` hits, zero secrets/emails, no dev-doc leakage, `.gitignore` correct, LICENSE present (see open questions).
- [ ] 4.2a **PII scan (hard gate):** mechanical case-insensitive scan of the entire fresh repo (tracked files *and* full new git history) for `alex` and `bernson` — zero hits required before push. These stay strictly in the local historical repo. Include word-boundary-free match (catches emails/handles); manually review any hit before deciding it's a false positive. Known false positive as of 2026-07-04: the minified identifier `apiRefusalExplanation` (contains "alEx") in `packages/fable-fallback/payloads/gcm-assistant-case.js` — scanned today, zero true hits in the ship set, zero `bernson` hits anywhere. **Text scan cannot inspect images** — additionally eyeball every shipped image (`assets/`, `packages/*/preview.png`, all GIFs) for leaked screen content before push; this is how the `fabletriggered-screenshot.jpeg` leak was caught.
- [ ] 4.3 ~~User creates `github.com/hackerbara/harnessmonkey`~~ ✅ repo created 2026-07-04. Remaining: `git init` in the clean folder, single commit, push.
- [ ] 4.4 **Proof:** fresh clone in a temp dir → full install journey (`uv sync` → `doctor` → enable a patch → `build --activate` → `install-shim` → launch) → full test suite → README renders with all images on GitHub.

## Risks

- **Re-pin scope unknown (1.5):** if the latest Claude Code binary moved significantly past 2.1.201, some patches may need op re-authoring, not just pin bumps. Budget for it; it's the least mechanical task here.
- **GUI rebase (G2):** 94 files, 41 commits behind; the rebase is the highest-conflict moment. Do it immediately after G1, before anything else moves.
- **Copy-manifest omissions (2.1):** a clean-folder cutover fails *silently* by leaving something behind (a payload dir, a test fixture). Mitigated by 2.4 full-suite + 4.4 fresh-clone proof.
- **GIF weight:** 10 GIFs of terminal recordings can get heavy for a repo clone; review sizes at 3.3, consider palette/fps tuning before committing.

## Non-goals

- Real PyPI releases / Trusted Publishing (post-launch)
- Auto-tracking new Claude Code versions (design is fail-closed by intent; README says so honestly)
- Cross-platform support (macOS arm64 only, stated)
- Prompt/option packages in the launch set (the schema supports them; v1 ships 9 patches)

## Open questions

*(none — resolved 2026-07-04)*

1. ~~LICENSE~~ → **MIT** (user decision). Added as task 2.5.
2. ~~Header GIF~~ → **capy-onsen scene** (`capyclaude.gif`), confirmed.

## State of play — handoff for a fresh-context session

*Last updated 2026-07-04, session 1. A fresh agent should read this runbook top to bottom, then this section, then check `git log --oneline -15` and the task states below before doing anything.*

**Done:**
- All design decisions locked (tables above are signed off by the user — do not re-litigate names, schema, or repo contents).
- Adversarial review folded in (commit `0331f76`); the G2 gate description, 2.2 rename scope, and PII gate reflect its findings.
- PyPI stubs built (see 4.1) — awaiting user's API token to publish. Names verified free.
- PII scan baseline: zero true `alex`/`bernson` hits in ship set (known false positive documented in 4.2a).

**In flight (2026-07-04):**
- ~~1.3 examples/ curation~~ **done** — commit `7ff5781`. NOTE: generators are stale vs live packages — see 1.3b (parity required, user decision).
- ~~1.6 test-path parameterization~~ **done** — commit `52f0f8b`; merge collision with G1 resolved (migrated content canonical, parameterization re-applied); helper `tests/claude_binary.py` with `CLAUDE_MONKEY_CLAUDE_BIN` / `CLAUDE_MONKEY_CLAUDE_VERSIONS_DIR` env overrides; covers the two new footer-drawers test files too. Only remaining `/Users/MAC` in tests: the 3 dvd files (cut in 1.1).
- **pytest invocation fix** — commit `13e4110`: bare `pytest` never worked (`from tests.X` needed `python -m` cwd semantics); added `pythonpath = ["."]` ini. Public users run the bare form.
- ~~G1 regression repair~~ **done** — commit `a6c28e7`: all 7 `test_reference_packages.py` failures retargeted to the migrated footer-drawers payload structure, guard-intent preserved (mojibake, scroll-step, flash, open/close wiring all re-anchored to their new payload homes). **Suite state: 456 passed, 2 skipped, 1 failed** — the single failure is `test_dvd_cursor_goblin.py` (pre-existing, package cut in 1.1). This is the expected-green baseline until 1.1 runs.
- G3 (demo recorder) — **user's own in-flight work.**

**G2 landed** — user merged the GUI branch directly (`a982f08`). Both gates that blocked Phase 1 are now clear.

**README status:** `HarnessMonkey-README.md` is committed and canonical (user cleanup snapshot + TK fill). All text TKs are resolved — install journey (verified against the real CLI: `enable-patch` is one package per call; codesign is stock, no Xcode), lessanxious-claude link, doctor/rollback/use-official troubleshooting, final 9-row package table. Doc is written **future-state** (harnessmonkey names, public clone URL) — the Phase 2 rename makes code match doc; 2.2's zero-grep done-condition must therefore EXCLUDE this file's intentional forward references (it contains no old names, so this is automatic). Remaining README gap: demo GIFs only (blocked on G3). Old `README.md` (FableTriggered) stays archive-only.

**Dogfood round (2026-07-04 night):** user ran the real install + build flow end-to-end. Result: core works — install, shim (stable across repeated rebuilds/failures), responsive capy scene, drawer bar rendering, live patch swapping. Findings, all root-caused:
1. ~~install skipped stale state-dir packages~~ **fixed** `d10d25d` (add_package overwrite semantics, atomic swap, installed/updated/unchanged report).
2. ~~LaunchAgent launch failures were invisible~~ **fixed** `a5e2148` (plist Standard{Out,Error}Path → `~/.claude-monkey/logs/menubar.launchd.log`, printed by install). ROOT CAUSE OF ORIGINAL NO-LAUNCH STILL UNDIAGNOSED — user to re-run uninstall/install and read the log. **Pre-ship gate: README's "monkey lands in your menubar" claim must be verified true, or install falls back to printing an explicit launch command.**
3. ~~stale config officialClaudePath silently outranked the fresher install record~~ **fixed** (doctor divergence warning, commit "doctor warns when config officialClaudePath diverges").
4. ~~drawer patches didn't auto-select their footer-drawers dependency~~ **fixed** `f7bc31f` (requires-closure auto-enable both surfaces; disable blocked with dependents named).
5. **OPEN — capybara-onsen breaks Enter-to-open on all drawers** when composed together (bars render; Enter dead; drawers-without-capy fine; 2.1.199-era capy coexisted fine). Debug agent in flight: root cause → fix through the emitter → extend composition matrix test to cover capy. **Blocks GIF recording** (header shot is capy+drawers).

**GIF decisions (user):** mute-reminders gets NO gif (blank cell — no visible UI); drawer-dock's gif = ensemble shot (all three drawers on the dock); individual drawers get individual gifs. 9 GIFs total. Codex runs the recording session from a user-pasted prompt once the capy fix lands.

**Late-day status (2026-07-04 evening):** All three gates closed (G1 `70c467d`, G2 `a982f08`, G3 `5b015d0`). Install/uninstall merged (`b8e17c8`, verified). GitHub repo `hackerbara/harnessmonkey` exists (empty). Main suite: 15 failed / 905 passed / 2 skipped — all 14 tracked failures are owned by the schema branch's Task 0; +1 untracked dvd-goblin test (dies at 1.1).

**In flight:** `codex/schema-unification-and-repin` worktree is ready-for-merge pending review — a review agent is verifying it against the plan and writing the install-merge handoff (v2-scaffolding removal per Task 2 Step 3b, rebase over `b8e17c8`, install regression check) into `docs/superpowers/reviews/2026-07-04-schema-unification-review.md` on that branch.

**Remaining before publish, in order:**
1. Schema branch: review lands → user's agent addresses findings → merge. Expected post-merge suite: 1 failed (dvd-goblin only).
2. 1.1 cuts (4 packages + tests + the goblin failure dies) and 1.7 doc scrub — small, agent-dispatchable immediately after schema merges.
3. Phase 2 cutover: clean folder + copy manifest (2.1), full rename sweep (2.2/2.3), suite green + doctor (2.4), MIT LICENSE (2.5).
4. Phase 3: record 10 GIFs via `.development/demo-recorder/` (9 packages + capy header), install into `assets/demos/`, verify README images (3.3), final TK sweep (3.4).
5. Phase 4: PyPI publish (stubs ready — needs user's token, 4.1); hygiene + PII gates incl. image eyeball (4.2/4.2a); `git init` + single commit + push to the created repo (4.3); fresh-clone end-to-end proof (4.4).

**User-only items left:** PyPI API token; merging their own schema branch; final say on the cutover copy manifest before push.

## Research appendix

Findings from three survey agents, 2026-07-04 (full reports in session transcript): package inventory & generator locations; launch-script/entry-point map, version-pin census (2.1.198–2.1.201 spread), schema-family analysis (`manifest.py` legacy / `manifest_v2.py` / `package_model.py`, dispatch at `builder_v15.py:92-107`); worktree audit — 12 worktrees, GUI-branch canonicality (`v3-gui` ⊃ `sr1`/`t16`/`t17`), footer-drawers = clean FF at `3364d04`, main canonical for all packages except the drawer family, `/Users/MAC` footprint (551 hits, ~500 in dev docs), no secrets/emails found.
