"""ClaudeMonkey v3 manager window: sidebar navigation + stacked pages.

Discipline (see `docs/superpowers/specs/2026-07-03-claude-monkey-v3-gui-design.md`):
this file only *renders*. Every piece of business logic -- status
normalization, compatibility rules, enable/disable rules, label
formatting for status/version/prompt/patches -- already lives in
`menubar_state.py` / `gui/window_model.py`. `SettingsWindow.render()` reads
those view-models and pushes strings into widgets; it never re-derives
them.

Overview, Logs & Reports, Patches, Prompts, and Options have real content;
Install remains an empty placeholder wired into the sidebar/stack now so a
later task (18) can fill it in without touching the window skeleton.
Patches/Prompts/Options pages live in `gui/pages/` (moved out of this file
once real content pushed it past the ~500-line split threshold noted in
the GUI plan); this module re-exports them for convenience.

Closing the window never quits the app -- it only hides, per the plan's
"tray keeps running" requirement; the singleton window is re-shown by the
tray's "Open ClaudeMonkey..." action (a later task).
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from claude_monkey.gui.pages.common import Banner as _Banner
from claude_monkey.gui.pages.options_page import OptionsPage
from claude_monkey.gui.pages.patches_page import PatchesPage
from claude_monkey.gui.pages.prompts_page import PromptsPage
from claude_monkey.gui.window_model import build_tray_model
from claude_monkey.menubar_state import MenuState

__all__ = [
    "SettingsWindow",
    "OverviewPage",
    "LogsPage",
    "PatchesPage",
    "PromptsPage",
    "OptionsPage",
]

MAX_LOG_TAIL_LINES = 200
LOG_FILE_NAME = "menubar.log"  # historical name, kept for continuity -- see design doc.

# (page key used by show_banner/render, sidebar display label)
SIDEBAR_PAGES: tuple[tuple[str, str], ...] = (
    ("overview", "Overview"),
    ("patches", "Patches"),
    ("prompts", "Prompts"),
    ("options", "Options"),
    ("install", "Install"),
    ("logs", "Logs & Reports"),
)


def _tail_lines(path: Path, max_lines: int = MAX_LOG_TAIL_LINES) -> str:
    """Return up to `max_lines` trailing lines of `path` as a single string.

    A missing log file is expected (nothing has run yet) rather than an
    error condition, so it renders a friendly placeholder instead of
    raising.
    """
    if not path.exists():
        return "(no log file yet)"
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return f"(could not read log: {exc})"
    return "\n".join(lines[-max_lines:])


class _PlaceholderPage(QWidget):
    """Empty page for Install, filled in later (Task 18)."""

    def __init__(self, title: str) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        self.banner = _Banner()
        layout.addWidget(self.banner)
        layout.addWidget(QLabel(f"{title} management is coming soon."))
        layout.addStretch(1)

    def render(self, state: MenuState | None) -> None:
        pass  # nothing to render yet; kept for a uniform page interface.


class OverviewPage(QWidget):
    """Status/version/prompt/patch-set summary, high-risk warnings, rebuild."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        self.banner = _Banner()
        layout.addWidget(self.banner)

        self.status_label = QLabel()
        self.version_label = QLabel()
        self.prompt_label = QLabel()
        self.options_label = QLabel()
        self.patches_label = QLabel()
        self.patch_set_label = QLabel()
        for label in (
            self.status_label,
            self.version_label,
            self.prompt_label,
            self.options_label,
            self.patches_label,
            self.patch_set_label,
        ):
            layout.addWidget(label)

        layout.addWidget(QLabel("High-risk option warnings:"))
        self.high_risk_list = QListWidget()
        layout.addWidget(self.high_risk_list)

        self.rebuild_button = QPushButton("Rebuild / Apply")
        layout.addWidget(self.rebuild_button)

        self.build_summary_label = QLabel()
        layout.addWidget(self.build_summary_label)
        self.open_report_button = QPushButton("Open report")
        layout.addWidget(self.open_report_button)
        layout.addStretch(1)

        self.report_path: Path | None = None
        self.render(None)

    def render(self, state: MenuState | None) -> None:
        if state is None:
            for label in (
                self.status_label,
                self.version_label,
                self.prompt_label,
                self.options_label,
                self.patches_label,
                self.patch_set_label,
                self.build_summary_label,
            ):
                label.setText("")
            self.high_risk_list.clear()
            self.rebuild_button.setEnabled(False)
            self.open_report_button.setEnabled(False)
            self.report_path = None
            return

        # Status/version/prompt/options/patches lines are the exact strings
        # window_model already computes for the tray -- reused verbatim so
        # this page never re-derives the "N active", "⚠" suffix, etc. logic.
        model = build_tray_model(state, busy_command=None)
        self.status_label.setText(model.status_lines[0])
        self.version_label.setText(model.status_lines[1])
        self.prompt_label.setText(model.status_lines[2])
        self.options_label.setText(model.status_lines[3])
        self.patches_label.setText(model.status_lines[4])
        self.patch_set_label.setText(f"Patch set: {state.active_patch_set or 'none'}")

        self.high_risk_list.clear()
        self.high_risk_list.addItems(list(state.high_risk_warnings))

        self.rebuild_button.setEnabled(True)

        modules_changed = len(state.changed_modules)
        self.build_summary_label.setText(
            f"Last build: {state.last_build_strategy} ({modules_changed} module(s) changed)"
        )
        self.report_path = state.latest_build_report_path
        self.open_report_button.setEnabled(self.report_path is not None)


