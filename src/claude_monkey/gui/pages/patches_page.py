"""Patches page: checkbox|label|compatibility table + add/remove controls.

Follows `settings_window.py`'s rendering discipline: `patch_item_enabled`
(row enable/disable) and `remove_enabled` (Remove-button enable/disable +
refusal reason) are read from `window_model.py`, never re-derived here.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from claude_monkey.gui.pages.common import Banner
from claude_monkey.gui.window_model import compatibility_display, patch_item_enabled, remove_enabled
from claude_monkey.menubar_state import MenuState, PatchMenuItem

COLUMN_LABELS = ("", "Patch", "Compatibility")
PATCH_ID_ROLE = Qt.ItemDataRole.UserRole


class PatchesPage(QWidget):
    """Table of installed patch packages, plus add/remove controls.

    Signals:
        action(str, dict): "toggle_patch" (checkbox toggled), "add_package"
            (folder picked), "remove_package" (Remove clicked) -- bubbled
            through `SettingsWindow.action` by the caller.
    """

    action = Signal(str, dict)

    def __init__(self) -> None:
        super().__init__()
        self._state: MenuState | None = None

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
        self.add_button = QPushButton("Add Patch Package…")
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
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        if state is not None:
            self.table.setRowCount(len(state.patch_items))
            for row, patch in enumerate(state.patch_items):
                self._render_row(row, patch)
        self.table.blockSignals(False)
        self._update_remove_button()

    def _render_row(self, row: int, patch: PatchMenuItem) -> None:
        row_enabled = patch_item_enabled(patch, mutating_enabled=True)

        checkbox_item = QTableWidgetItem()
        flags = Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsSelectable
        if row_enabled:
            flags |= Qt.ItemFlag.ItemIsEnabled
        checkbox_item.setFlags(flags)
        checkbox_item.setCheckState(
            Qt.CheckState.Checked if patch.checked else Qt.CheckState.Unchecked
        )
        checkbox_item.setData(PATCH_ID_ROLE, patch.patch_id)
        self.table.setItem(row, 0, checkbox_item)

        label_flags = Qt.ItemFlag.ItemIsSelectable
        if row_enabled:
            label_flags |= Qt.ItemFlag.ItemIsEnabled
        label_item = QTableWidgetItem(patch.label)
        label_item.setFlags(label_flags)
        self.table.setItem(row, 1, label_item)

        compat_item = QTableWidgetItem(
            compatibility_display(patch.compatibility_status, patch.compatibility_message)
        )
        compat_item.setFlags(label_flags)
        self.table.setItem(row, 2, compat_item)

    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if item.column() != 0 or self._state is None:
            return
        patch = self._patch_by_id(item.data(PATCH_ID_ROLE))
        if patch is None:
            return
        # `enabled` reports the patch's CURRENT (pre-toggle) state, matching
        # `command_for_patch_toggle`'s enable/disable direction convention.
        self.action.emit("toggle_patch", {"patch_id": patch.patch_id, "enabled": patch.checked})

    def _patch_by_id(self, patch_id: object) -> PatchMenuItem | None:
        if self._state is None:
            return None
        return next((p for p in self._state.patch_items if p.patch_id == patch_id), None)

    def _selected_patch(self) -> PatchMenuItem | None:
        if self._state is None:
            return None
        row = self.table.currentRow()
        if row < 0 or row >= len(self._state.patch_items):
            return None
        return self._state.patch_items[row]

    def _update_remove_button(self) -> None:
        patch = self._selected_patch()
        if patch is None or self._state is None:
            self.remove_button.setEnabled(False)
            self.remove_button.setToolTip("")
            return
        can_remove, reason = remove_enabled("patch", patch.patch_id, self._state)
        self.remove_button.setEnabled(can_remove)
        self.remove_button.setToolTip("" if can_remove else reason)

    def _on_add_clicked(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Add Patch Package")
        if not path:
            return
        self.action.emit("add_package", {"kind": "patch", "path": path})

    def _on_remove_clicked(self) -> None:
        patch = self._selected_patch()
        if patch is None:
            return
        self.action.emit("remove_package", {"kind": "patch", "package_id": patch.patch_id})
