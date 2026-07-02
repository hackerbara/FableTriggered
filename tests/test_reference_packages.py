from __future__ import annotations

import json
from pathlib import Path

from claude_monkey.manifest import load_manifest_dict
from claude_monkey.payloads import load_payload_bytes

ROOT = Path(__file__).resolve().parents[1]


def test_reference_packages_load_and_payload_hashes_match():
    package_dirs = [
        ROOT / "packages" / "fable-fallback",
        ROOT / "packages" / "reminder-suppression",
    ]
    for package_dir in package_dirs:
        manifest = load_manifest_dict(json.loads((package_dir / "patch.json").read_text()))
        assert manifest.id == package_dir.name
        for target in manifest.targets:
            assert target.operations
            for operation in target.operations:
                payload = load_payload_bytes(operation.replacement, package_dir)
                assert payload
