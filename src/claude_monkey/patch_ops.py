from __future__ import annotations

import hashlib
from dataclasses import dataclass

from claude_monkey.manifest import Operation


class PatchError(ValueError):
    pass


@dataclass(frozen=True)
class PlannedOperation:
    package_id: str
    op_id: str
    label: str
    start: int
    end: int
    old_len: int
    new_len: int
    padding_len: int
    old_sha256: str
    replacement: bytes


def b(value: str) -> bytes:
    return value.encode("utf-8")


def count_occurrences(source: bytes, needle: bytes) -> int:
    if needle == b"":
        return 0
    count = 0
    start = 0
    while True:
        idx = source.find(needle, start)
        if idx < 0:
            return count
        count += 1
        start = idx + 1


def compute_operation_range(
    source: bytes,
    operation: Operation,
    replacement: bytes,
    package_id: str = "",
) -> PlannedOperation:
    if operation.type == "replace_between":
        if operation.start_marker is None or operation.end_marker is None:
            raise PatchError(
                f"{operation.op_id}: replace_between requires startMarker and endMarker"
            )
        start_marker = b(operation.start_marker)
        end_marker = b(operation.end_marker)
        start_count = count_occurrences(source, start_marker)
        if start_count != operation.expected_start_marker_count:
            raise PatchError(
                f"{operation.op_id}: start marker count "
                f"{start_count} != {operation.expected_start_marker_count}"
            )
        start = source.find(start_marker)
        end_count = count_occurrences(source[start + len(start_marker) :], end_marker)
        if end_count != operation.expected_end_marker_count:
            raise PatchError(
                f"{operation.op_id}: end marker count "
                f"{end_count} != {operation.expected_end_marker_count}"
            )
        end = source.find(end_marker, start + len(start_marker))
    elif operation.type == "replace_exact":
        if operation.exact is None:
            raise PatchError(f"{operation.op_id}: replace_exact requires exact")
        exact = b(operation.exact)
        exact_count = count_occurrences(source, exact)
        if exact_count != 1:
            raise PatchError(f"{operation.op_id}: exact marker count {exact_count} != 1")
        start = source.find(exact)
        end = start + len(exact)
    else:
        raise PatchError(f"{operation.op_id}: unsupported operation type {operation.type}")

    old = source[start:end]
    for required in operation.require_within_range:
        if b(required) not in old:
            raise PatchError(f"{operation.op_id}: required bytes missing from range: {required}")
    if operation.old_range_length is not None and operation.old_range_length != len(old):
        raise PatchError(f"{operation.op_id}: old range length mismatch")
    old_sha = hashlib.sha256(old).hexdigest()
    if operation.old_range_sha256 is not None and operation.old_range_sha256 != old_sha:
        raise PatchError(f"{operation.op_id}: old range sha256 mismatch")
    if len(replacement) > len(old):
        raise PatchError(
            f"{operation.op_id}: replacement too large: {len(replacement)} > {len(old)}"
        )
    if operation.padding == "spaces":
        padded = replacement + (b" " * (len(old) - len(replacement)))
    elif operation.padding == "none":
        if len(replacement) != len(old):
            raise PatchError(f"{operation.op_id}: padding none requires exact length")
        padded = replacement
    else:
        raise PatchError(f"{operation.op_id}: unsupported padding {operation.padding}")
    return PlannedOperation(
        package_id=package_id,
        op_id=operation.op_id,
        label=operation.label,
        start=start,
        end=end,
        old_len=len(old),
        new_len=len(replacement),
        padding_len=len(old) - len(replacement),
        old_sha256=old_sha,
        replacement=padded,
    )


def plan_patch(
    source: bytes,
    operations: list[tuple[str, Operation, bytes]],
) -> list[PlannedOperation]:
    planned = [
        compute_operation_range(source, op, replacement, package_id)
        for package_id, op, replacement in operations
    ]
    planned.sort(key=lambda item: (item.start, item.end, item.package_id, item.op_id))
    for left, right in zip(planned, planned[1:], strict=False):
        if left.end > right.start:
            raise PatchError(
                f"overlap: {left.package_id}:{left.op_id} [{left.start},{left.end}) and "
                f"{right.package_id}:{right.op_id} [{right.start},{right.end})"
            )
    return planned


def render_patched_bytes(source: bytes, planned: list[PlannedOperation]) -> bytes:
    output = bytearray()
    cursor = 0
    for item in sorted(planned, key=lambda p: p.start):
        output.extend(source[cursor : item.start])
        output.extend(item.replacement)
        cursor = item.end
    output.extend(source[cursor:])
    return bytes(output)
