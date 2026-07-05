# Composition Engine Structured Splices (Phases 1–2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add zero-width insertion ops (`insert_before`/`insert_after`), a subspan replacement op (`replace_substring_within`), deterministic shared-point ordering, structured conflict codes, insertion evidence verification, and package relationship metadata (`requiresPackages`/`conflictsWithPackages`) to the ClaudeMonkey composition engine — so multiple packages can co-edit the same stock statement without overlapping byte ranges.

**Architecture:** Everything stays pure-Python byte splicing against ORIGINAL stock module bytes with a single sorted render pass. New op types extend `manifest_v2.py` (parse) and `module_patch.py` (resolve/plan/render/verify); `builder_v15.py` gains relationship validation, insertion-evidence gating, and richer reports. No JS parser, no sequential patch application, no new dependencies.

**Tech Stack:** Python 3 stdlib only (`hashlib`, `dataclasses`). Tests: pytest, existing fixtures in `tests/fixtures_bun.py`.

**Source spec:** `docs/superpowers/specs/2026-07-03-composition-engine-structured-splices-design.md` (as amended 2026-07-04). Read it before starting.

## Global Constraints

- All operations resolve against **original stock module bytes** — never sequentially patched bytes. Rendering is one sorted pass.
- **Existing `replace_exact` and `replace_between` behavior is byte-for-byte unchanged.** Existing manifests parse with no edits. `schemaVersion` stays `2`.
- Fail closed on everything ambiguous: non-unique anchors, duplicate `insertOrder`, missing `insertOrder` at shared points, anchor evidence inside claimed ranges.
- Structured conflict errors keep the `patch_conflict:` prefix (existing tests match on it) and add a code segment: `patch_conflict:<code>:<detail…>`.
- `expectedAnchorCount` / `expectedSubExactCount` values other than `1` are **rejected** at parse (field accepted for forward-compat, only value 1 supported — YAGNI).
- Report changes are additive fields inside `operationsApplied` dicts (`BuildReportV2.operationsApplied` is `list[dict[str, Any]]` — no schema bump; `schemaVersion` stays 3).
- **Out of scope:** retarget diagnostics for `validate-package` (spec section exists but is not in Phase 1 or 2), helper ops (`append_to_array_after_item` etc. — explicitly deferred), named seams, any package migrations beyond test fixtures.
- Test command: `python3 -m pytest <file> -v` from repo root `/Users/MAC/Documents/Claude-patch`.
- Commit style (match `git log`): `feat:`/`fix:`/`test:` prefix, imperative, why-focused body when non-obvious.

## Vocabulary (from the spec)

