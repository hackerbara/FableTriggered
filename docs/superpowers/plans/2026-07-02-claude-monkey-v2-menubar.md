# ClaudeMonkey V2 Menu Bar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the full V2 source-first macOS menu bar companion for ClaudeMonkey on current `main`, using `rumps`, with an icon-only status item, complete status/actions, protected-path install UX, and all build/shim behavior delegated to the Python CLI/core.

**Architecture:** Add current-main JSON/dry-run contracts additively to the existing CLI parser/handlers, then build pure menu state, install-target, permissions, and command-runner modules that can be unit tested without AppKit. The `rumps` entrypoint is a UI adapter: it renders menu items, dispatches CLI commands through the safe runner/elevation boundary, drains worker results on the app loop, and never parses Bun graphs, patches binaries, or reimplements build/shim transactions.

**Tech Stack:** Python 3.11+, standard library, `pytest`, `rumps` + PyObjC for macOS runtime, existing ClaudeMonkey modules under `src/claude_monkey/`.

---

## Preconditions

This plan assumes current `main` is the implementation target and already includes the graph-aware repack baseline, with at least these files:

```text
pyproject.toml
src/claude_monkey/cli.py
src/claude_monkey/config.py
src/claude_monkey/paths.py
src/claude_monkey/builder.py
src/claude_monkey/install.py
src/claude_monkey/prompts.py
tests/conftest.py
```

If current `main` uses different helper names, preserve the contracts in this plan and adapt imports locally. Do not move patch/build/shim, Bun graph, repack, signing, smoke, authorization, or rollback logic into the menu bar layer.

## File structure

Create or modify these files:

```text
assets/claude-monkey-menubar-template.png
pyproject.toml
src/claude_monkey/cli.py
src/claude_monkey/cli_json.py
src/claude_monkey/menubar_state.py
src/claude_monkey/menubar_commands.py
src/claude_monkey/menubar_install.py
src/claude_monkey/menubar.py
tests/test_cli_json_contracts.py
tests/test_menubar_state.py
tests/test_menubar_commands.py
tests/test_menubar_install.py
tests/test_menubar_app_model.py
```

Responsibilities:

- `cli_json.py`: shared JSON envelope helpers and dry-run result helpers for current-main/V2 contracts.
- `cli.py`: add `--json` / `--dry-run` additively to existing rich command parsers/handlers; preserve human CLI behavior.
- `menubar_state.py`: pure dataclasses and tolerant parsers for status, patches, prompts, optional strategy/repack metadata, and command envelopes.
- `menubar_commands.py`: safe argv-list subprocess runner, serialized mutation gate, bounded output capture, menu log writer, thread-safe worker-result queue, and raw `open` helper.
- `menubar_install.py`: target selection model for user-writable and protected shim targets, plus authorization-required planning state.
- `menubar.py`: `rumps` adapter with icon-only app wiring, menu rendering, install-target UI, protected-path confirmation/elevation handoff, callback wiring, confirmation dialogs, queue draining, and `Quit` action.
- Tests: verify contracts and pure behavior without launching a real macOS menu bar.

---

### Task 1: Add JSON envelope helpers and CLI JSON contract tests

**Files:**
- Create: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/cli_json.py`
- Modify: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/cli.py`
- Test: `/Users/MAC/Documents/Claude-patch/tests/test_cli_json_contracts.py`

- [ ] **Step 1: Write failing JSON contract tests**

Create `/Users/MAC/Documents/Claude-patch/tests/test_cli_json_contracts.py`:

```python
from __future__ import annotations

import json

from claude_monkey.cli import main


def parse_json_output(capsys):
    out = capsys.readouterr().out
    return json.loads(out)


def test_status_json_contract(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert main(["status", "--json"]) == 0
    payload = parse_json_output(capsys)
    assert payload["schemaVersion"] == 1
    assert payload["status"] in {"ok", "rebuild_required", "error", "not_installed", "unknown"}
    assert payload["stateDir"].endswith(".claude-monkey")
    assert payload["logsDir"].endswith(".claude-monkey/logs")
    assert isinstance(payload["desiredPatchIds"], list)
    assert isinstance(payload["activePatchIds"], list)
    assert "rebuildRequired" in payload
    assert payload["lastError"] is None or "message" in payload["lastError"]


def test_mutating_command_json_envelope(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert main(["enable", "fable-fallback", "--json"]) == 0
    payload = parse_json_output(capsys)
    assert payload["schemaVersion"] == 1
    assert payload["ok"] is True
    assert payload["status"] in {"ok", "rebuild_required"}
    assert payload["summary"] == "enabled fable-fallback; rebuild required"
    assert payload["reportPath"] is None
    assert payload["targetPath"] is None
    assert payload["authorizationRequired"] is False
    assert payload["authorizationMethod"] is None
    assert payload["dryRun"] is False
    assert payload["plannedActions"] == []
    assert payload["error"] is None


def test_dry_run_envelope(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".claude-monkey" / "bin" / "claude"
    assert main(["install-shim", "--target", str(target), "--json", "--dry-run"]) == 0
    payload = parse_json_output(capsys)
    assert payload["ok"] is True
    assert payload["dryRun"] is True
    assert payload["targetPath"] == str(target)
    assert "authorizationRequired" in payload
    assert isinstance(payload["plannedActions"], list)
    assert payload["error"] is None


def test_real_install_uninstall_json_wraps_cli_core_transaction(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    target = tmp_path / ".claude-monkey" / "bin" / "claude"
    # Use a disposable user-writable target or monkeypatch the CLI/core transaction
    # if current main requires a built current symlink for real install.
    assert main(["install-shim", "--target", str(target), "--json"]) == 0
    install_payload = parse_json_output(capsys)
    assert install_payload["ok"] is True
    assert install_payload["dryRun"] is False
    assert install_payload["targetPath"] == str(target)

    assert main(["uninstall-shim", "--target", str(target), "--json"]) == 0
    uninstall_payload = parse_json_output(capsys)
    assert uninstall_payload["ok"] is True
    assert uninstall_payload["dryRun"] is False
    assert uninstall_payload["targetPath"] == str(target)
```

- [ ] **Step 2: Run tests and verify failure**

```bash
python3 -m pytest tests/test_cli_json_contracts.py -q
```

Expected: FAIL because `cli_json.py`, `--json`, and `--dry-run` support are missing or incomplete.

- [ ] **Step 3: Add JSON envelope helpers**

Create `/Users/MAC/Documents/Claude-patch/src/claude_monkey/cli_json.py`:

