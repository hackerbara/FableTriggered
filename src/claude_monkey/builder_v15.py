from __future__ import annotations

import base64
import hashlib
import json
import shutil
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from claude_monkey.binary_inspect import inspect_binary_bytes
from claude_monkey.bun_graph import parse_bun_section
from claude_monkey.install import use_official
from claude_monkey.macho import find_macho_layout
from claude_monkey.manifest_v2 import (
    AssertionV2,
    ManifestV2,
    ManifestV2Error,
    PayloadRefV2,
    TargetV2,
    load_manifest_v2_dict,
)
from claude_monkey.module_patch import (
    PlannedModuleOperation,
    plan_module_operations,
    render_changed_module,
)
from claude_monkey.repack import repack_changed_modules
from claude_monkey.reports_v2 import BuildReportV2
from claude_monkey.smoke import (
    CommandResult,
    codesign_sign,
    codesign_verify,
    run_command,
    smoke_claude_code_version_and_help,
)

CommandRunner = Callable[[list[str]], CommandResult]


@dataclass(frozen=True)
class ValidationRequestV15:
    source_path: Path
    package_dir: Path
    source_version: str
    source_version_output: str
    platform: str
    arch: str


@dataclass(frozen=True)
class BuildRequestV15:
    source_path: Path
    output_dir: Path
    package_dirs: list[Path]
    source_version: str
    source_version_output: str
    platform: str
    arch: str
    run_signing: bool = True
    run_smoke: bool = True
    activate: bool = False
    current_path: Path | None = None
    command_runner: CommandRunner = run_command


def load_manifest_v2(package_dir: Path) -> ManifestV2:
    return load_manifest_v2_dict(json.loads((package_dir / "patch.json").read_text()))


def load_payload(ref: PayloadRefV2, package_dir: Path) -> bytes:
    if ref.inline is not None:
        data = ref.inline.encode("utf-8") if ref.encoding == "utf-8" else base64.b64decode(ref.inline)
    else:
        assert ref.path is not None
        data = (package_dir / ref.path).read_bytes()
    if ref.sha256 is not None and hashlib.sha256(data).hexdigest() != ref.sha256:
        raise ValueError("replacement sha256 mismatch")
    return data


def target_matches(target: TargetV2, request: ValidationRequestV15 | BuildRequestV15, source: bytes) -> bool:
    ident = target.source_identity
    return (
        ident.claude_version == request.source_version
        and ident.version_output == request.source_version_output
        and ident.sha256 == hashlib.sha256(source).hexdigest()
        and ident.size_bytes == len(source)
        and ident.platform == request.platform
        and ident.arch == request.arch
    )


def validate_package(request: ValidationRequestV15) -> dict[str, Any]:
    source = request.source_path.read_bytes()
    manifest = load_manifest_v2(request.package_dir)
    matching_targets = [target for target in manifest.targets if target_matches(target, request, source)]
    if len(matching_targets) != 1:
        return {
            "schemaVersion": 1,
            "ok": False,
            "packageId": manifest.id,
            "errorCode": "source_identity_mismatch",
            "errors": ["source identity did not match exactly"],
        }
    target = matching_targets[0]
    layout = find_macho_layout(source)
    graph = parse_bun_section(
        source[layout.bun_section.offset : layout.bun_section.offset + layout.bun_section.size]
    )
    if graph.validation_errors:
        return {
            "schemaVersion": 1,
            "ok": False,
            "packageId": manifest.id,
            "errorCode": "bun_graph_invalid",
            "errors": graph.validation_errors,
        }
    resolved: list[PlannedModuleOperation] = []
    changed_modules: dict[str, bytes] = {}
    for module_target in target.modules:
        module = graph.module_by_path(module_target.path)
        if (
            hashlib.sha256(module.content).hexdigest() != module_target.content_sha256
            or module.content_size != module_target.content_length
        ):
            return {
                "schemaVersion": 1,
                "ok": False,
                "packageId": manifest.id,
                "errorCode": "module_identity_failed",
                "errors": [module_target.path],
            }
        operation_inputs = [
            (operation, load_payload(operation.replacement, request.package_dir))
            for operation in module_target.operations
        ]
        planned = plan_module_operations(manifest.id, module_target.path, module.content, operation_inputs)
        resolved.extend(planned)
        changed_modules[module_target.path] = render_changed_module(module.content, planned)
    return {
        "schemaVersion": 1,
        "ok": True,
        "packageId": manifest.id,
        "sourceMatched": True,
        "modulesMatched": True,
        "operationsResolved": [
            {
                "modulePath": item.module_path,
                "opId": item.op_id,
                "moduleStart": item.module_start,
                "moduleEnd": item.module_end,
                "oldLen": item.old_len,
                "newLen": item.new_len,
                "delta": item.delta,
            }
            for item in resolved
        ],
        "manualSmokeRequired": target.manual_smoke.required,
        "errors": [],
    }


