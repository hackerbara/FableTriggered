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