```python
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ErrorPayload:
    message: str
    code: str | None = None


@dataclass(frozen=True)
class CommandEnvelope:
    schemaVersion: int = 1
    ok: bool = True
    status: str = "ok"
    summary: str = "ok"
    reportPath: str | None = None
    targetPath: str | None = None
    authorizationRequired: bool = False
    authorizationMethod: str | None = None
    dryRun: bool = False
    plannedActions: list[str] = field(default_factory=list)
    error: ErrorPayload | None = None


def envelope_ok(
    summary: str,
    *,
    report_path: Path | str | None = None,
    target_path: Path | str | None = None,
    authorization_required: bool = False,
    authorization_method: str | None = None,
    dry_run: bool = False,
    planned_actions: list[str] | None = None,
    status: str = "ok",
) -> CommandEnvelope:
    return CommandEnvelope(
        ok=True,
        status=status,
        summary=summary,
        reportPath=str(report_path) if report_path is not None else None,
        targetPath=str(target_path) if target_path is not None else None,
        authorizationRequired=authorization_required,
        authorizationMethod=authorization_method,
        dryRun=dry_run,
        plannedActions=list(planned_actions or []),
        error=None,
    )


def envelope_error(
    message: str,
    *,
    code: str | None = None,
    dry_run: bool = False,
    planned_actions: list[str] | None = None,
    status: str = "error",
    report_path: Path | str | None = None,
    target_path: Path | str | None = None,
    authorization_required: bool = False,
    authorization_method: str | None = None,
) -> CommandEnvelope:
    return CommandEnvelope(
        ok=False,
        status=status,
        summary=message,
        reportPath=str(report_path) if report_path is not None else None,
        targetPath=str(target_path) if target_path is not None else None,
        authorizationRequired=authorization_required,
        authorizationMethod=authorization_method,
        dryRun=dry_run,
        plannedActions=list(planned_actions or []),
        error=ErrorPayload(message=message, code=code),
    )


def to_jsonable(value: Any) -> Any:
    if hasattr(value, "__dataclass_fields__"):
        return asdict(value)
    return value


def print_json(value: Any) -> None:
    print(json.dumps(to_jsonable(value), indent=2, sort_keys=True))
```

- [ ] **Step 4: Add JSON behavior without replacing existing parser shape**

Modify `/Users/MAC/Documents/Claude-patch/src/claude_monkey/cli.py` so the existing command parsers accept per-command `--json`, and so `build` exposes `--dry-run` if current main has not already added it. Do not recreate simplified subparsers for `build`, `set-prompt`, `install-shim`, `uninstall-shim`, `rollback`, or `use-official`; keep all existing flags and human CLI behavior.

Add helpers near the top:

```python
from pathlib import Path
from claude_monkey.cli_json import envelope_error, envelope_ok, print_json


def add_json_flag(parser):
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    return parser


def add_dry_run_flag(parser):
    parser.add_argument("--dry-run", action="store_true", help="plan without mutating active state")
    return parser


def emit(args, text: str, payload=None) -> int:
    if getattr(args, "json", False):
        print_json(payload if payload is not None else envelope_ok(text))
    else:
        print(text)
    return 0
```

In `build_parser()`, augment the existing parser objects in place. The current parser already creates rich command parsers for `set-prompt`, `build`, `install-shim`, `uninstall-shim`, `rollback`, and `use-official`; keep those parser variables and add flags to them. The following sketch shows the shape, not a replacement for the whole parser:

```python
status = add_json_flag(sub.add_parser("status"))
list_patches = add_json_flag(sub.add_parser("list-patches"))
list_prompts = add_json_flag(sub.add_parser("list-prompts"))

enable = add_json_flag(sub.add_parser("enable"))
enable.add_argument("patch_id")
disable = add_json_flag(sub.add_parser("disable"))
disable.add_argument("patch_id")
set_prompt = add_json_flag(sub.add_parser("set-prompt"))
set_prompt.add_argument("prompt")
set_prompt.add_argument("--id", default="default")
set_prompt.add_argument("--name")
set_prompt.add_argument("--mode", choices=("append", "replace"), default="append")
set_prompt.add_argument("--from-file", action="store_true")
add_json_flag(sub.add_parser("clear-prompt"))

build = add_json_flag(sub.add_parser("build"))
# Preserve every existing build flag here.
add_dry_run_flag(build)

install = add_json_flag(sub.add_parser("install-shim"))
install.add_argument("--target")
install.add_argument("--state-dir")
install.add_argument("--dry-run", action="store_true")

uninstall = add_json_flag(sub.add_parser("uninstall-shim"))
uninstall.add_argument("--target")
uninstall.add_argument("--state-dir")
uninstall.add_argument("--record")
uninstall.add_argument("--force", action="store_true")
```

If the concrete parser has already created any of these parser variables, do not call `sub.add_parser()` for that command again. Call `add_json_flag(existing_parser)` and add only missing flags. For current main, this mostly means adding `--json` to existing command parsers and adding `--dry-run` to `build` if current main has not already provided it.

For `status --json`, emit this required shape from existing config/paths:

```python
def _latest_build_report(active_patch_set: str | None) -> dict | None:
    if not active_patch_set:
        return None
    report_path = Path(active_patch_set).expanduser() / "build-report.json"
    if not report_path.exists():
        return None
    return json.loads(report_path.read_text())


def _active_patch_ids_from_report(report: dict | None) -> list[str]:
    if not report:
        return []
    for key in ("enabledPatches", "patchIds", "activePatchIds"):
        value = report.get(key)
        if isinstance(value, list):
            return [str(item) for item in value]
    return []


if args.command == "status" and args.json:
    profile = config.profiles.get(config.activeProfile)
    desired = list(profile.enabledPatches) if profile else []
    report = _latest_build_report(config.activePatchSet)
    active = _active_patch_ids_from_report(report)
    rebuild_required = desired != active
    print_json(
        {
            "schemaVersion": 1,
            "status": "rebuild_required" if rebuild_required else "ok",
            "sourceClaudeVersion": (report or {}).get("sourceVersion"),
            "sourceClaudePath": (report or {}).get("sourceClaudePath"),
            "currentClaudePath": str(paths.current_path.resolve()) if paths.current_path.exists() or paths.current_path.is_symlink() else None,
            "installMode": config.installMode,
            "shimInstalled": False,
            "activeProfile": config.activeProfile,
            "activePrompt": profile.promptProfile if profile else None,
            "desiredPatchIds": desired,
            "activePatchIds": active,
            "rebuildRequired": rebuild_required,
            "activePatchSet": config.activePatchSet,
            "latestBuildReportPath": str(Path(config.activePatchSet).expanduser() / "build-report.json") if config.activePatchSet else None,
            "buildStrategy": (report or {}).get("buildStrategy") or (report or {}).get("engine") or "unknown",
            "lastBuildStrategy": (report or {}).get("buildStrategy") or (report or {}).get("engine") or "unknown",
            "changedModules": (report or {}).get("changedModules", []),
            "repackSummary": (report or {}).get("repackSummary"),
            "stateDir": str(paths.state_dir),
            "logsDir": str(paths.state_dir / "logs"),
            "lastError": None,
        }
    )
    return 0
```

Wrap existing handler outcomes in JSON envelopes and add dry-run branches where the current command lacks them. Preserve the current command behavior first; JSON should report what the existing handler did, not replace that handler with a simplified mutation. For the simple config mutations, the shape is:

