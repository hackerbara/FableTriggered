# Structured Splice Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Python-only structured splice foundation for ClaudeMonkey: zero-width insertions, context-bounded subspan planning, deterministic render order, retarget diagnostics, and package relationship metadata while preserving V1.5 Bun graph repack safety.

**Architecture:** Keep binary-container mechanics unchanged: `bun_graph.py`, `macho.py`, and `repack.py` continue to handle existing-module repack and Mach-O metadata. Extend `manifest_v2.py` to parse additive operation metadata, extend `module_patch.py` to resolve structured splices into byte-preserving planned operations, and extend `builder_v15.py` to validate operation/package graphs, report richer operation evidence, and expose diagnostic-only retarget information. Package relationship fields remain explicit metadata and never override byte-level safety.

**Tech Stack:** Python 3.11+, stdlib dataclasses, pytest, current synthetic Bun/Mach-O fixtures, existing ClaudeMonkey schema-v2 package format, existing V1.5 `bun_graph_repack` builder.

---

## Scope

This plan implements the engine foundation from `/Users/MAC/Documents/Claude-patch/docs/superpowers/specs/2026-07-03-composition-engine-structured-splices-design.md`.

In scope:

- `insert_before` / `insert_after` operations, including optional context bounds.
- `replace_substring_within` operation.
- Planned operation metadata: `kind`, context range, insertion order, seam evidence, render order.
- Deterministic same-offset rendering.
- Structured conflict codes for overlaps and insertion-order conflicts.
- Extended `operationsApplied` / `operationsResolved` evidence.
- Explicit report schema compatibility: keep `BuildReportV2.schemaVersion == 3` and treat operation-entry fields as additive while preserving existing keys.
- Diagnostic-only retarget analysis for `validate-package --json` on identity mismatch.
- Top-level package relationship metadata and bridge support for package-envelope manifests.
- Tests for the above.

Out of scope for this plan:

- Real package migrations for `hidden-context-drawer` or `reminders-manager`.
- Named seam registry.
- JavaScript AST parser or whole-module reprint.
- Patch-owned Bun modules.
- Runtime trampolines or appended payloads.

## File structure

Modify:

- `/Users/MAC/Documents/Claude-patch/src/claude_monkey/manifest_v2.py`
  - Parse new operation fields and top-level package relationship fields.
- `/Users/MAC/Documents/Claude-patch/src/claude_monkey/module_patch.py`
  - Resolve structured operation ranges, validate context/claimed ranges, enforce deterministic render order, expose diagnostics helpers.
- `/Users/MAC/Documents/Claude-patch/src/claude_monkey/builder_v15.py`
  - Validate package relationships, preserve cross-package operation graph safety, serialize richer operation evidence, add diagnostic-only target selection.
- `/Users/MAC/Documents/Claude-patch/src/claude_monkey/package_model.py`
  - Allow package relationship fields in schema-v1 package-envelope manifests and carry them into `PatchPackage`.

Test:

- `/Users/MAC/Documents/Claude-patch/tests/test_manifest_v2.py`
- `/Users/MAC/Documents/Claude-patch/tests/test_module_patch.py`
- `/Users/MAC/Documents/Claude-patch/tests/test_builder_v15.py`
- `/Users/MAC/Documents/Claude-patch/tests/test_cli_v15.py`
- `/Users/MAC/Documents/Claude-patch/tests/test_package_model_v3.py`

Do not modify in this plan:

- `/Users/MAC/Documents/Claude-patch/src/claude_monkey/bun_graph.py`
- `/Users/MAC/Documents/Claude-patch/src/claude_monkey/macho.py`
- `/Users/MAC/Documents/Claude-patch/src/claude_monkey/repack.py`
- package payloads under `/Users/MAC/Documents/Claude-patch/packages/`

## Task 1: Extend manifest-v2 operation schema

**Files:**
- Modify: `/Users/MAC/Documents/Claude-patch/tests/test_manifest_v2.py`
- Modify: `/Users/MAC/Documents/Claude-patch/tests/test_module_patch.py`
- Modify: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/manifest_v2.py`

- [ ] **Step 1: Add failing manifest tests for structured operations**

Append these tests to `/Users/MAC/Documents/Claude-patch/tests/test_manifest_v2.py`:

```python

def test_manifest_v2_accepts_insert_operation_fields():
    data = valid_v2_manifest()
    op = data["targets"][0]["modules"][0]["operations"][0]
    op.clear()
    op.update(
        {
            "opId": "insert-footer-target",
            "label": "Insert footer target",
            "type": "insert_after",
            "anchor": "Oe&&\"frame\"",
            "expectedAnchorCount": 1,
            "insertOrder": 200,
            "startMarker": "ji=Ro.useMemo",
            "endMarker": "].filter(Boolean)",
            "contextSha256": "d" * 64,
            "seamHint": "footer.targets.afterFrame",
            "replacement": {"inline": ",\"reminders\""},
        }
    )

    manifest = load_manifest_v2_dict(data)
    parsed = manifest.targets[0].modules[0].operations[0]

    assert parsed.type == "insert_after"
    assert parsed.anchor == "Oe&&\"frame\""
    assert parsed.expected_anchor_count == 1
    assert parsed.insert_order == 200
    assert parsed.context_sha256 == "d" * 64
    assert parsed.seam_hint == "footer.targets.afterFrame"


def test_manifest_v2_accepts_replace_substring_within_fields():
    data = valid_v2_manifest()
    op = data["targets"][0]["modules"][0]["operations"][0]
    op.clear()
    op.update(
        {
            "opId": "replace-frame-flag-subspan",
            "label": "Replace frame flag subspan",
            "type": "replace_substring_within",
            "startMarker": "let qb=Du===\"tasks\"",
            "endMarker": ";function Sf",
            "subExact": "Ap=Du===\"frame\"",
            "expectedStartMarkerCount": 1,
            "expectedEndMarkerCount": 1,
            "expectedSubExactCount": 1,
            "oldRangeSha256": "e" * 64,
            "oldRangeLength": 15,
            "replacement": {"inline": "Ap=Du===\"frame\",hC=Du===\"hiddenContext\""},
        }
    )

    manifest = load_manifest_v2_dict(data)
    parsed = manifest.targets[0].modules[0].operations[0]

    assert parsed.type == "replace_substring_within"
    assert parsed.sub_exact == "Ap=Du===\"frame\""
    assert parsed.expected_sub_exact_count == 1


def test_manifest_v2_rejects_insert_without_insert_order():
    data = valid_v2_manifest()
    op = data["targets"][0]["modules"][0]["operations"][0]
    op.clear()
    op.update(
        {
            "opId": "insert-without-order",
            "label": "Insert without order",
            "type": "insert_after",
            "anchor": "OLD_RENDER",
            "replacement": {"inline": "NEW"},
        }
    )

    with pytest.raises(ManifestV2Error, match="insertOrder"):
        load_manifest_v2_dict(data)


def test_manifest_v2_accepts_insert_before_operation_fields():
    data = valid_v2_manifest()
    op = data["targets"][0]["modules"][0]["operations"][0]
    op.clear()
    op.update(
        {
            "opId": "insert-before-footer-target",
            "label": "Insert before footer target",
            "type": "insert_before",
            "anchor": "Oe&&\"frame\"",
            "expectedAnchorCount": 1,
            "insertOrder": 100,
            "replacement": {"inline": "\"hiddenContext\","},
        }
    )

    manifest = load_manifest_v2_dict(data)
    parsed = manifest.targets[0].modules[0].operations[0]

    assert parsed.type == "insert_before"
    assert parsed.anchor == "Oe&&\"frame\""
    assert parsed.insert_order == 100


def test_manifest_v2_rejects_non_unique_structured_locator_expectations():
    data = valid_v2_manifest()
    op = data["targets"][0]["modules"][0]["operations"][0]
    op.clear()
    op.update(
        {
            "opId": "insert-multiple-anchors",
            "label": "Insert multiple anchors",
            "type": "insert_after",
            "anchor": "OLD_RENDER",
            "expectedAnchorCount": 2,
            "insertOrder": 100,
            "replacement": {"inline": "NEW"},
        }
    )

    with pytest.raises(ManifestV2Error, match="expectedAnchorCount must be 1"):
        load_manifest_v2_dict(data)

    op.clear()
    op.update(
        {
            "opId": "replace-multiple-subspans",
            "label": "Replace multiple subspans",
            "type": "replace_substring_within",
            "startMarker": "function render(){",
            "endMarker": "function after(){",
            "subExact": "OLD_RENDER",
            "expectedSubExactCount": 2,
            "replacement": {"inline": "NEW"},
        }
    )

    with pytest.raises(ManifestV2Error, match="expectedSubExactCount must be 1"):
        load_manifest_v2_dict(data)
```

- [ ] **Step 2: Run manifest tests and verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_manifest_v2.py -q
```

Expected result: FAIL. The failure should mention unsupported operation type or missing dataclass fields such as `anchor`.

- [ ] **Step 3: Extend `ModuleOperationV2` and operation constants**

In `/Users/MAC/Documents/Claude-patch/src/claude_monkey/manifest_v2.py`, replace:

```python
SUPPORTED_OPERATION_TYPES = {"replace_between", "replace_exact"}
```

with:

```python
SUPPORTED_OPERATION_TYPES = {
    "replace_between",
    "replace_exact",
    "insert_before",
    "insert_after",
    "replace_substring_within",
}
```

Then replace the `ModuleOperationV2` dataclass with:

```python
@dataclass(frozen=True)
class ModuleOperationV2:
    op_id: str
    label: str
    type: str
    start_marker: str | None
    end_marker: str | None
    exact: str | None
    anchor: str | None
    sub_exact: str | None
    expected_start_marker_count: int
    expected_end_marker_count: int
    expected_anchor_count: int
    expected_sub_exact_count: int
    insert_order: int | None
    require_within_range: tuple[str, ...]
    old_range_sha256: str | None
    old_range_length: int | None
    context_sha256: str | None
    seam_hint: str | None
    replacement: PayloadRefV2
    known_behavior_change: str | None
```

