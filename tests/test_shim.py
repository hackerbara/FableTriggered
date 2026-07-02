from __future__ import annotations

from claude_monkey.shim import render_shim_script


def test_shim_script_uses_exec_and_bypass():
    script = render_shim_script("/tmp/state")
    assert "CLAUDE_MONKEY_BYPASS" in script
    assert "os.execv" in script
    assert "/tmp/state" in script
    assert "shell=True" not in script


def test_shim_script_detects_equals_prompt_flags():
    script = render_shim_script("/tmp/state")
    assert "startswith(flag + '=')" in script