```python
if args.command == "enable":
    profile = active_profile(config)
    if args.patch_id not in profile.enabledPatches:
        profile.enabledPatches.append(args.patch_id)
    save_config(paths.config_path, config)
    return emit(
        args,
        f"enabled {args.patch_id}; rebuild required",
        envelope_ok(f"enabled {args.patch_id}; rebuild required", status="rebuild_required"),
    )

if args.command == "disable":
    profile = active_profile(config)
    profile.enabledPatches = [item for item in profile.enabledPatches if item != args.patch_id]
    save_config(paths.config_path, config)
    return emit(
        args,
        f"disabled {args.patch_id}; rebuild required",
        envelope_ok(f"disabled {args.patch_id}; rebuild required", status="rebuild_required"),
    )

if args.command == "set-prompt":
    # Preserve the existing set-prompt implementation: prompt content/source,
    # --id, --name, --mode, and --from-file behavior must still run exactly as
    # the human CLI path expects. Only wrap the successful result for JSON mode.
    result = run_existing_set_prompt_handler(args, config, paths)
    if getattr(args, "json", False):
        print_json(envelope_ok(f"prompt set to {args.id}"))
        return 0
    return result

if args.command == "clear-prompt":
    profile = active_profile(config)
    profile.promptProfile = None
    save_config(paths.config_path, config)
    return emit(args, "prompt cleared", envelope_ok("prompt cleared"))

if args.command == "build" and args.dry_run:
    return emit(
        args,
        "planned build; no activation performed",
        envelope_ok(
            "planned build; no activation performed",
            dry_run=True,
            planned_actions=[
                "resolve enabled patches",
                "select current build strategy",
                "run source/package preflight if the current builder supports dry-run preflight",
                "build copied Claude binary only when the real build command is confirmed",
                "activate current symlink only after a successful real build",
            ],
        ),
    )

if args.command == "install-shim" and args.dry_run:
    if not args.target:
        return emit(args, "install-shim requires --target", envelope_error("install-shim requires --target", code="missing_target"))
    return emit(
        args,
        "would install managed claude shim",
        envelope_ok(
            "would install managed claude shim",
            target_path=Path(args.target).expanduser(),
            authorization_required=_target_needs_authorization(Path(args.target).expanduser()),
            authorization_method="macos_gui" if _target_needs_authorization(Path(args.target).expanduser()) else None,
            dry_run=True,
            planned_actions=["install managed claude shim"],
        ),
    )

if args.command == "uninstall-shim" and args.dry_run:
    if not args.target and not args.record:
        return emit(args, "uninstall-shim requires --target or --record", envelope_error("uninstall-shim requires --target or --record", code="missing_target"))
    return emit(
        args,
        "would uninstall managed claude shim",
        envelope_ok(
            "would uninstall managed claude shim",
            target_path=Path(args.target).expanduser() if args.target else None,
            authorization_required=_target_needs_authorization(Path(args.target).expanduser()) if args.target else False,
            authorization_method="macos_gui" if args.target and _target_needs_authorization(Path(args.target).expanduser()) else None,
            dry_run=True,
            planned_actions=["uninstall managed claude shim"],
        ),
    )

if args.command == "install-shim" and args.json:
    if not args.target:
        print_json(envelope_error("install-shim requires --target", code="missing_target"))
        return 2
    try:
        record = run_existing_install_shim_transaction(args, paths)
    except AuthorizationRequired as exc:
        print_json(envelope_error(str(exc), code="authorization_required", target_path=args.target, authorization_required=True, authorization_method=exc.method))
        return 1
    except AuthorizationDenied as exc:
        print_json(envelope_error(str(exc), code="authorization_denied", target_path=args.target, authorization_required=True, authorization_method=exc.method))
        return 1
    print_json(envelope_ok("installed managed claude shim", target_path=args.target, dry_run=False))
    return 0

if args.command == "uninstall-shim" and args.json:
    if not args.target and not args.record:
        print_json(envelope_error("uninstall-shim requires --target or --record", code="missing_target"))
        return 2
    try:
        restored = run_existing_uninstall_shim_transaction(args, paths)
    except AuthorizationRequired as exc:
        print_json(envelope_error(str(exc), code="authorization_required", target_path=args.target, authorization_required=True, authorization_method=exc.method))
        return 1
    except AuthorizationDenied as exc:
        print_json(envelope_error(str(exc), code="authorization_denied", target_path=args.target, authorization_required=True, authorization_method=exc.method))
        return 1
    print_json(envelope_ok("uninstalled managed claude shim", target_path=args.target or restored.target, dry_run=False))
    return 0
```

Add `_target_needs_authorization()` as a small helper or reuse the CLI/core authorization planner if current main provides one. This helper is only for JSON planning; the actual protected write must still go through the CLI/core's transaction and authorization path.

If the current builder performs real source/package discovery and operation planning during dry-run, include `buildStrategy`, `changedModules`, `repackSummary`, and planned operation/module details in the envelope. If it does not, the summary must stay honest: this is a planning envelope, not proof that visual behavior or patch applicability has been verified.

- [ ] **Step 5: Run JSON contract tests**

```bash
python3 -m pytest tests/test_cli_json_contracts.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 1**

```bash
git add src/claude_monkey/cli.py src/claude_monkey/cli_json.py tests/test_cli_json_contracts.py
git commit -m "Add ClaudeMonkey JSON CLI contracts"
```

---

### Task 2: Add menu state parser and derivation

**Files:**
- Create: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/menubar_state.py`
- Test: `/Users/MAC/Documents/Claude-patch/tests/test_menubar_state.py`

- [ ] **Step 1: Write failing state parser tests**

Create `/Users/MAC/Documents/Claude-patch/tests/test_menubar_state.py`:

```python
from __future__ import annotations

from claude_monkey.menubar_state import MenuState, parse_command_envelope, parse_menu_state


def test_parse_menu_state_applies_status_precedence():
    state = parse_menu_state(
        {
            "schemaVersion": 1,
            "status": "ok",
            "sourceClaudeVersion": "2.1.198",
            "sourceClaudePath": "/tmp/claude",
            "installMode": "shim",
            "shimInstalled": True,
            "activeProfile": "default",
            "activePrompt": "research",
            "desiredPatchIds": ["a"],
            "activePatchIds": [],
            "rebuildRequired": True,
            "latestBuildReportPath": None,
            "activePatchSet": None,
            "currentClaudePath": None,
            "shimTargetPath": None,
            "installRecordPath": None,
            "buildStrategy": "repack",
            "lastBuildStrategy": "repack",
            "changedModules": [{"path": "/$bunfs/root/src/entrypoints/cli.js"}],
            "repackSummary": {"changedModuleCount": 1},
            "stateDir": "/tmp/state",
            "logsDir": "/tmp/state/logs",
            "lastError": None,
        },
        {"schemaVersion": 1, "patches": []},
        {"schemaVersion": 1, "prompts": []},
    )
    assert state.status == "rebuild_required"
    assert state.status_label == "Rebuild Required"
    assert state.last_build_strategy == "repack"
    assert state.changed_modules == ({"path": "/$bunfs/root/src/entrypoints/cli.js"},)


def test_parse_command_envelope_requires_error_message_on_failure():
    envelope = parse_command_envelope(
        {
            "schemaVersion": 1,
            "ok": False,
            "status": "error",
            "summary": "failed",
            "reportPath": None,
            "dryRun": False,
            "plannedActions": [],
            "error": {"message": "failed", "code": "boom"},
        }
    )
    assert envelope.error.message == "failed"


def test_prompt_and_patch_items_are_checked():
    state = parse_menu_state(
        {
            "schemaVersion": 1,
            "status": "ok",
            "sourceClaudeVersion": None,
            "sourceClaudePath": None,
            "installMode": "shim",
            "shimInstalled": False,
            "activeProfile": "default",
            "activePrompt": "research",
            "desiredPatchIds": ["fable-fallback"],
            "activePatchIds": ["fable-fallback"],
            "rebuildRequired": False,
            "latestBuildReportPath": None,
            "activePatchSet": "/tmp/state/patchsets/default",
            "currentClaudePath": "/tmp/state/current",
            "shimTargetPath": "/tmp/state/bin/claude",
            "installRecordPath": "/tmp/state/shims/claude.json",
            "stateDir": "/tmp/state",
            "logsDir": "/tmp/state/logs",
            "lastError": None,
        },
        {"schemaVersion": 1, "patches": [{"id": "fable-fallback", "label": "Fable", "desiredEnabled": True, "activeEnabled": True, "available": True, "compatibilityStatus": "compatible"}]},
        {"schemaVersion": 1, "prompts": [{"id": "research", "label": "Research", "active": True, "mode": "append", "sourcePath": "/tmp/research.md"}]},
    )
    assert state.patch_items[0].checked is True
    assert state.prompt_items[0].checked is True
```