- [ ] **Step 4: Add validation helpers in `manifest_v2.py`**

Add this helper after `optional_non_negative_int`:

```python
def optional_int(obj: dict[str, Any], field: str) -> int | None:
    value = obj.get(field)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ManifestV2Error(f"{field} must be an integer")
    return value
```

Add these helpers after `parse_payload`:

```python
def _operation_requires_anchor(op_type: str) -> bool:
    return op_type in {"insert_before", "insert_after"}


def _operation_requires_sub_exact(op_type: str) -> bool:
    return op_type == "replace_substring_within"


def _validate_operation_shape(op: dict[str, Any], op_type: str) -> None:
    if _operation_requires_anchor(op_type):
        if not isinstance(op.get("anchor"), str) or op.get("anchor") == "":
            raise ManifestV2Error("anchor is required for insert operations")
        if "insertOrder" not in op:
            raise ManifestV2Error("insertOrder is required for insert operations")
        if op.get("expectedAnchorCount", 1) != 1:
            raise ManifestV2Error("expectedAnchorCount must be 1 for insert operations")
    if _operation_requires_sub_exact(op_type):
        if not isinstance(op.get("subExact"), str) or op.get("subExact") == "":
            raise ManifestV2Error("subExact is required for replace_substring_within")
        if not isinstance(op.get("startMarker"), str) or op.get("startMarker") == "":
            raise ManifestV2Error("startMarker is required for replace_substring_within")
        if not isinstance(op.get("endMarker"), str) or op.get("endMarker") == "":
            raise ManifestV2Error("endMarker is required for replace_substring_within")
        if op.get("expectedSubExactCount", 1) != 1:
            raise ManifestV2Error(
                "expectedSubExactCount must be 1 for replace_substring_within"
            )
```

- [ ] **Step 5: Update `parse_operation()`**

In `parse_operation()`, after checking `SUPPORTED_OPERATION_TYPES`, insert:

```python
    _validate_operation_shape(op, op_type)
```

Then update the `ModuleOperationV2(...)` call to include the new fields:

```python
        anchor=optional_string(op, "anchor"),
        sub_exact=optional_string(op, "subExact"),
        expected_anchor_count=require_int(op, "expectedAnchorCount")
        if "expectedAnchorCount" in op
        else 1,
        expected_sub_exact_count=require_int(op, "expectedSubExactCount")
        if "expectedSubExactCount" in op
        else 1,
        insert_order=optional_int(op, "insertOrder"),
        context_sha256=optional_sha256(op, "contextSha256"),
        seam_hint=optional_string(op, "seamHint"),
```

Keep the existing fields and existing defaults unchanged.

- [ ] **Step 6: Keep existing module-patch tests compatible with new dataclass fields**

In `/Users/MAC/Documents/Claude-patch/tests/test_module_patch.py`, update the existing `op()` helper's `ModuleOperationV2(...)` constructor to include the new fields before `expected_start_marker_count`:

```python
        anchor=None,
        sub_exact=None,
```

and include these fields before `require_within_range`:

```python
        expected_anchor_count=1,
        expected_sub_exact_count=1,
        insert_order=None,
```

and include these fields before `replacement`:

```python
        context_sha256=None,
        seam_hint=None,
```

This keeps the broader test suite importable between Task 1 and Task 2.

- [ ] **Step 7: Run manifest tests and existing module-patch tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_manifest_v2.py tests/test_module_patch.py -q
```

Expected result: PASS.

- [ ] **Step 8: Commit Task 1**

Run:

```bash
git add src/claude_monkey/manifest_v2.py tests/test_manifest_v2.py tests/test_module_patch.py
git commit -m "Add structured splice manifest fields"
```

Expected result: commit created with only those three files.

## Task 2: Implement structured module operation planning

**Files:**
- Modify: `/Users/MAC/Documents/Claude-patch/tests/test_module_patch.py`
- Modify: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/module_patch.py`

- [ ] **Step 1: Replace the compatibility test helper with an override-friendly helper**

In `/Users/MAC/Documents/Claude-patch/tests/test_module_patch.py`, replace the `op()` helper updated in Task 1 with:

```python
def op(replacement: bytes, **overrides) -> ModuleOperationV2:
    old = MODULE[: MODULE.index(b"function after(){")]
    values = {
        "op_id": "replace-renderer",
        "label": "Replace renderer",
        "type": "replace_between",
        "start_marker": "function render(){",
        "end_marker": "function after(){",
        "exact": None,
        "anchor": None,
        "sub_exact": None,
        "expected_start_marker_count": 1,
        "expected_end_marker_count": 1,
        "expected_anchor_count": 1,
        "expected_sub_exact_count": 1,
        "insert_order": None,
        "require_within_range": ("OLD_RENDER",),
        "old_range_sha256": hashlib.sha256(old).hexdigest(),
        "old_range_length": len(old),
        "context_sha256": None,
        "seam_hint": None,
        "replacement": PayloadRefV2(inline=replacement.decode("utf-8")),
        "known_behavior_change": None,
    }
    values.update(overrides)
    return ModuleOperationV2(**values)
```

- [ ] **Step 2: Add failing module patch tests**

Append these tests to `/Users/MAC/Documents/Claude-patch/tests/test_module_patch.py`:

```python

def test_insert_after_renders_same_offset_operations_by_insert_order():
    module = b"items=[\"frame\"]\n"
    first = op(
        b",\"hiddenContext\"",
        op_id="insert-hidden-context",
        type="insert_after",
        start_marker=None,
        end_marker=None,
        anchor="\"frame\"",
        insert_order=100,
        require_within_range=(),
        old_range_sha256=None,
        old_range_length=None,
    )
    second = op(
        b",\"reminders\"",
        op_id="insert-reminders",
        type="insert_after",
        start_marker=None,
        end_marker=None,
        anchor="\"frame\"",
        insert_order=200,
        require_within_range=(),
        old_range_sha256=None,
        old_range_length=None,
    )

    planned = plan_module_operations(
        "pkg",
        "cli.js",
        module,
        [(second, b",\"reminders\""), (first, b",\"hiddenContext\"")],
    )
    changed = render_changed_module(module, planned)

    assert changed == b"items=[\"frame\",\"hiddenContext\",\"reminders\"]\n"
    assert [item.op_id for item in planned] == ["insert-hidden-context", "insert-reminders"]
    assert all(item.kind == "insertion" for item in planned)


def test_insert_order_duplicate_at_same_point_is_rejected():
    module = b"items=[\"frame\"]\n"
    first = op(
        b",\"a\"",
        op_id="insert-a",
        type="insert_after",
        start_marker=None,
        end_marker=None,
        anchor="\"frame\"",
        insert_order=100,
        require_within_range=(),
        old_range_sha256=None,
        old_range_length=None,
    )
    second = op(
        b",\"b\"",
        op_id="insert-b",
        type="insert_after",
        start_marker=None,
        end_marker=None,
        anchor="\"frame\"",
        insert_order=100,
        require_within_range=(),
        old_range_sha256=None,
        old_range_length=None,
    )

    with pytest.raises(ModulePatchError, match="insert_order_duplicate"):
        plan_module_operations("pkg", "cli.js", module, [(first, b",\"a\""), (second, b",\"b\"")])


def test_replace_substring_within_claims_only_subspan():
    module = b'let qb=Du==="tasks",Ap=Du==="frame";function Sf(){}\n'
    operation = op(
        b'Ap=Du==="frame",hC=Du==="hiddenContext"',
        op_id="replace-frame-flag",
        type="replace_substring_within",
        start_marker='let qb=Du==="tasks"',
        end_marker=";function Sf",
        sub_exact='Ap=Du==="frame"',
        require_within_range=(),
        old_range_sha256=hashlib.sha256(b'Ap=Du==="frame"').hexdigest(),
        old_range_length=len(b'Ap=Du==="frame"'),
    )

    planned = plan_module_operations(
        "pkg",
        "cli.js",
        module,
        [(operation, b'Ap=Du==="frame",hC=Du==="hiddenContext"')],
    )
    changed = render_changed_module(module, planned)

    assert planned[0].kind == "subspan_replacement"
    assert planned[0].old_len == len(b'Ap=Du==="frame"')
    assert changed == (
        b'let qb=Du==="tasks",Ap=Du==="frame",hC=Du==="hiddenContext";function Sf(){}\n'
    )


def test_insert_before_renders_before_anchor():
    module = b"items=[\"frame\"]\n"
    operation = op(
        b"\"hiddenContext\",",
        op_id="insert-hidden-before-frame",
        type="insert_before",
        start_marker=None,
        end_marker=None,
        anchor="\"frame\"",
        insert_order=100,
        require_within_range=(),
        old_range_sha256=None,
        old_range_length=None,
    )

    planned = plan_module_operations(
        "pkg", "cli.js", module, [(operation, b"\"hiddenContext\",")]
    )
    changed = render_changed_module(module, planned)

    assert changed == b"items=[\"hiddenContext\",\"frame\"]\n"
    assert planned[0].module_start == module.index(b'"frame"')
    assert planned[0].module_end == planned[0].module_start


def test_insert_rejects_ambiguous_anchor_even_if_expected_count_is_two():
    module = b"items=[\"frame\",\"frame\"]\n"
    operation = op(
        b",\"reminders\"",
        op_id="insert-ambiguous-anchor",
        type="insert_after",
        start_marker=None,
        end_marker=None,
        anchor="\"frame\"",
        expected_anchor_count=2,
        insert_order=200,
        require_within_range=(),
        old_range_sha256=None,
        old_range_length=None,
    )

    with pytest.raises(ModulePatchError, match="anchor count 2 != 1"):
        plan_module_operations("pkg", "cli.js", module, [(operation, b",\"reminders\"")])


def test_replace_substring_within_rejects_ambiguous_subspan_even_if_expected_count_is_two():
    module = b'let x=Du==="frame",y=Du==="frame";function Sf(){}\n'
    operation = op(
        b'y=Du==="hiddenContext"',
        op_id="replace-ambiguous-subspan",
        type="replace_substring_within",
        start_marker="let x=",
        end_marker=";function Sf",
        sub_exact='Du==="frame"',
        expected_sub_exact_count=2,
        require_within_range=(),
        old_range_sha256=None,
        old_range_length=None,
    )

    with pytest.raises(ModulePatchError, match="subExact count 2 != 1"):
        plan_module_operations("pkg", "cli.js", module, [(operation, b'y=Du==="hiddenContext"')])


def test_replace_between_without_markers_still_fails_closed():
    operation = op(
        b"replacement",
        start_marker=None,
        end_marker=None,
        require_within_range=(),
        old_range_sha256=None,
        old_range_length=None,
    )

    with pytest.raises(
        ModulePatchError, match="replace_between requires startMarker and endMarker"
    ):
        plan_module_operations("pkg", "cli.js", MODULE, [(operation, b"replacement")])


def test_insertion_inside_nonzero_claimed_range_is_rejected():
    replacement = op(b"function render(){NEW}\n")
    insertion = op(
        b"_INSERT",
        op_id="insert-inside",
        type="insert_after",
        start_marker=None,
        end_marker=None,
        anchor="OLD_RENDER",
        insert_order=100,
        require_within_range=(),
        old_range_sha256=None,
        old_range_length=None,
    )

    with pytest.raises(ModulePatchError, match="insert_inside_claimed_range"):
        plan_module_operations(
            "pkg",
            "cli.js",
            MODULE,
            [(replacement, b"function render(){NEW}\n"), (insertion, b"_INSERT")],
        )


def test_insertion_at_nonzero_claimed_range_boundary_is_allowed():
    replacement = op(b"function render(){NEW}\n")
    insertion = op(
        b"/*before*/",
        op_id="insert-at-start-boundary",
        type="insert_before",
        start_marker=None,
        end_marker=None,
        anchor="function render(){",
        insert_order=100,
        require_within_range=(),
        old_range_sha256=None,
        old_range_length=None,
    )

    planned = plan_module_operations(
        "pkg",
        "cli.js",
        MODULE,
        [(replacement, b"function render(){NEW}\n"), (insertion, b"/*before*/")],
    )

    assert render_changed_module(MODULE, planned).startswith(b"/*before*/function render(){NEW}")


def test_nonzero_overlap_still_fails_closed_at_module_level():
    first = op(b"function render(){NEW}\n")
    second = op(
        b"OLD",
        op_id="overlap",
        start_marker="OLD",
        end_marker="after",
        require_within_range=(),
        old_range_sha256=None,
        old_range_length=None,
    )

    with pytest.raises(ModulePatchError, match="range_overlap"):
        plan_module_operations(
            "pkg",
            "cli.js",
            MODULE,
            [(first, b"function render(){NEW}\n"), (second, b"OLD")],
        )


def test_context_sha_mismatch_fails_build_planning():
    module = b'let qb=Du==="tasks",Ap=Du==="frame";function Sf(){}\n'
    operation = op(
        b'Ap=Du==="frame",hC=Du==="hiddenContext"',
        op_id="replace-frame-flag",
        type="replace_substring_within",
        start_marker='let qb=Du==="tasks"',
        end_marker=";function Sf",
        sub_exact='Ap=Du==="frame"',
        require_within_range=(),
        old_range_sha256=hashlib.sha256(b'Ap=Du==="frame"').hexdigest(),
        old_range_length=len(b'Ap=Du==="frame"'),
        context_sha256="0" * 64,
    )

    with pytest.raises(ModulePatchError, match="context sha256 mismatch"):
        plan_module_operations(
            "pkg",
            "cli.js",
            module,
            [(operation, b'Ap=Du==="frame",hC=Du==="hiddenContext"')],
        )
```

