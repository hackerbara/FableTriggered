from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from claude_monkey.install import use_official
from claude_monkey.manifest import Assertion, Manifest, Target
from claude_monkey.patch_ops import PatchError, PlannedOperation, plan_patch, render_patched_bytes
from claude_monkey.payloads import load_payload_bytes
from claude_monkey.reports import BuildReport
from claude_monkey.smoke import (
    CommandResult,
    codesign_sign,
    codesign_verify,
    run_command,
    smoke_version_and_help,
)

CommandRunner = Callable[[list[str]], CommandResult]


@dataclass(frozen=True)
class BuildRequest:
    source_path: Path
    output_dir: Path
    manifests: list[tuple[Path, Manifest]]
    source_version: str
    source_version_output: str
    source_sha256: str
    source_size_bytes: int
    platform: str
    arch: str
    skip_identity_check: bool = False
    unverified_candidate: bool = False
    run_signing: bool = True
    run_smoke: bool = True
    activate: bool = False
    current_path: Path | None = None
    command_runner: CommandRunner = run_command


def digest_manifest(manifest: Manifest) -> str:
    encoded = json.dumps(manifest.raw, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def target_matches_request(target: Target, request: BuildRequest) -> bool:
    ident = target.source_identity
    return (
        ident.claude_version == request.source_version
        and ident.version_output == request.source_version_output
        and ident.sha256 == request.source_sha256
        and ident.size_bytes == request.source_size_bytes
        and ident.platform == request.platform
        and ident.arch == request.arch
    )


def select_target(manifest: Manifest, request: BuildRequest) -> Target | None:
    for target in manifest.targets:
        if target_matches_request(target, request):
            return target
    return None


def select_bypass_target(manifest: Manifest) -> Target | None:
    if len(manifest.targets) != 1:
        return None
    return manifest.targets[0]


def _range_index(planned: list[PlannedOperation]) -> dict[str, list[tuple[int, int]]]:
    ranges: dict[str, list[tuple[int, int]]] = {}
    for item in planned:
        ranges.setdefault(item.op_id, []).append((item.start, item.end))
    return ranges


def assert_condition(
    data: bytes,
    assertion: Assertion,
    ranges_by_op_id: dict[str, list[tuple[int, int]]] | None = None,
) -> dict[str, Any]:
    if assertion.scope == "whole_binary":
        haystack = data
    elif assertion.scope == "range":
        if not assertion.op_id:
            raise ValueError("range_assertion_requires_op_id")
        ranges = (ranges_by_op_id or {}).get(assertion.op_id, [])
        if len(ranges) != 1:
            raise ValueError(f"range_assertion_op_id_not_unique:{assertion.op_id}")
        start, end = ranges[0]
        haystack = data[start:end]
    else:
        raise ValueError(f"unsupported_assertion_scope:{assertion.scope}")
    needle = assertion.value.encode("utf-8")
    found = needle in haystack
    passed = found if assertion.type == "must_contain" else not found
    return {
        "type": assertion.type,
        "scope": assertion.scope,
        "value": assertion.value,
        "opId": assertion.op_id,
        "passed": passed,
    }


def failed_report(
    request: BuildRequest,
    reason: str,
    source_sha256: str | None = None,
    source_size_bytes: int | None = None,
) -> BuildReport:
    return BuildReport(
        status="failed",
        sourceClaudePath=str(request.source_path),
        sourceVersion=request.source_version,
        sourceVersionOutput=request.source_version_output,
        sourceSha256=source_sha256 or request.source_sha256,
        sourceSizeBytes=(
            source_size_bytes if source_size_bytes is not None else request.source_size_bytes
        ),
        platform=request.platform,
        arch=request.arch,
        enabledPatches=[manifest.id for _, manifest in request.manifests],
        manifestDigests={
            manifest.id: digest_manifest(manifest) for _, manifest in request.manifests
        },
        failureReason=reason,
        unverifiedCandidate=request.unverified_candidate,
    )


def _command_result_dict(result: CommandResult) -> dict[str, Any]:
    return asdict(result)


def _apply_signing(report: BuildReport, output: Path, runner: CommandRunner) -> bool:
    sign = codesign_sign(output, runner)
    verify = codesign_verify(output, runner)
    passed = sign.returncode == 0 and verify.returncode == 0
    report.signingResult = {
        "status": "passed" if passed else "failed",
        "sign": _command_result_dict(sign),
        "verify": _command_result_dict(verify),
    }
    if not passed:
        report.status = "failed"
        report.failureReason = "signing_failed"
    return passed


def _apply_smoke(report: BuildReport, output: Path, runner: CommandRunner) -> bool:
    results = smoke_version_and_help(output, runner)
    report.smokeTestResults = [_command_result_dict(result) for result in results]
    passed = all(result.returncode == 0 for result in results)
    if not passed:
        report.status = "failed"
        report.failureReason = "smoke_failed"
    return passed


def build_patchset(request: BuildRequest) -> BuildReport:
    request.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = request.output_dir / "build-report.json"
    source = request.source_path.read_bytes()
    actual_source_sha256 = hashlib.sha256(source).hexdigest()
    actual_source_size_bytes = len(source)
    if (
        actual_source_sha256 != request.source_sha256
        or actual_source_size_bytes != request.source_size_bytes
    ) and not (request.skip_identity_check or request.unverified_candidate):
        report = failed_report(
            request,
            "source_identity_mismatch",
            actual_source_sha256,
            actual_source_size_bytes,
        )
        report.write(report_path)
        return report
    selected: list[tuple[Path, Manifest, Target]] = []
    identity_bypassed = request.skip_identity_check
    for package_dir, manifest in request.manifests:
        target = select_target(manifest, request)
        if target is None and (request.skip_identity_check or request.unverified_candidate):
            target = select_bypass_target(manifest)
            identity_bypassed = target is not None
            if target is None:
                report = failed_report(request, f"ambiguous_identity_bypass:{manifest.id}")
                report.write(report_path)
                return report
        if target is None:
            report = failed_report(request, f"identity_mismatch:{manifest.id}")
            report.write(report_path)
            return report
        selected.append((package_dir, manifest, target))

    try:
        patch_inputs = []
        verification_results = []
        for package_dir, manifest, target in selected:
            for operation in target.operations:
                replacement = load_payload_bytes(operation.replacement, package_dir)
                patch_inputs.append((manifest.id, operation, replacement))
        planned = plan_patch(source, patch_inputs)
        old_ranges = _range_index(planned)
        for _, manifest, target in selected:
            for precondition in target.preconditions:
                result = assert_condition(source, precondition, old_ranges)
                verification_results.append({"packageId": manifest.id, **result})
                if not result["passed"]:
                    report = failed_report(request, f"precondition_failed:{manifest.id}")
                    report.verificationResults = verification_results
                    report.write(report_path)
                    return report
        final = render_patched_bytes(source, planned)
        new_ranges = _range_index(planned)
        for _, manifest, target in selected:
            for postcondition in target.postconditions:
                result = assert_condition(final, postcondition, new_ranges)
                verification_results.append({"packageId": manifest.id, **result})
                if not result["passed"]:
                    report = failed_report(request, f"postcondition_failed:{manifest.id}")
                    report.verificationResults = verification_results
                    report.write(report_path)
                    return report
    except (PatchError, ValueError, OSError) as exc:
        report = failed_report(request, f"patch_failed:{exc}")
        report.write(report_path)
        return report

    output = request.output_dir / "claude"
    output.write_bytes(final)
    shutil.copymode(request.source_path, output)
    operations = [
        {
            "packageId": item.package_id,
            "opId": item.op_id,
            "label": item.label,
            "oldLen": item.old_len,
            "newLen": item.new_len,
            "paddingLen": item.padding_len,
            "oldSha256": item.old_sha256,
        }
        for item in planned
    ]
    ranges = [
        {"packageId": item.package_id, "opId": item.op_id, "start": item.start, "end": item.end}
        for item in planned
    ]
    report = BuildReport(
        status="unverified_candidate"
        if request.unverified_candidate or identity_bypassed
        else "verified",
        sourceClaudePath=str(request.source_path),
        sourceVersion=request.source_version,
        sourceVersionOutput=request.source_version_output,
        sourceSha256=actual_source_sha256,
        sourceSizeBytes=actual_source_size_bytes,
        platform=request.platform,
        arch=request.arch,
        enabledPatches=[manifest.id for _, manifest in request.manifests],
        manifestDigests={
            manifest.id: digest_manifest(manifest) for _, manifest in request.manifests
        },
        operationsApplied=operations,
        byteRanges=ranges,
        verificationResults=verification_results,
        activationStatus="skipped",
        unverifiedCandidate=request.unverified_candidate or identity_bypassed,
    )
    if request.run_signing and not _apply_signing(report, output, request.command_runner):
        report.write(report_path)
        return report
    if request.run_smoke and not _apply_smoke(report, output, request.command_runner):
        report.write(report_path)
        return report
    if request.activate:
        if request.current_path is None:
            report.status = "failed"
            report.failureReason = "activation_requires_current_path"
            report.write(report_path)
            return report
        use_official(request.current_path, output)
        report.activationStatus = "activated"
    report.write(report_path)
    return report
