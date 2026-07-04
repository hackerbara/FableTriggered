from __future__ import annotations

import hashlib

import pytest

from claude_monkey.manifest_v2 import ModuleOperationV2, PayloadRefV2
from claude_monkey.module_patch import (
    ModulePatchError,
    plan_module_operations,
    render_changed_module,
)

MODULE = b"function render(){OLD_RENDER}\nfunction after(){return 1}\n"


def op(replacement: bytes) -> ModuleOperationV2:
    old = MODULE[: MODULE.index(b"function after(){")]
    return ModuleOperationV2(
        op_id="replace-renderer",
        label="Replace renderer",
        type="replace_between",
        start_marker="function render(){",
        end_marker="function after(){",
        exact=None,
        expected_start_marker_count=1,
        expected_end_marker_count=1,
        require_within_range=("OLD_RENDER",),
        old_range_sha256=hashlib.sha256(old).hexdigest(),
        old_range_length=len(old),
        replacement=PayloadRefV2(inline=replacement.decode("utf-8")),
        known_behavior_change=None,
    )


def test_plan_module_operations_allows_growth_without_padding():
    replacement = b"function render(){NEW_RENDER_LONGER}\n"
    planned = plan_module_operations(
        "pkg", "/$bunfs/root/src/entrypoints/cli.js", MODULE, [(op(replacement), replacement)]
    )
    assert planned[0].module_start == 0
    assert planned[0].module_end == MODULE.index(b"function after(){")
    assert planned[0].old_len < planned[0].new_len
    changed = render_changed_module(MODULE, planned)
    assert replacement in changed
    assert len(changed) > len(MODULE)


def test_plan_module_operations_rejects_old_range_hash_mismatch():
    operation = op(b"function render(){NEW}\n")
    operation = ModuleOperationV2(**{**operation.__dict__, "old_range_sha256": "0" * 64})
    with pytest.raises(ModulePatchError, match="old range sha256 mismatch"):
        plan_module_operations(
            "pkg",
            "/$bunfs/root/src/entrypoints/cli.js",
            MODULE,
            [(operation, b"function render(){NEW}\n")],
        )


def test_plan_module_operations_rejects_overlaps():
    first = op(b"function render(){NEW}\n")
    second = ModuleOperationV2(
        **{
            **first.__dict__,
            "op_id": "overlap",
            "start_marker": "OLD",
            "end_marker": "after",
            "old_range_sha256": None,
            "old_range_length": None,
        }
    )
    with pytest.raises(ModulePatchError, match="overlap"):
        plan_module_operations(
            "pkg",
            "/$bunfs/root/src/entrypoints/cli.js",
            MODULE,
            [(first, b"function render(){NEW}\n"), (second, b"NEW")],
        )



def make_op(**overrides) -> ModuleOperationV2:
    base = dict(
        op_id="insert-entry",
        label="Insert entry",
        type="insert_after",
        start_marker=None,
        end_marker=None,
        exact=None,
        expected_start_marker_count=1,
        expected_end_marker_count=1,
        require_within_range=(),
        old_range_sha256=None,
        old_range_length=None,
        replacement=PayloadRefV2(inline=",NEW_ENTRY"),
        known_behavior_change=None,
        anchor="OLD_RENDER",
        insert_order=None,
    )
    base.update(overrides)
    return ModuleOperationV2(**base)


def test_insert_after_plans_zero_width_point_after_anchor():
    replacement = b",NEW_ENTRY"
    planned = plan_module_operations(
        "pkg", "/$bunfs/root/src/entrypoints/cli.js", MODULE, [(make_op(), replacement)]
    )
    point = MODULE.index(b"OLD_RENDER") + len(b"OLD_RENDER")
    item = planned[0]
    assert item.kind == "insertion"
    assert item.op_type == "insert_after"
    assert (item.module_start, item.module_end) == (point, point)
    assert item.old_len == 0
    assert item.new_len == len(replacement)
    assert item.delta == len(replacement)
    anchor_start = MODULE.index(b"OLD_RENDER")
    assert (anchor_start, anchor_start + len(b"OLD_RENDER")) in item.evidence_spans
    changed = render_changed_module(MODULE, planned)
    assert b"OLD_RENDER,NEW_ENTRY" in changed
    assert len(changed) == len(MODULE) + len(replacement)


def test_insert_before_plans_point_at_anchor_start():
    replacement = b"PREFIX_"
    planned = plan_module_operations(
        "pkg",
        "/$bunfs/root/src/entrypoints/cli.js",
        MODULE,
        [(make_op(type="insert_before"), replacement)],
    )
    assert planned[0].module_start == MODULE.index(b"OLD_RENDER")
    changed = render_changed_module(MODULE, planned)
    assert b"PREFIX_OLD_RENDER" in changed


