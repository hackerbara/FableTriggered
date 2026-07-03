from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform as platform_module
import shutil
import sys
from pathlib import Path
from typing import Any

from claude_monkey import __version__
from claude_monkey.authorization import (
    AuthorizationDenied,
    AuthorizationRequired,
    authorization_method_for_target,
    target_needs_authorization,
)
from claude_monkey.binary_inspect import inspect_binary_bytes
from claude_monkey.builder_v15 import (
    BuildRequestV15,
    ValidationRequestV15,
    build_patchset_v15,
    validate_package,
)
from claude_monkey.cli_json import envelope_error, envelope_ok, print_json, to_jsonable
from claude_monkey.config import LaunchProfile, load_config, save_config
from claude_monkey.install import (
    ProtectedTargetRestoreUnavailable,
    clean_source_from_install_record,
    current_target_is_installed_shim,
    install_shim_transaction,
    protected_install_requires_refusal,
    restore_install_transaction,
    use_official,
)
from claude_monkey.paths import StatePaths, default_paths
from claude_monkey.smoke import run_command


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="claude-monkey")
    parser.add_argument("--version", action="store_true", help="print ClaudeMonkey version")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("doctor")
    list_patches = sub.add_parser("list-patches")
    list_patches.add_argument("--json", action="store_true")
    status = sub.add_parser("status")
    status.add_argument("--json", action="store_true")
    enable = sub.add_parser("enable")
    enable.add_argument("--json", action="store_true")
    enable.add_argument("patch_id")
    disable = sub.add_parser("disable")
    disable.add_argument("--json", action="store_true")
    disable.add_argument("patch_id")
    list_prompts = sub.add_parser("list-prompts")
    list_prompts.add_argument("--json", action="store_true")
    set_prompt = sub.add_parser("set-prompt")
    set_prompt.add_argument("--json", action="store_true")
    set_prompt.add_argument("prompt")
    set_prompt.add_argument("--id", default="default")
    set_prompt.add_argument("--name")
    set_prompt.add_argument("--mode", choices=("append", "replace"), default="append")
    set_prompt.add_argument("--from-file", action="store_true")
    clear_prompt = sub.add_parser("clear-prompt")
    clear_prompt.add_argument("--json", action="store_true")

    inspect_binary = sub.add_parser("inspect-binary")
    inspect_binary.add_argument("--source", required=True)
    inspect_binary.add_argument("--json", action="store_true")

    validate = sub.add_parser("validate-package")
    validate.add_argument("--source", required=True)
    validate.add_argument("--package", required=True)
    validate.add_argument("--source-version", required=True)
    validate.add_argument("--source-version-output", required=True)
    validate.add_argument("--platform", default=sys.platform)
    validate.add_argument("--arch", default=platform_module.machine() or "unknown")
    validate.add_argument("--json", action="store_true")

    build = sub.add_parser("build")
    build.add_argument("--source")
    build.add_argument("--package", action="append", dest="packages")
    build.add_argument("--output-dir")
    build.add_argument("--source-version")
    build.add_argument("--source-version-output")
    build.add_argument("--platform", default=sys.platform)
    build.add_argument("--arch", default=platform_module.machine() or "unknown")
    build.add_argument("--skip-signing", action="store_true")
    build.add_argument("--skip-smoke", action="store_true")
    build.add_argument("--json", action="store_true")
    build.add_argument("--dry-run", action="store_true")
    build.add_argument("--activate", action="store_true")

    install = sub.add_parser("install-shim")
    install.add_argument("--target")
    install.add_argument("--state-dir")
    install.add_argument("--dry-run", action="store_true")
    install.add_argument("--json", action="store_true")

    uninstall = sub.add_parser("uninstall-shim")
    uninstall.add_argument("--target")
    uninstall.add_argument("--state-dir")
    uninstall.add_argument("--record")
    uninstall.add_argument("--force", action="store_true")
    uninstall.add_argument("--dry-run", action="store_true")
    uninstall.add_argument("--json", action="store_true")

    rollback = sub.add_parser("rollback")
    rollback.add_argument("--target")
    rollback.add_argument("--state-dir")
    rollback.add_argument("--record")
    rollback.add_argument("--force", action="store_true")
    rollback.add_argument("--dry-run", action="store_true")
    rollback.add_argument("--json", action="store_true")

    official = sub.add_parser("use-official")
    official.add_argument("--official")
    official.add_argument("--json", action="store_true")
    return parser


