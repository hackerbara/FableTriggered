from __future__ import annotations

import hashlib
import json
import os
import platform as platform_module
import sys
from pathlib import Path

from claude_monkey.cli import main
from claude_monkey.config import load_config
from claude_monkey.install import install_shim_transaction
from claude_monkey.paths import StatePaths
from claude_monkey.status import status_payload


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def make_executable(path: Path, text: str = "#!/bin/sh\necho '2.1.199 (Claude Code)'\n") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(path.stat().st_mode | 0o111)
    return path


def prompt_manifest(package_id: str) -> dict:
    return {
        "schemaVersion": 1,
        "kind": "prompt",
        "id": package_id,
        "label": "Research",
        "description": "Research prompt",
        "risk": {"level": "low"},
        "prompt": {"mode": "append", "source": {"path": "prompt.md"}},
    }


def option_manifest(
    package_id: str,
    *,
    risk: dict | None = None,
    label: str | None = None,
) -> dict:
    return {
        "schemaVersion": 1,
        "kind": "option",
        "id": package_id,
        "label": label or package_id,
        "description": "Option",
        "risk": risk or {"level": "low"},
        "option": {
            "argv": (
                ["--dangerously-skip-permissions"] if package_id == "dangerous-permissions" else []
            ),
            "env": {},
            "conflictsWithArgv": [],
            "conflictsWithOptions": [],
            "conflictsWithEnv": [],
        },
    }


def patch_manifest(package_id: str, source: Path) -> dict:
    return {
        "schemaVersion": 1,
        "kind": "patch",
        "id": package_id,
        "label": "Fable fallback",
        "description": "Patch package",
        "risk": {"level": "low"},
        "patch": {
            "engine": "bun_graph_repack",
            "targets": [
                {
                    "sourceIdentity": {
                        "claudeVersion": "2.1.199",
                        "versionOutput": "2.1.199 (Claude Code)",
                        "sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                        "sizeBytes": source.stat().st_size,
                        "platform": sys.platform,
                        "arch": platform_module.machine() or "unknown",
                    },
                    "requiredEngine": "bun_graph_repack",
                    "requiredBinaryFormat": "bun_standalone_macho64",
                    "modules": [
                        {
                            "path": "/$bunfs/root/src/entrypoints/cli.js",
                            "contentSha256": "a" * 64,
                            "contentLength": 1,
                            "operations": [
                                {
                                    "opId": "replace-demo",
                                    "label": "Replace demo",
                                    "type": "replace_exact",
                                    "exact": "a",
                                    "replacement": {"inline": "b"},
                                }
                            ],
                        }
                    ],
                }
            ],
        },
    }


def seed_matching_state(tmp_path: Path, monkeypatch) -> tuple[Path, Path, str]:
    home = tmp_path / "home"
    state = home / ".claude-monkey"
    monkeypatch.setenv("HOME", str(home))
    source = make_executable(tmp_path / "claude")
    source_sha = hashlib.sha256(source.read_bytes()).hexdigest()
    write_json(
        state / "config.json",
        {
            "schemaVersion": 1,
            "activeProfile": "default",
            "activePatchSet": str(state / "versions" / "2.1.199" / "patchsets" / "default"),
            "officialClaudePath": str(source),
            "profiles": {
                "default": {
                    "prompt": "research",
                    "patches": ["fable-fallback"],
                    "options": ["dangerous-permissions"],
                }
            },
        },
    )
    prompt_dir = state / "prompts" / "research"
    prompt_dir.mkdir(parents=True)
    (prompt_dir / "prompt.md").write_text("research prompt")
    write_json(prompt_dir / "research.json", prompt_manifest("research"))
    write_json(
        state / "options" / "dangerous-permissions" / "dangerous-permissions.json",
        option_manifest(
            "dangerous-permissions",
            label="Dangerous permissions",
            risk={
                "level": "high",
                "statusWarning": "Dangerous permissions enabled",
                "requiresConfirmation": True,
            },
        ),
    )
    manifest = patch_manifest("fable-fallback", source)
    write_json(state / "patches" / "fable-fallback" / "fable-fallback.json", manifest)
    patchset = state / "versions" / "2.1.199" / "patchsets" / "default"
    patched = make_executable(patchset / "claude", "#!/bin/sh\necho patched\n")
    write_json(
        patchset / "build-report.json",
        {
            "schemaVersion": 3,
            "status": "verified",
            "enabledPatches": ["fable-fallback"],
            "packageManifestDigests": {
                "fable-fallback": hashlib.sha256(
                    json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()
                ).hexdigest()
            },
            "sourceClaudePath": str(source),
            "sourceVersion": "2.1.199",
            "sourceSha256": source_sha,
            "sourceIdentity": {
                "claudeVersion": "2.1.199",
                "versionOutput": "2.1.199 (Claude Code)",
                "sha256": source_sha,
                "sizeBytes": source.stat().st_size,
                "platform": "darwin",
                "arch": "arm64",
            },
            "compatibility": {"status": "compatible", "warnings": []},
        },
    )
    state.mkdir(parents=True, exist_ok=True)
    os.symlink(patched, state / "current")
    return state, source, source_sha


