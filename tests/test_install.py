from __future__ import annotations

import json

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