class LogsPage(QWidget):
    """Three "open" buttons plus a read-only tail of menubar.log."""

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        self.banner = _Banner()
        layout.addWidget(self.banner)

        buttons_row = QHBoxLayout()
        self.open_report_button = QPushButton("Open report")
        self.open_logs_folder_button = QPushButton("Open logs folder")
        self.open_state_folder_button = QPushButton("Open state folder")
        for button in (
            self.open_report_button,
            self.open_logs_folder_button,
            self.open_state_folder_button,
        ):
            buttons_row.addWidget(button)
        layout.addLayout(buttons_row)

        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        layout.addWidget(self.log_view, 1)

        self.report_path: Path | None = None
        self.logs_dir: Path | None = None
        self.state_dir: Path | None = None
        self.render(None)

    def render(self, state: MenuState | None) -> None:
        if state is None:
            self.report_path = None
            self.logs_dir = None
            self.state_dir = None
            self.open_report_button.setEnabled(False)
            self.open_logs_folder_button.setEnabled(False)
            self.open_state_folder_button.setEnabled(False)
            self.log_view.setPlainText("")
            return

        self.report_path = state.latest_build_report_path
        self.logs_dir = state.logs_dir
        self.state_dir = state.state_dir
        self.open_report_button.setEnabled(self.report_path is not None)
        self.open_logs_folder_button.setEnabled(True)
        self.open_state_folder_button.setEnabled(True)
        self.log_view.setPlainText(_tail_lines(state.logs_dir / LOG_FILE_NAME))