def test_status_payload_reports_matching_patched_v3_build(monkeypatch, tmp_path):
    state, source, source_sha = seed_matching_state(tmp_path, monkeypatch)
    paths = StatePaths(state)
    payload = status_payload(paths, load_config(paths.config_path))

    expected = {
        "schemaVersion": 1,
        "status": "ok",
        "activeProfile": "default",
        "activePrompt": "research",
        "desiredPatchIds": ["fable-fallback"],
        "builtPatchIds": ["fable-fallback"],
        "activePatchIds": ["fable-fallback"],
        "patchedBuildActive": True,
        "targetClaudeKind": "patched",
        "activeOptionIds": ["dangerous-permissions"],
        "highRiskOptions": [
            {
                "id": "dangerous-permissions",
                "label": "Dangerous permissions",
                "warning": "Dangerous permissions enabled",
            }
        ],
        "sourceClaudeVersion": "2.1.199",
        "sourceClaudePath": str(source),
        "compatibilityStatus": "compatible",
        "manifestCompatibilityStatus": "compatible",
        "sourceIdentityStatus": "compatible",
        "lastBuildCompatibilityStatus": "compatible",
        "liveValidationStatus": "unknown",
        "compatibilityWarnings": [],
        "rebuildRequired": False,
        "lastError": None,
    }
    assert {key: payload[key] for key in expected} == expected
    assert payload["sourceSha256"] == source_sha
    assert payload["latestBuildReportPath"].endswith("build-report.json")


def test_status_payload_uses_live_source_identity_when_report_source_is_stale(
    monkeypatch, tmp_path
):
    state, _source_a, _source_a_sha = seed_matching_state(tmp_path, monkeypatch)
    source_b = make_executable(
        tmp_path / "source-b" / "claude",
        "#!/bin/sh\n"
        "echo '2.1.199 (Claude Code)'\n"
        "# source-b has different bytes from the report source\n",
    )
    source_b_sha = hashlib.sha256(source_b.read_bytes()).hexdigest()
    config = json.loads((state / "config.json").read_text())
    config["officialClaudePath"] = str(source_b)
    write_json(state / "config.json", config)

    payload = status_payload(StatePaths(state), load_config(state / "config.json"))

    assert payload["sourceClaudePath"] == str(source_b)
    assert payload["sourceSha256"] == source_b_sha
    assert payload["sourceIdentityStatus"] == "source_sha_mismatch"
    assert payload["compatibilityStatus"] == "source_sha_mismatch"
    assert payload["rebuildRequired"] is True


def test_status_payload_distinguishes_version_mismatch(monkeypatch, tmp_path):
    state, _source_a, _source_a_sha = seed_matching_state(tmp_path, monkeypatch)
    source_b = make_executable(
        tmp_path / "source-b" / "claude",
        "#!/bin/sh\necho '2.1.200 (Claude Code)'\n",
    )
    config = json.loads((state / "config.json").read_text())
    config["officialClaudePath"] = str(source_b)
    write_json(state / "config.json", config)

    payload = status_payload(StatePaths(state), load_config(state / "config.json"))

    assert payload["sourceClaudeVersion"] == "2.1.200"
    assert payload["sourceIdentityStatus"] == "version_mismatch"
    assert payload["compatibilityStatus"] == "version_mismatch"
    assert payload["rebuildRequired"] is True


