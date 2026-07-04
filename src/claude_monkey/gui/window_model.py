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
class NoticeModel:
    """Pure description of the shim-update-resilience notice (spec sec4).

    `message` is already de-jargoned, ready to render verbatim. `digest` is
    the `detectedOfficialSha256` this notice is *about* -- the key the
    Controller's dismissed-digest set (R5) tracks; it may be `None` for the
    post-repair informational state, which has no digest to key on and
    (being non-dismissable in practice, since it carries no action) does not
    need one. `actions` is a subset of `("repair", "rollout")`, in the order
    they should render; an empty tuple means informational-only -- no button.
    """

    message: str
    digest: str | None
    actions: tuple[str, ...]


@dataclass(frozen=True)
class TrayModel:
    status_lines: tuple[str, ...]
    running_label: str | None
    mutating_enabled: bool
    show_install_shim: bool
    prompt_items: tuple[PromptMenuItem, ...]
    patch_items: tuple[PatchMenuItem, ...]
    option_items: tuple[OptionMenuItem, ...]
    notice: NoticeModel | None = None


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


def mutating_controls_enabled(busy_command: str | None) -> bool:
    """Whether every mutating control should be enabled right now.

    A command is "in flight" exactly when `busy_command` (`Controller.
    _busy_command`) is not `None`. This is the single source of truth for
    that rule -- `build_tray_model` (via `TrayModel.mutating_enabled`) and
    the window/pages (via `SettingsWindow.render`'s `busy_command` param)
    both read it, so the tray and every window page (Patches/Options/
    Prompts/Install checkboxes, add/remove buttons, the rebuild button)
    always agree on which controls are safe to click. Non-mutating controls
    (page navigation, log viewing, quit) never consult this at all.
    """
    return busy_command is None


def build_tray_model(
    state: MenuState | None,
    busy_command: str | None,
    notice: NoticeModel | None = None,
) -> TrayModel:
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
        mutating_enabled=mutating_controls_enabled(busy_command),
        show_install_shim=not state.shim_installed,
        prompt_items=state.prompt_items,
        patch_items=state.patch_items,
        option_items=state.option_items,
        notice=notice,
    )


# ---------------------------------------------------------------------------
# shim-update-resilience notice (spec 2026-07-04 sec4/sec5, R2/R5/R7/R8)
# ---------------------------------------------------------------------------


def _short_digest(digest: str | None) -> str | None:
    return digest[:8] if digest else None


def _repair_needed_message(state: MenuState) -> str:
    if state.detected_official_version:
        return f"Claude {state.detected_official_version} available — shim repair needed"
    short = _short_digest(state.detected_official_sha256)
    if short:
        return f"New Claude build available ({short}…) — shim repair needed"
    return "New Claude build available — shim repair needed"


def _rollout_message(state: MenuState) -> str:
    if state.detected_official_version:
        return f"Claude {state.detected_official_version} available — rebuild to roll out"
    short = _short_digest(state.detected_official_sha256)
    if short:
        return f"New Claude build available ({short}…) — rebuild to roll out"
    return "New Claude build available — rebuild to roll out"