- **claimed range** — the byte span `[module_start, module_end)` an op owns. Replacements claim non-zero spans; insertions claim a zero-width point (`module_start == module_end`).
- **kind** — planned-op classification: `"replacement"` (replace_exact/replace_between), `"insertion"` (insert_before/insert_after), `"subspan_replacement"` (replace_substring_within).
- **context** — for context-bounded ops, the byte span from start of `startMarker` through **end** of `endMarker` (both markers included — note this differs from `replace_between`'s claimed range, which excludes the endMarker). Context is evidence, not claimed.
- **evidence spans** — for insertions: the anchor's byte span plus both context-marker spans. Must be disjoint from every claimed non-zero range in the build.
- **render order** — the tuple `(module_start, module_end, insert_order ?? 0, package_id, op_id)`. Validation and rendering both sort by it; same-point insertions therefore render in exactly the order validation accepted.

---

### Task 1: Manifest parsing — insertion op types

**Files:**
- Modify: `src/claude_monkey/manifest_v2.py` (lines 9, 41–56, 193–219)
- Test: `tests/test_manifest_v2.py`

**Interfaces:**
- Produces: `ModuleOperationV2` gains fields `anchor: str | None`, `insert_order: int | None`, `expected_anchor_count: int`, `sub_exact: str | None`, `expected_sub_exact_count: int`, `context_sha256: str | None`, `seam_hint: str | None` (all defaulted, appended after `known_behavior_change`). `SUPPORTED_OPERATION_TYPES` gains `"insert_before"`, `"insert_after"`. New private validator `_validate_operation_shape(operation)`.
- Consumes: nothing new.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_manifest_v2.py` (check the file's existing helper for building a minimal valid manifest dict; if it has one, reuse it — the ops below assume a helper `manifest_dict()` returning a parseable schema-2 dict whose first operation you can replace. If no such helper exists, build the dict inline copying the shape from `tests/test_builder_v15.py::write_fixture_package`):

```python
import pytest

from claude_monkey.manifest_v2 import ManifestV2Error, load_manifest_v2_dict


def _insert_op(**overrides):
    op = {
        "opId": "append-entry",
        "label": "Append entry",
        "type": "insert_after",
        "anchor": 'Oe&&"frame"',
        "insertOrder": 200,
        "replacement": {"inline": ',"reminders"'},
    }
    op.update(overrides)
    return op


def _manifest_with_op(op):
    return {
        "schemaVersion": 2,
        "id": "fixture",
        "name": "Fixture",
        "description": "Fixture",
        "packageVersion": "0.1.0",
        "targets": [
            {
                "sourceIdentity": {
                    "claudeVersion": "fixture",
                    "versionOutput": "fixture (Claude Code)",
                    "sha256": "0" * 64,
                    "sizeBytes": 1,
                    "platform": "darwin",
                    "arch": "arm64",
                },
                "requiredEngine": "bun_graph_repack",
                "requiredBinaryFormat": "bun_standalone_macho64",
                "modules": [
                    {
                        "path": "/$bunfs/root/src/entrypoints/cli.js",
                        "contentSha256": "0" * 64,
                        "contentLength": 1,
                        "operations": [op],
                    }
                ],
            }
        ],
    }


def test_insert_after_parses_with_anchor_and_order():
    manifest = load_manifest_v2_dict(_manifest_with_op(_insert_op()))
    operation = manifest.targets[0].modules[0].operations[0]
    assert operation.type == "insert_after"
    assert operation.anchor == 'Oe&&"frame"'
    assert operation.insert_order == 200
    assert operation.expected_anchor_count == 1


def test_insert_before_parses_without_order():
    op = _insert_op(type="insert_before")
    del op["insertOrder"]
    operation = load_manifest_v2_dict(_manifest_with_op(op)).targets[0].modules[0].operations[0]
    assert operation.type == "insert_before"
    assert operation.insert_order is None


def test_insertion_requires_anchor():
    op = _insert_op()
    del op["anchor"]
    with pytest.raises(ManifestV2Error, match="requires anchor"):
        load_manifest_v2_dict(_manifest_with_op(op))


def test_insertion_rejects_old_range_evidence():
    with pytest.raises(ManifestV2Error, match="old-range evidence"):
        load_manifest_v2_dict(_manifest_with_op(_insert_op(oldRangeLength=0)))


def test_insertion_rejects_expected_anchor_count_other_than_one():
    with pytest.raises(ManifestV2Error, match="expectedAnchorCount"):
        load_manifest_v2_dict(_manifest_with_op(_insert_op(expectedAnchorCount=2)))


def test_insertion_context_markers_must_pair():
    with pytest.raises(ManifestV2Error, match="context markers"):
        load_manifest_v2_dict(_manifest_with_op(_insert_op(startMarker="ji=")))


def test_replace_exact_rejects_structured_splice_fields():
    op = {
        "opId": "legacy",
        "label": "Legacy",
        "type": "replace_exact",
        "exact": "OLD",
        "anchor": "OLD",
        "replacement": {"inline": "NEW"},
    }
    with pytest.raises(ManifestV2Error, match="not allowed on replace_exact"):
        load_manifest_v2_dict(_manifest_with_op(op))


def test_replace_exact_rejects_seam_hint():
    op = {
        "opId": "legacy-hint",
        "label": "Legacy",
        "type": "replace_exact",
        "exact": "OLD",
        "seamHint": "some.seam",
        "replacement": {"inline": "NEW"},
    }
    with pytest.raises(ManifestV2Error, match="not allowed on replace_exact"):
        load_manifest_v2_dict(_manifest_with_op(op))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_manifest_v2.py -v -k "insert or structured"`
Expected: FAIL — `unsupported operation type: insert_after` (and the reject-tests fail because parsing succeeds).

- [ ] **Step 3: Implement**

In `src/claude_monkey/manifest_v2.py`:

Line 9, extend the supported set:

```python
SUPPORTED_OPERATION_TYPES = {
    "replace_between",
    "replace_exact",
    "insert_before",
    "insert_after",
}
```

Extend `ModuleOperationV2` (after `known_behavior_change: str | None`) with defaulted fields:

```python
    anchor: str | None = None
    insert_order: int | None = None
    expected_anchor_count: int = 1
    sub_exact: str | None = None
    expected_sub_exact_count: int = 1
    context_sha256: str | None = None
    seam_hint: str | None = None
```

In `parse_operation`, add the new kwargs to the `ModuleOperationV2(...)` construction and validate afterwards:

```python
    operation = ModuleOperationV2(
        op_id=require_string(op, "opId"),
        label=require_string(op, "label"),
        type=op_type,
        start_marker=optional_string(op, "startMarker"),
        end_marker=optional_string(op, "endMarker"),
        exact=optional_string(op, "exact"),
        expected_start_marker_count=require_int(op, "expectedStartMarkerCount")
        if "expectedStartMarkerCount" in op
        else 1,
        expected_end_marker_count=require_int(op, "expectedEndMarkerCount")
        if "expectedEndMarkerCount" in op
        else 1,
        require_within_range=tuple(require_within),
        old_range_sha256=optional_sha256(op, "oldRangeSha256"),
        old_range_length=optional_non_negative_int(op, "oldRangeLength"),
        replacement=parse_payload(op.get("replacement")),
        known_behavior_change=optional_string(op, "knownBehaviorChange"),
        anchor=optional_string(op, "anchor"),
        insert_order=optional_non_negative_int(op, "insertOrder"),
        expected_anchor_count=require_int(op, "expectedAnchorCount")
        if "expectedAnchorCount" in op
        else 1,
        sub_exact=optional_string(op, "subExact"),
        expected_sub_exact_count=require_int(op, "expectedSubExactCount")
        if "expectedSubExactCount" in op
        else 1,
        context_sha256=optional_sha256(op, "contextSha256"),
        seam_hint=optional_string(op, "seamHint"),
    )
    _validate_operation_shape(operation)
    return operation
```

Add the validator below `parse_operation`:

```python
def _validate_operation_shape(operation: ModuleOperationV2) -> None:
    if operation.type in {"insert_before", "insert_after"}:
        if operation.anchor is None:
            raise ManifestV2Error(f"{operation.op_id}: {operation.type} requires anchor")
        if operation.expected_anchor_count != 1:
            raise ManifestV2Error(
                f"{operation.op_id}: expectedAnchorCount must be 1 (other values unsupported)"
            )
        if (operation.start_marker is None) != (operation.end_marker is None):
            raise ManifestV2Error(
                f"{operation.op_id}: context markers must be provided together"
            )
        if operation.exact is not None or operation.sub_exact is not None:
            raise ManifestV2Error(
                f"{operation.op_id}: exact/subExact not allowed on insertions"
            )
        if (
            operation.require_within_range
            or operation.old_range_sha256 is not None
            or operation.old_range_length is not None
        ):
            raise ManifestV2Error(
                f"{operation.op_id}: old-range evidence not allowed on insertions"
            )
    elif operation.type == "replace_substring_within":
        if operation.start_marker is None or operation.end_marker is None:
            raise ManifestV2Error(
                f"{operation.op_id}: replace_substring_within requires startMarker and endMarker"
            )
        if operation.sub_exact is None:
            raise ManifestV2Error(
                f"{operation.op_id}: replace_substring_within requires subExact"
            )
        if operation.expected_sub_exact_count != 1:
            raise ManifestV2Error(
                f"{operation.op_id}: expectedSubExactCount must be 1 (other values unsupported)"
            )
        if (
            operation.anchor is not None
            or operation.insert_order is not None
            or operation.exact is not None
        ):
            raise ManifestV2Error(
                f"{operation.op_id}: anchor/insertOrder/exact not allowed on replace_substring_within"
            )
    else:
        if (
            operation.anchor is not None
            or operation.insert_order is not None
            or operation.sub_exact is not None
            or operation.context_sha256 is not None
            or operation.seam_hint is not None
        ):
            raise ManifestV2Error(
                f"{operation.op_id}: structured-splice fields not allowed on {operation.type}"
            )
```

(The `replace_substring_within` branch is dead until Task 2 adds the type to `SUPPORTED_OPERATION_TYPES` — that's intentional; it keeps Task 2 a one-line type-set change plus tests.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_manifest_v2.py -v`
Expected: all PASS (new tests plus every pre-existing test — the pre-existing ones prove old manifests still parse).

- [ ] **Step 5: Commit**

```bash
git add src/claude_monkey/manifest_v2.py tests/test_manifest_v2.py
git commit -m "feat: parse insert_before/insert_after manifest operations"
```

---

### Task 2: Manifest parsing — replace_substring_within

**Files:**
- Modify: `src/claude_monkey/manifest_v2.py` (line 9 only — validator branch already exists from Task 1)
- Test: `tests/test_manifest_v2.py`

**Interfaces:**
- Produces: `"replace_substring_within"` in `SUPPORTED_OPERATION_TYPES`; ops parse with `sub_exact`, `context_sha256`, `seam_hint`, and old-range evidence applying to the subspan.
- Consumes: Task 1's fields and `_validate_operation_shape`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_manifest_v2.py` (reuses `_manifest_with_op` from Task 1):

```python
def _subspan_op(**overrides):
    op = {
        "opId": "add-flag",
        "label": "Add selection flag",
        "type": "replace_substring_within",
        "startMarker": 'let qb=Du==="tasks"',
        "endMarker": ";function Sf",
        "subExact": 'Ap=Du==="frame"',
        "oldRangeLength": 15,
        "replacement": {"inline": 'Ap=Du==="frame",hC=Du==="hiddenContext"'},
        "seamHint": "footer.selection.afterFrame",
    }
    op.update(overrides)
    return op


def test_replace_substring_within_parses():
    operation = (
        load_manifest_v2_dict(_manifest_with_op(_subspan_op()))
        .targets[0].modules[0].operations[0]
    )
    assert operation.type == "replace_substring_within"
    assert operation.sub_exact == 'Ap=Du==="frame"'
    assert operation.old_range_length == 15
    assert operation.seam_hint == "footer.selection.afterFrame"


def test_replace_substring_within_requires_sub_exact():
    op = _subspan_op()
    del op["subExact"]
    with pytest.raises(ManifestV2Error, match="requires subExact"):
        load_manifest_v2_dict(_manifest_with_op(op))


def test_replace_substring_within_requires_markers():
    op = _subspan_op()
    del op["endMarker"]
    with pytest.raises(ManifestV2Error, match="requires startMarker and endMarker"):
        load_manifest_v2_dict(_manifest_with_op(op))


def test_replace_substring_within_rejects_insert_order():
    with pytest.raises(ManifestV2Error, match="not allowed on replace_substring_within"):
        load_manifest_v2_dict(_manifest_with_op(_subspan_op(insertOrder=5)))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_manifest_v2.py -v -k "substring"`
Expected: FAIL — `unsupported operation type: replace_substring_within`.

- [ ] **Step 3: Implement**

In `src/claude_monkey/manifest_v2.py` line 9:

```python
SUPPORTED_OPERATION_TYPES = {
    "replace_between",
    "replace_exact",
    "insert_before",
    "insert_after",
    "replace_substring_within",
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_manifest_v2.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/claude_monkey/manifest_v2.py tests/test_manifest_v2.py
git commit -m "feat: parse replace_substring_within manifest operations"
```

---

### Task 3: Planner — resolve insertion ops to zero-width points

**Files:**
- Modify: `src/claude_monkey/module_patch.py`
- Test: `tests/test_module_patch.py`

**Interfaces:**
- Produces: `PlannedModuleOperation` gains defaulted fields `kind: str = "replacement"`, `op_type: str = "replace_exact"`, `insert_order: int | None = None`, `context_start: int | None = None`, `context_end: int | None = None`, `evidence_spans: tuple[tuple[int, int], ...] = ()`, `anchor: str | None = None`, `seam_hint: str | None = None`. New internal `_Resolved` dataclass and `_resolve_context(module, operation)`. `_range_for_operation` is replaced by `_resolve_operation(module, operation) -> _Resolved`.
- Consumes: Task 1's `ModuleOperationV2` fields.
- Later tasks rely on: `kind`, `insert_order`, `evidence_spans`, `delta` semantics (insertion: `old_len == 0`, `delta == new_len`).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_module_patch.py`. Note `MODULE = b"function render(){OLD_RENDER}\nfunction after(){return 1}\n"` already exists at the top of the file. Add a keyword-argument helper for building arbitrary ops (the existing `op()` helper is replace_between-specific — leave it alone):

```python
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
```

Note on `test_insertion_context_bounds_anchor_search`: `expected_end_marker_count` counts occurrences of the end marker **after** the start marker (see `_range_for_operation`'s tail-count behavior, which `_resolve_context` mirrors). In `MODULE`, after `function after(){` there is exactly one `}`. If this assumption is wrong when you run it, adjust `expected_end_marker_count` to the actual count printed in the error — the count check is the behavior under test, not the specific number.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_module_patch.py -v -k "insert"`
Expected: FAIL — `unsupported operation type insert_after` (from `_range_for_operation`'s else branch) and missing `kind` attribute.

- [ ] **Step 3: Implement**

In `src/claude_monkey/module_patch.py`:

Extend `PlannedModuleOperation` (append after `replacement: bytes`):

```python
    kind: str = "replacement"
    op_type: str = "replace_exact"
    insert_order: int | None = None
    context_start: int | None = None
    context_end: int | None = None
    evidence_spans: tuple[tuple[int, int], ...] = ()
    anchor: str | None = None
    seam_hint: str | None = None
```

Add below `_count`:

```python
@dataclass(frozen=True)
class _Resolved:
    start: int
    end: int
    kind: str
    context_start: int | None = None
    context_end: int | None = None
    evidence_spans: tuple[tuple[int, int], ...] = ()


def _resolve_context(
    module: bytes, operation: ModuleOperationV2
) -> tuple[int, int, tuple[tuple[int, int], ...]]:
    """Resolve a context span: start of startMarker through END of endMarker.

    Differs from replace_between's claimed range (which excludes the endMarker):
    context is search scope and evidence, not a claimed range.
    """
    if operation.start_marker is None or operation.end_marker is None:
        raise ModulePatchError(f"{operation.op_id}: context requires startMarker and endMarker")
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
    end_marker_start = module.find(end_marker, start + len(start_marker))
    end = end_marker_start + len(end_marker)
    spans = ((start, start + len(start_marker)), (end_marker_start, end))
    return start, end, spans
```

Rename `_range_for_operation` to `_resolve_operation` returning `_Resolved`. The `replace_between` / `replace_exact` branches keep their exact current logic (behavior unchanged), wrapped at the end as `return _Resolved(start, end, "replacement")`. Add the insertion branch before the `else`:

```python
    elif operation.type in {"insert_before", "insert_after"}:
        if operation.anchor is None:
            raise ModulePatchError(f"{operation.op_id}: insertion requires anchor")
        anchor = _b(operation.anchor)
        if operation.start_marker is not None:
            ctx_start, ctx_end, ctx_spans = _resolve_context(module, operation)
        else:
            ctx_start, ctx_end, ctx_spans = None, None, ()
        scope_base = ctx_start if ctx_start is not None else 0
        scope = module[ctx_start:ctx_end] if ctx_start is not None else module
        anchor_count = _count(scope, anchor)
        if anchor_count != 1:
            raise ModulePatchError(f"{operation.op_id}: anchor count {anchor_count} != 1")
        found = scope_base + scope.find(anchor)
        point = found if operation.type == "insert_before" else found + len(anchor)
        return _Resolved(
            start=point,
            end=point,
            kind="insertion",
            context_start=ctx_start,
            context_end=ctx_end,
            evidence_spans=ctx_spans + ((found, found + len(anchor)),),
        )
```

In `plan_module_operations`, use the resolver and thread the new fields:

```python
    for operation, replacement in operations:
        resolved = _resolve_operation(module_content, operation)
        start, end = resolved.start, resolved.end
        old = module_content[start:end]
        # ... existing require_within_range / old_range_length / old_range_sha256 checks unchanged ...
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
                kind=resolved.kind,
                op_type=operation.type,
                insert_order=operation.insert_order,
                context_start=resolved.context_start,
                context_end=resolved.context_end,
                evidence_spans=resolved.evidence_spans,
                anchor=operation.anchor,
                seam_hint=operation.seam_hint,
            )
        )
```

Leave the existing sort + zip overlap check at the end of `plan_module_operations` untouched in this task (Task 5 replaces it). Zero-width old ranges need no special-casing: `old = module[p:p] == b""`, `old_len == 0`, and the manifest validator already rejected old-range evidence on insertions.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_module_patch.py -v`
Expected: all PASS (including the three pre-existing tests — replacement behavior unchanged).

- [ ] **Step 5: Commit**

```bash
git add src/claude_monkey/module_patch.py tests/test_module_patch.py
git commit -m "feat: plan zero-width insertion operations in module patcher"
```

---

### Task 4: Planner — replace_substring_within resolution

**Files:**
- Modify: `src/claude_monkey/module_patch.py`
- Test: `tests/test_module_patch.py`

**Interfaces:**
- Produces: `_resolve_operation` handles `replace_substring_within` — claims only the `subExact` span inside the marker-resolved context; `contextSha256` verified against stock context bytes in `plan_module_operations`.
- Consumes: Task 3's `_Resolved` / `_resolve_context`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_module_patch.py`:

```python
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
```

Add `insert_order=None` compatibility: `make_op` from Task 3 already includes `insert_order` in its base dict — when overriding for subspan ops pass `insert_order=None` implicitly (it's the default). `expected_end_marker_count` values: in `MODULE`, after `function render(){` the byte `}` appears twice (`OLD_RENDER}` and `return 1}`). If a count assertion fails at runtime, fix the expected count to the actual count in the error message — the uniqueness rule is what's under test.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_module_patch.py -v -k "substring"`
Expected: FAIL — `unsupported operation type replace_substring_within`.

- [ ] **Step 3: Implement**

In `_resolve_operation`, add before the final `else`:

```python
    elif operation.type == "replace_substring_within":
        if operation.sub_exact is None:
            raise ModulePatchError(
                f"{operation.op_id}: replace_substring_within requires subExact"
            )
        ctx_start, ctx_end, _ctx_spans = _resolve_context(module, operation)
        sub = _b(operation.sub_exact)
        scope = module[ctx_start:ctx_end]
        sub_count = _count(scope, sub)
        if sub_count != 1:
            raise ModulePatchError(f"{operation.op_id}: subExact count {sub_count} != 1")
        start = ctx_start + scope.find(sub)
        return _Resolved(
            start=start,
            end=start + len(sub),
            kind="subspan_replacement",
            context_start=ctx_start,
            context_end=ctx_end,
        )
```

(Evidence spans stay empty for subspan ops — the amended spec's anchor-disjointness rule applies to insertions only; a subspan op's claimed range participates in normal overlap checking.)

In `plan_module_operations`, after the existing `old_range_sha256` check, add the context evidence check:

```python
        if (
            operation.context_sha256 is not None
            and resolved.context_start is not None
            and resolved.context_end is not None
        ):
            context = module_content[resolved.context_start : resolved.context_end]
            if hashlib.sha256(context).hexdigest() != operation.context_sha256:
                raise ModulePatchError(f"{operation.op_id}: context sha256 mismatch")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_module_patch.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/claude_monkey/module_patch.py tests/test_module_patch.py
git commit -m "feat: plan replace_substring_within subspan operations"
```

---

### Task 5: Conflict validation — render order, shared points, structured codes

**Files:**
- Modify: `src/claude_monkey/module_patch.py`
- Modify: `src/claude_monkey/builder_v15.py:348-357` (`_check_overlaps`)
- Test: `tests/test_module_patch.py`

**Interfaces:**
- Produces: `_render_order(item) -> tuple` and public `check_planned_conflicts(planned: list[PlannedModuleOperation]) -> None` in `module_patch.py`, raising `ModulePatchError` with codes:
  - `patch_conflict:range_overlap:<pkgA>:<opA>:<pkgB>:<opB>`
  - `patch_conflict:insert_inside_claimed_range:<pkgA>:<opA>:<pkgB>:<opB>`
  - `patch_conflict:insert_order_required:<modulePath>:<offset>`
  - `patch_conflict:insert_order_duplicate:<modulePath>:<offset>:<order>`
  - `patch_conflict:insert_anchor_inside_claimed_range:<insertPkg>:<insertOp>:<ownerPkg>:<ownerOp>`
- Consumes: Task 3/4 planned-op fields. `builder_v15._check_overlaps` becomes a thin delegate.
- **Breaking change to error text:** the old within-package message was `overlap: pkg:op [a,b) and pkg:op [c,d)`; the old cross-package message was `patch_conflict:pkgA:opA:pkgB:opB`. Both change to the structured codes. Step 5 hunts down every existing test asserting the old formats.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_module_patch.py`:

```python
from claude_monkey.module_patch import check_planned_conflicts


def _plan(ops):
    return plan_module_operations("pkg", "/$bunfs/root/src/entrypoints/cli.js", MODULE, ops)


def test_shared_point_insertions_merge_in_insert_order():
    a = make_op(op_id="a", insert_order=200, replacement=PayloadRefV2(inline=",SECOND"))
    b = make_op(op_id="b", insert_order=100, replacement=PayloadRefV2(inline=",FIRST"))
    planned = _plan([(a, b",SECOND"), (b, b",FIRST")])
    changed = render_changed_module(MODULE, planned)
    assert b"OLD_RENDER,FIRST,SECOND" in changed


def test_shared_point_duplicate_insert_order_fails():
    a = make_op(op_id="a", insert_order=100)
    b = make_op(op_id="b", insert_order=100)
    with pytest.raises(ModulePatchError, match="patch_conflict:insert_order_duplicate"):
        _plan([(a, b",X"), (b, b",Y")])


def test_shared_point_missing_insert_order_fails():
    a = make_op(op_id="a", insert_order=100)
    b = make_op(op_id="b")  # insert_order=None
    with pytest.raises(ModulePatchError, match="patch_conflict:insert_order_required"):
        _plan([(a, b",X"), (b, b",Y")])


def test_single_insertion_needs_no_insert_order():
    planned = _plan([(make_op(), b",ONLY")])
    assert planned[0].insert_order is None


def test_insertion_inside_claimed_range_fails():
    # replacement claims [render-start, "function after(){"); insertion point lands inside it
    replacement_op = op(b"function render(){NEW}\n")  # existing replace_between helper
    inside = make_op(op_id="inside", anchor="function render(){")  # insert_after -> point inside claimed range
    with pytest.raises(ModulePatchError, match="patch_conflict:insert_inside_claimed_range"):
        _plan([(replacement_op, b"function render(){NEW}\n"), (inside, b",X")])


def test_insertion_anchor_inside_claimed_range_fails():
    # anchor "OLD_RENDER" lies INSIDE the replacement's claimed range, but the
    # insert_after point would be at offset 28 which is also inside; use an anchor
    # whose END coincides with the claimed range END so the point is at the boundary:
    # claimed range end is at index of "function after(){"; anchor ends exactly there.
    end = MODULE.index(b"function after(){")
    anchor_text = MODULE[end - 10 : end].decode()  # last 10 bytes of the claimed range
    replacement_op = op(b"function render(){NEW}\n")
    boundary = make_op(op_id="boundary", anchor=anchor_text)
    with pytest.raises(
        ModulePatchError, match="patch_conflict:insert_anchor_inside_claimed_range"
    ):
        _plan([(replacement_op, b"function render(){NEW}\n"), (boundary, b",X")])


def test_replacement_overlap_reports_range_overlap_code():
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
    with pytest.raises(ModulePatchError, match="patch_conflict:range_overlap"):
        _plan([(first, b"function render(){NEW}\n"), (second, b"NEW")])


def test_insertion_at_replacement_end_boundary_with_outside_anchor_is_allowed():
    # anchor entirely OUTSIDE the claimed range, point at/after boundary: allowed
    replacement_op = op(b"function render(){NEW}\n")
    after = make_op(op_id="after-fn", anchor="function after(){return 1}")
    planned = _plan([(replacement_op, b"function render(){NEW}\n"), (after, b"/*T*/")])
    changed = render_changed_module(MODULE, planned)
    assert b"function after(){return 1}/*T*/" in changed
    assert b"function render(){NEW}" in changed
```

(Check the anchor uniqueness assumptions when running: `anchor_text` sliced from `MODULE` must occur exactly once — if the sliced text is ambiguous, widen the slice until unique. The behavior under test is the disjointness rule, not the specific slice.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_module_patch.py -v -k "shared or inside or boundary or range_overlap"`
Expected: FAIL — `ImportError: cannot import name 'check_planned_conflicts'`.

- [ ] **Step 3: Implement**

In `src/claude_monkey/module_patch.py`, add:

```python
def _render_order(item: PlannedModuleOperation) -> tuple:
    return (
        item.module_start,
        item.module_end,
        item.insert_order if item.insert_order is not None else 0,
        item.package_id,
        item.op_id,
    )


def check_planned_conflicts(planned: list[PlannedModuleOperation]) -> None:
    ordered = sorted(planned, key=_render_order)
    for left, right in zip(ordered, ordered[1:], strict=False):
        if left.module_end > right.module_start:
            if "insertion" in (left.kind, right.kind):
                # stable role order: inserter first, owner second — matches the
                # insert_anchor_inside_claimed_range convention and the spec's
                # <insertPkg>:<insertOp>:<ownerPkg>:<ownerOp> code shape.
                inserter, owner = (left, right) if left.kind == "insertion" else (right, left)
                raise ModulePatchError(
                    "patch_conflict:insert_inside_claimed_range:"
                    f"{inserter.package_id}:{inserter.op_id}:{owner.package_id}:{owner.op_id}"
                )
            raise ModulePatchError(
                "patch_conflict:range_overlap:"
                f"{left.package_id}:{left.op_id}:{right.package_id}:{right.op_id}"
            )
    points: dict[int, list[PlannedModuleOperation]] = {}
    for item in ordered:
        if item.kind == "insertion":
            points.setdefault(item.module_start, []).append(item)
    for offset, items in sorted(points.items()):
        if len(items) < 2:
            continue
        if any(item.insert_order is None for item in items):
            raise ModulePatchError(
                f"patch_conflict:insert_order_required:{items[0].module_path}:{offset}"
            )
        seen_orders: set[int] = set()
        for item in items:
            assert item.insert_order is not None
            if item.insert_order in seen_orders:
                raise ModulePatchError(
                    f"patch_conflict:insert_order_duplicate:"
                    f"{item.module_path}:{offset}:{item.insert_order}"
                )
            seen_orders.add(item.insert_order)
    claimed = [item for item in ordered if item.module_end > item.module_start]
    for item in ordered:
        if item.kind != "insertion":
            continue
        for evidence_start, evidence_end in item.evidence_spans:
            for owner in claimed:
                if evidence_start < owner.module_end and owner.module_start < evidence_end:
                    raise ModulePatchError(
                        f"patch_conflict:insert_anchor_inside_claimed_range:"
                        f"{item.package_id}:{item.op_id}:{owner.package_id}:{owner.op_id}"
                    )
```

Replace the tail of `plan_module_operations` (the `planned.sort(...)` + zip loop) with:

```python
    planned.sort(key=_render_order)
    check_planned_conflicts(planned)
    return planned
```

In `src/claude_monkey/builder_v15.py`, replace `_check_overlaps` (lines 348–357):

```python
def _check_overlaps(planned: list[PlannedModuleOperation]) -> None:
    try:
        check_planned_conflicts(planned)
    except ModulePatchError as exc:
        raise ValueError(str(exc)) from exc
```

and add `check_planned_conflicts` to the `from claude_monkey.module_patch import (...)` block at the top.

- [ ] **Step 4: Run tests to verify they pass, then hunt stale format assertions**

Run: `python3 -m pytest tests/test_module_patch.py tests/test_builder_v15.py -v`
Then: `grep -rn "patch_conflict\|overlap" tests/ --include="*.py" | grep -v test_module_patch`
Verified state of existing assertions (2026-07-04 review): `test_module_patch.py::test_plan_module_operations_rejects_overlaps` uses `match="overlap"`, which still matches `patch_conflict:range_overlap:` as a substring — **no change required**, but tighten it to `match="patch_conflict:range_overlap"` while you're in the file. `tests/test_reminders_manager.py:290` uses a loose `"patch_conflict" in report.failureReason` substring check (gated behind `local_real_smoke`) — still passes, no change. `tests/test_reference_packages.py` and `tests/test_hidden_context_drawer_package.py` contain no conflict-format assertions. If the grep surfaces anything new beyond these, update it to the structured form.

Run the full suite: `python3 -m pytest tests/ -x -q --ignore=tests/test_dvd_cursor_goblin.py`
Expected: PASS (the dvd-cursor-goblin exclusion is pre-existing unrelated red — do not fix it in this plan).

- [ ] **Step 5: Commit**

```bash
git add src/claude_monkey/module_patch.py src/claude_monkey/builder_v15.py tests/
git commit -m "feat: structured conflict validation for shared insertion points

Render order (start, end, insertOrder, packageId, opId) is now the single
sort key for validation and rendering. Conflict errors carry structured
codes so composition failures name the graph problem, not just 'overlap'."
```

---

### Task 6: Deterministic rendering + insertion evidence verification

**Files:**
- Modify: `src/claude_monkey/module_patch.py:129-137` (`render_changed_module`)
- Test: `tests/test_module_patch.py`

**Interfaces:**
- Produces: `render_changed_module` sorts by `_render_order` (not bare `module_start`). New public `verify_insertions(rendered: bytes, planned: list[PlannedModuleOperation]) -> list[dict]` returning `{"packageId", "opId", "finalOffset", "insertionVerified"}` per insertion op.
- Consumes: Task 5's `_render_order`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_module_patch.py`:

```python
from claude_monkey.module_patch import verify_insertions


def test_render_orders_same_point_insertions_by_insert_order_not_list_order():
    a = make_op(op_id="a", insert_order=300, replacement=PayloadRefV2(inline=",LAST"))
    b = make_op(op_id="b", insert_order=100, replacement=PayloadRefV2(inline=",FIRST"))
    c = make_op(op_id="c", insert_order=200, replacement=PayloadRefV2(inline=",MID"))
    planned = _plan([(a, b",LAST"), (b, b",FIRST"), (c, b",MID")])
    changed = render_changed_module(MODULE, planned)
    assert b"OLD_RENDER,FIRST,MID,LAST" in changed
    # determinism: shuffled input order produces identical bytes
    planned_shuffled = _plan([(c, b",MID"), (a, b",LAST"), (b, b",FIRST")])
    assert render_changed_module(MODULE, planned_shuffled) == changed


def test_verify_insertions_reports_final_offsets():
    a = make_op(op_id="a", insert_order=100, replacement=PayloadRefV2(inline=",FIRST"))
    b = make_op(op_id="b", insert_order=200, replacement=PayloadRefV2(inline=",SECOND"))
    planned = _plan([(a, b",FIRST"), (b, b",SECOND")])
    rendered = render_changed_module(MODULE, planned)
    results = verify_insertions(rendered, planned)
    assert len(results) == 2
    assert all(item["insertionVerified"] for item in results)
    by_op = {item["opId"]: item for item in results}
    point = MODULE.index(b"OLD_RENDER") + len(b"OLD_RENDER")
    assert by_op["a"]["finalOffset"] == point
    assert by_op["b"]["finalOffset"] == point + len(b",FIRST")


def test_verify_insertions_detects_corrupt_render():
    planned = _plan([(make_op(op_id="a"), b",ENTRY")])
    rendered = render_changed_module(MODULE, planned)
    corrupted = rendered.replace(b",ENTRY", b",WRONGX")
    results = verify_insertions(corrupted, planned)
    assert results[0]["insertionVerified"] is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_module_patch.py -v -k "render_orders or verify_insertions"`
Expected: FAIL — `ImportError: cannot import name 'verify_insertions'` (and the ordering test may fail on the old bare-`module_start` sort being unstable across input orders).

- [ ] **Step 3: Implement**

In `render_changed_module`, change the sort key:

```python
    for item in sorted(planned, key=_render_order):
```

Add:

```python
def verify_insertions(
    rendered: bytes, planned: list[PlannedModuleOperation]
) -> list[dict]:
    results: list[dict] = []
    delta = 0
    for item in sorted(planned, key=_render_order):
        final_start = item.module_start + delta
        if item.kind == "insertion":
            verified = rendered[final_start : final_start + item.new_len] == item.replacement
            results.append(
                {
                    "packageId": item.package_id,
                    "opId": item.op_id,
                    "finalOffset": final_start,
                    "insertionVerified": verified,
                }
            )
        delta += item.delta
    return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_module_patch.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/claude_monkey/module_patch.py tests/test_module_patch.py
git commit -m "feat: render by normalized order and verify insertion evidence"
```

---

### Task 7: Builder integration — evidence gate, report fields, composition-sensitive postconditions

**Files:**
- Modify: `src/claude_monkey/builder_v15.py` (imports; the render loop at lines 533–538; `operationsApplied` at lines 556–571; new check after the planning loop)
- Test: `tests/test_builder_v15.py`

**Interfaces:**
- Produces: build fails with `insertion_evidence_failed:<pkg>:<op>` if any insertion's bytes are absent at the planned final offset (internal invariant — should never fire, checked anyway, fail-closed). `operationsApplied` entries gain `"type"`, `"kind"`, `"insertOrder"`, `"anchor"`, `"seamHint"`, `"contextStart"`, `"contextEnd"`, and for insertions `"finalOffset"`, `"insertionVerified"`. Build fails with `postcondition_composition_sensitive:<pkg>:<value-prefix>` when a postcondition value contains an anchor of a **shared** insertion point (2+ insertions at one offset).
- Consumes: Task 6's `verify_insertions`, Task 3's planned-op fields.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_builder_v15.py`. First add an insertion-package writer beside `write_fixture_package` (note it reuses that function's manifest shape — copy, don't import-and-mutate):

```python
def write_insertion_package(
    package: Path,
    binary: Path,
    *,
    package_id: str,
    payload: str,
    insert_order: int,
    postcondition_value: str,
) -> None:
    manifest = {
        "schemaVersion": 2,
        "id": package_id,
        "name": package_id,
        "description": "Insertion fixture",
        "packageVersion": "0.1.0",
        "targets": [
            {
                "sourceIdentity": {
                    "claudeVersion": "fixture",
                    "versionOutput": "fixture (Claude Code)",
                    "sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                    "sizeBytes": binary.stat().st_size,
                    "platform": "darwin",
                    "arch": "arm64",
                },
                "requiredEngine": "bun_graph_repack",
                "requiredBinaryFormat": "bun_standalone_macho64",
                "modules": [
                    {
                        "path": "/$bunfs/root/src/entrypoints/cli.js",
                        "contentSha256": hashlib.sha256(MODULE_0).hexdigest(),
                        "contentLength": len(MODULE_0),
                        "operations": [
                            {
                                "opId": f"{package_id}-insert",
                                "label": "Insert entry",
                                "type": "insert_after",
                                "anchor": "OLD_RENDER",
                                "insertOrder": insert_order,
                                "seamHint": "fixture.afterOldRender",
                                "replacement": {"inline": payload},
                            }
                        ],
                    }
                ],
                "postconditions": [
                    {
                        "type": "module_must_contain",
                        "modulePath": "/$bunfs/root/src/entrypoints/cli.js",
                        "value": postcondition_value,
                    }
                ],
            }
        ],
    }
    package.mkdir()
    (package / "patch.json").write_text(json.dumps(manifest))


def _build(tmp_path, source, package_dirs):
    return build_patchset_v15(
        BuildRequestV15(
            source_path=source,
            output_dir=tmp_path / "out",
            package_dirs=package_dirs,
            source_version="fixture",
            source_version_output="fixture (Claude Code)",
            platform="darwin",
            arch="arm64",
            command_runner=successful_runner,
        )
    )


def test_insertion_build_reports_evidence_and_extended_fields(tmp_path):
    source = tmp_path / "claude-source"
    source.write_bytes(build_aligned_macho_fixture()[0])
    pkg = tmp_path / "pkg-a"
    write_insertion_package(
        pkg, source, package_id="pkg-a", payload=",A_ENTRY",
        insert_order=100, postcondition_value="A_ENTRY",
    )
    report = _build(tmp_path, source, [pkg])
    assert report.automatedStatus == "passed"
    applied = report.operationsApplied[0]
    assert applied["type"] == "insert_after"
    assert applied["kind"] == "insertion"
    assert applied["insertOrder"] == 100
    assert applied["anchor"] == "OLD_RENDER"
    assert applied["seamHint"] == "fixture.afterOldRender"
    assert applied["insertionVerified"] is True
    assert applied["oldLen"] == 0
    assert applied["moduleStart"] == applied["moduleEnd"]
    assert isinstance(applied["finalOffset"], int)


def test_composition_sensitive_postcondition_fails_build(tmp_path):
    source = tmp_path / "claude-source"
    source.write_bytes(build_aligned_macho_fixture()[0])
    pkg_a = tmp_path / "pkg-a"
    pkg_b = tmp_path / "pkg-b"
    write_insertion_package(
        pkg_a, source, package_id="pkg-a", payload=",A_ENTRY",
        insert_order=100,
        postcondition_value="OLD_RENDER,A_ENTRY",  # asserts adjacency across a SHARED point
    )
    write_insertion_package(
        pkg_b, source, package_id="pkg-b", payload=",B_ENTRY",
        insert_order=200, postcondition_value="B_ENTRY",
    )
    report = _build(tmp_path, source, [pkg_a, pkg_b])
    assert report.status == "failed"
    assert report.failureReason.startswith("postcondition_composition_sensitive:pkg-a")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_builder_v15.py -v -k "insertion_build or composition_sensitive"`
Expected: first test FAILs on missing `"type"`/`"kind"` keys in `operationsApplied`; second FAILs because the build passes (adjacency happens to hold in 100/200 order) instead of failing closed.

- [ ] **Step 3: Implement**

In `src/claude_monkey/builder_v15.py`:

Add `verify_insertions` to the `module_patch` import block.

Replace the render loop (lines 533–538) with:

```python
        changed_modules: dict[str, bytes] = {}
        insertion_evidence: dict[tuple[str, str], dict[str, Any]] = {}
        for module_path, planned in planned_by_module.items():
            changed_modules[module_path] = render_changed_module(
                original_modules[module_path], planned
            )
            for evidence in verify_insertions(changed_modules[module_path], planned):
                if not evidence["insertionVerified"]:
                    raise ValueError(
                        f"insertion_evidence_failed:{evidence['packageId']}:{evidence['opId']}"
                    )
                insertion_evidence[(evidence["packageId"], evidence["opId"])] = evidence
```

Immediately before that block (after the planning loop, before rendering), add the structural conflict pre-pass and then the composition-sensitivity check — the pre-pass MUST run first so a fundamental conflict (e.g. `insert_order_duplicate`) is never masked by the postcondition heuristic:

```python
        for planned in planned_by_module.values():
            _check_overlaps(planned)
        shared_anchors: set[str] = set()
        for planned in planned_by_module.values():
            insertion_points: dict[int, list[PlannedModuleOperation]] = {}
            for item in planned:
                if item.kind == "insertion":
                    insertion_points.setdefault(item.module_start, []).append(item)
            for items in insertion_points.values():
                if len(items) > 1:
                    shared_anchors.update(item.anchor for item in items if item.anchor)
        if shared_anchors:
            for _, manifest, target in selected:
                for assertion in target.postconditions:
                    if any(anchor in assertion.value for anchor in shared_anchors):
                        raise ValueError(
                            "postcondition_composition_sensitive:"
                            f"{manifest.id}:{assertion.value[:60]}"
                        )
```

Extend the `operationsApplied` construction (lines 556–571):

```python
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
                "type": item.op_type,
                "kind": item.kind,
                "insertOrder": item.insert_order,
                "anchor": item.anchor,
                "seamHint": item.seam_hint,
                "contextStart": item.context_start,
                "contextEnd": item.context_end,
                **insertion_evidence.get((item.package_id, item.op_id), {}),
            }
            for planned in planned_by_module.values()
            for item in planned
        ]
```

(The `**insertion_evidence.get(...)` spread re-adds `packageId`/`opId` with identical values — harmless — plus `finalOffset` and `insertionVerified` for insertions.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_builder_v15.py -v`
Expected: all PASS (pre-existing builder tests confirm replacement-only builds are untouched — their `operationsApplied` entries just gain the new keys with `"type": "replace_between"`, `"kind": "replacement"`, `None` splice fields; if any pre-existing test asserts exact dict equality on `operationsApplied`, update it to subset assertions).

- [ ] **Step 5: Commit**

```bash
git add src/claude_monkey/builder_v15.py tests/test_builder_v15.py
git commit -m "feat: insertion evidence gate and structured splice build reports"
```

---

### Task 8: Phase 2 — relationship metadata parsing

**Files:**
- Modify: `src/claude_monkey/manifest_v2.py` (`ManifestV2` dataclass, `load_manifest_v2_dict`)
- Test: `tests/test_manifest_v2.py`

**Interfaces:**
- Produces: `ManifestV2` gains `requires_packages: tuple[str, ...] = ()` and `conflicts_with_packages: tuple[str, ...] = ()`, parsed from optional top-level `requiresPackages` / `conflictsWithPackages` string lists.
- Consumes: nothing new.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_manifest_v2.py`:

```python
def test_relationship_metadata_parses():
    data = _manifest_with_op(_insert_op())
    data["requiresPackages"] = ["footer-drawers"]
    data["conflictsWithPackages"] = ["upstream-attachment-suppression"]
    manifest = load_manifest_v2_dict(data)
    assert manifest.requires_packages == ("footer-drawers",)
    assert manifest.conflicts_with_packages == ("upstream-attachment-suppression",)


def test_relationship_metadata_defaults_empty():
    manifest = load_manifest_v2_dict(_manifest_with_op(_insert_op()))
    assert manifest.requires_packages == ()
    assert manifest.conflicts_with_packages == ()


def test_relationship_metadata_rejects_non_string_list():
    data = _manifest_with_op(_insert_op())
    data["requiresPackages"] = "footer-drawers"
    with pytest.raises(ManifestV2Error, match="requiresPackages"):
        load_manifest_v2_dict(data)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_manifest_v2.py -v -k "relationship"`
Expected: FAIL — `AttributeError: 'ManifestV2' object has no attribute 'requires_packages'`.

- [ ] **Step 3: Implement**

In `src/claude_monkey/manifest_v2.py`:

Add a helper near the other parse helpers:

```python
def optional_string_list(obj: dict[str, Any], field: str) -> tuple[str, ...]:
    value = obj.get(field, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ManifestV2Error(f"{field} must be a list of strings")
    return tuple(value)
```

Extend `ManifestV2` (after `raw: dict[str, Any]`):

```python
    requires_packages: tuple[str, ...] = ()
    conflicts_with_packages: tuple[str, ...] = ()
```

In `load_manifest_v2_dict`'s final construction:

```python
    return ManifestV2(
        schema_version=2,
        id=require_string(top, "id"),
        name=require_string(top, "name"),
        description=require_string(top, "description"),
        package_version=require_string(top, "packageVersion"),
        targets=parsed_targets,
        raw=data,
        requires_packages=optional_string_list(top, "requiresPackages"),
        conflicts_with_packages=optional_string_list(top, "conflictsWithPackages"),
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_manifest_v2.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/claude_monkey/manifest_v2.py tests/test_manifest_v2.py
git commit -m "feat: parse requiresPackages/conflictsWithPackages metadata"
```

---

### Task 9: Phase 2 — builder relationship validation

**Files:**
- Modify: `src/claude_monkey/builder_v15.py` (top of the `try` block in `build_patchset_v15`, before `find_macho_layout`)
- Test: `tests/test_builder_v15.py`

**Interfaces:**
- Produces: builds fail before any byte planning with `patch_conflict:required_package_missing:<pkg>:<required>` or `patch_conflict:package_conflict:<pkgA>:<pkgB>`. Byte-overlap checking is unchanged and remains the final safety net.
- Consumes: Task 8's `ManifestV2` fields.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_builder_v15.py` (uses `write_insertion_package` + `_build` from Task 7; the relationship writer patches the manifest dict after writing):

```python
def _add_relationships(package: Path, *, requires=None, conflicts=None) -> None:
    manifest = json.loads((package / "patch.json").read_text())
    if requires is not None:
        manifest["requiresPackages"] = requires
    if conflicts is not None:
        manifest["conflictsWithPackages"] = conflicts
    (package / "patch.json").write_text(json.dumps(manifest))


def test_required_package_missing_fails_before_planning(tmp_path):
    source = tmp_path / "claude-source"
    source.write_bytes(build_aligned_macho_fixture()[0])
    pkg = tmp_path / "pkg-a"
    write_insertion_package(
        pkg, source, package_id="pkg-a", payload=",A_ENTRY",
        insert_order=100, postcondition_value="A_ENTRY",
    )
    _add_relationships(pkg, requires=["footer-drawers"])
    report = _build(tmp_path, source, [pkg])
    assert report.status == "failed"
    assert report.failureReason == "patch_conflict:required_package_missing:pkg-a:footer-drawers"


def test_package_conflict_fails_before_planning(tmp_path):
    source = tmp_path / "claude-source"
    source.write_bytes(build_aligned_macho_fixture()[0])
    pkg_a = tmp_path / "pkg-a"
    pkg_b = tmp_path / "pkg-b"
    write_insertion_package(
        pkg_a, source, package_id="pkg-a", payload=",A_ENTRY",
        insert_order=100, postcondition_value="A_ENTRY",
    )
    write_insertion_package(
        pkg_b, source, package_id="pkg-b", payload=",B_ENTRY",
        insert_order=200, postcondition_value="B_ENTRY",
    )
    _add_relationships(pkg_a, conflicts=["pkg-b"])
    report = _build(tmp_path, source, [pkg_a, pkg_b])
    assert report.status == "failed"
    assert report.failureReason == "patch_conflict:package_conflict:pkg-a:pkg-b"


def test_requirements_satisfied_build_passes(tmp_path):
    source = tmp_path / "claude-source"
    source.write_bytes(build_aligned_macho_fixture()[0])
    pkg_a = tmp_path / "pkg-a"
    pkg_b = tmp_path / "pkg-b"
    write_insertion_package(
        pkg_a, source, package_id="pkg-a", payload=",A_ENTRY",
        insert_order=100, postcondition_value="A_ENTRY",
    )
    write_insertion_package(
        pkg_b, source, package_id="pkg-b", payload=",B_ENTRY",
        insert_order=200, postcondition_value="B_ENTRY",
    )
    _add_relationships(pkg_a, requires=["pkg-b"])
    report = _build(tmp_path, source, [pkg_a, pkg_b])
    assert report.automatedStatus == "passed"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_builder_v15.py -v -k "required_package or package_conflict or requirements_satisfied"`
Expected: the two failure tests FAIL (builds pass — relationships ignored); the satisfied test PASSes trivially.

- [ ] **Step 3: Implement**

In `build_patchset_v15`, at the very top of the `try:` block (before `layout = find_macho_layout(source)`):

```python
        enabled_ids = {manifest.id for _, manifest, _ in selected}
        for _, manifest, _ in selected:
            for required in sorted(manifest.requires_packages):
                if required not in enabled_ids:
                    raise ValueError(
                        f"patch_conflict:required_package_missing:{manifest.id}:{required}"
                    )
            for conflict in sorted(manifest.conflicts_with_packages):
                if conflict in enabled_ids:
                    raise ValueError(
                        f"patch_conflict:package_conflict:{manifest.id}:{conflict}"
                    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_builder_v15.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/claude_monkey/builder_v15.py tests/test_builder_v15.py
git commit -m "feat: validate package relationships before operation planning"
```

---

### Task 10: Phase 2 — envelope/bridge support for relationship metadata

**Files:**
- Modify: `src/claude_monkey/package_model.py` (line 21 `TOP_LEVEL_FIELDS`, `PackageManifest`, `load_package_manifest_from_dict`)
- Modify: `src/claude_monkey/builder_v15.py:72-83` (`_v3_manifest_as_v2_dict`)
- Test: `tests/test_package_model_v3.py`

**Interfaces:**
- Produces: schema-1 envelope manifests (kind=patch) may declare `requiresPackages`/`conflictsWithPackages` at top level; `PackageManifest` gains `requires_packages: tuple[str, ...] = ()` / `conflicts_with_packages: tuple[str, ...] = ()`; the V2 bridge dict carries them through so `load_manifest_v2` exposes them identically for both manifest surfaces.
- Consumes: Task 8's `ManifestV2` parsing (the bridge output goes through `load_manifest_v2_dict`).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_package_model_v3.py` (check the file's existing fixture helper for a valid kind=patch envelope dict and reuse its shape — the test below writes the minimal form inline; adapt field values to whatever the existing tests use for a passing patch envelope):

```python
def test_envelope_relationship_metadata_parses(tmp_path):
    package_dir = tmp_path / "thin-drawer"
    package_dir.mkdir()
    manifest = {
        "schemaVersion": 1,
        "kind": "patch",
        "id": "thin-drawer",
        "label": "Thin drawer",
        "description": "Fixture",
        "requiresPackages": ["footer-drawers"],
        "conflictsWithPackages": ["old-drawer"],
        "patch": {"engine": "bun_graph_repack", "targets": [{}]},
    }
    (package_dir / "package.json").write_text(json.dumps(manifest))
    loaded = load_package_manifest(package_dir, PackageKind.PATCH)
    assert loaded.requires_packages == ("footer-drawers",)
    assert loaded.conflicts_with_packages == ("old-drawer",)


def test_envelope_relationship_metadata_defaults_empty(tmp_path):
    package_dir = tmp_path / "plain"
    package_dir.mkdir()
    manifest = {
        "schemaVersion": 1,
        "kind": "patch",
        "id": "plain",
        "label": "Plain",
        "description": "Fixture",
        "patch": {"engine": "bun_graph_repack", "targets": [{}]},
    }
    (package_dir / "package.json").write_text(json.dumps(manifest))
    loaded = load_package_manifest(package_dir, PackageKind.PATCH)
    assert loaded.requires_packages == ()
    assert loaded.conflicts_with_packages == ()
```

And a bridge test in `tests/test_builder_v15.py`:

```python
def test_v3_bridge_carries_relationship_metadata(tmp_path):
    from claude_monkey.builder_v15 import _v3_manifest_as_v2_dict

    package_dir = tmp_path / "thin-drawer"
    package_dir.mkdir()
    manifest = {
        "schemaVersion": 1,
        "kind": "patch",
        "id": "thin-drawer",
        "label": "Thin drawer",
        "description": "Fixture",
        "requiresPackages": ["footer-drawers"],
        "patch": {"engine": "bun_graph_repack", "targets": [{}]},
    }
    (package_dir / "package.json").write_text(json.dumps(manifest))
    bridged = _v3_manifest_as_v2_dict(package_dir)
    assert bridged["requiresPackages"] == ["footer-drawers"]
    assert bridged["conflictsWithPackages"] == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_package_model_v3.py tests/test_builder_v15.py -v -k "relationship or bridge"`
Expected: FAIL — `unknown_top_level_field:conflictsWithPackages` (the envelope parser's allowlist rejects the field).

- [ ] **Step 3: Implement**

In `src/claude_monkey/package_model.py`:

Add to `TOP_LEVEL_FIELDS` (line 21 block):

```python
    "requiresPackages",
    "conflictsWithPackages",
```

Extend `PackageManifest` (after `raw: dict[str, Any]`):

```python
    requires_packages: tuple[str, ...] = ()
    conflicts_with_packages: tuple[str, ...] = ()
```

In `load_package_manifest_from_dict`'s final construction, add:

```python
        requires_packages=_require_string_list(top, "requiresPackages"),
        conflicts_with_packages=_require_string_list(top, "conflictsWithPackages"),
```

(`_require_string_list` already defaults to `()` for missing fields via `obj.get(field, [])`.)

In `src/claude_monkey/builder_v15.py`, `_v3_manifest_as_v2_dict`:

```python
    return {
        "schemaVersion": 2,
        "id": manifest.id,
        "name": manifest.label,
        "description": manifest.description,
        "packageVersion": "0.0.0",
        "targets": list(manifest.patch.targets),
        "requiresPackages": list(manifest.requires_packages),
        "conflictsWithPackages": list(manifest.conflicts_with_packages),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_package_model_v3.py tests/test_builder_v15.py tests/test_cli_v3_packages.py -v`
Expected: all PASS (the cli_v3 file exercises envelope discovery — run it to confirm the allowlist change breaks nothing).

- [ ] **Step 5: Commit**

```bash
git add src/claude_monkey/package_model.py src/claude_monkey/builder_v15.py tests/
git commit -m "feat: bridge relationship metadata through envelope manifests"
```

---

### Task 11: Cross-package collision proof (the fixture pair from the spec)

**Files:**
- Create: `tests/test_structured_splices.py`

**Interfaces:**
- Consumes: everything above. This is the spec's "Package/reference tests" requirement: two packages inserting at the same footer-like anchor, deterministic merged order, proven end-to-end through `build_patchset_v15` including output-binary content.

- [ ] **Step 1: Write the failing test** (fails only if earlier tasks are broken — this is the integration proof, written red-green against the full pipeline)

Create `tests/test_structured_splices.py`:

```python
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tests.fixtures_bun import MODULE_0, build_aligned_macho_fixture

from claude_monkey.builder_v15 import BuildRequestV15, build_patchset_v15
from claude_monkey.bun_graph import parse_bun_section
from claude_monkey.macho import find_macho_layout
from claude_monkey.smoke import CommandResult

MODULE_PATH = "/$bunfs/root/src/entrypoints/cli.js"


def runner(argv):
    if argv[0] == "codesign" and "--verify" in argv:
        return CommandResult(argv=argv, returncode=0, stdout="", stderr="valid")
    if argv[0] == "codesign":
        return CommandResult(argv=argv, returncode=0, stdout="", stderr="signed")
    if argv[-1] == "--version":
        return CommandResult(argv=argv, returncode=0, stdout="fixture (Claude Code)\n", stderr="")
    if argv[-1] == "--help":
        return CommandResult(
            argv=argv, returncode=0, stdout="Usage: claude [options]\nClaude Code help\n", stderr=""
        )
    return CommandResult(argv=argv, returncode=1, stdout="", stderr="unexpected")


def write_package(package: Path, binary: Path, package_id: str, payload: str, order: int) -> None:
    manifest = {
        "schemaVersion": 2,
        "id": package_id,
        "name": package_id,
        "description": "Shared-anchor insertion fixture",
        "packageVersion": "0.1.0",
        "targets": [
            {
                "sourceIdentity": {
                    "claudeVersion": "fixture",
                    "versionOutput": "fixture (Claude Code)",
                    "sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                    "sizeBytes": binary.stat().st_size,
                    "platform": "darwin",
                    "arch": "arm64",
                },
                "requiredEngine": "bun_graph_repack",
                "requiredBinaryFormat": "bun_standalone_macho64",
                "modules": [
                    {
                        "path": MODULE_PATH,
                        "contentSha256": hashlib.sha256(MODULE_0).hexdigest(),
                        "contentLength": len(MODULE_0),
                        "operations": [
                            {
                                "opId": f"{package_id}-insert",
                                "label": "Insert entry",
                                "type": "insert_after",
                                "anchor": "OLD_RENDER",
                                "insertOrder": order,
                                "replacement": {"inline": payload},
                            }
                        ],
                    }
                ],
                "postconditions": [
                    {
                        "type": "module_must_contain",
                        "modulePath": MODULE_PATH,
                        "value": payload,
                    }
                ],
            }
        ],
    }
    package.mkdir()
    (package / "patch.json").write_text(json.dumps(manifest))


def build(tmp_path: Path, source: Path, package_dirs: list[Path], out: str):
    return build_patchset_v15(
        BuildRequestV15(
            source_path=source,
            output_dir=tmp_path / out,
            package_dirs=package_dirs,
            source_version="fixture",
            source_version_output="fixture (Claude Code)",
            platform="darwin",
            arch="arm64",
            command_runner=runner,
        )
    )


def output_module(report) -> bytes:
    data = Path(report.outputPath).read_bytes()
    layout = find_macho_layout(data)
    graph = parse_bun_section(
        data[layout.bun_section.offset : layout.bun_section.offset + layout.bun_section.size]
    )
    return graph.module_by_path(MODULE_PATH).content


def test_two_packages_share_one_anchor_deterministically(tmp_path):
    source = tmp_path / "claude-source"
    source.write_bytes(build_aligned_macho_fixture()[0])
    pkg_a = tmp_path / "pkg-a"
    pkg_b = tmp_path / "pkg-b"
    write_package(pkg_a, source, "pkg-a", ",A_ENTRY", 100)
    write_package(pkg_b, source, "pkg-b", ",B_ENTRY", 200)

    report = build(tmp_path, source, [pkg_a, pkg_b], "out-ab")
    assert report.automatedStatus == "passed"
    module = output_module(report)
    assert b"OLD_RENDER,A_ENTRY,B_ENTRY" in module

    # determinism: reversed --package order produces identical module bytes
    report_ba = build(tmp_path, source, [pkg_b, pkg_a], "out-ba")
    assert report_ba.automatedStatus == "passed"
    assert output_module(report_ba) == module


def test_duplicate_insert_order_across_packages_fails_closed(tmp_path):
    source = tmp_path / "claude-source"
    source.write_bytes(build_aligned_macho_fixture()[0])
    pkg_a = tmp_path / "pkg-a"
    pkg_b = tmp_path / "pkg-b"
    write_package(pkg_a, source, "pkg-a", ",A_ENTRY", 100)
    write_package(pkg_b, source, "pkg-b", ",B_ENTRY", 100)
    report = build(tmp_path, source, [pkg_a, pkg_b], "out")
    assert report.status == "failed"
    assert report.failureReason.startswith("patch_conflict:insert_order_duplicate")


def test_insertion_composes_with_disjoint_replacement_package(tmp_path):
    source = tmp_path / "claude-source"
    source.write_bytes(build_aligned_macho_fixture()[0])
    pkg_a = tmp_path / "pkg-a"
    write_package(pkg_a, source, "pkg-a", ",A_ENTRY", 100)
    # replacement package owning a disjoint span ("return 1")
    pkg_c = tmp_path / "pkg-c"
    manifest = json.loads((pkg_a / "patch.json").read_text())
    manifest["id"] = "pkg-c"
    manifest["name"] = "pkg-c"
    manifest["targets"][0]["modules"][0]["operations"] = [
        {
            "opId": "pkg-c-replace",
            "label": "Replace return",
            "type": "replace_exact",
            "exact": "return 1",
            "replacement": {"inline": "return 2"},
        }
    ]
    manifest["targets"][0]["postconditions"] = [
        {"type": "module_must_contain", "modulePath": MODULE_PATH, "value": "return 2"}
    ]
    pkg_c.mkdir()
    (pkg_c / "patch.json").write_text(json.dumps(manifest))

    report = build(tmp_path, source, [pkg_a, pkg_c], "out")
    assert report.automatedStatus == "passed"
    module = output_module(report)
    assert b"OLD_RENDER,A_ENTRY" in module
    assert b"return 2" in module
```

- [ ] **Step 2: Run the tests**

Run: `python3 -m pytest tests/test_structured_splices.py -v`
Expected: all PASS if Tasks 1–9 are correct. Any failure here is a real integration bug in an earlier task — fix it there (with a unit test in that task's file), not here.

- [ ] **Step 3: Commit**

```bash
git add tests/test_structured_splices.py
git commit -m "test: prove cross-package shared-anchor insertion composition"
```

---

### Task 12: Authoring documentation + full-suite verification

**Files:**
- Create: `docs/manifest-v2-operations.md`
- Modify: `docs/superpowers/specs/2026-07-03-composition-engine-structured-splices-design.md` (status line only)

**Interfaces:** none (docs).

- [ ] **Step 1: Write the reference doc**

Create `docs/manifest-v2-operations.md`:

```markdown
# Manifest schema-v2 operation reference

Operation types accepted in `patch.json` `targets[].modules[].operations[]`.
All ops resolve against ORIGINAL stock module bytes; rendering is one pass
sorted by `(moduleStart, moduleEnd, insertOrder, packageId, opId)`.

## replace_exact
Claims the byte range of a unique `exact` substring; replaces it whole.
Fields: `exact` (must occur exactly once), `requireWithinRange`,
`oldRangeSha256`, `oldRangeLength`, `replacement`.

## replace_between
Claims start-of-`startMarker` → start-of-`endMarker` (endMarker excluded).
Fields: `startMarker`, `endMarker`, `expectedStartMarkerCount`,
`expectedEndMarkerCount`, plus the evidence fields above.

## insert_before / insert_after
Claims a ZERO-WIDTH point at the start (insert_before) or end (insert_after)
of a unique `anchor`. Multiple packages may target the same point when each
supplies a distinct `insertOrder`; the merged bytes render in ascending order.
- `anchor` (required, must resolve exactly once in scope)
- `insertOrder` (required when the point is shared; omit for sole inserts)
- optional `startMarker`+`endMarker` context: anchor uniqueness is evaluated
  inside the context span (start of startMarker → END of endMarker)
- `seamHint` (informational, surfaces in build reports)
- old-range evidence fields are REJECTED (the claimed range is empty)
- anchor and context-marker bytes must be disjoint from every claimed
  replacement range in the build (fail-closed)
- POSTCONDITIONS: assert your own payload marker only. Never assert
  anchor+payload adjacency — a sibling package's insertion at the same
  point makes it order-dependent, and the builder fails such postconditions
  as `postcondition_composition_sensitive`.

## replace_substring_within
Resolves an outer context via `startMarker`/`endMarker`, then claims and
replaces only the unique `subExact` inside it. Use for editing one owned
clause without restating siblings. For additive clauses that other packages
may also extend, prefer insert_before/insert_after.
- `subExact` (must occur exactly once inside the context)
- `oldRangeSha256`/`oldRangeLength` apply to the claimed subspan
- `contextSha256` (optional): hard-fail hash of the full context span

## Package relationships (top level, both manifest surfaces)
- `requiresPackages`: build fails with
  `patch_conflict:required_package_missing:<pkg>:<required>` unless every
  named package is enabled in the same build.
- `conflictsWithPackages`: build fails with
  `patch_conflict:package_conflict:<pkgA>:<pkgB>` when both are enabled.
Relationship checks run before byte planning; byte-overlap checking remains
the final safety net and is never overridden by metadata.

## Conflict codes
- `patch_conflict:range_overlap:<pkgA>:<opA>:<pkgB>:<opB>`
- `patch_conflict:insert_inside_claimed_range:<pkgA>:<opA>:<pkgB>:<opB>`
- `patch_conflict:insert_order_required:<modulePath>:<offset>`
- `patch_conflict:insert_order_duplicate:<modulePath>:<offset>:<order>`
- `patch_conflict:insert_anchor_inside_claimed_range:<insertPkg>:<insertOp>:<ownerPkg>:<ownerOp>`
- `patch_conflict:required_package_missing:<pkg>:<required>`
- `patch_conflict:package_conflict:<pkgA>:<pkgB>`
```

- [ ] **Step 2: Update the spec status line**

In `docs/superpowers/specs/2026-07-03-composition-engine-structured-splices-design.md`, change `**Status:** Draft for user review.` to `**Status:** Implemented (Phases 1–2) — see docs/superpowers/plans/2026-07-04-composition-engine-structured-splices.md and docs/manifest-v2-operations.md.` (keep the amendment sentence that follows).

- [ ] **Step 3: Run the full suite**

Run: `python3 -m pytest tests/ -q --ignore=tests/test_dvd_cursor_goblin.py`
Expected: PASS. Also verify the shipping packages still validate end-to-end:
`python3 -m pytest tests/test_reminders_manager.py tests/test_hidden_context_drawer_package.py tests/test_reference_packages.py -v`
Expected: PASS (these prove existing replacement-only packages build unchanged through the new code paths).

- [ ] **Step 4: Commit**

```bash
git add docs/manifest-v2-operations.md docs/superpowers/specs/2026-07-03-composition-engine-structured-splices-design.md
git commit -m "docs: manifest v2 structured splice operation reference"
```

---

## Out-of-scope reminders for the implementer

- Do NOT touch `bun_graph.py`, `macho.py`, `repack.py` — the container layer has no composition concerns.
- Do NOT implement retarget diagnostics, helper ops, or named seams.
- Do NOT migrate any real package (`hidden-context-drawer`, `reminders-manager`, `upstream-attachment-suppression`) — that is the footer-drawers framework's job (`docs/superpowers/specs/2026-07-03-footer-drawers-framework-design.md`), which starts only after this plan is complete.
- `tests/test_dvd_cursor_goblin.py` is pre-existing unrelated red — leave it alone.
```
