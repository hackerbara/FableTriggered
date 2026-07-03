from __future__ import annotations

from pathlib import Path

from claude_monkey.menubar import (
    build_menu_labels,
    command_for_install_shim,
    command_for_install_shim_dry_run,
    command_for_patch_toggle,
    command_for_prompt,
    command_for_uninstall_shim,
    command_for_uninstall_shim_dry_run,
    default_install_target,
)
from claude_monkey.menubar_state import MenuState, PatchMenuItem, PromptMenuItem

ROOT = Path(__file__).resolve().parents[1]


def test_menubar_icon_asset_exists():
    icon = ROOT / "assets" / "claude-monkey-menubar-template.png"
    assert icon.exists()
    assert icon.stat().st_size > 0


def sample_state(tmp_path):
    return MenuState(
        status="rebuild_required",
        status_label="Rebuild Required",
        source_claude_version="2.1.198",
        source_claude_path=None,
        install_mode="shim",
        shim_installed=False,
        active_profile="default",
        active_prompt="research",
        desired_patch_ids=("fable-fallback",),
        active_patch_ids=(),
        rebuild_required=True,
        latest_build_report_path=None,
        active_patch_set=None,
        current_claude_path=None,
        shim_target_path=None,
        install_record_path=None,
        last_build_strategy="repack",
        changed_modules=(),
        repack_summary=None,
        state_dir=tmp_path,
        logs_dir=tmp_path / "logs",
        last_error=None,
        patch_items=(
            PatchMenuItem("fable-fallback", "Fable", True, False, True, "compatible"),
        ),
        prompt_items=(
            PromptMenuItem("research", "Research", True, "append", tmp_path / "research.md"),
        ),
    )


def test_build_menu_labels_contains_required_actions(tmp_path):
    labels = build_menu_labels(sample_state(tmp_path))
    assert "ClaudeMonkey: Rebuild Required" in labels
    assert "Open logs folder" in labels
    assert "Open state folder" in labels
    assert "Quit" in labels


def test_command_mapping_uses_json():
    assert command_for_patch_toggle("fable-fallback", enabled=True) == [
        "disable",
        "fable-fallback",
        "--json",
    ]
    assert command_for_patch_toggle("fable-fallback", enabled=False) == [
        "enable",
        "fable-fallback",
        "--json",
    ]
    target = default_install_target()
    prompt_path = target.parent / "research.md"
    assert command_for_prompt("research", prompt_path) == [
        "set-prompt",
        str(prompt_path),
        "--id",
        "research",
        "--from-file",
        "--json",
    ]
    assert command_for_prompt(None) == ["clear-prompt", "--json"]
    assert command_for_install_shim_dry_run(target) == [
        "install-shim",
        "--target",
        str(target),
        "--json",
        "--dry-run",
    ]
    assert command_for_install_shim(target) == [
        "install-shim",
        "--target",
        str(target),
        "--json",
    ]
    assert command_for_uninstall_shim_dry_run(target=target) == [
        "uninstall-shim",
        "--target",
        str(target),
        "--json",
        "--dry-run",
    ]
    assert command_for_uninstall_shim(target=target) == [
        "uninstall-shim",
        "--target",
        str(target),
        "--json",
    ]
    record = target.parent / "record.json"
    assert command_for_uninstall_shim(record=record) == [
        "uninstall-shim",
        "--record",
        str(record),
        "--json",
    ]
