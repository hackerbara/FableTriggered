from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CommandResult:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str


def run_command(argv: list[str]) -> CommandResult:
    proc = subprocess.run(argv, text=True, capture_output=True, check=False)
    return CommandResult(
        argv=argv, returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr
    )


def smoke_version_and_help(binary: Path, runner=run_command) -> list[CommandResult]:
    return [runner([str(binary), "--version"]), runner([str(binary), "--help"])]


def codesign_verify(binary: Path, runner=run_command) -> CommandResult:
    return runner(["codesign", "--verify", "--deep", "--strict", "--verbose=4", str(binary)])
