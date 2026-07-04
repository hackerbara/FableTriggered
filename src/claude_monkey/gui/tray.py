"""Qt tray renderer for the ClaudeMonkey v3 GUI.

`Tray` is a thin renderer over `TrayModel` (`window_model.py`, Task 9): it
owns the `QSystemTrayIcon`/`QMenu` widgets and the single dispatcher that
funnels every menu action to the caller's `on_action` callback, but it makes
no decisions of its own. Every piece of rendered state -- which lines show,
which submenus/items are enabled, which labels are used, whether "Install
shim…" appears at all -- is read directly off the `TrayModel` passed to
`render()`, or from the pure helper functions in `window_model.py`
(`patch_menu_label`, `patch_item_enabled`, `option_item_enabled`) that
already encapsulate those decisions. Task 19 is responsible for
constructing this against a live `CommandRunner`/`CommandBridge` and wiring
`on_action` to actually run commands.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from claude_monkey.gui.icons import tray_icon
from claude_monkey.gui.window_model import (
    TrayModel,
    option_item_enabled,
    patch_item_enabled,
    patch_menu_label,
)

ActionCallback = Callable[[str, dict[str, Any]], None]


class Tray(QObject):
    """Owns the tray icon/menu and dispatches every action to `on_action`."""

    def __init__(self, *, on_action: ActionCallback) -> None:
        super().__init__()
        self.on_action = on_action
        self.menu = QMenu()
        self.icon = QSystemTrayIcon(tray_icon())
        self.icon.setContextMenu(self.menu)

    def render(self, model: TrayModel) -> None:
        self.menu.clear()

        for line in model.status_lines:
            self._add_action(self.menu, line, enabled=False)
        if model.running_label is not None:
            self._add_action(self.menu, model.running_label, enabled=False)
        self.menu.addSeparator()

        self._add_action(self.menu, "Open ClaudeMonkey…", action_id="open_window")
        self.menu.addSeparator()

        self._add_prompts_submenu(model)
        self._add_patches_submenu(model)
        self._add_options_submenu(model)

        self.menu.addSeparator()
        self._add_action(
            self.menu,
            "Rebuild / Apply…",
            action_id="rebuild",
            enabled=model.mutating_enabled,
        )
        if model.show_install_shim:
            self._add_action(
                self.menu,
                "Install shim…",
                action_id="install_shim",
                enabled=model.mutating_enabled,
            )

        self.menu.addSeparator()
        self._add_action(self.menu, "Refresh", action_id="refresh")
        self._add_action(self.menu, "Quit", action_id="quit")

    def _add_prompts_submenu(self, model: TrayModel) -> None:
        submenu = self.menu.addMenu("Prompts")
        submenu.menuAction().setEnabled(model.mutating_enabled)
        for prompt in model.prompt_items:
            self._add_action(
                submenu,
                prompt.label,
                action_id="set_prompt",
                kwargs={"prompt_id": prompt.prompt_id},
                enabled=model.mutating_enabled,
                checkable=True,
                checked=prompt.checked,
            )

    def _add_patches_submenu(self, model: TrayModel) -> None:
        submenu = self.menu.addMenu("Patches")
        submenu.menuAction().setEnabled(model.mutating_enabled)
        for patch in model.patch_items:
            self._add_action(
                submenu,
                patch_menu_label(patch),
                action_id="toggle_patch",
                kwargs={"patch_id": patch.patch_id, "enabled": patch.checked},
                enabled=patch_item_enabled(patch, mutating_enabled=model.mutating_enabled),
                checkable=True,
                checked=patch.checked,
            )

    def _add_options_submenu(self, model: TrayModel) -> None:
        submenu = self.menu.addMenu("Options")
        submenu.menuAction().setEnabled(model.mutating_enabled)
        for option in model.option_items:
            self._add_action(
                submenu,
                option.label,
                action_id="toggle_option",
                kwargs={
                    "option_id": option.option_id,
                    "enabled": option.enabled,
                    "requires_confirmation": option.requires_confirmation,
                },
                enabled=option_item_enabled(option, mutating_enabled=model.mutating_enabled),
                checkable=True,
                checked=option.enabled,
            )

    def _add_action(
        self,
        menu: QMenu,
        label: str,
        *,
        action_id: str | None = None,
        kwargs: dict[str, Any] | None = None,
        enabled: bool = True,
        checkable: bool = False,
        checked: bool = False,
    ) -> QAction:
        action = menu.addAction(label)
        action.setEnabled(enabled)
        if checkable:
            action.setCheckable(True)
            action.setChecked(checked)
        if action_id is not None:
            action.setData((action_id, kwargs or {}))
            action.triggered.connect(self._on_triggered)
        return action

    def _on_triggered(self) -> None:
        action = self.sender()
        if action is None:
            return
        data = action.data()
        if not data:
            return
        action_id, kwargs = data
        self.on_action(action_id, kwargs)
