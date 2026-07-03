from __future__ import annotations

import json

from claude_monkey.cli import main


def parse_json_output(capsys):
    out = capsys.readouterr().out
    return json.loads(out)


def test_status_json_contract(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert main(["status", "--json"]) == 0
    payload = parse_json_output(capsys)
    assert payload["schemaVersion"] == 1
    assert payload["status"] in {"ok", "rebuild_required", "error", "not_installed", "unknown"}
    assert payload["stateDir"].endswith(".claude-monkey")
    assert payload["logsDir"].endswith(".claude-monkey/logs")
    assert isinstance(payload["desiredPatchIds"], list)
    assert isinstance(payload["activePatchIds"], list)
    assert "rebuildRequired" in payload
    assert payload["lastError"] is None or "message" in payload["lastError"]


def test_mutating_command_json_envelope(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert main(["enable", "fable-fallback", "--json"]) == 0
    payload = parse_json_output(capsys)
    assert payload["schemaVersion"] == 1
    assert payload["ok"] is True
    assert payload["status"] in {"ok", "rebuild_required"}
    assert payload["summary"] == "enabled fable-fallback; rebuild required"
    assert payload["reportPath"] is None
    assert payload["targetPath"] is None
    assert payload["authorizationRequired"] is False
    assert payload["authorizationMethod"] is None
    assert payload["dryRun"] is False
    assert payload["plannedActions"] == []
    assert payload["error"] is None


def test_dry_run_envelope(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".claude-monkey" / "bin" / "claude"
    assert main(["install-shim", "--target", str(target), "--json", "--dry-run"]) == 0
    payload = parse_json_output(capsys)
    assert payload["ok"] is True
    assert payload["dryRun"] is True
    assert payload["targetPath"] == str(target)
    assert "authorizationRequired" in payload
    assert isinstance(payload["plannedActions"], list)
    assert payload["error"] is None


def test_real_install_uninstall_json_wraps_cli_core_transaction(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".claude-monkey" / "bin" / "claude"
    # Current install_shim_transaction does not require a built current symlink;
    # this is a real disposable user-writable install path.
    assert main(["install-shim", "--target", str(target), "--json"]) == 0
    install_payload = parse_json_output(capsys)
    assert install_payload["ok"] is True
    assert install_payload["dryRun"] is False
    assert install_payload["targetPath"] == str(target)

    assert main(["uninstall-shim", "--target", str(target), "--json"]) == 0
    uninstall_payload = parse_json_output(capsys)
    assert uninstall_payload["ok"] is True
    assert uninstall_payload["dryRun"] is False
    assert uninstall_payload["targetPath"] == str(target)
