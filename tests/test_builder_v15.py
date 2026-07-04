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


def test_source_identity_mismatch_report_names_current_and_target(tmp_path):
    source = tmp_path / "claude-source"
    source.write_bytes(build_aligned_macho_fixture()[0])
    package = tmp_path / "pkg"
    write_fixture_package(package, source)

    report = build_patchset_v15(
        BuildRequestV15(
            source_path=source,
            output_dir=tmp_path / "out",
            package_dirs=[package],
            source_version="2.1.199",
            source_version_output="2.1.199 (Claude Code)",
            platform="darwin",
            arch="arm64",
            command_runner=successful_runner,
        )
    )

    assert report.status == "failed"
    assert report.failureReason is not None
    assert "source_identity_mismatch:fixture-v15" in report.failureReason
    assert "current source is Claude 2.1.199" in report.failureReason
    assert "package targets Claude fixture" in report.failureReason



def write_insertion_package(
    package: Path,
    binary: Path,
    *,
    package_id: str,
    payload: str,
    insert_order: int,
    postcondition_value: str,
) -> None:
    manifest = {
        "schemaVersion": 2,
        "id": package_id,
        "name": package_id,
        "description": "Insertion fixture",
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
                                "opId": f"{package_id}-insert",
                                "label": "Insert entry",
                                "type": "insert_after",
                                "anchor": "OLD_RENDER",
                                "insertOrder": insert_order,
                                "seamHint": "fixture.afterOldRender",
                                "replacement": {"inline": payload},
                            }
                        ],
                    }
                ],
                "postconditions": [
                    {
                        "type": "module_must_contain",
                        "modulePath": "/$bunfs/root/src/entrypoints/cli.js",
                        "value": postcondition_value,
                    }
                ],
            }
        ],
    }
    package.mkdir()
    (package / "patch.json").write_text(json.dumps(manifest))


def _build(tmp_path, source, package_dirs):
    return build_patchset_v15(
        BuildRequestV15(
            source_path=source,
            output_dir=tmp_path / "out",
            package_dirs=package_dirs,
            source_version="fixture",
            source_version_output="fixture (Claude Code)",
            platform="darwin",
            arch="arm64",
            command_runner=successful_runner,
        )
    )


def test_insertion_build_reports_evidence_and_extended_fields(tmp_path):
    source = tmp_path / "claude-source"
    source.write_bytes(build_aligned_macho_fixture()[0])
    pkg = tmp_path / "pkg-a"
    write_insertion_package(
        pkg, source, package_id="pkg-a", payload=",A_ENTRY",
        insert_order=100, postcondition_value="A_ENTRY",
    )
    report = _build(tmp_path, source, [pkg])
    assert report.automatedStatus == "passed"
    applied = report.operationsApplied[0]
    assert applied["type"] == "insert_after"
    assert applied["kind"] == "insertion"
    assert applied["insertOrder"] == 100
    assert applied["anchor"] == "OLD_RENDER"
    assert applied["seamHint"] == "fixture.afterOldRender"
    assert applied["insertionVerified"] is True
    assert applied["oldLen"] == 0
    assert applied["moduleStart"] == applied["moduleEnd"]
    assert isinstance(applied["finalOffset"], int)


def test_composition_sensitive_postcondition_fails_build(tmp_path):
    source = tmp_path / "claude-source"
    source.write_bytes(build_aligned_macho_fixture()[0])
    pkg_a = tmp_path / "pkg-a"
    pkg_b = tmp_path / "pkg-b"
    write_insertion_package(
        pkg_a, source, package_id="pkg-a", payload=",A_ENTRY",
        insert_order=100,
        postcondition_value="OLD_RENDER,A_ENTRY",  # asserts adjacency across a SHARED point
    )
    write_insertion_package(
        pkg_b, source, package_id="pkg-b", payload=",B_ENTRY",
        insert_order=200, postcondition_value="B_ENTRY",
    )
    report = _build(tmp_path, source, [pkg_a, pkg_b])
    assert report.status == "failed"
    assert report.failureReason.startswith("postcondition_composition_sensitive:pkg-a")



def _add_relationships(package: Path, *, requires=None, conflicts=None) -> None:
    manifest = json.loads((package / "patch.json").read_text())
    if requires is not None:
        manifest["requiresPackages"] = requires
    if conflicts is not None:
        manifest["conflictsWithPackages"] = conflicts
    (package / "patch.json").write_text(json.dumps(manifest))


def test_required_package_missing_fails_before_planning(tmp_path):
    source = tmp_path / "claude-source"
    source.write_bytes(build_aligned_macho_fixture()[0])
    pkg = tmp_path / "pkg-a"
    write_insertion_package(
        pkg, source, package_id="pkg-a", payload=",A_ENTRY",
        insert_order=100, postcondition_value="A_ENTRY",
    )
    _add_relationships(pkg, requires=["footer-drawers"])
    report = _build(tmp_path, source, [pkg])
    assert report.status == "failed"
    assert report.failureReason == "patch_conflict:required_package_missing:pkg-a:footer-drawers"


def test_package_conflict_fails_before_planning(tmp_path):
    source = tmp_path / "claude-source"
    source.write_bytes(build_aligned_macho_fixture()[0])
    pkg_a = tmp_path / "pkg-a"
    pkg_b = tmp_path / "pkg-b"
    write_insertion_package(
        pkg_a, source, package_id="pkg-a", payload=",A_ENTRY",
        insert_order=100, postcondition_value="A_ENTRY",
    )
    write_insertion_package(
        pkg_b, source, package_id="pkg-b", payload=",B_ENTRY",
        insert_order=200, postcondition_value="B_ENTRY",
    )
    _add_relationships(pkg_a, conflicts=["pkg-b"])
    report = _build(tmp_path, source, [pkg_a, pkg_b])
    assert report.status == "failed"
    assert report.failureReason == "patch_conflict:package_conflict:pkg-a:pkg-b"


def test_requirements_satisfied_build_passes(tmp_path):
    source = tmp_path / "claude-source"
    source.write_bytes(build_aligned_macho_fixture()[0])
    pkg_a = tmp_path / "pkg-a"
    pkg_b = tmp_path / "pkg-b"
    write_insertion_package(
        pkg_a, source, package_id="pkg-a", payload=",A_ENTRY",
        insert_order=100, postcondition_value="A_ENTRY",
    )
    write_insertion_package(
        pkg_b, source, package_id="pkg-b", payload=",B_ENTRY",
        insert_order=200, postcondition_value="B_ENTRY",
    )
    _add_relationships(pkg_a, requires=["pkg-b"])
    report = _build(tmp_path, source, [pkg_a, pkg_b])
    assert report.automatedStatus == "passed"
