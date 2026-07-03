from __future__ import annotations

import struct
import zlib
from pathlib import Path
from types import SimpleNamespace

from claude_monkey.menubar import (
    REBUILD_CONFIRMATION_BODY,
    ClaudeMonkeyMenuBar,
    alert_for_result,
    build_menu_labels,
    command_for_install_shim,
    command_for_install_shim_dry_run,
    command_for_patch_toggle,
    command_for_prompt,
    command_for_uninstall_shim,
    command_for_uninstall_shim_dry_run,
    default_install_target,
    install_target_menu_label,
)
from claude_monkey.menubar_state import MenuState, PatchMenuItem, PromptMenuItem

ROOT = Path(__file__).resolve().parents[1]


def test_menubar_icon_asset_exists():
    icon = ROOT / "assets" / "claude-monkey-menubar-template.png"
    assert icon.exists()
    assert icon.stat().st_size > 0


def _png_rgba_rows(path: Path) -> list[bytes]:
    data = path.read_bytes()
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    offset = 8
    width = height = color_type = None
    compressed = b""
    while offset < len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        chunk = data[offset + 8 : offset + 8 + length]
        offset += length + 12
        if chunk_type == b"IHDR":
            width, height, bit_depth, color_type, _compression, _filter, _interlace = struct.unpack(
                ">IIBBBBB", chunk
            )
            assert bit_depth == 8
            assert color_type == 6
        elif chunk_type == b"IDAT":
            compressed += chunk
        elif chunk_type == b"IEND":
            break
    assert width is not None and height is not None and color_type == 6
    raw = zlib.decompress(compressed)
    stride = width * 4
    rows: list[bytes] = []
    prior = bytearray(stride)
    position = 0
    for _row_index in range(height):
        filter_type = raw[position]
        position += 1
        row = bytearray(raw[position : position + stride])
        position += stride
        if filter_type == 1:
            for index in range(stride):
                left = row[index - 4] if index >= 4 else 0
                row[index] = (row[index] + left) & 0xFF
        elif filter_type == 2:
            for index in range(stride):
                row[index] = (row[index] + prior[index]) & 0xFF
        else:
            assert filter_type == 0
        rows.append(bytes(row))
        prior = row
    return rows


def test_menubar_icon_asset_has_visible_template_pixels():
    icon = ROOT / "assets" / "claude-monkey-menubar-template.png"
    rows = _png_rgba_rows(icon)
    alphas = [row[index + 3] for row in rows for index in range(0, len(row), 4)]
    assert any(alpha > 0 for alpha in alphas)


def sample_state(tmp_path):
    return MenuState(
        status="rebuild_required",
        status_label="Rebuild Required",
        source_claude_version="2.1.198",
        source_claude_path=None,
        install_mode="shim",
        shim_installed=False,
        active_profile="default",
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
        patch_items=(
            PatchMenuItem("fable-fallback", "Fable", True, False, True, "compatible"),
        ),
        prompt_items=(
            PromptMenuItem("research", "Research", True, "append", tmp_path / "research.md"),
        ),
    )


def test_build_menu_labels_contains_required_actions(tmp_path):
    labels = build_menu_labels(sample_state(tmp_path))
    assert "ClaudeMonkey: Rebuild Required" in labels
    assert "Open logs folder" in labels
    assert "Open state folder" in labels
    assert "Quit" in labels


def test_install_target_label_identifies_writable_and_protected(tmp_path):
    writable = tmp_path / ".claude-monkey" / "bin" / "claude"
    assert "user-writable" in install_target_menu_label(writable, state_dir=tmp_path)
    assert "protected" in install_target_menu_label(
        Path("/usr/local/bin/claude"), state_dir=tmp_path
    )


def test_rebuild_confirmation_copy_matches_spec_minimum():
    assert "copied Claude Code binary" in REBUILD_CONFIRMATION_BODY
    assert "verify it" in REBUILD_CONFIRMATION_BODY
    assert "sign it" in REBUILD_CONFIRMATION_BODY
    assert "smoke-test it" in REBUILD_CONFIRMATION_BODY
    assert "activate it only if the build succeeds" in REBUILD_CONFIRMATION_BODY
    assert "official Claude binary will not be modified" in REBUILD_CONFIRMATION_BODY


def test_result_alerts_cover_prompt_and_build_summaries(tmp_path):
    state = sample_state(tmp_path)
    prompt_alert = alert_for_result("set_prompt", {"ok": True, "summary": "prompt set"}, state)
    assert prompt_alert is not None
    assert prompt_alert.message == "Prompt will apply on next Claude launch."

    build_alert = alert_for_result(
        "build",
        {"ok": True, "summary": "Build activated", "reportPath": str(tmp_path / "report.json")},
        state,
    )
    assert build_alert is not None
    assert "Build activated" in build_alert.message
    assert "Active patch set:" in build_alert.message
    assert "Report:" in build_alert.message

    failure_alert = alert_for_result(
        "build",
        {
            "ok": False,
            "summary": "boom",
            "reportPath": str(tmp_path / "report.json"),
            "error": {"message": "boom", "code": "command_failed"},
        },
        state,
    )
    assert failure_alert is not None
    assert "Open report" in failure_alert.message
    assert "Open logs" in failure_alert.message


