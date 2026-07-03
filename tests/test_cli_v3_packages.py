from __future__ import annotations

import json
from pathlib import Path

from claude_monkey.cli import main


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def option_manifest(package_id: str, **overrides):
    payload = {
        "schemaVersion": 1,
        "kind": "option",
        "id": package_id,
        "label": package_id.replace("-", " ").title(),
        "description": "Option package",
        "risk": {"level": "low"},
        "option": {
            "argv": [],
            "env": {},
            "conflictsWithArgv": [],
            "conflictsWithOptions": [],
            "conflictsWithEnv": [],
        },
    }
    payload.update(overrides)
    return payload


def prompt_manifest(package_id: str, *, label: str | None = None):
    return {
        "schemaVersion": 1,
        "kind": "prompt",
        "id": package_id,
        "label": label or package_id.replace("-", " ").title(),
        "description": "Prompt package",
        "risk": {"level": "low"},
        "prompt": {"mode": "append", "source": {"path": "prompt.md"}},
    }


def make_executable(path: Path, text: str = "#!/bin/sh\necho claude\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(0o755)
    return path


def configure_home(monkeypatch, tmp_path: Path) -> tuple[Path, Path]:
    home = tmp_path / "home"
    state = home / ".claude-monkey"
    monkeypatch.setenv("HOME", str(home))
    official = make_executable(tmp_path / "official" / "claude")
    write_json(
        state / "config.json",
        {
            "schemaVersion": 1,
            "activeProfile": "default",
            "installMode": "shim",
            "officialClaudePath": str(official),
            "profiles": {
                "default": {
                    "prompt": "research-prompt",
                    "patches": [],
                    "options": ["local-session-defaults"],
                }
            },
        },
    )
    return state, official


def write_prompt_package(state: Path) -> Path:
    package_dir = state / "prompts" / "research-prompt"
    package_dir.mkdir(parents=True)
    prompt = package_dir / "prompt.md"
    prompt.write_text("extra system prompt")
    write_json(package_dir / "research-prompt.json", prompt_manifest("research-prompt"))
    return prompt


def write_option_package(state: Path, payload: dict | None = None) -> None:
    package_dir = state / "options" / "local-session-defaults"
    manifest = payload or option_manifest(
        "local-session-defaults",
        label="Local Session Defaults",
        option={
            "argv": ["--model", "sonnet"],
            "env": {},
            "conflictsWithArgv": [],
            "conflictsWithOptions": [],
            "conflictsWithEnv": [],
        },
    )
    write_json(package_dir / "local-session-defaults.json", manifest)


def read_cli_json(capsys) -> dict:
    captured = capsys.readouterr()
    assert captured.err == ""
    return json.loads(captured.out)


def test_launch_preview_outputs_merged_argv_and_target(monkeypatch, tmp_path, capsys):
    state, official = configure_home(monkeypatch, tmp_path)
    prompt = write_prompt_package(state)
    write_option_package(state)

    code = main(["launch-preview", "--json", "--", "--resume"])

    assert code == 0
    assert read_cli_json(capsys) == {
        "schemaVersion": 1,
        "targetClaudePath": str(official.resolve()),
        "targetClaudeKind": "official_fallback",
        "argv": ["--append-system-prompt-file", str(prompt), "--model", "sonnet", "--resume"],
        "envPreview": {},
        "skipped": [],
        "warnings": [],
        "errors": [],
    }


def test_launch_preview_redacts_secret_env(monkeypatch, tmp_path, capsys):
    state, _official = configure_home(monkeypatch, tmp_path)
    write_prompt_package(state)
    write_option_package(
        state,
        option_manifest(
            "local-session-defaults",
            label="Local Session Defaults",
            option={
                "argv": [],
                "env": {"ANTHROPIC_API_KEY": {"value": "secret", "secret": True}},
                "conflictsWithArgv": [],
                "conflictsWithOptions": [],
                "conflictsWithEnv": [],
            },
        ),
    )

    code = main(["launch-preview", "--json"])

    assert code == 0
    payload = read_cli_json(capsys)
    assert payload["envPreview"] == {"ANTHROPIC_API_KEY": "<redacted>"}
