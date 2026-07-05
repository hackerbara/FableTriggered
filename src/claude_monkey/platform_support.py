from __future__ import annotations

import os
import sys
from collections.abc import Mapping
from pathlib import Path

# Standard Windows executable extensions, used only as a fallback when PATHEXT
# is unset. Lowercase, dot-prefixed.
_WINDOWS_EXECUTABLE_EXTS = (".exe", ".com", ".bat", ".cmd")


def is_windows() -> bool:
    return sys.platform == "win32"


def claude_executable_name() -> str:
    """The on-disk name of the official Claude binary for this platform."""
    return "claude.exe" if is_windows() else "claude"


def default_state_dir(environ: Mapping[str, str] | None = None) -> Path:
    """ClaudeMonkey's per-user state root.

    Windows: %LOCALAPPDATA%\\ClaudeMonkey (idiomatic), with %APPDATA% then a
    %USERPROFILE%-derived path as fallbacks. Elsewhere: $HOME/.claude-monkey,
    preserving the historical HOME-first lookup byte-for-byte.
    """
    environ = os.environ if environ is None else environ
    if is_windows():
        base = environ.get("LOCALAPPDATA") or environ.get("APPDATA")
        if base:
            return Path(base) / "ClaudeMonkey"
        userprofile = environ.get("USERPROFILE")
        if userprofile:
            return Path(userprofile) / "AppData" / "Local" / "ClaudeMonkey"
        return Path.home() / "AppData" / "Local" / "ClaudeMonkey"
    home = environ.get("HOME", str(Path.home()))
    return Path(home) / ".claude-monkey"


def is_executable_file(path: Path) -> bool:
    """Whether `path` is a runnable program file.

    On Windows `os.access(path, os.X_OK)` degenerates to an existence check
    (it ignores the executable concept), so it would 'fail open' on any file.
    Gate on a real executable extension instead (PATHEXT, or a sane fallback).
    Elsewhere, use the POSIX executable bit.
    """
    if not path.is_file():
        return False
    if is_windows():
        raw = os.environ.get("PATHEXT", "")
        exts = [e.strip().lower() for e in raw.split(os.pathsep) if e.strip()]
        if not exts:
            exts = list(_WINDOWS_EXECUTABLE_EXTS)
        return path.suffix.lower() in exts
    return os.access(path, os.X_OK)


def windows_claude_install_candidates(environ: Mapping[str, str] | None = None) -> list[Path]:
    """Standard native-Windows locations for the official claude.exe.

    Per the port research: launcher stub at %USERPROFILE%\\.local\\bin\\claude.exe,
    versioned real binaries under %USERPROFILE%\\.local\\share\\claude\\versions\\.
    Best-effort: returns paths that may or may not exist; callers validate.
    """
    environ = os.environ if environ is None else environ
    userprofile = environ.get("USERPROFILE")
    base = Path(userprofile) if userprofile else Path.home()
    candidates: list[Path] = [base / ".local" / "bin" / "claude.exe"]
    versions = base / ".local" / "share" / "claude" / "versions"
    try:
        subdirs = sorted((p for p in versions.iterdir() if p.is_dir()), reverse=True)
    except OSError:
        subdirs = []
    for d in subdirs:
        exe = d / "claude.exe"
        if exe.exists():
            candidates.append(exe)
    return candidates
