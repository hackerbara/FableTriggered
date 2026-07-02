from __future__ import annotations

import base64
import hashlib
import json
import os
import stat
from pathlib import Path
from time import time

from claude_monkey.shim import write_shim

OWNER_MARKER = "ClaudeMonkey managed shim"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def shim_digest(state_dir: Path) -> str:
    return sha256_bytes(_shim_bytes(state_dir))


def _shim_bytes(state_dir: Path) -> bytes:
    from claude_monkey.shim import render_shim_script

    return render_shim_script(str(state_dir)).encode("utf-8")


def describe_existing(path: Path) -> dict:
    if not path.exists() and not path.is_symlink():
        return {"previousType": "missing"}
    if path.is_symlink():
        return {"previousType": "symlink", "previousTarget": os.readlink(path)}
    data = path.read_bytes()
    return {
        "previousType": "file",
        "previousContentBase64": base64.b64encode(data).decode("ascii"),
        "previousMode": stat.S_IMODE(path.stat().st_mode),
    }


def install_shim_transaction(target_path: Path, state_dir: Path, dry_run: bool) -> Path:
    record_path = state_dir / "install-record.json"
    record = {
        "owner": OWNER_MARKER,
        "targetPath": str(target_path),
        "stateDir": str(state_dir),
        "timestamp": time(),
        "installedShimSha256": shim_digest(state_dir),
        **describe_existing(target_path),
    }
    if dry_run:
        return record_path
    state_dir.mkdir(parents=True, exist_ok=True)
    record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    tmp = target_path.with_suffix(target_path.suffix + ".claude-monkey.tmp")
    write_shim(tmp, state_dir)
    tmp.replace(target_path)
    return record_path


def current_target_is_installed_shim(target_path: Path, record: dict) -> bool:
    if target_path.is_symlink() or not target_path.exists():
        return False
    expected = record.get("installedShimSha256")
    return isinstance(expected, str) and sha256_bytes(target_path.read_bytes()) == expected


def restore_install_transaction(target_path: Path, record_path: Path, force: bool) -> bool:
    if not record_path.exists():
        return False
    record = json.loads(record_path.read_text())
    if record.get("owner") != OWNER_MARKER and not force:
        return False
    if record.get("targetPath") != str(target_path) and not force:
        return False
    if not force and not current_target_is_installed_shim(target_path, record):
        return False
    previous_type = record.get("previousType")
    if previous_type == "missing":
        target_path.unlink(missing_ok=True)
    elif previous_type == "symlink":
        target_path.unlink(missing_ok=True)
        target_path.symlink_to(record["previousTarget"])
    elif previous_type == "file":
        content = base64.b64decode(record["previousContentBase64"].encode("ascii"), validate=True)
        tmp = target_path.with_suffix(target_path.suffix + ".restore.tmp")
        tmp.write_bytes(content)
        tmp.chmod(int(record.get("previousMode", 0o755)))
        target_path.unlink(missing_ok=True)
        tmp.replace(target_path)
    else:
        return False
    return True


def use_official(current_path: Path, official_path: Path) -> None:
    current_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = current_path.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    tmp.symlink_to(official_path)
    tmp.replace(current_path)
