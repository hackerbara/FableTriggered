from __future__ import annotations

import base64
import hashlib
import json
import os
import stat
from pathlib import Path
from time import time

from claude_monkey import authorization
from claude_monkey.shim import write_shim

OWNER_MARKER = "ClaudeMonkey managed shim"


class ProtectedTargetRestoreUnavailable(RuntimeError):
    pass


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


def _existing_managed_record(record_path: Path, target_path: Path) -> dict | None:
    if not record_path.exists():
        return None
    try:
        record = json.loads(record_path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(record, dict):
        return None
    if record.get("targetPath") != str(target_path):
        return None
    try:
        if current_target_is_installed_shim(target_path, record):
            return record
    except OSError:
        return None
    return None


def _cache_previous_source(target_path: Path, state_dir: Path) -> dict:
    if not (target_path.exists() or target_path.is_symlink()):
        return {}
    try:
        source_path = target_path.resolve(strict=True)
    except OSError:
        return {}
    if not source_path.is_file() or not os.access(source_path, os.X_OK):
        return {}
    data = source_path.read_bytes()
    digest = sha256_bytes(data)
    cache_path = state_dir / "sources" / digest / "claude"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    if not cache_path.exists():
        cache_path.write_bytes(data)
        cache_path.chmod(stat.S_IMODE(source_path.stat().st_mode) | 0o755)
    return {
        "sourcePath": str(source_path),
        "previousResolvedPath": str(source_path),
        "previousSourceCachePath": str(cache_path),
        "previousSourceSha256": digest,
        "previousSourceSizeBytes": len(data),
    }


def clean_source_from_install_record(target_path: Path, record_path: Path) -> Path | None:
    record = _existing_managed_record(record_path, target_path)
    if record is None:
        return None
    cache_raw = record.get("previousSourceCachePath")
    expected_sha = record.get("previousSourceSha256")
    if isinstance(cache_raw, str) and isinstance(expected_sha, str):
        cache_path = Path(cache_raw)
        try:
            if (
                cache_path.is_file()
                and os.access(cache_path, os.X_OK)
                and sha256_bytes(cache_path.read_bytes()) == expected_sha
            ):
                return cache_path
        except OSError:
            pass
    previous_target = record.get("previousTarget")
    if isinstance(previous_target, str):
        try:
            resolved = Path(previous_target).expanduser().resolve(strict=True)
        except OSError:
            return None
        if resolved.is_file() and os.access(resolved, os.X_OK):
            return resolved
    return None


def _privileged_mkdir(path: Path) -> None:
    authorization.run_privileged_argv(
        ["/bin/mkdir", "-p", str(path)],
        reason=f"ClaudeMonkey needs permission to create {path}",
    )


def _privileged_replace(tmp_path: Path, target_path: Path) -> None:
    authorization.run_privileged_argv(
        ["/bin/mv", "-f", str(tmp_path), str(target_path)],
        reason=f"ClaudeMonkey needs permission to update {target_path}",
    )


def _privileged_remove(target_path: Path) -> None:
    authorization.run_privileged_argv(
        ["/bin/rm", "-f", str(target_path)],
        reason=f"ClaudeMonkey needs permission to restore {target_path}",
    )


def _write_shim_to_target(target_path: Path, state_dir: Path) -> None:
    if authorization.target_needs_authorization(target_path):
        tmp = state_dir / (target_path.name + ".claude-monkey.tmp")
        write_shim(tmp, state_dir)
        _privileged_mkdir(target_path.parent)
        _privileged_replace(tmp, target_path)
        return
    tmp = target_path.with_suffix(target_path.suffix + ".claude-monkey.tmp")
    write_shim(tmp, state_dir)
    tmp.replace(target_path)


def _install_tmp_candidates(target_path: Path, state_dir: Path) -> tuple[Path, ...]:
    return (
        state_dir / (target_path.name + ".claude-monkey.tmp"),
        target_path.with_suffix(target_path.suffix + ".claude-monkey.tmp"),
    )


def protected_install_requires_refusal(target_path: Path, record_path: Path) -> bool:
    if not authorization.target_needs_authorization(target_path):
        return False
    if not target_path.exists() and not target_path.is_symlink():
        return False
    if record_path.exists():
        try:
            record = json.loads(record_path.read_text())
        except (OSError, json.JSONDecodeError):
            record = None
        if isinstance(record, dict) and current_target_is_installed_shim(target_path, record):
            return False
    return True


def install_shim_transaction(target_path: Path, state_dir: Path, dry_run: bool) -> Path:
    record_path = state_dir / "install-record.json"
    if protected_install_requires_refusal(target_path, record_path):
        raise ProtectedTargetRestoreUnavailable(
            f"refusing to overwrite protected existing target without safe restore: {target_path}"
        )
    existing_record = _existing_managed_record(record_path, target_path)
    previous = (
        {
            key: value
            for key, value in existing_record.items()
            if key.startswith("previous")
        }
        if existing_record is not None
        else describe_existing(target_path)
    )
    if not dry_run:
        state_dir.mkdir(parents=True, exist_ok=True)
        if existing_record is None:
            previous.update(_cache_previous_source(target_path, state_dir))
    record = {
        "owner": OWNER_MARKER,
        "targetPath": str(target_path),
        "stateDir": str(state_dir),
        "timestamp": time(),
        "installedShimSha256": shim_digest(state_dir),
        **previous,
    }
    if dry_run:
        return record_path
    record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    try:
        _write_shim_to_target(target_path, state_dir)
    except Exception:
        record_path.unlink(missing_ok=True)
        for tmp in _install_tmp_candidates(target_path, state_dir):
            tmp.unlink(missing_ok=True)
        raise
    return record_path


def current_target_is_installed_shim(target_path: Path, record: dict) -> bool:
    if target_path.is_symlink() or not target_path.exists():
        return False
    state_dir = record.get("stateDir")
    if not isinstance(state_dir, str):
        return False
    expected = shim_digest(Path(state_dir))
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
    needs_authorization = authorization.target_needs_authorization(target_path)
    if needs_authorization:
        if previous_type not in {"missing", "symlink", "file"}:
            return False
        # The install record lives in the user-writable state directory. For a
        # protected target, do not let that mutable record drive elevated writes
        # of file bytes or symlink destinations. The narrow privileged operation
        # for protected uninstall is remove-only; richer restore can be added
        # later with integrity protected prior-payload storage.
        _privileged_remove(target_path)
        return True
    if previous_type == "missing":
        target_path.unlink(missing_ok=True)
    elif previous_type == "symlink":
        tmp = record_path.parent / (target_path.name + ".restore.symlink.tmp")
        tmp.unlink(missing_ok=True)
        tmp.symlink_to(record["previousTarget"])
        try:
            tmp.replace(target_path)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise
    elif previous_type == "file":
        content = base64.b64decode(record["previousContentBase64"].encode("ascii"), validate=True)
        tmp = (
            record_path.parent / (target_path.name + ".restore.tmp")
            if needs_authorization
            else target_path.with_suffix(target_path.suffix + ".restore.tmp")
        )
        tmp.write_bytes(content)
        tmp.chmod(int(record.get("previousMode", 0o755)))
        try:
            tmp.replace(target_path)
        except Exception:
            tmp.unlink(missing_ok=True)
            raise
    else:
        return False
    return True


def use_official(current_path: Path, official_path: Path) -> None:
    current_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = current_path.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    tmp.symlink_to(official_path)
    tmp.replace(current_path)
