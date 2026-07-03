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
        if self.state is None:
            return
        self.app.menu.clear()
        for label in build_menu_labels(self.state)[:4]:
            self.app.menu.add(rumps.MenuItem(label, callback=None))
        self.app.menu.add(None)

        prompts = rumps.MenuItem("Prompts")
        prompts.add(rumps.MenuItem("none", callback=lambda _sender: self.set_prompt(None, None)))
        for prompt in self.state.prompt_items:
            item = rumps.MenuItem(
                prompt.label,
                callback=lambda _sender, p=prompt: self.set_prompt(
                    p.prompt_id, p.source_path
                ),
            )
            item.state = 1 if prompt.checked else 0
            prompts.add(item)
        self.app.menu.add(prompts)

        patches = rumps.MenuItem("Patches")
        for patch in self.state.patch_items:
            item = rumps.MenuItem(
                patch.label,
                callback=lambda _sender, p=patch: self.toggle_patch(p.patch_id, p.checked),
            )
            item.state = 1 if patch.checked else 0
            patches.add(item)
        self.app.menu.add(patches)

        self.app.menu.add(None)
        self.app.menu.add(rumps.MenuItem("Rebuild / Apply…", callback=self.rebuild))
        self.app.menu.add(
            rumps.MenuItem(
                f"Install target… {self.install_target}",
                callback=self.choose_install_target,
            )
        )
        self.app.menu.add(rumps.MenuItem("Install shim…", callback=self.install_shim))
        self.app.menu.add(rumps.MenuItem("Uninstall shim…", callback=self.uninstall_shim))
        self.app.menu.add(rumps.MenuItem("Open build report", callback=self.open_build_report))
        self.app.menu.add(rumps.MenuItem("Open logs folder", callback=self.open_logs))
        self.app.menu.add(rumps.MenuItem("Open state folder", callback=self.open_state))
        self.app.menu.add(rumps.MenuItem("Refresh", callback=self.refresh))
        self.app.menu.add(rumps.MenuItem("Quit", callback=rumps.quit_application))

    def set_prompt(self, prompt_id: str | None, source_path: Path | None) -> None:
        self.runner.run_background(
            "set_prompt", command_for_prompt(prompt_id, source_path), mutating=True
        )

    def toggle_patch(self, patch_id: str, enabled: bool) -> None:
        self.runner.run_background(
            "toggle_patch", command_for_patch_toggle(patch_id, enabled=enabled), mutating=True
        )

    def rebuild(self, _sender: Any = None) -> None:
        response = self.rumps.alert(
            "Rebuild ClaudeMonkey patched binary?",
            "The official Claude binary will not be modified.",
            ok="Rebuild",
            cancel=True,
        )
        if response == 1:
            self.runner.run_background("build", ["build", "--json"], mutating=True)

    def choose_install_target(self, _sender: Any = None) -> None:
        response = self.rumps.Window(
            message=(
                "Choose claude shim target. Protected paths are allowed but may require "
                "authorization."
            ),
            title="ClaudeMonkey install target",
            default_text=str(self.install_target),
        ).run()
        if response.clicked:
            self.install_target = Path(response.text).expanduser()
            self.user_selected_install_target = True
            self.render_menu()

    def install_shim(self, _sender: Any = None) -> None:
        state_dir = self.state.state_dir if self.state else Path.home() / ".claude-monkey"
        plan = install_plan_for_target(self.install_target, state_dir=state_dir)
        dry_run = self.runner.run_json(
            command_for_install_shim_dry_run(plan.target), mutating=False
        )
        message = "This changes which claude command your shell finds."
        if dry_run.get("authorizationRequired"):
            message += (
                " This target requires authorization; ClaudeMonkey will request it only "
                "for the install transaction."
            )
        if dry_run.get("plannedActions"):
            message += "\n\nPlanned: " + "; ".join(str(item) for item in dry_run["plannedActions"])
        if self.rumps.alert("Install ClaudeMonkey shim?", message, ok="Install", cancel=True) == 1:
            self.runner.run_background(
                "install_shim", command_for_install_shim(plan.target), mutating=True
            )

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
        message = "This restores the previous claude command path when possible."
        if dry_run.get("authorizationRequired"):
            message += (
                " This target requires authorization; ClaudeMonkey will request it only "
                "for the restore transaction."
            )
        if dry_run.get("plannedActions"):
            message += "\n\nPlanned: " + "; ".join(str(item) for item in dry_run["plannedActions"])
        if (
            self.rumps.alert(
                "Uninstall ClaudeMonkey shim?", message, ok="Uninstall", cancel=True
            )
            == 1
        ):
            self.runner.run_background("uninstall_shim", real_args, mutating=True)

    def open_build_report(self, _sender: Any = None) -> None:
        if not self.state or not self.state.latest_build_report_path:
            self.rumps.alert(
                "No build report", "No active or failed build report is available yet."
            )
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
                error = payload.get("error") or {
                    "message": payload.get("summary", "Command failed")
                }
                self.rumps.alert("ClaudeMonkey command failed", str(error.get("message")))
        self.refresh()

    def run(self) -> None:
        self.app.run()


def main() -> int:
    runner = CommandRunner(logs_dir=Path.home() / ".claude-monkey" / "logs")
    ClaudeMonkeyMenuBar(runner=runner).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
