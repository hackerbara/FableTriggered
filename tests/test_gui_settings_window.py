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
