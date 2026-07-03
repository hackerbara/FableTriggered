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
    assert paths.patchset_dir("2.1.199", "default") == (
        paths.state_dir / "versions" / "2.1.199" / "patchsets" / "default"
    )


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


def test_v3_config_rejects_non_default_active_profile(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(
        '{"schemaVersion":1,"activeProfile":"custom","profiles":{"default":{"prompt":null,"patches":[],"options":[]}}}'
    )
    try:
        load_config(path)
    except ValueError as exc:
        assert "active_profile_must_be_default" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_active_profile_never_creates_non_default_profile():
    from claude_monkey.cli import active_profile

    config = ClaudeMonkeyConfig(
        activeProfile="custom",
        profiles={"default": LaunchProfile(patches=["fable-fallback"])},
    )

    profile = active_profile(config)

    assert profile is config.profiles["default"]
    assert profile.patches == ["fable-fallback"]
    assert set(config.profiles) == {"default"}
