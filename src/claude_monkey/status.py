from __future__ import annotations

import hashlib
import json
import os
import platform as platform_module
import sys
from pathlib import Path
from typing import Any

from claude_monkey.config import ClaudeMonkeyConfig, LaunchProfile
from claude_monkey.install import current_target_is_installed_shim
from claude_monkey.launch_profile import load_active_launch_packages, select_launch_target
from claude_monkey.package_model import (
    PackageKind,
    PackageManifest,
    PackageValidationError,
    load_package_manifest,
    manifest_digest,
)
from claude_monkey.paths import StatePaths
from claude_monkey.smoke import run_command
from claude_monkey.source_discovery import discover_official_claude


def _active_profile(config: ClaudeMonkeyConfig) -> LaunchProfile:
    return config.profiles.setdefault("default", LaunchProfile())


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
    if report is None:
        return None, None
    return report_path, report


def _display_patch_set(active_patch_set: str | None) -> str | None:
    if not active_patch_set:
        return None
    patch_set_path = Path(active_patch_set).expanduser()
    if not patch_set_path.is_absolute():
        patch_set_path = patch_set_path.resolve()
    return str(patch_set_path)


def _built_patch_ids(report: dict[str, Any] | None) -> list[str]:
    if not report:
        return []
    for key in ("enabledPatches", "patchIds", "builtPatchIds", "activePatchIds"):
        value = report.get(key)
        if isinstance(value, list):
            return [str(item) for item in value]
    snapshot = report.get("buildInputSnapshot")
    if isinstance(snapshot, dict) and isinstance(snapshot.get("patches"), list):
        return [str(item) for item in snapshot["patches"]]
    return []


def _load_desired_patch_manifests(
    paths: StatePaths, desired_patch_ids: list[str]
) -> tuple[dict[str, PackageManifest], list[str]]:
    manifests: dict[str, PackageManifest] = {}
    warnings: list[str] = []
    for patch_id in desired_patch_ids:
        package_dir = paths.patches_dir / patch_id
        if not package_dir.exists():
            warnings.append(f"patch {patch_id} skipped: missing")
            continue
        try:
            manifests[patch_id] = load_package_manifest(package_dir, PackageKind.PATCH)
        except PackageValidationError as exc:
            warnings.append(f"patch {patch_id} skipped: invalid ({exc})")
    return manifests, warnings


def _file_sha256(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _version_from_output(output: str | None) -> str | None:
    if not output:
        return None
    first = output.split(maxsplit=1)[0]
    return first or None


def _source_identity_from_report(report: dict[str, Any] | None) -> dict[str, Any]:
    if not report:
        return {}
    identity = report.get("sourceIdentity")
    if isinstance(identity, dict):
        result = dict(identity)
    else:
        result = {}
    if isinstance(report.get("sourceClaudePath"), str):
        result.setdefault("path", report["sourceClaudePath"])
    if isinstance(report.get("sourceVersion"), str):
        result.setdefault("claudeVersion", report["sourceVersion"])
    if isinstance(report.get("sourceVersionOutput"), str):
        result.setdefault("versionOutput", report["sourceVersionOutput"])
    if isinstance(report.get("sourceSha256"), str):
        result.setdefault("sha256", report["sourceSha256"])
    if isinstance(report.get("sourceSizeBytes"), int):
        result.setdefault("sizeBytes", report["sourceSizeBytes"])
    return result


def _source_identity_from_discovery(
    paths: StatePaths, config: ClaudeMonkeyConfig
) -> dict[str, Any]:
    source = discover_official_claude(config, paths)
    if source is None:
        return {}
    result = run_command([str(source), "--version"])
    version_output = None
    if result.returncode == 0:
        version_output = result.stdout.strip() or result.stderr.strip() or None
    try:
        size = source.stat().st_size
    except OSError:
        size = None
    identity: dict[str, Any] = {
        "path": str(source),
        "claudeVersion": _version_from_output(version_output),
        "versionOutput": version_output,
        "sha256": _file_sha256(source),
        "platform": sys.platform,
        "arch": platform_module.machine() or "unknown",
    }
    if size is not None:
        identity["sizeBytes"] = size
    return {key: value for key, value in identity.items() if value is not None}


def _source_identity(
    paths: StatePaths, config: ClaudeMonkeyConfig, report: dict[str, Any] | None
) -> dict[str, Any]:
    from_report = _source_identity_from_report(report)
    from_discovery = _source_identity_from_discovery(paths, config)
    return from_discovery or from_report


def _target_identities(manifest: PackageManifest) -> list[dict[str, Any]]:
    if manifest.patch is None:
        return []
    identities: list[dict[str, Any]] = []
    for target in manifest.patch.targets:
        identity = target.get("sourceIdentity")
        if isinstance(identity, dict):
            identities.append(identity)
    return identities


def _source_identity_status(
    source: dict[str, Any], patch_manifests: dict[str, PackageManifest]
) -> str:
    if not patch_manifests:
        return "unknown"
    if not source:
        return "unknown"
    for manifest in patch_manifests.values():
        identities = _target_identities(manifest)
        if not identities:
            return "unknown"
        if not any(_identity_matches(source, identity) for identity in identities):
            return "source_mismatch"
    return "compatible"


def _identity_matches(source: dict[str, Any], target: dict[str, Any]) -> bool:
    fields = (
        ("claudeVersion", "claudeVersion"),
        ("versionOutput", "versionOutput"),
        ("sha256", "sha256"),
        ("sizeBytes", "sizeBytes"),
        ("platform", "platform"),
        ("arch", "arch"),
    )
    for source_key, target_key in fields:
        target_value = target.get(target_key)
        if target_value is None:
            continue
        source_value = source.get(source_key)
        if source_value is None:
            return False
        if str(source_value) != str(target_value):
            return False
    return True


def _manifest_compatibility_status(
    desired_patch_ids: list[str], patch_manifests: dict[str, PackageManifest], warnings: list[str]
) -> str:
    if warnings:
        return "invalid"
    if len(patch_manifests) != len(desired_patch_ids):
        return "invalid"
    return "compatible" if desired_patch_ids else "unknown"


def _last_build_compatibility(report: dict[str, Any] | None) -> tuple[str, list[str]]:
    if not report:
        return "unknown", []
    compatibility = report.get("compatibility")
    if isinstance(compatibility, dict):
        status = str(compatibility.get("status") or "unknown")
        warnings = compatibility.get("warnings")
        return status, [str(item) for item in warnings] if isinstance(warnings, list) else []
    if str(report.get("status")) in {"verified", "manual_smoke_pending", "skipped_gates"}:
        return "compatible", []
    if report.get("failureReason"):
        return "unknown", [str(report["failureReason"])]
    return "unknown", []


def _manifest_digests(patch_manifests: dict[str, PackageManifest]) -> dict[str, str]:
    return {patch_id: manifest_digest(manifest) for patch_id, manifest in patch_manifests.items()}


def _reported_manifest_digests(report: dict[str, Any] | None) -> dict[str, str]:
    value = (report or {}).get("packageManifestDigests")
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items() if isinstance(item, str)}


