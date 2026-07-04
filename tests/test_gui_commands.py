"""Table-driven tests for pure argv builder functions in claude_monkey.gui.commands.

These builders map GUI intents to CLI argv lists. They must never include a
`claude-monkey` prefix (CommandRunner adds that separately) and must never
import Qt/PySide6.
"""

from __future__ import annotations

from pathlib import Path

from claude_monkey.gui import commands

# ---------------------------------------------------------------------------
# 1. command_for_patch_toggle
# ---------------------------------------------------------------------------


def test_patch_toggle_enabled_true_produces_disable():
    # enabled=True means the patch is CURRENTLY on, so the action is to
    # disable it. This direction is easy to invert accidentally.
    assert commands.command_for_patch_toggle("p", enabled=True) == [
        "disable-patch",
        "p",
        "--json",
    ]


def test_patch_toggle_enabled_false_produces_enable():
    assert commands.command_for_patch_toggle("p", enabled=False) == [
        "enable-patch",
        "p",
        "--json",
    ]


# ---------------------------------------------------------------------------
# 2. command_for_option_toggle
# ---------------------------------------------------------------------------


def test_option_toggle_enable_with_confirm():
    # --confirm must come BEFORE --json.
    assert commands.command_for_option_toggle("o", enabled=False, confirm=True) == [
        "enable-option",
        "o",
        "--confirm",
        "--json",
    ]


def test_option_toggle_enable_without_confirm():
    assert commands.command_for_option_toggle("o", enabled=False, confirm=False) == [
        "enable-option",
        "o",
        "--json",
    ]


def test_option_toggle_enable_default_confirm_is_false():
    assert commands.command_for_option_toggle("o", enabled=False) == [
        "enable-option",
        "o",
        "--json",
    ]


def test_option_toggle_disable_ignores_confirm_true():
    assert commands.command_for_option_toggle("o", enabled=True, confirm=True) == [
        "disable-option",
        "o",
        "--json",
    ]


def test_option_toggle_disable_ignores_confirm_false():
    assert commands.command_for_option_toggle("o", enabled=True, confirm=False) == [
        "disable-option",
        "o",
        "--json",
    ]


# ---------------------------------------------------------------------------
# 3. command_for_prompt
# ---------------------------------------------------------------------------


def test_prompt_with_id():
    result = commands.command_for_prompt("my-prompt")
    assert result == ["set-prompt", "my-prompt", "--json"]
    # Sanity: no file-path style flags should ever appear here.
    assert "--from-file" not in result


def test_prompt_with_none():
    result = commands.command_for_prompt(None)
    assert result == ["clear-prompt", "--json"]
    assert "--from-file" not in result


# ---------------------------------------------------------------------------
# 4. command_for_rebuild_apply
# ---------------------------------------------------------------------------


def test_rebuild_apply_takes_no_args_and_is_exact():
    assert commands.command_for_rebuild_apply() == [
        "build",
        "--json",
        "--activate",
        "--progress",
    ]


# ---------------------------------------------------------------------------
# 5. command_for_install_shim
# ---------------------------------------------------------------------------


def test_install_shim_dry_run_excludes_progress_str_target():
    result = commands.command_for_install_shim("/tmp/target", dry_run=True)
    assert result == ["install-shim", "/tmp/target", "--dry-run"]
    assert "--progress" not in result


def test_install_shim_dry_run_excludes_progress_path_target():
    result = commands.command_for_install_shim(Path("/tmp/target"), dry_run=True)
    assert result == ["install-shim", "/tmp/target", "--dry-run"]
    assert "--progress" not in result


def test_install_shim_real_run_includes_progress_excludes_dry_run():
    result = commands.command_for_install_shim(Path("/tmp/target"), dry_run=False)
    assert result == ["install-shim", "/tmp/target", "--progress"]
    assert "--dry-run" not in result


def test_install_shim_default_dry_run_is_false():
    result = commands.command_for_install_shim("/tmp/target")
    assert result == ["install-shim", "/tmp/target", "--progress"]


# ---------------------------------------------------------------------------
# 6. command_for_uninstall_shim
# ---------------------------------------------------------------------------


def test_uninstall_shim_no_args():
    assert commands.command_for_uninstall_shim() == ["uninstall-shim", "--progress"]


def test_uninstall_shim_target_only_dry_run_str():
    assert commands.command_for_uninstall_shim(target="/x", dry_run=True) == [
        "uninstall-shim",
        "--target",
        "/x",
        "--dry-run",
    ]


def test_uninstall_shim_target_only_path():
    result = commands.command_for_uninstall_shim(target=Path("/x"), dry_run=True)
    assert result == ["uninstall-shim", "--target", "/x", "--dry-run"]


def test_uninstall_shim_record_only_progress():
    assert commands.command_for_uninstall_shim(record="/r") == [
        "uninstall-shim",
        "--record",
        "/r",
        "--progress",
    ]


def test_uninstall_shim_record_only_path_dry_run():
    result = commands.command_for_uninstall_shim(record=Path("/r"), dry_run=True)
    assert result == ["uninstall-shim", "--record", "/r", "--dry-run"]


def test_uninstall_shim_target_takes_precedence_over_record():
    result = commands.command_for_uninstall_shim(target="/x", record="/r")
    assert result == ["uninstall-shim", "--target", "/x", "--progress"]


# ---------------------------------------------------------------------------
# 7. command_for_add_package
# ---------------------------------------------------------------------------


def test_add_package_patch():
    assert commands.command_for_add_package("/dir/patch", "patch") == [
        "add-patch",
        "/dir/patch",
        "--json",
    ]


def test_add_package_option():
    assert commands.command_for_add_package("/dir/option", "option") == [
        "add-option",
        "/dir/option",
        "--json",
    ]


def test_add_package_accepts_path():
    assert commands.command_for_add_package(Path("/dir/patch"), "patch") == [
        "add-patch",
        "/dir/patch",
        "--json",
    ]


# ---------------------------------------------------------------------------
# 8. command_for_remove_package
# ---------------------------------------------------------------------------


def test_remove_package_patch():
    assert commands.command_for_remove_package("p-id", "patch") == [
        "remove-patch",
        "p-id",
        "--json",
    ]


def test_remove_package_option():
    assert commands.command_for_remove_package("o-id", "option") == [
        "remove-option",
        "o-id",
        "--json",
    ]


def test_remove_package_prompt():
    assert commands.command_for_remove_package("pr-id", "prompt") == [
        "remove-prompt",
        "pr-id",
        "--json",
    ]


# ---------------------------------------------------------------------------
# 9. command_for_add_prompt_file
# ---------------------------------------------------------------------------


def test_add_prompt_file_without_name():
    result = commands.command_for_add_prompt_file(Path("/p/prompt.md"), "pkg-id")
    assert result == ["add-prompt", "/p/prompt.md", "--id", "pkg-id", "--json"]


def test_add_prompt_file_with_name():
    result = commands.command_for_add_prompt_file(
        Path("/p/prompt.md"), "pkg-id", name="My Prompt"
    )
    assert result == [
        "add-prompt",
        "/p/prompt.md",
        "--id",
        "pkg-id",
        "--name",
        "My Prompt",
        "--json",
    ]


def test_add_prompt_file_default_name_is_none():
    result = commands.command_for_add_prompt_file("/p/prompt.md", "pkg-id")
    assert result == ["add-prompt", "/p/prompt.md", "--id", "pkg-id", "--json"]
