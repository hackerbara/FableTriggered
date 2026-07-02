from __future__ import annotations

import pytest
from tests.fixtures import tiny_binary

from claude_monkey.manifest import Operation, PayloadRef
from claude_monkey.patch_ops import (
    PatchError,
    compute_operation_range,
    plan_patch,
    render_patched_bytes,
)


def op(op_id: str, start: str, end: str, replacement: str) -> Operation:
    return Operation(
        op_id=op_id,
        label=op_id,
        type="replace_between",
        start_marker=start,
        end_marker=end,
        exact=None,
        expected_start_marker_count=1,
        expected_end_marker_count=1,
        require_within_range=("OLD_A_BODY",) if op_id == "a" else (),
        replacement=PayloadRef(inline=replacement),
        padding="spaces",
    )


def test_replace_between_half_open_and_padded():
    source = tiny_binary()
    operation = op("a", "case\"a\":{", "case\"b\":{", "case\"a\":{NEW}")
    planned = compute_operation_range(source, operation, b"case\"a\":{NEW}")
    assert source[planned.start : planned.end].startswith(b"case\"a\":{")
    result = render_patched_bytes(source, [planned])
    assert b"case\"a\":{NEW}" in result
    assert len(result) == len(source)


def test_missing_marker_fails_closed():
    with pytest.raises(PatchError, match="start marker count"):
        compute_operation_range(tiny_binary(), op("a", "missing", "case\"b\":{", "x"), b"x")


def test_duplicate_marker_fails_closed():
    source = tiny_binary() + b" case\"a\":{duplicate}"
    with pytest.raises(PatchError, match="start marker count"):
        compute_operation_range(source, op("a", "case\"a\":{", "case\"b\":{", "x"), b"x")


def test_required_within_range_fails_closed():
    operation = op("a", "case\"a\":{", "case\"b\":{", "x")
    operation = Operation(**{**operation.__dict__, "require_within_range": ("NOT_PRESENT",)})
    with pytest.raises(PatchError, match="required bytes missing"):
        compute_operation_range(tiny_binary(), operation, b"x")


def test_oversized_replacement_fails_closed():
    with pytest.raises(PatchError, match="replacement too large"):
        compute_operation_range(
            tiny_binary(), op("a", "case\"a\":{", "case\"b\":{", "X" * 1000), b"X" * 1000
        )


def test_overlapping_ranges_are_rejected():
    first = op("a", "case\"a\":{", "case\"b\":{", "case\"a\":{NEW}")
    second = op("overlap", "OLD_A_BODY", "case\"b\":{", "Z")
    with pytest.raises(PatchError, match="overlap"):
        plan_patch(tiny_binary(), [("pkg", first, b"case\"a\":{NEW}"), ("pkg", second, b"Z")])


def test_adjacent_ranges_are_allowed_and_ordered_by_original_offset():
    source = tiny_binary()
    first = op("a", "case\"a\":{", "case\"b\":{", "case\"a\":{NEW_A}")
    second = op("b", "case\"b\":{", "TAIL", "case\"b\":{NEW_B} ")
    planned = plan_patch(
        source,
        [("pkg", second, b"case\"b\":{NEW_B} "), ("pkg", first, b"case\"a\":{NEW_A}")],
    )
    assert [p.op_id for p in planned] == ["a", "b"]


def test_replace_between_defensively_rejects_negative_end_range():
    operation = op("bad", "HEAD", "MISSING", "HEAD")
    operation = Operation(**{**operation.__dict__, "expected_end_marker_count": 0})
    with pytest.raises(PatchError, match="invalid byte range"):
        compute_operation_range(tiny_binary(), operation, b"HEAD")


def test_replace_exact_requires_single_exact_match():
    operation = Operation(
        op_id="exact",
        label="exact",
        type="replace_exact",
        start_marker=None,
        end_marker=None,
        exact="OLD_A_BODY",
        expected_start_marker_count=1,
        expected_end_marker_count=1,
        require_within_range=(),
        replacement=PayloadRef(inline="NEW_A_BODY"),
        padding="spaces",
    )
    planned = compute_operation_range(tiny_binary(), operation, b"NEW_A_BODY")
    assert tiny_binary()[planned.start : planned.end] == b"OLD_A_BODY"


def test_padding_none_requires_exact_length():
    operation = op("a", "case\"a\":{", "case\"b\":{", "short")
    operation = Operation(**{**operation.__dict__, "padding": "none"})
    with pytest.raises(PatchError, match="padding none requires exact length"):
        compute_operation_range(tiny_binary(), operation, b"short")


def test_old_range_length_and_sha_are_checked():
    operation = op("a", "case\"a\":{", "case\"b\":{", "case\"a\":{NEW}")
    wrong_length = Operation(**{**operation.__dict__, "old_range_length": 1})
    with pytest.raises(PatchError, match="old range length mismatch"):
        compute_operation_range(tiny_binary(), wrong_length, b"case\"a\":{NEW}")

    wrong_sha = Operation(**{**operation.__dict__, "old_range_sha256": "0" * 64})
    with pytest.raises(PatchError, match="old range sha256 mismatch"):
        compute_operation_range(tiny_binary(), wrong_sha, b"case\"a\":{NEW}")
