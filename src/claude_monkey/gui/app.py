"""Qt application shell for the ClaudeMonkey v3 GUI.

This module owns process-level concerns that have to exist before any
window/tray is built: refusing to run as root, enforcing a single running
instance, applying the macOS "accessory" (LSUIElement-equivalent) activation
policy, and bridging worker-thread progress events into the Qt event loop
via `CommandBridge`.

Tray/window/progress-dialog construction is wired in a later task (see the
seam comment in `main()` below); this module intentionally does not import
`claude_monkey.gui.tray` or any other not-yet-built GUI module.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication

from claude_monkey.menubar_commands import CommandRunner

PUMP_INTERVAL_MS = 250


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

    runner = CommandRunner(logs_dir=Path.home() / ".claude-monkey" / "logs")
    bridge = CommandBridge()
    # Stash on `app` so Task 19 can find them and so they aren't garbage
    # collected before the seam below wires them into a tray/window.
    app.runner = runner  # type: ignore[attr-defined]
    app.bridge = bridge  # type: ignore[attr-defined]
    app.single_instance = instance  # type: ignore[attr-defined]

    # --- Seam for Task 19 -------------------------------------------------
    # Task 19 wires the tray (Task 14), settings window (Tasks 16-18), and
    # progress dialog (Task 15) here: construct them against `runner` and
    # `bridge`, connect `instance.activated` to raise the window/tray, and
    # call `bridge.pump(runner)` once the consumers are ready to receive
    # `command_finished`/`progress_event`. Then `return app.exec()`.
    # ------------------------------------------------------------------

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