- [ ] **Step 3: Run module tests and verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_module_patch.py -q
```

Expected result: FAIL because `PlannedModuleOperation` lacks `kind`, insert operations are unsupported, structured locator uniqueness is not enforced, `replace_between` without markers may not fail correctly after helper refactoring, and graph-safety checks do not yet understand insertion boundaries.

- [ ] **Step 4: Extend `PlannedModuleOperation`**

In `/Users/MAC/Documents/Claude-patch/src/claude_monkey/module_patch.py`, replace the dataclass with:

```python
@dataclass(frozen=True)
class PlannedModuleOperation:
    package_id: str
    op_id: str
    label: str
    operation_type: str
    module_path: str
    module_start: int
    module_end: int
    old_len: int
    new_len: int
    delta: int
    old_sha256: str
    replacement: bytes
    kind: str = "replacement"
    context_start: int | None = None
    context_end: int | None = None
    insert_order: int | None = None
    anchor: str | None = None
    seam_hint: str | None = None

    @property
    def render_order(self) -> tuple[int, int, int, str, str]:
        if self.kind == "insertion":
            order = self.insert_order if self.insert_order is not None else 0
            return (self.module_start, 0, order, self.package_id, self.op_id)
        return (self.module_start, 1, 0, self.package_id, self.op_id)
```

- [ ] **Step 5: Add context and range helpers**

In `/Users/MAC/Documents/Claude-patch/src/claude_monkey/module_patch.py`, replace `_range_for_operation()` with these helpers and function:

```python
def _resolve_context(module: bytes, operation: ModuleOperationV2) -> tuple[int, int]:
    if operation.start_marker is None and operation.end_marker is None:
        return 0, len(module)
    if operation.start_marker is None or operation.end_marker is None:
        raise ModulePatchError(
            f"{operation.op_id}: context requires both startMarker and endMarker"
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
    if start < 0 or end < 0 or end < start:
        raise ModulePatchError(f"{operation.op_id}: invalid context range [{start},{end})")
    return start, end


def _context_sha_matches(module: bytes, operation: ModuleOperationV2, start: int, end: int) -> bool:
    if operation.context_sha256 is None:
        return True
    return hashlib.sha256(module[start:end]).hexdigest() == operation.context_sha256


def _enforce_context_sha(module: bytes, operation: ModuleOperationV2, start: int, end: int) -> None:
    if not _context_sha_matches(module, operation, start, end):
        raise ModulePatchError(f"{operation.op_id}: context sha256 mismatch")


def _count_in_range(source: bytes, needle: bytes, start: int, end: int) -> int:
    return _count(source[start:end], needle)


def _find_in_range(source: bytes, needle: bytes, start: int, end: int) -> int:
    relative = source[start:end].find(needle)
    return -1 if relative < 0 else start + relative


def _range_for_operation(
    module: bytes, operation: ModuleOperationV2, *, enforce_context_sha: bool = True
) -> tuple[int, int, int | None, int | None, str]:
    if operation.type == "replace_between":
        if operation.start_marker is None or operation.end_marker is None:
            raise ModulePatchError(
                f"{operation.op_id}: replace_between requires startMarker and endMarker"
            )
        start, end = _resolve_context(module, operation)
        if enforce_context_sha:
            _enforce_context_sha(module, operation, start, end)
        return start, end, None, None, "replacement"
    if operation.type == "replace_exact":
        if operation.exact is None:
            raise ModulePatchError(f"{operation.op_id}: replace_exact requires exact")
        exact = _b(operation.exact)
        exact_count = _count(module, exact)
        if exact_count != 1:
            raise ModulePatchError(f"{operation.op_id}: exact marker count {exact_count} != 1")
        start = module.find(exact)
        end = start + len(exact)
        if enforce_context_sha:
            _enforce_context_sha(module, operation, start, end)
        return start, end, None, None, "replacement"
    if operation.type in {"insert_before", "insert_after"}:
        if operation.anchor is None:
            raise ModulePatchError(f"{operation.op_id}: insert requires anchor")
        if operation.insert_order is None:
            raise ModulePatchError(f"{operation.op_id}: insert requires insertOrder")
        context_start, context_end = _resolve_context(module, operation)
        if enforce_context_sha:
            _enforce_context_sha(module, operation, context_start, context_end)
        anchor = _b(operation.anchor)
        anchor_count = _count_in_range(module, anchor, context_start, context_end)
        if anchor_count != 1:
            raise ModulePatchError(f"{operation.op_id}: anchor count {anchor_count} != 1")
        anchor_start = _find_in_range(module, anchor, context_start, context_end)
        point = anchor_start if operation.type == "insert_before" else anchor_start + len(anchor)
        return point, point, context_start, context_end, "insertion"
    if operation.type == "replace_substring_within":
        if operation.sub_exact is None:
            raise ModulePatchError(f"{operation.op_id}: replace_substring_within requires subExact")
        context_start, context_end = _resolve_context(module, operation)
        if enforce_context_sha:
            _enforce_context_sha(module, operation, context_start, context_end)
        context = module[context_start:context_end]
        sub = _b(operation.sub_exact)
        sub_count = _count(context, sub)
        if sub_count != 1:
            raise ModulePatchError(f"{operation.op_id}: subExact count {sub_count} != 1")
        start = _find_in_range(module, sub, context_start, context_end)
        return start, start + len(sub), context_start, context_end, "subspan_replacement"
    raise ModulePatchError(f"{operation.op_id}: unsupported operation type {operation.type}")
```

- [ ] **Step 6: Update planning and validation**

In `plan_module_operations()`, replace:

```python
        start, end = _range_for_operation(module_content, operation)
```

with:

```python
        start, end, context_start, context_end, kind = _range_for_operation(
            module_content, operation
        )
```

When constructing `PlannedModuleOperation`, add:

```python
                operation_type=operation.type,
                kind=kind,
                context_start=context_start,
                context_end=context_end,
                insert_order=operation.insert_order,
                anchor=operation.anchor,
                seam_hint=operation.seam_hint,
```

Replace the sorting and overlap block with:

```python
    planned.sort(key=lambda item: item.render_order)
    _check_operation_graph(planned)
```

Add this helper before `render_changed_module()`:

```python
def _check_operation_graph(planned: list[PlannedModuleOperation]) -> None:
    ordered = sorted(
        planned, key=lambda item: (item.module_start, item.module_end, item.render_order)
    )
    insert_groups: set[tuple[int, int]] = set()
    for item in ordered:
        if item.kind == "insertion":
            key = (item.module_start, item.insert_order if item.insert_order is not None else 0)
            if key in insert_groups:
                raise ModulePatchError(
                    "patch_conflict:insert_order_duplicate:"
                    f"{item.module_path}:{item.module_start}:{item.insert_order}"
                )
            insert_groups.add(key)
    non_insertions = [item for item in ordered if item.kind != "insertion"]
    for left, right in zip(non_insertions, non_insertions[1:], strict=False):
        if left.module_end > right.module_start:
            raise ModulePatchError(
                "patch_conflict:range_overlap:"
                f"{left.package_id}:{left.op_id}:{right.package_id}:{right.op_id}"
            )
    for insertion in [item for item in ordered if item.kind == "insertion"]:
        for owner in non_insertions:
            if owner.module_start < insertion.module_start < owner.module_end:
                raise ModulePatchError(
                    "patch_conflict:insert_inside_claimed_range:"
                    f"{insertion.package_id}:{insertion.op_id}:{owner.package_id}:{owner.op_id}"
                )
```

- [ ] **Step 7: Update rendering order**

In `render_changed_module()`, replace:

```python
    for item in sorted(planned, key=lambda op: op.module_start):
```

with:

```python
    for item in sorted(planned, key=lambda op: op.render_order):
```

- [ ] **Step 8: Run module patch tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_module_patch.py -q
```

Expected result: PASS.

- [ ] **Step 9: Commit Task 2**

Run:

```bash
git add src/claude_monkey/module_patch.py tests/test_module_patch.py
git commit -m "Add structured module splice planning"
```

Expected result: commit created with only `module_patch.py` and `test_module_patch.py`.

## Task 3: Validate cross-package operation graph in builder

**Files:**
- Modify: `/Users/MAC/Documents/Claude-patch/tests/test_builder_v15.py`
- Modify: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/builder_v15.py`

- [ ] **Step 1: Add fixture package helper for insertion packages**

Append this helper after `write_fixture_package()` in `/Users/MAC/Documents/Claude-patch/tests/test_builder_v15.py`:

```python
def write_insert_fixture_package(
    package: Path, binary: Path, package_id: str, insert_order: int, value: str
) -> None:
    manifest = {
        "schemaVersion": 2,
        "id": package_id,
        "name": package_id,
        "description": f"Insert fixture {package_id}",
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
                                "opId": f"insert-{value}",
                                "label": f"Insert {value}",
                                "type": "insert_after",
                                "anchor": "OLD_RENDER",
                                "expectedAnchorCount": 1,
                                "insertOrder": insert_order,
                                "replacement": {"inline": value},
                            }
                        ],
                    }
                ],
                "postconditions": [
                    {
                        "type": "module_must_contain",
                        "modulePath": "/$bunfs/root/src/entrypoints/cli.js",
                        "value": value,
                    }
                ],
                "manualSmoke": {"required": False},
            }
        ],
    }
    package.mkdir()
    (package / "patch.json").write_text(json.dumps(manifest))
