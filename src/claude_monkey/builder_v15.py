from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from claude_monkey.bun_graph import parse_bun_section
from claude_monkey.macho import find_macho_layout
from claude_monkey.manifest_v2 import ManifestV2, PayloadRefV2, TargetV2, load_manifest_v2_dict
from claude_monkey.module_patch import PlannedModuleOperation, plan_module_operations, render_changed_module


@dataclass(frozen=True)
class ValidationRequestV15:
    source_path: Path
    package_dir: Path
    source_version: str
    source_version_output: str
    platform: str
    arch: str


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


def target_matches(target: TargetV2, request: ValidationRequestV15, source: bytes) -> bool:
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
