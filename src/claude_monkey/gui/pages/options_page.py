"""Options page: checkbox|label|risk|compatibility table + add/remove.

Follows `settings_window.py`'s rendering discipline: `option_item_enabled`
(row enable/disable) and `remove_enabled` (Remove-button enable/disable +
refusal reason) are read from `window_model.py`, never re-derived here.
Enabling a `requires_confirmation` option shows a confirm dialog whose
warning text is read off `MenuState.high_risk_options` -- never hardcoded.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from claude_monkey.gui.pages.common import Banner
from claude_monkey.gui.window_model import option_item_enabled, remove_enabled
from claude_monkey.menubar_state import MenuState, OptionMenuItem

COLUMN_LABELS = ("", "Option", "Risk", "Compatibility")
OPTION_ID_ROLE = Qt.ItemDataRole.UserRole
HIGH_RISK_COLOR = QColor("#a00")


class OptionsPage(QWidget):
    """Table of installed option packages, plus add/remove controls.

    Signals:
        action(str, dict): "toggle_option" (checkbox toggled -- carries
            "confirmed": True only after a high-risk confirm dialog is
            accepted), "add_package" (folder picked), "remove_package"
            (Remove clicked) -- bubbled through `SettingsWindow.action` by
            the caller.
    """

    action = Signal(str, dict)

    def __init__(self) -> None:
        super().__init__()
        self._state: MenuState | None = None
        self._high_risk_warning_by_id: dict[str, str] = {}

        layout = QVBoxLayout(self)
        self.banner = Banner()
        layout.addWidget(self.banner)

        self.table = QTableWidget(0, len(COLUMN_LABELS))
        self.table.setHorizontalHeaderLabels(COLUMN_LABELS)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.itemSelectionChanged.connect(self._update_remove_button)
        layout.addWidget(self.table, 1)

        buttons_row = QHBoxLayout()
        self.add_button = QPushButton("Add Option Package…")
        self.add_button.clicked.connect(self._on_add_clicked)
        buttons_row.addWidget(self.add_button)
        self.remove_button = QPushButton("Remove")
        self.remove_button.setEnabled(False)
        self.remove_button.clicked.connect(self._on_remove_clicked)
        buttons_row.addWidget(self.remove_button)
        layout.addLayout(buttons_row)

        self.render(None)

    def render(self, state: MenuState | None) -> None:
        self._state = state
        self._high_risk_warning_by_id = (
            {summary.option_id: summary.warning for summary in state.high_risk_options}
            if state is not None
            else {}
        )
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        if state is not None:
            self.table.setRowCount(len(state.option_items))
            for row, option in enumerate(state.option_items):
                self._render_row(row, option)
        self.table.blockSignals(False)
        self._update_remove_button()

    def _render_row(self, row: int, option: OptionMenuItem) -> None:
        row_enabled = option_item_enabled(option, mutating_enabled=True)
        cell_flags = Qt.ItemFlag.ItemIsSelectable
        if row_enabled:
            cell_flags |= Qt.ItemFlag.ItemIsEnabled

        checkbox_item = QTableWidgetItem()
        checkbox_item.setFlags(cell_flags | Qt.ItemFlag.ItemIsUserCheckable)
        checkbox_item.setCheckState(
            Qt.CheckState.Checked if option.enabled else Qt.CheckState.Unchecked
        )
        checkbox_item.setData(OPTION_ID_ROLE, option.option_id)
        self.table.setItem(row, 0, checkbox_item)

        label_item = QTableWidgetItem(option.label)
        label_item.setFlags(cell_flags)
        self.table.setItem(row, 1, label_item)

        risk_item = QTableWidgetItem(option.risk_level)
        risk_item.setFlags(cell_flags)
        if option.risk_level == "high":
            risk_item.setForeground(HIGH_RISK_COLOR)
        self.table.setItem(row, 2, risk_item)

        compat_item = QTableWidgetItem(option.compatibility_status)
        compat_item.setFlags(cell_flags)
        self.table.setItem(row, 3, compat_item)

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != 0 or self._state is None:
            return
        option = self._option_by_id(item.data(OPTION_ID_ROLE))
        if option is None:
            return

        turning_on = not option.enabled
        if turning_on and option.requires_confirmation:
            self._confirm_and_emit(item, option)
            return

        # `enabled` reports the option's CURRENT (pre-toggle) state, matching
        # `command_for_option_toggle`'s enable/disable direction convention.
        self.action.emit(
            "toggle_option", {"option_id": option.option_id, "enabled": option.enabled}
        )

    def _confirm_and_emit(self, item: QTableWidgetItem, option: OptionMenuItem) -> None:
        warning = self._high_risk_warning_by_id.get(option.option_id, "")
        message = f"{option.label}\n\n{warning}" if warning else option.label
        answer = QMessageBox.question(
            self,
            "Confirm high-risk option",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            self.table.blockSignals(True)
            item.setCheckState(Qt.CheckState.Unchecked)
            self.table.blockSignals(False)
            return
        self.action.emit(
            "toggle_option",
            {"option_id": option.option_id, "enabled": option.enabled, "confirmed": True},
        )

    def _option_by_id(self, option_id: object) -> OptionMenuItem | None:
        if self._state is None:
            return None
        return next((o for o in self._state.option_items if o.option_id == option_id), None)

    def _selected_option(self) -> OptionMenuItem | None:
        if self._state is None:
            return None
        row = self.table.currentRow()
        if row < 0 or row >= len(self._state.option_items):
            return None
        return self._state.option_items[row]

    def _update_remove_button(self) -> None:
        option = self._selected_option()
        if option is None or self._state is None:
            self.remove_button.setEnabled(False)
            self.remove_button.setToolTip("")
            return
        can_remove, reason = remove_enabled("option", option.option_id, self._state)
        self.remove_button.setEnabled(can_remove)
        self.remove_button.setToolTip("" if can_remove else reason)

    def _on_add_clicked(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Add Option Package")
        if not path:
            return
        self.action.emit("add_package", {"kind": "option", "path": path})

    def _on_remove_clicked(self) -> None:
        option = self._selected_option()
        if option is None:
            return
        self.action.emit("remove_package", {"kind": "option", "package_id": option.option_id})
