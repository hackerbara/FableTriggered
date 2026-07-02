from __future__ import annotations

import hashlib

import pytest

from claude_monkey.manifest_v2 import ModuleOperationV2, PayloadRefV2
from claude_monkey.module_patch import ModulePatchError, plan_module_operations, render_changed_module

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
