"""Qt application shell for the ClaudeMonkey v3 GUI.

This module owns process-level concerns that have to exist before any
window/tray is built: refusing to run as root, enforcing a single running
instance, applying the macOS "accessory" (LSUIElement-equivalent) activation
policy, and bridging worker-thread progress events into the Qt event loop
via `CommandBridge`. It also owns `Controller`, the single `on_action`
handler that wires every tray/window intent to `CommandRunner` and the
`ProgressDialog`, and `main()`, which assembles all of the above into a
running application (see `Controller`'s docstring for the wiring contract).
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMessageBox, QWidget

from claude_monkey.gui.commands import (
    command_for_add_package,
    command_for_add_prompt_file,
    command_for_install_shim,
    command_for_option_toggle,
    command_for_patch_toggle,
    command_for_prompt,
    command_for_rebuild_apply,
    command_for_remove_package,
    command_for_uninstall_shim,
)
from claude_monkey.gui.progress_dialog import ProgressDialog
from claude_monkey.gui.settings_window import SettingsWindow
from claude_monkey.gui.tray import Tray
from claude_monkey.gui.window_model import InstallTargetSelection, build_tray_model
from claude_monkey.menubar_commands import CommandRunner
from claude_monkey.menubar_state import MenuState, parse_menu_state

PUMP_INTERVAL_MS = 250

# `add_package`/`remove_package` payloads carry a "kind" ("patch"/"option"/
# "prompt"); this maps each to the settings-window sidebar page key that
# should show a failure banner for that kind.
PAGE_BY_KIND = {"patch": "patches", "option": "options", "prompt": "prompts"}


class CommandBridge(QObject):
    """Delivers `CommandRunner` progress/result events into the Qt event loop.

    `progress_event` is emitted directly by worker-thread `on_event`
    callbacks passed to `CommandRunner.run_streaming`; Qt's queued
    connection semantics (signal emitted from a non-GUI thread, received by
    a QObject that lives on the GUI thread) make that delivery thread-safe
    without any extra locking here.

    `command_finished` is emitted from `pump()`, which polls
    `runner.drain_results()` on a QTimer running on the GUI thread.
    """

    progress_event = Signal(str, dict)
    command_finished = Signal(str, dict)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._timer: QTimer | None = None

    def pump(self, runner: CommandRunner) -> QTimer:
        """Start a QTimer that drains `runner`'s finished-command queue.

        Returns the QTimer so the caller can keep a reference (parenting it
        to this QObject already keeps it alive, but callers may want to
        stop() it explicitly, e.g. in tests).
        """
        timer = QTimer(self)
        timer.setInterval(PUMP_INTERVAL_MS)
        timer.timeout.connect(lambda: self._drain(runner))
        timer.start()
        self._timer = timer
        return timer

    def _drain(self, runner: CommandRunner) -> None:
        for name, payload in runner.drain_results():
            self.command_finished.emit(name, payload)


def apply_macos_accessory_policy() -> None:
    """Hide the app from the Dock/Cmd-Tab by setting an "accessory" policy.

    Verbatim port of `ClaudeMonkeyMenuBar._ensure_modal_activation_policy`
    from `menubar.py`, with an added `sys.platform` guard since this GUI
    (unlike rumps) also runs in CI/offscreen contexts on non-macOS platforms
    where the AppKit import would simply fail every time anyway.
    """
    if sys.platform != "darwin":
        return
    try:
        from AppKit import (  # type: ignore[import-not-found]
            NSApplication,
            NSApplicationActivationPolicyAccessory,
        )
    except Exception:
        return
    try:
        app = NSApplication.sharedApplication()
        if app is not None and app.activationPolicy() != NSApplicationActivationPolicyAccessory:
            app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    except Exception:
        pass


class SingleInstance(QObject):
    """Ensures only one GUI process is active for a given `key`.

    The first instance to call `QLocalServer.listen(key)` becomes the
    `is_primary` instance and listens for connections from later launches;
    each later launch connects as a client, sends `b"raise"`, and is not
    primary (the caller is expected to exit rather than start a second GUI).

    The primary emits `activated` whenever any client connects, so the
    caller can bring its window/tray to the foreground.
    """

    activated = Signal()

    def __init__(self, key: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._key = key
        self._server: QLocalServer | None = None
        self._socket: QLocalSocket | None = None
        self.is_primary = self._claim()

    def _claim(self) -> bool:
        # Probe for a live primary first: if one is listening, connect,
        # announce ourselves, and give up primary status. We must not call
        # QLocalServer.removeServer() before this probe, since on Unix that
        # unlinks the socket path out from under an already-listening
        # primary, which would let us (wrongly) also succeed at listen().
        socket = QLocalSocket(self)
        socket.connectToServer(self._key)
        if socket.waitForConnected(1000):
            socket.write(b"raise")
            socket.flush()
            socket.waitForBytesWritten(1000)
            socket.disconnectFromServer()
            self._socket = socket
            return False

        # No live primary answered. Clear a stale socket left behind by a
        # process that didn't shut down cleanly (e.g. killed rather than
        # quit) so listen() below doesn't fail spuriously, then claim
        # primary status.
        QLocalServer.removeServer(self._key)
        server = QLocalServer(self)
        if server.listen(self._key):
            server.newConnection.connect(self._on_new_connection)
            self._server = server
            return True

        # Listen failed for some other reason (e.g. a race against another
        # process claiming primary between our probe and our listen call).
        # Treat this instance as secondary rather than crashing.
        return False

    def _on_new_connection(self) -> None:
        server = self._server
        if server is None:
            return
        connection = server.nextPendingConnection()
        if connection is not None:
            connection.readyRead.connect(connection.deleteLater)
            connection.disconnected.connect(connection.deleteLater)
        self.activated.emit()


def refuse_root() -> bool:
    """Port of `menubar.refuse_root_menu_process`: True if running as root."""
    return getattr(os, "geteuid", lambda: 1)() == 0


class Controller:
    """The single `on_action(action_id, payload)` handler for the whole GUI.

    Both `Tray` and `SettingsWindow` (plus its pages) funnel every user
    intent through this one entry point, using the same action-id
    vocabulary documented on those classes. `Controller` is the only piece
    of the GUI that decides *what a click means* -- it is the sole owner of
    `CommandRunner`/`CommandBridge`, the current `MenuState`, and whichever
    `ProgressDialog` (if any) is open.

    Dispatch:
      - `refresh`: fetch `status`/`list-patches`/`list-prompts`/
        `list-options` via `run_json` (non-mutating), parse into a
        `MenuState`, and push it into both `tray.render()` and
        `window.render()`. A fetch failure renders a `None` state (tray's
        error line, window's disconnected banner) rather than raising.
      - Quick ops (`toggle_patch`, `toggle_option`, `set_prompt`,
        `add_package`, `add_prompt_file`, `remove_package`): build argv via
        `gui/commands.py`, fire `runner.run_background`; the eventual
        `command_finished` triggers a `refresh()`, and an `ok: false`
        result shows an inline banner on the originating settings page.
      - Long ops (`rebuild`, `install_shim`, `uninstall_shim`): open exactly
        one `ProgressDialog` at a time regardless of trigger source (tray or
        window) -- a second long-op request while one is already open/running
        is a no-op. `install_shim`/`uninstall_shim` first run a non-mutating
        `run_json` dry-run fetch to get the real `authorizationRequired`
        flag (which gates `cancel_allowed_during_run`) and a confirm
        summary; `rebuild` has no CLI-side dry-run variant to fetch (see
        `commands.command_for_rebuild_apply`), so its confirm text is built
        from the already-known `MenuState` instead of an extra subprocess
        round trip. Once confirmed, `runner.run_streaming` is started and
        its `progress_event`/`command_finished` bridge signals drive
        `dialog.apply_event`/`dialog.finish`. `dialog.finish` is called for
        *every* terminal `command_finished` for the active long op, even a
        malformed/missing-field payload (both `ProgressModel.apply_result`
        and `ProgressDialog.finish` already tolerate that defensively), so a
        dialog is never stranded mid-RUNNING.
      - `toggle_option` is emitted with two different shapes (see the
        per-emitter handling in `_action_toggle_option`): the window's
        Options page always runs its own confirm `QMessageBox` before
        emitting (payload carries `confirmed` when relevant), while the
        tray emits a static `requires_confirmation` flag and never shows a
        dialog of its own -- when the tray asks to enable a
        `requires_confirmation` option, `Controller` runs the confirm
        prompt itself (`confirm_high_risk`, using the warning text from
        `MenuState.high_risk_options`).
      - `open_path` -> `runner.open_path`. `quit` cancels any live
        streaming handle and calls `quit_callback` (defaults to
        `QApplication.quit`).
    """

    def __init__(
        self,
        *,
        runner: CommandRunner,
        bridge: CommandBridge,
        tray: Any,
        window: Any,
        confirm_high_risk: Callable[[str, str], bool] | None = None,
        quit_callback: Callable[[], None] | None = None,
    ) -> None:
        self.runner = runner
        self.bridge = bridge
        self.tray = tray
        self.window = window
        self._confirm_high_risk = confirm_high_risk or self._default_confirm_high_risk
        self._quit_callback = quit_callback or self._default_quit

        self._state: MenuState | None = None
        self._busy_command: str | None = None
        self._install_selection = InstallTargetSelection()

        self._dialog: ProgressDialog | None = None
        self._handle: Any | None = None
        self._long_op: str | None = None
        self._pending_quick_pages: dict[str, str] = {}

        bridge.command_finished.connect(self._on_command_finished)
        bridge.progress_event.connect(self._on_progress_event)

    # -- action dispatch -----------------------------------------------------

    def on_action(self, action_id: str, payload: dict[str, Any]) -> None:
        handler = getattr(self, f"_action_{action_id}", None)
        if handler is None:
            return
        handler(payload)

    def _action_refresh(self, payload: dict[str, Any]) -> None:
        self.refresh()

    def _action_open_window(self, payload: dict[str, Any]) -> None:
        self.show_window()

    def _action_quit(self, payload: dict[str, Any]) -> None:
        if self._handle is not None:
            self._handle.cancel()
        self._quit_callback()

    def _action_open_path(self, payload: dict[str, Any]) -> None:
        path = payload.get("path")
        if path:
            self.runner.open_path(Path(path))

    def _action_set_install_target(self, payload: dict[str, Any]) -> None:
        path = payload.get("path")
        if path:
            self._install_selection.select(Path(path))

    def _action_toggle_patch(self, payload: dict[str, Any]) -> None:
        patch_id = payload["patch_id"]
        enabled = bool(payload.get("enabled", False))
        argv = command_for_patch_toggle(patch_id, enabled=enabled)
        self._run_quick("toggle_patch", argv, page="patches")

    def _action_set_prompt(self, payload: dict[str, Any]) -> None:
        argv = command_for_prompt(payload.get("prompt_id"))
        self._run_quick("set_prompt", argv, page="prompts")

    def _action_toggle_option(self, payload: dict[str, Any]) -> None:
        option_id = payload["option_id"]
        enabled = bool(payload.get("enabled", False))

        if "requires_confirmation" in payload:
            # Tray emitter: `requires_confirmation` is a static flag -- the
            # tray has no confirm-dialog UI of its own, so if the user is
            # turning a high-risk option ON (currently disabled), Controller
            # must run the confirm prompt itself.
            requires_confirmation = bool(payload["requires_confirmation"])
            confirm = False
            if requires_confirmation and not enabled:
                warning = self._high_risk_warning(option_id)
                if not self._confirm_high_risk(option_id, warning):
                    return
                confirm = True
        else:
            # Window emitter: the Options page already ran its own
            # QMessageBox confirm flow before emitting, if one was needed.
            confirm = bool(payload.get("confirmed", False))

        argv = command_for_option_toggle(option_id, enabled=enabled, confirm=confirm)
        self._run_quick("toggle_option", argv, page="options")

    def _action_add_package(self, payload: dict[str, Any]) -> None:
        kind = payload["kind"]
        argv = command_for_add_package(payload["path"], kind)
        self._run_quick("add_package", argv, page=PAGE_BY_KIND[kind])

    def _action_add_prompt_file(self, payload: dict[str, Any]) -> None:
        argv = command_for_add_prompt_file(
            payload["path"], payload["package_id"], payload.get("name")
        )
        self._run_quick("add_prompt_file", argv, page="prompts")

    def _action_remove_package(self, payload: dict[str, Any]) -> None:
        kind = payload["kind"]
        argv = command_for_remove_package(payload["package_id"], kind)
        self._run_quick("remove_package", argv, page=PAGE_BY_KIND[kind])

    def _action_rebuild(self, payload: dict[str, Any]) -> None:
        self._start_long_op(
            name="rebuild",
            title="Rebuild / Apply",
            confirm_button="Rebuild",
            real_argv=command_for_rebuild_apply(),
            dry_run_argv=None,
            confirm_text=self._rebuild_confirm_text(),
            page="overview",
        )

    def _action_install_shim(self, payload: dict[str, Any]) -> None:
        target = self._install_selection.target(self._state)
        self._start_long_op(
            name="install_shim",
            title="Install shim",
            confirm_button="Install",
            real_argv=command_for_install_shim(target, dry_run=False),
            dry_run_argv=command_for_install_shim(target, dry_run=True),
            page="install",
        )

    def _action_uninstall_shim(self, payload: dict[str, Any]) -> None:
        # Prefer the recorded install target over the (forward-looking)
        # install-target selection: uninstall should act on what's actually
        # installed. If neither is known, omit --target/--record entirely so
        # the CLI falls back to its own default install-record.json.
        target = self._state.shim_target_path if self._state is not None else None
        kwargs: dict[str, Any] = {"target": target} if target is not None else {}
        self._start_long_op(
            name="uninstall_shim",
            title="Uninstall shim",
            confirm_button="Uninstall",
            real_argv=command_for_uninstall_shim(dry_run=False, **kwargs),
            dry_run_argv=command_for_uninstall_shim(dry_run=True, **kwargs),
            page="install",
        )

    # -- refresh ---------------------------------------------------------

    def refresh(self) -> None:
        try:
            status_raw = self.runner.run_json(["status", "--json"], mutating=False)
            patches_raw = self.runner.run_json(["list-patches", "--json"], mutating=False)
            prompts_raw = self.runner.run_json(["list-prompts", "--json"], mutating=False)
            options_raw = self.runner.run_json(["list-options", "--json"], mutating=False)
            state = parse_menu_state(status_raw, patches_raw, prompts_raw, options_raw)
        except Exception:
            self._state = None
            self.tray.render(build_tray_model(None, self._busy_command))
            self.window.render(None)
            return

        self._state = state
        self.tray.render(build_tray_model(state, self._busy_command))
        self.window.render(state)

    def show_window(self) -> None:
        self.window.show()
        self.window.raise_()
        self.window.activateWindow()

    def _dialog_parent(self) -> QWidget | None:
        if isinstance(self.window, QWidget):
            return self.window
        active_window = QApplication.activeWindow()
        return active_window if isinstance(active_window, QWidget) else None

    def _show_dialog_foreground(self, dialog: QWidget) -> None:
        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    # -- quick ops ---------------------------------------------------------

    def _run_quick(self, name: str, argv: list[str], *, page: str) -> None:
        if self._busy_command is not None:
            return
        self._busy_command = name
        self._pending_quick_pages[name] = page
        self.runner.run_background(name, argv, mutating=True)

    # -- long ops ---------------------------------------------------------

    def _rebuild_confirm_text(self) -> str:
        state = self._state
        if state is None:
            return "Rebuild and activate Claude Code with the current selection."
        return (
            "Rebuild and activate Claude Code.\n"
            f"Patches: {len(state.desired_patch_ids)} enabled\n"
            f"Prompt: {state.active_prompt or 'none'}\n"
            f"Options: {len(state.active_option_ids)} active"
        )

    def _confirm_text_from_payload(self, payload: dict[str, Any]) -> str:
        summary = payload.get("summary") or ""
        actions = payload.get("plannedActions") or []
        if actions:
            bullets = "\n".join(f"- {action}" for action in actions)
            return f"{summary}\n\n{bullets}" if summary else bullets
        return summary or "Continue?"

    def _start_long_op(
        self,
        *,
        name: str,
        title: str,
        confirm_button: str,
        real_argv: list[str],
        dry_run_argv: list[str] | None,
        page: str,
        confirm_text: str = "",
    ) -> None:
        # Exactly one open ProgressDialog at a time, regardless of trigger
        # source (tray vs window) -- a busy Controller (quick or long op)
        # simply ignores a second long-op request.
        if self._busy_command is not None or self._dialog is not None:
            return

        cancel_allowed_during_run = True
        if dry_run_argv is not None:
            try:
                payload = self.runner.run_json(dry_run_argv, mutating=False)
            except Exception as exc:
                self.window.show_banner(page, str(exc))
                return
            if not payload.get("ok", False):
                self.window.show_banner(page, payload.get("summary") or "command failed")
                return
            cancel_allowed_during_run = not bool(payload.get("authorizationRequired", False))
            confirm_text = self._confirm_text_from_payload(payload)

        parent = self._dialog_parent()
        dialog = ProgressDialog(
            title=title,
            confirm_text=confirm_text,
            confirm_button=confirm_button,
            cancel_allowed_during_run=cancel_allowed_during_run,
            parent=parent,
        )
        dialog.setWindowModality(
            Qt.WindowModality.WindowModal
            if parent is not None
            else Qt.WindowModality.ApplicationModal
        )
        dialog.confirmed.connect(lambda: self._on_long_op_confirmed(name, real_argv))
        dialog.cancel_requested.connect(self._on_long_op_cancel)
        dialog.open_path_requested.connect(lambda path: self.runner.open_path(Path(path)))

        self._dialog = dialog
        self._long_op = name
        self._busy_command = name
        self._show_dialog_foreground(dialog)

    def _on_long_op_confirmed(self, name: str, argv: list[str]) -> None:
        dialog = self._dialog
        if dialog is None:
            return
        dialog.start_running()
        try:
            handle = self.runner.run_streaming(
                name, argv, on_event=lambda event: self.bridge.progress_event.emit(name, event)
            )
        except Exception as exc:
            error_payload = {"schemaVersion": 1, "ok": False, "summary": str(exc)}
            dialog.finish(error_payload, report_path=None, logs_dir=str(self.runner.logs_dir))
            self._dialog = None
            self._handle = None
            self._long_op = None
            self._busy_command = None
            self.refresh()
            return
        self._handle = handle

    def _on_long_op_cancel(self) -> None:
        if self._handle is not None:
            # RUNNING phase: terminate the subprocess; the eventual
            # `command_finished` still drives `dialog.finish` so the dialog
            # is never left stranded mid-RUNNING.
            self._handle.cancel()
            return
        # CONFIRM phase: nothing has been started yet, so just tear the
        # dialog down.
        if self._dialog is not None:
            self._dialog.close()
        self._dialog = None
        self._long_op = None
        self._busy_command = None

    # -- bridge signal handlers --------------------------------------------

    def _on_command_finished(self, name: str, payload: dict[str, Any]) -> None:
        if self._long_op is not None and name == self._long_op:
            self._finish_long_op(payload)
            return

        self._busy_command = None
        page = self._pending_quick_pages.pop(name, None)
        if not payload.get("ok", True) and page is not None:
            self.window.show_banner(page, payload.get("summary") or "command failed")
        self.refresh()

    def _finish_long_op(self, payload: dict[str, Any]) -> None:
        dialog = self._dialog
        if dialog is not None:
            report_path = payload.get("reportPath") if isinstance(payload, dict) else None
            dialog.finish(payload, report_path=report_path, logs_dir=str(self.runner.logs_dir))
        self._dialog = None
        self._handle = None
        self._long_op = None
        self._busy_command = None
        self.refresh()

    def _on_progress_event(self, name: str, event: dict[str, Any]) -> None:
        if self._dialog is not None and name == self._long_op:
            self._dialog.apply_event(event)

    # -- high-risk option confirm ------------------------------------------

    def _high_risk_warning(self, option_id: str) -> str:
        if self._state is None:
            return ""
        summary = next(
            (o for o in self._state.high_risk_options if o.option_id == option_id), None
        )
        return summary.warning if summary is not None else ""

    def _default_confirm_high_risk(self, option_id: str, warning: str) -> bool:
        parent = self._dialog_parent()
        message = warning or "This option is high-risk."
        answer = QMessageBox.question(
            parent,
            "Confirm high-risk option",
            message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes

    @staticmethod
    def _default_quit() -> None:
        app = QApplication.instance()
        if app is not None:
            app.quit()


def build_runner() -> CommandRunner:
    # Always drive the CLI via this process's own interpreter (`python -m
    # claude_monkey`) rather than a bare `claude-monkey` PATH lookup: the
    # GUI must stay version-locked to its own venv/code and must not depend
    # on `claude-monkey` being installed on the user's PATH.
    return CommandRunner(
        cli_argv=[sys.executable, "-m", "claude_monkey"],
        logs_dir=Path.home() / ".claude-monkey" / "logs",
    )


def main() -> int:
    if refuse_root():
        print(
            "refusing to run claude-monkey GUI as root; start it as your user",
            file=sys.stderr,
        )
        return 1

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    apply_macos_accessory_policy()

    instance = SingleInstance(f"claude-monkey-gui-{os.getuid()}")
    if not instance.is_primary:
        print("claude-monkey GUI is already running")
        return 0

    runner = build_runner()
    bridge = CommandBridge()

    window = SettingsWindow()

    controller_holder: dict[str, Controller] = {}

    def _dispatch(action_id: str, payload: dict[str, Any]) -> None:
        controller_holder["controller"].on_action(action_id, payload)

    tray = Tray(on_action=_dispatch)
    controller = Controller(runner=runner, bridge=bridge, tray=tray, window=window)
    controller_holder["controller"] = controller

    window.action.connect(controller.on_action)
    window.refresh_requested.connect(controller.refresh)
    instance.activated.connect(controller.show_window)

    # Stash everything on `app` so it isn't garbage collected once `main`'s
    # local scope would otherwise go away, and so it's inspectable (e.g. in
    # a future test or a debugger) the same way `runner`/`bridge` already
    # were before this task.
    app.runner = runner  # type: ignore[attr-defined]
    app.bridge = bridge  # type: ignore[attr-defined]
    app.single_instance = instance  # type: ignore[attr-defined]
    app.tray = tray  # type: ignore[attr-defined]
    app.window = window  # type: ignore[attr-defined]
    app.controller = controller  # type: ignore[attr-defined]

    tray.icon.show()
    bridge.pump(runner)
    controller.refresh()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
