from __future__ import annotations

import json

from tests.fixtures_bun import build_macho_fixture

from claude_monkey.cli import main


def read_json(capsys):
    return json.loads(capsys.readouterr().out)


def test_inspect_binary_json_command(tmp_path, capsys):
    binary = tmp_path / "claude"
    binary.write_bytes(build_macho_fixture()[0])
    assert main(["inspect-binary", "--source", str(binary), "--json"]) == 0
    payload = read_json(capsys)
    assert payload["ok"] is True
    assert payload["sourcePath"] == str(binary)
    assert payload["modules"][0]["path"] == "/$bunfs/root/src/entrypoints/cli.js"


def test_validate_package_json_resolves_module_operation(tmp_path, capsys):
    import hashlib

    from tests.fixtures_bun import MODULE_0, build_macho_fixture

    binary = tmp_path / "claude"
    binary.write_bytes(build_macho_fixture()[0])
    old = MODULE_0[: MODULE_0.index(b"function after(){")]
    package = tmp_path / "pkg"
    package.mkdir()
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
                    "versionOutput": "fixture",
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
                "manualSmoke": {"required": False},
            }
        ],
    }
    (package / "patch.json").write_text(json.dumps(manifest))
    assert main(
        [
            "validate-package",
            "--source",
            str(binary),
            "--package",
            str(package),
            "--source-version",
            "fixture",
            "--source-version-output",
            "fixture",
            "--json",
        ]
    ) == 0
    payload = read_json(capsys)
    assert payload["ok"] is True
    assert payload["operationsResolved"][0]["moduleStart"] == 0
    assert payload["operationsResolved"][0]["newLen"] > payload["operationsResolved"][0]["oldLen"]
