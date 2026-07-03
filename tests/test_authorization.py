from __future__ import annotations

import base64
import json

from claude_monkey.install import (
    ProtectedTargetRestoreUnavailable,
    install_shim_transaction,
    restore_install_transaction,
)


def test_protected_install_uses_narrow_authorized_file_operation(monkeypatch, tmp_path):
    calls = []
    target = tmp_path / "protected" / "claude"
    state = tmp_path / "state"

    monkeypatch.setattr(
        "claude_monkey.install.authorization.target_needs_authorization", lambda path: True
    )

    def fake_privileged(argv, *, reason):
        calls.append((argv, reason))
        if argv[0].endswith("mkdir"):
            target.parent.mkdir(parents=True, exist_ok=True)
        elif argv[0].endswith("mv"):
            src = argv[-2]
            dst = argv[-1]
            target.parent.mkdir(parents=True, exist_ok=True)
            __import__("shutil").move(src, dst)

    monkeypatch.setattr("claude_monkey.install.authorization.run_privileged_argv", fake_privileged)

    record = install_shim_transaction(target, state, dry_run=False)

    assert calls
    assert target.exists()
    assert "ClaudeMonkey" in target.read_text()
    assert json.loads(record.read_text())["targetPath"] == str(target)


def test_protected_install_refuses_existing_non_managed_target(monkeypatch, tmp_path):
    target = tmp_path / "protected" / "claude"
    target.parent.mkdir()
    target.write_text("official")
    state = tmp_path / "state"

    monkeypatch.setattr(
        "claude_monkey.install.authorization.target_needs_authorization", lambda path: True
    )

    try:
        install_shim_transaction(target, state, dry_run=False)
    except ProtectedTargetRestoreUnavailable as exc:
        assert str(target) in str(exc)
    else:
        raise AssertionError("expected protected overwrite refusal")

    assert target.read_text() == "official"
    assert not (state / "install-record.json").exists()


def test_protected_restore_uses_narrow_authorized_file_operation(monkeypatch, tmp_path):
    target = tmp_path / "protected" / "claude"
    target.parent.mkdir()
    target.write_text("official")
    state = tmp_path / "state"
    record = install_shim_transaction(target, state, dry_run=False)
    calls = []

    monkeypatch.setattr(
        "claude_monkey.install.authorization.target_needs_authorization", lambda path: True
    )

    def fake_privileged(argv, *, reason):
        calls.append((argv, reason))
        if argv[0].endswith("rm"):
            target.unlink(missing_ok=True)
        elif argv[0].endswith("mv"):
            __import__("shutil").move(argv[-2], argv[-1])

    monkeypatch.setattr("claude_monkey.install.authorization.run_privileged_argv", fake_privileged)

    assert restore_install_transaction(target, record, force=False) is True
    assert calls
    assert not target.exists()


def test_protected_restore_does_not_trust_tampered_record_payload(monkeypatch, tmp_path):
    target = tmp_path / "protected" / "claude"
    target.parent.mkdir()
    target.write_text("official")
    state = tmp_path / "state"
    record = install_shim_transaction(target, state, dry_run=False)
    raw = json.loads(record.read_text())
    raw["previousContentBase64"] = base64.b64encode(b"attacker payload").decode("ascii")
    raw["previousMode"] = 0o777
    record.write_text(json.dumps(raw, indent=2, sort_keys=True) + "\n")

    monkeypatch.setattr(
        "claude_monkey.install.authorization.target_needs_authorization", lambda path: True
    )

    calls = []

    def fake_privileged(argv, *, reason):
        calls.append((argv, reason))
        if argv[0].endswith("rm"):
            target.unlink(missing_ok=True)
        elif argv[0].endswith("mv"):
            raise AssertionError("protected restore must not mv record-controlled payload")

    monkeypatch.setattr("claude_monkey.install.authorization.run_privileged_argv", fake_privileged)

    assert restore_install_transaction(target, record, force=False) is True
    assert calls
    assert not target.exists()


