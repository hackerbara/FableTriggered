import plistlib
from pathlib import Path

from claude_monkey.launch_agent import (
    LAUNCH_AGENT_LABEL,
    agent_plist_path,
    install_agent,
    render_plist,
    uninstall_agent,
)


class FakeRunner:
    def __init__(self):
        self.calls = []

    def __call__(self, argv):
        self.calls.append(argv)
        return type("R", (), {"ok": True, "returncode": 0, "stdout": "", "stderr": ""})()


def test_render_plist_shape():
    data = plistlib.loads(render_plist(Path("/venv/bin/claude-monkey-menubar")))
    assert data["Label"] == LAUNCH_AGENT_LABEL
    assert data["ProgramArguments"] == ["/venv/bin/claude-monkey-menubar"]
    assert data["RunAtLoad"] is True
    assert data["ProcessType"] == "Interactive"


def test_install_agent_writes_plist_and_bootstraps(tmp_path):
    runner = FakeRunner()
    install_agent(Path("/venv/bin/claude-monkey-menubar"), home=tmp_path, runner=runner)
    plist = agent_plist_path(tmp_path)
    assert plist.exists()
    assert any(c[:2] == ["launchctl", "bootstrap"] for c in runner.calls)


def test_uninstall_agent_removes_plist(tmp_path):
    runner = FakeRunner()
    install_agent(Path("/x"), home=tmp_path, runner=runner)
    uninstall_agent(home=tmp_path, runner=runner)
    assert not agent_plist_path(tmp_path).exists()
    assert any(c[:2] == ["launchctl", "bootout"] for c in runner.calls)


def test_install_agent_is_idempotent(tmp_path):
    runner = FakeRunner()
    install_agent(Path("/x"), home=tmp_path, runner=runner)
    install_agent(Path("/x"), home=tmp_path, runner=runner)
    assert agent_plist_path(tmp_path).exists()
