"""Tests for the Qt application shell in claude_monkey.gui.app.

Covers the pieces that exist ahead of Task 19's wiring: root refusal,
single-instance detection via QLocalServer, and the CommandBridge signal
plumbing that lets a worker thread deliver progress events across to the Qt
event loop.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import sys
from pathlib import Path

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QWidget  # noqa: E402

import claude_monkey.gui.app as app_module  # noqa: E402
from claude_monkey.gui.app import (  # noqa: E402
    CommandBridge,
    Controller,
    SingleInstance,
    build_runner,
    refuse_root,
)


def test_build_runner_invokes_cli_via_own_interpreter():
    runner = build_runner()
    assert runner.cli_argv == [sys.executable, "-m", "claude_monkey"]
    assert runner.logs_dir == Path.home() / ".claude-monkey" / "logs"



class _Runner:
    logs_dir = Path("/tmp/claude-monkey-test-logs")


class _Tray:
    def render(self, _model):
        pass


def test_long_op_progress_dialog_is_parented_modal_and_foregrounded(qtbot, monkeypatch):
    window = QWidget()
    qtbot.addWidget(window)

    class SpyProgressDialog(app_module.ProgressDialog):
        last = None

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            SpyProgressDialog.last = self
            self.foreground_calls = []

        def show(self):
            self.foreground_calls.append("show")
            super().show()

        def raise_(self):
            self.foreground_calls.append("raise")
            super().raise_()

        def activateWindow(self):
            self.foreground_calls.append("activate")
            super().activateWindow()

    monkeypatch.setattr(app_module, "ProgressDialog", SpyProgressDialog)

    controller = Controller(runner=_Runner(), bridge=CommandBridge(), tray=_Tray(), window=window)

    controller.on_action("rebuild", {})

    dialog = SpyProgressDialog.last
    assert dialog is not None
    qtbot.addWidget(dialog)
    assert dialog.parent() is window
    assert dialog.windowModality() in {
        Qt.WindowModality.WindowModal,
        Qt.WindowModality.ApplicationModal,
    }
    assert dialog.foreground_calls == ["show", "raise", "activate"]


def test_refuse_root(monkeypatch):
    monkeypatch.setattr(os, "geteuid", lambda: 0)
    assert refuse_root() is True
    monkeypatch.setattr(os, "geteuid", lambda: 501)
    assert refuse_root() is False


def test_single_instance_second_is_not_primary(qapp):
    a = SingleInstance("claude-monkey-test-si")
    b = SingleInstance("claude-monkey-test-si")
    assert a.is_primary is True and b.is_primary is False


def test_bridge_signals_deliver_across_threads(qtbot, qapp):
    bridge = CommandBridge()
    got: list = []
    bridge.progress_event.connect(lambda name, e: got.append((name, e)))
    import threading

    t = threading.Thread(
        target=lambda: bridge.progress_event.emit("build", {"event": "log", "line": "x"})
    )
    t.start()
    t.join()
    qtbot.waitUntil(lambda: len(got) == 1, timeout=2000)
    assert got[0][0] == "build"