def _command_result_dict(result: CommandResult) -> dict[str, Any]:
    return asdict(result)


def _exception_result(argv: list[str], exc: Exception) -> CommandResult:
    return CommandResult(
        argv=argv,
        returncode=127,
        stdout="",
        stderr=f"{type(exc).__name__}: {exc}",
    )


def _safe_runner(runner: CommandRunner) -> CommandRunner:
    def wrapped(argv: list[str]) -> CommandResult:
        try:
            return runner(argv)
        except Exception as exc:
            return _exception_result(argv, exc)

    return wrapped


def _base_report(request: BuildRequestV15, source: bytes | None = None) -> BuildReportV2:
    source_bytes = source if source is not None else b""
    return BuildReportV2(
        sourceClaudePath=str(request.source_path),
        sourceVersion=request.source_version,
        sourceVersionOutput=request.source_version_output,
        sourceSha256=hashlib.sha256(source_bytes).hexdigest() if source is not None else "",
        sourceSizeBytes=len(source_bytes) if source is not None else 0,
    )


def _write_failed(
    request: BuildRequestV15,
    report_path: Path,
    reason: str,
    *,
    source: bytes | None = None,
    enabled: list[str] | None = None,
) -> BuildReportV2:
    report = _base_report(request, source)
    report.status = "failed"
    report.automatedStatus = "failed"
    report.enabledPatches = enabled or []
    report.failureReason = reason
    report.activationEligible = False
    report.activationStatus = "blocked" if request.activate else "skipped"
    report.write(report_path)
    return report


def _assert_condition_v2(
    assertion: AssertionV2,
    *,
    modules: dict[str, bytes],
    binary: bytes | None,
) -> dict[str, Any]:
    if assertion.type.startswith("module_"):
        if assertion.module_path is None:
            raise ValueError("module_assertion_requires_modulePath")
        haystack = modules.get(assertion.module_path)
        if haystack is None:
            raise ValueError(f"module_assertion_missing_module:{assertion.module_path}")
    elif assertion.type.startswith("binary_"):
        if binary is None:
            raise ValueError("binary_assertion_requires_binary")
        haystack = binary
    else:
        raise ValueError(f"unsupported_assertion_type:{assertion.type}")
    needle = assertion.value.encode("utf-8")
    found = needle in haystack
    passed = found if assertion.type.endswith("_must_contain") else not found
    return {
        "type": assertion.type,
        "modulePath": assertion.module_path,
        "value": assertion.value,
        "passed": passed,
    }


def _check_overlaps(planned: list[PlannedModuleOperation]) -> None:
    ordered = sorted(planned, key=lambda item: (item.module_start, item.module_end, item.package_id, item.op_id))
    for left, right in zip(ordered, ordered[1:], strict=False):
        if left.module_end > right.module_start:
            raise ValueError(
                f"patch_conflict:{left.package_id}:{left.op_id}:{right.package_id}:{right.op_id}"
            )