def test_command_mapping_uses_json():
    assert command_for_patch_toggle("fable-fallback", enabled=True) == [
        "disable",
        "fable-fallback",
        "--json",
    ]
    assert command_for_patch_toggle("fable-fallback", enabled=False) == [
        "enable",
        "fable-fallback",
        "--json",
    ]
    target = default_install_target()
    prompt_path = target.parent / "research.md"
    assert command_for_prompt("research", prompt_path) == [
        "set-prompt",
        str(prompt_path),
        "--id",
        "research",
        "--from-file",
        "--json",
    ]
    assert command_for_prompt(None) == ["clear-prompt", "--json"]
    assert command_for_install_shim_dry_run(target) == [
        "install-shim",
        "--target",
        str(target),
        "--json",
        "--dry-run",
    ]
    assert command_for_install_shim(target) == [
        "install-shim",
        "--target",
        str(target),
        "--json",
    ]
    assert command_for_uninstall_shim_dry_run(target=target) == [
        "uninstall-shim",
        "--target",
        str(target),
        "--json",
        "--dry-run",
    ]
    assert command_for_uninstall_shim(target=target) == [
        "uninstall-shim",
        "--target",
        str(target),
        "--json",
    ]
    record = target.parent / "record.json"
    assert command_for_uninstall_shim(record=record) == [
        "uninstall-shim",
        "--record",
        str(record),
        "--json",
    ]


class FakeMenu:
    def __init__(self) -> None:
        self.items = []

    def clear(self):
        self.items.clear()

    def add(self, item):
        self.items.append(item)


class FakeMenuItem:
    def __init__(self, title, callback=None):
        self.title = title
        self.callback = callback
        self.state = 0
        self.children = []
        self.enabled = True

    def add(self, item):
        self.children.append(item)


class FakeRumps:
    MenuItem = FakeMenuItem

    def __init__(self) -> None:
        self.alerts = []
        self.next_response = 1

    def alert(self, title, message="", **kwargs):
        self.alerts.append((title, message, kwargs))
        return self.next_response

    @staticmethod
    def quit_application():
        return None


class FakeRunner:
    def __init__(self, dry_run_payload=None, load_error: Exception | None = None) -> None:
        self.dry_run_payload = dry_run_payload or {"ok": True, "plannedActions": []}
        self.load_error = load_error
        self.background_calls = []
        self.opened = []

    def run_json(self, args, *, mutating):
        if self.load_error is not None:
            raise self.load_error
        if "--dry-run" in args:
            return self.dry_run_payload
        raise AssertionError(f"unexpected run_json call: {args}")

    def run_background(self, name, args, *, mutating):
        self.background_calls.append((name, args, mutating))

    def open_path(self, path):
        self.opened.append(path)

    def drain_results(self):
        return []


def make_bar(tmp_path, runner):
    rumps = FakeRumps()
    bar = ClaudeMonkeyMenuBar.__new__(ClaudeMonkeyMenuBar)
    bar.rumps = rumps
    bar.runner = runner
    bar.state = sample_state(tmp_path)
    bar.install_target = tmp_path / ".claude-monkey" / "bin" / "claude"
    bar.install_record = None
    bar.user_selected_install_target = False
    bar.busy_command = None
    bar.last_error_message = None
    bar.app = SimpleNamespace(menu=FakeMenu())
    return bar, rumps


def flat_items(items):
    flattened = []
    for item in items:
        if item is None:
            continue
        flattened.append(item)
        flattened.extend(flat_items(getattr(item, "children", [])))
    return flattened


def test_install_dry_run_failure_stops_before_real_command(tmp_path):
    runner = FakeRunner(
        dry_run_payload={
            "ok": False,
            "summary": "preflight failed",
            "error": {"message": "preflight failed", "code": "bad_target"},
        }
    )
    bar, rumps = make_bar(tmp_path, runner)

    bar.install_shim()

    assert not runner.background_calls
    assert rumps.alerts[-1][0] == "ClaudeMonkey install preflight failed"


def test_refresh_failure_renders_minimal_recovery_menu(tmp_path):
    runner = FakeRunner(load_error=RuntimeError("status boom"))
    bar, rumps = make_bar(tmp_path, runner)
    bar.state = None

    bar.refresh()

    labels = [item.title for item in flat_items(bar.app.menu.items)]
    assert "ClaudeMonkey: Error" in labels
    assert "Refresh" in labels
    assert "Open logs folder" in labels
    assert "Quit" in labels
    assert "status boom" in rumps.alerts[-1][1]


def test_open_logs_uses_default_logs_dir_without_state(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    bar, _rumps = make_bar(tmp_path, FakeRunner())
    bar.state = None

    bar.open_logs()

    expected = tmp_path / ".claude-monkey" / "logs"
    assert expected.exists()
    assert bar.runner.opened == [expected]


def test_busy_render_disables_mutating_items_and_shows_running_status(tmp_path):
    bar, _rumps = make_bar(tmp_path, FakeRunner())
    bar.busy_command = "build"

    bar.render_menu()

    items = flat_items(bar.app.menu.items)
    labels = [item.title for item in items]
    assert "Running: build" in labels
    for title in ("Rebuild / Apply…", "Install shim…", "Uninstall shim…", "Fable"):
        item = next(item for item in items if item.title == title)
        assert item.enabled is False


def test_open_state_creates_directory_before_opening(tmp_path):
    bar, _rumps = make_bar(tmp_path, FakeRunner())
    missing_state = tmp_path / "missing-state"
    bar.state = sample_state(missing_state)

    bar.open_state()

    assert missing_state.exists()
    assert bar.runner.opened == [missing_state]
