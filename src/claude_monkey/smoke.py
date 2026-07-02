from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

DEFAULT_TIMEOUT_SECONDS = 15.0
TIMEOUT_RETURN_CODE = 124


@dataclass(frozen=True)
class CommandResult:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str


def run_command(argv: list[str], timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS) -> CommandResult:
    try:
        proc = subprocess.run(
            argv,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        message = f"command timed out after {timeout_seconds} seconds"
        stderr = f"{stderr}\n{message}" if stderr else message
        return CommandResult(
            argv=argv,
            returncode=TIMEOUT_RETURN_CODE,
            stdout=stdout,
            stderr=stderr,
        )
    return CommandResult(
        argv=argv, returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr
    )


def smoke_version_and_help(binary: Path, runner=run_command) -> list[CommandResult]:
    return [runner([str(binary), "--version"]), runner([str(binary), "--help"])]


def codesign_sign(binary: Path, runner=run_command) -> CommandResult:
    return runner(["codesign", "--force", "--sign", "-", str(binary)])


def codesign_verify(binary: Path, runner=run_command) -> CommandResult:
    return runner(["codesign", "--verify", "--deep", "--strict", "--verbose=4", str(binary)])