def test_insertion_rejects_ambiguous_anchor():
    with pytest.raises(ModulePatchError, match="anchor count 2"):
        plan_module_operations(
            "pkg",
            "/$bunfs/root/src/entrypoints/cli.js",
            MODULE,
            [(make_op(anchor="function"), b",X")],
        )


def test_insertion_context_bounds_anchor_search():
    # "return 1" appears once; "n" appears many times. Context makes "n 1" unique scope.
    operation = make_op(
        anchor="return 1",
        start_marker="function after(){",
        end_marker="}",
        expected_end_marker_count=1,
    )
    planned = plan_module_operations(
        "pkg", "/$bunfs/root/src/entrypoints/cli.js", MODULE, [(operation, b";EXTRA()")]
    )
    item = planned[0]
    ctx_start = MODULE.index(b"function after(){")
    assert item.context_start == ctx_start
    assert item.context_end is not None and item.context_end > ctx_start
    changed = render_changed_module(MODULE, planned)
    assert b"return 1;EXTRA()" in changed


def test_insertion_missing_anchor_in_context_fails():
    operation = make_op(
        anchor="OLD_RENDER",
        start_marker="function after(){",
        end_marker="}",
    )
    with pytest.raises(ModulePatchError, match="anchor count 0"):
        plan_module_operations(
            "pkg", "/$bunfs/root/src/entrypoints/cli.js", MODULE, [(operation, b",X")]
        )



def test_replace_substring_within_claims_only_subspan():
    operation = make_op(
        op_id="sub",
        type="replace_substring_within",
        anchor=None,
        start_marker="function render(){",
        end_marker="}",
        expected_end_marker_count=2,
        sub_exact="OLD_RENDER",
        replacement=PayloadRefV2(inline="OLD_RENDER,EXTRA_FLAG"),
    )
    replacement = b"OLD_RENDER,EXTRA_FLAG"
    planned = plan_module_operations(
        "pkg", "/$bunfs/root/src/entrypoints/cli.js", MODULE, [(operation, replacement)]
    )
    item = planned[0]
    assert item.kind == "subspan_replacement"
    assert item.module_start == MODULE.index(b"OLD_RENDER")
    assert item.module_end == item.module_start + len(b"OLD_RENDER")
    assert item.context_start == MODULE.index(b"function render(){")
    changed = render_changed_module(MODULE, planned)
    assert b"function render(){OLD_RENDER,EXTRA_FLAG}" in changed
    # bytes outside the subspan are untouched stock
    assert changed.endswith(b"function after(){return 1}\n")


def test_replace_substring_within_rejects_non_unique_subspan():
    operation = make_op(
        op_id="sub-dup",
        type="replace_substring_within",
        anchor=None,
        start_marker="function render(){",
        end_marker="return 1}",
        expected_end_marker_count=1,
        sub_exact="function",  # appears twice inside this context
        replacement=PayloadRefV2(inline="fn"),
    )
    with pytest.raises(ModulePatchError, match="subExact count"):
        plan_module_operations(
            "pkg", "/$bunfs/root/src/entrypoints/cli.js", MODULE, [(operation, b"fn")]
        )


def test_replace_substring_within_context_sha_mismatch_fails():
    operation = make_op(
        op_id="sub-ctx",
        type="replace_substring_within",
        anchor=None,
        start_marker="function render(){",
        end_marker="}",
        expected_end_marker_count=2,
        sub_exact="OLD_RENDER",
        context_sha256="0" * 64,
        replacement=PayloadRefV2(inline="NEW"),
    )
    with pytest.raises(ModulePatchError, match="context sha256 mismatch"):
        plan_module_operations(
            "pkg", "/$bunfs/root/src/entrypoints/cli.js", MODULE, [(operation, b"NEW")]
        )


def test_replace_substring_within_old_range_applies_to_subspan():
    old = b"OLD_RENDER"
    operation = make_op(
        op_id="sub-old",
        type="replace_substring_within",
        anchor=None,
        start_marker="function render(){",
        end_marker="}",
        expected_end_marker_count=2,
        sub_exact="OLD_RENDER",
        old_range_sha256=hashlib.sha256(old).hexdigest(),
        old_range_length=len(old),
        replacement=PayloadRefV2(inline="NEW"),
    )
    planned = plan_module_operations(
        "pkg", "/$bunfs/root/src/entrypoints/cli.js", MODULE, [(operation, b"NEW")]
    )
    assert planned[0].old_len == len(old)