class SettingsWindow(QMainWindow):
    """Singleton manager window: sidebar navigation over stacked pages.

    Signals:
        action(str, dict): a user-triggered command intent, using the same
            action-id vocabulary as the tray, plus window-only ids
            ("uninstall_shim", "add_package", "remove_package",
            "add_prompt_file", "set_install_target", "open_path"). Overview
            emits "rebuild"/"open_path"; Logs & Reports emits "open_path";
            Patches/Prompts/Options (their own page-local `action` signals,
            bubbled through this one) emit "toggle_patch"/"toggle_option"/
            "set_prompt"/"add_package"/"add_prompt_file"/"remove_package".
            Install is wired up by a later task (18) once its page exists.
        refresh_requested(): emitted by the disconnected-state Retry button.
    """

    action = Signal(str, dict)
    refresh_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("ClaudeMonkey")

        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)

        self.disconnected_banner = QLabel(
            "Disconnected from ClaudeMonkey -- state could not be read."
        )
        self.disconnected_banner.setStyleSheet("color: #a00; font-weight: bold;")
        self.disconnected_banner.hide()
        outer.addWidget(self.disconnected_banner)

        self.retry_button = QPushButton("Retry")
        self.retry_button.hide()
        self.retry_button.clicked.connect(self.refresh_requested.emit)
        outer.addWidget(self.retry_button)

        body = QHBoxLayout()
        outer.addLayout(body, 1)

        self.sidebar = QListWidget()
        self.sidebar.setFixedWidth(160)
        for _key, label in SIDEBAR_PAGES:
            QListWidgetItem(label, self.sidebar)
        body.addWidget(self.sidebar)

        self.overview_page = OverviewPage()
        self.patches_page = PatchesPage()
        self.prompts_page = PromptsPage()
        self.options_page = OptionsPage()
        self.install_page = _PlaceholderPage("Install")
        self.logs_page = LogsPage()

        self._pages_by_key: dict[str, QWidget] = {
            "overview": self.overview_page,
            "patches": self.patches_page,
            "prompts": self.prompts_page,
            "options": self.options_page,
            "install": self.install_page,
            "logs": self.logs_page,
        }

        self.stack = QStackedWidget()
        for _key, _label in SIDEBAR_PAGES:
            self.stack.addWidget(self._pages_by_key[_key])
        body.addWidget(self.stack, 1)

        self.sidebar.setCurrentRow(0)
        self.sidebar.currentRowChanged.connect(self.stack.setCurrentIndex)

        self._banners: dict[str, _Banner] = {
            key: page.banner for key, page in self._pages_by_key.items()
        }

        self.overview_page.rebuild_button.clicked.connect(lambda: self.action.emit("rebuild", {}))
        self.overview_page.open_report_button.clicked.connect(self._open_overview_report)
        self.logs_page.open_report_button.clicked.connect(self._open_logs_report)
        self.logs_page.open_logs_folder_button.clicked.connect(self._open_logs_folder)
        self.logs_page.open_state_folder_button.clicked.connect(self._open_state_folder)

        # Patches/Prompts/Options each own a small `action` signal; bubble
        # every emission straight through this window's `action` signal.
        self.patches_page.action.connect(self.action.emit)
        self.prompts_page.action.connect(self.action.emit)
        self.options_page.action.connect(self.action.emit)

    def render(self, state: MenuState | None) -> None:
        """Repopulate every page from `state`; `None` shows a disconnected banner."""
        if state is None:
            self.disconnected_banner.show()
            self.retry_button.show()
        else:
            self.disconnected_banner.hide()
            self.retry_button.hide()

        for page in self._pages_by_key.values():
            page.render(state)

    def show_banner(self, page: str, message: str) -> None:
        """Show a dismissible inline error banner on `page` (a sidebar key)."""
        banner = self._banners.get(page)
        if banner is None:
            raise ValueError(f"unknown settings page: {page!r}")
        banner.show_message(message)

    def _open_overview_report(self) -> None:
        path = self.overview_page.report_path
        if path is not None:
            self.action.emit("open_path", {"path": str(path)})

    def _open_logs_report(self) -> None:
        path = self.logs_page.report_path
        if path is not None:
            self.action.emit("open_path", {"path": str(path)})

    def _open_logs_folder(self) -> None:
        path = self.logs_page.logs_dir
        if path is not None:
            self.action.emit("open_path", {"path": str(path)})

    def _open_state_folder(self) -> None:
        path = self.logs_page.state_dir
        if path is not None:
            self.action.emit("open_path", {"path": str(path)})

    def closeEvent(self, event: QCloseEvent) -> None:
        """Never quit the app on close -- just hide (tray keeps it alive)."""
        event.ignore()
        self.hide()
