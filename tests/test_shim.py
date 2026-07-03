from __future__ import annotations

from claude_monkey.shim import render_shim_script


def test_shim_script_bootstraps_canonical_entrypoint():
    script = render_shim_script("/tmp/state")
    assert "from claude_monkey.shim_entry import main" in script
    assert 'main("/tmp/state")' in script
    assert "shell=True" not in script


def test_shim_script_does_not_embed_legacy_prompt_merge_logic():
    script = render_shim_script("/tmp/state")
    assert "active_prompt_args" not in script
    assert "PROMPT_FLAGS" not in script
    assert "CONFIG.read_text" not in script
