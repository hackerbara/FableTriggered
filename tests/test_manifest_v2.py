from __future__ import annotations

import pytest

from claude_monkey.manifest_v2 import ManifestV2Error, load_manifest_v2_dict


def valid_v2_manifest() -> dict:
    return {
        "schemaVersion": 2,
        "id": "example-v15",
        "name": "Example V1.5 patch",
        "description": "Module-coordinate example",
        "packageVersion": "0.1.0",
        "targets": [
            {
                "sourceIdentity": {
                    "claudeVersion": "2.1.198",
                    "versionOutput": "2.1.198 (Claude Code)",
                    "sha256": "a" * 64,
                    "sizeBytes": 229328464,
                    "platform": "darwin",
                    "arch": "arm64",
                },
                "requiredEngine": "bun_graph_repack",
                "requiredBinaryFormat": "bun_standalone_macho64",
                "modules": [
                    {
                        "path": "/$bunfs/root/src/entrypoints/cli.js",
                        "contentSha256": "b" * 64,
                        "contentLength": 64,
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
                                "oldRangeSha256": "c" * 64,
                                "oldRangeLength": 28,
                                "replacement": {"inline": "function render(){NEW_RENDER}\n"},
                                "knownBehaviorChange": "Changes renderer output",
                            }
                        ],
                    }
                ],
                "preconditions": [],
                "postconditions": [
                    {
                        "type": "module_must_contain",
                        "modulePath": "/$bunfs/root/src/entrypoints/cli.js",
                        "value": "NEW_RENDER",
                    }
                ],
                "manualSmoke": {"required": True, "reason": "UI renderer changed"},
            }
        ],
    }


def test_load_manifest_v2_accepts_valid_shape():
    manifest = load_manifest_v2_dict(valid_v2_manifest())
    assert manifest.schema_version == 2
    assert manifest.id == "example-v15"
    target = manifest.targets[0]
    assert target.required_engine == "bun_graph_repack"
    assert target.required_binary_format == "bun_standalone_macho64"
    assert target.modules[0].path == "/$bunfs/root/src/entrypoints/cli.js"
    assert target.modules[0].operations[0].op_id == "replace-renderer"


def test_schema_v1_is_rejected_with_migration_required():
    data = valid_v2_manifest()
    data["schemaVersion"] = 1
    with pytest.raises(ManifestV2Error, match="schema_v1_migration_required"):
        load_manifest_v2_dict(data)


@pytest.mark.parametrize("field", ["requiredEngine", "requiredBinaryFormat", "modules"])
def test_target_requires_engine_and_modules(field):
    data = valid_v2_manifest()
    del data["targets"][0][field]
    with pytest.raises(ManifestV2Error, match=field):
        load_manifest_v2_dict(data)


def test_manifest_v2_rejects_binary_shape_leak():
    data = valid_v2_manifest()
    data["targets"][0]["binaryShape"] = {"moduleRecordSize": 52}
    with pytest.raises(ManifestV2Error, match="binaryShape"):
        load_manifest_v2_dict(data)


def test_manifest_v2_rejects_padding_and_growth_flags():
    data = valid_v2_manifest()
    op = data["targets"][0]["modules"][0]["operations"][0]
    op["padding"] = "spaces"
    with pytest.raises(ManifestV2Error, match="padding"):
        load_manifest_v2_dict(data)
    del op["padding"]
    op["allowGrowth"] = True
    with pytest.raises(ManifestV2Error, match="allowGrowth"):
        load_manifest_v2_dict(data)


def test_manifest_v2_rejects_duplicate_op_ids_across_modules():
    data = valid_v2_manifest()
    module = dict(data["targets"][0]["modules"][0])
    module["path"] = "/$bunfs/root/src/other.js"
    module["operations"] = [dict(module["operations"][0])]
    data["targets"][0]["modules"].append(module)
    with pytest.raises(ManifestV2Error, match="duplicate opId"):
        load_manifest_v2_dict(data)


@pytest.mark.parametrize("bad", ["run_shell", "module_must_contain"])
def test_manifest_v2_rejects_non_mutating_operation_types(bad):
    data = valid_v2_manifest()
    data["targets"][0]["modules"][0]["operations"][0]["type"] = bad
    with pytest.raises(ManifestV2Error, match="unsupported operation type"):
        load_manifest_v2_dict(data)
