from __future__ import annotations

import hashlib
import json
from pathlib import Path

from claude_monkey.builder import BuildRequest, build_patchset
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


def test_fable_package_builds_when_later_user_cases_repeat(tmp_path):
    package_dir = ROOT / "packages" / "fable-fallback"
    manifest_data = json.loads((package_dir / "patch.json").read_text())
    chunks = []
    real_net_range = (
        'function net(e){let t=e.fileSize!==void 0?$a(e.fileSize):`${e.messageCount} messages`,'
        'n=[Bz(e.modified,{style:"short"}),...e.sessionKind==="bg"?["bg"]:[],'
        '...e.gitBranch?[e.gitBranch]:[],t];if(e.tag)n.push(`#${e.tag}`);'
        'if(e.agentSetting)n.push(`@${e.agentSetting}`);if(e.prNumber)n.push('
        'e.prRepository?`${e.prRepository}#${e.prNumber}`:`#${e.prNumber}`);'
        'return n.join(" \\xB7 ")}'
    )
    for operation in manifest_data["targets"][0]["operations"]:
        if operation["opId"] == "net-resume-marker":
            chunks.append(real_net_range + operation["endMarker"])
            continue
        required = " ".join(operation.get("requireWithinRange", []))
        filler = "A" * 5000
        chunks.append(
            f"{operation['startMarker']} {required} {filler} {operation['endMarker']}"
        )
    chunks.append(' case"user":{}' * 4)
    source_bytes = " ".join(chunks).encode("utf-8")
    source = tmp_path / "claude-source"
    source.write_bytes(source_bytes)
    source_sha = hashlib.sha256(source_bytes).hexdigest()
    manifest_data["targets"][0]["sourceIdentity"]["sha256"] = source_sha
    manifest_data["targets"][0]["sourceIdentity"]["sizeBytes"] = len(source_bytes)
    manifest = load_manifest_dict(manifest_data)
    report = build_patchset(
        BuildRequest(
            source_path=source,
            output_dir=tmp_path / "out",
            manifests=[(package_dir, manifest)],
            source_version="2.1.198",
            source_version_output="2.1.198 (Claude Code)",
            source_sha256=source_sha,
            source_size_bytes=len(source_bytes),
            platform="darwin",
            arch="arm64",
            run_signing=False,
            run_smoke=False,
            activate=False,
        )
    )
    assert report.status == "verified", report.failureReason
    assert (tmp_path / "out" / "claude").exists()
