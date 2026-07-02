from __future__ import annotations

import hashlib
from dataclasses import dataclass

from claude_monkey.manifest_v2 import ModuleOperationV2


class ModulePatchError(ValueError):
    pass


@dataclass(frozen=True)
class PlannedModuleOperation:
    package_id: str
    op_id: str
    label: str
    module_path: str
    module_start: int
    module_end: int
    old_len: int
    new_len: int
    delta: int
    old_sha256: str
    replacement: bytes


def _b(value: str) -> bytes:
    return value.encode("utf-8")


def _count(source: bytes, needle: bytes) -> int:
    if needle == b"":
        return 0
    count = 0
    pos = 0
    while True:
        found = source.find(needle, pos)
        if found < 0:
            return count
        count += 1
        pos = found + 1


def _range_for_operation(module: bytes, operation: ModuleOperationV2) -> tuple[int, int]:
    if operation.type == "replace_between":
        if operation.start_marker is None or operation.end_marker is None:
            raise ModulePatchError(
                f"{operation.op_id}: replace_between requires startMarker and endMarker"
            )
        start_marker = _b(operation.start_marker)
        end_marker = _b(operation.end_marker)
        start_count = _count(module, start_marker)
        if start_count != operation.expected_start_marker_count:
            raise ModulePatchError(
                f"{operation.op_id}: start marker count {start_count} "
                f"!= {operation.expected_start_marker_count}"
            )
        start = module.find(start_marker)
        tail = module[start + len(start_marker) :]
        end_count = _count(tail, end_marker)
        if end_count != operation.expected_end_marker_count:
            raise ModulePatchError(
                f"{operation.op_id}: end marker count {end_count} "
                f"!= {operation.expected_end_marker_count}"
            )
        end = module.find(end_marker, start + len(start_marker))
    elif operation.type == "replace_exact":
        if operation.exact is None:
            raise ModulePatchError(f"{operation.op_id}: replace_exact requires exact")
        exact = _b(operation.exact)
        exact_count = _count(module, exact)
        if exact_count != 1:
            raise ModulePatchError(f"{operation.op_id}: exact marker count {exact_count} != 1")
        start = module.find(exact)
        end = start + len(exact)
    else:
        raise ModulePatchError(f"{operation.op_id}: unsupported operation type {operation.type}")
    if start < 0 or end < 0 or end < start:
        raise ModulePatchError(f"{operation.op_id}: invalid module range [{start},{end})")
    return start, end


def plan_module_operations(
    package_id: str,
    module_path: str,
    module_content: bytes,
    operations: list[tuple[ModuleOperationV2, bytes]],
) -> list[PlannedModuleOperation]:
    planned: list[PlannedModuleOperation] = []
    for operation, replacement in operations:
        start, end = _range_for_operation(module_content, operation)
        old = module_content[start:end]
        for required in operation.require_within_range:
            if _b(required) not in old:
                raise ModulePatchError(
                    f"{operation.op_id}: required bytes missing from range: {required}"
                )
        if operation.old_range_length is not None and operation.old_range_length != len(old):
            raise ModulePatchError(f"{operation.op_id}: old range length mismatch")
        old_sha = hashlib.sha256(old).hexdigest()
        if operation.old_range_sha256 is not None and operation.old_range_sha256 != old_sha:
            raise ModulePatchError(f"{operation.op_id}: old range sha256 mismatch")
        planned.append(
            PlannedModuleOperation(
                package_id=package_id,
                op_id=operation.op_id,
                label=operation.label,
                module_path=module_path,
                module_start=start,
                module_end=end,
                old_len=len(old),
                new_len=len(replacement),
                delta=len(replacement) - len(old),
                old_sha256=old_sha,
                replacement=replacement,
            )
        )
    planned.sort(key=lambda item: (item.module_start, item.module_end, item.package_id, item.op_id))
    for left, right in zip(planned, planned[1:], strict=False):
        if left.module_end > right.module_start:
            raise ModulePatchError(
                f"overlap: {left.package_id}:{left.op_id} [{left.module_start},{left.module_end}) "
                f"and {right.package_id}:{right.op_id} [{right.module_start},{right.module_end})"
            )
    return planned


def render_changed_module(module_content: bytes, planned: list[PlannedModuleOperation]) -> bytes:
    output = bytearray()
    cursor = 0
    for item in sorted(planned, key=lambda op: op.module_start):
        output.extend(module_content[cursor : item.module_start])
        output.extend(item.replacement)
        cursor = item.module_end
    output.extend(module_content[cursor:])
    return bytes(output)
