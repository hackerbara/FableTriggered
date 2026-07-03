from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from claude_monkey.menubar_commands import CommandRunner
from claude_monkey.menubar_install import install_plan_for_target, managed_user_target
from claude_monkey.menubar_state import MenuState, parse_menu_state

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ICON = ROOT / "assets" / "claude-monkey-menubar-template.png"
COMMON_INSTALL_TARGETS = (
    Path("/usr/local/bin/claude"),
    Path("/opt/homebrew/bin/claude"),
)
REBUILD_CONFIRMATION_BODY = (
    "This will build a copied Claude Code binary from the selected patches, verify it, "
    "sign it, smoke-test it, and activate it only if the build succeeds. The official "
    "Claude binary will not be modified."
)


@dataclass(frozen=True)
class AlertPlan:
    title: str
    message: str
    ok: str = "OK"
    open_path: Path | None = None


def default_install_target(state: MenuState | None = None) -> Path:
    if state and state.shim_target_path:
        return state.shim_target_path
    return managed_user_target(Path.home() / ".claude-monkey")


def command_for_patch_toggle(patch_id: str, *, enabled: bool) -> list[str]:
    return ["disable" if enabled else "enable", patch_id, "--json"]


def command_for_rebuild_apply() -> list[str]:
    return ["build", "--json", "--activate"]


def command_for_prompt(prompt_id: str | None, source_path: Path | None = None) -> list[str]:
    if prompt_id is None:
        return ["clear-prompt", "--json"]
    if source_path is None:
        raise ValueError("source_path is required when selecting an existing prompt profile")
    return [
        "set-prompt",
        str(source_path.expanduser()),
        "--id",
        prompt_id,
        "--from-file",
        "--json",
    ]


def command_for_install_shim_dry_run(target: Path) -> list[str]:
    return ["install-shim", "--target", str(target.expanduser()), "--json", "--dry-run"]


def command_for_install_shim(target: Path) -> list[str]:
    return ["install-shim", "--target", str(target.expanduser()), "--json"]


def command_for_uninstall_shim_dry_run(
    *, target: Path | None = None, record: Path | None = None
) -> list[str]:
    if record is not None:
        return ["uninstall-shim", "--record", str(record.expanduser()), "--json", "--dry-run"]
    if target is None:
        raise ValueError("target or record is required")
    return ["uninstall-shim", "--target", str(target.expanduser()), "--json", "--dry-run"]


def command_for_uninstall_shim(
    *, target: Path | None = None, record: Path | None = None
) -> list[str]:
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


def install_target_menu_label(target: Path, *, state_dir: Path) -> str:
    plan = install_plan_for_target(target, state_dir=state_dir)
    status = "protected" if plan.authorization_required else "user-writable"
    return f"Install target… {plan.target} ({status})"


def install_target_choices(state: MenuState | None) -> tuple[tuple[str, Path], ...]:
    state_dir = state.state_dir if state else Path.home() / ".claude-monkey"
    choices: list[tuple[str, Path]] = [
        ("Use managed user target", managed_user_target(state_dir)),
    ]
    if state and state.shim_target_path:
        choices.append(("Use recorded target", state.shim_target_path))
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


def alert_for_result(
    name: str, payload: dict[str, Any], state: MenuState | None
) -> AlertPlan | None:
    if payload.get("ok") is False:
        error = payload.get("error") if isinstance(payload.get("error"), dict) else {}
        message = str(error.get("message") or payload.get("summary") or "Command failed")
        report = payload.get("reportPath")
        logs_dir = state.logs_dir if state else Path.home() / ".claude-monkey" / "logs"
        if name == "build":
            if report:
                return AlertPlan(
                    "ClaudeMonkey build failed",
                    f"{message}\n\nOpen report or use Open logs folder for details.",
                    ok="Open report",
                    open_path=Path(str(report)).expanduser(),
                )
            return AlertPlan(
                "ClaudeMonkey build failed",
                f"{message}\n\nOpen logs folder for details.",
                ok="Open logs",
                open_path=logs_dir,
            )
        return AlertPlan("ClaudeMonkey command failed", message)

    if name == "set_prompt":
        return AlertPlan(
            "ClaudeMonkey prompt selected", "Prompt will apply on next Claude launch."
        )
    if name == "build":
        summary = str(payload.get("summary") or "Build activated")
        active_patch_set = state.active_patch_set if state else None
        report = payload.get("reportPath") or (
            str(state.latest_build_report_path)
            if state and state.latest_build_report_path is not None
            else None
        )
        return AlertPlan(
            "ClaudeMonkey build complete",
            f"{summary}\nActive patch set: {active_patch_set or 'unknown'}\n"
            f"Report: {report or 'unknown'}",
        )
    if name == "install_shim":
        summary = str(payload.get("summary") or "Installed managed ClaudeMonkey shim")
        target = str(payload.get("targetPath") or "unknown target")
        return AlertPlan("ClaudeMonkey shim installed", f"{summary}\nTarget: {target}")
    if name == "uninstall_shim":
        summary = str(payload.get("summary") or "Uninstalled managed ClaudeMonkey shim")
        target = str(payload.get("targetPath") or "unknown target")
        return AlertPlan("ClaudeMonkey shim uninstalled", f"{summary}\nTarget: {target}")
    return None


