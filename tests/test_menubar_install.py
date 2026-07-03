from __future__ import annotations

from pathlib import Path

from claude_monkey.menubar_install import install_plan_for_target, managed_user_target


def test_managed_user_target_is_under_state_bin(tmp_path):
    target = managed_user_target(tmp_path / ".claude-monkey")
    assert target == tmp_path / ".claude-monkey" / "bin" / "claude"


def test_user_writable_target_needs_no_authorization(tmp_path):
    target = tmp_path / ".claude-monkey" / "bin" / "claude"
    plan = install_plan_for_target(target, state_dir=tmp_path / ".claude-monkey")
    assert plan.target == target
    assert plan.authorization_required is False
    assert plan.authorization_reason is None


def test_protected_target_requires_narrow_authorization():
    target = Path("/usr/local/bin/claude")
    plan = install_plan_for_target(target, state_dir=Path("/tmp/state"))
    assert plan.authorization_required is True
    assert "protected" in (plan.authorization_reason or "")