def build_notice_model(
    state: MenuState, dismissed_digests: frozenset[str] | set[str]
) -> NoticeModel | None:
    """The single choke point deciding the shim-update-resilience notice.

    Pure function of `MenuState` (already-parsed status fields) plus the
    Controller-held set of dismissed digests (R5: in-memory, per-process --
    see the GUI report for why that's acceptable for v1). Mirrors
    `compatibility_display`'s discipline: every label here is already
    plain-language, per spec sec4 + R7's fallback rule (first 8 hex of the
    digest when the version couldn't be extracted).

    Two distinct states can produce a notice:
      - `targetReplacedByOfficial`: an official update clobbered the
        managed shim. Offers `("repair",)` when `shimRepairAvailable` is
        also true (it always should be whenever the target was replaced,
        but this never assumes that without checking -- a notice must
        never offer a button with no working action behind it).
      - Post-repair rollout required (`rolloutRequired` true while the shim
        is installed again): informational only (`actions=()`) -- there is
        no CLI-safe way to wire a rollout action today (`rebuild` does not
        consume the repair's newly cached source; see the GUI report's
        rollout investigation). Not reachable via the current, merged
        `status.py` (an installed shim always forces `rolloutRequired`
        false there today) -- modeled here anyway so the label/actions
        contract is pinned for when that gap closes.

    Returns `None` when neither state applies, or when the replacement's
    digest has already been dismissed (R5: dismissal is per-digest and
    recurring -- a new digest always re-raises the notice).
    """
    if state.target_replaced_by_official:
        digest = state.detected_official_sha256
        if digest is not None and digest in dismissed_digests:
            return None
        actions = ("repair",) if state.shim_repair_available else ()
        return NoticeModel(message=_repair_needed_message(state), digest=digest, actions=actions)

    if state.rollout_required and state.shim_installed:
        digest = state.detected_official_sha256
        if digest is not None and digest in dismissed_digests:
            return None
        return NoticeModel(message=_rollout_message(state), digest=digest, actions=())

    return None


def repair_confirm_text(state: MenuState | None) -> str:
    """Confirm-dialog body for the repair-shim action (R2: user-triggered).

    `repair-shim` has no `--dry-run`/`--progress` flags (see
    `src/claude_monkey/cli.py`'s `repair_shim_parser`), so unlike
    `install_shim`/`uninstall_shim` there is no CLI round-trip to build this
    text from a live payload -- it is built entirely from the already-known
    `MenuState`, the same way `Controller._rebuild_confirm_text` builds
    `rebuild`'s confirm text from state instead of an extra subprocess call.
    """
    if state is None or not (state.detected_official_version or state.detected_official_sha256):
        return (
            "Repair the ClaudeMonkey shim?\n\n"
            "This restores launches through PATH to go through ClaudeMonkey."
        )
    if state.detected_official_version:
        detail = f"Claude {state.detected_official_version}"
    else:
        detail = f"Claude build {_short_digest(state.detected_official_sha256)}…"
    return (
        f"Repair the ClaudeMonkey shim for {detail}?\n\n"
        "This restores launches through PATH to go through ClaudeMonkey. "
        "The newly detected official build is cached first so it can still "
        "be rolled out later."
    )


# Refusal codes raised by `repair.py`'s `RepairRefused` (surfaced via
# `cli.py`'s `handle_repair_shim` error envelope `error.code`), plus the
# CLI-layer `missing_target` code from `cli._resolve_cache_or_repair_target`.
# Every code must map to plain language here -- see `compatibility_display`
# for the precedent this follows: internal codes must never reach the UI.
_REPAIR_REFUSAL_MESSAGES = {
    "already_installed": "The shim is already installed correctly — nothing to repair.",
    "not_managed": "ClaudeMonkey has no record of managing this Claude target — repair refused.",
    "target_changed": "Claude changed again — re-checking.",
    "target_unavailable": "The Claude target is not available right now — re-checking.",
    "managed_path_refused": (
        "That target is one of ClaudeMonkey's own managed paths — repair refused."
    ),
    "authorization_required": (
        "This target needs elevated permission — use Install shim instead."
    ),
    "cache_failed": "Could not cache the current Claude build — repair refused.",
    "swap_failed": "Could not install the repaired shim — repair refused.",
    "no_install_record": "ClaudeMonkey has no install record for this target — repair refused.",
    "invalid_record": "ClaudeMonkey's install record is unreadable — repair refused.",
    "missing_target": "No Claude target is known to repair.",
}
_REPAIR_REFUSAL_FALLBACK = "Shim repair failed."


