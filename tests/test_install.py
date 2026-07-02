from __future__ import annotations

import json
from pathlib import Path

from claude_monkey.install import (
    install_shim_transaction,
    restore_install_transaction,
    use_official,
)
from claude_monkey.shim import render_shim_script


def test_install_records_previous_symlink_and_owner(tmp_path):
    target = tmp_path / "claude"
    previous = tmp_path / "official"
    previous.write_text("official")
    target.symlink_to(previous)
    record = install_shim_transaction(target, tmp_path / "state", dry_run=False)
    assert target.exists()
    assert "ClaudeMonkey" in target.read_text()
    raw = json.loads(record.read_text())
    assert raw["targetPath"] == str(target)
    assert raw["previousType"] == "symlink"


def test_restore_refuses_without_record(tmp_path):
    target = tmp_path / "claude"
    target.write_text(render_shim_script(str(tmp_path / "state")))
    assert restore_install_transaction(target, tmp_path / "missing.json", force=False) is False


def test_use_official_points_current_symlink(tmp_path):
    current = tmp_path / "current"
    official = tmp_path / "official"
    official.write_text("official")
    use_official(current, official)
    assert current.resolve() == official.resolve()


def test_restore_preserves_binary_file_bytes_and_mode(tmp_path):
    target = tmp_path / "claude"
    original = b"\xff\xfe\x00binary"
    target.write_bytes(original)
    target.chmod(0o755)
    record = install_shim_transaction(target, tmp_path / "state", dry_run=False)
    assert restore_install_transaction(target, record, force=False) is True
    assert target.read_bytes() == original
    assert target.stat().st_mode & 0o777 == 0o755


def test_restore_refuses_if_current_target_is_not_managed_shim(tmp_path):
    target = tmp_path / "claude"
    target.write_text("official")
    record = install_shim_transaction(target, tmp_path / "state", dry_run=False)
    target.write_text("someone else changed this")
    assert restore_install_transaction(target, record, force=False) is False
    assert target.read_text() == "someone else changed this"


def test_restore_file_record_does_not_follow_current_symlink(tmp_path):
    target = tmp_path / "claude"
    linked = tmp_path / "official"
    linked.write_bytes(b"official")
    target.write_bytes(b"previous")
    record = install_shim_transaction(target, tmp_path / "state", dry_run=False)
    target.unlink()
    target.symlink_to(linked)
    assert restore_install_transaction(target, record, force=True) is True
    assert linked.read_bytes() == b"official"
    assert target.read_bytes() == b"previous"
    assert not target.is_symlink()


def test_restore_refuses_record_for_different_target(tmp_path):
    target = tmp_path / "claude"
    other = tmp_path / "other-claude"
    target.write_text("official")
    record = install_shim_transaction(target, tmp_path / "state", dry_run=False)
    assert restore_install_transaction(other, record, force=False) is False


def test_dry_run_does_not_write_record_or_state(tmp_path):
    target = tmp_path / "claude"
    target.write_text("official")
    record = install_shim_transaction(target, tmp_path / "state", dry_run=True)
    assert record == tmp_path / "state" / "install-record.json"
    assert not record.exists()
    assert not (tmp_path / "state").exists()
    assert target.read_text() == "official"


def test_install_writes_record_before_replacing_target(tmp_path, monkeypatch):
    target = tmp_path / "claude"
    target.write_text("official")
    calls = []
    real_replace = Path.replace

    def tracking_replace(self, target_path):
        calls.append((self, target_path, (tmp_path / "state" / "install-record.json").exists()))
        return real_replace(self, target_path)

    monkeypatch.setattr(Path, "replace", tracking_replace)
    install_shim_transaction(target, tmp_path / "state", dry_run=False)
    assert calls
    assert calls[0][2] is True
