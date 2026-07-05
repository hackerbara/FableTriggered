from __future__ import annotations

import os
from pathlib import Path

from claude_monkey import platform_support
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


def test_managed_current_symlink_target_is_rejected(tmp_path):
    paths = StatePaths(state_dir=tmp_path / ".claude-monkey")
    managed = executable(
        paths.state_dir / "versions" / "2.1.199" / "patchsets" / "default" / "claude"
    )
    paths.current_path.parent.mkdir(parents=True, exist_ok=True)
    paths.current_path.symlink_to(managed)

    found = discover_official_claude(config(str(managed.resolve())), paths, {}, lambda _: None)

    assert found is None


def test_external_official_current_target_remains_discoverable(tmp_path):
    paths = StatePaths(state_dir=tmp_path / ".claude-monkey")
    official = executable(tmp_path / "official" / "claude")
    paths.current_path.parent.mkdir(parents=True, exist_ok=True)
    paths.current_path.symlink_to(official)

    found = discover_official_claude(config(str(official)), paths, {}, lambda _: None)

    assert found == official.resolve()


def test_windows_install_candidate_discovered_when_faked_windows(tmp_path, monkeypatch):
    monkeypatch.setattr(platform_support.sys, "platform", "win32")
    # is_executable_file splits PATHEXT on os.pathsep (";" on real Windows,
    # matching real PATHEXT formatting there); os.pathsep is tied to os.name,
    # not the faked sys.platform, so on this host it's still ":".
    monkeypatch.setenv("PATHEXT", os.pathsep.join([".COM", ".EXE", ".BAT", ".CMD"]))
    paths = StatePaths(state_dir=tmp_path / ".claude-monkey")
    launcher = tmp_path / ".local" / "bin" / "claude.exe"
    launcher.parent.mkdir(parents=True)
    launcher.write_text("claude")

    found = discover_official_claude(
        config(), paths, {"USERPROFILE": str(tmp_path)}, lambda _: None
    )

    assert found == launcher.resolve()


def test_windows_non_executable_extension_not_discovered(tmp_path, monkeypatch):
    monkeypatch.setattr(platform_support.sys, "platform", "win32")
    # PATHEXT deliberately excludes .exe -- a file at the expected launcher
    # path exists, but its extension is not recognized as executable, so it
    # must NOT be treated as discoverable (proves is_executable_file gates
    # correctly through the "install" candidate path).
    monkeypatch.setenv("PATHEXT", os.pathsep.join([".COM", ".BAT", ".CMD"]))
    paths = StatePaths(state_dir=tmp_path / ".claude-monkey")
    launcher = tmp_path / ".local" / "bin" / "claude.exe"
    launcher.parent.mkdir(parents=True)
    launcher.write_text("claude")

    found = discover_official_claude(
        config(), paths, {"USERPROFILE": str(tmp_path)}, lambda _: None
    )

    assert found is None
