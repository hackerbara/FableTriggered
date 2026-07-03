# ClaudeMonkey V3 Package Launch Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement ClaudeMonkey V3's local package model, clean active launch profile, command-line option packages, launch merge/preview, shared source discovery, compatibility status, and V3 build-report summaries from `/Users/MAC/Documents/Claude-patch/docs/superpowers/specs/2026-07-02-claude-monkey-v3-enhancements-design.md`.

**Architecture:** Build the V3 core in five checkpoints: package/config/source foundations; launch merge and shim parity; CLI package/status contracts; builder/report/rebuild semantics; optional menu-state parsing after V2 menu code is present. The implementation removes repo package discovery from runtime paths and treats `~/.claude-monkey/{patches,prompts,options}` as the only product package source.

**Tech Stack:** Python 3.11+ standard library, dataclasses, argparse, JSON, pathlib, pytest. Existing ClaudeMonkey package under `/Users/MAC/Documents/Claude-patch/src/claude_monkey/`.

---

## Execution location and hard boundaries

Implement in `/Users/MAC/Documents/Claude-patch` or in a linked worktree intentionally created for this work. Do not split edits between `/Users/MAC/Documents/Claude-patch` and `/Users/MAC/.codex/worktrees/c475/Claude-patch`.

Before starting implementation, run:

```bash
cd /Users/MAC/Documents/Claude-patch
git status --short
git rev-parse --show-toplevel
git branch --show-current
```

Do not stage or clean unrelated dirt. In the observed checkout, unrelated dirt may include README/test/package work not belonging to V3.

Hard non-goals:

- no migration/backcompat for old `~/.claude-patches` or loose prompt records;
- no repo-level package source, registry, or discovery model;
- no built-in option registry;
- no executable package hooks;
- no daemon/watch process;
- no menu Launch Preview item;
- no manual menu Refresh item;
- no live Claude install mutation outside existing explicit shim install code paths.

## Checkpoints

1. **Checkpoint A:** package model, clean paths/config, versions storage paths, shared source discovery, and removal of repo package source.
2. **Checkpoint B:** launch merge, launch preview, and shim parity through a canonical shim entrypoint.
3. **Checkpoint C:** CLI list/mutation/status contracts with invalid package visibility.
4. **Checkpoint D:** V3 builder/report and rebuild semantics.
5. **Checkpoint E:** menu-state parser adaptation after V2 menu code is present.

Each checkpoint ends with focused tests and a commit.

## File structure

Create or modify:

```text
src/claude_monkey/package_model.py
src/claude_monkey/config.py
src/claude_monkey/paths.py
src/claude_monkey/source_discovery.py
src/claude_monkey/launch_profile.py
src/claude_monkey/shim_entry.py
src/claude_monkey/shim.py
src/claude_monkey/cli.py
src/claude_monkey/builder_v15.py
src/claude_monkey/reports_v2.py
src/claude_monkey/menubar_state.py                 # only after V2 menu code exists

tests/test_package_model_v3.py
tests/test_config_v3.py
tests/test_source_discovery.py
tests/test_launch_profile.py
tests/test_shim_v3.py
tests/test_cli_v3_packages.py
tests/test_status_v3.py
tests/test_builder_v3_reports.py
tests/test_v3_contract_acceptance.py
tests/test_menubar_state_v3.py                     # only after V2 menu code exists
```

---

## Checkpoint A: package/config/source foundations

### Task 1: Inventory current V1/V2 references before editing

**Files:**
- No writes in this task.

- [ ] **Step 1: Run grep inventory**

```bash
cd /Users/MAC/Documents/Claude-patch
grep -R "enabledPatches\|promptProfile\|\.claude-patches\|_repo_root() / \"packages\"\|patch.json\|BuildReportV2\|activePatchIds\|current_path" -n src tests | tee /tmp/claude-monkey-v3-inventory.txt
```

Expected: inventory includes at least `src/claude_monkey/config.py`, `src/claude_monkey/paths.py`, `src/claude_monkey/cli.py`, `src/claude_monkey/shim.py`, `src/claude_monkey/builder_v15.py`, `src/claude_monkey/reports_v2.py`, and existing tests.

- [ ] **Step 2: Record inventory in commit message notes only**

Do not commit `/tmp/claude-monkey-v3-inventory.txt`. Use it to ensure later tasks update every found reference.

---

### Task 2: Add V3 package model and discovery

**Files:**
- Create: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/package_model.py`
- Create: `/Users/MAC/Documents/Claude-patch/tests/test_package_model_v3.py`

- [ ] **Step 1: Write failing package model tests**

Create `/Users/MAC/Documents/Claude-patch/tests/test_package_model_v3.py`:

```python
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from claude_monkey.package_model import (
    PackageKind,
    PackageValidationError,
    discover_packages,
    load_package_manifest,
    manifest_digest,
)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def option_manifest(package_id: str, **overrides):
    payload = {
        "schemaVersion": 1,
        "kind": "option",
        "id": package_id,
        "label": package_id.replace("-", " ").title(),
        "description": "Option package",
        "option": {
            "argv": [],
            "env": {},
            "conflictsWithArgv": [],
            "conflictsWithOptions": [],
            "conflictsWithEnv": [],
        },
    }
    payload.update(overrides)
    return payload