def active_profile(config):
    return config.profiles.setdefault("default", LaunchProfile())


def emit(
    args: argparse.Namespace, text: str, payload: Any | None = None, *, error: bool = False
) -> int:
    if getattr(args, "json", False):
        print_json(payload if payload is not None else envelope_ok(text))
    else:
        print(text, file=sys.stderr if error else sys.stdout)
    return 0


def _read_json_file(path: Path) -> dict[str, Any] | None:
    try:
        if not path.exists():
            return None
        raw = json.loads(path.read_text())
        return raw if isinstance(raw, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _latest_build_report(active_patch_set: str | None) -> tuple[Path | None, dict[str, Any] | None]:
    if not active_patch_set:
        return None, None
    patch_set_path = Path(active_patch_set).expanduser()
    if not patch_set_path.is_absolute():
        patch_set_path = patch_set_path.resolve()
    report_path = patch_set_path / "build-report.json"
    report = _read_json_file(report_path)
    return (report_path, report) if report is not None else (None, None)


def _display_patch_set(active_patch_set: str | None) -> str | None:
    if not active_patch_set:
        return None
    patch_set_path = Path(active_patch_set).expanduser()
    if not patch_set_path.is_absolute():
        patch_set_path = patch_set_path.resolve()
    return str(patch_set_path)


def _active_patch_ids_from_report(report: dict[str, Any] | None) -> list[str]:
    if not report:
        return []
    for key in ("enabledPatches", "patchIds", "activePatchIds"):
        value = report.get(key)
        if isinstance(value, list):
            return [str(item) for item in value]
    return []


def _safe_resolve(path: Path) -> str:
    try:
        return str(path.resolve())
    except OSError:
        return str(path)


def _current_executable_path(current_path: Path) -> str | None:
    try:
        if not (current_path.exists() or current_path.is_symlink()):
            return None
        resolved = current_path.resolve(strict=True)
    except OSError:
        return None
    return str(resolved) if resolved.is_file() and os.access(resolved, os.X_OK) else None


def _install_record_path(paths: StatePaths) -> Path:
    return paths.state_dir / "install-record.json"


def _shim_target_from_record(record_path: Path) -> str | None:
    record = _read_json_file(record_path)
    if not record:
        return None
    target = record.get("targetPath")
    return target if isinstance(target, str) else None


def _shim_record(record_path: Path) -> dict[str, Any] | None:
    return _read_json_file(record_path)


def _shim_is_installed(record_path: Path) -> bool:
    record = _shim_record(record_path)
    if not record:
        return False
    target = record.get("targetPath")
    try:
        return isinstance(target, str) and current_target_is_installed_shim(Path(target), record)
    except OSError:
        return False


def _status_payload(paths: StatePaths, config) -> dict[str, Any]:
    profile = active_profile(config)
    desired = list(profile.patches)
    report_path, report = _latest_build_report(config.activePatchSet)
    active = _active_patch_ids_from_report(report)
    install_record = _install_record_path(paths)
    current_executable = _current_executable_path(paths.current_path)
    shim_installed = _shim_is_installed(install_record)
    if config.installMode == "shim":
        installed = shim_installed
    else:
        installed = current_executable is not None or shim_installed
    runnable = current_executable is not None
    active_report_missing = config.activePatchSet is not None and report is None
    rebuild_required = desired != active or active_report_missing or (installed and not runnable)
    if not installed:
        status = "not_installed"
    elif rebuild_required or not runnable:
        status = "rebuild_required"
    else:
        status = "ok"
    build_strategy = (
        (report or {}).get("buildStrategy") or (report or {}).get("engine") or "unknown"
    )
    detected_command = _detected_claude_command_path()
    return {
        "schemaVersion": 1,
        "status": status,
        "sourceClaudeVersion": (report or {}).get("sourceVersion"),
        "sourceClaudePath": (report or {}).get("sourceClaudePath"),
        "detectedClaudeCommandPath": str(detected_command) if detected_command else None,
        "installMode": config.installMode,
        "shimInstalled": shim_installed,
        "activeProfile": config.activeProfile,
        "activePrompt": profile.prompt,
        "desiredPatchIds": desired,
        "activePatchIds": active,
        "rebuildRequired": rebuild_required,
        "latestBuildReportPath": str(report_path) if report_path is not None else None,
        "activePatchSet": _display_patch_set(config.activePatchSet),
        "currentClaudePath": current_executable,
        "shimTargetPath": _shim_target_from_record(install_record) if shim_installed else None,
        "installRecordPath": str(install_record) if shim_installed else None,
        "buildStrategy": build_strategy,
        "lastBuildStrategy": build_strategy,
        "changedModules": (report or {}).get("changedModules", []),
        "repackSummary": (report or {}).get("repackSummary"),
        "stateDir": str(paths.state_dir),
        "logsDir": str(paths.logs_dir),
        "lastError": None,
    }


def _patch_label(patch_json: Path) -> str:
    raw = _read_json_file(patch_json) or {}
    return str(raw.get("name") or raw.get("label") or patch_json.parent.name)


def _patch_label_from_raw(raw: dict[str, Any], patch_json: Path) -> str:
    return str(raw.get("name") or raw.get("label") or patch_json.parent.name)


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _source_identity_for_patch_status() -> dict[str, Any] | None:
    source = _discover_source(None)
    if source is None or not source.exists():
        return None
    version_output = _source_version_output(source, None)
    version = _source_version(None, version_output)
    if version_output is None or version is None:
        return None
    try:
        size_bytes = source.stat().st_size
    except OSError:
        return None
    return {
        "path": source,
        "claudeVersion": version,
        "versionOutput": version_output,
        "sizeBytes": size_bytes,
        "platform": sys.platform,
        "arch": platform_module.machine() or "unknown",
    }


def _source_status_sha256(source: dict[str, Any]) -> str | None:
    sha = source.get("sha256")
    if isinstance(sha, str):
        return sha
    path = source.get("path")
    if not isinstance(path, Path):
        return None
    try:
        sha = _file_sha256(path)
    except OSError:
        return None
    source["sha256"] = sha
    return sha


def _target_source_identities(raw: dict[str, Any]) -> list[dict[str, Any]]:
    targets = raw.get("targets", [])
    if not isinstance(targets, list):
        return []
    identities: list[dict[str, Any]] = []
    for target in targets:
        if not isinstance(target, dict):
            continue
        identity = target.get("sourceIdentity")
        if isinstance(identity, dict):
            identities.append(identity)
    return identities


def _target_versions(identities: list[dict[str, Any]]) -> str:
    versions = sorted(
        {
            str(identity.get("claudeVersion"))
            for identity in identities
            if identity.get("claudeVersion")
        }
    )
    return ", ".join(versions) if versions else "unknown"


def _patch_compatibility(
    raw: dict[str, Any], source: dict[str, Any] | None
) -> tuple[str, str | None]:
    identities = _target_source_identities(raw)
    if not identities:
        return "unknown", "Patch manifest has no source identity target."
    if source is None:
        return "unknown", "No current Claude source was found to check compatibility."

    current_version = str(source["claudeVersion"])
    same_version = [
        identity
        for identity in identities
        if str(identity.get("claudeVersion")) == current_version
    ]
    if not same_version:
        return (
            "version_mismatch",
            f"Package targets Claude {_target_versions(identities)}; "
            f"current source is {current_version}.",
        )

    current_size = int(source["sizeBytes"])
    for identity in same_version:
        target_size = identity.get("sizeBytes")
        if isinstance(target_size, int) and target_size != current_size:
            continue
        if str(identity.get("versionOutput")) != str(source["versionOutput"]):
            continue
        if str(identity.get("platform")) != str(source["platform"]):
            continue
        if str(identity.get("arch")) != str(source["arch"]):
            continue
        target_sha = identity.get("sha256")
        current_sha = _source_status_sha256(source)
        if isinstance(target_sha, str) and current_sha == target_sha:
            return "compatible", f"Compatible with current source {current_version}."

    target = same_version[0]
    current_sha = _source_status_sha256(source)
    expected_sha = str(target.get("sha256") or "unknown")
    expected_size = str(target.get("sizeBytes") or "unknown")
    return (
        "sha_mismatch",
        f"Package targets Claude {current_version}, but source identity differs "
        f"(expected {target.get('versionOutput') or 'unknown'}, "
        f"{target.get('platform') or 'unknown'}/{target.get('arch') or 'unknown'}, "
        f"sha256 {expected_sha[:12]}…, size {expected_size}; "
        f"current {source['versionOutput']}, {source['platform']}/{source['arch']}, "
        f"current sha256 {(current_sha or 'unknown')[:12]}…, size {current_size}).",
    )


def _list_patch_payload(paths: StatePaths, config) -> dict[str, Any]:
    profile = active_profile(config)
    desired = set(profile.patches)
    _, report = _latest_build_report(config.activePatchSet)
    active = set(_active_patch_ids_from_report(report))
    seen: set[str] = set()
    patches: list[dict[str, Any]] = []
    source_identity = _source_identity_for_patch_status()
    for root in _package_roots(paths):
        if not root.exists():
            continue
        for patch_json in sorted(root.glob("*/patch.json")):
            patch_id = patch_json.parent.name
            if patch_id in seen:
                continue
            seen.add(patch_id)
            raw = _read_json_file(patch_json) or {}
            compatibility_status, compatibility_message = _patch_compatibility(
                raw, source_identity
            )
            patches.append(
                {
                    "id": patch_id,
                    "label": _patch_label_from_raw(raw, patch_json),
                    "desiredEnabled": patch_id in desired,
                    "activeEnabled": patch_id in active,
                    "available": True,
                    "compatibilityStatus": compatibility_status,
                    "compatibilityMessage": compatibility_message,
                }
            )
    for patch_id in sorted((desired | active) - seen):
        patches.append(
            {
                "id": patch_id,
                "label": patch_id,
                "desiredEnabled": patch_id in desired,
                "activeEnabled": patch_id in active,
                "available": False,
                "compatibilityStatus": "unknown",
            }
        )
    return {"schemaVersion": 1, "patches": patches}


def _list_prompt_payload(paths: StatePaths, config) -> dict[str, Any]:
    profile = active_profile(config)
    prompt_dir = paths.prompts_dir
    prompts: list[dict[str, Any]] = []
    if prompt_dir.exists():
        for prompt_json in sorted(prompt_dir.glob("*.json")):
            raw = _read_json_file(prompt_json) or {}
            prompt_id = str(raw.get("id") or prompt_json.stem)
            source_path = raw.get("sourcePath") or str(prompt_dir / f"{prompt_id}.md")
            prompts.append(
                {
                    "id": prompt_id,
                    "label": str(raw.get("name") or raw.get("label") or prompt_id),
                    "active": profile.prompt == prompt_id,
                    "mode": str(raw.get("mode") or "append"),
                    "sourcePath": str(source_path),
                }
            )
    return {"schemaVersion": 1, "prompts": prompts}


def _dry_run_install_payload(
    target: Path, *, uninstall: bool = False, state_dir: Path | None = None
) -> Any:
    needs_auth = target_needs_authorization(target)
    action = "uninstall managed claude shim" if uninstall else "install managed claude shim"
    if (
        not uninstall
        and state_dir is not None
        and protected_install_requires_refusal(target, state_dir / "install-record.json")
    ):
        message = f"refusing to overwrite protected existing target without safe restore: {target}"
        return envelope_error(
            message,
            code="protected_restore_unavailable",
            target_path=target,
            authorization_required=needs_auth,
            authorization_method=authorization_method_for_target(target),
            dry_run=True,
            planned_actions=[action],
        )
    return envelope_ok(
        f"would {action}",
        target_path=target,
        authorization_required=needs_auth,
        authorization_method=authorization_method_for_target(target),
        dry_run=True,
        planned_actions=[action],
    )


def _build_dry_run_payload() -> Any:
    return envelope_ok(
        "planned build; no activation performed",
        dry_run=True,
        planned_actions=[
            "resolve enabled patches",
            "select current build strategy",
            "run source/package preflight if the current builder supports dry-run preflight",
            "build copied Claude binary only when the real build command is confirmed",
            "activate current symlink only after a successful real build",
        ],
    )


BUILD_ERROR_CODES = {
    "source_identity_mismatch": "source_identity_mismatch",
    "module_identity_failed": "module_identity_failed",
    "operation_resolution_failed": "operation_resolution_failed",
    "precondition_failed": "precondition_failed",
    "postcondition_failed": "postcondition_failed",
    "patch_conflict": "patch_conflict",
    "signing_failed": "signing_failed",
    "post_sign_inspection_failed": "post_sign_inspection_failed",
    "smoke_failed": "smoke_failed",
}


def _build_error_code(summary: str) -> str:
    prefix = summary.split(":", 1)[0]
    return BUILD_ERROR_CODES.get(prefix, "build_failed")


def _build_failure_summary(summary: str) -> str:
    if summary.startswith("source_identity_mismatch:"):
        parts = summary.split(":", 2)
        if len(parts) == 3:
            return (
                f"Patch {parts[1]} is not compatible with this Claude Code source. "
                f"{parts[2]}"
            )
    return summary


def _build_report_json_payload(report: Any, report_path: Path | None = None) -> dict[str, Any]:
    report_payload = dict(to_jsonable(report))
    ok = report_payload.get("status") in {"verified", "manual_smoke_pending"}
    if (
        report_payload.get("status") == "verified"
        and report_payload.get("activationStatus") == "activated"
    ):
        summary = "Build activated"
    elif report_payload.get("status") == "verified":
        summary = "Build verified; activation not performed"
    elif report_payload.get("status") == "manual_smoke_pending":
        summary = "Build requires manual smoke before activation"
    else:
        summary = _build_failure_summary(
            str(
                report_payload.get("failureReason")
                or report_payload.get("status")
                or "build failed"
            )
        )
    envelope = envelope_ok(
        summary,
        report_path=report_path,
        status="ok" if ok else "error",
        build_strategy=report_payload.get("buildStrategy") or report_payload.get("engine"),
        changed_modules=report_payload.get("changedModules", []),
        repack_summary=report_payload.get("repackSummary"),
    )
    payload = to_jsonable(envelope)
    payload["buildReportStatus"] = report_payload.get("status")
    if not ok:
        payload["ok"] = False
        raw_failure = str(report_payload.get("failureReason") or summary)
        payload["error"] = {"message": summary, "code": _build_error_code(raw_failure)}
    return payload


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _package_roots(paths: StatePaths) -> list[Path]:
    return [paths.patches_dir, _repo_root() / "packages"]


def _resolve_package(package_id_or_path: str, paths: StatePaths) -> Path:
    raw = Path(package_id_or_path).expanduser()
    if raw.exists():
        return raw
    for root in _package_roots(paths):
        candidate = root / package_id_or_path
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"patch package not found: {package_id_or_path}")


