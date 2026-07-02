from __future__ import annotations

import json

from claude_monkey.builder import BuildRequest, build_patchset
from claude_monkey.manifest import load_manifest_dict
from tests.test_manifest import valid_manifest

TEST_SHA = "b" * 64


def test_build_patchset_writes_report_and_output(tmp_path):
    source = tmp_path / "claude-source"
    source.write_bytes(b"HEAD case\"a\":{OLD_A_BODY} case\"b\":{OLD_B_BODY} TAIL")
    data = valid_manifest()
    data["targets"][0]["sourceIdentity"]["sha256"] = TEST_SHA
    manifest = load_manifest_dict(data)
    out_dir = tmp_path / "out"
    report = build_patchset(
        BuildRequest(
            source_path=source,
            output_dir=out_dir,
            manifests=[(tmp_path, manifest)],
            source_version="2.1.198",
            source_version_output="2.1.198 (Claude Code)",
            source_sha256=TEST_SHA,
            source_size_bytes=source.stat().st_size,
            platform="darwin",
            arch="arm64",
            skip_identity_check=True,
            run_signing=False,
            run_smoke=False,
            activate=False,
        )
    )
    output = out_dir / "claude"
    report_path = out_dir / "build-report.json"
    assert output.exists()
    assert report_path.exists()
    assert b"NEW_A_BODY" in output.read_bytes()
    encoded = json.loads(report_path.read_text())
    assert encoded["activationStatus"] == "skipped"
    assert encoded["enabledPatches"] == ["example-patch"]
    assert report.status == "verified"


def test_identity_mismatch_blocks_normal_build(tmp_path):
    source = tmp_path / "claude-source"
    source.write_bytes(b"HEAD case\"a\":{OLD_A_BODY} case\"b\":{OLD_B_BODY} TAIL")
    manifest = load_manifest_dict(valid_manifest())
    report = build_patchset(
        BuildRequest(
            source_path=source,
            output_dir=tmp_path / "out",
            manifests=[(tmp_path, manifest)],
            source_version="2.1.199",
            source_version_output="2.1.199 (Claude Code)",
            source_sha256=TEST_SHA,
            source_size_bytes=source.stat().st_size,
            platform="darwin",
            arch="arm64",
            skip_identity_check=False,
            unverified_candidate=False,
            run_signing=False,
            run_smoke=False,
            activate=False,
        )
    )
    assert report.status == "failed"
    assert "identity_mismatch" in report.failureReason
