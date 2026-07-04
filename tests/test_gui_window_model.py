"""Tests for pure tray/window view-models in claude_monkey.gui.window_model.

These view-models decide everything the tray and window render; the Qt files
(later tasks) are thin renderers over them. This module must never import
Qt/PySide6 -- see test_window_model_has_no_qt_imports below.

Several assertions here are ported from tests/test_menubar_app_model.py
(the rumps-based v1/v2 menu bar), adapted to the new pure-function names and
MenuState-based API described in the ClaudeMonkey v3 GUI plan (Task 9):

- test_patch_menu_label_surfaces_incompatibility_message: ported verbatim
  from test_menubar_app_model.py's test of the same name (same PatchMenuItem
  shape, same expected label string).
- test_status_lines_report_status_and_high_risk_options: ported from
  test_build_menu_labels_contains_required_actions -- keeps the
  "ClaudeMonkey: Rebuild Required" and "Options: 1 active ⚠" assertion
  values, but narrowed to the status header (build_tray_model's
  status_lines), since actions like "Open logs folder"/"Quit"/"Refresh" are
  now owned by the Task 14 Tray renderer, not this pure model.
- test_default_install_target_prefers_detected_claude_command: ported
  verbatim (same fixture shape, same assertion).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from claude_monkey.gui import window_model
from claude_monkey.gui.window_model import (
    InstallTargetSelection,
    NoticeModel,
    build_notice_model,
    build_tray_model,
    compatibility_display,
    default_install_target,
    install_target_choices,
    option_item_enabled,
    patch_item_enabled,
    patch_menu_label,
    remove_enabled,
    repair_confirm_text,
    repair_refusal_display,
)
from claude_monkey.menubar_install import managed_user_target
from claude_monkey.menubar_state import MenuState, OptionMenuItem, PatchMenuItem, PromptMenuItem


def _state(tmp_path: Path, **overrides) -> MenuState:
    defaults = dict(
        status="rebuild_required",
        status_label="Rebuild Required",
        source_claude_version="2.1.198",
        source_claude_path=None,
        detected_claude_command_path=None,
        install_mode="shim",
        shim_installed=False,
        active_profile="default",
        active_prompt="research",
        desired_patch_ids=("p1",),
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
            PatchMenuItem("p1", "Fable", True, False, True, "compatible", None),
        ),
        prompt_items=(
            PromptMenuItem("research", "Research", True, "append", tmp_path / "research.md"),
        ),
        active_option_ids=("dangerous-permissions",),
        high_risk_warnings=("Dangerous permissions enabled",),
        option_items=(
            OptionMenuItem(
                "dangerous-permissions",
                "Dangerous permissions",
                True,
                True,
                "unconstrained",
                "high",
                True,
            ),
            OptionMenuItem(
                "local-proxy",
                "Local proxy",
                False,
                True,
                "unconstrained",
                "low",
            ),
        ),
    )
    defaults.update(overrides)
    return MenuState(**defaults)


@pytest.fixture
def state_without_shim(tmp_path: Path) -> MenuState:
    return _state(tmp_path, shim_installed=False)


@pytest.fixture
def state_with_shim(tmp_path: Path) -> MenuState:
    return _state(tmp_path, shim_installed=True)


# ---------------------------------------------------------------------------
# Purity enforcement
# ---------------------------------------------------------------------------


def test_window_model_has_no_qt_imports():
    assert "PySide6" not in Path(window_model.__file__).read_text()


# ---------------------------------------------------------------------------
# build_tray_model / TrayModel
# ---------------------------------------------------------------------------


def test_status_lines_report_status_and_high_risk_options(state_without_shim):
    model = build_tray_model(state_without_shim, None)

    assert "ClaudeMonkey: Rebuild Required" in model.status_lines
    assert "Options: 1 active ⚠" in model.status_lines


def test_tray_model_exposes_underlying_item_tuples(state_without_shim):
    model = build_tray_model(state_without_shim, None)

    assert model.prompt_items == state_without_shim.prompt_items
    assert model.patch_items == state_without_shim.patch_items
    assert model.option_items == state_without_shim.option_items


def test_tray_hides_install_shim_when_installed(state_with_shim, state_without_shim):
    assert build_tray_model(state_with_shim, None).show_install_shim is False
    assert build_tray_model(state_without_shim, None).show_install_shim is True


def test_busy_disables_mutating_and_shows_running(state_without_shim):
    model = build_tray_model(state_without_shim, "build")
    assert model.mutating_enabled is False
    assert model.running_label == "Running: build"


def test_not_busy_has_no_running_label(state_without_shim):
    model = build_tray_model(state_without_shim, None)
    assert model.mutating_enabled is True
    assert model.running_label is None


def test_none_state_yields_error_model():
    model = build_tray_model(None, None)
    assert model.mutating_enabled is False
    assert model.status_lines[0].startswith("ClaudeMonkey: Error")
    assert model.prompt_items == ()
    assert model.patch_items == ()
    assert model.option_items == ()


def test_tray_model_defaults_notice_to_none(state_without_shim):
    assert build_tray_model(state_without_shim, None).notice is None


def test_tray_model_carries_notice_through(state_without_shim):
    notice = NoticeModel(
        message="Claude 2.1.201 available — shim repair needed",
        digest="abcd",
        actions=("repair",),
    )
    model = build_tray_model(state_without_shim, None, notice=notice)
    assert model.notice is notice


# ---------------------------------------------------------------------------
# compatibility_display
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "status",
    ["compatible", "unknown", "unconstrained", "constrained"],
)
def test_compatibility_display_healthy_statuses_are_blank(status):
    # Internal jargon like "unconstrained" must never reach the UI -- a
    # healthy/neutral status shows nothing, letting the row speak for
    # itself via the package name alone. "constrained" means the manifest
    # merely *declares* a compatibility constraint -- it is not itself a
    # failure (those surface as "version_mismatch"/"sha_mismatch"), so it
    # belongs in the healthy/neutral bucket too.
    assert compatibility_display(status) == ""
    assert compatibility_display(status, "some message") == ""


@pytest.mark.parametrize(
    "status",
    ["version_mismatch", "sha_mismatch", "incompatible", "some_future_status"],
)
def test_compatibility_display_problem_status_uses_message_when_present(status):
    assert compatibility_display(status, "Human readable detail.") == "Human readable detail."


@pytest.mark.parametrize(
    "status",
    ["version_mismatch", "sha_mismatch", "incompatible", "some_future_status"],
)
def test_compatibility_display_problem_status_falls_back_without_message(status):
    # No raw status word (e.g. "sha_mismatch") may pass through verbatim
    # when the CLI didn't supply a message.
    display = compatibility_display(status)
    assert display != ""
    assert display != status
    assert display == "Not compatible with this Claude version"


def test_compatibility_display_blank_message_falls_back():
    display = compatibility_display("version_mismatch", "")
    assert display == "Not compatible with this Claude version"


# ---------------------------------------------------------------------------
# patch_menu_label / patch_item_enabled
# ---------------------------------------------------------------------------


def test_patch_menu_label_surfaces_incompatibility_message():
    patch = PatchMenuItem(
        "fable-fallback",
        "Fable",
        False,
        False,
        True,
        "version_mismatch",
        "Package targets Claude 2.1.198; current source is 2.1.199.",
    )

    assert (
        patch_menu_label(patch)
        == "Fable — Package targets Claude 2.1.198; current source is 2.1.199."
    )


def test_patch_menu_label_plain_when_compatible():
    patch = PatchMenuItem("p1", "Fable", True, True, True, "compatible", None)
    assert patch_menu_label(patch) == "Fable"


def test_patch_menu_label_unavailable_overrides_compatibility():
    patch = PatchMenuItem("p1", "Fable", False, False, False, "compatible", None)
    assert patch_menu_label(patch) == "Fable — unavailable"


def test_patch_menu_label_plain_when_unconstrained():
    patch = PatchMenuItem("p1", "Fable", False, False, True, "unconstrained", None)
    assert patch_menu_label(patch) == "Fable"


def test_patch_item_enabled_false_when_not_mutating():
    patch = PatchMenuItem("p1", "Fable", True, True, True, "compatible", None)
    assert patch_item_enabled(patch, mutating_enabled=False) is False


def test_patch_item_enabled_true_when_already_checked():
    patch = PatchMenuItem("p1", "Fable", True, False, True, "compatible", None)
    assert patch_item_enabled(patch, mutating_enabled=True) is True


def test_patch_item_enabled_false_when_unavailable_and_unchecked():
    patch = PatchMenuItem("p1", "Fable", False, False, False, "compatible", None)
    assert patch_item_enabled(patch, mutating_enabled=True) is False


def test_patch_item_enabled_false_when_incompatible_and_unchecked():
    patch = PatchMenuItem("p1", "Fable", False, False, True, "version_mismatch", "msg")
    assert patch_item_enabled(patch, mutating_enabled=True) is False


def test_patch_item_enabled_true_when_compatible_and_unchecked():
    patch = PatchMenuItem("p1", "Fable", False, False, True, "compatible", None)
    assert patch_item_enabled(patch, mutating_enabled=True) is True


def test_patch_item_enabled_true_when_unconstrained_and_unchecked():
    patch = PatchMenuItem("p1", "Fable", False, False, True, "unconstrained", None)
    assert patch_item_enabled(patch, mutating_enabled=True) is True


# ---------------------------------------------------------------------------
# option_item_enabled
# ---------------------------------------------------------------------------


def test_option_item_enabled_requires_mutating_and_valid():
    option = OptionMenuItem("o", "Option", False, True, "unconstrained", "low")
    assert option_item_enabled(option, mutating_enabled=True) is True
    assert option_item_enabled(option, mutating_enabled=False) is False


def test_option_item_enabled_false_when_invalid():
    option = OptionMenuItem("o", "Option", False, False, "unconstrained", "low")
    assert option_item_enabled(option, mutating_enabled=True) is False


def test_option_item_enabled_allows_high_risk_requiring_confirmation():
    # Enabling a requires_confirmation option is allowed here -- the confirm
    # dialog (owned by a later task) handles the actual gate.
    option = OptionMenuItem("o", "Option", False, True, "unconstrained", "high", True)
    assert option_item_enabled(option, mutating_enabled=True) is True


# ---------------------------------------------------------------------------
# default_install_target / install_target_choices
# ---------------------------------------------------------------------------


def test_default_install_target_prefers_detected_claude_command(tmp_path):
    state = _state(tmp_path)
    detected = tmp_path / ".local" / "bin" / "claude"
    state = MenuState(**{**state.__dict__, "detected_claude_command_path": detected})

    assert default_install_target(state) == detected


def test_default_install_target_prefers_shim_target_over_detected(tmp_path):
    state = _state(tmp_path)
    recorded = tmp_path / "recorded" / "claude"
    detected = tmp_path / ".local" / "bin" / "claude"
    state = MenuState(
        **{**state.__dict__, "shim_target_path": recorded, "detected_claude_command_path": detected}
    )

    assert default_install_target(state) == recorded


def test_default_install_target_falls_back_to_managed_user_target_without_state(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert default_install_target(None) == managed_user_target(tmp_path / ".claude-monkey")


def test_install_target_choices_starts_with_managed_user_target(tmp_path):
    state = _state(tmp_path)
    choices = install_target_choices(state)
    assert choices[0] == ("Use managed user target", managed_user_target(tmp_path))


def test_install_target_choices_includes_recorded_and_detected(tmp_path):
    recorded = tmp_path / "recorded" / "claude"
    detected = tmp_path / "detected" / "claude"
    state = _state(tmp_path, shim_target_path=recorded, detected_claude_command_path=detected)

    choices = install_target_choices(state)

    assert ("Use recorded target", recorded) in choices
    assert ("Use detected claude command", detected) in choices


def test_install_target_choices_deduplicates_paths(tmp_path):
    state = _state(tmp_path, shim_target_path=managed_user_target(tmp_path))

    choices = install_target_choices(state)

    targets = [target for _label, target in choices]
    assert len(targets) == len(set(targets))


def test_install_target_choices_none_state_uses_home_default(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    choices = install_target_choices(None)
    expected = managed_user_target(tmp_path / ".claude-monkey")
    assert choices[0] == ("Use managed user target", expected)


# ---------------------------------------------------------------------------
# InstallTargetSelection
# ---------------------------------------------------------------------------


def test_install_target_selection_defaults_until_user_selects(tmp_path):
    state = _state(tmp_path)
    selection = InstallTargetSelection()

    assert selection.user_selected is False
    assert selection.target(state) == default_install_target(state)

    custom = tmp_path / "custom" / "claude"
    selection.select(custom)

    assert selection.user_selected is True
    assert selection.target(state) == custom
    # Selection sticks even as state changes.
    other_state = _state(tmp_path, detected_claude_command_path=tmp_path / "other" / "claude")
    assert selection.target(other_state) == custom


def test_install_target_selection_expands_selected_path(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    selection = InstallTargetSelection()
    selection.select(Path("~/custom/claude"))

    assert selection.target(None) == tmp_path / "custom" / "claude"


# ---------------------------------------------------------------------------
# remove_enabled
# ---------------------------------------------------------------------------


def test_remove_enabled_reflects_profile(state_without_shim):
    ok, reason = remove_enabled("patch", "p1", state_without_shim)
    assert ok is False and "profile" in reason


def test_remove_enabled_allows_patch_not_referenced_by_profile(state_without_shim):
    ok, reason = remove_enabled("patch", "unrelated-patch", state_without_shim)
    assert ok is True
    assert reason == ""


def test_remove_enabled_ignores_baked_into_build_patches(state_without_shim):
    # A patch that is part of the currently-built/active binary but is NOT
    # in the active profile's desired set must not be blocked -- only
    # profile-reference blocks removal.
    state = MenuState(
        **{
            **state_without_shim.__dict__,
            "built_patch_ids": ("baked-patch",),
            "active_patch_ids": ("baked-patch",),
        }
    )

    ok, reason = remove_enabled("patch", "baked-patch", state)

    assert ok is True
    assert reason == ""


def test_remove_enabled_blocks_active_prompt(state_without_shim):
    ok, reason = remove_enabled("prompt", "research", state_without_shim)
    assert ok is False and "profile" in reason


def test_remove_enabled_allows_inactive_prompt(state_without_shim):
    ok, reason = remove_enabled("prompt", "other-prompt", state_without_shim)
    assert ok is True
    assert reason == ""


def test_remove_enabled_blocks_active_option(state_without_shim):
    ok, reason = remove_enabled("option", "dangerous-permissions", state_without_shim)
    assert ok is False and "profile" in reason


def test_remove_enabled_allows_inactive_option(state_without_shim):
    ok, reason = remove_enabled("option", "local-proxy", state_without_shim)
    assert ok is True
    assert reason == ""


# ---------------------------------------------------------------------------
# build_notice_model (shim-update-resilience GUI notice, spec sec4 + R2/R5/R7)
# ---------------------------------------------------------------------------


def _replaced_state(tmp_path: Path, **overrides) -> MenuState:
    defaults = dict(
        shim_installed=False,
        shim_previously_managed=True,
        target_replaced_by_official=True,
        detected_official_sha256="a0852d76afc47b30f5cb0b7625ec9a7714cb189f2eeef6c28c77e2be954fb7fd",
        detected_official_version="2.1.201",
        shim_repair_available=True,
        rollout_required=True,
    )
    defaults.update(overrides)
    return _state(tmp_path, **defaults)


def test_build_notice_model_none_when_no_replacement(tmp_path):
    state = _state(tmp_path)  # default fixture: no replacement fields set
    assert build_notice_model(state, frozenset()) is None


def test_build_notice_model_repair_needed_known_version(tmp_path):
    state = _replaced_state(tmp_path)

    notice = build_notice_model(state, frozenset())

    assert notice == NoticeModel(
        message="Claude 2.1.201 available — shim repair needed",
        digest="a0852d76afc47b30f5cb0b7625ec9a7714cb189f2eeef6c28c77e2be954fb7fd",
        actions=("repair",),
    )


def test_build_notice_model_repair_needed_unknown_version(tmp_path):
    state = _replaced_state(tmp_path, detected_official_version=None)

    notice = build_notice_model(state, frozenset())

    assert notice is not None
    assert notice.message == "New Claude build available (a0852d76…) — shim repair needed"
    assert notice.actions == ("repair",)


def test_build_notice_model_no_actions_when_repair_not_available(tmp_path):
    # targetReplacedByOfficial can in principle be True while
    # shimRepairAvailable is False (e.g. a still-installed shim per
    # status.py's own gating) -- the notice must never offer a "repair"
    # button it cannot back with a working action.
    state = _replaced_state(tmp_path, shim_repair_available=False)

    notice = build_notice_model(state, frozenset())

    assert notice is not None
    assert notice.actions == ()


def test_build_notice_model_post_repair_rollout(tmp_path):
    # Labeled state from the brief: shim reinstalled (shim_installed=True)
    # but rollout still required. Not reachable via the current, merged
    # status.py (see repair-3-report.md investigation) -- constructed
    # directly here to pin the label/actions contract for when that gap is
    # closed.
    state = _state(
        tmp_path,
        shim_installed=True,
        target_replaced_by_official=False,
        detected_official_sha256=None,
        detected_official_version="2.1.201",
        shim_repair_available=False,
        rollout_required=True,
    )

    notice = build_notice_model(state, frozenset())

    assert notice is not None
    assert notice.message == "Claude 2.1.201 available — rebuild to roll out"
    # No CLI-safe way to wire a rollout button today (rebuild does not
    # consume the repaired install record's cached source) -- informational
    # only. See report for the investigation.
    assert notice.actions == ()


def test_build_notice_model_dismissed_digest_suppresses(tmp_path):
    state = _replaced_state(tmp_path)
    dismissed = frozenset({state.detected_official_sha256})

    assert build_notice_model(state, dismissed) is None


def test_build_notice_model_new_digest_re_raises(tmp_path):
    state = _replaced_state(tmp_path)
    dismissed = frozenset({"some-other-previously-dismissed-digest"})

    notice = build_notice_model(state, dismissed)

    assert notice is not None
    assert notice.digest == state.detected_official_sha256


# ---------------------------------------------------------------------------
# repair_confirm_text / repair_refusal_display
# ---------------------------------------------------------------------------


def test_repair_confirm_text_includes_known_version(tmp_path):
    state = _replaced_state(tmp_path)
    text = repair_confirm_text(state)
    assert "2.1.201" in text


def test_repair_confirm_text_falls_back_to_digest(tmp_path):
    state = _replaced_state(tmp_path, detected_official_version=None)
    text = repair_confirm_text(state)
    assert "a0852d76" in text


def test_repair_confirm_text_handles_none_state():
    assert repair_confirm_text(None) != ""


@pytest.mark.parametrize(
    "code",
    [
        "already_installed",
        "not_managed",
        "target_changed",
        "target_unavailable",
        "managed_path_refused",
        "authorization_required",
        "cache_failed",
        "swap_failed",
        "no_install_record",
        "invalid_record",
        "missing_target",
    ],
)
def test_repair_refusal_display_maps_every_known_code(code):
    display = repair_refusal_display(code)
    assert display != ""
    assert display != code  # raw code must never reach the UI


def test_repair_refusal_display_target_changed_reads_as_recheck():
    # Spec R3: an abort because the target changed mid-repair is a fresh
    # detection round, not an error -- the message must read that way.
    assert repair_refusal_display("target_changed") == "Claude changed again — re-checking."


def test_repair_refusal_display_falls_back_for_unknown_code():
    display = repair_refusal_display("some_future_code")
    assert display != ""
    assert display != "some_future_code"


def test_repair_refusal_display_falls_back_for_none_code():
    display = repair_refusal_display(None, fallback="repair failed")
    assert display == "repair failed"