- [ ] **Step 2: Run tests and verify failure**

```bash
python3 -m pytest tests/test_menubar_state.py -q
```

Expected: FAIL because `menubar_state.py` does not exist.

- [ ] **Step 3: Implement pure menu state parser**

Create `/Users/MAC/Documents/Claude-patch/src/claude_monkey/menubar_state.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

STATUS_PRECEDENCE = ["error", "not_installed", "rebuild_required", "ok", "unknown"]
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


def parse_error(raw: Any) -> ErrorInfo | None:
    if raw is None:
        return None
    if not isinstance(raw, dict) or not raw.get("message"):
        raise ValueError("error must be null or object with non-empty message")
    return ErrorInfo(message=str(raw["message"]), code=raw.get("code"))


def parse_command_envelope(raw: dict[str, Any]) -> CommandEnvelope:
    error = parse_error(raw.get("error"))
    ok = bool(raw.get("ok"))
    if ok and error is not None:
        raise ValueError("ok envelope must have error=null")
    if not ok and error is None:
        raise ValueError("failed envelope must include error.message")
    report = raw.get("reportPath")
    return CommandEnvelope(
        ok=ok,
        status=str(raw.get("status", "unknown")),
        summary=str(raw.get("summary", "")),
        report_path=Path(report).expanduser() if report else None,
        dry_run=bool(raw.get("dryRun", False)),
        planned_actions=tuple(str(item) for item in raw.get("plannedActions", [])),
        error=error,
    )


def normalize_status(raw_status: str, rebuild_required: bool, last_error: ErrorInfo | None) -> str:
    if last_error is not None:
        return "error"
    if raw_status == "not_installed":
        return "not_installed"
    if rebuild_required:
        return "rebuild_required"
    if raw_status in STATUS_LABELS and raw_status != "unknown":
        return raw_status
    return "unknown"


def parse_menu_state(status_raw: dict[str, Any], patches_raw: dict[str, Any], prompts_raw: dict[str, Any]) -> MenuState:
    last_error = parse_error(status_raw.get("lastError"))
    rebuild_required = bool(status_raw.get("rebuildRequired"))
    status = normalize_status(str(status_raw.get("status", "unknown")), rebuild_required, last_error)
    patch_items = tuple(
        PatchMenuItem(
            patch_id=str(item["id"]),
            label=str(item.get("label", item["id"])),
            checked=bool(item.get("desiredEnabled")),
            active_enabled=bool(item.get("activeEnabled")),
            available=bool(item.get("available", True)),
            compatibility_status=str(item.get("compatibilityStatus", "unknown")),
        )
        for item in patches_raw.get("patches", [])
    )
    prompt_items = tuple(
        PromptMenuItem(
            prompt_id=str(item["id"]),
            label=str(item.get("label", item["id"])),
            checked=bool(item.get("active")),
            mode=str(item.get("mode", "append")),
            source_path=Path(str(item.get("sourcePath", ""))).expanduser(),
        )
        for item in prompts_raw.get("prompts", [])
    )
    report = status_raw.get("latestBuildReportPath")
    return MenuState(
        status=status,
        status_label=STATUS_LABELS[status],
        source_claude_version=status_raw.get("sourceClaudeVersion"),
        active_prompt=status_raw.get("activePrompt"),
        desired_patch_ids=tuple(status_raw.get("desiredPatchIds", [])),
        active_patch_ids=tuple(status_raw.get("activePatchIds", [])),
        rebuild_required=rebuild_required,
        latest_build_report_path=Path(report).expanduser() if report else None,
        active_patch_set=status_raw.get("activePatchSet"),
        current_claude_path=Path(str(status_raw["currentClaudePath"])).expanduser() if status_raw.get("currentClaudePath") else None,
        shim_target_path=Path(str(status_raw["shimTargetPath"])).expanduser() if status_raw.get("shimTargetPath") else None,
        install_record_path=Path(str(status_raw["installRecordPath"])).expanduser() if status_raw.get("installRecordPath") else None,
        last_build_strategy=str(status_raw.get("lastBuildStrategy") or status_raw.get("buildStrategy") or "unknown"),
        changed_modules=tuple(dict(item) for item in status_raw.get("changedModules", [])),
        repack_summary=status_raw.get("repackSummary"),
        state_dir=Path(str(status_raw["stateDir"])).expanduser(),
        logs_dir=Path(str(status_raw["logsDir"])).expanduser(),
        last_error=last_error,
        patch_items=patch_items,
        prompt_items=prompt_items,
    )
```

- [ ] **Step 4: Run state tests**

```bash
python3 -m pytest tests/test_menubar_state.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add src/claude_monkey/menubar_state.py tests/test_menubar_state.py
git commit -m "Add menu bar state parsing"
```

---

### Task 3: Add safe command runner, serialization, and logs

**Files:**
- Create: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/menubar_commands.py`
- Test: `/Users/MAC/Documents/Claude-patch/tests/test_menubar_commands.py`

- [ ] **Step 1: Write failing command runner tests**

Create `/Users/MAC/Documents/Claude-patch/tests/test_menubar_commands.py`:

```python
from __future__ import annotations

import sys

from claude_monkey.menubar_commands import CommandRunner, MutatingCommandBusy


def test_runner_uses_argv_list_and_shell_false(tmp_path):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        class Result:
            returncode = 0
            stdout = '{"schemaVersion":1,"ok":true,"status":"ok","summary":"ok","reportPath":null,"dryRun":false,"plannedActions":[],"error":null}'
            stderr = ""
        return Result()

    runner = CommandRunner(cli_argv=[sys.executable, "-m", "claude_monkey"], logs_dir=tmp_path, run=fake_run)
    runner.run_json(["status", "--json"], mutating=False)
    argv, kwargs = calls[0]
    assert isinstance(argv, list)
    assert kwargs["shell"] is False
    assert kwargs["capture_output"] is True
    assert kwargs["text"] is True


