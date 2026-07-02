from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from claude_monkey.manifest import Assertion, Manifest, Target
from claude_monkey.patch_ops import PatchError, plan_patch, render_patched_bytes
from claude_monkey.payloads import load_payload_bytes
from claude_monkey.reports import BuildReport


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


def assert_condition(data: bytes, assertion: Assertion) -> dict:
    if assertion.scope != "whole_binary":
        raise ValueError(f"unsupported_assertion_scope:{assertion.scope}")
    needle = assertion.value.encode("utf-8")
    found = needle in data
    passed = found if assertion.type == "must_contain" else not found
    return {
        "type": assertion.type,
        "scope": assertion.scope,
        "value": assertion.value,
        "passed": passed,
    }


def failed_report(request: BuildRequest, reason: str) -> BuildReport:
    return BuildReport(
        status="failed",
        sourceClaudePath=str(request.source_path),
        sourceVersion=request.source_version,
        sourceVersionOutput=request.source_version_output,
        sourceSha256=request.source_sha256,
        sourceSizeBytes=request.source_size_bytes,
        platform=request.platform,
        arch=request.arch,
        enabledPatches=[manifest.id for _, manifest in request.manifests],
        manifestDigests={
            manifest.id: digest_manifest(manifest) for _, manifest in request.manifests
        },
        failureReason=reason,
        unverifiedCandidate=request.unverified_candidate,
    )


def build_patchset(request: BuildRequest) -> BuildReport:
    request.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = request.output_dir / "build-report.json"
    source = request.source_path.read_bytes()
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
            for precondition in target.preconditions:
                result = assert_condition(source, precondition)
                verification_results.append({"packageId": manifest.id, **result})
                if not result["passed"]:
                    report = failed_report(request, f"precondition_failed:{manifest.id}")
                    report.verificationResults = verification_results
                    report.write(report_path)
                    return report
            for operation in target.operations:
                replacement = load_payload_bytes(operation.replacement, package_dir)
                patch_inputs.append((manifest.id, operation, replacement))
        planned = plan_patch(source, patch_inputs)
        final = render_patched_bytes(source, planned)
        for _, manifest, target in selected:
            for postcondition in target.postconditions:
                result = assert_condition(final, postcondition)
                verification_results.append({"packageId": manifest.id, **result})
                if not result["passed"]:
                    report = failed_report(request, f"postcondition_failed:{manifest.id}")
                    report.verificationResults = verification_results
                    report.write(report_path)
                    return report
        if request.run_signing or request.run_smoke:
            report = failed_report(request, "verification_hooks_unimplemented")
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
        sourceSha256=request.source_sha256,
        sourceSizeBytes=request.source_size_bytes,
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
    report.write(report_path)
    return report
