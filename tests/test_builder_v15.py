from __future__ import annotations

from pathlib import Path

from tests.builder_fixtures import write_fixture_package  # noqa: F401 - re-exported for other tests
from tests.fixtures_bun import build_aligned_macho_fixture

from claude_monkey.builder_v15 import build_patchset_v15

pytest_plugins = ["tests.builder_fixtures"]


def test_build_patchset_v15_writes_copied_output_and_report(successful_build_request):
    request = successful_build_request()
    source = request.source_path
    report = build_patchset_v15(request)
    assert report.automatedStatus == "passed"
    assert report.activationEligible is True
    assert report.outputPath is not None
    assert Path(report.outputPath).exists()
    assert source.read_bytes() == build_aligned_macho_fixture()[0]


def test_build_patchset_v15_blocks_activation_for_manual_smoke(successful_build_request):
    report = build_patchset_v15(successful_build_request(manual_smoke=True))
    assert report.status == "manual_smoke_pending"
    assert report.activationEligible is False
    assert "manual_smoke_pending" in report.activationBlockers


def test_schema_v1_package_is_migration_required(bad_manifest_build_request):
    report = build_patchset_v15(bad_manifest_build_request())
    assert report.status == "failed"
    assert report.failureReason == "schema_v1_migration_required"


def test_source_identity_mismatch_report_names_current_and_target(successful_build_request):
    report = build_patchset_v15(
        successful_build_request(
            source_version="2.1.199",
            source_version_output="2.1.199 (Claude Code)",
        )
    )

    assert report.status == "failed"
    assert report.failureReason is not None
    assert "source_identity_mismatch:fixture-v15" in report.failureReason
    assert "current source is Claude 2.1.199" in report.failureReason
    assert "package targets Claude fixture" in report.failureReason