def _apply_signing_v15(report: BuildReportV2, output: Path, runner: CommandRunner) -> bool:
    safe_runner = _safe_runner(runner)
    sign = codesign_sign(output, safe_runner)
    verify = codesign_verify(output, safe_runner)
    passed = sign.returncode == 0 and verify.returncode == 0
    report.signingResult = {
        "status": "passed" if passed else "failed",
        "sign": _command_result_dict(sign),
        "verify": _command_result_dict(verify),
    }
    if not passed:
        report.status = "failed"
        report.automatedStatus = "failed"
        report.failureReason = "signing_failed"
    return passed


def _select_packages(
    request: BuildRequestV15, source: bytes, report_path: Path
) -> tuple[list[tuple[Path, ManifestV2, TargetV2]], BuildReportV2 | None]:
    selected: list[tuple[Path, ManifestV2, TargetV2]] = []
    enabled: list[str] = []
    for package_dir in request.package_dirs:
        try:
            manifest = load_manifest_v2(package_dir)
        except ManifestV2Error as exc:
            reason = str(exc)
            if reason != "schema_v1_migration_required":
                reason = f"manifest_v2_invalid:{reason}"
            return selected, _write_failed(request, report_path, reason, source=source, enabled=enabled)
        enabled.append(manifest.id)
        matching = [target for target in manifest.targets if target_matches(target, request, source)]
        if len(matching) != 1:
            return selected, _write_failed(
                request,
                report_path,
                f"source_identity_mismatch:{manifest.id}",
                source=source,
                enabled=enabled,
            )
        selected.append((package_dir, manifest, matching[0]))
    return selected, None


