from __future__ import annotations

import json

from claude_monkey.install import install_shim_transaction, restore_install_transaction


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
    assert target.read_text() == "official"