def _enabled_package_dirs(args: argparse.Namespace, paths: StatePaths, config) -> list[Path]:
    if args.packages:
        return [_resolve_package(item, paths) for item in args.packages]
    profile = active_profile(config)
    return [_resolve_package(item, paths) for item in profile.patches]


def _detected_claude_command_path() -> Path | None:
    found = shutil.which("claude")
    return Path(found) if found else None


def _clean_source_for_detected_command(found: Path) -> Path | None:
    paths = default_paths()
    return clean_source_from_install_record(found, _install_record_path(paths))


def _discover_source(source_arg: str | None) -> Path | None:
    if source_arg:
        return Path(source_arg).expanduser()
    env_source = __import__("os").environ.get("CLAUDE_MONKEY_SOURCE")
    if env_source:
        return Path(env_source).expanduser()
    found = _detected_claude_command_path()
    if found is None:
        return None
    return _clean_source_for_detected_command(found) or found


def _source_version_output(source: Path, explicit_output: str | None) -> str | None:
    if explicit_output:
        return explicit_output
    result = run_command([str(source), "--version"])
    if result.returncode != 0:
        return None
    return result.stdout.strip() or result.stderr.strip() or None


def _source_version(explicit_version: str | None, version_output: str | None) -> str | None:
    if explicit_version:
        return explicit_version
    if not version_output:
        return None
    first = version_output.split(maxsplit=1)[0]
    return first or None


