# Phase-1 contract notes (for the V3 GUI plan)

Written for Task 0 of `docs/superpowers/plans/2026-07-03-claude-monkey-v3-gui.md`. Every later
task's `# ADAPT:` marker should be resolvable from this document alone, without re-opening
phase-1 source. All citations were read directly from the worktree at commit `b93da1d`
(`codex/claude-monkey-v3-gui`, "Merge ClaudeMonkey V3 package launch profile").

## Step 1: Gate command results

Run from the worktree root with the venv interpreter (system `python3` does not have the
package installed):

```bash
.venv/bin/python -m claude_monkey list-patches --json
.venv/bin/python -m claude_monkey list-prompts --json
.venv/bin/python -m claude_monkey list-options --json
.venv/bin/python -m claude_monkey status --json
```

All four exited `0` and emitted JSON. `list-options` exists (phase 1 confirmed landed — this
subcommand does not exist in v2). `status --json` contains `activeOptionIds`.

```
$ .venv/bin/python -m claude_monkey list-patches --json
{"patches": [], "schemaVersion": 1}

$ .venv/bin/python -m claude_monkey list-prompts --json
{"prompts": [], "schemaVersion": 1}

$ .venv/bin/python -m claude_monkey list-options --json
{"options": [], "schemaVersion": 1}
```

(All three are empty because this worktree has no packages installed under `~/.claude-monkey`
yet — see Q2/Q5 below for why `list-patches` returns the v3 shape here rather than falling
back to the legacy v2 shape.)

## Q1: Manifest envelope loader (used by discovery)

Module: `src/claude_monkey/package_model.py`

- **Entry point used by discovery**: `load_package_manifest(package_dir: Path, expected_kind: PackageKind) -> PackageManifest`
  — `src/claude_monkey/package_model.py:429`. Globs `package_dir/*.json`, requires exactly one
  file that parses+validates; raises `PackageValidationError` (via `_fail`) on `manifest_json_missing`,
  `multiple_valid_manifests`, or when every candidate file fails validation.
- **Called by** `discover_packages(root: Path, expected_kind: PackageKind) -> DiscoveryResult`
  — `src/claude_monkey/package_model.py:452`. Iterates `root.iterdir()` directories, calls
  `load_package_manifest` per directory, sorts successes into `DiscoveryResult.valid` and
  catches `PackageValidationError` into `DiscoveryResult.invalid` (as `InvalidPackage(package_dir, errors)`,
  dataclass at `package_model.py:123-127`). Returns `DiscoveryResult(valid=(), invalid=())` if
  `root` does not exist (`package_model.py:456-457`) — no exception on a missing root.
- **Field-level parser** (envelope → dataclass): `load_package_manifest_from_dict(data: dict[str, Any], package_dir: Path, expected_kind: PackageKind, manifest_path: Path | None = None) -> PackageManifest`
  — `src/claude_monkey/package_model.py:373`. This is what actually validates the JSON object
  (schemaVersion==1, id/folder-slug match, kind match, unknown top-level fields, then dispatches
  to `_parse_prompt`/`_parse_option`/`_parse_patch` per `kind`).
- **Exception type on invalid**: `PackageValidationError` — `src/claude_monkey/package_model.py:45-46`,
  a subclass of `ValueError` (`class PackageValidationError(ValueError): pass`). Raised by the
  internal `_fail(message: str) -> None` helper (`package_model.py:141-142`); message strings are
  short codes like `"schemaVersion_must_be_1"`, `"id_must_match_folder"`, `"forbidden_prompt_flag"`,
  `"patch_engine_unsupported"`, etc. — treat these as a stable-ish error-code vocabulary, not
  free text (see `cli.py:535-556` `_strip_manifest_file_prefix`/`_invalid_package_errors`, which
  post-process these codes for display).
- **Package kind enum**: `PackageKind(StrEnum)` with values `PATCH = "patch"`, `PROMPT = "prompt"`,
  `OPTION = "option"` — `src/claude_monkey/package_model.py:39-42`.
- **Manifest dataclass returned**: `PackageManifest` — `src/claude_monkey/package_model.py:106-120`,
  frozen dataclass with fields `schema_version, kind, id, label, description, package_dir,
  manifest_path, risk, compatibility, prompt, option, patch, raw`.

## Q2: Per-kind package roots under `~/.claude-monkey`

- **Base state dir**: `default_paths() -> StatePaths` — `src/claude_monkey/paths.py:48-50`.
  Returns `StatePaths(state_dir=home / ".claude-monkey")` where `home` comes from
  `$HOME` env var (falls back to `Path.home()`).
