"""Tests for the Qt application shell in claude_monkey.gui.app.

Covers the pieces that exist ahead of Task 19's wiring: root refusal,
single-instance detection via QLocalServer, and the CommandBridge signal
plumbing that lets a worker thread deliver progress events across to the Qt
event loop.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from claude_monkey.gui.app import CommandBridge, SingleInstance, refuse_root  # noqa: E402


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
