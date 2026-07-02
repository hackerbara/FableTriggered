from __future__ import annotations

import json

from tests.test_manifest import valid_manifest

from claude_monkey.builder import BuildRequest, build_patchset
from claude_monkey.manifest import load_manifest_dict

TEST_SHA = "b" * 64


def test_build_patchset_writes_report_and_output(tmp_path):
    source = tmp_path / "claude-source"
    source.write_bytes(b"HEAD case\"a\":{OLD_A_BODY} case\"b\":{OLD_B_BODY} TAIL")
    data = valid_manifest()
    data["targets"][0]["sourceIdentity"]["sha256"] = TEST_SHA
    data["targets"][0]["sourceIdentity"]["sizeBytes"] = source.stat().st_size
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
            skip_identity_check=False,
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


def build_request_for_source(tmp_path, *, skip_identity_check=False, unverified_candidate=False):
    source = tmp_path / "claude-source"
    source.write_bytes(b"HEAD case\"a\":{OLD_A_BODY} case\"b\":{OLD_B_BODY} TAIL")
    data = valid_manifest()
    data["targets"][0]["sourceIdentity"]["sha256"] = TEST_SHA
    manifest = load_manifest_dict(data)
    return BuildRequest(
        source_path=source,
        output_dir=tmp_path / "out",
        manifests=[(tmp_path, manifest)],
        source_version="9.9.9",
        source_version_output="9.9.9 (Claude Code)",
        source_sha256="c" * 64,
        source_size_bytes=source.stat().st_size,
        platform="darwin",
        arch="arm64",
        skip_identity_check=skip_identity_check,
        unverified_candidate=unverified_candidate,
        run_signing=False,
        run_smoke=False,
        activate=False,
    )


def test_skip_identity_check_cannot_publish_verified_build(tmp_path):
    report = build_patchset(build_request_for_source(tmp_path, skip_identity_check=True))
    assert report.status == "unverified_candidate"
    assert report.unverifiedCandidate is True


def test_identity_bypass_requires_unambiguous_target(tmp_path):
    request = build_request_for_source(tmp_path, skip_identity_check=True)
    package_dir, manifest = request.manifests[0]
    duplicated = load_manifest_dict(
        {**manifest.raw, "targets": [*manifest.raw["targets"], manifest.raw["targets"][0]]}
    )
    ambiguous = BuildRequest(**{**request.__dict__, "manifests": [(package_dir, duplicated)]})
    report = build_patchset(ambiguous)
    assert report.status == "failed"
    assert "ambiguous_identity_bypass" in report.failureReason


def test_range_assertions_are_rejected_until_supported(tmp_path):
    source = tmp_path / "claude-source"
    source.write_bytes(b"HEAD case\"a\":{OLD_A_BODY} case\"b\":{OLD_B_BODY} TAIL")
    data = valid_manifest()
    data["targets"][0]["sourceIdentity"]["sha256"] = TEST_SHA
    data["targets"][0]["sourceIdentity"]["sizeBytes"] = source.stat().st_size
    data["targets"][0]["postconditions"] = [
        {"type": "must_not_contain", "scope": "range", "opId": "replace-a", "value": "TAIL"}
    ]
    manifest = load_manifest_dict(data)
    report = build_patchset(
        BuildRequest(
            source_path=source,
            output_dir=tmp_path / "out",
            manifests=[(tmp_path, manifest)],
            source_version="2.1.198",
            source_version_output="2.1.198 (Claude Code)",
            source_sha256=TEST_SHA,
            source_size_bytes=source.stat().st_size,
            platform="darwin",
            arch="arm64",
            run_signing=False,
            run_smoke=False,
            activate=False,
        )
    )
    assert report.status == "failed"
    assert "unsupported_assertion_scope" in report.failureReason


def test_requested_signing_or_smoke_without_hooks_is_not_verified(tmp_path):
    source = tmp_path / "claude-source"
    source.write_bytes(b"HEAD case\"a\":{OLD_A_BODY} case\"b\":{OLD_B_BODY} TAIL")
    data = valid_manifest()
    data["targets"][0]["sourceIdentity"]["sha256"] = TEST_SHA
    data["targets"][0]["sourceIdentity"]["sizeBytes"] = source.stat().st_size
    manifest = load_manifest_dict(data)
    report = build_patchset(
        BuildRequest(
            source_path=source,
            output_dir=tmp_path / "out",
            manifests=[(tmp_path, manifest)],
            source_version="2.1.198",
            source_version_output="2.1.198 (Claude Code)",
            source_sha256=TEST_SHA,
            source_size_bytes=source.stat().st_size,
            platform="darwin",
            arch="arm64",
            run_signing=True,
            run_smoke=True,
            activate=False,
        )
    )
    assert report.status == "failed"
    assert "verification_hooks_unimplemented" in report.failureReason


def test_skip_identity_check_is_unverified_even_when_identity_matches(tmp_path):
    source = tmp_path / "claude-source"
    source.write_bytes(b"HEAD case\"a\":{OLD_A_BODY} case\"b\":{OLD_B_BODY} TAIL")
    data = valid_manifest()
    data["targets"][0]["sourceIdentity"]["sha256"] = TEST_SHA
    data["targets"][0]["sourceIdentity"]["sizeBytes"] = source.stat().st_size
    manifest = load_manifest_dict(data)
    report = build_patchset(
        BuildRequest(
            source_path=source,
            output_dir=tmp_path / "out",
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
    assert report.status == "unverified_candidate"
    assert report.unverifiedCandidate is True