```

- [ ] **Step 2: Add failing cross-package insertion tests**

Append these tests to `/Users/MAC/Documents/Claude-patch/tests/test_builder_v15.py`:

```python

def test_build_patchset_v15_composes_same_anchor_insertions_by_order(tmp_path):
    source = tmp_path / "claude-source"
    source.write_bytes(build_aligned_macho_fixture()[0])
    first = tmp_path / "first"
    second = tmp_path / "second"
    write_insert_fixture_package(first, source, "first", 100, "_A")
    write_insert_fixture_package(second, source, "second", 200, "_B")

    report = build_patchset_v15(
        BuildRequestV15(
            source_path=source,
            output_dir=tmp_path / "out",
            package_dirs=[second, first],
            source_version="fixture",
            source_version_output="fixture (Claude Code)",
            platform="darwin",
            arch="arm64",
            command_runner=successful_runner,
        )
    )

    assert report.failureReason is None
    assert report.automatedStatus == "passed"
    assert report.schemaVersion == 3
    ops = [
        (item["packageId"], item["opId"], item["insertOrder"])
        for item in report.operationsApplied
    ]
    assert ops == [("first", "insert-_A", 100), ("second", "insert-_B", 200)]
    first_op = report.operationsApplied[0]
    for key in [
        "packageId",
        "opId",
        "label",
        "modulePath",
        "moduleStart",
        "moduleEnd",
        "oldLen",
        "newLen",
        "delta",
        "oldSha256",
    ]:
        assert key in first_op
    assert first_op["type"] == "insert_after"
    assert first_op["kind"] == "insertion"


def test_build_patchset_v15_rejects_duplicate_insert_order_across_packages(tmp_path):
    source = tmp_path / "claude-source"
    source.write_bytes(build_aligned_macho_fixture()[0])
    first = tmp_path / "first"
    second = tmp_path / "second"
    write_insert_fixture_package(first, source, "first", 100, "_A")
    write_insert_fixture_package(second, source, "second", 100, "_B")

    report = build_patchset_v15(
        BuildRequestV15(
            source_path=source,
            output_dir=tmp_path / "out",
            package_dirs=[first, second],
            source_version="fixture",
            source_version_output="fixture (Claude Code)",
            platform="darwin",
            arch="arm64",
            command_runner=successful_runner,
        )
    )

    assert report.status == "failed"
    assert report.failureReason is not None
    assert "patch_conflict:insert_order_duplicate" in report.failureReason


def test_build_patchset_v15_rejects_insertion_inside_claimed_replacement_range(tmp_path):
    source = tmp_path / "claude-source"
    source.write_bytes(build_aligned_macho_fixture()[0])
    owner = tmp_path / "owner"
    inserter = tmp_path / "inserter"
    write_fixture_package(owner, source)
    data = json.loads((owner / "patch.json").read_text())
    data["id"] = "owner"
    data["targets"][0]["modules"][0]["operations"][0]["opId"] = "owner-replace"
    (owner / "patch.json").write_text(json.dumps(data))
    write_insert_fixture_package(inserter, source, "inserter", 100, "_INSIDE")

    report = build_patchset_v15(
        BuildRequestV15(
            source_path=source,
            output_dir=tmp_path / "out",
            package_dirs=[owner, inserter],
            source_version="fixture",
            source_version_output="fixture (Claude Code)",
            platform="darwin",
            arch="arm64",
            command_runner=successful_runner,
        )
    )

    assert report.status == "failed"
    assert report.failureReason is not None
    assert "patch_conflict:insert_inside_claimed_range" in report.failureReason


def test_build_patchset_v15_rejects_cross_package_nonzero_overlap(tmp_path):
    source = tmp_path / "claude-source"
    source.write_bytes(build_aligned_macho_fixture()[0])
    first = tmp_path / "first"
    second = tmp_path / "second"
    write_fixture_package(first, source)
    write_fixture_package(second, source)
    for package, package_id in [(first, "first-owner"), (second, "second-owner")]:
        data = json.loads((package / "patch.json").read_text())
        data["id"] = package_id
        op = data["targets"][0]["modules"][0]["operations"][0]
        op["opId"] = f"{package_id}-replace"
        (package / "patch.json").write_text(json.dumps(data))

    report = build_patchset_v15(
        BuildRequestV15(
            source_path=source,
            output_dir=tmp_path / "out",
            package_dirs=[first, second],
            source_version="fixture",
            source_version_output="fixture (Claude Code)",
            platform="darwin",
            arch="arm64",
            command_runner=successful_runner,
        )
    )

    assert report.status == "failed"
    assert report.failureReason is not None
    assert "patch_conflict:range_overlap" in report.failureReason
```

- [ ] **Step 3: Run builder tests and verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_builder_v15.py -q
```

Expected result: FAIL. The shared insertion test should fail because `operationsApplied` does not yet include additive structured fields. The duplicate-order test may incorrectly pass because cross-package duplicate insert-order validation does not exist yet. The insertion-inside-range and non-zero overlap tests protect the graph-safety invariants while `_check_overlaps()` is replaced.

- [ ] **Step 4: Replace builder cross-package overlap check**

In `/Users/MAC/Documents/Claude-patch/src/claude_monkey/builder_v15.py`, replace `_check_overlaps()` with:

```python
def _check_overlaps(planned: list[PlannedModuleOperation]) -> None:
    ordered = sorted(
        planned, key=lambda item: (item.module_start, item.module_end, item.render_order)
    )
    insert_groups: set[tuple[str, int, int]] = set()
    for item in ordered:
        if item.kind == "insertion":
            order = item.insert_order if item.insert_order is not None else 0
            key = (item.module_path, item.module_start, order)
            if key in insert_groups:
                raise ValueError(
                    "patch_conflict:insert_order_duplicate:"
                    f"{item.module_path}:{item.module_start}:{order}"
                )
            insert_groups.add(key)
    non_insertions = [item for item in ordered if item.kind != "insertion"]
    for left, right in zip(non_insertions, non_insertions[1:], strict=False):
        if left.module_end > right.module_start:
            raise ValueError(
                "patch_conflict:range_overlap:"
                f"{left.package_id}:{left.op_id}:{right.package_id}:{right.op_id}"
            )
    insertions = [item for item in ordered if item.kind == "insertion"]
    for insertion in insertions:
        for owner in non_insertions:
            if owner.module_start < insertion.module_start < owner.module_end:
                raise ValueError(
                    "patch_conflict:insert_inside_claimed_range:"
                    f"{insertion.package_id}:{insertion.op_id}:{owner.package_id}:{owner.op_id}"
                )
```

- [ ] **Step 5: Add operation serialization helper**

Add this helper near `_assert_condition_v2()` in `builder_v15.py`:

```python
def _operation_report_dict(item: PlannedModuleOperation) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "packageId": item.package_id,
        "opId": item.op_id,
        "label": item.label,
        "type": item.operation_type,
        "kind": item.kind,
        "modulePath": item.module_path,
        "moduleStart": item.module_start,
        "moduleEnd": item.module_end,
        "oldLen": item.old_len,
        "newLen": item.new_len,
        "delta": item.delta,
        "oldSha256": item.old_sha256,
    }
    if item.context_start is not None:
        payload["contextStart"] = item.context_start
    if item.context_end is not None:
        payload["contextEnd"] = item.context_end
    if item.insert_order is not None:
        payload["insertOrder"] = item.insert_order
    if item.anchor is not None:
        payload["anchor"] = item.anchor
    if item.seam_hint is not None:
        payload["seamHint"] = item.seam_hint
    return payload
```

- [ ] **Step 6: Use operation serialization helper in build report**

In `build_patchset_v15()`, replace the `report.operationsApplied = [...]` comprehension with:

```python
        report.operationsApplied = [
            _operation_report_dict(item)
            for planned in planned_by_module.values()
            for item in sorted(planned, key=lambda op: op.render_order)
        ]
```

- [ ] **Step 7: Run builder tests and verify pass**

Run:

```bash
.venv/bin/python -m pytest tests/test_builder_v15.py -q
```

Expected result: PASS.

- [ ] **Step 8: Commit Task 3**

Run:

```bash
git add src/claude_monkey/builder_v15.py tests/test_builder_v15.py
git commit -m "Validate cross-package structured splice ordering"
```

Expected result: commit created with only those two files.

## Task 4: Extend validate-package operation evidence

**Files:**
- Modify: `/Users/MAC/Documents/Claude-patch/tests/test_cli_v15.py`
- Modify: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/builder_v15.py`

- [ ] **Step 1: Add validate-package evidence test**

Append this test to `/Users/MAC/Documents/Claude-patch/tests/test_cli_v15.py`:

```python

def test_validate_package_json_reports_structured_insert_fields(tmp_path, capsys):
    import hashlib

    from tests.fixtures_bun import MODULE_0, build_macho_fixture

    binary = tmp_path / "claude"
    binary.write_bytes(build_macho_fixture()[0])
    package = tmp_path / "pkg"
    package.mkdir()
    manifest = {
        "schemaVersion": 2,
        "id": "fixture-insert",
        "name": "Fixture Insert",
        "description": "Fixture insert package",
        "packageVersion": "0.1.0",
        "targets": [
            {
                "sourceIdentity": {
                    "claudeVersion": "fixture",
                    "versionOutput": "fixture",
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
                                "opId": "insert-marker",
                                "label": "Insert marker",
                                "type": "insert_after",
                                "anchor": "OLD_RENDER",
                                "expectedAnchorCount": 1,
                                "insertOrder": 100,
                                "seamHint": "fixture.oldRender.after",
                                "replacement": {"inline": "_MARKER"},
                            }
                        ],
                    }
                ],
                "manualSmoke": {"required": False},
            }
        ],
    }
    (package / "patch.json").write_text(json.dumps(manifest))

    assert (
        main(
            [
                "validate-package",
                "--source",
                str(binary),
                "--package",
                str(package),
                "--source-version",
                "fixture",
                "--source-version-output",
                "fixture",
                "--json",
            ]
        )
        == 0
    )
    payload = read_json(capsys)
    op = payload["operationsResolved"][0]
    assert op["type"] == "insert_after"
    assert op["kind"] == "insertion"
    assert op["insertOrder"] == 100
    assert op["seamHint"] == "fixture.oldRender.after"
    assert op["moduleStart"] == op["moduleEnd"]
```

- [ ] **Step 2: Run CLI v15 test and verify failure**

Run:

```bash
.venv/bin/python -m pytest tests/test_cli_v15.py::test_validate_package_json_reports_structured_insert_fields -q
```

Expected result: FAIL because `operationsResolved` uses an inline dict without structured fields.

- [ ] **Step 3: Reuse `_operation_report_dict()` in `validate_package()`**

In `/Users/MAC/Documents/Claude-patch/src/claude_monkey/builder_v15.py`, replace the `operationsResolved` comprehension in `validate_package()` with:

```python
            "operationsResolved": [
                _operation_report_dict(item)
                for item in sorted(resolved, key=lambda op: op.render_order)
            ],
```

- [ ] **Step 4: Run CLI v15 tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_cli_v15.py -q
```

Expected result: PASS.

- [ ] **Step 5: Commit Task 4**

Run:

```bash
git add src/claude_monkey/builder_v15.py tests/test_cli_v15.py
git commit -m "Report structured splice validation evidence"
```

Expected result: commit created with only those two files.

## Task 5: Add diagnostic-only retarget analysis

**Files:**
- Modify: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/module_patch.py`
- Modify: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/builder_v15.py`
- Modify: `/Users/MAC/Documents/Claude-patch/tests/test_module_patch.py`
- Modify: `/Users/MAC/Documents/Claude-patch/tests/test_cli_v15.py`

- [ ] **Step 1: Add module operation diagnostic helper tests**

In `/Users/MAC/Documents/Claude-patch/tests/test_module_patch.py`, update the import from `claude_monkey.module_patch` to include `diagnose_module_operation`:

```python
from claude_monkey.module_patch import (
    ModulePatchError,
    diagnose_module_operation,
    plan_module_operations,
    render_changed_module,
)
```

Then append these tests to `/Users/MAC/Documents/Claude-patch/tests/test_module_patch.py`:

```python

def test_diagnose_module_operation_reports_unique_candidate_without_accepting():
    module = b"items=[\"frame\"]\n"
    operation = op(
        b",\"reminders\"",
        op_id="insert-reminders",
        type="insert_after",
        start_marker=None,
        end_marker=None,
        anchor="\"frame\"",
        insert_order=200,
        require_within_range=(),
        old_range_sha256=None,
        old_range_length=None,
        context_sha256="0" * 64,
    )

    diagnostic = diagnose_module_operation(module, operation)

    assert diagnostic["opId"] == "insert-reminders"
    assert diagnostic["ok"] is False
    assert diagnostic["status"] == "candidate_found_context_hash_changed"
    assert diagnostic["anchorCount"] == 1
    assert diagnostic["candidateModuleStart"] == module.index(b'"frame"') + len(b'"frame"')


def test_diagnose_module_operation_distinguishes_missing_and_ambiguous_anchor():
    missing = op(
        b",\"reminders\"",
        op_id="insert-missing",
        type="insert_after",
        start_marker=None,
        end_marker=None,
        anchor="\"frame\"",
        insert_order=200,
        require_within_range=(),
        old_range_sha256=None,
        old_range_length=None,
    )
    ambiguous = op(
        b",\"reminders\"",
        op_id="insert-ambiguous",
        type="insert_after",
        start_marker=None,
        end_marker=None,
        anchor="\"frame\"",
        insert_order=200,
        require_within_range=(),
        old_range_sha256=None,
        old_range_length=None,
    )

    missing_diagnostic = diagnose_module_operation(b"items=[\"tasks\"]\n", missing)
    ambiguous_diagnostic = diagnose_module_operation(b"items=[\"frame\",\"frame\"]\n", ambiguous)

    assert missing_diagnostic["status"] == "anchor_missing"
    assert missing_diagnostic["anchorCount"] == 0
    assert ambiguous_diagnostic["status"] == "anchor_ambiguous"
    assert ambiguous_diagnostic["anchorCount"] == 2


def test_diagnose_replace_substring_within_reports_context_and_subspan_failures():
    missing_context = op(
        b"NEW",
        op_id="missing-context",
        type="replace_substring_within",
        start_marker="missing-start",
        end_marker="end",
        sub_exact="needle",
        require_within_range=(),
        old_range_sha256=None,
        old_range_length=None,
    )
    ambiguous_context = op(
        b"NEW",
        op_id="ambiguous-context",
        type="replace_substring_within",
        start_marker="start",
        end_marker="end",
        sub_exact="needle",
        require_within_range=(),
        old_range_sha256=None,
        old_range_length=None,
    )
    missing_sub = op(
        b"NEW",
        op_id="missing-sub",
        type="replace_substring_within",
        start_marker="start",
        end_marker="end",
        sub_exact="missing",
        require_within_range=(),
        old_range_sha256=None,
        old_range_length=None,
    )
    ambiguous_sub = op(
        b"NEW",
        op_id="ambiguous-sub",
        type="replace_substring_within",
        start_marker="start",
        end_marker="end",
        sub_exact="needle",
        require_within_range=(),
        old_range_sha256=None,
        old_range_length=None,
    )

    assert (
        diagnose_module_operation(b"prefix needle end", missing_context)["status"]
        == "context_missing"
    )
    assert (
        diagnose_module_operation(b"start needle end start needle end", ambiguous_context)[
            "status"
        ]
        == "context_ambiguous"
    )
    assert (
        diagnose_module_operation(b"start needle end", missing_sub)["status"]
        == "sub_exact_missing"
    )
    assert (
        diagnose_module_operation(b"start needle needle end", ambiguous_sub)["status"]
        == "sub_exact_ambiguous"
    )


def test_diagnose_replace_substring_within_reports_old_range_evidence():
    module = b"start needle end"
    operation = op(
        b"NEW",
        op_id="changed-old-range",
        type="replace_substring_within",
        start_marker="start",
        end_marker="end",
        sub_exact="needle",
        require_within_range=(),
        old_range_sha256="0" * 64,
        old_range_length=99,
    )

    diagnostic = diagnose_module_operation(module, operation)

    assert diagnostic["status"] == "candidate_found_old_range_changed"
    assert diagnostic["subExactCount"] == 1
    assert diagnostic["oldRangeLengthMatched"] is False
    assert diagnostic["oldRangeSha256Matched"] is False
```

- [ ] **Step 2: Implement `diagnose_module_operation()`**

In `/Users/MAC/Documents/Claude-patch/src/claude_monkey/module_patch.py`, add these helpers after `render_changed_module()`:

```python
def _diagnose_context_range(
    module_content: bytes, operation: ModuleOperationV2, result: dict[str, object]
) -> tuple[int, int] | None:
    if operation.start_marker is None and operation.end_marker is None:
        result["contextStatus"] = "whole_module"
        result["contextStart"] = 0
        result["contextEnd"] = len(module_content)
        return 0, len(module_content)
    if operation.start_marker is None or operation.end_marker is None:
        result["contextStatus"] = "invalid"
        result["status"] = "context_invalid"
        return None
    start_marker = _b(operation.start_marker)
    end_marker = _b(operation.end_marker)
    start_count = _count(module_content, start_marker)
    result["startMarkerCount"] = start_count
    if start_count == 0:
        result["contextStatus"] = "missing"
        result["status"] = "context_missing"
        return None
    if start_count != operation.expected_start_marker_count or start_count != 1:
        result["contextStatus"] = "ambiguous"
        result["status"] = "context_ambiguous"
        return None
    start = module_content.find(start_marker)
    tail_start = start + len(start_marker)
    tail = module_content[tail_start:]
    end_count = _count(tail, end_marker)
    result["endMarkerCount"] = end_count
    if end_count == 0:
        result["contextStatus"] = "missing"
        result["status"] = "context_missing"
        return None
    if end_count != operation.expected_end_marker_count or end_count != 1:
        result["contextStatus"] = "ambiguous"
        result["status"] = "context_ambiguous"
        return None
    end = module_content.find(end_marker, tail_start)
    result["contextStatus"] = "resolved"
    result["contextStart"] = start
    result["contextEnd"] = end
    return start, end


def _record_old_range_evidence(
    module_content: bytes,
    operation: ModuleOperationV2,
    result: dict[str, object],
    start: int,
    end: int,
) -> None:
    old = module_content[start:end]
    old_changed = False
    if operation.old_range_length is not None:
        matched = operation.old_range_length == len(old)
        result["oldRangeLengthMatched"] = matched
        old_changed = old_changed or not matched
    if operation.old_range_sha256 is not None:
        old_sha = hashlib.sha256(old).hexdigest()
        matched = operation.old_range_sha256 == old_sha
        result["oldRangeSha256Matched"] = matched
        old_changed = old_changed or not matched
    if old_changed and result.get("status") == "candidate_found":
        result["status"] = "candidate_found_old_range_changed"


def diagnose_module_operation(
    module_content: bytes, operation: ModuleOperationV2
) -> dict[str, object]:
    result: dict[str, object] = {"opId": operation.op_id, "ok": False, "status": "not_checked"}
    context_range = _diagnose_context_range(module_content, operation, result)
    if context_range is None:
        return result
    context_start, context_end = context_range
    if operation.context_sha256 is not None:
        context_sha_matches = _context_sha_matches(
            module_content, operation, context_start, context_end
        )
        result["contextSha256Matched"] = context_sha_matches
    if operation.type in {"insert_before", "insert_after"}:
        if operation.anchor is None:
            result["status"] = "anchor_missing"
            result["anchorCount"] = 0
            return result
        anchor = _b(operation.anchor)
        anchor_count = _count_in_range(module_content, anchor, context_start, context_end)
        result["anchorCount"] = anchor_count
        if anchor_count == 0:
            result["status"] = "anchor_missing"
            return result
        if anchor_count != 1:
            result["status"] = "anchor_ambiguous"
            return result
        anchor_start = _find_in_range(module_content, anchor, context_start, context_end)
        point = anchor_start if operation.type == "insert_before" else anchor_start + len(anchor)
        result.update(
            {
                "status": "candidate_found",
                "kind": "insertion",
                "candidateModuleStart": point,
                "candidateModuleEnd": point,
            }
        )
    elif operation.type == "replace_substring_within":
        if operation.sub_exact is None:
            result["status"] = "sub_exact_missing"
            result["subExactCount"] = 0
            return result
        sub = _b(operation.sub_exact)
        sub_count = _count_in_range(module_content, sub, context_start, context_end)
        result["subExactCount"] = sub_count
        if sub_count == 0:
            result["status"] = "sub_exact_missing"
            return result
        if sub_count != 1:
            result["status"] = "sub_exact_ambiguous"
            return result
        start = _find_in_range(module_content, sub, context_start, context_end)
        end = start + len(sub)
        result.update(
            {
                "status": "candidate_found",
                "kind": "subspan_replacement",
                "candidateModuleStart": start,
                "candidateModuleEnd": end,
            }
        )
        _record_old_range_evidence(module_content, operation, result, start, end)
    else:
        try:
            start, end, _, _, kind = _range_for_operation(
                module_content, operation, enforce_context_sha=False
            )
        except ModulePatchError as exc:
            result["status"] = "not_resolved"
            result["error"] = str(exc)
            return result
        result.update(
            {
                "status": "candidate_found",
                "kind": kind,
                "candidateModuleStart": start,
                "candidateModuleEnd": end,
            }
        )
        _record_old_range_evidence(module_content, operation, result, start, end)
    if result.get("contextSha256Matched") is False:
        result["status"] = "candidate_found_context_hash_changed"
    return result
```

- [ ] **Step 3: Run the new module diagnostic tests and verify pass**

Run:

```bash
.venv/bin/python -m pytest tests/test_module_patch.py::test_diagnose_module_operation_reports_unique_candidate_without_accepting tests/test_module_patch.py::test_diagnose_module_operation_distinguishes_missing_and_ambiguous_anchor tests/test_module_patch.py::test_diagnose_replace_substring_within_reports_context_and_subspan_failures tests/test_module_patch.py::test_diagnose_replace_substring_within_reports_old_range_evidence -q
```

Expected result: PASS.

- [ ] **Step 4: Add validate-package diagnostic tests**

Append these tests to `/Users/MAC/Documents/Claude-patch/tests/test_cli_v15.py`:

```python

def test_validate_package_identity_mismatch_reports_diagnostic_candidates(tmp_path, capsys):
    import hashlib

    from tests.fixtures_bun import build_macho_fixture
    from tests.test_builder_v15 import write_insert_fixture_package

    binary = tmp_path / "claude"
    binary.write_bytes(build_macho_fixture()[0])
    package = tmp_path / "pkg"
    write_insert_fixture_package(package, binary, "fixture-insert", 100, "_A")

    assert (
        main(
            [
                "validate-package",
                "--source",
                str(binary),
                "--package",
                str(package),
                "--source-version",
                "new-version",
                "--source-version-output",
                "new-version (Claude Code)",
                "--json",
            ]
        )
        == 1
    )
    payload = read_json(capsys)
    assert payload["ok"] is False
    assert payload["errorCode"] == "source_identity_mismatch"
    assert payload["currentSourceIdentity"]["claudeVersion"] == "new-version"
    assert payload["currentSourceIdentity"]["sha256"] == hashlib.sha256(
        binary.read_bytes()
    ).hexdigest()
    assert payload["diagnosticTargetSelected"] is True
    assert payload["operationDiagnostics"][0]["opId"] == "insert-_A"
    assert payload["operationDiagnostics"][0]["status"] == "candidate_found"


def test_validate_package_identity_mismatch_stops_on_ambiguous_diagnostic_target(
    tmp_path, capsys
):
    from tests.fixtures_bun import build_macho_fixture
    from tests.test_builder_v15 import write_insert_fixture_package

    binary = tmp_path / "claude"
    binary.write_bytes(build_macho_fixture()[0])
    package = tmp_path / "pkg"
    write_insert_fixture_package(package, binary, "fixture-insert", 100, "_A")
    data = json.loads((package / "patch.json").read_text())
    second_target = json.loads(json.dumps(data["targets"][0]))
    second_target["sourceIdentity"]["claudeVersion"] = "other-fixture"
    second_target["sourceIdentity"]["versionOutput"] = "other-fixture (Claude Code)"
    second_target["modules"][0]["operations"][0]["opId"] = "insert-_A-other"
    data["targets"].append(second_target)
    (package / "patch.json").write_text(json.dumps(data))

    assert (
        main(
            [
                "validate-package",
                "--source",
                str(binary),
                "--package",
                str(package),
                "--source-version",
                "new-version",
                "--source-version-output",
                "new-version (Claude Code)",
                "--json",
            ]
        )
        == 1
    )
    payload = read_json(capsys)
    assert payload["ok"] is False
    assert payload["diagnosticTargetSelected"] is False
    assert payload["operationDiagnostics"] == []
    assert payload["diagnosticErrors"] == ["diagnostic_target_ambiguous"]


def test_validate_package_identity_mismatch_ignores_targets_for_missing_module_path(
    tmp_path, capsys
):
    from tests.fixtures_bun import build_macho_fixture
    from tests.test_builder_v15 import write_insert_fixture_package

    binary = tmp_path / "claude"
    binary.write_bytes(build_macho_fixture()[0])
    package = tmp_path / "pkg"
    write_insert_fixture_package(package, binary, "fixture-insert", 100, "_A")
    data = json.loads((package / "patch.json").read_text())
    second_target = json.loads(json.dumps(data["targets"][0]))
    second_target["sourceIdentity"]["claudeVersion"] = "other-fixture"
    second_target["modules"][0]["path"] = "/$bunfs/root/src/missing.js"
    data["targets"].append(second_target)
    (package / "patch.json").write_text(json.dumps(data))

    assert (
        main(
            [
                "validate-package",
                "--source",
                str(binary),
                "--package",
                str(package),
                "--source-version",
                "new-version",
                "--source-version-output",
                "new-version (Claude Code)",
                "--json",
            ]
        )
        == 1
    )
    payload = read_json(capsys)
    assert payload["diagnosticTargetSelected"] is True
    assert payload["operationDiagnostics"][0]["opId"] == "insert-_A"


def test_validate_package_module_identity_mismatch_reports_operation_diagnostics(
    tmp_path, capsys
):
    from tests.fixtures_bun import build_macho_fixture
    from tests.test_builder_v15 import write_insert_fixture_package

    binary = tmp_path / "claude"
    binary.write_bytes(build_macho_fixture()[0])
    package = tmp_path / "pkg"
    write_insert_fixture_package(package, binary, "fixture-insert", 100, "_A")
    data = json.loads((package / "patch.json").read_text())
    data["targets"][0]["modules"][0]["contentSha256"] = "0" * 64
    (package / "patch.json").write_text(json.dumps(data))

    assert (
        main(
            [
                "validate-package",
                "--source",
                str(binary),
                "--package",
                str(package),
                "--source-version",
                "fixture",
                "--source-version-output",
                "fixture (Claude Code)",
                "--json",
            ]
        )
        == 1
    )
    payload = read_json(capsys)
    assert payload["ok"] is False
    assert payload["errorCode"] == "module_identity_failed"
    assert payload["diagnosticTargetSelected"] is True
    assert payload["operationDiagnostics"][0]["opId"] == "insert-_A"
    assert payload["operationDiagnostics"][0]["status"] == "candidate_found"
```