def _default_output_dir(paths: StatePaths, config, source_version: str) -> Path:
    return paths.patchset_dir(source_version, config.activeProfile)


def _print_report_summary(report) -> None:
    print(f"status={report.status}")
    print(f"sourceSha256={report.sourceSha256}")
    print(f"enabledPatches={','.join(report.enabledPatches)}")
    if report.failureReason:
        print(f"failureReason={report.failureReason}")


def handle_build(args: argparse.Namespace, paths: StatePaths, config) -> int:
    if getattr(args, "dry_run", False):
        return emit(args, "planned build; no activation performed", _build_dry_run_payload())
    source = _discover_source(args.source)
    if source is None:
        message = "build requires --source or a claude executable on PATH"
        if args.json:
            print_json(envelope_error(message, code="missing_source"))
        else:
            print(message, file=sys.stderr)
        return 2
    if not source.exists():
        message = f"source does not exist: {source}"
        if args.json:
            print_json(envelope_error(message, code="missing_source"))
        else:
            print(message, file=sys.stderr)
        return 2
    version_output = _source_version_output(source, args.source_version_output)
    source_version = _source_version(args.source_version, version_output)
    if version_output is None or source_version is None:
        message = "build requires --source-version-output/--source-version or a working --version"
        if args.json:
            print_json(envelope_error(message, code="missing_source_version"))
        else:
            print(message, file=sys.stderr)
        return 2
    try:
        package_dirs = _enabled_package_dirs(args, paths, config)
    except FileNotFoundError as exc:
        if args.json:
            print_json(envelope_error(str(exc), code="missing_package"))
        else:
            print(str(exc), file=sys.stderr)
        return 2
    if not package_dirs:
        message = "build requires enabled patches or at least one --package"
        if args.json:
            print_json(envelope_error(message, code="missing_package"))
        else:
            print(message, file=sys.stderr)
        return 2
    output_dir = (
        Path(args.output_dir).expanduser()
        if args.output_dir
        else _default_output_dir(paths, config, source_version)
    )
    report = build_patchset_v15(
        BuildRequestV15(
            source_path=source,
            output_dir=output_dir,
            package_dirs=package_dirs,
            source_version=source_version,
            source_version_output=version_output,
            platform=args.platform,
            arch=args.arch,
            run_signing=not args.skip_signing,
            run_smoke=not args.skip_smoke,
            activate=args.activate,
            current_path=paths.current_path,
        )
    )
    if report.status == "verified" and report.activationStatus == "activated":
        config.activePatchSet = str(output_dir)
        save_config(paths.config_path, config)
    if args.json:
        print_json(_build_report_json_payload(report, output_dir / "build-report.json"))
    else:
        _print_report_summary(report)
    return 0 if report.status in {"verified", "manual_smoke_pending"} else 1