def build_patchset_v15(request: BuildRequestV15) -> BuildReportV2:
    request.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = request.output_dir / "build-report.json"
    source = request.source_path.read_bytes()
    selected, failure = _select_packages(request, source, report_path)
    if failure is not None:
        return failure

    report = _base_report(request, source)
    report.enabledPatches = [manifest.id for _, manifest, _ in selected]
    try:
        layout = find_macho_layout(source)
        graph = parse_bun_section(
            source[layout.bun_section.offset : layout.bun_section.offset + layout.bun_section.size]
        )
        if graph.validation_errors:
            raise ValueError(f"bun_graph_invalid:{graph.validation_errors}")
        original_modules = {module.path: module.content for module in graph.modules}
        planned_by_module: dict[str, list[PlannedModuleOperation]] = {}
        verification_results: list[dict[str, Any]] = []
        manual_required = False
        manual_reasons: list[str] = []
        for package_dir, manifest, target in selected:
            manual_required = manual_required or target.manual_smoke.required
            if target.manual_smoke.reason:
                manual_reasons.append(target.manual_smoke.reason)
            for assertion in target.preconditions:
                result = _assert_condition_v2(assertion, modules=original_modules, binary=source)
                verification_results.append({"packageId": manifest.id, **result})
                if not result["passed"]:
                    raise ValueError(f"precondition_failed:{manifest.id}")
            for module_target in target.modules:
                module = graph.module_by_path(module_target.path)
                module_sha = hashlib.sha256(module.content).hexdigest()
                if module_sha != module_target.content_sha256 or module.content_size != module_target.content_length:
                    raise ValueError(f"module_identity_failed:{module_target.path}")
                operation_inputs = [
                    (operation, load_payload(operation.replacement, package_dir))
                    for operation in module_target.operations
                ]
                planned = plan_module_operations(
                    manifest.id, module_target.path, module.content, operation_inputs
                )
                planned_by_module.setdefault(module_target.path, []).extend(planned)
        changed_modules: dict[str, bytes] = {}
        for module_path, planned in planned_by_module.items():
            _check_overlaps(planned)
            changed_modules[module_path] = render_changed_module(original_modules[module_path], planned)
        if not changed_modules:
            raise ValueError("no_module_changes")
        repack = repack_changed_modules(source, changed_modules)
        for _, manifest, target in selected:
            for assertion in target.postconditions:
                result = _assert_condition_v2(
                    assertion,
                    modules={**original_modules, **changed_modules},
                    binary=repack.output_bytes,
                )
                verification_results.append({"packageId": manifest.id, **result})
                if not result["passed"]:
                    raise ValueError(f"postcondition_failed:{manifest.id}")
        output = request.output_dir / "claude"
        output.write_bytes(repack.output_bytes)
        shutil.copymode(request.source_path, output)
        report.outputPath = str(output)
        report.operationsApplied = [
            {
                "packageId": item.package_id,
                "opId": item.op_id,
                "label": item.label,
                "modulePath": item.module_path,
                "moduleStart": item.module_start,
                "moduleEnd": item.module_end,
                "oldLen": item.old_len,
                "newLen": item.new_len,
                "delta": item.delta,
                "oldSha256": item.old_sha256,
            }
            for planned in planned_by_module.values()
            for item in planned
        ]
        report.changedModules = [
            {
                "modulePath": path,
                "oldSize": len(original_modules[path]),
                "newSize": len(new_bytes),
                "delta": len(new_bytes) - len(original_modules[path]),
                "oldSha256": hashlib.sha256(original_modules[path]).hexdigest(),
                "newSha256": hashlib.sha256(new_bytes).hexdigest(),
            }
            for path, new_bytes in changed_modules.items()
        ]
        report.bunGraphUpdates = repack.bun_graph_updates
        report.machoUpdates = repack.macho_updates
        report.machoUpdateDetails = repack.macho_update_details
        report.verificationResults = verification_results
        blockers: list[str] = []
        if request.run_signing:
            if not _apply_signing_v15(report, output, request.command_runner):
                report.write(report_path)
                return report
        else:
            report.signingResult = {"status": "skipped"}
            report.skippedGates.append("signing")
            blockers.append("signing_skipped")
        output_bytes = output.read_bytes()
        report.outputSha256 = hashlib.sha256(output_bytes).hexdigest()
        report.outputSizeBytes = len(output_bytes)
        post_sign = inspect_binary_bytes(output_bytes, source_path=str(output))
        report.postSignInspection = {
            "bunGraphValid": bool(post_sign["ok"]),
            "validationErrors": post_sign["validationErrors"],
        }
        if not post_sign["ok"] or post_sign["validationErrors"]:
            report.status = "failed"
            report.automatedStatus = "failed"
            report.failureReason = "post_sign_inspection_failed"
            report.write(report_path)
            return report
        if request.run_smoke:
            smoke_result = smoke_claude_code_version_and_help(
                output, request.source_version_output, _safe_runner(request.command_runner)
            )
            report.smokeTestResults = [smoke_result]
            if not smoke_result["passed"]:
                report.status = "failed"
                report.automatedStatus = "failed"
                report.failureReason = "smoke_failed"
                report.write(report_path)
                return report
        else:
            report.skippedGates.append("smoke")
            blockers.append("smoke_skipped")
        if manual_required:
            blockers.append("manual_smoke_pending")
            report.manualSmoke = {
                "required": True,
                "status": "pending",
                "reason": "; ".join(manual_reasons) if manual_reasons else None,
            }
        else:
            report.manualSmoke = {"required": False, "status": "not_required", "reason": None}
        report.automatedStatus = "passed" if not report.skippedGates else "skipped"
        report.activationBlockers = blockers
        report.activationEligible = not blockers and report.automatedStatus == "passed"
        if report.activationEligible:
            report.status = "verified"
        elif "manual_smoke_pending" in blockers and report.automatedStatus == "passed":
            report.status = "manual_smoke_pending"
        else:
            report.status = "skipped_gates"
        if request.activate:
            if report.activationEligible and request.current_path is not None:
                use_official(request.current_path, output)
                report.activationStatus = "activated"
            else:
                if request.current_path is None and report.activationEligible:
                    report.activationBlockers.append("activation_requires_current_path")
                    report.activationEligible = False
                report.activationStatus = "blocked"
        else:
            report.activationStatus = "skipped"
        report.write(report_path)
        return report
    except Exception as exc:
        report.status = "failed"
        report.automatedStatus = "failed"
        report.failureReason = str(exc)
        report.activationEligible = False
        report.write(report_path)
        return report