- [ ] **Step 5: Implement diagnostic helpers in `builder_v15.py`**

In `/Users/MAC/Documents/Claude-patch/src/claude_monkey/builder_v15.py`, import the diagnostic helper:

```python
from claude_monkey.module_patch import (
    ModulePatchError,
    PlannedModuleOperation,
    diagnose_module_operation,
    plan_module_operations,
    render_changed_module,
)
```

Add these helpers after `target_matches()`:

```python
def _current_source_identity_dict(
    request: ValidationRequestV15, source: bytes
) -> dict[str, Any]:
    return {
        "claudeVersion": request.source_version,
        "versionOutput": request.source_version_output,
        "sha256": hashlib.sha256(source).hexdigest(),
        "sizeBytes": len(source),
        "platform": request.platform,
        "arch": request.arch,
    }


def _source_module_paths(source: bytes) -> set[str] | None:
    try:
        layout = find_macho_layout(source)
        graph = parse_bun_section(
            source[layout.bun_section.offset : layout.bun_section.offset + layout.bun_section.size]
        )
    except (MachOError, BunGraphError):
        return None
    if graph.validation_errors:
        return None
    return {module.path for module in graph.modules}


def _diagnostic_targets(
    manifest: ManifestV2, request: ValidationRequestV15, source: bytes
) -> list[TargetV2]:
    module_paths = _source_module_paths(source)
    return [
        target
        for target in manifest.targets
        if target.source_identity.platform == request.platform
        and target.source_identity.arch == request.arch
        and (
            module_paths is None
            or any(module.path in module_paths for module in target.modules)
        )
    ]


def _target_operation_diagnostics(
    target: TargetV2, source: bytes, manifest_id: str
) -> tuple[list[dict[str, object]], list[str]]:
    diagnostics: list[dict[str, object]] = []
    errors: list[str] = []
    try:
        layout = find_macho_layout(source)
        graph = parse_bun_section(
            source[layout.bun_section.offset : layout.bun_section.offset + layout.bun_section.size]
        )
    except (MachOError, BunGraphError) as exc:
        return diagnostics, [str(exc)]
    if graph.validation_errors:
        return diagnostics, graph.validation_errors
    for module_target in target.modules:
        try:
            module = graph.module_by_path(module_target.path)
        except BunGraphError as exc:
            errors.append(str(exc))
            continue
        for operation in module_target.operations:
            item = diagnose_module_operation(module.content, operation)
            item["packageId"] = manifest_id
            item["modulePath"] = module_target.path
            diagnostics.append(item)
    return diagnostics, errors
```

- [ ] **Step 6: Use diagnostics on validation source and module identity failures**

In `validate_package()`, replace the `if len(matching_targets) != 1:` return block with:

```python
        if len(matching_targets) != 1:
            diagnostic_targets = _diagnostic_targets(manifest, request, source)
            diagnostic_payload: dict[str, Any] = {
                "schemaVersion": 1,
                "ok": False,
                "packageId": manifest.id,
                "errorCode": "source_identity_mismatch",
                "errors": ["source identity did not match exactly"],
                "currentSourceIdentity": _current_source_identity_dict(request, source),
                "diagnosticTargetSelected": False,
                "operationDiagnostics": [],
            }
            if len(diagnostic_targets) == 1:
                diagnostics, diagnostic_errors = _target_operation_diagnostics(
                    diagnostic_targets[0], source, manifest.id
                )
                diagnostic_payload["diagnosticTargetSelected"] = True
                diagnostic_payload["operationDiagnostics"] = diagnostics
                if diagnostic_errors:
                    diagnostic_payload["diagnosticErrors"] = diagnostic_errors
            elif len(diagnostic_targets) > 1:
                diagnostic_payload["diagnosticErrors"] = ["diagnostic_target_ambiguous"]
            return diagnostic_payload
```

In the module identity check inside `validate_package()`, replace the `return` block with:

```python
                diagnostics, diagnostic_errors = _target_operation_diagnostics(
                    target, source, manifest.id
                )
                payload: dict[str, Any] = {
                    "schemaVersion": 1,
                    "ok": False,
                    "packageId": manifest.id,
                    "errorCode": "module_identity_failed",
                    "errors": [module_target.path],
                    "diagnosticTargetSelected": True,
                    "operationDiagnostics": diagnostics,
                }
                if diagnostic_errors:
                    payload["diagnosticErrors"] = diagnostic_errors
                return payload
```

- [ ] **Step 7: Run retarget diagnostic tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_module_patch.py::test_diagnose_module_operation_reports_unique_candidate_without_accepting tests/test_module_patch.py::test_diagnose_module_operation_distinguishes_missing_and_ambiguous_anchor tests/test_module_patch.py::test_diagnose_replace_substring_within_reports_context_and_subspan_failures tests/test_module_patch.py::test_diagnose_replace_substring_within_reports_old_range_evidence tests/test_cli_v15.py::test_validate_package_identity_mismatch_reports_diagnostic_candidates tests/test_cli_v15.py::test_validate_package_identity_mismatch_stops_on_ambiguous_diagnostic_target tests/test_cli_v15.py::test_validate_package_identity_mismatch_ignores_targets_for_missing_module_path tests/test_cli_v15.py::test_validate_package_module_identity_mismatch_reports_operation_diagnostics -q
```

Expected result: PASS.

- [ ] **Step 8: Commit Task 5**

Run:

```bash
git add src/claude_monkey/module_patch.py src/claude_monkey/builder_v15.py tests/test_module_patch.py tests/test_cli_v15.py
git commit -m "Add diagnostic-only splice retarget analysis"
```

Expected result: commit created with only those four files.

## Task 6: Add package relationship metadata

**Files:**
- Modify: `/Users/MAC/Documents/Claude-patch/tests/test_manifest_v2.py`
- Modify: `/Users/MAC/Documents/Claude-patch/tests/test_package_model_v3.py`
- Modify: `/Users/MAC/Documents/Claude-patch/tests/test_builder_v15.py`
- Modify: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/manifest_v2.py`
- Modify: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/package_model.py`
- Modify: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/builder_v15.py`

- [ ] **Step 1: Add manifest-v2 relationship tests**

Append this test to `/Users/MAC/Documents/Claude-patch/tests/test_manifest_v2.py`:

```python

def test_manifest_v2_accepts_package_relationship_fields():
    data = valid_v2_manifest()
    data["requiresPackages"] = ["footer-drawers"]
    data["conflictsWithPackages"] = ["upstream-attachment-suppression"]
    data["provides"] = ["footer-drawer:hiddenContext"]
    data["consumes"] = ["footer-drawers:v1"]

    manifest = load_manifest_v2_dict(data)

    assert manifest.requires_packages == ("footer-drawers",)
    assert manifest.conflicts_with_packages == ("upstream-attachment-suppression",)
    assert manifest.provides == ("footer-drawer:hiddenContext",)
    assert manifest.consumes == ("footer-drawers:v1",)
```

- [ ] **Step 2: Implement relationship fields in `manifest_v2.py`**

Add this helper after `optional_string()`:

```python
def optional_string_list(obj: dict[str, Any], field: str) -> tuple[str, ...]:
    value = obj.get(field, [])
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ManifestV2Error(f"{field} must be a list of non-empty strings")
    return tuple(value)
```

Extend `ManifestV2` with:

```python
    requires_packages: tuple[str, ...]
    conflicts_with_packages: tuple[str, ...]
    provides: tuple[str, ...]
    consumes: tuple[str, ...]
```

In `load_manifest_v2_dict()`, add these fields to the returned dataclass:

```python
        requires_packages=optional_string_list(top, "requiresPackages"),
        conflicts_with_packages=optional_string_list(top, "conflictsWithPackages"),
        provides=optional_string_list(top, "provides"),
        consumes=optional_string_list(top, "consumes"),
```

- [ ] **Step 3: Add package-envelope bridge test**

Append this test to `/Users/MAC/Documents/Claude-patch/tests/test_package_model_v3.py`:

```python

def test_patch_package_relationship_fields_are_preserved(tmp_path):
    package_dir = tmp_path / "relpatch"
    package_dir.mkdir()
    payload = patch_manifest("relpatch")
    payload["requiresPackages"] = ["footer-drawers"]
    payload["conflictsWithPackages"] = ["upstream-attachment-suppression"]
    payload["provides"] = ["footer-drawer:hiddenContext"]
    payload["consumes"] = ["footer-drawers:v1"]
    write_json(package_dir / "relpatch.json", payload)

    loaded = load_package_manifest(package_dir, PackageKind.PATCH)

    assert loaded.patch is not None
    assert loaded.patch.requires_packages == ("footer-drawers",)
    assert loaded.patch.conflicts_with_packages == ("upstream-attachment-suppression",)
    assert loaded.patch.provides == ("footer-drawer:hiddenContext",)
    assert loaded.patch.consumes == ("footer-drawers:v1",)


def test_patch_package_relationship_fields_reject_empty_strings(tmp_path):
    package_dir = tmp_path / "badrel"
    package_dir.mkdir()
    payload = patch_manifest("badrel")
    payload["requiresPackages"] = [""]
    write_json(package_dir / "badrel.json", payload)

    with pytest.raises(
        PackageValidationError, match="requiresPackages_must_be_non_empty_string_list"
    ):
        load_package_manifest(package_dir, PackageKind.PATCH)
```