def test_osascript_uses_valid_double_quoted_shell_script(monkeypatch):
    calls = []

    class Result:
        returncode = 0
        stdout = ""
        stderr = ""

    monkeypatch.setattr("claude_monkey.authorization.Path.exists", lambda self: True)

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        return Result()

    monkeypatch.setattr("claude_monkey.authorization.subprocess.run", fake_run)

    from claude_monkey.authorization import run_privileged_argv

    run_privileged_argv(["/bin/echo", "hi"], reason="test")
    script = calls[0][0][2]
    assert script.startswith('do shell script "')
    assert script.endswith('" with administrator privileges')
    assert "/bin/echo hi" in script


def test_failed_protected_install_cleans_record_and_temp(monkeypatch, tmp_path):
    target = tmp_path / "protected" / "claude"
    state = tmp_path / "state"

    monkeypatch.setattr(
        "claude_monkey.install.authorization.target_needs_authorization", lambda path: True
    )

    def fake_privileged(argv, *, reason):
        if argv[0].endswith("mv"):
            from claude_monkey.authorization import AuthorizationDenied

            raise AuthorizationDenied("denied", method="macos_gui")
        target.parent.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        "claude_monkey.install.authorization.run_privileged_argv", fake_privileged
    )

    from claude_monkey.authorization import AuthorizationDenied

    try:
        install_shim_transaction(target, state, dry_run=False)
    except AuthorizationDenied:
        pass
    else:
        raise AssertionError("expected authorization denial")

    assert not (state / "install-record.json").exists()
    assert not (state / "claude.claude-monkey.tmp").exists()
    assert not target.exists()


def test_protected_restore_keeps_current_target_if_replacement_fails(monkeypatch, tmp_path):
    target = tmp_path / "protected" / "claude"
    target.parent.mkdir()
    target.write_text("official")
    state = tmp_path / "state"
    record = install_shim_transaction(target, state, dry_run=False)
    target.write_text("managed shim replacement")

    monkeypatch.setattr(
        "claude_monkey.install.current_target_is_installed_shim", lambda path, record: True
    )
    monkeypatch.setattr(
        "claude_monkey.install.authorization.target_needs_authorization", lambda path: True
    )

    def fake_privileged(argv, *, reason):
        from claude_monkey.authorization import AuthorizationDenied

        raise AuthorizationDenied("denied", method="macos_gui")

    monkeypatch.setattr(
        "claude_monkey.install.authorization.run_privileged_argv", fake_privileged
    )

    from claude_monkey.authorization import AuthorizationDenied

    try:
        restore_install_transaction(target, record, force=False)
    except AuthorizationDenied:
        pass
    else:
        raise AssertionError("expected authorization denial")

    assert target.read_text() == "managed shim replacement"


def test_protected_restore_cleans_temp_if_replacement_fails(monkeypatch, tmp_path):
    target = tmp_path / "protected" / "claude"
    target.parent.mkdir()
    target.write_text("official")
    state = tmp_path / "state"
    record = install_shim_transaction(target, state, dry_run=False)
    target.write_text("managed shim replacement")

    monkeypatch.setattr(
        "claude_monkey.install.current_target_is_installed_shim", lambda path, record: True
    )
    monkeypatch.setattr(
        "claude_monkey.install.authorization.target_needs_authorization", lambda path: True
    )

    def fake_privileged(argv, *, reason):
        from claude_monkey.authorization import AuthorizationDenied

        raise AuthorizationDenied("denied", method="macos_gui")

    monkeypatch.setattr(
        "claude_monkey.install.authorization.run_privileged_argv", fake_privileged
    )

    from claude_monkey.authorization import AuthorizationDenied

    try:
        restore_install_transaction(target, record, force=False)
    except AuthorizationDenied:
        pass
    else:
        raise AssertionError("expected authorization denial")

    assert not (state / "claude.restore.tmp").exists()
