from __future__ import annotations

import json
from pathlib import Path

import pytest

from claude_monkey.builder_v15 import ValidationRequestV15, validate_package
from claude_monkey.manifest_v2 import load_manifest_v2_dict
from claude_monkey.payloads import load_payload_bytes

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(
    "/Users/MAC/Documents/Claude-patch/.development/artifacts/claude-2.1.198.unpatched-copy"
)
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


def test_reference_packages_validate_against_real_2_1_198_source():
    if not SOURCE.exists():
        pytest.skip(f"local Claude Code 2.1.198 source artifact missing: {SOURCE}")
    for package_dir in PACKAGE_DIRS:
        result = validate_package(
            ValidationRequestV15(
                source_path=SOURCE,
                package_dir=package_dir,
                source_version="2.1.198",
                source_version_output="2.1.198 (Claude Code)",
                platform="darwin",
                arch="arm64",
            )
        )
        assert result["ok"] is True, result
        assert result["packageId"] == package_dir.name
        assert result["operationsResolved"]