def prompt_manifest(package_id: str, source_path: str = "prompt.md", sha256: str | None = None):
    source = {"path": source_path}
    if sha256 is not None:
        source["sha256"] = sha256
    return {
        "schemaVersion": 1,
        "kind": "prompt",
        "id": package_id,
        "label": package_id.title(),
        "description": "Prompt package",
        "prompt": {"mode": "append", "source": source},
    }


def patch_manifest(package_id: str):
    return {
        "schemaVersion": 1,
        "kind": "patch",
        "id": package_id,
        "label": package_id.title(),
        "description": "Patch package",
        "patch": {"engine": "bun_graph_repack", "targets": []},
    }


def test_discovers_valid_and_invalid_packages(tmp_path):
    root = tmp_path / ".claude-monkey"
    write_json(root / "options" / "good-option" / "good.json", option_manifest("good-option"))
    write_json(root / "options" / "bad-option" / "bad.json", {"schemaVersion": 1, "kind": "option", "id": "wrong"})

    result = discover_packages(root / "options", PackageKind.OPTION)

    assert [item.id for item in result.valid] == ["good-option"]
    assert len(result.invalid) == 1
    assert result.invalid[0].package_dir.name == "bad-option"
    assert result.invalid[0].errors


def test_id_must_match_folder_slug(tmp_path):
    package_dir = tmp_path / "options" / "actual"
    write_json(package_dir / "manifest.json", option_manifest("different"))
    with pytest.raises(PackageValidationError, match="id_must_match_folder"):
        load_package_manifest(package_dir, PackageKind.OPTION)


def test_kind_must_match_bucket(tmp_path):
    package_dir = tmp_path / "options" / "research"
    (package_dir / "prompt.md").parent.mkdir(parents=True)
    (package_dir / "prompt.md").write_text("prompt")
    write_json(package_dir / "research.json", prompt_manifest("research"))
    with pytest.raises(PackageValidationError, match="kind_must_match_bucket"):
        load_package_manifest(package_dir, PackageKind.OPTION)


def test_option_rejects_prompt_channel_flags(tmp_path):
    package_dir = tmp_path / "options" / "bad-option"
    payload = option_manifest("bad-option")
    payload["option"]["argv"] = ["--append-system-prompt-file", "prompt.md"]
    write_json(package_dir / "bad-option.json", payload)
    with pytest.raises(PackageValidationError, match="forbidden_prompt_flag"):
        load_package_manifest(package_dir, PackageKind.OPTION)


def test_prompt_sha_and_package_local_path_are_verified(tmp_path):
    package_dir = tmp_path / "prompts" / "research"
    prompt = package_dir / "prompt.md"
    prompt.parent.mkdir(parents=True)
    prompt.write_text("extra prompt")
    digest = hashlib.sha256(prompt.read_bytes()).hexdigest()
    write_json(package_dir / "research.json", prompt_manifest("research", sha256=digest))
    loaded = load_package_manifest(package_dir, PackageKind.PROMPT)
    assert loaded.prompt is not None
    assert loaded.prompt.source.path == prompt


def test_prompt_path_cannot_escape_package(tmp_path):
    package_dir = tmp_path / "prompts" / "research"
    write_json(package_dir / "research.json", prompt_manifest("research", source_path="../escape.md"))
    with pytest.raises(PackageValidationError, match="package_path_escape"):
        load_package_manifest(package_dir, PackageKind.PROMPT)


def test_multiple_valid_json_manifests_are_invalid(tmp_path):
    package_dir = tmp_path / "options" / "dupe"
    write_json(package_dir / "one.json", option_manifest("dupe"))
    write_json(package_dir / "two.json", option_manifest("dupe"))
    with pytest.raises(PackageValidationError, match="multiple_valid_manifests"):
        load_package_manifest(package_dir, PackageKind.OPTION)


def test_manifest_digest_is_stable(tmp_path):
    package_dir = tmp_path / "patches" / "demo-patch"
    write_json(package_dir / "demo.json", patch_manifest("demo-patch"))
    loaded = load_package_manifest(package_dir, PackageKind.PATCH)
    assert manifest_digest(loaded) == manifest_digest(loaded)
```

- [ ] **Step 2: Run failing tests**

```bash
python3 -m pytest tests/test_package_model_v3.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'claude_monkey.package_model'`.

- [ ] **Step 3: Implement package model dataclasses and validation**

Create `/Users/MAC/Documents/Claude-patch/src/claude_monkey/package_model.py` with these public names:

```python
PackageKind
PackageValidationError
Risk
Compatibility
PromptSource
PromptPackage
EnvValue
EnvConflict
OptionPackage
PatchPackage
PackageManifest
InvalidPackage
DiscoveryResult
load_package_manifest
load_package_manifest_from_dict
discover_packages
manifest_digest
option_forbidden_prompt_flag
```

Validation rules to implement exactly:

- slug regex: `^[a-z0-9][a-z0-9._-]*$`;
- env regex: `^[A-Za-z_][A-Za-z0-9_]*$`;
- sha regex: `^[0-9a-fA-F]{64}$`;
- allowed `kind`: `patch`, `prompt`, `option`;
- allowed `risk.level`: `low`, `medium`, `high`;
- allowed prompt modes: `append`, `replace`;
- allowed env conflict policies: `override`, `error`;
- unknown top-level fields invalid unless field starts with `x-`;
- `id` must match folder slug;
- `kind` must match expected bucket;
- package-local paths must resolve inside package dir;
- symlinks are allowed only when resolved target stays inside package dir;
- option argv cannot include protected prompt flag forms: exact flag or `<flag>=value`;
- discovery returns both `valid` and `invalid` records.

- [ ] **Step 4: Run package model tests**

```bash
python3 -m pytest tests/test_package_model_v3.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/claude_monkey/package_model.py tests/test_package_model_v3.py
git commit -m "Add V3 package model"
```

---

### Task 3: Clean paths/config and V3 versions storage

**Files:**
- Modify: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/paths.py`
- Modify: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/config.py`
- Modify: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/cli.py`
- Create: `/Users/MAC/Documents/Claude-patch/tests/test_config_v3.py`

