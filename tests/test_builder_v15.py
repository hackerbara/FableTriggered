from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tests.fixtures_bun import MODULE_0, build_aligned_macho_fixture

from claude_monkey.builder_v15 import BuildRequestV15, build_patchset_v15
from claude_monkey.smoke import CommandResult


def write_fixture_package(package: Path, binary: Path, *, manual_smoke: bool = False) -> None:
    old = MODULE_0[: MODULE_0.index(b"function after(){")]
    manifest = {
        "schemaVersion": 2,
        "id": "fixture-v15",
        "name": "Fixture V1.5",
        "description": "Fixture package",
        "packageVersion": "0.1.0",
        "targets": [
            {
                "sourceIdentity": {
                    "claudeVersion": "fixture",
                    "versionOutput": "fixture (Claude Code)",
                    "sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                    "sizeBytes": binary.stat().st_size,
                    "platform": "darwin",
                    "arch": "arm64",
                },
                "requiredEngine": "bun_graph_repack",
                "requiredBinaryFormat": "bun_standalone_macho64",
                "modules": [
                    {
                        "path": "/$bunfs/root/src/entrypoints/cli.js",
                        "contentSha256": hashlib.sha256(MODULE_0).hexdigest(),
                        "contentLength": len(MODULE_0),
                        "operations": [
                            {
                                "opId": "replace-renderer",
                                "label": "Replace renderer",
                                "type": "replace_between",
                                "startMarker": "function render(){",
                                "endMarker": "function after(){",
                                "expectedStartMarkerCount": 1,
                                "expectedEndMarkerCount": 1,
                                "requireWithinRange": ["OLD_RENDER"],
                                "oldRangeSha256": hashlib.sha256(old).hexdigest(),
                                "oldRangeLength": len(old),
                                "replacement": {"inline": "function render(){NEW_RENDER_LONGER}\n"},
                            }
                        ],
                    }
                ],
                "postconditions": [
                    {
                        "type": "module_must_contain",
                        "modulePath": "/$bunfs/root/src/entrypoints/cli.js",
                        "value": "NEW_RENDER_LONGER",
                    }
                ],
                "manualSmoke": {"required": manual_smoke, "reason": "UI" if manual_smoke else None},
            }
        ],
    }
    package.mkdir()
    (package / "patch.json").write_text(json.dumps(manifest))


def successful_runner(argv):
    if argv[0] == "codesign" and "--verify" in argv:
        return CommandResult(argv=argv, returncode=0, stdout="", stderr="valid")
    if argv[0] == "codesign":
        return CommandResult(argv=argv, returncode=0, stdout="", stderr="signed")
    if argv[-1] == "--version":
        return CommandResult(argv=argv, returncode=0, stdout="fixture (Claude Code)\n", stderr="")
    if argv[-1] == "--help":
        return CommandResult(
            argv=argv, returncode=0, stdout="Usage: claude [options]\nClaude Code help\n", stderr=""
        )
    return CommandResult(argv=argv, returncode=1, stdout="", stderr="unexpected")


def test_build_patchset_v15_writes_copied_output_and_report(tmp_path):
    source = tmp_path / "claude-source"
    source.write_bytes(build_aligned_macho_fixture()[0])
    package = tmp_path / "pkg"
    write_fixture_package(package, source)
    report = build_patchset_v15(
        BuildRequestV15(
            source_path=source,
            output_dir=tmp_path / "out",
            package_dirs=[package],
            source_version="fixture",
            source_version_output="fixture (Claude Code)",
            platform="darwin",
            arch="arm64",
            command_runner=successful_runner,
        )
    )
    assert report.automatedStatus == "passed"
    assert report.activationEligible is True
    assert report.outputPath is not None
    assert Path(report.outputPath).exists()
    assert source.read_bytes() == build_aligned_macho_fixture()[0]


def test_build_patchset_v15_blocks_activation_for_manual_smoke(tmp_path):
    source = tmp_path / "claude-source"
    source.write_bytes(build_aligned_macho_fixture()[0])
    package = tmp_path / "pkg"
    write_fixture_package(package, source, manual_smoke=True)
    report = build_patchset_v15(
        BuildRequestV15(
            source_path=source,
            output_dir=tmp_path / "out",
            package_dirs=[package],
            source_version="fixture",
            source_version_output="fixture (Claude Code)",
            platform="darwin",
            arch="arm64",
            command_runner=successful_runner,
        )
    )
    assert report.status == "manual_smoke_pending"
    assert report.activationEligible is False
    assert "manual_smoke_pending" in report.activationBlockers


def test_schema_v1_package_is_migration_required(tmp_path):
    source = tmp_path / "claude-source"
    source.write_bytes(build_aligned_macho_fixture()[0])
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "patch.json").write_text(json.dumps({"schemaVersion": 1}))
    report = build_patchset_v15(
        BuildRequestV15(
            source_path=source,
            output_dir=tmp_path / "out",
            package_dirs=[package],
            source_version="fixture",
            source_version_output="fixture (Claude Code)",
            platform="darwin",
            arch="arm64",
            command_runner=successful_runner,
        )
    )
    assert report.status == "failed"
    assert report.failureReason == "schema_v1_migration_required"
