from __future__ import annotations

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
    return ClaudeMonkeyConfig(
        activeProfile="default",
        profiles={"default": LaunchProfile()},
        officialClaudePath=path,
    )


def test_durable_config_source_wins_over_env(tmp_path):
    paths = StatePaths(state_dir=tmp_path / ".claude-monkey")
    durable = executable(tmp_path / "durable" / "claude")
    env_source = executable(tmp_path / "env" / "claude")
    found = discover_official_claude(
        config(str(durable)),
        paths,
        {"CLAUDE_MONKEY_SOURCE": str(env_source)},
        lambda _: None,
    )
    assert found == durable.resolve()


def test_env_source_used_when_no_durable_source(tmp_path):
    paths = StatePaths(state_dir=tmp_path / ".claude-monkey")
    env_source = executable(tmp_path / "env" / "claude")
    found = discover_official_claude(
        config(), paths, {"CLAUDE_MONKEY_SOURCE": str(env_source)}, lambda _: None
    )
    assert found == env_source.resolve()


def test_path_lookup_ignores_managed_shim(tmp_path):
    paths = StatePaths(state_dir=tmp_path / ".claude-monkey")
    shim = executable(paths.bin_dir / "claude")
    assert is_managed_launcher_path(shim.resolve(), paths)
    found = discover_official_claude(config(), paths, {}, lambda _: str(shim))
    assert found is None


def test_current_symlink_target_is_rejected(tmp_path):
    paths = StatePaths(state_dir=tmp_path / ".claude-monkey")
    current_target = executable(
        paths.state_dir / "versions" / "2.1.199" / "patchsets" / "default" / "claude"
    )
    paths.current_path.parent.mkdir(parents=True, exist_ok=True)
    paths.current_path.symlink_to(current_target)
    found = discover_official_claude(config(str(paths.current_path)), paths, {}, lambda _: None)
    assert found is None


def test_direct_managed_patchset_path_is_rejected(tmp_path):
    paths = StatePaths(state_dir=tmp_path / ".claude-monkey")
    managed = executable(
        paths.state_dir / "versions" / "2.1.199" / "patchsets" / "default" / "claude"
    )
    found = discover_official_claude(config(str(managed)), paths, {}, lambda _: None)
    assert found is None