- [ ] **Step 1: Write failing path/config tests**

Create `/Users/MAC/Documents/Claude-patch/tests/test_config_v3.py`:

```python
from __future__ import annotations

from claude_monkey.config import ClaudeMonkeyConfig, LaunchProfile, load_config, save_config
from claude_monkey.paths import default_paths


def test_default_paths_keep_all_packages_and_builds_under_state(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    paths = default_paths()
    assert paths.state_dir == tmp_path / ".claude-monkey"
    assert paths.patches_dir == paths.state_dir / "patches"
    assert paths.prompts_dir == paths.state_dir / "prompts"
    assert paths.options_dir == paths.state_dir / "options"
    assert paths.logs_dir == paths.state_dir / "logs"
    assert paths.versions_dir == paths.state_dir / "versions"
    assert paths.patchset_dir("2.1.199", "default") == paths.state_dir / "versions" / "2.1.199" / "patchsets" / "default"


def test_v3_config_round_trip(tmp_path):
    path = tmp_path / ".claude-monkey" / "config.json"
    config = ClaudeMonkeyConfig(
        activeProfile="default",
        profiles={
            "default": LaunchProfile(
                prompt="research",
                patches=["fable-fallback", "reminder-suppression"],
                options=["local-proxy", "dangerous-permissions"],
            )
        },
        installMode="shim",
        activePatchSet="/tmp/patchset",
        officialClaudePath="/tmp/claude-official",
    )
    save_config(path, config)
    loaded = load_config(path)
    assert loaded.schemaVersion == 1
    assert loaded.activeProfile == "default"
    assert loaded.profiles["default"].prompt == "research"
    assert loaded.profiles["default"].patches == ["fable-fallback", "reminder-suppression"]
    assert loaded.profiles["default"].options == ["local-proxy", "dangerous-permissions"]
    assert loaded.officialClaudePath == "/tmp/claude-official"


def test_v3_config_rejects_multiple_profiles(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        '{"schemaVersion":1,"activeProfile":"default","profiles":{"default":{"prompt":null,"patches":[],"options":[]},"other":{"prompt":null,"patches":[],"options":[]}}}'
    )
    try:
        load_config(path)
    except ValueError as exc:
        assert "only_default_profile_supported" in str(exc)
    else:
        raise AssertionError("expected ValueError")
```

- [ ] **Step 2: Run failing tests**

```bash
python3 -m pytest tests/test_config_v3.py -q
```

Expected: FAIL because current `StatePaths` and config classes are V1/V2 shaped.

- [ ] **Step 3: Update paths**

`StatePaths` must expose:

```python
state_dir
config_path
current_path
bin_dir
patches_dir
prompts_dir
options_dir
logs_dir
versions_dir
patchset_dir(source_version: str, patchset_id: str) -> Path
```

`default_paths()` must return only `StatePaths(state_dir=home / ".claude-monkey")`. Remove `patches_dir=home / ".claude-patches"`.

- [ ] **Step 4: Update config**

Replace `Profile` with `LaunchProfile` and update load/save. `load_config()` must reject multiple profile keys in clean V3.

- [ ] **Step 5: Update immediate call sites**

Use grep inventory from Task 1. Update every current reference in `src/` from:

- `Profile` -> `LaunchProfile`;
- `enabledPatches` -> `patches`;
- `promptProfile` -> `prompt`;
- old `paths.patches_dir` constructor field -> property under state;
- `_default_output_dir()` -> `paths.patchset_dir(source_version, config.activeProfile)`.

- [ ] **Step 6: Run tests**

```bash
python3 -m pytest tests/test_config_v3.py tests/test_config_prompts.py tests/test_cli_json_contracts.py -q
```

Expected: PASS. Update tests in the same commit only where they assert old field names.

- [ ] **Step 7: Commit**

```bash
git add src/claude_monkey/paths.py src/claude_monkey/config.py src/claude_monkey/cli.py tests/test_config_v3.py tests/test_config_prompts.py tests/test_cli_json_contracts.py
git commit -m "Move config and paths to V3 layout"
```

---

### Task 4: Remove repo package source from runtime resolution

**Files:**
- Modify: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/cli.py`
- Modify: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/builder_v15.py`
- Create: `/Users/MAC/Documents/Claude-patch/tests/test_no_repo_package_source_v3.py`

- [ ] **Step 1: Write failing tests proving repo packages are ignored**

