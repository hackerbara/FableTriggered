from __future__ import annotations

import json
from pathlib import Path

import pytest

from claude_monkey.builder_v15 import ValidationRequestV15, validate_package
from claude_monkey.manifest_v2 import load_manifest_v2_dict
from claude_monkey.payloads import load_payload_bytes

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path("/Users/MAC/.local/bin/claude")
PACKAGE_DIRS = [
    ROOT / "packages" / "fable-fallback",
    ROOT / "packages" / "reminder-suppression",
]


def test_reference_packages_are_v15_schema_v2_with_valid_payload_hashes():
    for package_dir in PACKAGE_DIRS:
        manifest_data = json.loads((package_dir / "patch.json").read_text())
        manifest = load_manifest_v2_dict(manifest_data)
        assert manifest.id == package_dir.name
        assert manifest.schema_version == 2
        target = manifest.targets[0]
        assert target.required_engine == "bun_graph_repack"
        assert target.required_binary_format == "bun_standalone_macho64"
        assert [module.path for module in target.modules] == [
            "/$bunfs/root/src/entrypoints/cli.js"
        ]
        for module in target.modules:
            assert module.content_sha256
            assert module.content_length > 0
            for operation in module.operations:
                assert operation.old_range_sha256
                assert operation.old_range_length is not None
                payload = load_payload_bytes(operation.replacement, package_dir)
                assert payload


def test_reference_packages_validate_against_current_pinned_source():
    if not SOURCE.exists():
        pytest.skip(f"local Claude Code source missing: {SOURCE}")
    for package_dir in PACKAGE_DIRS:
        manifest = load_manifest_v2_dict(json.loads((package_dir / "patch.json").read_text()))
        identity = manifest.targets[0].source_identity
        result = validate_package(
            ValidationRequestV15(
                source_path=SOURCE,
                package_dir=package_dir,
                source_version=identity.claude_version,
                source_version_output=identity.version_output,
                platform=identity.platform,
                arch=identity.arch,
            )
        )
        assert result["ok"] is True, result
        assert result["packageId"] == package_dir.name
        assert result["operationsResolved"]


def test_fable_resume_metadata_payload_uses_ascii_escapes_for_terminal_rendering():
    payload_path = (
        ROOT / "packages" / "fable-fallback" / "payloads" / "net-metadata-formatter.js"
    )
    payload = payload_path.read_bytes()
    assert b"\xc2\xb7" not in payload
    assert b"\\xB7" in payload
    assert b"\\x1b[33mFable classifier triggered\\x1b[39m" in payload