- **Per-kind roots (properties on `StatePaths`)** — `src/claude_monkey/paths.py`:
  - `patches_dir` → `state_dir / "patches"` (`paths.py:24-26`)
  - `prompts_dir` → `state_dir / "prompts"` (`paths.py:28-30`)
  - `options_dir` → `state_dir / "options"` (`paths.py:32-34`)
  - (also present but not package roots: `config_path` = `state_dir/"config.json"` at
    `paths.py:12-14`; `current_path` = `state_dir/"current"` at `paths.py:16-18`; `bin_dir`,
    `logs_dir`, `versions_dir`, `patchset_dir(...)`.)
- **The function GUI code should call to go from `PackageKind` → root path**:
  `_kind_root(paths: StatePaths, kind: PackageKind) -> Path` — `src/claude_monkey/cli.py:505-510`.
  Dispatches `PATCH → paths.patches_dir`, `PROMPT → paths.prompts_dir`, else `paths.options_dir`.
  This is a private (underscore) helper in `cli.py`, not currently exported from a public module —
  GUI code will need to either import it directly (`from claude_monkey.cli import _kind_root`) or
  re-derive it from the three `StatePaths` properties above.
- **Caution — do not confuse with a second, narrower helper**: `_package_roots(paths: StatePaths) -> list[Path]`
  — `src/claude_monkey/cli.py:859-860` — returns only `[paths.patches_dir]`. This is a legacy,
  patch-only resolver used by `_resolve_package` (`cli.py:863`), `_enabled_package_dirs`
  (`cli.py:874`), `_list_patch_payload` (`cli.py:441`, legacy v2 patch listing), and the build-time
  digest helpers `_manifest_digests_for_build`/`_patch_ids_for_build_snapshot` (`cli.py:912`, `923`).
  It has nothing to do with prompts/options and predates `_kind_root`.

## Q3: Active profile read/write (`config.json`)

Module: `src/claude_monkey/config.py`

- **Config schema**: `ClaudeMonkeyConfig` dataclass — `src/claude_monkey/config.py:15-22`:
  `activeProfile: str`, `profiles: dict[str, LaunchProfile]`, `schemaVersion: int = 1`,
  `installMode: str = "shim"`, `activePatchSet: str | None = None`,
  `officialClaudePath: str | None = None`.
- **Profile schema**: `LaunchProfile` dataclass — `src/claude_monkey/config.py:8-12`:
  `prompt: str | None = None`, `patches: list[str] = []`, `options: list[str] = []`.
- **IMPORTANT constraint**: only a single profile named `"default"` is currently supported.
  `load_config` raises `ValueError("only_default_profile_supported")` if
  `set(profiles.keys()) != {"default"}`, and `ValueError("active_profile_must_be_default")` if
  `activeProfile != "default"` — `src/claude_monkey/config.py:44-47`. The "profile" concept exists
  in the schema/status payload but is not yet multi-profile in phase 1; GUI should not build a
  profile switcher against this yet.
- **Read from disk**: `load_config(path: Path) -> ClaudeMonkeyConfig` — `src/claude_monkey/config.py:39-55`.
  Returns `default_config()` (`config.py:25-28`, single `"default"` profile, empty lists) if
  `path` does not exist; otherwise parses JSON and raises the `ValueError`s above on an invalid
  shape.
- **Write to disk**: `save_config(path: Path, config: ClaudeMonkeyConfig) -> None` — `src/claude_monkey/config.py:58-60`.
  Creates parent dirs, writes `json.dumps(asdict(config), indent=2, sort_keys=True) + "\n"`.
- **Path used for both**: `paths.config_path` = `state_dir / "config.json"` (`paths.py:12-14`).
- **CLI entry/exit points** (for reference, not part of the module contract):
  `main()` loads once via `config = load_config(paths.config_path)` at `src/claude_monkey/cli.py:1239`,
  after `paths = default_paths()` at `cli.py:1238`. Mutating subcommands (`enable`, `disable`,
  `enable-patch`, `disable-patch`, `enable-option`, `disable-option`, prompt-set, etc.) call
  `save_config(paths.config_path, config)` immediately after mutating the profile in place
  (e.g. `cli.py:683, 694, 708, 732, 743, 1022, 1176, 1272, 1281, 1305, 1431`).
- **Convenience accessor for the active `LaunchProfile` object** (lives in `cli.py`, not `config.py`):
  `active_profile(config)` — `src/claude_monkey/cli.py:154-155` — returns
  `config.profiles.setdefault("default", LaunchProfile())`. `status.py` has its own private
  equivalent, `_active_profile(config) -> LaunchProfile` at `src/claude_monkey/status.py:26`
  (same semantics, separate copy — not shared code).

## Q4: `status --json` key set (real, redacted payload)