def test_status_source_path_drift_does_not_require_rebuild_for_same_identity(monkeypatch, tmp_path):
    state, source, source_sha = seed_matching_state(tmp_path, monkeypatch)
    source_copy = tmp_path / "different-path" / "claude"
    source_copy.parent.mkdir(parents=True)
    source_copy.write_bytes(source.read_bytes())
    source_copy.chmod(source.stat().st_mode)
    config = json.loads((state / "config.json").read_text())
    config["officialClaudePath"] = str(source_copy)
    write_json(state / "config.json", config)

    payload = status_payload(StatePaths(state), load_config(state / "config.json"))

    assert payload["sourceClaudePath"] == str(source_copy)
    assert payload["sourceSha256"] == source_sha
    assert payload["sourceIdentityStatus"] == "compatible"
    assert payload["compatibilityStatus"] == "compatible"
    assert payload["rebuildRequired"] is False


def test_status_payload_does_not_claim_report_patch_ids_for_other_current_patchset(
    monkeypatch, tmp_path
):
    state, _source, _source_sha = seed_matching_state(tmp_path, monkeypatch)
    other_patched = make_executable(
        state / "versions" / "2.1.199" / "patchsets" / "other" / "claude",
        "#!/bin/sh\necho other patched\n",
    )
    (state / "current").unlink()
    os.symlink(other_patched, state / "current")

    payload = status_payload(StatePaths(state), load_config(state / "config.json"))

    assert payload["builtPatchIds"] == ["fable-fallback"]
    assert payload["patchedBuildActive"] is False
    assert payload["activePatchIds"] == []
    assert payload["rebuildRequired"] is True


def test_status_payload_requires_rebuild_when_active_report_lacks_manifest_digests(
    monkeypatch, tmp_path
):
    state, _source, _source_sha = seed_matching_state(tmp_path, monkeypatch)
    report_path = state / "versions" / "2.1.199" / "patchsets" / "default" / "build-report.json"
    report = json.loads(report_path.read_text())
    report.pop("packageManifestDigests")
    write_json(report_path, report)

    payload = status_payload(StatePaths(state), load_config(state / "config.json"))

    assert payload["rebuildRequired"] is True
    assert (
        "enabled patch package manifest digest missing from last build"
        in payload["compatibilityWarnings"]
    )


def test_status_cli_reports_official_fallback_with_desired_patches(monkeypatch, tmp_path, capsys):
    state, _source, _sha = seed_matching_state(tmp_path, monkeypatch)
    (state / "current").unlink()

    assert main(["status", "--json"]) == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    payload = json.loads(captured.out)

    assert payload["targetClaudeKind"] == "official_fallback"
    assert payload["patchedBuildActive"] is False
    assert payload["activePatchIds"] == []
    assert payload["desiredPatchIds"] == ["fable-fallback"]
    assert payload["builtPatchIds"] == ["fable-fallback"]
    assert payload["rebuildRequired"] is True


def test_status_payload_keeps_invalid_active_prompt_and_option_visible(monkeypatch, tmp_path):
    home = tmp_path / "home"
    state = home / ".claude-monkey"
    monkeypatch.setenv("HOME", str(home))
    write_json(
        state / "config.json",
        {
            "schemaVersion": 1,
            "activeProfile": "default",
            "profiles": {
                "default": {
                    "prompt": "broken-prompt",
                    "patches": [],
                    "options": ["broken-option"],
                }
            },
        },
    )
    write_json(
        state / "prompts" / "broken-prompt" / "broken-prompt.json",
        {"schemaVersion": 1, "kind": "prompt", "id": "different"},
    )
    write_json(
        state / "options" / "broken-option" / "broken-option.json",
        {"schemaVersion": 1, "kind": "option", "id": "different"},
    )

    payload = status_payload(StatePaths(state), load_config(state / "config.json"))

    assert payload["activePrompt"] == "broken-prompt"
    assert payload["activeOptionIds"] == ["broken-option"]
    assert any(
        "prompt broken-prompt skipped: invalid" in item for item in payload["compatibilityWarnings"]
    )
    assert any(
        "option broken-option skipped: invalid" in item for item in payload["compatibilityWarnings"]
    )
    assert payload["status"] == "warning"


