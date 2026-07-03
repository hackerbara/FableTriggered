from __future__ import annotations

import json
import os
import shutil
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from claude_monkey.config import ClaudeMonkeyConfig
from claude_monkey.paths import StatePaths


@dataclass(frozen=True)
class SourceIdentity:
    path: Path
    kind: str


def _resolve_existing_executable(candidate: str | Path | None) -> Path | None:
    if candidate is None:
        return None
    try:
        path = Path(candidate).expanduser().resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    if path.is_file() and os.access(path, os.X_OK):
        return path
    return None


def _relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def is_managed_launcher_path(path: Path, paths: StatePaths) -> bool:
    try:
        resolved = Path(path).expanduser().resolve(strict=True)
    except (OSError, RuntimeError):
        resolved = Path(path).expanduser().resolve(strict=False)

    managed_roots = [
        paths.bin_dir.resolve(strict=False),
        paths.versions_dir.resolve(strict=False),
    ]
    return any(_relative_to(resolved, root) for root in managed_roots)


def _is_current_launcher_path(path: str | Path | None, paths: StatePaths) -> bool:
    if path is None:
        return False
    try:
        candidate = Path(path).expanduser()
    except TypeError:
        return False
    if not candidate.is_absolute():
        candidate = candidate.resolve(strict=False)
    current = paths.current_path.expanduser()
    if not current.is_absolute():
        current = current.resolve(strict=False)
    return candidate == current


def _recorded_managed_target(paths: StatePaths) -> Path | None:
    record_path = paths.state_dir / "install-record.json"
    try:
        raw = json.loads(record_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict) or raw.get("owner") != "ClaudeMonkey managed shim":
        return None
    target = raw.get("targetPath")
    if not isinstance(target, str):
        return None
    try:
        return Path(target).expanduser().resolve(strict=True)
    except (OSError, RuntimeError):
        return Path(target).expanduser().resolve(strict=False)


def source_identity(path: str | Path | None, paths: StatePaths, kind: str) -> SourceIdentity | None:
    if _is_current_launcher_path(path, paths):
        return None
    resolved = _resolve_existing_executable(path)
    if resolved is None or is_managed_launcher_path(resolved, paths):
        return None
    recorded_target = _recorded_managed_target(paths)
    if recorded_target is not None and resolved == recorded_target:
        return None
    return SourceIdentity(path=resolved, kind=kind)


def discover_official_claude(
    config: ClaudeMonkeyConfig,
    paths: StatePaths,
    environ: Mapping[str, str] | None = None,
    which: Callable[[str], str | None] | None = None,
) -> Path | None:
    environ = os.environ if environ is None else environ
    which = shutil.which if which is None else which

    for candidate, kind in (
        (config.officialClaudePath, "config"),
        (environ.get("CLAUDE_MONKEY_SOURCE"), "env"),
        (which("claude"), "path"),
    ):
        identity = source_identity(candidate, paths, kind)
        if identity is not None:
            return identity.path
    return None
