from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

STATUS_LABELS = {
    "ok": "OK",
    "rebuild_required": "Rebuild Required",
    "error": "Error",
    "not_installed": "Not Installed",
    "unknown": "Unknown",
}


@dataclass(frozen=True)
class ErrorInfo:
    message: str
    code: str | None = None


@dataclass(frozen=True)
class CommandEnvelope:
    ok: bool
    status: str
    summary: str
    report_path: Path | None
    target_path: Path | None
    authorization_required: bool
    authorization_method: str | None
    dry_run: bool
    planned_actions: tuple[str, ...]
    error: ErrorInfo | None


@dataclass(frozen=True)
class PatchMenuItem:
    patch_id: str
    label: str
    checked: bool
    active_enabled: bool
    available: bool
    compatibility_status: str


@dataclass(frozen=True)
class PromptMenuItem:
    prompt_id: str
    label: str
    checked: bool
    mode: str
    source_path: Path


@dataclass(frozen=True)
class MenuState:
    status: str
    status_label: str
    source_claude_version: str | None
    source_claude_path: Path | None
    install_mode: str
    shim_installed: bool
    active_profile: str | None
    active_prompt: str | None
    desired_patch_ids: tuple[str, ...]
    active_patch_ids: tuple[str, ...]
    rebuild_required: bool
    latest_build_report_path: Path | None
    active_patch_set: str | None
    current_claude_path: Path | None
    shim_target_path: Path | None
    install_record_path: Path | None
    last_build_strategy: str
    changed_modules: tuple[dict[str, Any], ...]
    repack_summary: dict[str, Any] | None
    state_dir: Path
    logs_dir: Path
    last_error: ErrorInfo | None
    patch_items: tuple[PatchMenuItem, ...]
    prompt_items: tuple[PromptMenuItem, ...]


def _optional_path(value: Any) -> Path | None:
    return Path(str(value)).expanduser() if value else None


def parse_error(raw: Any) -> ErrorInfo | None:
    if raw is None:
        return None
    if not isinstance(raw, dict) or not raw.get("message"):
        raise ValueError("error must be null or object with non-empty message")
    code = raw.get("code")
    return ErrorInfo(message=str(raw["message"]), code=str(code) if code is not None else None)


def _required_bool(raw: dict[str, Any], key: str) -> bool:
    value = raw.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be boolean")
    return value


def _optional_bool(raw: dict[str, Any], key: str, default: bool = False) -> bool:
    value = raw.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be boolean")
    return value


def _planned_actions(raw: dict[str, Any]) -> tuple[str, ...]:
    value = raw.get("plannedActions", [])
    if not isinstance(value, list):
        raise ValueError("plannedActions must be a list")
    if not all(isinstance(item, str) for item in value):
        raise ValueError("plannedActions items must be strings")
    return tuple(value)


def parse_command_envelope(raw: dict[str, Any]) -> CommandEnvelope:
    if raw.get("schemaVersion") != 1:
        raise ValueError("schemaVersion must be 1")
    error = parse_error(raw.get("error"))
    ok = _required_bool(raw, "ok")
    if ok and error is not None:
        raise ValueError("ok envelope must have error=null")
    if not ok and error is None:
        raise ValueError("failed envelope must include error.message")
    status = str(raw.get("status", "unknown"))
    if ok and status == "error":
        raise ValueError("ok envelope cannot have error status")
    if not ok and status == "ok":
        raise ValueError("failed envelope cannot have ok status")
    return CommandEnvelope(
        ok=ok,
        status=status,
        summary=str(raw.get("summary", "")),
        report_path=_optional_path(raw.get("reportPath")),
        target_path=_optional_path(raw.get("targetPath")),
        authorization_required=_optional_bool(raw, "authorizationRequired", False),
        authorization_method=raw.get("authorizationMethod"),
        dry_run=_optional_bool(raw, "dryRun", False),
        planned_actions=_planned_actions(raw),
        error=error,
    )


def normalize_status(raw_status: str, rebuild_required: bool, last_error: ErrorInfo | None) -> str:
    if last_error is not None or raw_status == "error":
        return "error"
    if raw_status == "not_installed":
        return "not_installed"
    if rebuild_required or raw_status == "rebuild_required":
        return "rebuild_required"
    if raw_status == "ok":
        return "ok"
    return "unknown"


def parse_menu_state(
    status_raw: dict[str, Any], patches_raw: dict[str, Any], prompts_raw: dict[str, Any]
) -> MenuState:
    last_error = parse_error(status_raw.get("lastError"))
    rebuild_required = _required_bool(status_raw, "rebuildRequired")
    status = normalize_status(
        str(status_raw.get("status", "unknown")), rebuild_required, last_error
    )
    patch_items = tuple(
        PatchMenuItem(
            patch_id=str(item["id"]),
            label=str(item.get("label", item["id"])),
            checked=_required_bool(item, "desiredEnabled"),
            active_enabled=_required_bool(item, "activeEnabled"),
            available=_optional_bool(item, "available", True),
            compatibility_status=str(item.get("compatibilityStatus", "unknown")),
        )
        for item in patches_raw.get("patches", [])
    )
    prompt_items = tuple(
        PromptMenuItem(
            prompt_id=str(item["id"]),
            label=str(item.get("label", item["id"])),
            checked=_required_bool(item, "active"),
            mode=str(item.get("mode", "append")),
            source_path=Path(str(item.get("sourcePath", ""))).expanduser(),
        )
        for item in prompts_raw.get("prompts", [])
    )
    return MenuState(
        status=status,
        status_label=STATUS_LABELS[status],
        source_claude_version=status_raw.get("sourceClaudeVersion"),
        source_claude_path=_optional_path(status_raw.get("sourceClaudePath")),
        install_mode=str(status_raw.get("installMode", "shim")),
        shim_installed=_optional_bool(status_raw, "shimInstalled", False),
        active_profile=status_raw.get("activeProfile"),
        active_prompt=status_raw.get("activePrompt"),
        desired_patch_ids=tuple(str(item) for item in status_raw.get("desiredPatchIds", [])),
        active_patch_ids=tuple(str(item) for item in status_raw.get("activePatchIds", [])),
        rebuild_required=rebuild_required,
        latest_build_report_path=_optional_path(status_raw.get("latestBuildReportPath")),
        active_patch_set=status_raw.get("activePatchSet"),
        current_claude_path=_optional_path(status_raw.get("currentClaudePath")),
        shim_target_path=_optional_path(status_raw.get("shimTargetPath")),
        install_record_path=_optional_path(status_raw.get("installRecordPath")),
        last_build_strategy=str(
            status_raw.get("lastBuildStrategy") or status_raw.get("buildStrategy") or "unknown"
        ),
        changed_modules=tuple(dict(item) for item in status_raw.get("changedModules", [])),
        repack_summary=status_raw.get("repackSummary"),
        state_dir=Path(str(status_raw["stateDir"])).expanduser(),
        logs_dir=Path(str(status_raw["logsDir"])).expanduser(),
        last_error=last_error,
        patch_items=patch_items,
        prompt_items=prompt_items,
    )