Create `/Users/MAC/Documents/Claude-patch/tests/test_no_repo_package_source_v3.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

import claude_monkey.cli as cli
from claude_monkey.paths import StatePaths


def test_resolve_package_does_not_use_repo_packages(tmp_path, monkeypatch):
    state = tmp_path / ".claude-monkey"
    paths = StatePaths(state_dir=state)
    fake_repo = tmp_path / "fake-repo"
    repo_package = fake_repo / "packages" / "repo-only-package"
    repo_package.mkdir(parents=True)
    (repo_package / "repo-only-package.json").write_text("{}")
    monkeypatch.setattr(cli, "_repo_root", lambda: fake_repo, raising=False)

    with pytest.raises(FileNotFoundError):
        cli._resolve_package("repo-only-package", paths)
```

- [ ] **Step 2: Run failing test**

```bash
python3 -m pytest tests/test_no_repo_package_source_v3.py -q
```

Expected: FAIL if `_resolve_package()` still searches `_repo_root() / "packages"`.

- [ ] **Step 3: Remove repo package roots**

Delete `_repo_root()` and `_package_roots()` if they only exist to add repo package discovery. `_resolve_package(id, paths)` must resolve only:

```text
paths.patches_dir / id
```

for build/patch commands. Prompt and option commands use `paths.prompts_dir` and `paths.options_dir` through package discovery.

- [ ] **Step 4: Run grep guard**

```bash
! grep -R "_repo_root() / \"packages\"\|home / \".claude-patches\"" -n src tests
```

Expected: command exits 0.

- [ ] **Step 5: Commit**

```bash
git add src/claude_monkey/cli.py src/claude_monkey/builder_v15.py tests/test_no_repo_package_source_v3.py
git commit -m "Remove repo package source discovery"
```

---

### Task 5: Add shared official Claude source discovery and persist install source

**Files:**
- Create: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/source_discovery.py`
- Modify: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/cli.py`
- Modify: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/install.py`
- Create: `/Users/MAC/Documents/Claude-patch/tests/test_source_discovery.py`

- [ ] **Step 1: Write failing source discovery tests**

Create `/Users/MAC/Documents/Claude-patch/tests/test_source_discovery.py` with concrete tests:

```python
from __future__ import annotations

import os
from pathlib import Path

from claude_monkey.config import ClaudeMonkeyConfig, LaunchProfile
from claude_monkey.paths import StatePaths
from claude_monkey.source_discovery import discover_official_claude, is_managed_launcher_path