def test_mutating_commands_are_serialized(tmp_path):
    runner = CommandRunner(cli_argv=["claude-monkey"], logs_dir=tmp_path, run=lambda *a, **k: None)
    runner.mark_busy_for_test()
    try:
        try:
            runner.run_json(["enable", "x", "--json"], mutating=True)
        except MutatingCommandBusy:
            pass
        else:
            raise AssertionError("expected busy")
    finally:
        runner.clear_busy_for_test()


def test_worker_queue_boundary(tmp_path):
    runner = CommandRunner(cli_argv=[sys.executable, "-c"], logs_dir=tmp_path)
    runner.post_result_for_test("refresh", {"ok": True})
    assert runner.drain_results() == [("refresh", {"ok": True})]


def test_open_path_does_not_prefix_claude_monkey(tmp_path):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append((argv, kwargs))
        class Result:
            returncode = 0
            stdout = ""
            stderr = ""
        return Result()

    runner = CommandRunner(cli_argv=["claude-monkey"], logs_dir=tmp_path, run=fake_run)
    runner.open_path(tmp_path / "logs")
    argv, kwargs = calls[0]
    assert argv == ["open", str(tmp_path / "logs")]
    assert kwargs["shell"] is False


def test_nonzero_json_error_envelope_is_preserved(tmp_path):
    def fake_run(argv, **kwargs):
        class Result:
            returncode = 1
            stdout = '{"schemaVersion":1,"ok":false,"status":"error","summary":"authorization denied","reportPath":null,"targetPath":"/usr/local/bin/claude","authorizationRequired":true,"authorizationMethod":"macos_gui","dryRun":false,"plannedActions":[],"error":{"message":"authorization denied","code":"authorization_denied"}}'
            stderr = ""
        return Result()

    runner = CommandRunner(cli_argv=["claude-monkey"], logs_dir=tmp_path, run=fake_run)
    payload = runner.run_json(["install-shim", "--target", "/usr/local/bin/claude", "--json"], mutating=True)
    assert payload["error"]["code"] == "authorization_denied"
    assert payload["authorizationRequired"] is True
    assert payload["targetPath"] == "/usr/local/bin/claude"
```

- [ ] **Step 2: Run tests and verify failure**

```bash
python3 -m pytest tests/test_menubar_commands.py -q
```

Expected: FAIL because `menubar_commands.py` does not exist.

- [ ] **Step 3: Implement command runner**

Create `/Users/MAC/Documents/Claude-patch/src/claude_monkey/menubar_commands.py`:

```python
from __future__ import annotations

import json
import queue
import subprocess
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MAX_CAPTURE_CHARS = 120_000


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
        stamp = datetime.now(timezone.utc).isoformat()
        safe_stderr = stderr[:2000]
        line = json.dumps(
            {"timestamp": stamp, "command": command, "returncode": returncode, "stderr": safe_stderr},
            sort_keys=True,
        )
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def run_json(self, args: list[str], *, mutating: bool) -> dict[str, Any]:
        if self._busy_for_test and mutating:
            raise MutatingCommandBusy("another mutating command is running")
        if mutating and not self._mutating_lock.acquire(blocking=False):
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
                return {
                    "schemaVersion": 1,
                    "ok": False,
                    "status": "error",
                    "summary": stderr.strip() or f"command exited {result.returncode}",
                    "reportPath": None,
                    "targetPath": None,
                    "authorizationRequired": False,
                    "authorizationMethod": None,
                    "dryRun": False,
                    "plannedActions": [],
                    "error": {"message": stderr.strip() or f"command exited {result.returncode}", "code": "command_failed"},
                }
            raise ValueError("command succeeded but did not emit JSON")
        finally:
            if mutating:
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
            payload = self.run_json(args, mutating=mutating)
            self._results.put((name, payload))

        threading.Thread(target=worker, daemon=True).start()
```

- [ ] **Step 4: Run command runner tests**

```bash
python3 -m pytest tests/test_menubar_commands.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

```bash
git add src/claude_monkey/menubar_commands.py tests/test_menubar_commands.py
git commit -m "Add menu bar command runner"
```

---


### Task 4: Add install target and protected-path planning model

**Files:**
- Create: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/menubar_install.py`
- Test: `/Users/MAC/Documents/Claude-patch/tests/test_menubar_install.py`

- [ ] **Step 1: Write failing install target tests**

Create `/Users/MAC/Documents/Claude-patch/tests/test_menubar_install.py`:

```python
from __future__ import annotations

from pathlib import Path

from claude_monkey.menubar_install import install_plan_for_target, managed_user_target


def test_managed_user_target_is_under_state_bin(tmp_path):
    target = managed_user_target(tmp_path / ".claude-monkey")
    assert target == tmp_path / ".claude-monkey" / "bin" / "claude"


def test_user_writable_target_needs_no_authorization(tmp_path):
    target = tmp_path / ".claude-monkey" / "bin" / "claude"
    plan = install_plan_for_target(target, state_dir=tmp_path / ".claude-monkey")
    assert plan.target == target
    assert plan.authorization_required is False
    assert plan.authorization_reason is None


def test_protected_target_requires_narrow_authorization():
    target = Path("/usr/local/bin/claude")
    plan = install_plan_for_target(target, state_dir=Path("/tmp/state"))
    assert plan.authorization_required is True
    assert "protected" in (plan.authorization_reason or "")
```

- [ ] **Step 2: Run tests and verify failure**

```bash
python3 -m pytest tests/test_menubar_install.py -q
```

Expected: FAIL because `menubar_install.py` does not exist.

- [ ] **Step 3: Implement install target model**

Create `/Users/MAC/Documents/Claude-patch/src/claude_monkey/menubar_install.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class InstallTargetPlan:
    target: Path
    authorization_required: bool
    authorization_reason: str | None
    planned_actions: tuple[str, ...]


def managed_user_target(state_dir: Path) -> Path:
    return state_dir / "bin" / "claude"


def is_probably_protected_target(target: Path) -> bool:
    expanded = target.expanduser()
    protected_roots = (Path("/bin"), Path("/sbin"), Path("/usr/bin"), Path("/usr/sbin"), Path("/usr/local/bin"), Path("/opt/homebrew/bin"))
    return any(expanded == root or root in expanded.parents for root in protected_roots)


def install_plan_for_target(target: Path, *, state_dir: Path) -> InstallTargetPlan:
    expanded = target.expanduser()
    protected = is_probably_protected_target(expanded)
    return InstallTargetPlan(
        target=expanded,
        authorization_required=protected,
        authorization_reason="protected target requires narrow install authorization" if protected else None,
        planned_actions=(
            f"dry-run install-shim --target {expanded}",
            "request authorization only for install/restore operation" if protected else "install without elevation",
            "run CLI/core install transaction",
        ),
    )
```

This model is only UI planning. The CLI/core remains responsible for the real install transaction, protected write, authorization helper, and rollback evidence.

- [ ] **Step 4: Run install target tests**

```bash
python3 -m pytest tests/test_menubar_install.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 4**

```bash
git add src/claude_monkey/menubar_install.py tests/test_menubar_install.py
git commit -m "Add menu bar install target planning"
```

---

### Task 5: Add icon asset and package metadata

**Files:**
- Create: `/Users/MAC/Documents/Claude-patch/assets/claude-monkey-menubar-template.png`
- Modify: `/Users/MAC/Documents/Claude-patch/pyproject.toml`
- Test: `/Users/MAC/Documents/Claude-patch/tests/test_menubar_app_model.py`

