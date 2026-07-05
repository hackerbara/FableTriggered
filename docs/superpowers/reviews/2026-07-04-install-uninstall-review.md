# Review: `install`/`uninstall` command implementation

Branch: `codex/install-uninstall-command` (4 commits: `bec4d88`, `6454147`, `65a0403`, `ab28f50`)
Reviewed against: `docs/superpowers/plans/2026-07-04-install-uninstall-command.md`, `HarnessMonkey-README.md`

## Verdict

**Mergeable, with one flag that needs a human/orchestrator decision before merge — not a code defect.** The install/uninstall functionality itself is correct, tested, idempotent, and matches the README contract. The one finding below is a cross-plan scope/sequencing conflict, not a bug in this branch's own logic.

## Findings (ordered by severity)

### 1. (Medium-High — needs coordination, not a bug) `package_model.py` gained permanent schema-v2 support, conflicting with the concurrent schema-unification plan

- `src/claude_monkey/package_model.py:371` (`_parse_patch_v2`), `:407` (`schema_version not in {1, 2}`), `:415` (`kind = PackageKind.PATCH if schema_version == 2 else ...`), `:422-423` (`schema2_only_supports_patch` / dispatch to `_parse_patch_v2`).
- Introduced in commit `ab28f50` ("feat: uninstall command"), whose own commit message admits the scope: *"Also taught package_model to accept schema-v2 repo patch manifests so install can copy every maintained package through add_package validation."*
- **Why it was needed:** five real, currently-shipped packages (`capybara-onsen`, `hotrod-dragons`, `footer-drawers`, `hidden-context-drawer`, `reminders-manager`) use `schemaVersion: 2` (flat-v2) manifests, which `package_model.py` on `main` rejects outright (`schemaVersion_must_be_1`). Without this change, `install` would report failures for 5 of 10 repo packages — verified by temporarily reverting to check: the real-home-safe smoke test (temp `HOME`) below confirms all 10 packages, including the 5 flat-v2 ones, install cleanly only because of this change.
- **Why it's a problem:** `docs/superpowers/plans/2026-07-04-schema-unification-and-repin.md` is a sibling plan, already committed to the repo (visible in `git log main`), whose explicit Global Constraint is the opposite direction: *"Public manifest format: schemaVersion: 1 with kind REQUIRED... Flat-v2 and legacy-v1 cease to exist."* That plan's job is to migrate these same 5 packages away from schemaVersion 2 and delete support for it. This branch instead makes schemaVersion 2 acceptance permanent and general — not scoped to `install`, but added to `package_model.load_package_manifest_from_dict`, the same validator used by `add-patch` (i.e., now any user-supplied package, not just repo-shipped ones, can use schema-v2). This is also **out of the install/uninstall plan's own stated scope**: Task 3/4's "Consumes" list only names `add_package`, `install_agent`, `gui_executable` — nothing about `package_model.py` or schema versions, and the plan's Global Constraints say nothing about schema handling.
- **What conformance requires:** this needs a merge-order decision, not a code fix by either branch alone:
  - If `schema-unification-and-repin` lands first (it already migrates all 5 flat-v2 packages to schemaVersion 1 and deletes legacy-loader support), then this branch's `_parse_patch_v2` path and `tests/test_cli_install.py::test_install_accepts_repo_schema_v2_patch_packages` become dead code that should be dropped during rebase/merge — install will work fine without them once packages are migrated.
  - If this branch lands first, whoever executes the schema-unification plan needs to know this file now has a second manifest-format acceptance path to remove, or their "Flat-v2... cease to exist" constraint won't actually be true after their own plan completes.
  - Either way: flag to whoever is sequencing these two plans. This is not something I should silently patch out mid-review (that's product/architecture territory, not merge verification).

### 2. (Low — minor validation-allowlist looseness, no observed impact) Global `TOP_LEVEL_FIELDS` grew fields that only apply to schema-v2

- `src/claude_monkey/package_model.py` — `name`, `packageVersion`, and `targets` were added to the module-level `TOP_LEVEL_FIELDS` allow-list (used by the `unknown_top_level_field` check for *all* schema versions, not just v2).
- Effect: a `schemaVersion: 1` manifest that stray-includes a top-level `name`, `packageVersion`, or `targets` key (which have no meaning under v1) will now silently pass validation instead of failing with `unknown_top_level_field`, because the check isn't schema-version-scoped.
- No test exercises this gap and no shipped v1 package currently has these stray fields, so it's cosmetic today — noting it since it's a side effect of finding #1's change, for whoever cleans that up.

## Global Constraints — pass/fail

| Constraint | Result |
|---|---|
| Current names only (`rg -i harnessmonkey -- src/ tests/ pyproject.toml`) | **Pass** — zero matches |
| `install` copies packages, repo never becomes a live source | **Pass** — `tests/test_no_repo_package_source_v3.py` unmodified, passes; smoke-verified packages are physically copied into `~/.claude-monkey/patches/<id>/` |
| `install` never touches `claude` binary / never calls install-shim | **Pass** — `handle_install`/`handle_uninstall` (cli.py:1479-1591) never reference `install_shim_transaction` or the `install-shim`/`uninstall-shim` dispatch branches |
| launchctl/filesystem effects injectable; tests never touch real `~/Library`/launchd | **Pass** — `launch_agent.py`'s `install_agent`/`uninstall_agent` take `home`/`runner` params; all of `tests/test_launch_agent.py` and `tests/test_cli_install.py` use `tmp_path`/monkeypatched `HOME` and never touch real paths |
| Idempotence: install twice safe, uninstall without install safe | **Pass** — verified both by unit test (`test_install_agent_is_idempotent`) and live smoke (temp `HOME`): second `install --cli` returns `ok: true` for all packages via the `package_exists` → `ok` remap in `cli.py:_install_package_result` (~line 1467); `uninstall` with no prior install/plist returns exit 0 |
| GUI deps default, `gui` extra gone, `uv sync` → `import PySide6` works | **Pass** — `pyproject.toml` diff matches the plan exactly; `uv sync && uv run python -c "import PySide6"` → `ok`. (Note: plain `uv sync` does *not* install `pytest` — that's pre-existing on `main` too, since `dev` was already a separate optional-dependency group before this branch; not a regression here.) |

## Test suite

- Clean `main` baseline (verified in an isolated temp worktree at the same merge-base `3ec89ce`, `uv sync --extra dev --extra gui`): **14 failed, 889 passed, 3 skipped**.
- This branch (`uv sync --extra dev`): **14 failed, 899 passed, 3 skipped**.
- The 14 failing tests are byte-identical by name on both sides (all in `test_footer_drawers_package.py`, `test_footer_drawers_faithful_spike_port.py`, `test_reference_packages.py`, `test_reminders_manager.py` — owned by the schema-unification plan). This branch adds exactly 10 new passing tests (`tests/test_launch_agent.py` ×4, `tests/test_cli_install.py` ×6) and touches nothing in the failing set.
- (The "15 failed" figure quoted in the task brief includes `tests/test_dvd_cursor_goblin.py`, which is an untracked file only present in the primary worktree, not in git — it doesn't exist in a clean checkout of either branch, hence 14 vs 15.)

## Smoke test

Ran for real (not just unit tests), with `HOME` overridden to a disposable temp directory — confirmed safe because `pathlib.Path.home()` honors `$HOME` on POSIX, and `paths.default_paths()` explicitly reads `os.environ.get("HOME", ...)` too, so both the state-dir path and `launch_agent`'s `home=Path.home()` calls in `cli.py:1505`/`cli.py:1552` redirect together:

- `HOME=<temp> uv run claude-monkey install --cli --json` → exit 0, all 10 real repo packages copied and reported `enabled: false` via `list-patches --json`.
- Ran `install --cli` a second time → exit 0, all packages still `ok: true` (idempotent, no duplicate-copy errors).
- `HOME=<temp> uv run claude-monkey uninstall --json` with no LaunchAgent ever installed → exit 0, `stateDirUntouched: true`, `shimUntouched: true`.
- Confirmed no plist was ever written to the temp home's `Library/LaunchAgents` (never created, since `--cli` was used) and confirmed the **real** `~/Library/LaunchAgents/com.hackerbara.claude-monkey.plist` does not exist before or after this session.
- **Skipped:** the non-`--cli` path (`launchctl bootstrap`/`bootout` against the real `gui/$(id -u)` launchd domain). Even pointed at a temp `HOME`, `launchctl bootstrap` registers with the real user's live launchd session (the plist's *location* is sandboxed but the *domain* is not) — judged not worth the residual risk given `tests/test_launch_agent.py` already exercises the exact bootstrap/bootout/idempotence sequence via injected `FakeRunner`, and the branch's own commit message (`ab28f50`) documents a prior real-machine smoke of this exact path (install → `launchctl print` shows loaded → uninstall → `launchctl print` reports missing, plist removed) which left no residue (confirmed: no plist present on this machine now).

## Summary for merge

- Commits reviewed: `bec4d88`, `6454147`, `65a0403`, `ab28f50`.
- All Global Constraints from the install/uninstall plan: pass.
- Suite: 14 failed / 899 passed / 3 skipped, vs. clean-`main` baseline 14 failed / 889 passed / 3 skipped — same failures, 10 new passing tests, zero new failures.
- Smoke: package-copy + idempotence + uninstall-without-install verified live against a temp `HOME`; LaunchAgent bootstrap/bootout path verified via unit tests + the branch's own prior documented real-machine run.
- One escalation needed before/around merge: the `package_model.py` schema-v2 support (finding #1) should be resolved with whoever is sequencing this branch against `docs/superpowers/plans/2026-07-04-schema-unification-and-repin.md` — likely by dropping it during rebase once that plan's package migrations land, since it otherwise re-opens a manifest format that plan is actively trying to close.