- [ ] **Step 4: Implement package-envelope relationship fields**

In `/Users/MAC/Documents/Claude-patch/src/claude_monkey/package_model.py`, add these field names to `TOP_LEVEL_FIELDS`:

```python
    "requiresPackages",
    "conflictsWithPackages",
    "provides",
    "consumes",
```

Extend `PatchPackage` with:

```python
    requires_packages: tuple[str, ...] = ()
    conflicts_with_packages: tuple[str, ...] = ()
    provides: tuple[str, ...] = ()
    consumes: tuple[str, ...] = ()
```

Add this helper after `_require_string_list()` so package-envelope relationship metadata has the same non-empty-string invariant as direct schema-v2 manifests:

```python
def _require_non_empty_string_list(obj: dict[str, Any], field: str) -> tuple[str, ...]:
    value = obj.get(field, [])
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        _fail(f"{field}_must_be_non_empty_string_list")
    return tuple(value)
```

Change `_parse_patch()` to accept the top-level manifest mapping and read relationship fields from that top level:

```python
def _parse_patch(value: Any, package_dir: Path, top: dict[str, Any]) -> PatchPackage:
    patch = _require_mapping(value, "patch")
    engine = _require_string(patch, "engine")
    if engine not in SUPPORTED_PATCH_ENGINES:
        _fail("patch_engine_unsupported")
    targets = patch.get("targets")
    if not isinstance(targets, list) or not all(isinstance(item, dict) for item in targets):
        _fail("patch.targets_must_be_object_list")
    _validate_patch_replacement_paths(targets, package_dir)
    return PatchPackage(
        engine=engine,
        targets=tuple(targets),
        requires_packages=_require_non_empty_string_list(top, "requiresPackages"),
        conflicts_with_packages=_require_non_empty_string_list(top, "conflictsWithPackages"),
        provides=_require_non_empty_string_list(top, "provides"),
        consumes=_require_non_empty_string_list(top, "consumes"),
    )
```

In `load_package_manifest_from_dict()`, change the patch call to pass `top`:

```python
        patch = _parse_patch(top.get("patch"), package_dir, top)
```

- [ ] **Step 5: Preserve relationship fields in `_v3_manifest_as_v2_dict()`**

In `/Users/MAC/Documents/Claude-patch/src/claude_monkey/builder_v15.py`, extend the returned dict from `_v3_manifest_as_v2_dict()`:

```python
        "requiresPackages": list(manifest.patch.requires_packages),
        "conflictsWithPackages": list(manifest.patch.conflicts_with_packages),
        "provides": list(manifest.patch.provides),
        "consumes": list(manifest.patch.consumes),
```

- [ ] **Step 6: Add package relationship builder tests**

Append these tests to `/Users/MAC/Documents/Claude-patch/tests/test_builder_v15.py`:

```python

def test_build_patchset_v15_fails_missing_required_package(tmp_path):
    source = tmp_path / "claude-source"
    source.write_bytes(build_aligned_macho_fixture()[0])
    package = tmp_path / "needs-framework"
    write_fixture_package(package, source)
    data = json.loads((package / "patch.json").read_text())
    data["id"] = "needs-framework"
    data["requiresPackages"] = ["footer-drawers"]
    (package / "patch.json").write_text(json.dumps(data))

    report = build_patchset_v15(
        BuildRequestV15(
            source_path=source,
            output_dir=tmp_path / "out",
            package_dirs=[package],
            source_version="fixture",
            source_version_output="fixture (Claude Code)",
            platform="darwin",
            arch="arm64",
            command_runner=successful_runner,
        )
    )

    assert report.status == "failed"
    assert report.failureReason == (
        "patch_conflict:required_package_missing:needs-framework:footer-drawers"
    )


def test_build_patchset_v15_fails_explicit_package_conflict(tmp_path):
    source = tmp_path / "claude-source"
    source.write_bytes(build_aligned_macho_fixture()[0])
    first = tmp_path / "first"
    second = tmp_path / "second"
    write_insert_fixture_package(first, source, "first", 100, "_A")
    write_insert_fixture_package(second, source, "second", 200, "_B")
    data = json.loads((first / "patch.json").read_text())
    data["conflictsWithPackages"] = ["second"]
    (first / "patch.json").write_text(json.dumps(data))

    report = build_patchset_v15(
        BuildRequestV15(
            source_path=source,
            output_dir=tmp_path / "out",
            package_dirs=[first, second],
            source_version="fixture",
            source_version_output="fixture (Claude Code)",
            platform="darwin",
            arch="arm64",
            command_runner=successful_runner,
        )
    )

    assert report.status == "failed"
    assert report.failureReason == "patch_conflict:package_conflict:first:second"
```

- [ ] **Step 7: Implement relationship validation in `builder_v15.py`**

Add this helper near `_select_packages()`:

```python
def _check_package_relationships(selected: list[tuple[Path, ManifestV2, TargetV2]]) -> str | None:
    enabled = {manifest.id for _, manifest, _ in selected}
    for _, manifest, _ in selected:
        for required in manifest.requires_packages:
            if required not in enabled:
                return f"patch_conflict:required_package_missing:{manifest.id}:{required}"
        for conflict in manifest.conflicts_with_packages:
            if conflict in enabled:
                left, right = sorted((manifest.id, conflict))
                return f"patch_conflict:package_conflict:{left}:{right}"
    return None
```

In `build_patchset_v15()`, after `_select_packages()` succeeds and before creating the base report, add:

```python
    relationship_failure = _check_package_relationships(selected)
    if relationship_failure is not None:
        return _write_failed(
            request,
            report_path,
            relationship_failure,
            source=source,
            enabled=[manifest.id for _, manifest, _ in selected],
        )
```

- [ ] **Step 8: Run relationship tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_manifest_v2.py::test_manifest_v2_accepts_package_relationship_fields tests/test_package_model_v3.py::test_patch_package_relationship_fields_are_preserved tests/test_package_model_v3.py::test_patch_package_relationship_fields_reject_empty_strings tests/test_builder_v15.py::test_build_patchset_v15_fails_missing_required_package tests/test_builder_v15.py::test_build_patchset_v15_fails_explicit_package_conflict -q
```

Expected result: PASS.

- [ ] **Step 9: Commit Task 6**

Run:

```bash
git add src/claude_monkey/manifest_v2.py src/claude_monkey/package_model.py src/claude_monkey/builder_v15.py tests/test_manifest_v2.py tests/test_package_model_v3.py tests/test_builder_v15.py
git commit -m "Add package relationship metadata for patch composition"
```

Expected result: commit created with only those files.

## Task 7: Full verification and cleanup

**Files:**
- Modify only if tests reveal necessary corrections in files already changed by Tasks 1-6.

- [ ] **Step 1: Run focused structured-splice tests**

Run:

```bash
.venv/bin/python -m pytest tests/test_manifest_v2.py tests/test_module_patch.py tests/test_builder_v15.py tests/test_cli_v15.py tests/test_package_model_v3.py -q
```

Expected result: PASS.

- [ ] **Step 2: Run broader Python test suite**

Run:

```bash
.venv/bin/python -m pytest -q
```

Expected result: PASS. If unrelated dirty worktree packages introduce failures, capture the failing tests and verify whether they touch files outside this plan before editing anything.

- [ ] **Step 3: Run ruff**

Run:

```bash
.venv/bin/python -m ruff check src tests
```

Expected result: `All checks passed!`

- [ ] **Step 4: Inspect git status**

Run:

```bash
git status --short --branch
```

Expected result: only intentional files from this plan are modified or newly committed. Existing unrelated dirt may still be present and must remain untouched.

- [ ] **Step 5: Commit verification cleanup if needed**

If Step 1-3 required small fixes, commit only the touched implementation/test files:

```bash
git add src/claude_monkey/manifest_v2.py src/claude_monkey/module_patch.py src/claude_monkey/builder_v15.py src/claude_monkey/package_model.py tests/test_manifest_v2.py tests/test_module_patch.py tests/test_builder_v15.py tests/test_cli_v15.py tests/test_package_model_v3.py
git commit -m "Finalize structured splice engine verification"
```

Expected result: either a cleanup commit exists with only plan-owned files, or no commit is needed because verification passed after Task 6.

## Acceptance checklist

The implementation is complete when all of these are true:

- `insert_before` and `insert_after` parse, plan, report, and render as zero-width operations.
- Same-offset insertions render deterministically by `insertOrder`, independent of package CLI order.
- Duplicate same-point `insertOrder` fails closed.
- Structured `anchor` and `subExact` locators are unique-only; expected counts greater than `1` are rejected.
- `replace_between` without both markers still fails closed and never becomes whole-module replacement.
- `replace_substring_within` claims only its subspan and hard-fails on supplied `contextSha256` mismatch during build planning.
- Cross-package non-zero overlaps still fail closed.
- `operationsApplied` and `operationsResolved` include structured operation evidence.
- `BuildReportV2.schemaVersion` remains `3` with additive operation-entry fields and preserved existing keys.
- `validate-package --json` can emit diagnostic-only candidates on identity mismatch while still returning `ok: false`.
- Retarget diagnostics distinguish missing anchors, ambiguous anchors, missing/ambiguous context, missing/ambiguous subspans, changed old-range evidence, and unique candidates whose context hash changed.
- Module identity mismatch can report operation-level diagnostics without accepting the candidate.
- Package relationship metadata works for direct schema-v2 `patch.json` and package-envelope manifests.
- Missing required packages and explicit conflicts fail before operation planning.
- Existing schema-v2 packages still load and validate.
- No code in `bun_graph.py`, `macho.py`, or `repack.py` changed for composition concerns.
- Focused tests pass.
- Broad tests and ruff pass, or any unrelated failures are documented with evidence.
