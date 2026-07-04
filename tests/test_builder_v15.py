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


def test_build_patchset_v15_activates_despite_manual_smoke_flag(successful_build_request):
    # The manual-smoke activation gate is disabled: there is no GUI affordance to
    # perform manual smoke/activation, so a package declaring manualSmoke.required
    # no longer blocks activation. A successful build (automated validation
    # passing) activates directly; see builder_v15.py for the bypass comment.
    report = build_patchset_v15(successful_build_request(manual_smoke=True))
    assert report.status == "verified"
    assert report.activationEligible is True
    assert "manual_smoke_pending" not in report.activationBlockers
    assert report.manualSmoke["required"] is True
    assert report.manualSmoke["status"] == "bypassed"


def test_build_patchset_v15_activate_true_activates_with_manual_smoke_flag(
    successful_build_request, tmp_path
):
    # End-to-end version of the bypass: with --activate requested and a real
    # current_path target, a build from a manualSmoke-required package activates
    # the symlink directly instead of stalling with activationStatus="blocked".
    current_path = tmp_path / "current" / "claude"
    request = successful_build_request(manual_smoke=True, activate=True, current_path=current_path)
    report = build_patchset_v15(request)
    assert report.status == "verified"
    assert report.activationStatus == "activated"
    assert current_path.is_symlink()


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
