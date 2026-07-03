from __future__ import annotations

import json
import queue
import subprocess
import threading
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

MAX_CAPTURE_CHARS = 120_000
MAX_LOG_STDERR_CHARS = 2_000


class MutatingCommandBusy(RuntimeError):
    pass


class CommandRunner:
    def __init__(
        self,
        *,
        cli_argv: list[str] | None = None,
        logs_dir: Path,
        run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ) -> None:
        self.cli_argv = list(cli_argv or ["claude-monkey"])
        self.logs_dir = logs_dir
        self.run = run
        self._mutating_lock = threading.Lock()
        self._busy_for_test = False
        self._results: queue.Queue[tuple[str, dict[str, Any]]] = queue.Queue()
        self.logs_dir.mkdir(parents=True, exist_ok=True)

    @property
    def log_path(self) -> Path:
        return self.logs_dir / "menubar.log"

    def mark_busy_for_test(self) -> None:
        self._busy_for_test = True

    def clear_busy_for_test(self) -> None:
        self._busy_for_test = False

    def post_result_for_test(self, name: str, payload: dict[str, Any]) -> None:
        self._results.put((name, payload))

    def drain_results(self) -> list[tuple[str, dict[str, Any]]]:
        items: list[tuple[str, dict[str, Any]]] = []
        while True:
            try:
                items.append(self._results.get_nowait())
            except queue.Empty:
                break
        return items

    def _log(self, command: list[str], returncode: int, stderr: str) -> None:
        stamp = datetime.now(UTC).isoformat()
        line = json.dumps(
            {
                "timestamp": stamp,
                "command": command,
                "returncode": returncode,
                "stderr": stderr[:MAX_LOG_STDERR_CHARS],
            },
            sort_keys=True,
        )
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def run_json(self, args: list[str], *, mutating: bool) -> dict[str, Any]:
        if self._busy_for_test and mutating:
            raise MutatingCommandBusy("another mutating command is running")

        acquired = False
        if mutating:
            acquired = self._mutating_lock.acquire(blocking=False)
            if not acquired:
                raise MutatingCommandBusy("another mutating command is running")

        try:
            argv = [*self.cli_argv, *args]
            result = self.run(
                argv,
                shell=False,
                capture_output=True,
                text=True,
                check=False,
            )
            stdout = (result.stdout or "")[:MAX_CAPTURE_CHARS]
            stderr = (result.stderr or "")[:MAX_CAPTURE_CHARS]
            self._log(argv, int(result.returncode), stderr)
            if stdout.strip():
                try:
                    payload = json.loads(stdout)
                except json.JSONDecodeError:
                    payload = None
                if isinstance(payload, dict):
                    return payload
            if result.returncode != 0:
                message = stderr.strip() or f"command exited {result.returncode}"
                return {
                    "schemaVersion": 1,
                    "ok": False,
                    "status": "error",
                    "summary": message,
                    "reportPath": None,
                    "targetPath": None,
                    "authorizationRequired": False,
                    "authorizationMethod": None,
                    "dryRun": False,
                    "plannedActions": [],
                    "error": {"message": message, "code": "command_failed"},
                }
            raise ValueError("command succeeded but did not emit JSON")
        finally:
            if acquired:
                self._mutating_lock.release()

    def open_path(self, path: Path) -> None:
        expanded = path.expanduser()
        result = self.run(
            ["open", str(expanded)],
            shell=False,
            capture_output=True,
            text=True,
            check=False,
        )
        self._log(["open", str(expanded)], int(result.returncode), result.stderr or "")

    def run_background(self, name: str, args: list[str], *, mutating: bool) -> None:
        def worker() -> None:
            try:
                payload = self.run_json(args, mutating=mutating)
            except Exception as exc:
                payload = {
                    "schemaVersion": 1,
                    "ok": False,
                    "status": "error",
                    "summary": str(exc),
                    "reportPath": None,
                    "targetPath": None,
                    "authorizationRequired": False,
                    "authorizationMethod": None,
                    "dryRun": False,
                    "plannedActions": [],
                    "error": {"message": str(exc), "code": "command_failed"},
                }
            self._results.put((name, payload))

        threading.Thread(target=worker, daemon=True).start()