def _source_matches_report(source: dict[str, Any], report: dict[str, Any] | None) -> bool:
    report_identity = _source_identity_from_report(report)
    if not source or not report_identity:
        return True
    for key in ("path", "sha256", "sizeBytes"):
        expected = report_identity.get(key)
        if expected is None:
            continue
        actual = source.get(key)
        if actual is None or str(actual) != str(expected):
            return False
    return True


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


def _shim_is_installed(record_path: Path) -> bool:
    record = _read_json_file(record_path)
    if not record:
        return False
    target = record.get("targetPath")
    try:
        return isinstance(target, str) and current_target_is_installed_shim(Path(target), record)
    except OSError:
        return False


def _detected_claude_command_path() -> Path | None:
    import shutil

    found = shutil.which("claude")
    return Path(found) if found else None

def _patchset_path(active_patch_set: str | None) -> Path | None:
    if not active_patch_set:
        return None
    patchset_path = Path(active_patch_set).expanduser()
    if not patchset_path.is_absolute():
        patchset_path = patchset_path.resolve(strict=False)
    return patchset_path


def _expected_active_executables(
    active_patch_set: str | None, report: dict[str, Any] | None
) -> list[Path]:
    expected: list[Path] = []
    patchset_path = _patchset_path(active_patch_set)
    if patchset_path is not None:
        expected.append(patchset_path / "claude")
    output_path = (report or {}).get("outputPath")
    if isinstance(output_path, str):
        expected.append(Path(output_path).expanduser())
    return expected


def _patched_build_active(
    paths: StatePaths, active_patch_set: str | None, report: dict[str, Any] | None
) -> bool:
    try:
        resolved = paths.current_path.resolve(strict=True)
    except OSError:
        return False
    if not (resolved.is_file() and os.access(resolved, os.X_OK)):
        return False
    for expected in _expected_active_executables(active_patch_set, report):
        try:
            if resolved == expected.resolve(strict=True):
                return True
        except OSError:
            continue
    return False


def _high_risk_options(loaded_options: list[PackageManifest]) -> list[dict[str, str]]:
    records: list[dict[str, str]] = []
    for option in loaded_options:
        risk = option.risk
        if risk is None or risk.level != "high":
            continue
        records.append(
            {
                "id": option.id,
                "label": option.label,
                "warning": risk.status_warning or risk.notes or f"{option.label} enabled",
            }
        )
    return records


