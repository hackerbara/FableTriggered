"""Tests for the ClaudeMonkey v3 settings window (Task 16).

`SettingsWindow` is the Qt manager window skeleton: a sidebar + stacked
pages, with real content on Overview and Logs & Reports; Patches, Prompts,
Options, and Install are empty placeholders filled in by later tasks
(17/18). Per the GUI plan's discipline, this file only renders
`MenuState`/`window_model` view-models -- it must not re-derive any
business logic (compatibility, enable rules, status normalization) that
already lives in `menubar_state.py` / `gui/window_model.py`.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox  # noqa: E402

from claude_monkey.gui.settings_window import SettingsWindow  # noqa: E402
from claude_monkey.menubar_state import (  # noqa: E402
    HighRiskOptionSummary,
    MenuState,
    OptionMenuItem,
    PatchMenuItem,
    PromptMenuItem,
)

SIDEBAR_LABELS = ("Overview", "Patches", "Prompts", "Options", "Install", "Logs & Reports")


def _state(tmp_path: Path, **overrides) -> MenuState:
    defaults = dict(
        status="ok",
        status_label="OK",
        source_claude_version="2.1.199",
        source_claude_path=None,
        detected_claude_command_path=None,
        install_mode="shim",
        shim_installed=True,
        active_profile="default",
        active_prompt="research",
        desired_patch_ids=("p1",),
        active_patch_ids=("p1",),
        rebuild_required=False,
        latest_build_report_path=tmp_path / "report.json",
        active_patch_set="everyday",
        current_claude_path=None,
        shim_target_path=None,
        install_record_path=None,
        last_build_strategy="repack",
        changed_modules=({"id": "m1"}, {"id": "m2"}),
        repack_summary=None,
        state_dir=tmp_path,
        logs_dir=tmp_path / "logs",
        last_error=None,
        patch_items=(PatchMenuItem("p1", "Fable", True, True, True, "compatible", None),),
        prompt_items=(
            PromptMenuItem("research", "Research", True, "append", tmp_path / "research.md"),
        ),
        active_option_ids=("dangerous-permissions",),
        high_risk_options=(
            HighRiskOptionSummary(
                "dangerous-permissions", "Dangerous permissions", "This is risky."
            ),
        ),
        high_risk_warnings=("This is risky.",),
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
        ),
    )
    defaults.update(overrides)
    return MenuState(**defaults)


@pytest.fixture
def fake_state(tmp_path: Path) -> MenuState:
    return _state(tmp_path)


def test_sidebar_has_six_entries(qtbot):
    window = SettingsWindow()
    qtbot.addWidget(window)

    assert window.sidebar.count() == 6
    labels = [window.sidebar.item(i).text() for i in range(window.sidebar.count())]
    assert labels == list(SIDEBAR_LABELS)


def test_render_fake_state_fills_overview(qtbot, fake_state):
    window = SettingsWindow()
    qtbot.addWidget(window)

    window.render(fake_state)

    assert "ClaudeMonkey: OK" in window.overview_page.status_label.text()
    assert "2.1.199" in window.overview_page.version_label.text()
    assert "research" in window.overview_page.prompt_label.text()
    assert "everyday" in window.overview_page.patch_set_label.text()
    assert window.overview_page.high_risk_list.count() == 1
    assert window.overview_page.high_risk_list.item(0).text() == "This is risky."
    assert window.overview_page.rebuild_button.isEnabled() is True
    assert window.overview_page.open_report_button.isEnabled() is True
    assert window.disconnected_banner.isVisible() is False


def test_render_none_shows_disconnected_banner_and_retry_emits_refresh(qtbot):
    window = SettingsWindow()
    qtbot.addWidget(window)
    window.show()

    window.render(None)

    assert window.disconnected_banner.isVisible() is True
    assert window.retry_button.isVisible() is True

    with qtbot.waitSignal(window.refresh_requested, timeout=1000):
        qtbot.mouseClick(window.retry_button, Qt.MouseButton.LeftButton)


def test_rebuild_button_emits_action(qtbot, fake_state):
    window = SettingsWindow()
    qtbot.addWidget(window)
    window.show()
    window.render(fake_state)

    with qtbot.waitSignal(window.action, timeout=1000) as blocker:
        qtbot.mouseClick(window.overview_page.rebuild_button, Qt.MouseButton.LeftButton)

    assert blocker.args == ["rebuild", {}]


def test_open_report_button_emits_open_path_action(qtbot, fake_state):
    window = SettingsWindow()
    qtbot.addWidget(window)
    window.show()
    window.render(fake_state)

    with qtbot.waitSignal(window.action, timeout=1000) as blocker:
        qtbot.mouseClick(window.overview_page.open_report_button, Qt.MouseButton.LeftButton)

    assert blocker.args == ["open_path", {"path": str(fake_state.latest_build_report_path)}]


def test_close_hides_instead_of_destroying(qtbot):
    window = SettingsWindow()
    qtbot.addWidget(window)
    window.show()

    assert window.isVisible() is True
    window.close()

    assert window.isVisible() is False
    # Object must still be alive: further attribute access must not raise.
    assert window.sidebar.count() == 6


def test_show_banner_is_dismissible(qtbot):
    window = SettingsWindow()
    qtbot.addWidget(window)
    window.show()

    window.show_banner("overview", "Something went wrong.")
    banner = window._banners["overview"]
    assert banner.isVisible() is True
    assert "Something went wrong." in banner.label.text()

    qtbot.mouseClick(banner.dismiss_button, Qt.MouseButton.LeftButton)
    assert banner.isVisible() is False


def test_show_banner_rejects_unknown_page(qtbot):
    window = SettingsWindow()
    qtbot.addWidget(window)

    with pytest.raises(ValueError):
        window.show_banner("no-such-page", "boom")


def test_placeholder_pages_render_without_crashing(qtbot, fake_state):
    window = SettingsWindow()
    qtbot.addWidget(window)

    window.render(fake_state)
    window.render(None)
    window.render(fake_state)  # renders must be idempotent/repeatable


def test_logs_page_tails_menubar_log(qtbot, tmp_path):
    logs_dir = tmp_path / "logs"
    logs_dir.mkdir()
    log_path = logs_dir / "menubar.log"
    lines = [f"line-{i}" for i in range(250)]
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    state = _state(tmp_path, logs_dir=logs_dir)

    window = SettingsWindow()
    qtbot.addWidget(window)
    window.render(state)

    text = window.logs_page.log_view.toPlainText()
    assert "line-249" in text
    assert "line-0" not in text  # only the last 200 lines are kept
    assert text.count("\n") == 199  # 200 lines -> 199 newlines


def test_logs_page_open_buttons_emit_open_path(qtbot, tmp_path):
    state = _state(tmp_path)
    window = SettingsWindow()
    qtbot.addWidget(window)
    window.show()
    window.render(state)

    with qtbot.waitSignal(window.action, timeout=1000) as blocker:
        qtbot.mouseClick(window.logs_page.open_logs_folder_button, Qt.MouseButton.LeftButton)
    assert blocker.args == ["open_path", {"path": str(state.logs_dir)}]

    with qtbot.waitSignal(window.action, timeout=1000) as blocker:
        qtbot.mouseClick(window.logs_page.open_state_folder_button, Qt.MouseButton.LeftButton)
    assert blocker.args == ["open_path", {"path": str(state.state_dir)}]

    with qtbot.waitSignal(window.action, timeout=1000) as blocker:
        qtbot.mouseClick(window.logs_page.open_report_button, Qt.MouseButton.LeftButton)
    assert blocker.args == ["open_path", {"path": str(state.latest_build_report_path)}]


def test_logs_page_missing_log_file_is_handled(qtbot, tmp_path):
    state = _state(tmp_path, logs_dir=tmp_path / "no-such-logs-dir")
    window = SettingsWindow()
    qtbot.addWidget(window)

    window.render(state)  # must not raise

    assert window.logs_page.log_view.toPlainText() != ""


# --- Patches page (Task 17) --------------------------------------------


def test_patches_toggle_emits_toggle_patch_action(qtbot, fake_state):
    window = SettingsWindow()
    qtbot.addWidget(window)
    window.render(fake_state)

    checkbox_item = window.patches_page.table.item(0, 0)

    with qtbot.waitSignal(window.action, timeout=1000) as blocker:
        checkbox_item.setCheckState(Qt.CheckState.Unchecked)

    assert blocker.args == ["toggle_patch", {"patch_id": "p1", "enabled": True}]


def test_patches_incompatible_row_is_disabled(qtbot, tmp_path):
    state = _state(
        tmp_path,
        patch_items=(
            PatchMenuItem("p2", "Broken", False, False, True, "incompatible", "needs v16"),
        ),
    )
    window = SettingsWindow()
    qtbot.addWidget(window)

    window.render(state)

    checkbox_item = window.patches_page.table.item(0, 0)
    assert not (checkbox_item.flags() & Qt.ItemFlag.ItemIsEnabled)


def test_patches_add_package_emits_action(qtbot, monkeypatch, fake_state, tmp_path):
    window = SettingsWindow()
    qtbot.addWidget(window)
    window.render(fake_state)

    fake_dir = str(tmp_path / "new-patch")
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *a, **k: fake_dir)

    with qtbot.waitSignal(window.action, timeout=1000) as blocker:
        qtbot.mouseClick(window.patches_page.add_button, Qt.MouseButton.LeftButton)

    assert blocker.args == ["add_package", {"kind": "patch", "path": fake_dir}]


def test_patches_remove_button_disabled_with_reason_tooltip(qtbot, fake_state):
    # Default fake_state has desired_patch_ids=("p1",) -- p1 is referenced by
    # the active profile, so remove_enabled refuses it.
    window = SettingsWindow()
    qtbot.addWidget(window)
    window.render(fake_state)

    window.patches_page.table.setCurrentCell(0, 0)

    assert window.patches_page.remove_button.isEnabled() is False
    assert "p1" in window.patches_page.remove_button.toolTip()


def test_patches_remove_button_enabled_when_not_referenced(qtbot, tmp_path):
    state = _state(tmp_path, desired_patch_ids=())
    window = SettingsWindow()
    qtbot.addWidget(window)
    window.render(state)

    window.patches_page.table.setCurrentCell(0, 0)

    assert window.patches_page.remove_button.isEnabled() is True
    assert window.patches_page.remove_button.toolTip() == ""


def test_patches_remove_click_emits_action(qtbot, tmp_path):
    state = _state(tmp_path, desired_patch_ids=())
    window = SettingsWindow()
    qtbot.addWidget(window)
    window.render(state)
    window.patches_page.table.setCurrentCell(0, 0)

    with qtbot.waitSignal(window.action, timeout=1000) as blocker:
        qtbot.mouseClick(window.patches_page.remove_button, Qt.MouseButton.LeftButton)

    assert blocker.args == ["remove_package", {"kind": "patch", "package_id": "p1"}]


# --- Prompts page (Task 17) ---------------------------------------------


def test_prompts_click_emits_set_prompt(qtbot, fake_state):
    window = SettingsWindow()
    qtbot.addWidget(window)
    window.render(fake_state)

    list_widget = window.prompts_page.list
    item = list_widget.item(1)  # row 0 is "(none)"
    rect = list_widget.visualItemRect(item)

    with qtbot.waitSignal(window.action, timeout=1000) as blocker:
        qtbot.mouseClick(list_widget.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())

    assert blocker.args == ["set_prompt", {"prompt_id": "research"}]


def test_prompts_click_none_emits_set_prompt_with_none(qtbot, fake_state):
    window = SettingsWindow()
    qtbot.addWidget(window)
    window.render(fake_state)

    list_widget = window.prompts_page.list
    item = list_widget.item(0)  # "(none)" row
    rect = list_widget.visualItemRect(item)

    with qtbot.waitSignal(window.action, timeout=1000) as blocker:
        qtbot.mouseClick(list_widget.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())

    assert blocker.args == ["set_prompt", {"prompt_id": None}]


def test_add_prompt_emits_add_prompt_file_and_never_set_prompt(
    qtbot, monkeypatch, fake_state, tmp_path
):
    window = SettingsWindow()
    qtbot.addWidget(window)
    window.render(fake_state)

    fake_path = str(tmp_path / "My Research Notes.md")
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: (fake_path, ""))
    monkeypatch.setattr(QDialog, "exec", lambda self: QDialog.DialogCode.Accepted)

    seen: list[tuple[str, dict]] = []
    window.action.connect(lambda action_id, payload: seen.append((action_id, payload)))

    qtbot.mouseClick(window.prompts_page.add_button, Qt.MouseButton.LeftButton)

    assert seen == [
        (
            "add_prompt_file",
            {
                "path": fake_path,
                "package_id": "my-research-notes",
                "name": "My Research Notes",
            },
        )
    ]


def test_add_prompt_cancelled_file_picker_emits_nothing(qtbot, monkeypatch, fake_state):
    window = SettingsWindow()
    qtbot.addWidget(window)
    window.render(fake_state)

    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *a, **k: ("", ""))

    seen: list[tuple[str, dict]] = []
    window.action.connect(lambda action_id, payload: seen.append((action_id, payload)))

    qtbot.mouseClick(window.prompts_page.add_button, Qt.MouseButton.LeftButton)

    assert seen == []


def test_prompts_remove_button_disabled_with_reason_tooltip(qtbot, fake_state):
    # Default fake_state has active_prompt="research" -- referenced, refused.
    window = SettingsWindow()
    qtbot.addWidget(window)
    window.render(fake_state)

    window.prompts_page.list.setCurrentRow(1)  # "research" row

    assert window.prompts_page.remove_button.isEnabled() is False
    assert "research" in window.prompts_page.remove_button.toolTip()


def test_prompts_remove_button_disabled_for_none_row(qtbot, fake_state):
    window = SettingsWindow()
    qtbot.addWidget(window)
    window.render(fake_state)

    window.prompts_page.list.setCurrentRow(0)  # "(none)" row -- no package id

    assert window.prompts_page.remove_button.isEnabled() is False


# --- Options page (Task 17) ---------------------------------------------


def _high_risk_state(tmp_path: Path, *, enabled: bool) -> MenuState:
    return _state(
        tmp_path,
        active_option_ids=("dangerous-permissions",) if enabled else (),
        option_items=(
            OptionMenuItem(
                "dangerous-permissions",
                "Dangerous permissions",
                enabled,
                True,
                "unconstrained",
                "high",
                True,
            ),
        ),
        high_risk_options=(
            HighRiskOptionSummary(
                "dangerous-permissions", "Dangerous permissions", "This is risky."
            ),
        ),
        high_risk_warnings=("This is risky.",) if enabled else (),
    )


def test_high_risk_option_confirm_yes_emits_confirmed_true(qtbot, monkeypatch, tmp_path):
    state = _high_risk_state(tmp_path, enabled=False)
    window = SettingsWindow()
    qtbot.addWidget(window)
    window.render(state)

    seen_messages: list[str] = []

    def fake_question(_parent, _title, message, *_args, **_kwargs):
        seen_messages.append(message)
        return QMessageBox.StandardButton.Yes

    monkeypatch.setattr(QMessageBox, "question", fake_question)

    checkbox_item = window.options_page.table.item(0, 0)
    with qtbot.waitSignal(window.action, timeout=1000) as blocker:
        checkbox_item.setCheckState(Qt.CheckState.Checked)

    assert blocker.args == [
        "toggle_option",
        {"option_id": "dangerous-permissions", "enabled": False, "confirmed": True},
    ]
    # The warning text comes from state (high_risk_options), not a hardcoded string.
    assert "This is risky." in seen_messages[0]
    assert "Dangerous permissions" in seen_messages[0]


def test_high_risk_option_confirm_no_emits_nothing_and_reverts_checkbox(
    qtbot, monkeypatch, tmp_path
):
    state = _high_risk_state(tmp_path, enabled=False)
    window = SettingsWindow()
    qtbot.addWidget(window)
    window.render(state)

    monkeypatch.setattr(QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.No)

    seen: list[tuple[str, dict]] = []
    window.action.connect(lambda action_id, payload: seen.append((action_id, payload)))

    checkbox_item = window.options_page.table.item(0, 0)
    checkbox_item.setCheckState(Qt.CheckState.Checked)
    qtbot.wait(50)

    assert seen == []
    assert checkbox_item.checkState() == Qt.CheckState.Unchecked


def test_low_risk_option_toggle_emits_action_without_confirm_dialog(qtbot, monkeypatch, tmp_path):
    state = _state(
        tmp_path,
        option_items=(
            OptionMenuItem("safe-thing", "Safe thing", True, True, "compatible", "low", False),
        ),
    )
    window = SettingsWindow()
    qtbot.addWidget(window)
    window.render(state)

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("QMessageBox.question must not be called for non-confirm options")

    monkeypatch.setattr(QMessageBox, "question", fail_if_called)

    checkbox_item = window.options_page.table.item(0, 0)
    with qtbot.waitSignal(window.action, timeout=1000) as blocker:
        checkbox_item.setCheckState(Qt.CheckState.Unchecked)

    assert blocker.args == ["toggle_option", {"option_id": "safe-thing", "enabled": True}]


def test_disabling_high_risk_option_skips_confirm_dialog(qtbot, monkeypatch, tmp_path):
    # requires_confirmation only gates ENABLING; an already-enabled high-risk
    # option must be disable-able without a confirm dialog.
    state = _high_risk_state(tmp_path, enabled=True)
    window = SettingsWindow()
    qtbot.addWidget(window)
    window.render(state)

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("QMessageBox.question must not be called when disabling")

    monkeypatch.setattr(QMessageBox, "question", fail_if_called)

    checkbox_item = window.options_page.table.item(0, 0)
    with qtbot.waitSignal(window.action, timeout=1000) as blocker:
        checkbox_item.setCheckState(Qt.CheckState.Unchecked)

    assert blocker.args == [
        "toggle_option",
        {"option_id": "dangerous-permissions", "enabled": True},
    ]


def test_options_remove_button_disabled_with_reason_tooltip(qtbot, fake_state):
    # Default fake_state has active_option_ids=("dangerous-permissions",).
    window = SettingsWindow()
    qtbot.addWidget(window)
    window.render(fake_state)

    window.options_page.table.setCurrentCell(0, 0)

    assert window.options_page.remove_button.isEnabled() is False
    assert "dangerous-permissions" in window.options_page.remove_button.toolTip()
