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


def test_fresh_status_json_is_not_installed(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert main(["status", "--json"]) == 0
    payload = parse_json_output(capsys)
    assert payload["status"] == "not_installed"
    assert payload["currentClaudePath"] is None
    assert payload["latestBuildReportPath"] is None


def test_build_json_preflight_failure_is_error_envelope(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    missing = tmp_path / "missing-claude"
    assert main(["build", "--source", str(missing), "--json"]) == 2
    payload = parse_json_output(capsys)
    assert payload["schemaVersion"] == 1
    assert payload["ok"] is False
    assert payload["status"] == "error"
    assert payload["error"]["message"] == f"source does not exist: {missing}"


def test_build_json_success_uses_command_envelope_schema(monkeypatch, tmp_path, capsys):
    from claude_monkey.reports_v2 import BuildReportV2

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    source = tmp_path / "claude"
    source.write_text("source")
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "patch.json").write_text("{}")

    def fake_build(request):
        request.output_dir.mkdir(parents=True, exist_ok=True)
        report = BuildReportV2(
            status="verified",
            automatedStatus="passed",
            sourceClaudePath=str(source),
            sourceVersion="fixture",
            sourceVersionOutput="fixture (Claude Code)",
            activationEligible=True,
            activationStatus="activated",
        )
        report.outputPath = str(request.output_dir / "claude")
        return report

    monkeypatch.setattr("claude_monkey.cli.build_patchset_v15", fake_build)
    assert (
        main(
            [
                "build",
                "--source",
                str(source),
                "--package",
                str(package),
                "--output-dir",
                str(tmp_path / "out"),
                "--source-version",
                "fixture",
                "--source-version-output",
                "fixture (Claude Code)",
                "--json",
            ]
        )
        == 0
    )
    payload = parse_json_output(capsys)
    assert payload["schemaVersion"] == 1
    assert payload["ok"] is True
    assert payload["summary"] == "Build activated"
    assert payload["error"] is None
    assert payload["reportPath"] == str(tmp_path / "out" / "build-report.json")


def test_status_ignores_stale_install_record(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    state = tmp_path / ".claude-monkey"
    state.mkdir()
    (state / "install-record.json").write_text(
        json.dumps(
            {
                "owner": "ClaudeMonkey managed shim",
                "targetPath": str(tmp_path / "missing-claude"),
                "installedShimSha256": "abc",
            }
        )
    )
    assert main(["status", "--json"]) == 0
    payload = parse_json_output(capsys)
    assert payload["shimInstalled"] is False
    assert payload["status"] == "not_installed"


def test_install_auth_failure_human_cli_uses_stderr(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / "protected" / "claude"

    def fake_install(*args, **kwargs):
        from claude_monkey.authorization import AuthorizationDenied

        raise AuthorizationDenied("denied", method="macos_gui")

    monkeypatch.setattr("claude_monkey.cli.install_shim_transaction", fake_install)
    assert main(["install-shim", "--target", str(target)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "denied" in captured.err


def test_install_json_success_reports_authorization_metadata(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / "protected" / "claude"

    monkeypatch.setattr("claude_monkey.cli.target_needs_authorization", lambda path: True)
    monkeypatch.setattr(
        "claude_monkey.cli.authorization_method_for_target", lambda path: "macos_gui"
    )

    def fake_install(target_path, state_dir, dry_run):
        return state_dir / "install-record.json"

    monkeypatch.setattr("claude_monkey.cli.install_shim_transaction", fake_install)
    assert main(["install-shim", "--target", str(target), "--json"]) == 0
    payload = parse_json_output(capsys)
    assert payload["authorizationRequired"] is True
    assert payload["authorizationMethod"] == "macos_gui"
    assert payload["targetPath"] == str(target)


def test_malformed_uninstall_record_json_returns_envelope(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    record = tmp_path / "bad-record.json"
    record.write_text("{bad json")
    assert main(["uninstall-shim", "--record", str(record), "--json"]) == 2
    payload = parse_json_output(capsys)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "invalid_record"


def test_manual_smoke_pending_json_summary_does_not_claim_activation(monkeypatch, tmp_path, capsys):
    from claude_monkey.reports_v2 import BuildReportV2

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    source = tmp_path / "claude"
    source.write_text("source")
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "patch.json").write_text("{}")

    def fake_build(request):
        request.output_dir.mkdir(parents=True, exist_ok=True)
        return BuildReportV2(
            status="manual_smoke_pending",
            automatedStatus="passed",
            sourceClaudePath=str(source),
            sourceVersion="fixture",
            sourceVersionOutput="fixture (Claude Code)",
            activationEligible=False,
            activationBlockers=["manual_smoke_pending"],
        )

    monkeypatch.setattr("claude_monkey.cli.build_patchset_v15", fake_build)
    assert (
        main(
            [
                "build",
                "--source",
                str(source),
                "--package",
                str(package),
                "--output-dir",
                str(tmp_path / "out"),
                "--source-version",
                "fixture",
                "--source-version-output",
                "fixture (Claude Code)",
                "--json",
            ]
        )
        == 0
    )
    payload = parse_json_output(capsys)
    assert payload["ok"] is True
    assert payload["summary"] == "Build requires manual smoke before activation"


def test_status_with_report_but_no_current_is_not_ok(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    report_dir = tmp_path / ".claude-monkey" / "patchsets" / "fixture" / "default"
    report_dir.mkdir(parents=True)
    (report_dir / "build-report.json").write_text(
        json.dumps({"schemaVersion": 2, "status": "verified", "enabledPatches": []})
    )
    config = tmp_path / ".claude-monkey" / "config.json"
    config.write_text(
        json.dumps(
            {
                "activeProfile": "default",
                "profiles": {"default": {"enabledPatches": []}},
                "activePatchSet": str(report_dir),
            }
        )
    )
    assert main(["status", "--json"]) == 0
    payload = parse_json_output(capsys)
    assert payload["currentClaudePath"] is None
    assert payload["shimInstalled"] is False
    assert payload["status"] == "not_installed"


def test_status_ignores_install_record_target_directory(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    target_dir = tmp_path / "target-dir"
    target_dir.mkdir()
    state = tmp_path / ".claude-monkey"
    state.mkdir()
    (state / "install-record.json").write_text(
        json.dumps(
            {
                "owner": "ClaudeMonkey managed shim",
                "targetPath": str(target_dir),
                "installedShimSha256": "abc",
            }
        )
    )
    assert main(["status", "--json"]) == 0
    payload = parse_json_output(capsys)
    assert payload["shimInstalled"] is False
    assert payload["status"] == "not_installed"


def test_verified_build_without_activation_does_not_claim_activation(monkeypatch, tmp_path, capsys):
    from claude_monkey.reports_v2 import BuildReportV2

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    source = tmp_path / "claude"
    source.write_text("source")
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "patch.json").write_text("{}")

    def fake_build(request):
        request.output_dir.mkdir(parents=True, exist_ok=True)
        return BuildReportV2(
            status="verified",
            automatedStatus="passed",
            sourceClaudePath=str(source),
            sourceVersion="fixture",
            sourceVersionOutput="fixture (Claude Code)",
            activationEligible=True,
            activationStatus="skipped",
        )

    monkeypatch.setattr("claude_monkey.cli.build_patchset_v15", fake_build)
    assert main(
        [
            "build",
            "--source",
            str(source),
            "--package",
            str(package),
            "--output-dir",
            str(tmp_path / "out"),
            "--source-version",
            "fixture",
            "--source-version-output",
            "fixture (Claude Code)",
            "--json",
        ]
    ) == 0
    payload = parse_json_output(capsys)
    assert payload["summary"] == "Build verified; activation not performed"


def test_installed_shim_without_current_is_rebuild_required_not_ok(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".claude-monkey" / "bin" / "claude"
    assert main(["install-shim", "--target", str(target), "--json"]) == 0
    parse_json_output(capsys)

    assert main(["status", "--json"]) == 0
    payload = parse_json_output(capsys)
    assert payload["shimInstalled"] is True
    assert payload["currentClaudePath"] is None
    assert payload["status"] == "rebuild_required"


def test_status_requires_current_to_resolve_to_executable(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    state = tmp_path / ".claude-monkey"
    state.mkdir()
    (state / "current").symlink_to(tmp_path / "missing")
    assert main(["status", "--json"]) == 0
    payload = parse_json_output(capsys)
    assert payload["currentClaudePath"] is None
    assert payload["status"] == "not_installed"

    (state / "current").unlink()
    non_executable = tmp_path / "claude"
    non_executable.write_text("not executable")
    (state / "current").symlink_to(non_executable)
    assert main(["status", "--json"]) == 0
    payload = parse_json_output(capsys)
    assert payload["currentClaudePath"] is None
    assert payload["status"] == "not_installed"


def test_verified_build_without_activation_does_not_persist_active_patchset(
    monkeypatch, tmp_path, capsys
):
    from claude_monkey.reports_v2 import BuildReportV2

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    source = tmp_path / "claude"
    source.write_text("source")
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "patch.json").write_text("{}")

    def fake_build(request):
        request.output_dir.mkdir(parents=True, exist_ok=True)
        return BuildReportV2(
            status="verified",
            automatedStatus="passed",
            sourceClaudePath=str(source),
            sourceVersion="fixture",
            sourceVersionOutput="fixture (Claude Code)",
            activationEligible=True,
            activationStatus="skipped",
            enabledPatches=[],
        )

    monkeypatch.setattr("claude_monkey.cli.build_patchset_v15", fake_build)
    assert main(
        [
            "build",
            "--source",
            str(source),
            "--package",
            str(package),
            "--output-dir",
            str(tmp_path / "out"),
            "--source-version",
            "fixture",
            "--source-version-output",
            "fixture (Claude Code)",
            "--json",
        ]
    ) == 0
    parse_json_output(capsys)
    config_path = tmp_path / "home" / ".claude-monkey" / "config.json"
    if config_path.exists():
        assert json.loads(config_path.read_text()).get("activePatchSet") is None


def test_status_does_not_trust_forged_install_record_digest(monkeypatch, tmp_path, capsys):
    import hashlib

    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / "claude"
    target.write_text("not a claude monkey shim")
    state = tmp_path / ".claude-monkey"
    state.mkdir()
    (state / "install-record.json").write_text(
        json.dumps(
            {
                "owner": "ClaudeMonkey managed shim",
                "targetPath": str(target),
                "stateDir": str(state),
                "installedShimSha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            }
        )
    )
    assert main(["status", "--json"]) == 0
    payload = parse_json_output(capsys)
    assert payload["shimInstalled"] is False
    assert payload["status"] == "not_installed"


def test_status_in_shim_mode_requires_installed_shim(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    current_target = tmp_path / "claude"
    current_target.write_text("#!/bin/sh\nexit 0\n")
    current_target.chmod(0o755)
    state = tmp_path / ".claude-monkey"
    state.mkdir()
    (state / "current").symlink_to(current_target)
    assert main(["status", "--json"]) == 0
    payload = parse_json_output(capsys)
    assert payload["currentClaudePath"] == str(current_target)
    assert payload["shimInstalled"] is False
    assert payload["status"] == "not_installed"


def test_set_prompt_missing_file_json_returns_envelope(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    missing = tmp_path / "missing.md"
    assert main(["set-prompt", str(missing), "--from-file", "--json"]) == 2
    payload = parse_json_output(capsys)
    assert payload["ok"] is False
    assert payload["error"]["code"] == "missing_prompt_file"