- [ ] **Step 1: Write failing asset/metadata test**

Create `/Users/MAC/Documents/Claude-patch/tests/test_menubar_app_model.py`:

```python
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_menubar_icon_asset_exists():
    icon = ROOT / "assets" / "claude-monkey-menubar-template.png"
    assert icon.exists()
    assert icon.stat().st_size > 0
```

- [ ] **Step 2: Run test and verify failure**

```bash
python3 -m pytest tests/test_menubar_app_model.py -q
```

Expected: FAIL because the icon does not exist.

- [ ] **Step 3: Create a source-run template PNG asset**

Run this script once from repo root:

```bash
python3 - <<'PY'
from pathlib import Path
import base64

# 18x18 monochrome template asset. The pixels may be replaced during
# visual polish without changing the file contract or reducing the icon-only requirement.
PNG = b'iVBORw0KGgoAAAANSUhEUgAAABIAAAASCAYAAABWzo5XAAAACXBIWXMAAAsTAAALEwEAmpwYAAAAKUlEQVR4nGNgGAWjYBSMglEwCkbBKBjF/////w8mBoYGRkYGJgYGAB3EAxD9Jb9YAAAAAElFTkSuQmCC'
path = Path('assets/claude-monkey-menubar-template.png')
path.parent.mkdir(parents=True, exist_ok=True)
path.write_bytes(base64.b64decode(PNG))
PY
```

- [ ] **Step 4: Add optional GUI dependencies and script entrypoint**

Modify `/Users/MAC/Documents/Claude-patch/pyproject.toml`:

```toml
[project.optional-dependencies]
dev = [
  "pytest>=8.2",
  "ruff>=0.5"
]
gui = [
  "rumps>=0.4.0",
  "pyobjc-framework-Cocoa>=10.0"
]

[project.scripts]
claude-monkey = "claude_monkey.cli:main"
claude-monkey-menubar = "claude_monkey.menubar:main"
```

If the current pyproject already has these sections, combine entries rather than duplicating sections.

- [ ] **Step 5: Run asset test**

```bash
python3 -m pytest tests/test_menubar_app_model.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 5**

```bash
git add assets/claude-monkey-menubar-template.png pyproject.toml tests/test_menubar_app_model.py
git commit -m "Add ClaudeMonkey menu bar icon asset"
```

---

### Task 6: Add rumps menu bar adapter

**Files:**
- Create: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/menubar.py`
- Test: `/Users/MAC/Documents/Claude-patch/tests/test_menubar_app_model.py`

- [ ] **Step 1: Extend app model tests without importing rumps**

Append to `/Users/MAC/Documents/Claude-patch/tests/test_menubar_app_model.py`:

```python
from claude_monkey.menubar import (
    build_menu_labels,
    command_for_install_shim,
    command_for_install_shim_dry_run,
    command_for_patch_toggle,
    command_for_prompt,
    command_for_uninstall_shim,
    command_for_uninstall_shim_dry_run,
    default_install_target,
)
from claude_monkey.menubar_state import MenuState, PatchMenuItem, PromptMenuItem


def sample_state(tmp_path):
    return MenuState(
        status="rebuild_required",
        status_label="Rebuild Required",
        source_claude_version="2.1.198",
        active_prompt="research",
        desired_patch_ids=("fable-fallback",),
        active_patch_ids=(),
        rebuild_required=True,
        latest_build_report_path=None,
        active_patch_set=None,
        current_claude_path=None,
        shim_target_path=None,
        install_record_path=None,
        last_build_strategy="repack",
        changed_modules=(),
        repack_summary=None,
        state_dir=tmp_path,
        logs_dir=tmp_path / "logs",
        last_error=None,
        patch_items=(PatchMenuItem("fable-fallback", "Fable", True, False, True, "compatible"),),
        prompt_items=(PromptMenuItem("research", "Research", True, "append", tmp_path / "research.md"),),
    )


def test_build_menu_labels_contains_required_actions(tmp_path):
    labels = build_menu_labels(sample_state(tmp_path))
    assert "ClaudeMonkey: Rebuild Required" in labels
    assert "Open logs folder" in labels
    assert "Open state folder" in labels
    assert "Quit" in labels


def test_command_mapping_uses_json():
    assert command_for_patch_toggle("fable-fallback", enabled=True) == ["disable", "fable-fallback", "--json"]
    assert command_for_patch_toggle("fable-fallback", enabled=False) == ["enable", "fable-fallback", "--json"]
    target = default_install_target()
    prompt_path = target.parent / "research.md"
    assert command_for_prompt("research", prompt_path) == ["set-prompt", str(prompt_path), "--id", "research", "--from-file", "--json"]
    assert command_for_prompt(None) == ["clear-prompt", "--json"]
    assert command_for_install_shim_dry_run(target) == ["install-shim", "--target", str(target), "--json", "--dry-run"]
    assert command_for_install_shim(target) == ["install-shim", "--target", str(target), "--json"]
    assert command_for_uninstall_shim_dry_run(target=target) == ["uninstall-shim", "--target", str(target), "--json", "--dry-run"]
    assert command_for_uninstall_shim(target=target) == ["uninstall-shim", "--target", str(target), "--json"]
    record = target.parent / "record.json"
    assert command_for_uninstall_shim(record=record) == ["uninstall-shim", "--record", str(record), "--json"]
```

- [ ] **Step 2: Run tests and verify failure**

```bash
python3 -m pytest tests/test_menubar_app_model.py -q
```

Expected: FAIL because `menubar.py` does not exist.

- [ ] **Step 3: Implement rumps adapter with pure helpers**