def status_payload(paths: StatePaths, config: ClaudeMonkeyConfig) -> dict[str, Any]:
    profile = _active_profile(config)
    desired_patch_ids = list(profile.patches)
    active_option_ids = list(profile.options)
    report_path, report = _latest_build_report(config.activePatchSet)
    built_patch_ids = _built_patch_ids(report)
    loaded_launch = load_active_launch_packages(paths, config)
    patch_manifests, patch_warnings = _load_desired_patch_manifests(paths, desired_patch_ids)
    source = _source_identity(paths, config, report)
    manifest_status = _manifest_compatibility_status(
        desired_patch_ids, patch_manifests, patch_warnings
    )
    source_status = _source_identity_status(source, patch_manifests)
    last_build_status, build_warnings = _last_build_compatibility(report)
    current_digests = _manifest_digests(patch_manifests)
    reported_digests = _reported_manifest_digests(report)
    digest_missing = bool(
        desired_patch_ids
        and current_digests
        and report is not None
        and any(pid not in reported_digests for pid in desired_patch_ids)
    )
    digest_mismatch = bool(
        desired_patch_ids
        and reported_digests
        and any(reported_digests.get(pid) != current_digests.get(pid) for pid in desired_patch_ids)
    )
    source_report_mismatch = not _source_matches_report(source, report)
    patched_active = _patched_build_active(paths, config.activePatchSet, report)
    target = select_launch_target(paths, config, dict(os.environ))
    target_kind = target.kind if target is not None else "missing"
    active_patch_ids = built_patch_ids if patched_active else []
    active_report_missing = config.activePatchSet is not None and report is None
    current_executable = _current_executable_path(paths.current_path)
    install_record = _install_record_path(paths)
    shim_installed = _shim_is_installed(install_record)
    installed = (
        (patched_active or shim_installed)
        if config.installMode == "shim"
        else (current_executable is not None or shim_installed)
    )
    runnable = current_executable is not None
    rebuild_required = (
        desired_patch_ids != built_patch_ids
        or desired_patch_ids != active_patch_ids
        or active_report_missing
        or digest_missing
        or digest_mismatch
        or source_status not in {"compatible", "unknown"}
        or source_report_mismatch
        or manifest_status == "invalid"
        or (installed and not runnable)
    )
    compatibility_warnings = [
        *loaded_launch.warnings,
        *patch_warnings,
        *build_warnings,
    ]
    if digest_missing:
        compatibility_warnings.append(
            "enabled patch package manifest digest missing from last build"
        )
    if digest_mismatch:
        compatibility_warnings.append("enabled patch package manifest changed since last build")
    if source_report_mismatch:
        compatibility_warnings.append("source identity changed since last build")
    if manifest_status == "invalid":
        compatibility_status = "invalid"
    elif source_status not in {"compatible", "unknown"}:
        compatibility_status = source_status
    elif source_report_mismatch:
        compatibility_status = "source_mismatch"
    else:
        compatibility_status = (
            last_build_status if last_build_status != "unknown" else manifest_status
        )
    if compatibility_warnings and not desired_patch_ids and not installed:
        status = "warning"
    elif not installed:
        status = "not_installed"
    elif rebuild_required or not runnable:
        status = "rebuild_required"
    elif compatibility_warnings:
        status = "warning"
    else:
        status = "ok"

    return {
        "schemaVersion": 1,
        "status": status,
        "activeProfile": config.activeProfile,
        "activePrompt": profile.prompt,
        "desiredPatchIds": desired_patch_ids,
        "builtPatchIds": built_patch_ids,
        "activePatchIds": active_patch_ids,
        "patchedBuildActive": patched_active,
        "targetClaudeKind": target_kind,
        "activeOptionIds": active_option_ids,
        "highRiskOptions": _high_risk_options(loaded_launch.options),
        "sourceClaudeVersion": source.get("claudeVersion"),
        "sourceClaudePath": source.get("path"),
        "sourceSha256": source.get("sha256"),
        "compatibilityStatus": compatibility_status,
        "manifestCompatibilityStatus": manifest_status,
        "sourceIdentityStatus": source_status,
        "lastBuildCompatibilityStatus": last_build_status,
        "liveValidationStatus": "unknown",
        "compatibilityWarnings": compatibility_warnings,
        "statusWarnings": compatibility_warnings,
        "rebuildRequired": rebuild_required,
        "latestBuildReportPath": str(report_path) if report_path is not None else None,
        "lastError": None,
        # Transitional V1/V1.5 status fields kept for existing consumers.
        "sourceClaudePathLegacy": source.get("path"),
        "officialClaudePath": config.officialClaudePath,
        "installMode": config.installMode,
        "activePatchSet": _display_patch_set(config.activePatchSet),
        "currentClaudePath": current_executable,
        "shimInstalled": shim_installed,
        "shimTargetPath": _shim_target_from_record(install_record) if shim_installed else None,
        "installRecordPath": str(install_record) if shim_installed else None,
        "discoveredOfficialClaudePath": str(discover_official_claude(config, paths))
        if discover_official_claude(config, paths)
        else None,
        "detectedClaudeCommandPath": str(_detected_claude_command_path())
        if _detected_claude_command_path()
        else None,
        "buildStrategy": (
            (report or {}).get("buildStrategy")
            or (report or {}).get("engine")
            or "unknown"
        ),
        "lastBuildStrategy": (
            (report or {}).get("buildStrategy")
            or (report or {}).get("engine")
            or "unknown"
        ),
        "changedModules": (report or {}).get("changedModules", []),
        "repackSummary": (report or {}).get("repackSummary"),
        "stateDir": str(paths.state_dir),
        "logsDir": str(paths.logs_dir),
    }
