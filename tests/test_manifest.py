from __future__ import annotations

import json

import pytest

from claude_monkey.manifest import ManifestError, load_manifest_dict


def valid_manifest() -> dict:
    return {
        "schemaVersion": 1,
        "id": "example-patch",
        "name": "Example Patch",
        "description": "Example declarative patch",
        "packageVersion": "0.1.0",
        "targets": [
            {
                "sourceIdentity": {
                    "claudeVersion": "2.1.198",
                    "versionOutput": "2.1.198 (Claude Code)",
                    "sha256": "a" * 64,
                    "sizeBytes": 100,
                    "platform": "darwin",
                    "arch": "arm64",
                },
                "operations": [
                    {
                        "opId": "replace-a",
                        "label": "Replace A",
                        "type": "replace_between",
                        "startMarker": "case\"a\":{",
                        "endMarker": "case\"b\":{",
                        "expectedStartMarkerCount": 1,
                        "expectedEndMarkerCount": 1,
                        "requireWithinRange": ["OLD_A_BODY"],
                        "replacement": {"inline": "case\"a\":{NEW_A_BODY} "},
                        "padding": "spaces",
                    }
                ],
                "postconditions": [
                    {"type": "must_contain", "scope": "whole_binary", "value": "NEW_A_BODY"}
                ],
            }
        ],
    }


def test_load_manifest_accepts_valid_shape():
    manifest = load_manifest_dict(valid_manifest())
    assert manifest.id == "example-patch"
    assert manifest.targets[0].source_identity.claude_version == "2.1.198"
    assert manifest.targets[0].operations[0].op_id == "replace-a"


@pytest.mark.parametrize(
    "field", ["schemaVersion", "id", "name", "description", "packageVersion", "targets"]
)
def test_manifest_requires_top_level_fields(field):
    data = valid_manifest()
    del data[field]
    with pytest.raises(ManifestError, match=field):
        load_manifest_dict(data)


def test_manifest_rejects_duplicate_operation_ids():
    data = valid_manifest()
    data["targets"][0]["operations"].append(dict(data["targets"][0]["operations"][0]))
    with pytest.raises(ManifestError, match="duplicate opId"):
        load_manifest_dict(data)


def test_manifest_rejects_unknown_operation_type():
    data = valid_manifest()
    data["targets"][0]["operations"][0]["type"] = "run_shell"
    with pytest.raises(ManifestError, match="unsupported operation type"):
        load_manifest_dict(data)


def test_manifest_can_be_json_serialized_for_digest_stability():
    data = valid_manifest()
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":"))
    assert "example-patch" in encoded