def test_status_payload_keeps_invalid_desired_patch_visible(monkeypatch, tmp_path):
    home = tmp_path / "home"
    state = home / ".claude-monkey"
    monkeypatch.setenv("HOME", str(home))
    write_json(
        state / "config.json",
        {
            "schemaVersion": 1,
            "activeProfile": "default",
            "profiles": {"default": {"prompt": None, "patches": ["bad-patch"], "options": []}},
        },
    )
    write_json(
        state / "patches" / "bad-patch" / "bad-patch.json",
        {"schemaVersion": 1, "kind": "patch", "id": "different"},
    )

    payload = status_payload(StatePaths(state), load_config(state / "config.json"))

    assert payload["desiredPatchIds"] == ["bad-patch"]
    assert payload["builtPatchIds"] == []
    assert payload["manifestCompatibilityStatus"] == "invalid"
    assert any(
        "patch bad-patch skipped: invalid" in item for item in payload["compatibilityWarnings"]
    )
    assert payload["rebuildRequired"] is True


# -- shim-update-resilience stage 1: replaced-managed-shim detection --------
#
# docs/superpowers/specs/2026-07-04-claude-monkey-shim-update-resilience.md
# section 1 + "Refinements (controller review, 2026-07-04)".


def seed_shim_target(tmp_path: Path) -> tuple[Path, Path]:
    """Install a real managed shim over an existing binary at an external
    target path (outside ClaudeMonkey's own managed bin/versions roots, like
    the spec's `/Users/MAC/.local/bin/claude`). Returns (state_dir, target).
    """
    state = tmp_path / ".claude-monkey"
    target = tmp_path / "local-bin" / "claude"
    make_executable(target, "#!/bin/sh\necho '2.1.199 (Claude Code)'\n")
    install_shim_transaction(target, state, dry_run=False)
    return state, target


def replace_target_with_official(target: Path, tmp_path: Path, version: str = "2.1.201") -> Path:
    """Simulate an official Claude updater clobbering the shim in place with
    a symlink to a newly installed official binary (the spec's observed
    failure mode: target path unchanged, target identity replaced).
    """
    official = make_executable(
        tmp_path / "official-source" / "claude",
        f"#!/bin/sh\necho '{version} (Claude Code)'\n",
    )
    target.unlink()
    target.symlink_to(official)
    return official


def test_status_detects_target_replaced_by_official(tmp_path):
    state, target = seed_shim_target(tmp_path)
    official = replace_target_with_official(target, tmp_path)
    official_sha = hashlib.sha256(official.read_bytes()).hexdigest()

    payload = status_payload(StatePaths(state), load_config(state / "config.json"))

    assert payload["shimInstalled"] is False
    assert payload["shimPreviouslyManaged"] is True
    assert payload["targetReplacedByOfficial"] is True
    assert payload["detectedOfficialSha256"] == official_sha
    assert payload["detectedOfficialVersion"] == "2.1.201"
    assert payload["shimRepairAvailable"] is True
    assert payload["rolloutRequired"] is True


def test_status_never_managed_target_reports_all_new_fields_empty(tmp_path):
    state = tmp_path / ".claude-monkey"
    state.mkdir(parents=True)

    payload = status_payload(StatePaths(state), load_config(state / "config.json"))

    assert payload["shimPreviouslyManaged"] is False
    assert payload["targetReplacedByOfficial"] is False
    assert payload["detectedOfficialSha256"] is None
    assert payload["detectedOfficialVersion"] is None
    assert payload["shimRepairAvailable"] is False
    assert payload["rolloutRequired"] is False


def test_status_intact_shim_reports_no_replacement(tmp_path):
    state, _target = seed_shim_target(tmp_path)

    payload = status_payload(StatePaths(state), load_config(state / "config.json"))

    assert payload["shimInstalled"] is True
    assert payload["shimPreviouslyManaged"] is True
    assert payload["targetReplacedByOfficial"] is False
    assert payload["detectedOfficialSha256"] is None
    assert payload["detectedOfficialVersion"] is None
    assert payload["shimRepairAvailable"] is False
    assert payload["rolloutRequired"] is False


def test_status_corrupt_cache_disables_repair_but_keeps_detecting_replacement(tmp_path):
    state, target = seed_shim_target(tmp_path)
    replace_target_with_official(target, tmp_path)

    record_path = state / "install-record.json"
    record = json.loads(record_path.read_text())
    cache_path = Path(record["previousSourceCachePath"])
    cache_path.write_bytes(b"corrupted-cache-bytes")

    payload = status_payload(StatePaths(state), load_config(state / "config.json"))

    assert payload["shimPreviouslyManaged"] is True
    assert payload["targetReplacedByOfficial"] is True
    assert payload["shimRepairAvailable"] is False
