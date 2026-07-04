from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from claude_monkey import repair as repair_module
from claude_monkey.install import install_shim_transaction, restore_install_transaction
from claude_monkey.paths import StatePaths
from claude_monkey.repair import (
    CacheSourceRefused,
    RepairRefused,
    cache_source_action,
    repair_shim_action,
)

# docs/superpowers/specs/2026-07-04-claude-monkey-shim-update-resilience.md
# Sec2 (cache official source) / Sec3 (repair existing shim) / Refinements
# R1-R4, R6, R8, R9. Stage 2: cache-source + repair-shim.


def make_executable(path: Path, text: str = "#!/bin/sh\necho '2.1.199 (Claude Code)'\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(path.stat().st_mode | 0o111)
    return path


def seed_shim_target(tmp_path: Path) -> tuple[Path, Path]:
    """Install a real managed shim over an existing binary at an external
    target path, mirroring test_status_v3.py's stage-1 helper and the
    spec's observed failure mode.
    """
    state = tmp_path / ".claude-monkey"
    target = tmp_path / "local-bin" / "claude"
    make_executable(target, "#!/bin/sh\necho '2.1.199 (Claude Code)'\n")
    install_shim_transaction(target, state, dry_run=False)
    return state, target


def replace_target_with_official(
    target: Path, tmp_path: Path, *, version: str = "2.1.201", name: str = "official-source"
) -> Path:
    """Simulate an official Claude updater clobbering the shim in place with
    a symlink to a newly installed official binary.
    """
    official = make_executable(
        tmp_path / name / "claude",
        f"#!/bin/sh\necho '{version} (Claude Code)'\n",
    )
    target.unlink()
    target.symlink_to(official)
    return official


# -- repair-shim: happy path --------------------------------------------


def test_repair_shim_happy_path_caches_swaps_and_rewrites_record(tmp_path):
    state, target = seed_shim_target(tmp_path)
    official = replace_target_with_official(target, tmp_path)
    official_sha = hashlib.sha256(official.read_bytes()).hexdigest()
    paths = StatePaths(state)

    result = repair_shim_action(target, state, paths)

    assert result["repaired"] is True
    assert result["newOfficialSha256"] == official_sha
    assert result["newOfficialVersion"] == "2.1.201"
    assert result["previousOfficialSha256"] == official_sha

    # 1. cached
    cache_path = Path(result["cachedSourcePath"])
    assert cache_path.is_file()
    assert cache_path.read_bytes() == official.read_bytes()

    # 2. swapped: target is the ClaudeMonkey shim again
    assert "ClaudeMonkey" in target.read_text()
    assert not target.is_symlink()

    # 3. record rewritten to point at the NEW official source (R4), not the
    # stale 2.1.199 the shim was originally installed over.
    record = json.loads((state / "install-record.json").read_text())
    assert record["previousSourceSha256"] == official_sha
    assert record["previousType"] == "symlink"
    assert record["previousTarget"] == str(official)
    assert record["installedShimSha256"]


# -- R9: concurrent clobber ----------------------------------------------


def test_repair_shim_aborts_on_concurrent_clobber_after_cache(tmp_path, monkeypatch):
    state, target = seed_shim_target(tmp_path)
    replace_target_with_official(target, tmp_path)
    paths = StatePaths(state)

    real_cache_source = repair_module.cache_source
    clobber_bytes = b"#!/bin/sh\necho newer-official-landed-mid-repair\n"

    def clobbering_cache_source(resolved_source, state_dir, **kwargs):
        result = real_cache_source(resolved_source, state_dir, **kwargs)
        # A concurrent official updater replaces the target again, after we
        # cached the (now-stale) bytes but before the swap -- exactly the
        # window R3 requires a re-verify to close.
        target.unlink()
        target.write_bytes(clobber_bytes)
        target.chmod(target.stat().st_mode | 0o111)
        return result

    monkeypatch.setattr(repair_module, "cache_source", clobbering_cache_source)

    with pytest.raises(RepairRefused) as exc_info:
        repair_shim_action(target, state, paths)

    assert exc_info.value.code == "target_changed"
    # No partial write: target holds exactly the clobbering bytes, not the
    # shim and not reverted to anything else.
    assert target.read_bytes() == clobber_bytes
    assert "ClaudeMonkey" not in target.read_text()


# -- R9: corrupt cache -----------------------------------------------------


def test_repair_shim_refuses_when_previous_source_cache_is_corrupt(tmp_path):
    state, target = seed_shim_target(tmp_path)
    replace_target_with_official(target, tmp_path)
    paths = StatePaths(state)

    record_path = state / "install-record.json"
    record = json.loads(record_path.read_text())
    cache_path = Path(record["previousSourceCachePath"])
    cache_path.write_bytes(b"corrupted-cache-bytes")

    with pytest.raises(RepairRefused) as exc_info:
        repair_shim_action(target, state, paths)

    assert exc_info.value.code == "cache_invalid"
    # No write attempted at all: target is still the (replaced) symlink.
    assert target.is_symlink()


# -- R9: repair-then-uninstall ----------------------------------------------


def test_repair_then_uninstall_restores_new_official_not_stale_one(tmp_path):
    state, target = seed_shim_target(tmp_path)
    official = replace_target_with_official(target, tmp_path)
    paths = StatePaths(state)

    repair_shim_action(target, state, paths)
    assert "ClaudeMonkey" in target.read_text()

    record_path = state / "install-record.json"
    restored = restore_install_transaction(target, record_path, force=False)

    assert restored is True
    assert target.is_symlink()
    assert target.resolve() == official.resolve()


# -- never-managed / preconditions ------------------------------------------


def test_repair_shim_refuses_never_managed_target(tmp_path):
    state = tmp_path / ".claude-monkey"
    state.mkdir(parents=True)
    target = tmp_path / "local-bin" / "claude"
    make_executable(target)
    paths = StatePaths(state)

    with pytest.raises(RepairRefused) as exc_info:
        repair_shim_action(target, state, paths)

    assert exc_info.value.code == "no_install_record"
    assert target.read_text().startswith("#!/bin/sh")


def test_repair_shim_refuses_authorization_required_target_before_any_write(
    tmp_path, monkeypatch
):
    state, target = seed_shim_target(tmp_path)
    replace_target_with_official(target, tmp_path)
    paths = StatePaths(state)

    monkeypatch.setattr(repair_module, "target_needs_authorization", lambda path: True)

    sources_before = set((state / "sources").iterdir()) if (state / "sources").exists() else set()

    with pytest.raises(RepairRefused) as exc_info:
        repair_shim_action(target, state, paths)

    assert exc_info.value.code == "authorization_required"
    # No write attempted: target untouched, and no new cache entry created.
    assert target.is_symlink()
    sources_after = set((state / "sources").iterdir()) if (state / "sources").exists() else set()
    assert sources_after == sources_before


# -- cache-source ------------------------------------------------------------


def test_cache_source_action_happy_path(tmp_path):
    state, target = seed_shim_target(tmp_path)
    official = replace_target_with_official(target, tmp_path)
    official_sha = hashlib.sha256(official.read_bytes()).hexdigest()
    paths = StatePaths(state)

    result = cache_source_action(target, state, paths)

    assert result["sha256"] == official_sha
    cache_path = Path(result["cachedSourcePath"])
    assert cache_path.is_file()
    assert cache_path.read_bytes() == official.read_bytes()
    source_record = json.loads(
        (cache_path.parent / "source-record.json").read_text()
    )
    assert source_record["sha256"] == official_sha
    assert source_record["version"] == "2.1.201"
    # Never touches the target itself.
    assert target.is_symlink()
    assert target.resolve() == official.resolve()


def test_cache_source_refuses_managed_path(tmp_path):
    state = tmp_path / ".claude-monkey"
    paths = StatePaths(state)
    managed = paths.bin_dir / "claude"
    make_executable(managed)

    with pytest.raises(CacheSourceRefused) as exc_info:
        cache_source_action(managed, state, paths)

    assert exc_info.value.code == "managed_path_refused"


def test_cache_source_aborts_when_target_changes_before_copy(tmp_path, monkeypatch):
    state, target = seed_shim_target(tmp_path)
    replace_target_with_official(target, tmp_path)
    paths = StatePaths(state)

    real_classify = repair_module.classify_plausible_official_source
    calls = {"n": 0}

    def flaky_classify(target_path, paths_arg):
        calls["n"] += 1
        if calls["n"] == 1:
            return real_classify(target_path, paths_arg)
        # Simulate the target having changed between the initial
        # classify/hash and the pre-copy re-verify.
        return tmp_path / "unrelated-does-not-exist"

    monkeypatch.setattr(repair_module, "classify_plausible_official_source", flaky_classify)

    with pytest.raises(CacheSourceRefused) as exc_info:
        cache_source_action(target, state, paths)

    assert exc_info.value.code == "target_changed"


# -- R6: cache retention -----------------------------------------------------


def test_cache_source_retention_keeps_active_and_two_newest(tmp_path, monkeypatch):
    counter = iter(range(1, 10_000))
    monkeypatch.setattr("claude_monkey.install.time", lambda: next(counter))

    state, target = seed_shim_target(tmp_path)
    paths = StatePaths(state)
    record_path = state / "install-record.json"
    active_digest = json.loads(record_path.read_text())["previousSourceSha256"]

    digests = []
    for index in range(3):
        official = replace_target_with_official(
            target, tmp_path, version=f"2.1.20{index}", name=f"official-{index}"
        )
        digests.append(hashlib.sha256(official.read_bytes()).hexdigest())
        cache_source_action(target, state, paths)

    sources_dir = state / "sources"
    remaining = {entry.name for entry in sources_dir.iterdir() if entry.is_dir()}

    # The active install record's rollback digest is never GC'd...
    assert active_digest in remaining
    # ...and only the 2 most recently captured *other* distinct digests
    # survive: the oldest of the three newly cached sources is removed.
    assert digests[0] not in remaining
    assert digests[1] in remaining
    assert digests[2] in remaining
