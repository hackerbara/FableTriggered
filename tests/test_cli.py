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