Built by `status_payload(paths: StatePaths, config: ClaudeMonkeyConfig) -> dict[str, Any]` —
`src/claude_monkey/status.py:397-534` (the full function body is the payload; nothing is added or
removed by the caller). Invoked directly by the CLI at `src/claude_monkey/cli.py:1257-1259`
(`if args.command == "status": ... print_json(status_payload(paths, config))`).

**Caution — do not confuse with a second, dead function of the same shape**:
`_status_payload(paths, config) -> dict[str, Any]` also exists at `src/claude_monkey/cli.py:252-281`
(a private, older/narrower payload builder). It is defined but **never called** anywhere in
`cli.py` — grep confirms zero call sites. The live implementation for the `status` command is
`status.py:status_payload`, imported at `cli.py:50`. Do not build the GUI's status view against
`cli.py`'s `_status_payload`.

Real payload from this worktree (`.venv/bin/python -m claude_monkey status --json`), with
`/Users/MAC/...` paths redacted to `~/...` and the sha256 hash redacted:

```json
{
  "activeOptionIds": [],
  "activePatchIds": [],
  "activePatchSet": "~/.config/superpowers/worktrees/Claude-patch/claude-monkey-v3-gui/.development/claude-monkey-builds/upstream-attachment-suppression-2.1.199",
  "activeProfile": "default",
  "activePrompt": null,
  "buildStrategy": "unknown",
  "builtPatchIds": [],
  "changedModules": [],
  "compatibilityStatus": "unknown",
  "compatibilityWarnings": [],
  "currentClaudePath": "~/.claude-monkey/patchsets/2.1.199/default/claude",
  "desiredPatchIds": [],
  "detectedClaudeCommandPath": "/Applications/cmux.app/Contents/Resources/bin/claude",
  "discoveredOfficialClaudePath": "/Applications/cmux.app/Contents/Resources/bin/claude",
  "highRiskOptions": [],
  "installMode": "shim",
  "installRecordPath": null,
  "lastBuildCompatibilityStatus": "unknown",
  "lastBuildStrategy": "unknown",
  "lastError": null,
  "latestBuildReportPath": null,
  "liveValidationStatus": "unknown",
  "logsDir": "~/.claude-monkey/logs",
  "manifestCompatibilityStatus": "unknown",
  "officialClaudePath": null,
  "patchedBuildActive": false,
  "rebuildRequired": true,
  "repackSummary": null,
  "schemaVersion": 1,
  "shimInstalled": false,
  "shimTargetPath": null,
  "sourceClaudePath": "/Applications/cmux.app/Contents/Resources/bin/claude",
  "sourceClaudePathLegacy": "/Applications/cmux.app/Contents/Resources/bin/claude",
  "sourceClaudeVersion": "2.1.200",
  "sourceIdentityStatus": "unknown",
  "sourceSha256": "<redacted-sha256>",
  "stateDir": "~/.claude-monkey",
  "status": "not_installed",
  "statusWarnings": [],
  "targetClaudeKind": "official_fallback"
}
```