Create `/Users/MAC/Documents/Claude-patch/src/claude_monkey/menubar.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Any

from claude_monkey.menubar_commands import CommandRunner
from claude_monkey.menubar_install import install_plan_for_target, managed_user_target
from claude_monkey.menubar_state import MenuState, parse_menu_state

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ICON = ROOT / "assets" / "claude-monkey-menubar-template.png"


def default_install_target(state: MenuState | None = None) -> Path:
    if state and state.shim_target_path:
        return state.shim_target_path
    return managed_user_target(Path.home() / ".claude-monkey")


def command_for_patch_toggle(patch_id: str, *, enabled: bool) -> list[str]:
    return ["disable" if enabled else "enable", patch_id, "--json"]


def command_for_prompt(prompt_id: str | None, source_path: Path | None = None) -> list[str]:
    if prompt_id is None:
        return ["clear-prompt", "--json"]
    if source_path is None:
        raise ValueError("source_path is required when selecting an existing prompt profile")
    return ["set-prompt", str(source_path.expanduser()), "--id", prompt_id, "--from-file", "--json"]


def command_for_install_shim_dry_run(target: Path) -> list[str]:
    return ["install-shim", "--target", str(target.expanduser()), "--json", "--dry-run"]


def command_for_install_shim(target: Path) -> list[str]:
    return ["install-shim", "--target", str(target.expanduser()), "--json"]


def command_for_uninstall_shim_dry_run(*, target: Path | None = None, record: Path | None = None) -> list[str]:
    if record is not None:
        return ["uninstall-shim", "--record", str(record.expanduser()), "--json", "--dry-run"]
    if target is None:
        raise ValueError("target or record is required")
    return ["uninstall-shim", "--target", str(target.expanduser()), "--json", "--dry-run"]


def command_for_uninstall_shim(*, target: Path | None = None, record: Path | None = None) -> list[str]:
    if record is not None:
        return ["uninstall-shim", "--record", str(record.expanduser()), "--json"]
    if target is None:
        raise ValueError("target or record is required")
    return ["uninstall-shim", "--target", str(target.expanduser()), "--json"]


def build_menu_labels(state: MenuState) -> list[str]:
    return [
        f"ClaudeMonkey: {state.status_label}",
        f"Claude Code: {state.source_claude_version or 'unknown'}",
        f"Prompt: {state.active_prompt or 'none'}",
        f"Patches: {len(state.desired_patch_ids)} enabled",
        "Prompts",
        "Patches",
        "Rebuild / Apply…",
        "Install shim…",
        "Uninstall shim…",
        "Install target…",
        "Open build report",
        "Open logs folder",
        "Open state folder",
        "Refresh",
        "Quit",
    ]


class ClaudeMonkeyMenuBar:
    def __init__(self, *, runner: CommandRunner, icon_path: Path = DEFAULT_ICON) -> None:
        try:
            import rumps
        except ImportError as exc:  # pragma: no cover - exercised manually on macOS source runs
            raise SystemExit("Install GUI deps with: python3 -m pip install -e '.[gui]'") from exc
        self.rumps = rumps
        self.runner = runner
        self.state: MenuState | None = None
        self.install_target = default_install_target()
        self.install_record: Path | None = None
        self.user_selected_install_target = False
        self.app = rumps.App(
            name="ClaudeMonkey",
            title=None,
            icon=str(icon_path),
            template=True,
            quit_button=None,
        )
        self.timer = rumps.Timer(self.drain_results, 0.25)
        self.refresh()
        self.timer.start()

    def load_state(self) -> MenuState:
        status = self.runner.run_json(["status", "--json"], mutating=False)
        patches = self.runner.run_json(["list-patches", "--json"], mutating=False)
        prompts = self.runner.run_json(["list-prompts", "--json"], mutating=False)
        return parse_menu_state(status, patches, prompts)

    def refresh(self, _sender: Any = None) -> None:
        self.state = self.load_state()
        self.install_record = self.state.install_record_path
        if not self.user_selected_install_target:
            self.install_target = default_install_target(self.state)
        self.render_menu()

    def render_menu(self) -> None:
        rumps = self.rumps
        assert self.state is not None
        self.app.menu.clear()
        for label in build_menu_labels(self.state)[:4]:
            item = rumps.MenuItem(label, callback=None)
            self.app.menu.add(item)
        self.app.menu.add(None)
        prompts = rumps.MenuItem("Prompts")
        prompts.add(rumps.MenuItem("none", callback=lambda sender: self.set_prompt(None, None)))
        for prompt in self.state.prompt_items:
            item = rumps.MenuItem(prompt.label, callback=lambda sender, p=prompt: self.set_prompt(p.prompt_id, p.source_path))
            item.state = 1 if prompt.checked else 0
            prompts.add(item)
        self.app.menu.add(prompts)
        patches = rumps.MenuItem("Patches")
        for patch in self.state.patch_items:
            item = rumps.MenuItem(patch.label, callback=lambda sender, p=patch: self.toggle_patch(p.patch_id, p.checked))
            item.state = 1 if patch.checked else 0
            patches.add(item)
        self.app.menu.add(patches)
        self.app.menu.add(None)
        self.app.menu.add(rumps.MenuItem("Rebuild / Apply…", callback=self.rebuild))
        self.app.menu.add(rumps.MenuItem(f"Install target… {self.install_target}", callback=self.choose_install_target))
        self.app.menu.add(rumps.MenuItem("Install shim…", callback=self.install_shim))
        self.app.menu.add(rumps.MenuItem("Uninstall shim…", callback=self.uninstall_shim))
        self.app.menu.add(rumps.MenuItem("Open build report", callback=self.open_build_report))
        self.app.menu.add(rumps.MenuItem("Open logs folder", callback=self.open_logs))
        self.app.menu.add(rumps.MenuItem("Open state folder", callback=self.open_state))
        self.app.menu.add(rumps.MenuItem("Refresh", callback=self.refresh))
        self.app.menu.add(rumps.MenuItem("Quit", callback=rumps.quit_application))

    def set_prompt(self, prompt_id: str | None, source_path: Path | None) -> None:
        self.runner.run_background("set_prompt", command_for_prompt(prompt_id, source_path), mutating=True)

    def toggle_patch(self, patch_id: str, enabled: bool) -> None:
        self.runner.run_background("toggle_patch", command_for_patch_toggle(patch_id, enabled=enabled), mutating=True)

    def rebuild(self, _sender: Any = None) -> None:
        if self.rumps.alert("Rebuild ClaudeMonkey patched binary?", "The official Claude binary will not be modified.", ok="Rebuild", cancel=True) == 1:
            self.runner.run_background("build", ["build", "--json"], mutating=True)

    def choose_install_target(self, _sender: Any = None) -> None:
        response = self.rumps.Window(
            message="Choose claude shim target. Protected paths are allowed but may require authorization.",
            title="ClaudeMonkey install target",
            default_text=str(self.install_target),
        ).run()
        if response.clicked:
            self.install_target = Path(response.text).expanduser()
            self.user_selected_install_target = True
            self.render_menu()

    def install_shim(self, _sender: Any = None) -> None:
        plan = install_plan_for_target(self.install_target, state_dir=Path.home() / ".claude-monkey")
        dry_run = self.runner.run_json(command_for_install_shim_dry_run(plan.target), mutating=False)
        message = "This changes which claude command your shell finds."
        if dry_run.get("authorizationRequired"):
            message += " This target requires authorization; ClaudeMonkey will request it only for the install transaction."
        if dry_run.get("plannedActions"):
            message += "\n\nPlanned: " + "; ".join(str(item) for item in dry_run["plannedActions"])
        if self.rumps.alert("Install ClaudeMonkey shim?", message, ok="Install", cancel=True) == 1:
            self.runner.run_background("install_shim", command_for_install_shim(plan.target), mutating=True)

    def uninstall_shim(self, _sender: Any = None) -> None:
        record = self.install_record if self.install_record and not self.user_selected_install_target else None
        dry_run_args = command_for_uninstall_shim_dry_run(record=record) if record else command_for_uninstall_shim_dry_run(target=self.install_target)
        real_args = command_for_uninstall_shim(record=record) if record else command_for_uninstall_shim(target=self.install_target)
        dry_run = self.runner.run_json(dry_run_args, mutating=False)
        message = "This restores the previous claude command path when possible."
        if dry_run.get("authorizationRequired"):
            message += " This target requires authorization; ClaudeMonkey will request it only for the restore transaction."
        if dry_run.get("plannedActions"):
            message += "\n\nPlanned: " + "; ".join(str(item) for item in dry_run["plannedActions"])
        if self.rumps.alert("Uninstall ClaudeMonkey shim?", message, ok="Uninstall", cancel=True) == 1:
            self.runner.run_background("uninstall_shim", real_args, mutating=True)

    def open_build_report(self, _sender: Any = None) -> None:
        if not self.state or not self.state.latest_build_report_path:
            self.rumps.alert("No build report", "No active or failed build report is available yet.")
            return
        self.runner.open_path(self.state.latest_build_report_path)

    def open_logs(self, _sender: Any = None) -> None:
        if self.state:
            self.state.logs_dir.mkdir(parents=True, exist_ok=True)
            self.runner.open_path(self.state.logs_dir)

    def open_state(self, _sender: Any = None) -> None:
        if self.state:
            self.runner.open_path(self.state.state_dir)

    def drain_results(self, _timer: Any = None) -> None:
        results = self.runner.drain_results()
        if not results:
            return
        for _name, payload in results:
            if payload.get("ok") is False:
                error = payload.get("error") or {"message": payload.get("summary", "Command failed")}
                self.rumps.alert("ClaudeMonkey command failed", str(error.get("message", "Command failed")))
        self.refresh()

    def run(self) -> None:
        self.app.run()


def main() -> int:
    runner = CommandRunner(logs_dir=Path.home() / ".claude-monkey" / "logs")
    ClaudeMonkeyMenuBar(runner=runner).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```


