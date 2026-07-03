from __future__ import annotations

import json
import sys

from claude_monkey.menubar_commands import CommandRunner, MutatingCommandBusy


def test_runner_uses_argv_list_and_shell_false(tmp_path):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))

        class Result:
            returncode = 0
            stdout = json.dumps(
                {
                    "schemaVersion": 1,
                    "ok": True,
                    "status": "ok",
                    "summary": "ok",
                    "reportPath": None,
                    "dryRun": False,
                    "plannedActions": [],
                    "error": None,
                }
            )
            stderr = ""

        return Result()

    runner = CommandRunner(
        cli_argv=[sys.executable, "-m", "claude_monkey"], logs_dir=tmp_path, run=fake_run
    )
    runner.run_json(["status", "--json"], mutating=False)
    argv, kwargs = calls[0]
    assert isinstance(argv, list)
    assert kwargs["shell"] is False
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True


def test_mutating_commands_are_serialized(tmp_path):
    runner = CommandRunner(cli_argv=["claude-monkey"], logs_dir=tmp_path, run=lambda *a, **k: None)
    runner.mark_busy_for_test()
    try:
        try:
            runner.run_json(["enable", "x", "--json"], mutating=True)
        except MutatingCommandBusy:
            pass
        else:
            raise AssertionError("expected busy")
    finally:
        runner.clear_busy_for_test()


def test_worker_queue_boundary(tmp_path):
    runner = CommandRunner(cli_argv=[sys.executable, "-c"], logs_dir=tmp_path)
    runner.post_result_for_test("refresh", {"ok": True})
    assert runner.drain_results() == [("refresh", {"ok": True})]


def test_open_path_does_not_prefix_claude_monkey(tmp_path):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))

        class Result:
            returncode = 0
            stdout = ""
            stderr = ""

        return Result()

    runner = CommandRunner(cli_argv=["claude-monkey"], logs_dir=tmp_path, run=fake_run)
    runner.open_path(tmp_path / "logs")
    argv, kwargs = calls[0]
    assert argv == ["open", str(tmp_path / "logs")]
    assert kwargs["shell"] is False


def test_nonzero_json_error_envelope_is_preserved(tmp_path):
    def fake_run(argv, **kwargs):
        class Result:
            returncode = 1
            stdout = json.dumps(
                {
                    "schemaVersion": 1,
                    "ok": False,
                    "status": "error",
                    "summary": "authorization denied",
                    "reportPath": None,
                    "targetPath": "/usr/local/bin/claude",
                    "authorizationRequired": True,
                    "authorizationMethod": "macos_gui",
                    "dryRun": False,
                    "plannedActions": [],
                    "error": {
                        "message": "authorization denied",
                        "code": "authorization_denied",
                    },
                }
            )
            stderr = ""

        return Result()

    runner = CommandRunner(cli_argv=["claude-monkey"], logs_dir=tmp_path, run=fake_run)
    payload = runner.run_json(
        ["install-shim", "--target", "/usr/local/bin/claude", "--json"], mutating=True
    )
    assert payload["error"]["code"] == "authorization_denied"
    assert payload["authorizationRequired"] is True
    assert payload["targetPath"] == "/usr/local/bin/claude"


def test_default_runner_bounds_subprocess_output_before_error_envelope(
    monkeypatch, tmp_path
):
    monkeypatch.setattr("claude_monkey.menubar_commands.MAX_CAPTURE_CHARS", 32)
    runner = CommandRunner(cli_argv=[sys.executable, "-c"], logs_dir=tmp_path)

    payload = runner.run_json(
        ["import sys; sys.stderr.write('x' * 10_000); sys.exit(1)"], mutating=False
    )

    assert payload["error"]["code"] == "command_failed"
    assert payload["error"]["message"] == "x" * 32
    logged = json.loads(runner.log_path.read_text().splitlines()[-1])
    assert logged["stderr"] == "x" * 32