Full key set (40 keys, alphabetical as emitted by `print_json`'s `sort_keys=True`):
`activeOptionIds, activePatchIds, activePatchSet, activeProfile, activePrompt, buildStrategy,
builtPatchIds, changedModules, compatibilityStatus, compatibilityWarnings, currentClaudePath,
desiredPatchIds, detectedClaudeCommandPath, discoveredOfficialClaudePath, highRiskOptions,
installMode, installRecordPath, lastBuildCompatibilityStatus, lastBuildStrategy, lastError,
latestBuildReportPath, liveValidationStatus, logsDir, manifestCompatibilityStatus,
officialClaudePath, patchedBuildActive, rebuildRequired, repackSummary, schemaVersion,
shimInstalled, shimTargetPath, sourceClaudePath, sourceClaudePathLegacy, sourceClaudeVersion,
sourceIdentityStatus, sourceSha256, stateDir, status, statusWarnings, targetClaudeKind`.

Notes for GUI implementers:
- `activeOptionIds` / `desiredPatchIds` / `activePatchIds` are the three lists to drive an
  "enabled packages" view; `activeOptionIds` is just `list(profile.options)` (`status.py:400`) —
  there is no separate "active vs desired" distinction for options the way there is for patches
  (patches distinguish desired-in-config vs. actually-built-and-active).
- `compatibilityWarnings` and `statusWarnings` are currently always the same list
  (`status.py:504-505`) — both keys are populated from the same `compatibility_warnings` local.
- `status` is one of `"not_installed" | "rebuild_required" | "warning" | "ok"` (see the
  if/elif chain at `status.py:473-482`).

## Q5: Item-record builders for `list-patches` / `list-options`

Both subcommands go through the same dispatcher in `src/claude_monkey/cli.py`:

- `list-patches` handler: `cli.py:1287-1293`, calls `_list_payload(paths, config, PackageKind.PATCH)`.
- `list-options` handler: `cli.py:1242-1248`, calls `_list_payload(paths, config, PackageKind.OPTION)`.

`_list_payload(paths: StatePaths, config, kind: PackageKind) -> dict[str, Any]` — `cli.py:609-615`:
computes the v3 (phase-1) payload via `_list_kind_payload`, and **only for `PackageKind.PATCH`**,
falls back to the legacy v2 payload `_list_patch_payload` if the v3 discovery found zero patches
(`v3_payload if v3_payload["patches"] else _list_patch_payload(...)`). `PackageKind.OPTION` always
returns the v3 payload directly — there is no legacy fallback for options (options did not exist
pre-phase-1). This is why the `list-patches --json` run above returned the empty v3 shape
`{"patches": [], "schemaVersion": 1}` rather than the legacy shape (v3 path returned `[]`, which
is falsy, so it *did* fall through — but `_list_patch_payload` also found nothing on disk and
likewise returns `"patches": []`; the two empty shapes are indistinguishable here. **GUI code must
not assume list-patches records always have the v3 field set — check for `"valid"`/`"errors"` vs.
`"desiredEnabled"`/`"available"` to tell which shape you got.**)

- **v3 record path**: `_list_kind_payload(paths: StatePaths, config, kind: PackageKind) -> dict[str, Any]`
  — `cli.py:592-606`.
  1. Root: `_kind_root(paths, kind)` (`cli.py:505`, see Q2).
  2. Discovery: `discover_packages(root, kind) -> DiscoveryResult` (`package_model.py:452`, see Q1).
  3. Enabled-id set: `_enabled_ids_for_kind(config, kind) -> set[str]` — `cli.py:513-519` (reads
     `active_profile(config).patches` / `.options` / `{.prompt}` depending on `kind`).
  4. Valid records: `_package_record(manifest: PackageManifest, enabled: set[str]) -> dict[str, Any]`
     — `cli.py:559-574`. Emits `{id, label, kind, enabled, valid: True, compatibilityStatus,
     riskLevel, errors: [], requiresConfirmation?, statusWarning?}`. `compatibilityStatus` comes
     from `_compatibility_status(manifest)` (`cli.py:522-528`, `"unconstrained"` or `"constrained"`);
     `riskLevel` from `_risk_level(manifest)` (`cli.py:531-532`, `manifest.risk.level` or `"unknown"`).
  5. Invalid records: `_invalid_package_record(package_dir, kind, errors, enabled) -> dict[str, Any]`
     — `cli.py:577-589`. Emits `{id: package_dir.name, label: package_dir.name, kind, enabled,
     valid: False, compatibilityStatus: "unknown", riskLevel: "unknown", errors: [...]}` where
     `errors` is post-processed by `_invalid_package_errors`/`_strip_manifest_file_prefix`
     (`cli.py:535-556`) to strip the `<file>.json: ` prefix and special-case
     `id_must_match_folder` into a friendlier `"id_must_match_folder: <manifest-id> != <folder>"`
     string.
  6. Records sorted by `id` (`cli.py:600`); collection key is `"patches"`/`"prompts"`/`"options"`
     per `kind` (`cli.py:601-605`).
- **Legacy patch-only fallback**: `_list_patch_payload(paths: StatePaths, config) -> dict[str, Any]`
  — `cli.py:441-481`. Scans `_package_roots(paths)` (i.e. only `patches_dir`, see Q2 caution) for
  `*/patch.json` (old flat filename, not the v3 `load_package_manifest` glob-any-`*.json`
  convention), and emits a **different record shape**: `{id, label, desiredEnabled, activeEnabled,
  available, compatibilityStatus, compatibilityMessage}` — no `valid`/`errors`/`riskLevel`/`enabled`
  keys at all. This is the v2-era shape kept for backward compatibility while phase-1 packages
  are still being adopted; GUI code that renders `list-patches` output must handle both shapes
  (see the caution above) or only rely on fields common to both (`id`, `label`,
  `compatibilityStatus`).

## Step 3: Test suite result

`.venv/bin/python -m pytest tests/ -q` → **2 failed, 337 passed** (matches the approved
known-red baseline). Both failures are in `tests/test_reference_packages.py`
(`test_reference_packages_are_v15_schema_v2_with_valid_payload_hashes` and
`test_reference_packages_validate_against_current_pinned_source`), caused by
`FileNotFoundError` on `packages/hotrod-dragons/patch.json` — that fixture package is untracked
and absent from this worktree. No other failures were observed.