def _record_path(args: argparse.Namespace, state_dir: Path) -> Path:
    return Path(args.record).expanduser() if args.record else state_dir / "install-record.json"


def _target_from_args_or_record(args: argparse.Namespace, record_path: Path) -> Path | None:
    if args.target:
        return Path(args.target).expanduser()
    if not record_path.exists():
        return None
    try:
        raw = json.loads(record_path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid install record JSON: {record_path}") from exc
    if not isinstance(raw, dict):
        raise ValueError(f"invalid install record JSON: {record_path}")
    target = raw.get("targetPath")
    return Path(target) if isinstance(target, str) else None


def handle_restore(args: argparse.Namespace, paths: StatePaths) -> int:
    state_dir = Path(args.state_dir).expanduser() if args.state_dir else paths.state_dir
    record_path = _record_path(args, state_dir)
    command_label = "rollback" if args.command == "rollback" else "uninstall-shim"
    try:
        target = _target_from_args_or_record(args, record_path)
    except ValueError as exc:
        if getattr(args, "json", False):
            print_json(envelope_error(str(exc), code="invalid_record"))
        else:
            print(str(exc), file=sys.stderr)
        return 2
    if target is None:
        payload = envelope_error(
            f"{command_label} requires --target or an install record with targetPath",
            code="missing_target",
        )
        if getattr(args, "json", False):
            print_json(payload)
        else:
            print(
                f"{command_label} requires --target or an install record with targetPath",
                file=sys.stderr,
            )
        return 2
    authorization_required = target_needs_authorization(target)
    authorization_method = authorization_method_for_target(target)
    if getattr(args, "dry_run", False):
        payload = _dry_run_install_payload(target, uninstall=True)
        if getattr(args, "json", False):
            print_json(payload)
        else:
            print(f"target={target}")
            print("dryRun=true")
        return 0
    try:
        restored = restore_install_transaction(target, record_path, force=args.force)
    except (AuthorizationRequired, AuthorizationDenied) as exc:
        code = (
            "authorization_denied"
            if isinstance(exc, AuthorizationDenied)
            else "authorization_required"
        )
        payload = envelope_error(
            str(exc),
            code=code,
            target_path=target,
            authorization_required=True,
            authorization_method=exc.method,
        )
        if getattr(args, "json", False):
            print_json(payload)
        else:
            print(str(exc), file=sys.stderr)
        return 1
    except OSError as exc:
        payload = envelope_error(str(exc), code="filesystem_error", target_path=target)
        if getattr(args, "json", False):
            print_json(payload)
        else:
            print(str(exc), file=sys.stderr)
        return 1
    if getattr(args, "json", False):
        if restored:
            print_json(
                envelope_ok(
                    "uninstalled managed claude shim",
                    target_path=target,
                    authorization_required=authorization_required,
                    authorization_method=authorization_method,
                )
            )
        else:
            print_json(
                envelope_error(
                    "managed shim was not restored", code="restore_failed", target_path=target
                )
            )
    else:
        print(f"restored={str(restored).lower()}")
    return 0 if restored else 1


def handle_set_prompt(args: argparse.Namespace, paths: StatePaths, config) -> int:
    profile_dir = paths.prompts_dir
    profile_dir.mkdir(parents=True, exist_ok=True)
    if args.from_file:
        source_path = Path(args.prompt).expanduser()
        if not source_path.exists():
            message = f"prompt file does not exist: {source_path}"
            if args.json:
                print_json(envelope_error(message, code="missing_prompt_file"))
            else:
                print(message, file=sys.stderr)
            return 2
    else:
        source_path = profile_dir / f"{args.id}.md"
        source_path.write_text(args.prompt)
    profile_json = profile_dir / f"{args.id}.json"
    profile_json.write_text(
        json.dumps(
            {
                "id": args.id,
                "name": args.name or args.id,
                "mode": args.mode,
                "sourcePath": str(source_path),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )
    active_profile(config).prompt = args.id
    save_config(paths.config_path, config)
    return emit(args, f"set prompt profile {args.id}", envelope_ok(f"prompt set to {args.id}"))


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.version:
        print(__version__)
        return 0
    if getattr(os, "geteuid", lambda: 1)() == 0:
        message = (
            "refusing to run claude-monkey manager as root; use the normal user "
            "process and let ClaudeMonkey request narrow authorization for protected "
            "install/restore file operations"
        )
        payload = envelope_error(message, code="root_process_refused")
        if getattr(args, "json", False):
            print_json(payload)
        else:
            print(message, file=sys.stderr)
        return 1
    paths = default_paths()
    config = load_config(paths.config_path)
    if args.command == "status":
        if args.json:
            print_json(_status_payload(paths, config))
        else:
            print(f"stateDir={paths.state_dir}")
            print(f"patchesDir={paths.patches_dir}")
            print(f"activeProfile={config.activeProfile}")
            print(f"activePatchSet={config.activePatchSet}")
            if paths.current_path.exists() or paths.current_path.is_symlink():
                print(f"current={paths.current_path.resolve()}")
        return 0
    if args.command == "enable":
        profile = active_profile(config)
        if args.patch_id not in profile.patches:
            profile.patches.append(args.patch_id)
        save_config(paths.config_path, config)
        return emit(
            args,
            f"enabled {args.patch_id}; rebuild required",
            envelope_ok(f"enabled {args.patch_id}; rebuild required", status="rebuild_required"),
        )
    if args.command == "disable":
        profile = active_profile(config)
        profile.patches = [item for item in profile.patches if item != args.patch_id]
        save_config(paths.config_path, config)
        return emit(
            args,
            f"disabled {args.patch_id}; rebuild required",
            envelope_ok(f"disabled {args.patch_id}; rebuild required", status="rebuild_required"),
        )
    if args.command == "list-patches":
        if args.json:
            print_json(_list_patch_payload(paths, config))
        else:
            for root in _package_roots(paths):
                if root.exists():
                    for patch_json in sorted(root.glob("*/patch.json")):
                        print(patch_json.parent.name)
        return 0
    if args.command == "list-prompts":
        if args.json:
            print_json(_list_prompt_payload(paths, config))
        else:
            prompt_dir = paths.prompts_dir
            if prompt_dir.exists():
                for prompt_json in sorted(prompt_dir.glob("*.json")):
                    print(prompt_json.stem)
        return 0
    if args.command == "set-prompt":
        return handle_set_prompt(args, paths, config)
    if args.command == "clear-prompt":
        active_profile(config).prompt = None
        save_config(paths.config_path, config)
        return emit(args, "cleared active prompt profile", envelope_ok("prompt cleared"))
    if args.command == "inspect-binary":
        source = Path(args.source).expanduser()
        payload = inspect_binary_bytes(source.read_bytes(), source_path=str(source))
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"supported={str(payload['supported']).lower()}")
            print(f"modules={len(payload['modules'])}")
        return 0 if payload["ok"] and not payload["validationErrors"] else 1
    if args.command == "validate-package":
        payload = validate_package(
            ValidationRequestV15(
                source_path=Path(args.source).expanduser(),
                package_dir=Path(args.package).expanduser(),
                source_version=args.source_version,
                source_version_output=args.source_version_output,
                platform=args.platform,
                arch=args.arch,
            )
        )
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"ok={str(payload['ok']).lower()}")
        return 0 if payload["ok"] else 1
    if args.command == "build":
        return handle_build(args, paths, config)
    if args.command == "install-shim":
        state_dir = Path(args.state_dir).expanduser() if args.state_dir else paths.state_dir
        if not args.target:
            payload = envelope_error("install-shim requires --target", code="missing_target")
            if args.json:
                print_json(payload)
            else:
                print("install-shim requires --target", file=sys.stderr)
            return 2
        target = Path(args.target).expanduser()
        authorization_required = target_needs_authorization(target)
        authorization_method = authorization_method_for_target(target)
        if args.dry_run:
            payload = _dry_run_install_payload(target, state_dir=state_dir)
            if args.json:
                print_json(payload)
            else:
                if getattr(payload, "ok", False):
                    print(f"installRecord={state_dir / 'install-record.json'}")
                    print("dryRun=true")
                else:
                    print(payload.summary, file=sys.stderr)
            return 0 if getattr(payload, "ok", False) else 1
        try:
            record = install_shim_transaction(target, state_dir, dry_run=False)
        except ProtectedTargetRestoreUnavailable as exc:
            payload = envelope_error(
                str(exc),
                code="protected_restore_unavailable",
                target_path=target,
                authorization_required=authorization_required,
                authorization_method=authorization_method,
            )
            if args.json:
                print_json(payload)
            else:
                print(str(exc), file=sys.stderr)
            return 1
        except (AuthorizationRequired, AuthorizationDenied) as exc:
            code = (
                "authorization_denied"
                if isinstance(exc, AuthorizationDenied)
                else "authorization_required"
            )
            payload = envelope_error(
                str(exc),
                code=code,
                target_path=target,
                authorization_required=True,
                authorization_method=exc.method,
            )
            if args.json:
                print_json(payload)
            else:
                print(str(exc), file=sys.stderr)
            return 1
        except OSError as exc:
            if args.json:
                print_json(envelope_error(str(exc), code="filesystem_error", target_path=target))
            else:
                print(str(exc), file=sys.stderr)
            return 1
        if args.json:
            print_json(
                envelope_ok(
                    "installed managed claude shim",
                    target_path=target,
                    authorization_required=authorization_required,
                    authorization_method=authorization_method,
                )
            )
        else:
            print(f"installRecord={record}")
            print("dryRun=false")
        return 0
    if args.command in {"uninstall-shim", "rollback"}:
        return handle_restore(args, paths)
    if args.command == "use-official":
        if not args.official:
            message = "use-official requires --official"
            if args.json:
                print_json(envelope_error(message, code="missing_official"))
            else:
                print(message, file=sys.stderr)
            return 2
        official = Path(args.official).expanduser()
        if not official.exists():
            message = f"official path does not exist: {official}"
            if args.json:
                print_json(envelope_error(message, code="missing_official"))
            else:
                print(message, file=sys.stderr)
            return 2
        use_official(paths.current_path, official)
        config.activePatchSet = None
        save_config(paths.config_path, config)
        if args.json:
            print_json(envelope_ok("using official Claude binary", target_path=official))
        else:
            print(f"current={paths.current_path.resolve()}")
        return 0
    if args.command == "doctor":
        print(f"stateDir={paths.state_dir}")
        print(f"sourceDiscovery={_discover_source(None) or 'missing'}")
        return 0
    parser.print_help()
    return 0