- [ ] **Step 4: Run model tests**

```bash
python3 -m pytest tests/test_menubar_app_model.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 6**

```bash
git add src/claude_monkey/menubar.py tests/test_menubar_app_model.py
git commit -m "Add rumps menu bar adapter"
```

---

### Task 7: Add contract acceptance fixture test

**Files:**
- Create: `/Users/MAC/Documents/Claude-patch/tests/test_v2_contract_acceptance.py`

- [ ] **Step 1: Write fixture-level acceptance test**

Create `/Users/MAC/Documents/Claude-patch/tests/test_v2_contract_acceptance.py`:

```python
from __future__ import annotations

import json

from claude_monkey.cli import main


def read_json(capsys):
    return json.loads(capsys.readouterr().out)


def test_v2_contract_acceptance_uses_one_disposable_home(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".claude-patches" / "fable-fallback").mkdir(parents=True)
    (tmp_path / ".claude-monkey" / "prompts").mkdir(parents=True)
    (tmp_path / ".claude-monkey" / "prompts" / "research.json").write_text(
        '{"id":"research","name":"Research","sourcePath":"/tmp/research.md","mode":"append"}\n'
    )

    assert main(["status", "--json"]) == 0
    assert read_json(capsys)["schemaVersion"] == 1

    assert main(["enable", "fable-fallback", "--json"]) == 0
    assert read_json(capsys)["ok"] is True

    assert main(["disable", "fable-fallback", "--json"]) == 0
    assert read_json(capsys)["ok"] is True

    prompt_source = tmp_path / ".claude-monkey" / "prompts" / "research.md"
    prompt_source.write_text("Prompt text")
    assert main(["set-prompt", str(prompt_source), "--id", "research", "--from-file", "--json"]) == 0
    assert read_json(capsys)["ok"] is True

    assert main(["clear-prompt", "--json"]) == 0
    assert read_json(capsys)["ok"] is True

    shim_target = tmp_path / ".claude-monkey" / "bin" / "claude"
    for command in (
        ["build", "--json", "--dry-run"],
        ["install-shim", "--target", str(shim_target), "--json", "--dry-run"],
        ["uninstall-shim", "--target", str(shim_target), "--json", "--dry-run"],
    ):
        assert main(command) == 0
        payload = read_json(capsys)
        assert payload["dryRun"] is True
        assert isinstance(payload["plannedActions"], list)

    for command in (
        ["install-shim", "--target", str(shim_target), "--json"],
        ["uninstall-shim", "--target", str(shim_target), "--json"],
    ):
        assert main(command) == 0
        payload = read_json(capsys)
        assert payload["dryRun"] is False
        assert payload["targetPath"] == str(shim_target)
```

- [ ] **Step 2: Run acceptance test**

```bash
python3 -m pytest tests/test_v2_contract_acceptance.py -q
```

Expected: PASS. If current main requires a built `current` symlink before real shim install, monkeypatch the CLI/core install transaction for this acceptance test rather than weakening the JSON contract. A failure here means an earlier task did not implement the documented current-main/V2 contract; stop and repair the specific earlier task before continuing.

- [ ] **Step 3: Commit Task 7**

```bash
git add src/claude_monkey/cli.py tests/test_v2_contract_acceptance.py
git commit -m "Add V2 menu bar contract acceptance test"
```

---

### Task 8: Run full verification and manual macOS smoke

**Files:**
- No new files required unless smoke notes reveal a doc update is needed.

- [ ] **Step 1: Run full unit suite**

```bash
python3 -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Run lint if the current project has ruff configured**

```bash
python3 -m ruff check src tests
```

Expected: PASS.

- [ ] **Step 3: Source-run the menu bar on macOS**

```bash
python3 -m pip install -e '.[gui]'
python3 -m claude_monkey.menubar
```

Expected:

```text
A ClaudeMonkey icon-only menu bar item appears.
No persistent text label appears in the macOS menu bar.
```

- [ ] **Step 4: Manual menu smoke checklist**

Verify manually:

```text
[ ] Icon is visible in light mode.
[ ] Icon is visible in dark mode.
[ ] Menu top line shows ClaudeMonkey status.
[ ] Prompt submenu shows checked active prompt.
[ ] Patch submenu shows checked desired patches.
[ ] Patch toggle changes desired state and shows rebuild required without auto-build.
[ ] Rebuild / Apply cancellation runs no build.
[ ] Rebuild / Apply confirmation calls current build command.
[ ] Install target defaults to ~/.claude-monkey/bin/claude and can be edited.
[ ] Install shim calls install-shim with --target and shows planned authorization state.
[ ] Uninstall shim calls uninstall-shim with --target or recorded target and shows planned authorization state.
[ ] Protected-target install/restore is exercised in a safe environment or through a safe authorization test double.
[ ] Open build report opens the latest report or shows a no-report alert.
[ ] Open logs folder opens ~/.claude-monkey/logs.
[ ] Open state folder opens ~/.claude-monkey.
[ ] Simulated CLI failure shows error alert and leaves Refresh available.
[ ] Quit exits through rumps.quit_application().
```

- [ ] **Step 5: Capture any manual caveat in docs if needed**

If rumps requires a local macOS-specific workaround, add a short note to `/Users/MAC/Documents/Claude-patch/docs/superpowers/specs/2026-07-02-claude-monkey-v2-menubar-design.md` or a README section. Do not add packaging/notarization work unless explicitly requested.

- [ ] **Step 6: Final review gate**

Request adversarial code review over the full V2 implementation range.

```bash
git log --oneline --decorate -8
git diff --stat $(git rev-parse HEAD~7)..HEAD
git diff $(git rev-parse HEAD~7)..HEAD
```

Expected review result: no Critical or Important issues before presenting execution completion.

- [ ] **Step 7: Commit any final smoke/doc fixes**

```bash
git add docs/superpowers/specs/2026-07-02-claude-monkey-v2-menubar-design.md src/claude_monkey tests assets pyproject.toml
git commit -m "Finalize ClaudeMonkey V2 menu bar"
```

Only run this commit if there were final fixes. Do not create an empty commit.
