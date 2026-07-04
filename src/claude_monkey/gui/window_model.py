"""Pure view-models deciding everything the tray and window render.

This module is the single source of truth for what the ClaudeMonkey v3 GUI
displays and which controls are enabled. It must never import a GUI toolkit
and must never perform I/O -- the Qt-based files (later tasks) are thin
renderers over these dataclasses/functions.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from claude_monkey.menubar_install import managed_user_target
from claude_monkey.menubar_state import MenuState, OptionMenuItem, PatchMenuItem, PromptMenuItem

COMMON_INSTALL_TARGETS = (
    Path("/usr/local/bin/claude"),
    Path("/opt/homebrew/bin/claude"),
)


@dataclass(frozen=True)
class TrayModel:
    status_lines: tuple[str, ...]
    running_label: str | None
    mutating_enabled: bool
    show_install_shim: bool
    prompt_items: tuple[PromptMenuItem, ...]
    patch_items: tuple[PatchMenuItem, ...]
    option_items: tuple[OptionMenuItem, ...]


def _status_lines(state: MenuState) -> tuple[str, ...]:
    option_label = f"Options: {len(state.active_option_ids)} active"
    if state.high_risk_warnings:
        option_label += " ⚠"
    return (
        f"ClaudeMonkey: {state.status_label}",
        f"Claude Code: {state.source_claude_version or 'unknown'}",
        f"Prompt: {state.active_prompt or 'none'}",
        option_label,
        f"Patches: {len(state.desired_patch_ids)} enabled",
    )


def build_tray_model(state: MenuState | None, busy_command: str | None) -> TrayModel:
    if state is None:
        return TrayModel(
            status_lines=("ClaudeMonkey: Error",),
            running_label=None,
            mutating_enabled=False,
            show_install_shim=True,
            prompt_items=(),
            patch_items=(),
            option_items=(),
        )
    return TrayModel(
        status_lines=_status_lines(state),
        running_label=f"Running: {busy_command}" if busy_command else None,
        mutating_enabled=busy_command is None,
        show_install_shim=not state.shim_installed,
        prompt_items=state.prompt_items,
        patch_items=state.patch_items,
        option_items=state.option_items,
    )


def patch_menu_label(patch: PatchMenuItem) -> str:
    if not patch.available:
        return f"{patch.label} — unavailable"
    if patch.compatibility_status not in {"compatible", "unknown", "unconstrained"}:
        detail = patch.compatibility_message or patch.compatibility_status
        return f"{patch.label} — {detail}"
    return patch.label


def patch_item_enabled(patch: PatchMenuItem, *, mutating_enabled: bool) -> bool:
    if not mutating_enabled:
        return False
    if patch.checked:
        return True
    if not patch.available:
        return False
    return patch.compatibility_status in {"compatible", "unknown", "unconstrained"}


def option_item_enabled(option: OptionMenuItem, *, mutating_enabled: bool) -> bool:
    # Enabling a requires_confirmation option is allowed here; the confirm
    # dialog (owned by a later task) handles the actual high-risk gate.
    return mutating_enabled and option.valid


def default_install_target(state: MenuState | None = None) -> Path:
    if state and state.shim_target_path:
        return state.shim_target_path
    if state and state.detected_claude_command_path:
        return state.detected_claude_command_path
    return managed_user_target(Path.home() / ".claude-monkey")


def install_target_choices(state: MenuState | None) -> tuple[tuple[str, Path], ...]:
    state_dir = state.state_dir if state else Path.home() / ".claude-monkey"
    choices: list[tuple[str, Path]] = [
        ("Use managed user target", managed_user_target(state_dir)),
    ]
    if state and state.shim_target_path:
        choices.append(("Use recorded target", state.shim_target_path))
    if state and state.detected_claude_command_path:
        choices.append(("Use detected claude command", state.detected_claude_command_path))
    for target in COMMON_INSTALL_TARGETS:
        choices.append((f"Use {target}", target))

    deduped: list[tuple[str, Path]] = []
    seen: set[str] = set()
    for label, target in choices:
        key = str(target.expanduser())
        if key not in seen:
            deduped.append((label, target.expanduser()))
            seen.add(key)
    return tuple(deduped)


class InstallTargetSelection:
    """Shared tray/window install-target state.

    Tracks the user's explicit choice (if any); falls back to
    `default_install_target(state)` until the user selects a path.
    """

    def __init__(self) -> None:
        self._selected: Path | None = None
        self.user_selected: bool = False

    def target(self, state: MenuState | None) -> Path:
        if self.user_selected and self._selected is not None:
            return self._selected
        return default_install_target(state)

    def select(self, path: Path) -> None:
        self._selected = Path(path).expanduser()
        self.user_selected = True


def remove_enabled(item_kind: str, package_id: str, state: MenuState) -> tuple[bool, str]:
    """Decide whether a package may be removed from the GUI.

    Mirrors the CLI/core rule (Task 6): removal is refused only when the
    active profile still references the package -- a patch in the desired
    set, the active prompt, or an enabled option. Whether the package is
    baked into the currently built/active binary does NOT block removal.
    """
    referenced = False
    if item_kind == "patch":
        referenced = package_id in state.desired_patch_ids
    elif item_kind == "prompt":
        referenced = package_id == state.active_prompt
    elif item_kind == "option":
        referenced = package_id in state.active_option_ids

    if referenced:
        return False, f"{package_id} is referenced by the active profile; disable it first."
    return True, ""