class ClaudeMonkeyMenuBar:
    def __init__(self, *, runner: CommandRunner, icon_path: Path = DEFAULT_ICON) -> None:
        try:
            import rumps
        except ImportError as exc:  # pragma: no cover - exercised by macOS source runs.
            raise SystemExit("Install GUI deps with: python3 -m pip install -e '.[gui]'") from exc

        self.rumps = rumps
        self.runner = runner
        self.state: MenuState | None = None
        self.install_target = default_install_target()
        self.install_record: Path | None = None
        self.user_selected_install_target = False
        self.busy_command: str | None = None
        self.last_error_message: str | None = None
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
        try:
            state = self.load_state()
        except Exception as exc:
            self.last_error_message = str(exc)
            self._log_ui_event("refresh_failed", message=self.last_error_message)
            self.render_error_menu()
            self._alert("ClaudeMonkey refresh failed", self.last_error_message)
            return
        self.state = state
        self.last_error_message = None
        self.install_record = self.state.install_record_path
        if not self.user_selected_install_target:
            self.install_target = default_install_target(self.state)
        self.render_menu()

    def _set_menu_item_enabled(self, item: Any, enabled: bool) -> None:
        item.enabled = enabled
        native = getattr(item, "_menuitem", None)
        if native is not None and hasattr(native, "setEnabled_"):
            native.setEnabled_(enabled)

    def _menu_item(self, label: str, callback: Any = None, *, enabled: bool = True) -> Any:
        item = self.rumps.MenuItem(label, callback=callback if enabled else None)
        self._set_menu_item_enabled(item, enabled)
        return item

    def render_error_menu(self) -> None:
        self.app.menu.clear()
        self.app.menu.add(self._menu_item("ClaudeMonkey: Error", enabled=False))
        if self.last_error_message:
            self.app.menu.add(self._menu_item(self.last_error_message, enabled=False))
        self.app.menu.add(None)
        self.app.menu.add(self._menu_item("Open logs folder", callback=self.open_logs))
        self.app.menu.add(self._menu_item("Open state folder", callback=self.open_state))
        self.app.menu.add(self._menu_item("Refresh", callback=self.refresh))
        self.app.menu.add(self._menu_item("Quit", callback=self.rumps.quit_application))

    def _log_ui_event(self, event: str, **fields: Any) -> None:
        log_ui_event = getattr(self.runner, "log_ui_event", None)
        if callable(log_ui_event):
            log_ui_event(event, **fields)

    def _activate_for_modal(self) -> None:
        try:
            from AppKit import (  # type: ignore[import-not-found]
                NSApplication,
                NSApplicationActivateIgnoringOtherApps,
                NSRunningApplication,
            )
        except Exception:
            return
        try:
            app = NSApplication.sharedApplication()
            if app is not None:
                app.activateIgnoringOtherApps_(True)
        except Exception:
            pass
        try:
            NSRunningApplication.currentApplication().activateWithOptions_(
                NSApplicationActivateIgnoringOtherApps
            )
        except Exception:
            pass

    def _alert(self, title: str, message: str = "", **kwargs: Any) -> Any:
        self._activate_for_modal()
        return self.rumps.alert(title, message, **kwargs)

    def render_menu(self) -> None:
        rumps = self.rumps
        if self.state is None:
            return
        self.app.menu.clear()
        for label in build_menu_labels(self.state)[:4]:
            self.app.menu.add(self._menu_item(label, callback=None, enabled=False))
        mutating_enabled = self.busy_command is None
        if self.busy_command:
            self.app.menu.add(self._menu_item(f"Running: {self.busy_command}", enabled=False))
        self.app.menu.add(None)

        prompts = rumps.MenuItem("Prompts")
        none_item = self._menu_item(
            "none",
            callback=lambda _sender: self.set_prompt(None, None),
            enabled=mutating_enabled,
        )
        none_item.state = 1 if self.state.active_prompt is None else 0
        prompts.add(none_item)
        for prompt in self.state.prompt_items:
            item = self._menu_item(
                prompt.label,
                callback=lambda _sender, p=prompt: self.set_prompt(
                    p.prompt_id, p.source_path
                ),
                enabled=mutating_enabled,
            )
            item.state = 1 if prompt.checked else 0
            prompts.add(item)
        self.app.menu.add(prompts)

        patches = rumps.MenuItem("Patches")
        for patch in self.state.patch_items:
            item = self._menu_item(
                patch.label,
                callback=lambda _sender, p=patch: self.toggle_patch(p.patch_id, p.checked),
                enabled=mutating_enabled,
            )
            item.state = 1 if patch.checked else 0
            patches.add(item)
        self.app.menu.add(patches)

        self.app.menu.add(None)
        self.app.menu.add(
            self._menu_item(
                "Rebuild / Apply…", callback=self.rebuild, enabled=mutating_enabled
            )
        )
        state_dir = self.state.state_dir if self.state else Path.home() / ".claude-monkey"
        self.app.menu.add(self._install_target_menu(state_dir, mutating_enabled))
        self.app.menu.add(
            self._menu_item("Install shim…", callback=self.install_shim, enabled=mutating_enabled)
        )
        self.app.menu.add(
            self._menu_item(
                "Uninstall shim…", callback=self.uninstall_shim, enabled=mutating_enabled
            )
        )
        self.app.menu.add(self._menu_item("Open build report", callback=self.open_build_report))
        self.app.menu.add(self._menu_item("Open logs folder", callback=self.open_logs))
        self.app.menu.add(self._menu_item("Open state folder", callback=self.open_state))
        self.app.menu.add(self._menu_item("Refresh", callback=self.refresh))
        self.app.menu.add(self._menu_item("Quit", callback=rumps.quit_application))

    def _start_mutating_command(self, name: str, args: list[str]) -> None:
        if self.busy_command is not None:
            self._alert(
                "ClaudeMonkey is busy", f"{self.busy_command} is already running."
            )
            return
        self.busy_command = name
        self.render_menu()
        self.runner.run_background(name, args, mutating=True)

    def set_prompt(self, prompt_id: str | None, source_path: Path | None) -> None:
        self._start_mutating_command("set_prompt", command_for_prompt(prompt_id, source_path))

    def toggle_patch(self, patch_id: str, enabled: bool) -> None:
        self._start_mutating_command(
            "toggle_patch", command_for_patch_toggle(patch_id, enabled=enabled)
        )

    def rebuild(self, _sender: Any = None) -> None:
        response = self._alert(
            "Rebuild ClaudeMonkey patched binary?",
            REBUILD_CONFIRMATION_BODY,
            ok="Rebuild",
            cancel=True,
        )
        if response == 1:
            self._start_mutating_command("build", command_for_rebuild_apply())

    def _install_target_menu(self, state_dir: Path, mutating_enabled: bool) -> Any:
        menu = self._menu_item(
            install_target_menu_label(self.install_target, state_dir=state_dir),
            enabled=mutating_enabled,
        )
        for label, target in install_target_choices(self.state):
            item = self._menu_item(
                f"{label}: {target}",
                callback=lambda _sender, t=target: self.set_install_target(t),
                enabled=mutating_enabled,
            )
            item.state = 1 if target == self.install_target else 0
            menu.add(item)
        menu.add(
            self._menu_item(
                "Use path from clipboard…",
                callback=lambda _sender: self.choose_install_target_from_clipboard(),
                enabled=mutating_enabled,
            )
        )
        return menu

    def set_install_target(self, target: Path) -> None:
        self.install_target = target.expanduser()
        self.user_selected_install_target = True
        self.render_menu()

    def clipboard_text(self) -> str:
        try:
            from AppKit import NSPasteboard, NSPasteboardTypeString
        except ImportError:
            return ""
        pasteboard = NSPasteboard.generalPasteboard()
        value = pasteboard.stringForType_(NSPasteboardTypeString)
        return str(value or "").strip()

    def choose_install_target_from_clipboard(self) -> None:
        text = self.clipboard_text()
        if not text:
            self._alert(
                "No install target on clipboard",
                "Copy a target path first, then choose Use path from clipboard.",
            )
            return
        self.set_install_target(Path(text).expanduser())

    def install_shim(self, _sender: Any = None) -> None:
        state_dir = self.state.state_dir if self.state else Path.home() / ".claude-monkey"
        plan = install_plan_for_target(self.install_target, state_dir=state_dir)
        dry_run = self.runner.run_json(
            command_for_install_shim_dry_run(plan.target), mutating=False
        )
        if dry_run.get("ok") is False:
            self._alert_preflight_failure("install", dry_run)
            return
        message = "This changes which claude command your shell finds."
        if dry_run.get("authorizationRequired"):
            message += (
                " This target requires authorization; ClaudeMonkey will request it only "
                "for the install transaction."
            )
        if dry_run.get("plannedActions"):
            message += "\n\nPlanned: " + "; ".join(str(item) for item in dry_run["plannedActions"])
        if self._alert("Install ClaudeMonkey shim?", message, ok="Install", cancel=True) == 1:
            self._start_mutating_command("install_shim", command_for_install_shim(plan.target))

    def uninstall_shim(self, _sender: Any = None) -> None:
        record = (
            self.install_record
            if self.install_record and not self.user_selected_install_target
            else None
        )
        dry_run_args = (
            command_for_uninstall_shim_dry_run(record=record)
            if record
            else command_for_uninstall_shim_dry_run(target=self.install_target)
        )
        real_args = (
            command_for_uninstall_shim(record=record)
            if record
            else command_for_uninstall_shim(target=self.install_target)
        )
        dry_run = self.runner.run_json(dry_run_args, mutating=False)
        if dry_run.get("ok") is False:
            self._alert_preflight_failure("uninstall", dry_run)
            return
        message = "This restores the previous claude command path when possible."
        if dry_run.get("authorizationRequired"):
            message += (
                " This target requires authorization; ClaudeMonkey will request it only "
                "for the restore transaction."
            )
        if dry_run.get("plannedActions"):
            message += "\n\nPlanned: " + "; ".join(str(item) for item in dry_run["plannedActions"])
        if (
            self._alert(
                "Uninstall ClaudeMonkey shim?", message, ok="Uninstall", cancel=True
            )
            == 1
        ):
            self._start_mutating_command("uninstall_shim", real_args)

    def _alert_preflight_failure(self, action: str, payload: dict[str, Any]) -> None:
        error = payload.get("error") if isinstance(payload.get("error"), dict) else {}
        message = str(error.get("message") or payload.get("summary") or "Preflight failed")
        self._alert(f"ClaudeMonkey {action} preflight failed", message)

    def open_build_report(self, _sender: Any = None) -> None:
        if not self.state or not self.state.latest_build_report_path:
            self._alert(
                "No build report", "No active or failed build report is available yet."
            )
            return
        self.runner.open_path(self.state.latest_build_report_path)

    def open_logs(self, _sender: Any = None) -> None:
        logs_dir = self.state.logs_dir if self.state else Path.home() / ".claude-monkey" / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        self.runner.open_path(logs_dir)

    def open_state(self, _sender: Any = None) -> None:
        state_dir = self.state.state_dir if self.state else Path.home() / ".claude-monkey"
        state_dir.mkdir(parents=True, exist_ok=True)
        self.runner.open_path(state_dir)

    def drain_results(self, _timer: Any = None) -> None:
        results = self.runner.drain_results()
        if not results:
            return
        refresh_failed = False
        for name, payload in results:
            if self.busy_command == name:
                self.busy_command = None
            try:
                state = self.load_state()
            except Exception as exc:
                self.last_error_message = str(exc)
                self._log_ui_event("refresh_failed", message=self.last_error_message)
                refresh_failed = True
                self._alert("ClaudeMonkey refresh failed", self.last_error_message)
            else:
                self.state = state
                self.last_error_message = None
                self.install_record = self.state.install_record_path
                if not self.user_selected_install_target:
                    self.install_target = default_install_target(self.state)
            alert = alert_for_result(name, payload, self.state)
            if alert is not None:
                self._show_alert(alert)
        if refresh_failed or self.state is None:
            self.render_error_menu()
        else:
            self.render_menu()

    def _show_alert(self, alert: AlertPlan) -> None:
        response = self._alert(
            alert.title,
            alert.message,
            ok=alert.ok,
            cancel=alert.open_path is not None,
        )
        if response == 1 and alert.open_path is not None:
            self.runner.open_path(alert.open_path)

    def run(self) -> None:
        self.app.run()


def main() -> int:
    runner = CommandRunner(logs_dir=Path.home() / ".claude-monkey" / "logs")
    ClaudeMonkeyMenuBar(runner=runner).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
