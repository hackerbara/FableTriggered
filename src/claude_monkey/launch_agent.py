from __future__ import annotations

import os
import plistlib
import sys
from pathlib import Path

from .smoke import CommandResult, run_command

LAUNCH_AGENT_LABEL = "com.hackerbara.claude-monkey"


def render_plist(gui_executable: Path) -> bytes:
    return plistlib.dumps(
        {
            "Label": LAUNCH_AGENT_LABEL,
            "ProgramArguments": [str(gui_executable)],
            "RunAtLoad": True,
            "ProcessType": "Interactive",
        }
    )


def agent_plist_path(home: Path) -> Path:
    return home / "Library" / "LaunchAgents" / f"{LAUNCH_AGENT_LABEL}.plist"


def _gui_domain() -> str:
    return f"gui/{os.getuid()}"


def _ok_result(argv: list[str] | None = None) -> CommandResult:
    return CommandResult(argv=argv or [], returncode=0, stdout="", stderr="")


def install_agent(gui_executable: Path, home: Path, runner=run_command) -> CommandResult:
    plist = agent_plist_path(home)
    plist.parent.mkdir(parents=True, exist_ok=True)
    plist.write_bytes(render_plist(gui_executable))

    runner(["launchctl", "bootout", _gui_domain(), str(plist)])
    return runner(["launchctl", "bootstrap", _gui_domain(), str(plist)])


def uninstall_agent(home: Path, runner=run_command) -> CommandResult:
    plist = agent_plist_path(home)
    runner(["launchctl", "bootout", _gui_domain(), str(plist)])
    plist.unlink(missing_ok=True)
    return _ok_result(["launchctl", "bootout", _gui_domain(), str(plist)])


def gui_executable() -> Path:
    executable = Path(sys.executable).parent / "claude-monkey-menubar"
    if not executable.exists():
        raise FileNotFoundError(
            "claude-monkey-menubar console script not found next to Python "
            f"interpreter: {executable}"
        )
    return executable
