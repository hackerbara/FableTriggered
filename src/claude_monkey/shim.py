from __future__ import annotations

from pathlib import Path


def render_shim_script(state_dir: str) -> str:
    return f'''#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

STATE_DIR = Path({state_dir!r})
CURRENT = STATE_DIR / "current"
CONFIG = STATE_DIR / "config.json"
PROMPT_FLAGS = {{
    "--system-prompt",
    "--system-prompt-file",
    "--append-system-prompt",
    "--append-system-prompt-file",
}}
MANAGEMENT = {{"--help", "-h", "--version", "update", "mcp", "plugin"}}


def is_management(argv):
    return bool(argv) and argv[0] in MANAGEMENT


def is_prompt_flag(arg):
    return arg in PROMPT_FLAGS or any(arg.startswith(flag + '=') for flag in PROMPT_FLAGS)


def has_prompt_flag(argv):
    return any(is_prompt_flag(arg) for arg in argv)


def active_prompt_args(argv):
    if (
        os.environ.get("CLAUDE_MONKEY_BYPASS") == "1"
        or is_management(argv)
        or has_prompt_flag(argv)
    ):
        return argv
    if not CONFIG.exists():
        return argv
    config = json.loads(CONFIG.read_text())
    profile_name = (
        config.get("profiles", {{}})
        .get(config.get("activeProfile", "default"), {{}})
        .get("prompt")
    )
    if not profile_name:
        return argv
    profile_path = STATE_DIR / "prompts" / (profile_name + ".json")
    if not profile_path.exists():
        return argv
    profile = json.loads(profile_path.read_text())
    mode = profile.get("mode", "append")
    source = profile["sourcePath"]
    flag = "--append-system-prompt-file" if mode == "append" else "--system-prompt-file"
    return [flag, source, *argv]


def main():
    argv = sys.argv[1:]
    target = (
        os.environ.get("CLAUDE_MONKEY_OFFICIAL")
        if os.environ.get("CLAUDE_MONKEY_BYPASS") == "1"
        else None
    )
    if target is None:
        if not CURRENT.exists():
            print("ClaudeMonkey: no active Claude binary at " + str(CURRENT), file=sys.stderr)
            print("Run: claude-monkey use-official or claude-monkey build", file=sys.stderr)
            return 127
        target = str(CURRENT.resolve())
    os.execv(target, [target, *active_prompt_args(argv)])

if __name__ == "__main__":
    raise SystemExit(main())
'''


def write_shim(path: Path, state_dir: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_shim_script(str(state_dir)))
    path.chmod(0o755)