def executable(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/bin/sh\necho claude\n")
    path.chmod(0o755)
    return path


def config(path: str | None = None) -> ClaudeMonkeyConfig:
    return ClaudeMonkeyConfig(activeProfile="default", profiles={"default": LaunchProfile()}, officialClaudePath=path)


def test_durable_config_source_wins_over_env(tmp_path):
    paths = StatePaths(state_dir=tmp_path / ".claude-monkey")
    durable = executable(tmp_path / "durable" / "claude")
    env_source = executable(tmp_path / "env" / "claude")
    found = discover_official_claude(config(str(durable)), paths, {"CLAUDE_MONKEY_SOURCE": str(env_source)}, lambda _: None)
    assert found == durable.resolve()


def test_env_source_used_when_no_durable_source(tmp_path):
    paths = StatePaths(state_dir=tmp_path / ".claude-monkey")
    env_source = executable(tmp_path / "env" / "claude")
    found = discover_official_claude(config(), paths, {"CLAUDE_MONKEY_SOURCE": str(env_source)}, lambda _: None)
    assert found == env_source.resolve()


def test_path_lookup_ignores_managed_shim(tmp_path):
    paths = StatePaths(state_dir=tmp_path / ".claude-monkey")
    shim = executable(paths.bin_dir / "claude")
    assert is_managed_launcher_path(shim.resolve(), paths)
    found = discover_official_claude(config(), paths, {}, lambda _: str(shim))
    assert found is None


def test_current_symlink_target_is_rejected(tmp_path):
    paths = StatePaths(state_dir=tmp_path / ".claude-monkey")
    current_target = executable(paths.state_dir / "versions" / "2.1.199" / "patchsets" / "default" / "claude")
    paths.current_path.parent.mkdir(parents=True, exist_ok=True)
    paths.current_path.symlink_to(current_target)
    found = discover_official_claude(config(str(paths.current_path)), paths, {}, lambda _: None)
    assert found is None


def test_direct_managed_patchset_path_is_rejected(tmp_path):
    paths = StatePaths(state_dir=tmp_path / ".claude-monkey")
    managed = executable(paths.state_dir / "versions" / "2.1.199" / "patchsets" / "default" / "claude")
    found = discover_official_claude(config(str(managed)), paths, {}, lambda _: None)
    assert found is None
```

- [ ] **Step 2: Implement `source_discovery.py`**

Public functions/classes:

```python
SourceIdentity
discover_official_claude
source_identity
is_managed_launcher_path
```

Rules:

- durable config source wins over `CLAUDE_MONKEY_SOURCE`;
- env source used when durable source absent;
- PATH lookup used last;
- managed shim/current paths rejected;
- returned paths are executable files.

- [ ] **Step 3: Wire every source-discovery call site**

Update these call sites to use `discover_official_claude()`:

- `cli.py` `_discover_source()` / build source default;
- `cli.py` `status --json` source fields;
- `cli.py` `use-official --official` updates `config.officialClaudePath`;
- `install.py` install transaction records source path when installing a shim;
- future `shim_entry.py` in Checkpoint B.

- [ ] **Step 4: Add persistence test**

Extend source/CLI tests so `use-official --official <path> --json` saves `officialClaudePath` in config.

- [ ] **Step 5: Run tests**

```bash
python3 -m pytest tests/test_source_discovery.py tests/test_install.py tests/test_cli_json_contracts.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/claude_monkey/source_discovery.py src/claude_monkey/cli.py src/claude_monkey/install.py tests/test_source_discovery.py tests/test_install.py tests/test_cli_json_contracts.py
git commit -m "Add shared official Claude source discovery"
```

---

## Checkpoint B: launch merge, preview, and shim parity

### Task 6: Add launch profile merge core

**Files:**
- Create: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/launch_profile.py`
- Create: `/Users/MAC/Documents/Claude-patch/tests/test_launch_profile.py`

- [ ] **Step 1: Write concrete launch merge tests**

Create table-driven tests for:

- prompt append and replace flag mapping;
- user prompt flag skip;
- every management token: `--help`, `-h`, `--version`, `update`, `upgrade`, `doctor`, `auth`, `mcp`, `plugin`, `plugins`, `install`;
- `--` boundary;
- user argv conflict skips whole option argv contribution;
- `conflictsWithOptions` creates merge error when both options are enabled;
- base process env wins unless `allowOverrideProcessEnv` is true;
- `conflictsWithEnv` policy `error` blocks merge;
- secret env values redacted.

- [ ] **Step 2: Implement merge dataclasses and functions**

Public names:

```python
LaunchTarget
LaunchMergeInput
LaunchMergeResult
MANAGEMENT_TOKENS
is_management_invocation
has_user_prompt_flag
LoadedLaunchPackages
load_active_launch_packages
select_launch_target
merge_launch_profile
```

Implement these dataclasses in `/Users/MAC/Documents/Claude-patch/src/claude_monkey/launch_profile.py`:

```python
@dataclass(frozen=True)
class LaunchTarget:
    path: Path
    kind: str


@dataclass(frozen=True)
class LoadedLaunchPackages:
    prompt: PackageManifest | None
    options: list[PackageManifest]
    skipped: list[dict[str, str]]
    warnings: list[str]


@dataclass(frozen=True)
class LaunchMergeInput:
    user_argv: list[str]
    process_env: dict[str, str]
    prompt: PackageManifest | None
    options: list[PackageManifest]
    target: LaunchTarget
    initial_skipped: list[dict[str, str]]
    initial_warnings: list[str]


@dataclass(frozen=True)
class LaunchMergeResult:
    target: LaunchTarget
    argv: list[str]
    env: dict[str, str]
    env_preview: dict[str, str]
    skipped: list[dict[str, str]]
    warnings: list[str]
    errors: list[str]
    management: bool
```

`load_active_launch_packages(paths, config)` returns `LoadedLaunchPackages`. Missing or invalid active prompt/option ids do not raise; they are represented in `skipped` and `warnings` so launch-preview and status can surface them.

`select_launch_target(paths, config, process_env)` returns `LaunchTarget(path, kind)` where `kind` is `patched`, `official_fallback`, or `official_management`. `patched` is returned only when `current` resolves to an executable managed patched build. `official_fallback` is returned when `current` is missing/unusable and shared source discovery finds an official Claude. `official_management` is used by `merge_launch_profile()` for management invocations so preview/status can distinguish management skip.

`merge_launch_profile()` must be deterministic and side-effect free. It receives loaded `PackageManifest` objects, initial skipped/warning records from package loading, plus a `LaunchTarget`, and returns final argv/env/preview/skipped/warnings/errors.

- [ ] **Step 3: Run tests**

```bash
python3 -m pytest tests/test_launch_profile.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/claude_monkey/launch_profile.py tests/test_launch_profile.py
git commit -m "Add V3 launch profile merge"
```

---

### Task 7: Add launch-preview CLI command

**Files:**
- Modify: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/cli.py`
- Create/modify: `/Users/MAC/Documents/Claude-patch/tests/test_cli_v3_packages.py`

- [ ] **Step 1: Write launch-preview tests**

Use temp HOME with a prompt package and option package. Assert:

```json
{
  "schemaVersion": 1,
  "targetClaudeKind": "official_fallback",
  "argv": ["--append-system-prompt-file", "<path>", "--model", "sonnet", "--resume"],
  "envPreview": {},
  "skipped": [],
  "warnings": [],
  "errors": []
}
```

Also test secret env redaction:

```json
"envPreview": {"ANTHROPIC_API_KEY": "<redacted>"}
```

- [ ] **Step 2: Add parser and handler**

Add:

```python
launch_preview = sub.add_parser("launch-preview")
launch_preview.add_argument("--json", action="store_true")
launch_preview.add_argument("argv", nargs=argparse.REMAINDER)
```

Strip one leading `--` separator from `args.argv` before merging. Load packages from active config. Use shared source discovery/current target logic. Print stable unwrapped JSON. Serialize `targetClaudePath` from `result.target.path` and `targetClaudeKind` from `result.target.kind`. Include `result.skipped` and `result.warnings`, including missing/invalid active package records from `LoadedLaunchPackages`.

- [ ] **Step 3: Run tests**

```bash
python3 -m pytest tests/test_launch_profile.py tests/test_cli_v3_packages.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/claude_monkey/cli.py tests/test_cli_v3_packages.py
git commit -m "Add launch preview command"
```

---

### Task 8: Replace standalone shim logic with canonical shim entrypoint

**Files:**
- Create: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/shim_entry.py`
- Modify: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/shim.py`
- Create/modify: `/Users/MAC/Documents/Claude-patch/tests/test_shim_v3.py`

- [ ] **Step 1: Write shim parity tests**

Tests must prove the generated shim delegates to an importable canonical entrypoint rather than duplicating merge logic. Assert rendered shim contains:

```python
from claude_monkey.shim_entry import main
```

and does not contain old standalone prompt merge functions such as `active_prompt_args`.

Add tests for `shim_entry.compute_launch()` covering the same representative cases as `launch-preview`:

- prompt append;
- option argv/env;
- management skip;
- official fallback when current missing;
- recursion rejection.

- [ ] **Step 2: Implement `shim_entry.py`**

Public functions:

```python
def compute_launch(state_dir: Path, user_argv: list[str], process_env: Mapping[str, str]) -> LaunchMergeResult:
    state_dir = state_dir.expanduser()
    paths = StatePaths(state_dir=state_dir)
    config = load_config(paths.config_path)
    loaded = load_active_launch_packages(paths, config)
    target = select_launch_target(paths, config, process_env)
    return merge_launch_profile(
        LaunchMergeInput(
            user_argv=list(user_argv),
            process_env=dict(process_env),
            prompt=loaded.prompt,
            options=loaded.options,
            target=target,
            initial_skipped=list(loaded.skipped),
            initial_warnings=list(loaded.warnings),
        )
    )


def main(state_dir_text: str | None = None) -> int:
    state_dir = Path(state_dir_text) if state_dir_text is not None else Path.home() / ".claude-monkey"
    result = compute_launch(state_dir, sys.argv[1:], os.environ)
    if result.errors:
        for error in result.errors:
            print(f"ClaudeMonkey: {error}", file=sys.stderr)
        return 2
    os.execvpe(str(result.target.path), [str(result.target.path), *result.argv], result.env)
    return 127
```

`compute_launch()` loads config/packages, selects target, and calls `merge_launch_profile()`.

`main()` calls `os.execvpe(str(result.target.path), [str(result.target.path), *result.argv], result.env)` when no merge errors exist. If merge errors exist, print concise errors to stderr and return 2.

- [ ] **Step 3: Update generated shim**

`render_shim_script(state_dir)` should produce only bootstrap code:

```python
#!/usr/bin/env python3
from __future__ import annotations

from claude_monkey.shim_entry import main

if __name__ == "__main__":
    raise SystemExit(main("<state_dir>"))
```

- [ ] **Step 4: Run shim tests**

```bash
python3 -m pytest tests/test_shim.py tests/test_shim_v3.py tests/test_launch_profile.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/claude_monkey/shim.py src/claude_monkey/shim_entry.py tests/test_shim.py tests/test_shim_v3.py
git commit -m "Use canonical V3 shim entrypoint"
```

---

## Checkpoint C: CLI package/status contracts

### Task 9: Add kind-specific package CLI commands with invalid package visibility

**Files:**
- Modify: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/cli.py`
- Modify: `/Users/MAC/Documents/Claude-patch/tests/test_cli_v3_packages.py`

- [ ] **Step 1: Write list command tests including invalid packages**

Tests for `list-options --json`, `list-prompts --json`, and `list-patches --json` must assert invalid packages are present:

```json
{
  "id": "bad-option",
  "label": "bad-option",
  "kind": "option",
  "enabled": false,
  "valid": false,
  "compatibilityStatus": "unknown",
  "riskLevel": "unknown",
  "errors": ["id_must_match_folder: different != bad-option"]
}
```

Valid records must include:

```json
{"id":"local-session-defaults","label":"Local Session Defaults","kind":"option","enabled":true,"valid":true,"compatibilityStatus":"unconstrained","riskLevel":"low","errors":[]}
```

- [ ] **Step 2: Write mutation command tests**

Cover:

```bash
enable-patch <id> --json
disable-patch <id> --json
set-prompt <id> --json
clear-prompt --json
enable-option <id> --json
enable-option <id> --confirm --json
disable-option <id> --json
```

Include high-risk confirmation behavior and `conflictsWithOptions` rejection when enabling a conflicting option.

- [ ] **Step 3: Add parser and handlers**

Add explicit V3 commands. Keep mutating commands wrapped in the existing JSON envelope style. List/status remain stable unwrapped JSON state documents.

Mutation semantics:

- `enable-patch` appends to `profiles.default.patches` if absent;
- `disable-patch` removes from `profiles.default.patches`;
- `set-prompt` validates package and sets `profiles.default.prompt`;
- `clear-prompt` sets prompt to null;
- `enable-option` appends to `profiles.default.options`;
- disabling and re-enabling an option moves it to the end;
- high-risk `requiresConfirmation` needs `--confirm`;
- `conflictsWithOptions` blocks enabling and returns `error.code: "option_conflict"`.

- [ ] **Step 4: Run tests**

```bash
python3 -m pytest tests/test_cli_v3_packages.py tests/test_package_model_v3.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/claude_monkey/cli.py tests/test_cli_v3_packages.py
git commit -m "Add V3 package CLI commands"
```

---

### Task 10: Add V3 status JSON and rebuild semantics

**Files:**
- Create: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/status.py`
- Modify: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/cli.py`
- Create: `/Users/MAC/Documents/Claude-patch/tests/test_status_v3.py`

- [ ] **Step 1: Write full status payload tests**

Create tests asserting this complete shape for a matching patched build:

```json
{
  "schemaVersion": 1,
  "status": "ok",
  "activeProfile": "default",
  "activePrompt": "research",
  "desiredPatchIds": ["fable-fallback"],
  "builtPatchIds": ["fable-fallback"],
  "activePatchIds": ["fable-fallback"],
  "patchedBuildActive": true,
  "targetClaudeKind": "patched",
  "activeOptionIds": ["dangerous-permissions"],
  "highRiskOptions": [{"id":"dangerous-permissions","label":"Dangerous permissions","warning":"Dangerous permissions enabled"}],
  "sourceClaudeVersion": "2.1.199",
  "sourceClaudePath": "/tmp/claude",
  "sourceSha256": "<sha>",
  "compatibilityStatus": "compatible",
  "manifestCompatibilityStatus": "compatible",
  "sourceIdentityStatus": "compatible",
  "lastBuildCompatibilityStatus": "compatible",
  "liveValidationStatus": "unknown",
  "compatibilityWarnings": [],
  "rebuildRequired": false,
  "latestBuildReportPath": "<path>",
  "lastError": null
}
```

Add tests for official fallback with desired patches:

```json
{"targetClaudeKind":"official_fallback","patchedBuildActive":false,"activePatchIds":[],"rebuildRequired":true}
```

Add tests for invalid prompt/option warnings and invalid package visibility. The status implementation must use `load_active_launch_packages()` or equivalent package-loading result data so missing/invalid active prompt/options appear in `compatibilityWarnings` or status warnings rather than disappearing.

- [ ] **Step 2: Implement status helpers**

Create `/Users/MAC/Documents/Claude-patch/src/claude_monkey/status.py` and implement:

```python
def status_payload(paths: StatePaths, config: ClaudeMonkeyConfig) -> dict[str, Any]:
    profile = config.profiles["default"]
    source = discover_official_claude(config, paths)
    report_path, report = latest_build_report(config.activePatchSet)
    desired_patch_ids = list(profile.patches)
    built_patch_ids = patch_ids_from_report(report)
    target_kind, active_patch_ids = active_target_patch_state(paths, report, built_patch_ids)
    return build_status_payload(
        paths=paths,
        config=config,
        source=source,
        report_path=report_path,
        report=report,
        desired_patch_ids=desired_patch_ids,
        built_patch_ids=built_patch_ids,
        active_patch_ids=active_patch_ids,
        target_kind=target_kind,
    )
```

Use:

- package discovery for prompt/patch/option state;
- shared source discovery for source fields;
- active build report for `builtPatchIds` and `lastBuildCompatibilityStatus`;
- current symlink/executable checks for `patchedBuildActive` and `targetClaudeKind`;
- manifest digests for rebuild-required.

- [ ] **Step 3: Run status tests**

```bash
python3 -m pytest tests/test_status_v3.py tests/test_cli_json_contracts.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add src/claude_monkey/status.py src/claude_monkey/cli.py tests/test_status_v3.py tests/test_cli_json_contracts.py
git commit -m "Add V3 status payload"
```

---

## Checkpoint D: builder/report v3

### Task 11: Evolve builder/report to V3 patch package envelope

**Files:**
- Modify: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/builder_v15.py`
- Modify: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/reports_v2.py`
- Modify: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/cli.py`
- Create: `/Users/MAC/Documents/Claude-patch/tests/test_builder_v3_reports.py`

- [ ] **Step 1: Write failing builder/report tests**

Tests must cover success and failure reports. For a manifest identity mismatch failure, assert the written `build-report.json` still includes:

```json
{
  "schemaVersion": 3,
  "packageManifestDigests": {"demo-patch":"<sha>"},
  "sourceIdentity": {"claudeVersion":"fixture","versionOutput":"fixture","sha256":"<sha>","sizeBytes":123,"platform":"darwin","arch":"arm64"},
  "buildInputSnapshot": {"patches":["demo-patch"],"promptAtBuildTime":"research","optionsAtBuildTime":["local-session-defaults"]},
  "compatibility": {"status":"source_sha_mismatch","warnings":[]}
}
```

- [ ] **Step 2: Choose explicit report class direction**

Evolve `BuildReportV2` in place to emit `schemaVersion: 3` and add V3 fields. Do not create a parallel class in this task.

Add fields:

```python
packageManifestDigests: dict[str, str]
sourceIdentity: dict[str, Any]
buildInputSnapshot: dict[str, Any]
compatibility: dict[str, Any]
```

- [ ] **Step 3: Load V3 patch envelope inside builder**

Use `load_package_manifest(package_dir, PackageKind.PATCH)`. Convert `manifest.patch.targets` into the existing V1.5 target parser by building the raw dict shape expected by `load_manifest_v2_dict()` or by extracting the target parsing helpers into reusable functions.

- [ ] **Step 4: Pass V3 report context into builder**

Extend `BuildRequestV15` with:

```python
manifest_digests: dict[str, str]
build_input_snapshot: dict[str, Any]
```

`handle_build()` computes those from config and package manifests before calling builder. Builder writes those fields for both success and failure reports.

- [ ] **Step 5: Run builder/report tests**

```bash
python3 -m pytest tests/test_builder_v3_reports.py tests/test_builder_v15.py tests/test_cli_v15.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/claude_monkey/builder_v15.py src/claude_monkey/reports_v2.py src/claude_monkey/cli.py tests/test_builder_v3_reports.py tests/test_builder_v15.py tests/test_cli_v15.py
git commit -m "Write V3 build report summaries"
```

---

### Task 12: Add V3 contract acceptance tests

**Files:**
- Create: `/Users/MAC/Documents/Claude-patch/tests/test_v3_contract_acceptance.py`
- Modify the implementation files from Tasks 2-11 when this test exposes a contract bug.

- [ ] **Step 1: Write prompt/option acceptance test**

Acceptance flow:

1. Temp HOME.
2. Seed prompt package and option package under `.claude-monkey`.
3. Run `list-prompts --json`, `list-options --json`.
4. Run `set-prompt research --json`.
5. Run `enable-option local-session-defaults --json`.
6. Run `launch-preview --json -- --resume` and assert prompt/option argv are present.
7. Run `status --json` and assert active prompt/options are present.
8. Run `clear-prompt --json` and `disable-option local-session-defaults --json`.
9. Assert launch preview no longer includes prompt/option additions.

- [ ] **Step 2: Write report/status acceptance test using fixture report**

Acceptance flow:

1. Temp HOME.
2. Seed active config with desired patch id.
3. Seed `versions/2.1.199/patchsets/default/build-report.json` with V3 report fields and matching patch ids.
4. Point `config.activePatchSet` at that patchset.
5. Symlink `current` to a disposable executable under the patchset.
6. Run `status --json`.
7. Assert `patchedBuildActive:true`, `targetClaudeKind:"patched"`, `builtPatchIds` and `activePatchIds` match.
8. Remove `current`.
9. Run `status --json`.
10. Assert `targetClaudeKind:"official_fallback"`, `activePatchIds:[]`, and `rebuildRequired:true`.

- [ ] **Step 3: Run focused acceptance**

```bash
python3 -m pytest tests/test_v3_contract_acceptance.py -q
```

Expected: PASS.

- [ ] **Step 4: Run checkpoint suite**

```bash
python3 -m pytest tests/test_package_model_v3.py tests/test_config_v3.py tests/test_no_repo_package_source_v3.py tests/test_source_discovery.py tests/test_launch_profile.py tests/test_shim_v3.py tests/test_cli_v3_packages.py tests/test_status_v3.py tests/test_builder_v3_reports.py tests/test_v3_contract_acceptance.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/test_v3_contract_acceptance.py src/claude_monkey
git commit -m "Add V3 contract acceptance coverage"
```

---

## Checkpoint E: V2 menu-state parser integration

### Task 13: Update menu parser after V2 menu code is present

**Files:**
- Modify: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/menubar_state.py`
- Create: `/Users/MAC/Documents/Claude-patch/tests/test_menubar_state_v3.py`

- [ ] **Step 1: Verify V2 menu parser prerequisite**

Run:

```bash
test -f src/claude_monkey/menubar_state.py
```

Expected: PASS. If it fails, stop this task and merge/complete V2 menu implementation first. Do not create a substitute V3-only menu parser in this plan.

- [ ] **Step 2: Write V3 menu-state tests**

Tests must assert parser captures:

- `activeOptionIds`;
- option package list payload;
- `highRiskOptions`;
- `builtPatchIds`;
- `patchedBuildActive`;
- `targetClaudeKind`;
- compatibility dimension fields;
- no Launch Preview menu action;
- no Refresh menu action.

- [ ] **Step 3: Update parser dataclasses**

Add `OptionMenuItem` and high-risk option summary dataclasses. Extend `MenuState` with V3 status fields. Parse list-options payload separately from list-prompts/list-patches.

- [ ] **Step 4: Run menu parser tests**

```bash
python3 -m pytest tests/test_menubar_state.py tests/test_menubar_state_v3.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/claude_monkey/menubar_state.py tests/test_menubar_state_v3.py tests/test_menubar_state.py
git commit -m "Parse V3 menu state fields"
```

---

## Final verification

Run:

```bash
python3 -m pytest -q
python3 -m claude_monkey status --json
python3 -m claude_monkey list-prompts --json
python3 -m claude_monkey list-options --json
python3 -m claude_monkey launch-preview --json -- --help
```

Expected:

- tests pass;
- JSON commands emit valid JSON;
- `launch-preview -- --help` classifies as management and skips prompt/option injection;
- no runtime code searches `/Users/MAC/Documents/Claude-patch/packages` as a product package source;
- no runtime code searches `~/.claude-patches`;
- existing unrelated worktree dirt remains untouched.
