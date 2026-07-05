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


def test_render_plist_shape(tmp_path):
    data = plistlib.loads(render_plist(Path("/venv/bin/claude-monkey-menubar"), home=tmp_path))
    assert data["Label"] == LAUNCH_AGENT_LABEL
    assert data["ProgramArguments"] == ["/venv/bin/claude-monkey-menubar"]
    assert data["RunAtLoad"] is True
    assert data["ProcessType"] == "Interactive"


def test_render_plist_logs_stdout_and_stderr_to_state_dir(tmp_path):
    """BUG 2 regression: a bare-environment launchd launch that dies before the
    menubar app can open its own log leaves zero diagnostics. Redirect launchd's
    own stdout/stderr capture to a file under the real (expanded) home passed
    in -- never a literal '~', which launchd will not expand."""
    data = plistlib.loads(render_plist(Path("/venv/bin/claude-monkey-menubar"), home=tmp_path))
    expected_log = str(tmp_path / ".claude-monkey" / "logs" / "menubar.launchd.log")
    assert data["StandardOutPath"] == expected_log
    assert data["StandardErrorPath"] == expected_log
    assert "~" not in data["StandardOutPath"]


def test_install_agent_writes_plist_and_bootstraps(tmp_path):
    runner = FakeRunner()
    install_agent(Path("/venv/bin/claude-monkey-menubar"), home=tmp_path, runner=runner)
    plist = agent_plist_path(tmp_path)
    assert plist.exists()
    assert any(c[:2] == ["launchctl", "bootstrap"] for c in runner.calls)


def test_install_agent_creates_logs_dir_before_bootstrap(tmp_path):
    """BUG 2: the logs dir must exist before launchd bootstraps the agent, or
    launchd's StandardOutPath/StandardErrorPath redirection has nowhere to
    write and silently fails."""
    runner = FakeRunner()
    install_agent(Path("/venv/bin/claude-monkey-menubar"), home=tmp_path, runner=runner)
    logs_dir = tmp_path / ".claude-monkey" / "logs"
    assert logs_dir.is_dir()


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
