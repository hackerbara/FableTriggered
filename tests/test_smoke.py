from __future__ import annotations

from claude_monkey.smoke import (
    CommandResult,
    codesign_verify,
    run_command,
    smoke_version_and_help,
)


def test_smoke_runner_records_commands(tmp_path):
    binary = tmp_path / "claude"
    binary.write_text("fake")
    calls = []

    def runner(argv):
        calls.append(argv)
        return CommandResult(argv=argv, returncode=0, stdout="ok", stderr="")

    results = smoke_version_and_help(binary, runner)
    assert [r.argv[-1] for r in results] == ["--version", "--help"]
    assert calls[0] == [str(binary), "--version"]


def test_codesign_verify_records_expected_command(tmp_path):
    binary = tmp_path / "claude"
    binary.write_text("fake")

    def runner(argv):
        return CommandResult(argv=argv, returncode=0, stdout="", stderr="valid")

    result = codesign_verify(binary, runner)
    assert result.argv == [
        "codesign",
        "--verify",
        "--deep",
        "--strict",
        "--verbose=4",
        str(binary),
    ]


def test_run_command_timeout_returns_failure_result():
    result = run_command(["python3", "-c", "import time; time.sleep(2)"], timeout_seconds=0.01)
    assert result.returncode == 124
    assert "timed out" in result.stderr