def repair_refusal_display(code: str | None, fallback: str = _REPAIR_REFUSAL_FALLBACK) -> str:
    """Map a `repair-shim` refusal `error.code` to plain UI text.

    Every raw code from `repair.py`/`cli.py` is covered by
    `_REPAIR_REFUSAL_MESSAGES`; an unrecognized or missing code falls back
    to `fallback` rather than ever rendering the code (or a raw CLI
    exception string) verbatim -- refusal codes must never appear raw in
    the UI (plan Global Constraints).
    """
    if code is None:
        return fallback
    return _REPAIR_REFUSAL_MESSAGES.get(code, fallback)


HEALTHY_COMPATIBILITY_STATUSES = frozenset(
    {"compatible", "unknown", "unconstrained", "constrained"}
)
_COMPATIBILITY_FALLBACK_TEXT = "Not compatible with this Claude version"


def compatibility_display(status: str, message: str | None = None) -> str:
    """Map an internal compatibility status word to UI-safe text.

    The CLI's internal status vocabulary (``compatible``, ``unknown``,
    ``unconstrained``, ``version_mismatch``, ``sha_mismatch``,
    ``constrained``, ...) must never render verbatim in the UI -- it only
    makes sense to someone who understands ClaudeMonkey's internals.

    Healthy/neutral statuses render as an empty string: the row already
    shows the package name, and that's enough. ``constrained`` belongs in
    this bucket -- it only means the manifest *declares* a compatibility
    constraint, not that a check failed (actual failures surface as
    ``version_mismatch``/``sha_mismatch``). Anything else is a problem
    status, so it renders the CLI-supplied, already human-phrased
    ``message`` when one is available, or a short generic fallback when it
    isn't. This is the single place every GUI surface routes compatibility
    text through -- no caller should format ``status`` itself.
    """
    if status in HEALTHY_COMPATIBILITY_STATUSES:
        return ""
    return message or _COMPATIBILITY_FALLBACK_TEXT


def patch_menu_label(patch: PatchMenuItem) -> str:
    if not patch.available:
        return f"{patch.label} — unavailable"
    detail = compatibility_display(patch.compatibility_status, patch.compatibility_message)
    if detail:
        return f"{patch.label} — {detail}"
    return patch.label


def patch_item_enabled(patch: PatchMenuItem, *, mutating_enabled: bool) -> bool:
    if not mutating_enabled:
        return False
    if patch.checked:
        return True
    if not patch.available:
        return False
    return patch.compatibility_status in HEALTHY_COMPATIBILITY_STATUSES


def option_item_enabled(option: OptionMenuItem, *, mutating_enabled: bool) -> bool:
    # Enabling a requires_confirmation option is allowed here; the confirm
    # dialog (owned by a later task) handles the actual high-risk gate.
    return mutating_enabled and option.valid


def rebuild_button_enabled(state: MenuState | None, *, mutating_enabled: bool) -> bool:
    """Whether the Overview page's "Rebuild / Apply" button should be enabled.

    Mirrors `patch_item_enabled`/`option_item_enabled`'s discipline: the page
    consumes this, it never re-derives "disconnected or busy" itself.
    """
    return state is not None and mutating_enabled


def install_button_enabled(state: MenuState | None, *, mutating_enabled: bool) -> bool:
    """Whether the Install page's "Install" button should be enabled."""
    return state is not None and mutating_enabled and not state.shim_installed


def uninstall_button_enabled(state: MenuState | None, *, mutating_enabled: bool) -> bool:
    """Whether the Install page's "Uninstall" button should be enabled."""
    return state is not None and mutating_enabled and state.shim_installed


def default_install_target(state: MenuState | None = None) -> Path:
    if state and state.shim_target_path:
        return state.shim_target_path
    if state and state.detected_claude_command_path:
        return state.detected_claude_command_path
    state_dir = state.state_dir if state else Path.home() / ".claude-monkey"
    return managed_user_target(state_dir)


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
