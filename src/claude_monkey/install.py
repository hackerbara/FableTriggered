from __future__ import annotations

import json
import os
from pathlib import Path
from time import time

from claude_monkey.shim import write_shim

OWNER_MARKER = "ClaudeMonkey managed shim"


def describe_existing(path: Path) -> dict:
    if not path.exists() and not path.is_symlink():
        return {"previousType": "missing"}
    if path.is_symlink():
        return {"previousType": "symlink", "previousTarget": os.readlink(path)}
    return {"previousType": "file", "previousContent": path.read_text(errors="replace")}


def install_shim_transaction(target_path: Path, state_dir: Path, dry_run: bool) -> Path:
    state_dir.mkdir(parents=True, exist_ok=True)
    record_path = state_dir / "install-record.json"
    record = {
        "owner": OWNER_MARKER,
        "targetPath": str(target_path),
        "stateDir": str(state_dir),
        "timestamp": time(),
        **describe_existing(target_path),
    }
    if not dry_run:
        tmp = target_path.with_suffix(target_path.suffix + ".claude-monkey.tmp")
        write_shim(tmp, state_dir)
        tmp.replace(target_path)
    record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return record_path


def restore_install_transaction(target_path: Path, record_path: Path, force: bool) -> bool:
    if not record_path.exists():
        return False
    record = json.loads(record_path.read_text())
    if record.get("owner") != OWNER_MARKER and not force:
        return False
    previous_type = record.get("previousType")
    if previous_type == "missing":
        target_path.unlink(missing_ok=True)
    elif previous_type == "symlink":
        target_path.unlink(missing_ok=True)
        target_path.symlink_to(record["previousTarget"])
    elif previous_type == "file":
        target_path.write_text(record["previousContent"])
    else:
        return False
    return True


def use_official(current_path: Path, official_path: Path) -> None:
    current_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = current_path.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    tmp.symlink_to(official_path)
    tmp.replace(current_path)
