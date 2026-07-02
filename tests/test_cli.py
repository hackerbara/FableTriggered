from __future__ import annotations

from claude_monkey.cli import main


def test_cli_version(capsys):
    assert main(["--version"]) == 0
    assert "0.1.0" in capsys.readouterr().out


def test_status_prints_state_dir(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert main(["status"]) == 0
    out = capsys.readouterr().out
    assert ".claude-monkey" in out


def test_enable_and_disable_patch_mutate_default_profile(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert main(["enable", "fable-fallback"]) == 0
    assert main(["disable", "fable-fallback"]) == 0


def test_high_impact_unimplemented_commands_return_nonzero(capsys):
    for command in ["build", "install-shim", "uninstall-shim", "rollback", "use-official"]:
        assert main([command]) == 2
    assert "not implemented" in capsys.readouterr().err


def test_enable_handles_missing_active_profile(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    config_path = tmp_path / ".claude-monkey" / "config.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text('{"activeProfile":"missing","profiles":{}}\n')
    assert main(["enable", "fable-fallback"]) == 0
