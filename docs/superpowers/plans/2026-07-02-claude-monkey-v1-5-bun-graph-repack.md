# ClaudeMonkey V1.5 Bun Graph Repack Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace ClaudeMonkey's active byte-slot patch engine with a schema v2 module-coordinate Bun graph repack engine that patches copied Claude Code binaries only, signs/smokes them, writes evidence-rich reports, and rejects V1 whole-binary packages in the V1.5 build path.

**Architecture:** Add the V1.5 engine beside the V1 modules first, then route `build` through the new engine for schema v2 packages and reject schema v1 packages with a migration-required error. Keep binary-format mechanics in focused modules: Mach-O parsing/updating, Bun graph parsing/updating, module patch planning, repack orchestration, inspection JSON, and report serialization. Use synthetic fixtures for normal tests; real Claude Code repack smoke stays opt-in and copied-output-only.

**Tech Stack:** Python 3.11+ standard library, `pytest`, JSON manifests/reports, macOS `codesign` via existing command-runner abstraction, no vendored gist/GPL code.

---

## Preconditions and invariants

Read this spec before starting implementation:

`/Users/MAC/Documents/Claude-patch/docs/superpowers/specs/2026-07-02-claude-monkey-v1-5-bun-graph-repack-design.md`

Hard invariants from the spec:

- No slot strategy.
- No padding path in the V1.5 build engine.
- No same-size/smaller byte budget model.
- No `allowGrowth` flag.
- No `--strategy` flag.
- No `--unverified-candidate` in V1.5.
- No `--skip-identity-check` in V1.5; source/module identity is never bypassed.
- Schema v1 whole-binary packages must be rejected by the V1.5 build path with a migration-required error.
- Schema v2 package authors target Bun module paths and module content identity, not Mach-O/Bun container internals.
- Public gist/project code is research only; do not vendor or copy it.
- Every normal build writes a copied output only. The official Claude binary must remain unchanged.
- Activation requires source identity, module identity, graph validation, operation resolution, static postconditions, signing, post-sign inspection, content-based smoke, and required manual smoke all to pass.

## File structure

Create or modify these files:

```text
src/claude_monkey/manifest_v2.py
src/claude_monkey/module_patch.py
src/claude_monkey/macho.py
src/claude_monkey/bun_graph.py
src/claude_monkey/binary_inspect.py
src/claude_monkey/repack.py
src/claude_monkey/reports_v2.py
src/claude_monkey/smoke.py
src/claude_monkey/cli.py
src/claude_monkey/builder_v15.py

tests/fixtures_bun.py
tests/test_manifest_v2.py
tests/test_module_patch.py
tests/test_macho.py
tests/test_bun_graph.py
tests/test_binary_inspect.py
tests/test_repack.py
tests/test_builder_v15.py
tests/test_cli_v15.py
tests/test_smoke.py

# Conditional only if exact real module evidence is available; see Task 11:
# packages/fable-fallback-v15/README.md
# packages/fable-fallback-v15/patch.json
# packages/fable-fallback-v15/payloads/gcm-assistant-case.js
```

Responsibility map:

- `manifest_v2.py`: schema v2 parsing/validation; no schema v1 compatibility behavior.
- `module_patch.py`: module-local range resolution and changed-module rendering; no binary offsets and no padding.
- `macho.py`: thin little-endian Mach-O 64 parser/updater for synthetic fixtures and local arm64 Claude Code shape.
- `bun_graph.py`: Bun standalone payload parser/updater; graph validation; module map by path.
- `binary_inspect.py`: read-only source inspection and JSON-friendly summaries.
- `repack.py`: combine changed Bun payload and Mach-O metadata into copied output bytes.
- `reports_v2.py`: evidence-rich V1.5 report model.
- `builder_v15.py`: application-level V1.5 build flow, signing, post-sign inspection, smoke, activation eligibility.
- `cli.py`: expose `inspect-binary`, `validate-package`, and V1.5 `build` behavior.
- `fixtures_bun.py`: small deterministic synthetic Mach-O/Bun fixtures for tests.

## Task 1: Add schema v2 manifest models and reject old package shape

**Files:**
- Create: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/manifest_v2.py`
- Create: `/Users/MAC/Documents/Claude-patch/tests/test_manifest_v2.py`

- [ ] **Step 1: Write failing schema v2 manifest tests**

Create `/Users/MAC/Documents/Claude-patch/tests/test_manifest_v2.py`:

```python
from __future__ import annotations

import pytest

from claude_monkey.manifest_v2 import ManifestV2Error, load_manifest_v2_dict


def valid_v2_manifest() -> dict:
    return {
        "schemaVersion": 2,
        "id": "example-v15",
        "name": "Example V1.5 patch",
        "description": "Module-coordinate example",
        "packageVersion": "0.1.0",
        "targets": [
            {
                "sourceIdentity": {
                    "claudeVersion": "2.1.198",
                    "versionOutput": "2.1.198 (Claude Code)",
                    "sha256": "a" * 64,
                    "sizeBytes": 229328464,
                    "platform": "darwin",
                    "arch": "arm64",
                },
                "requiredEngine": "bun_graph_repack",
                "requiredBinaryFormat": "bun_standalone_macho64",
                "modules": [
                    {
                        "path": "/$bunfs/root/src/entrypoints/cli.js",
                        "contentSha256": "b" * 64,
                        "contentLength": 64,
                        "operations": [
                            {
                                "opId": "replace-renderer",
                                "label": "Replace renderer",
                                "type": "replace_between",
                                "startMarker": "function render(){",
                                "endMarker": "function after(){",
                                "expectedStartMarkerCount": 1,
                                "expectedEndMarkerCount": 1,
                                "requireWithinRange": ["OLD_RENDER"],
                                "oldRangeSha256": "c" * 64,
                                "oldRangeLength": 28,
                                "replacement": {"inline": "function render(){NEW_RENDER}\n"},
                                "knownBehaviorChange": "Changes renderer output",
                            }
                        ],
                    }
                ],
                "preconditions": [],
                "postconditions": [
                    {
                        "type": "module_must_contain",
                        "modulePath": "/$bunfs/root/src/entrypoints/cli.js",
                        "value": "NEW_RENDER",
                    }
                ],
                "manualSmoke": {"required": True, "reason": "UI renderer changed"},
            }
        ],
    }


def test_load_manifest_v2_accepts_valid_shape():
    manifest = load_manifest_v2_dict(valid_v2_manifest())
    assert manifest.schema_version == 2
    assert manifest.id == "example-v15"
    target = manifest.targets[0]
    assert target.required_engine == "bun_graph_repack"
    assert target.required_binary_format == "bun_standalone_macho64"
    assert target.modules[0].path == "/$bunfs/root/src/entrypoints/cli.js"
    assert target.modules[0].operations[0].op_id == "replace-renderer"


def test_schema_v1_is_rejected_with_migration_required():
    data = valid_v2_manifest()
    data["schemaVersion"] = 1
    with pytest.raises(ManifestV2Error, match="schema_v1_migration_required"):
        load_manifest_v2_dict(data)


@pytest.mark.parametrize("field", ["requiredEngine", "requiredBinaryFormat", "modules"])
def test_target_requires_engine_and_modules(field):
    data = valid_v2_manifest()
    del data["targets"][0][field]
    with pytest.raises(ManifestV2Error, match=field):
        load_manifest_v2_dict(data)


def test_manifest_v2_rejects_binary_shape_leak():
    data = valid_v2_manifest()
    data["targets"][0]["binaryShape"] = {"moduleRecordSize": 52}
    with pytest.raises(ManifestV2Error, match="binaryShape"):
        load_manifest_v2_dict(data)


def test_manifest_v2_rejects_padding_and_growth_flags():
    data = valid_v2_manifest()
    op = data["targets"][0]["modules"][0]["operations"][0]
    op["padding"] = "spaces"
    with pytest.raises(ManifestV2Error, match="padding"):
        load_manifest_v2_dict(data)
    del op["padding"]
    op["allowGrowth"] = True
    with pytest.raises(ManifestV2Error, match="allowGrowth"):
        load_manifest_v2_dict(data)


def test_manifest_v2_rejects_duplicate_op_ids_across_modules():
    data = valid_v2_manifest()
    module = dict(data["targets"][0]["modules"][0])
    module["path"] = "/$bunfs/root/src/other.js"
    module["operations"] = [dict(module["operations"][0])]
    data["targets"][0]["modules"].append(module)
    with pytest.raises(ManifestV2Error, match="duplicate opId"):
        load_manifest_v2_dict(data)


@pytest.mark.parametrize("bad", ["run_shell", "module_must_contain"])
def test_manifest_v2_rejects_non_mutating_operation_types(bad):
    data = valid_v2_manifest()
    data["targets"][0]["modules"][0]["operations"][0]["type"] = bad
    with pytest.raises(ManifestV2Error, match="unsupported operation type"):
        load_manifest_v2_dict(data)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd /Users/MAC/Documents/Claude-patch
python3 -m pytest tests/test_manifest_v2.py -q
```

Expected: FAIL because `claude_monkey.manifest_v2` does not exist.

- [ ] **Step 3: Implement schema v2 manifest parser**

Create `/Users/MAC/Documents/Claude-patch/src/claude_monkey/manifest_v2.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

HEX_DIGITS = set("0123456789abcdefABCDEF")
SUPPORTED_ENGINES = {"bun_graph_repack"}
SUPPORTED_BINARY_FORMATS = {"bun_standalone_macho64"}
SUPPORTED_OPERATION_TYPES = {"replace_between", "replace_exact"}
SUPPORTED_ASSERTION_TYPES = {
    "module_must_contain",
    "module_must_not_contain",
    "binary_must_contain",
    "binary_must_not_contain",
}
FORBIDDEN_FIELDS = {"binaryShape", "padding", "allowGrowth", "strategy"}


class ManifestV2Error(ValueError):
    pass


@dataclass(frozen=True)
class SourceIdentityV2:
    claude_version: str
    version_output: str
    sha256: str
    size_bytes: int
    platform: str
    arch: str


@dataclass(frozen=True)
class PayloadRefV2:
    inline: str | None = None
    path: str | None = None
    sha256: str | None = None
    encoding: Literal["utf-8", "base64"] = "utf-8"


@dataclass(frozen=True)
class ModuleOperationV2:
    op_id: str
    label: str
    type: str
    start_marker: str | None
    end_marker: str | None
    exact: str | None
    expected_start_marker_count: int
    expected_end_marker_count: int
    require_within_range: tuple[str, ...]
    old_range_sha256: str | None
    old_range_length: int | None
    replacement: PayloadRefV2
    known_behavior_change: str | None


@dataclass(frozen=True)
class ModuleTargetV2:
    path: str
    content_sha256: str
    content_length: int
    operations: tuple[ModuleOperationV2, ...]


@dataclass(frozen=True)
class AssertionV2:
    type: str
    module_path: str | None
    value: str


@dataclass(frozen=True)
class ManualSmokeV2:
    required: bool
    reason: str | None


@dataclass(frozen=True)
class TargetV2:
    source_identity: SourceIdentityV2
    required_engine: str
    required_binary_format: str
    modules: tuple[ModuleTargetV2, ...]
    preconditions: tuple[AssertionV2, ...]
    postconditions: tuple[AssertionV2, ...]
    manual_smoke: ManualSmokeV2


@dataclass(frozen=True)
class ManifestV2:
    schema_version: int
    id: str
    name: str
    description: str
    package_version: str
    targets: tuple[TargetV2, ...]
    raw: dict[str, Any]


def require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ManifestV2Error(f"{label} must be an object")
    for field in FORBIDDEN_FIELDS:
        if field in value:
            raise ManifestV2Error(f"unsupported V1.5 field: {field}")
    return value


def require_string(obj: dict[str, Any], field: str) -> str:
    value = obj.get(field)
    if not isinstance(value, str) or value == "":
        raise ManifestV2Error(f"{field} must be a non-empty string")
    return value


def optional_string(obj: dict[str, Any], field: str) -> str | None:
    value = obj.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ManifestV2Error(f"{field} must be a string")
    return value


def require_int(obj: dict[str, Any], field: str) -> int:
    value = obj.get(field)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ManifestV2Error(f"{field} must be an integer")
    return value


def optional_non_negative_int(obj: dict[str, Any], field: str) -> int | None:
    value = obj.get(field)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ManifestV2Error(f"{field} must be a non-negative integer")
    return value


def require_sha256(value: Any, field: str) -> str:
    if not isinstance(value, str):
        raise ManifestV2Error(f"{field} must be a string")
    if len(value) != 64 or any(ch not in HEX_DIGITS for ch in value):
        raise ManifestV2Error(f"{field} must be 64 hex characters")
    return value


def optional_sha256(obj: dict[str, Any], field: str) -> str | None:
    value = obj.get(field)
    if value is None:
        return None
    return require_sha256(value, field)


def parse_payload(value: Any) -> PayloadRefV2:
    payload = require_mapping(value, "replacement")
    inline = payload.get("inline")
    path = payload.get("path")
    sha256 = payload.get("sha256")
    encoding = payload.get("encoding", "utf-8")
    if encoding not in {"utf-8", "base64"}:
        raise ManifestV2Error("replacement.encoding must be utf-8 or base64")
    if inline is not None and not isinstance(inline, str):
        raise ManifestV2Error("replacement.inline must be a string")
    if path is not None and not isinstance(path, str):
        raise ManifestV2Error("replacement.path must be a string")
    if (inline is None) == (path is None):
        raise ManifestV2Error("replacement must provide exactly one of inline or path")
    if path is not None and sha256 is None:
        raise ManifestV2Error("replacement.path requires replacement.sha256")
    return PayloadRefV2(
        inline=inline,
        path=path,
        sha256=require_sha256(sha256, "replacement.sha256") if sha256 is not None else None,
        encoding=encoding,
    )


def parse_source_identity(value: Any) -> SourceIdentityV2:
    item = require_mapping(value, "sourceIdentity")
    return SourceIdentityV2(
        claude_version=require_string(item, "claudeVersion"),
        version_output=require_string(item, "versionOutput"),
        sha256=require_sha256(item.get("sha256"), "sha256"),
        size_bytes=require_int(item, "sizeBytes"),
        platform=require_string(item, "platform"),
        arch=require_string(item, "arch"),
    )


def parse_operation(value: Any) -> ModuleOperationV2:
    op = require_mapping(value, "operation")
    op_type = require_string(op, "type")
    if op_type not in SUPPORTED_OPERATION_TYPES:
        raise ManifestV2Error(f"unsupported operation type: {op_type}")
    require_within = op.get("requireWithinRange", [])
    if not isinstance(require_within, list) or not all(isinstance(x, str) for x in require_within):
        raise ManifestV2Error("requireWithinRange must be a list of strings")
    return ModuleOperationV2(
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
    )


def parse_module(value: Any) -> ModuleTargetV2:
    module = require_mapping(value, "module")
    operations = module.get("operations")
    if not isinstance(operations, list) or not operations:
        raise ManifestV2Error("operations must be a non-empty list")
    return ModuleTargetV2(
        path=require_string(module, "path"),
        content_sha256=require_sha256(module.get("contentSha256"), "contentSha256"),
        content_length=require_int(module, "contentLength"),
        operations=tuple(parse_operation(item) for item in operations),
    )


def parse_assertion(value: Any) -> AssertionV2:
    assertion = require_mapping(value, "assertion")
    assertion_type = require_string(assertion, "type")
    if assertion_type not in SUPPORTED_ASSERTION_TYPES:
        raise ManifestV2Error(f"unsupported assertion type: {assertion_type}")
    module_path = optional_string(assertion, "modulePath")
    if assertion_type.startswith("module_") and module_path is None:
        raise ManifestV2Error("module assertion requires modulePath")
    if assertion_type.startswith("binary_") and module_path is not None:
        raise ManifestV2Error("binary assertion must not include modulePath")
    return AssertionV2(
        type=assertion_type,
        module_path=module_path,
        value=require_string(assertion, "value"),
    )


def parse_manual_smoke(value: Any) -> ManualSmokeV2:
    if value is None:
        return ManualSmokeV2(required=False, reason=None)
    smoke = require_mapping(value, "manualSmoke")
    required = smoke.get("required", False)
    if not isinstance(required, bool):
        raise ManifestV2Error("manualSmoke.required must be a boolean")
    reason = optional_string(smoke, "reason")
    if required and not reason:
        raise ManifestV2Error("manualSmoke.reason is required when manual smoke is required")
    return ManualSmokeV2(required=required, reason=reason)


def parse_target(value: Any) -> TargetV2:
    target = require_mapping(value, "target")
    engine = require_string(target, "requiredEngine")
    if engine not in SUPPORTED_ENGINES:
        raise ManifestV2Error(f"unsupported requiredEngine: {engine}")
    binary_format = require_string(target, "requiredBinaryFormat")
    if binary_format not in SUPPORTED_BINARY_FORMATS:
        raise ManifestV2Error(f"unsupported requiredBinaryFormat: {binary_format}")
    modules_raw = target.get("modules")
    if not isinstance(modules_raw, list) or not modules_raw:
        raise ManifestV2Error("modules must be a non-empty list")
    return TargetV2(
        source_identity=parse_source_identity(target.get("sourceIdentity")),
        required_engine=engine,
        required_binary_format=binary_format,
        modules=tuple(parse_module(item) for item in modules_raw),
        preconditions=tuple(parse_assertion(item) for item in target.get("preconditions", [])),
        postconditions=tuple(parse_assertion(item) for item in target.get("postconditions", [])),
        manual_smoke=parse_manual_smoke(target.get("manualSmoke")),
    )


def load_manifest_v2_dict(data: dict[str, Any]) -> ManifestV2:
    top = require_mapping(data, "manifest")
    schema = top.get("schemaVersion")
    if schema == 1:
        raise ManifestV2Error("schema_v1_migration_required")
    if schema != 2:
        raise ManifestV2Error("schemaVersion must be 2")
    targets = top.get("targets")
    if not isinstance(targets, list) or not targets:
        raise ManifestV2Error("targets must be a non-empty list")
    parsed_targets = tuple(parse_target(item) for item in targets)
    seen_ops: set[str] = set()
    for target in parsed_targets:
        seen_modules: set[str] = set()
        for module in target.modules:
            if module.path in seen_modules:
                raise ManifestV2Error(f"duplicate module path: {module.path}")
            seen_modules.add(module.path)
            for operation in module.operations:
                if operation.op_id in seen_ops:
                    raise ManifestV2Error(f"duplicate opId: {operation.op_id}")
                seen_ops.add(operation.op_id)
    return ManifestV2(
        schema_version=2,
        id=require_string(top, "id"),
        name=require_string(top, "name"),
        description=require_string(top, "description"),
        package_version=require_string(top, "packageVersion"),
        targets=parsed_targets,
        raw=data,
    )
```

- [ ] **Step 4: Run schema tests**

Run:

```bash
cd /Users/MAC/Documents/Claude-patch
python3 -m pytest tests/test_manifest_v2.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit schema v2 parser**

```bash
cd /Users/MAC/Documents/Claude-patch
git add src/claude_monkey/manifest_v2.py tests/test_manifest_v2.py
git commit -m "Add ClaudeMonkey schema v2 manifest parser"
```

## Task 2: Add deterministic synthetic Bun/Mach-O fixtures

**Files:**
- Create: `/Users/MAC/Documents/Claude-patch/tests/fixtures_bun.py`
- Create: `/Users/MAC/Documents/Claude-patch/tests/test_bun_graph.py`
- Create: `/Users/MAC/Documents/Claude-patch/tests/test_macho.py`

- [ ] **Step 1: Write fixture helper**

Create `/Users/MAC/Documents/Claude-patch/tests/fixtures_bun.py`:

```python
from __future__ import annotations

import struct
from dataclasses import dataclass

TRAILER = b"\n---- Bun! ----\n"
MACHO_MAGIC_64 = 0xFEEDFACF
LC_SEGMENT_64 = 0x19
LC_CODE_SIGNATURE = 0x1D
CPU_TYPE_ARM64 = 0x0100000C
CPU_SUBTYPE_ARM64_ALL = 0
MH_EXECUTE = 2

MODULE_PATH_0 = "/$bunfs/root/src/entrypoints/cli.js"
MODULE_PATH_1 = "/$bunfs/root/src/other.js"
MODULE_0 = b"function render(){OLD_RENDER}\nfunction after(){return 1}\n"
MODULE_1 = b"export const other = true;\n"


@dataclass(frozen=True)
class FixtureOffsets:
    bun_fileoff: int
    bun_size: int
    linkedit_fileoff: int
    code_signature_offset: int
    module0_content_offset: int
    module1_content_offset: int


def u32(value: int) -> bytes:
    return struct.pack("<I", value)


def u64(value: int) -> bytes:
    return struct.pack("<Q", value)


def pad_name(value: bytes) -> bytes:
    return value + (b"\0" * (16 - len(value)))


def module_record(path_off: int, path_len: int, content_off: int, content_len: int) -> bytes:
    pairs = [
        (path_off, path_len),
        (content_off, content_len),
        (0, 0),
        (0, 0),
        (0, 0),
        (0, 0),
    ]
    raw = b"".join(u32(off) + u32(size) for off, size in pairs)
    return raw + u32(0x00030201)


def build_payload() -> tuple[bytes, FixtureOffsets]:
    path0 = MODULE_PATH_0.encode("utf-8")
    path1 = MODULE_PATH_1.encode("utf-8")
    chunks = bytearray()
    path0_off = len(chunks); chunks.extend(path0)
    content0_off = len(chunks); chunks.extend(MODULE_0)
    path1_off = len(chunks); chunks.extend(path1)
    content1_off = len(chunks); chunks.extend(MODULE_1)
    modules_offset = len(chunks)
    records = module_record(path0_off, len(path0), content0_off, len(MODULE_0))
    records += module_record(path1_off, len(path1), content1_off, len(MODULE_1))
    chunks.extend(records)
    byte_count = len(chunks)
    chunks.extend(u64(byte_count))
    chunks.extend(u32(modules_offset))
    chunks.extend(u32(len(records)))
    chunks.extend(u32(0))
    chunks.extend(u32(0))
    chunks.extend(u32(0))
    chunks.extend(u32(0))
    chunks.extend(TRAILER)
    payload = bytes(chunks)
    return u64(len(payload)) + payload, FixtureOffsets(
        bun_fileoff=0,
        bun_size=0,
        linkedit_fileoff=0,
        code_signature_offset=0,
        module0_content_offset=content0_off,
        module1_content_offset=content1_off,
    )


def segment_command(segname: bytes, vmaddr: int, vmsize: int, fileoff: int, filesize: int, sections: list[bytes]) -> bytes:
    cmdsize = 72 + 80 * len(sections)
    return b"".join([
        u32(LC_SEGMENT_64), u32(cmdsize), pad_name(segname),
        u64(vmaddr), u64(vmsize), u64(fileoff), u64(filesize),
        u32(7), u32(5), u32(len(sections)), u32(0), *sections,
    ])


def section(sectname: bytes, segname: bytes, addr: int, size: int, offset: int) -> bytes:
    return b"".join([
        pad_name(sectname), pad_name(segname), u64(addr), u64(size), u32(offset),
        u32(0), u32(0), u32(0), u32(0), u32(0), u32(0), u32(0),
    ])


def code_signature_command(dataoff: int, datasize: int) -> bytes:
    return u32(LC_CODE_SIGNATURE) + u32(16) + u32(dataoff) + u32(datasize)


def build_macho_fixture() -> tuple[bytes, FixtureOffsets]:
    bun_section, partial = build_payload()
    header_size = 32
    bun_fileoff = 0x4000
    linkedit_fileoff = 0x8000
    code_sig_size = 128
    code_sig_offset = linkedit_fileoff
    bun_size = len(bun_section)
    text = segment_command(b"__TEXT", 0x100000000, 0x4000, 0, 0x4000, [])
    bun_sec = section(b"__bun", b"__BUN", 0x100004000, bun_size, bun_fileoff)
    bun = segment_command(b"__BUN", 0x100004000, bun_size, bun_fileoff, bun_size, [bun_sec])
    linkedit = segment_command(b"__LINKEDIT", 0x100008000, code_sig_size, linkedit_fileoff, code_sig_size, [])
    code_sig = code_signature_command(code_sig_offset, code_sig_size)
    load_commands = text + bun + linkedit + code_sig
    ncmds = 4
    header = struct.pack(
        "<IiiIIIII",
        MACHO_MAGIC_64,
        CPU_TYPE_ARM64,
        CPU_SUBTYPE_ARM64_ALL,
        MH_EXECUTE,
        ncmds,
        len(load_commands),
        0,
        0,
    )
    prefix = header + load_commands
    data = bytearray(prefix)
    data.extend(b"\0" * (bun_fileoff - len(data)))
    data.extend(bun_section)
    data.extend(b"\0" * (linkedit_fileoff - len(data)))
    data.extend(b"C" * code_sig_size)
    return bytes(data), FixtureOffsets(
        bun_fileoff=bun_fileoff,
        bun_size=bun_size,
        linkedit_fileoff=linkedit_fileoff,
        code_signature_offset=code_sig_offset,
        module0_content_offset=partial.module0_content_offset,
        module1_content_offset=partial.module1_content_offset,
    )
```

- [ ] **Step 2: Write parser placeholder tests that will fail**

Create `/Users/MAC/Documents/Claude-patch/tests/test_bun_graph.py`:

```python
from __future__ import annotations

import pytest

from tests.fixtures_bun import MODULE_PATH_0, TRAILER, build_payload

from claude_monkey.bun_graph import BunGraphError, parse_bun_section


def test_parse_bun_section_lists_modules():
    section, _ = build_payload()
    graph = parse_bun_section(section)
    assert graph.declared_payload_len == len(section) - 8
    assert graph.module_record_size == 52
    assert graph.modules[0].path == MODULE_PATH_0
    assert graph.modules[0].content.startswith(b"function render")
    assert graph.validation_errors == []


def test_parse_bun_section_rejects_bad_trailer():
    section, _ = build_payload()
    bad = section.replace(TRAILER, b"\n---- Bad! ----\n")
    with pytest.raises(BunGraphError, match="trailer"):
        parse_bun_section(bad)
```

Create `/Users/MAC/Documents/Claude-patch/tests/test_macho.py`:

```python
from __future__ import annotations

from tests.fixtures_bun import build_macho_fixture

from claude_monkey.macho import find_macho_layout


def test_find_macho_layout_locates_bun_and_linkedit():
    data, offsets = build_macho_fixture()
    layout = find_macho_layout(data)
    assert layout.bun_segment.fileoff == offsets.bun_fileoff
    assert layout.bun_section.offset == offsets.bun_fileoff
    assert layout.linkedit_segment.fileoff == offsets.linkedit_fileoff
    assert layout.code_signature.dataoff == offsets.code_signature_offset
```

- [ ] **Step 3: Run fixture parser tests to verify missing modules fail**

Run:

```bash
cd /Users/MAC/Documents/Claude-patch
python3 -m pytest tests/test_bun_graph.py tests/test_macho.py -q
```

Expected: FAIL because `claude_monkey.bun_graph` and `claude_monkey.macho` do not exist.

- [ ] **Step 4: Commit synthetic fixtures and failing tests only if your workflow allows red commits**

If using strict red/green local commits, skip this commit and continue to Task 3. If preserving red test evidence is desired:

```bash
cd /Users/MAC/Documents/Claude-patch
git add tests/fixtures_bun.py tests/test_bun_graph.py tests/test_macho.py
git commit -m "Add synthetic Bun standalone fixtures"
```

## Task 3: Implement Mach-O parser and updater foundation

**Files:**
- Create: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/macho.py`
- Modify: `/Users/MAC/Documents/Claude-patch/tests/test_macho.py`

- [ ] **Step 1: Extend Mach-O tests for updates**

Append to `/Users/MAC/Documents/Claude-patch/tests/test_macho.py`:

```python

def test_shift_layout_grows_bun_and_moves_linkedit():
    data, offsets = build_macho_fixture()
    from claude_monkey.macho import shift_macho_after_bun_change

    shifted, updates = shift_macho_after_bun_change(data, insert_abs=offsets.bun_fileoff + 32, delta=64)
    layout = find_macho_layout(shifted)
    assert layout.bun_segment.filesize == offsets.bun_size + 64
    assert layout.bun_section.size == offsets.bun_size + 64
    assert layout.linkedit_segment.fileoff == offsets.linkedit_fileoff + 64
    assert layout.code_signature.dataoff == offsets.code_signature_offset + 64
    assert any(item["field"] == "LC_CODE_SIGNATURE.dataoff" for item in updates)
```

- [ ] **Step 2: Implement `macho.py`**

Create `/Users/MAC/Documents/Claude-patch/src/claude_monkey/macho.py` with focused parser/update code:

```python
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Any

MACHO_MAGIC_64_LE = 0xFEEDFACF
LC_SEGMENT_64 = 0x19
LC_CODE_SIGNATURE = 0x1D
LC_SYMTAB = 0x2
LC_DYSYMTAB = 0xB
LC_DYLD_INFO = 0x22
LC_DYLD_INFO_ONLY = 0x80000022
LINKEDIT_DATA_CMDS = {0x26, 0x29, 0x2B, 0x2E, 0x32, 0x33, 0x34, 0x35, 0x80000033, 0x80000034}


class MachOError(ValueError):
    pass


@dataclass(frozen=True)
class Segment64:
    command_offset: int
    name: str
    vmaddr: int
    vmsize: int
    fileoff: int
    filesize: int
    nsects: int


@dataclass(frozen=True)
class Section64:
    command_offset: int
    name: str
    segname: str
    addr: int
    size: int
    offset: int


@dataclass(frozen=True)
class LinkeditData:
    command_offset: int
    dataoff: int
    datasize: int


@dataclass(frozen=True)
class MachOLayout:
    commands: tuple[tuple[int, int, int, int], ...]
    bun_segment: Segment64
    bun_section: Section64
    linkedit_segment: Segment64
    code_signature: LinkeditData


def u32(data: bytes | bytearray, off: int) -> int:
    return struct.unpack_from("<I", data, off)[0]


def u64(data: bytes | bytearray, off: int) -> int:
    return struct.unpack_from("<Q", data, off)[0]


def _name(raw: bytes) -> str:
    return raw.split(b"\0", 1)[0].decode("utf-8", "replace")


def find_macho_layout(data: bytes | bytearray) -> MachOLayout:
    if len(data) < 32 or u32(data, 0) != MACHO_MAGIC_64_LE:
        raise MachOError("unsupported_macho_magic")
    _magic, _cputype, _cpusubtype, _filetype, ncmds, sizeofcmds, _flags, _reserved = struct.unpack_from("<IiiIIIII", data, 0)
    commands: list[tuple[int, int, int, int]] = []
    bun_segment: Segment64 | None = None
    linkedit_segment: Segment64 | None = None
    bun_section: Section64 | None = None
    code_signature: LinkeditData | None = None
    off = 32
    end = 32 + sizeofcmds
    for index in range(ncmds):
        if off + 8 > len(data) or off >= end:
            raise MachOError("load_command_out_of_bounds")
        cmd, cmdsize = struct.unpack_from("<II", data, off)
        if cmdsize < 8 or off + cmdsize > len(data):
            raise MachOError("invalid_load_command_size")
        commands.append((index, off, cmd, cmdsize))
        if cmd == LC_SEGMENT_64:
            name = _name(struct.unpack_from("16s", data, off + 8)[0])
            vmaddr, vmsize, fileoff, filesize = struct.unpack_from("<QQQQ", data, off + 24)
            nsects = u32(data, off + 64)
            segment = Segment64(off, name, vmaddr, vmsize, fileoff, filesize, nsects)
            if name == "__BUN":
                bun_segment = segment
            elif name == "__LINKEDIT":
                linkedit_segment = segment
            section_off = off + 72
            for section_index in range(nsects):
                so = section_off + section_index * 80
                sect_name = _name(struct.unpack_from("16s", data, so)[0])
                seg_name = _name(struct.unpack_from("16s", data, so + 16)[0])
                addr, size = struct.unpack_from("<QQ", data, so + 32)
                file_offset = u32(data, so + 48)
                section = Section64(so, sect_name, seg_name, addr, size, file_offset)
                if seg_name == "__BUN" and sect_name == "__bun":
                    bun_section = section
        elif cmd == LC_CODE_SIGNATURE:
            code_signature = LinkeditData(off, u32(data, off + 8), u32(data, off + 12))
        off += cmdsize
    if bun_segment is None or bun_section is None or linkedit_segment is None or code_signature is None:
        raise MachOError("missing_required_macho_layout")
    return MachOLayout(tuple(commands), bun_segment, bun_section, linkedit_segment, code_signature)


def _bump_u32(data: bytearray, pos: int, threshold: int, delta: int, field: str, updates: list[dict[str, Any]]) -> None:
    value = u32(data, pos)
    if value >= threshold:
        struct.pack_into("<I", data, pos, value + delta)
        updates.append({"field": field, "old": value, "new": value + delta})


def shift_macho_after_bun_change(data: bytes | bytearray, *, insert_abs: int, delta: int) -> tuple[bytes, list[dict[str, Any]]]:
    out = bytearray(data)
    layout = find_macho_layout(out)
    updates: list[dict[str, Any]] = []
    bun = layout.bun_segment
    section = layout.bun_section
    linkedit = layout.linkedit_segment
    struct.pack_into("<Q", out, bun.command_offset + 32, bun.vmsize + delta)
    struct.pack_into("<Q", out, bun.command_offset + 48, bun.filesize + delta)
    struct.pack_into("<Q", out, section.command_offset + 40, section.size + delta)
    struct.pack_into("<Q", out, linkedit.command_offset + 24, linkedit.vmaddr + delta)
    struct.pack_into("<Q", out, linkedit.command_offset + 40, linkedit.fileoff + delta)
    updates.extend([
        {"field": "__BUN.vmsize", "old": bun.vmsize, "new": bun.vmsize + delta},
        {"field": "__BUN.filesize", "old": bun.filesize, "new": bun.filesize + delta},
        {"field": "__bun.size", "old": section.size, "new": section.size + delta},
        {"field": "__LINKEDIT.vmaddr", "old": linkedit.vmaddr, "new": linkedit.vmaddr + delta},
        {"field": "__LINKEDIT.fileoff", "old": linkedit.fileoff, "new": linkedit.fileoff + delta},
    ])
    for index, command_offset, cmd, _cmdsize in layout.commands:
        if cmd in (LC_DYLD_INFO, LC_DYLD_INFO_ONLY):
            for field_index, name in enumerate(["rebase_off", "bind_off", "weak_bind_off", "lazy_bind_off", "export_off"]):
                _bump_u32(out, command_offset + 8 + field_index * 8, insert_abs, delta, f"cmd{index}.{name}", updates)
        elif cmd == LC_SYMTAB:
            _bump_u32(out, command_offset + 8, insert_abs, delta, f"cmd{index}.symoff", updates)
            _bump_u32(out, command_offset + 16, insert_abs, delta, f"cmd{index}.stroff", updates)
        elif cmd == LC_DYSYMTAB:
            for rel, name in [(32, "tocoff"), (40, "modtaboff"), (48, "extrefsymoff"), (56, "indirectsymoff"), (64, "extreloff"), (72, "locreloff")]:
                _bump_u32(out, command_offset + rel, insert_abs, delta, f"cmd{index}.{name}", updates)
        elif cmd == LC_CODE_SIGNATURE:
            _bump_u32(out, command_offset + 8, insert_abs, delta, "LC_CODE_SIGNATURE.dataoff", updates)
        elif cmd in LINKEDIT_DATA_CMDS:
            _bump_u32(out, command_offset + 8, insert_abs, delta, f"cmd{index}.dataoff", updates)
    return bytes(out), updates
```

- [ ] **Step 3: Run Mach-O tests**

Run:

```bash
cd /Users/MAC/Documents/Claude-patch
python3 -m pytest tests/test_macho.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit Mach-O foundation**

```bash
cd /Users/MAC/Documents/Claude-patch
git add src/claude_monkey/macho.py tests/fixtures_bun.py tests/test_macho.py
git commit -m "Add Mach-O layout parser for repack engine"
```

## Task 4: Implement Bun standalone graph parser and module updater

**Files:**
- Create: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/bun_graph.py`
- Modify: `/Users/MAC/Documents/Claude-patch/tests/test_bun_graph.py`

- [ ] **Step 1: Extend graph tests for changed modules**

Append to `/Users/MAC/Documents/Claude-patch/tests/test_bun_graph.py`:

```python

def test_replace_module_content_updates_graph_and_shifts_later_offsets():
    section, offsets = build_payload()
    graph = parse_bun_section(section)
    old_module1_offset = graph.modules[1].content_offset
    changed = graph.replace_module_content(MODULE_PATH_0, b"function render(){NEW_RENDER_LONGER}\nfunction after(){return 1}\n")
    reparsed = parse_bun_section(changed.section_bytes)
    assert reparsed.module_by_path(MODULE_PATH_0).content == b"function render(){NEW_RENDER_LONGER}\nfunction after(){return 1}\n"
    assert reparsed.modules[1].content_offset > old_module1_offset
    assert changed.delta > 0
    assert changed.validation_errors == []


def test_module_by_path_requires_unique_path():
    section, _ = build_payload()
    graph = parse_bun_section(section)
    with pytest.raises(BunGraphError, match="module_not_found"):
        graph.module_by_path("/$bunfs/root/src/missing.js")


def test_parse_bun_section_rejects_module_table_size_not_divisible_by_52():
    section, _ = build_payload()
    payload = bytearray(section)
    trailer_off = bytes(payload[8:]).rfind(TRAILER)
    offsets_off = 8 + trailer_off - 32
    # modules_size is at offsets struct + 12. Make it invalid.
    payload[offsets_off + 12 : offsets_off + 16] = (53).to_bytes(4, "little")
    with pytest.raises(BunGraphError, match="bun_module_table_invalid"):
        parse_bun_section(bytes(payload))


def test_parse_bun_section_rejects_pointer_out_of_bounds():
    section, _ = build_payload()
    payload = bytearray(section)
    trailer_off = bytes(payload[8:]).rfind(TRAILER)
    offsets_off = 8 + trailer_off - 32
    modules_offset = int.from_bytes(payload[offsets_off + 8 : offsets_off + 12], "little")
    first_record = 8 + modules_offset
    payload[first_record + 8 : first_record + 12] = (999999).to_bytes(4, "little")
    with pytest.raises(BunGraphError, match="pointer_out_of_bounds"):
        parse_bun_section(bytes(payload))


def test_parse_bun_section_does_not_apply_content_plus_8_assumption():
    section, _ = build_payload()
    graph = parse_bun_section(section)
    module = graph.module_by_path(MODULE_PATH_0)
    assert module.content.startswith(b"function render")
    assert not module.content[0:1] == b" "
```

- [ ] **Step 2: Implement `bun_graph.py`**

Create `/Users/MAC/Documents/Claude-patch/src/claude_monkey/bun_graph.py` with dataclasses and parser/update logic. Keep implementation small and fixture-driven; do not copy public gist code.

```python
from __future__ import annotations

import struct
from dataclasses import dataclass

TRAILER = b"\n---- Bun! ----\n"
MODULE_RECORD_SIZE = 52
POINTER_PAIR_COUNT = 6


class BunGraphError(ValueError):
    pass


@dataclass(frozen=True)
class PointerPair:
    offset: int
    size: int


@dataclass(frozen=True)
class BunModule:
    index: int
    record_offset: int
    path: str
    path_offset: int
    path_size: int
    content_offset: int
    content_size: int
    content: bytes
    raw_u32: tuple[int, ...]


@dataclass(frozen=True)
class BunGraphRewriteResult:
    section_bytes: bytes
    delta: int
    old_payload_length: int
    new_payload_length: int
    old_byte_count: int
    new_byte_count: int
    shifted_pointers: int
    validation_errors: list[str]


@dataclass(frozen=True)
class BunGraph:
    section_bytes: bytes
    declared_payload_len: int
    payload: bytes
    trailer_offset: int
    offsets_struct_offset: int
    byte_count: int
    modules_offset: int
    modules_size: int
    entry_point_id: int
    compile_exec_argv_offset: int
    compile_exec_argv_size: int
    flags: int
    module_record_size: int
    modules: tuple[BunModule, ...]
    validation_errors: list[str]

    def module_by_path(self, path: str) -> BunModule:
        matches = [module for module in self.modules if module.path == path]
        if len(matches) != 1:
            raise BunGraphError(f"module_not_found_or_not_unique:{path}")
        return matches[0]

    def replace_module_content(self, path: str, new_content: bytes) -> BunGraphRewriteResult:
        module = self.module_by_path(path)
        start = module.content_offset
        end = module.content_offset + module.content_size
        payload = bytearray(self.payload)
        payload[start:end] = new_content
        delta = len(new_content) - module.content_size
        insert_point = end
        new_modules_offset = self.modules_offset + delta if self.modules_offset >= insert_point else self.modules_offset
        new_offsets_struct_offset = self.offsets_struct_offset + delta if self.offsets_struct_offset >= insert_point else self.offsets_struct_offset
        shifted = 0
        for index in range(len(self.modules)):
            rec = new_modules_offset + index * MODULE_RECORD_SIZE
            for pair in range(POINTER_PAIR_COUNT):
                pos = rec + pair * 8
                ptr = _u32(payload, pos)
                size = _u32(payload, pos + 4)
                if ptr <= start < ptr + size:
                    struct.pack_into("<I", payload, pos + 4, size + delta)
                elif ptr >= insert_point and ptr != 0:
                    struct.pack_into("<I", payload, pos, ptr + delta)
                    shifted += 1
        struct.pack_into("<Q", payload, new_offsets_struct_offset, self.byte_count + delta)
        struct.pack_into("<I", payload, new_offsets_struct_offset + 8, new_modules_offset)
        struct.pack_into("<I", payload, new_offsets_struct_offset + 12, self.modules_size)
        struct.pack_into("<I", payload, new_offsets_struct_offset + 16, self.entry_point_id)
        argv_offset = self.compile_exec_argv_offset
        if argv_offset >= insert_point and argv_offset != 0:
            argv_offset += delta
            shifted += 1
        struct.pack_into("<I", payload, new_offsets_struct_offset + 20, argv_offset)
        struct.pack_into("<I", payload, new_offsets_struct_offset + 24, self.compile_exec_argv_size)
        struct.pack_into("<I", payload, new_offsets_struct_offset + 28, self.flags)
        section = struct.pack("<Q", self.declared_payload_len + delta) + bytes(payload)
        reparsed = parse_bun_section(section)
        return BunGraphRewriteResult(
            section_bytes=section,
            delta=delta,
            old_payload_length=self.declared_payload_len,
            new_payload_length=self.declared_payload_len + delta,
            old_byte_count=self.byte_count,
            new_byte_count=self.byte_count + delta,
            shifted_pointers=shifted,
            validation_errors=reparsed.validation_errors,
        )


def _u32(data: bytes | bytearray, offset: int) -> int:
    return struct.unpack_from("<I", data, offset)[0]


def _u64(data: bytes | bytearray, offset: int) -> int:
    return struct.unpack_from("<Q", data, offset)[0]


def _slice(data: bytes, offset: int, size: int) -> bytes:
    if offset < 0 or size < 0 or offset + size > len(data):
        raise BunGraphError("pointer_out_of_bounds")
    return data[offset : offset + size]


def parse_bun_section(section: bytes) -> BunGraph:
    if len(section) < 8:
        raise BunGraphError("section_too_short")
    declared_len = _u64(section, 0)
    if declared_len + 8 > len(section):
        raise BunGraphError("payload_length_out_of_bounds")
    payload = section[8 : 8 + declared_len]
    trailer_offset = payload.rfind(TRAILER)
    if trailer_offset < 0:
        raise BunGraphError("trailer_not_found")
    if trailer_offset + len(TRAILER) != declared_len:
        raise BunGraphError("payload_length_trailer_mismatch")
    offsets_struct_offset = trailer_offset - 32
    if offsets_struct_offset < 0:
        raise BunGraphError("offsets_struct_missing")
    byte_count = _u64(payload, offsets_struct_offset)
    modules_offset = _u32(payload, offsets_struct_offset + 8)
    modules_size = _u32(payload, offsets_struct_offset + 12)
    entry_point_id = _u32(payload, offsets_struct_offset + 16)
    argv_offset = _u32(payload, offsets_struct_offset + 20)
    argv_size = _u32(payload, offsets_struct_offset + 24)
    flags = _u32(payload, offsets_struct_offset + 28)
    if modules_size % MODULE_RECORD_SIZE != 0:
        raise BunGraphError("bun_module_table_invalid")
    module_count = modules_size // MODULE_RECORD_SIZE
    modules: list[BunModule] = []
    validation_errors: list[str] = []
    for index in range(module_count):
        rec = modules_offset + index * MODULE_RECORD_SIZE
        if rec + MODULE_RECORD_SIZE > len(payload):
            raise BunGraphError("module_record_out_of_bounds")
        fields = tuple(_u32(payload, rec + i * 4) for i in range(13))
        path_offset, path_size = fields[0], fields[1]
        content_offset, content_size = fields[2], fields[3]
        try:
            path = _slice(payload, path_offset, path_size).decode("utf-8")
            content = _slice(payload, content_offset, content_size)
        except UnicodeDecodeError as exc:
            raise BunGraphError("module_path_not_utf8") from exc
        if not path.startswith("/$bunfs/") and not path.startswith("file:///$bunfs/"):
            validation_errors.append(f"module {index} suspicious path {path!r}")
        if content_offset + content_size > byte_count:
            validation_errors.append(f"module {index} content out of byte_count")
        modules.append(BunModule(index, rec, path, path_offset, path_size, content_offset, content_size, content, fields))
    return BunGraph(
        section_bytes=section,
        declared_payload_len=declared_len,
        payload=payload,
        trailer_offset=trailer_offset,
        offsets_struct_offset=offsets_struct_offset,
        byte_count=byte_count,
        modules_offset=modules_offset,
        modules_size=modules_size,
        entry_point_id=entry_point_id,
        compile_exec_argv_offset=argv_offset,
        compile_exec_argv_size=argv_size,
        flags=flags,
        module_record_size=MODULE_RECORD_SIZE,
        modules=tuple(modules),
        validation_errors=validation_errors,
    )
```

- [ ] **Step 3: Run Bun graph tests**

Run:

```bash
cd /Users/MAC/Documents/Claude-patch
python3 -m pytest tests/test_bun_graph.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit Bun graph parser/updater**

```bash
cd /Users/MAC/Documents/Claude-patch
git add src/claude_monkey/bun_graph.py tests/test_bun_graph.py
git commit -m "Add Bun standalone graph parser"
```

## Task 5: Add module-coordinate patch planner

**Files:**
- Create: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/module_patch.py`
- Create: `/Users/MAC/Documents/Claude-patch/tests/test_module_patch.py`

- [ ] **Step 1: Write failing module patch tests**

Create `/Users/MAC/Documents/Claude-patch/tests/test_module_patch.py`:

```python
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
    planned = plan_module_operations("pkg", "/$bunfs/root/src/entrypoints/cli.js", MODULE, [(op(replacement), replacement)])
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
        plan_module_operations("pkg", "/$bunfs/root/src/entrypoints/cli.js", MODULE, [(operation, b"function render(){NEW}\n")])


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
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd /Users/MAC/Documents/Claude-patch
python3 -m pytest tests/test_module_patch.py -q
```

Expected: FAIL because `module_patch.py` does not exist.

- [ ] **Step 3: Implement module patch planner**

Create `/Users/MAC/Documents/Claude-patch/src/claude_monkey/module_patch.py`:

```python
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
            raise ModulePatchError(f"{operation.op_id}: replace_between requires startMarker and endMarker")
        start_marker = _b(operation.start_marker)
        end_marker = _b(operation.end_marker)
        start_count = _count(module, start_marker)
        if start_count != operation.expected_start_marker_count:
            raise ModulePatchError(f"{operation.op_id}: start marker count {start_count} != {operation.expected_start_marker_count}")
        start = module.find(start_marker)
        tail = module[start + len(start_marker) :]
        end_count = _count(tail, end_marker)
        if end_count != operation.expected_end_marker_count:
            raise ModulePatchError(f"{operation.op_id}: end marker count {end_count} != {operation.expected_end_marker_count}")
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
                raise ModulePatchError(f"{operation.op_id}: required bytes missing from range: {required}")
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
                f"overlap: {left.package_id}:{left.op_id} [{left.module_start},{left.module_end}) and "
                f"{right.package_id}:{right.op_id} [{right.module_start},{right.module_end})"
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
```

- [ ] **Step 4: Run module patch tests**

```bash
cd /Users/MAC/Documents/Claude-patch
python3 -m pytest tests/test_module_patch.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit module planner**

```bash
cd /Users/MAC/Documents/Claude-patch
git add src/claude_monkey/module_patch.py tests/test_module_patch.py
git commit -m "Add module-coordinate patch planner"
```

## Task 6: Add read-only binary inspection and CLI command

**Files:**
- Create: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/binary_inspect.py`
- Create: `/Users/MAC/Documents/Claude-patch/tests/test_binary_inspect.py`
- Modify: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/cli.py`
- Create or modify: `/Users/MAC/Documents/Claude-patch/tests/test_cli_v15.py`

- [ ] **Step 1: Write inspection tests**

Create `/Users/MAC/Documents/Claude-patch/tests/test_binary_inspect.py`:

```python
from __future__ import annotations

from tests.fixtures_bun import MODULE_PATH_0, MODULE_PATH_1, build_macho_fixture

from claude_monkey.binary_inspect import inspect_binary_bytes


def test_inspect_binary_bytes_reports_bun_modules():
    data, _ = build_macho_fixture()
    report = inspect_binary_bytes(data, source_path="fixture-claude")
    assert report["ok"] is True
    assert report["format"] == "macho64"
    assert report["bun"]["moduleRecordSize"] == 52
    assert report["modules"][0]["path"] == MODULE_PATH_0
    assert report["validationErrors"] == []
```

Create `/Users/MAC/Documents/Claude-patch/tests/test_cli_v15.py` with the first CLI test:

```python
from __future__ import annotations

import json

from tests.fixtures_bun import build_macho_fixture

from claude_monkey.cli import main


def read_json(capsys):
    return json.loads(capsys.readouterr().out)


def test_inspect_binary_json_command(tmp_path, capsys):
    binary = tmp_path / "claude"
    binary.write_bytes(build_macho_fixture()[0])
    assert main(["inspect-binary", "--source", str(binary), "--json"]) == 0
    payload = read_json(capsys)
    assert payload["ok"] is True
    assert payload["sourcePath"] == str(binary)
    assert payload["modules"][0]["path"] == "/$bunfs/root/src/entrypoints/cli.js"
```

- [ ] **Step 2: Run tests to verify failure**

```bash
cd /Users/MAC/Documents/Claude-patch
python3 -m pytest tests/test_binary_inspect.py tests/test_cli_v15.py::test_inspect_binary_json_command -q
```

Expected: FAIL because `binary_inspect.py` and CLI command are missing.

- [ ] **Step 3: Implement `binary_inspect.py`**

Create `/Users/MAC/Documents/Claude-patch/src/claude_monkey/binary_inspect.py`:

```python
from __future__ import annotations

import hashlib
from typing import Any

from claude_monkey.bun_graph import parse_bun_section
from claude_monkey.macho import find_macho_layout


def inspect_binary_bytes(data: bytes, *, source_path: str) -> dict[str, Any]:
    source_sha = hashlib.sha256(data).hexdigest()
    try:
        layout = find_macho_layout(data)
        start = layout.bun_section.offset
        end = layout.bun_section.offset + layout.bun_section.size
        graph = parse_bun_section(data[start:end])
    except Exception as exc:
        return {
            "schemaVersion": 1,
            "ok": False,
            "sourcePath": source_path,
            "sourceSha256": source_sha,
            "sourceSizeBytes": len(data),
            "format": "unknown",
            "supported": False,
            "bun": None,
            "modules": [],
            "validationErrors": [f"{type(exc).__name__}: {exc}"],
        }
    return {
        "schemaVersion": 1,
        "ok": not graph.validation_errors,
        "sourcePath": source_path,
        "sourceSha256": source_sha,
        "sourceSizeBytes": len(data),
        "format": "macho64",
        "supported": True,
        "bun": {
            "segment": layout.bun_segment.name,
            "section": layout.bun_section.name,
            "payloadLength": graph.declared_payload_len,
            "trailerOffset": graph.trailer_offset,
            "moduleRecordSize": graph.module_record_size,
            "moduleCount": len(graph.modules),
            "entryPointId": graph.entry_point_id,
        },
        "modules": [
            {
                "index": module.index,
                "path": module.path,
                "contentLength": module.content_size,
                "contentSha256": hashlib.sha256(module.content).hexdigest(),
            }
            for module in graph.modules
        ],
        "validationErrors": graph.validation_errors,
    }
```

- [ ] **Step 4: Wire `inspect-binary --json` in CLI**

Modify `/Users/MAC/Documents/Claude-patch/src/claude_monkey/cli.py`:

1. Add import near existing imports:

```python
from claude_monkey.binary_inspect import inspect_binary_bytes
```

2. Add parser in `build_parser()` after existing subcommands are created:

```python
inspect_binary = sub.add_parser("inspect-binary")
inspect_binary.add_argument("--source", required=True)
inspect_binary.add_argument("--json", action="store_true")
```

3. Add branch in `main()` before `build` branch:

```python
    if args.command == "inspect-binary":
        source = Path(args.source).expanduser()
        payload = inspect_binary_bytes(source.read_bytes(), source_path=str(source))
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"supported={str(payload['supported']).lower()}")
            print(f"modules={len(payload['modules'])}")
        return 0 if payload["ok"] and not payload["validationErrors"] else 1
```

- [ ] **Step 5: Run inspection tests**

```bash
cd /Users/MAC/Documents/Claude-patch
python3 -m pytest tests/test_binary_inspect.py tests/test_cli_v15.py::test_inspect_binary_json_command -q
```

Expected: PASS.

- [ ] **Step 6: Commit inspection CLI**

```bash
cd /Users/MAC/Documents/Claude-patch
git add src/claude_monkey/binary_inspect.py src/claude_monkey/cli.py tests/test_binary_inspect.py tests/test_cli_v15.py
git commit -m "Add Bun graph binary inspection command"
```

## Task 7: Add package validation command

**Files:**
- Modify: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/cli.py`
- Create: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/builder_v15.py`
- Modify: `/Users/MAC/Documents/Claude-patch/tests/test_cli_v15.py`

- [ ] **Step 1: Add validation test**

Append to `/Users/MAC/Documents/Claude-patch/tests/test_cli_v15.py`:

```python

def test_validate_package_json_resolves_module_operation(tmp_path, capsys):
    import hashlib

    from tests.fixtures_bun import MODULE_0, build_macho_fixture

    binary = tmp_path / "claude"
    binary.write_bytes(build_macho_fixture()[0])
    old = MODULE_0[: MODULE_0.index(b"function after(){")]
    package = tmp_path / "pkg"
    package.mkdir()
    manifest = {
        "schemaVersion": 2,
        "id": "fixture-v15",
        "name": "Fixture V1.5",
        "description": "Fixture package",
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
                                "opId": "replace-renderer",
                                "label": "Replace renderer",
                                "type": "replace_between",
                                "startMarker": "function render(){",
                                "endMarker": "function after(){",
                                "expectedStartMarkerCount": 1,
                                "expectedEndMarkerCount": 1,
                                "requireWithinRange": ["OLD_RENDER"],
                                "oldRangeSha256": hashlib.sha256(old).hexdigest(),
                                "oldRangeLength": len(old),
                                "replacement": {"inline": "function render(){NEW_RENDER_LONGER}\n"},
                            }
                        ],
                    }
                ],
                "postconditions": [
                    {
                        "type": "module_must_contain",
                        "modulePath": "/$bunfs/root/src/entrypoints/cli.js",
                        "value": "NEW_RENDER_LONGER",
                    }
                ],
                "manualSmoke": {"required": False},
            }
        ],
    }
    (package / "patch.json").write_text(json.dumps(manifest))
    assert main(["validate-package", "--source", str(binary), "--package", str(package), "--source-version", "fixture", "--source-version-output", "fixture", "--json"]) == 0
    payload = read_json(capsys)
    assert payload["ok"] is True
    assert payload["operationsResolved"][0]["moduleStart"] == 0
    assert payload["operationsResolved"][0]["newLen"] > payload["operationsResolved"][0]["oldLen"]
```

- [ ] **Step 2: Implement validation helpers in `builder_v15.py`**

Create `/Users/MAC/Documents/Claude-patch/src/claude_monkey/builder_v15.py` with validation-only types and functions:

```python
from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from claude_monkey.binary_inspect import inspect_binary_bytes
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
        return {"schemaVersion": 1, "ok": False, "packageId": manifest.id, "errorCode": "source_identity_mismatch", "errors": ["source identity did not match exactly"]}
    target = matching_targets[0]
    layout = find_macho_layout(source)
    graph = parse_bun_section(source[layout.bun_section.offset : layout.bun_section.offset + layout.bun_section.size])
    if graph.validation_errors:
        return {"schemaVersion": 1, "ok": False, "packageId": manifest.id, "errorCode": "bun_graph_invalid", "errors": graph.validation_errors}
    resolved: list[PlannedModuleOperation] = []
    changed_modules: dict[str, bytes] = {}
    for module_target in target.modules:
        module = graph.module_by_path(module_target.path)
        if hashlib.sha256(module.content).hexdigest() != module_target.content_sha256 or module.content_size != module_target.content_length:
            return {"schemaVersion": 1, "ok": False, "packageId": manifest.id, "errorCode": "module_identity_failed", "errors": [module_target.path]}
        operation_inputs = [(operation, load_payload(operation.replacement, request.package_dir)) for operation in module_target.operations]
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
```

- [ ] **Step 3: Wire CLI `validate-package`**

Modify `/Users/MAC/Documents/Claude-patch/src/claude_monkey/cli.py`:

1. Add import:

```python
from claude_monkey.builder_v15 import ValidationRequestV15, validate_package
```

2. Add parser:

```python
validate = sub.add_parser("validate-package")
validate.add_argument("--source", required=True)
validate.add_argument("--package", required=True)
validate.add_argument("--source-version", required=True)
validate.add_argument("--source-version-output", required=True)
validate.add_argument("--platform", default=sys.platform)
validate.add_argument("--arch", default=platform_module.machine() or "unknown")
validate.add_argument("--json", action="store_true")
```

3. Add branch before build:

```python
    if args.command == "validate-package":
        payload = validate_package(
            ValidationRequestV15(
                source_path=Path(args.source).expanduser(),
                package_dir=Path(args.package).expanduser(),
                source_version=args.source_version,
                source_version_output=args.source_version_output,
                platform=args.platform,
                arch=args.arch,
            )
        )
        if args.json:
            print(json.dumps(payload, indent=2, sort_keys=True))
        else:
            print(f"ok={str(payload['ok']).lower()}")
        return 0 if payload["ok"] else 1
```

- [ ] **Step 4: Run validation tests**

```bash
cd /Users/MAC/Documents/Claude-patch
python3 -m pytest tests/test_cli_v15.py::test_validate_package_json_resolves_module_operation -q
```

Expected: PASS.

- [ ] **Step 5: Commit validation command**

```bash
cd /Users/MAC/Documents/Claude-patch
git add src/claude_monkey/builder_v15.py src/claude_monkey/cli.py tests/test_cli_v15.py
git commit -m "Add V1.5 package validation command"
```

## Task 8: Add repack orchestration and report model

**Files:**
- Create: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/repack.py`
- Create: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/reports_v2.py`
- Create: `/Users/MAC/Documents/Claude-patch/tests/test_repack.py`

- [ ] **Step 1: Write repack test**

Create `/Users/MAC/Documents/Claude-patch/tests/test_repack.py`:

```python
from __future__ import annotations

from tests.fixtures_bun import MODULE_PATH_0, MODULE_PATH_1, build_macho_fixture

from claude_monkey.binary_inspect import inspect_binary_bytes
from claude_monkey.bun_graph import parse_bun_section
from claude_monkey.macho import find_macho_layout
from claude_monkey.repack import repack_changed_modules


def test_repack_changed_modules_updates_module_and_preserves_inspectability():
    source, _ = build_macho_fixture()
    layout = find_macho_layout(source)
    graph = parse_bun_section(source[layout.bun_section.offset : layout.bun_section.offset + layout.bun_section.size])
    new_module = b"function render(){NEW_RENDER_LONGER}\nfunction after(){return 1}\n"
    result = repack_changed_modules(source, {MODULE_PATH_0: new_module})
    assert result.delta > 0
    inspected = inspect_binary_bytes(result.output_bytes, source_path="fixture-output")
    assert inspected["ok"] is True
    assert inspected["validationErrors"] == []
    layout2 = find_macho_layout(result.output_bytes)
    graph2 = parse_bun_section(result.output_bytes[layout2.bun_section.offset : layout2.bun_section.offset + layout2.bun_section.size])
    assert graph2.module_by_path(MODULE_PATH_0).content == new_module
    assert graph2.declared_payload_len == graph.declared_payload_len + result.delta


def test_repack_changed_modules_is_deterministic_for_two_modules():
    source, _ = build_macho_fixture()
    changed = {
        MODULE_PATH_1: b"x=1;\n",
        MODULE_PATH_0: b"function render(){NEW_RENDER_LONGER}\nfunction after(){return 1}\n",
    }
    first = repack_changed_modules(source, changed)
    second = repack_changed_modules(source, dict(reversed(list(changed.items()))))
    assert first.output_bytes == second.output_bytes
    inspected = inspect_binary_bytes(first.output_bytes, source_path="fixture-output")
    assert inspected["ok"] is True
```

- [ ] **Step 2: Implement `repack.py`**

Create `/Users/MAC/Documents/Claude-patch/src/claude_monkey/repack.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from claude_monkey.bun_graph import parse_bun_section
from claude_monkey.macho import find_macho_layout, shift_macho_after_bun_change


@dataclass(frozen=True)
class RepackResult:
    output_bytes: bytes
    delta: int
    bun_graph_updates: dict[str, Any]
    macho_updates: dict[str, Any]
    macho_update_details: list[dict[str, Any]]


def repack_changed_modules(source: bytes, changed_modules: dict[str, bytes]) -> RepackResult:
    if not changed_modules:
        raise ValueError("changed_modules_required")
    layout = find_macho_layout(source)
    section_start = layout.bun_section.offset
    section_end = layout.bun_section.offset + layout.bun_section.size
    graph = parse_bun_section(source[section_start:section_end])
    current_section = graph.section_bytes
    original_section_end = section_end
    original_order = {module.path: module.content_offset for module in graph.modules}
    total_delta = 0
    shifted_pointers = 0
    old_payload_length = graph.declared_payload_len
    old_byte_count = graph.byte_count
    for module_path in sorted(changed_modules, key=lambda path: original_order[path]):
        graph = parse_bun_section(current_section)
        rewrite = graph.replace_module_content(module_path, changed_modules[module_path])
        if rewrite.validation_errors:
            raise ValueError(f"bun_graph_validation_failed:{rewrite.validation_errors}")
        current_section = rewrite.section_bytes
        total_delta += rewrite.delta
        shifted_pointers += rewrite.shifted_pointers
    prefix = source[:section_start]
    suffix_start = section_end
    source_with_section = prefix + current_section + source[suffix_start:]
    shifted, macho_update_details = shift_macho_after_bun_change(source_with_section, insert_abs=original_section_end, delta=total_delta)
    reparsed_layout = find_macho_layout(shifted)
    reparsed_section = shifted[reparsed_layout.bun_section.offset : reparsed_layout.bun_section.offset + reparsed_layout.bun_section.size]
    reparsed_graph = parse_bun_section(reparsed_section)
    return RepackResult(
        output_bytes=shifted,
        delta=total_delta,
        bun_graph_updates={
            "oldPayloadLength": old_payload_length,
            "newPayloadLength": reparsed_graph.declared_payload_len,
            "oldByteCount": old_byte_count,
            "newByteCount": reparsed_graph.byte_count,
            "moduleRecordSize": reparsed_graph.module_record_size,
            "moduleCount": len(reparsed_graph.modules),
            "shiftedPointers": shifted_pointers,
            "validationErrors": reparsed_graph.validation_errors,
        },
        macho_updates={
            "bunSectionSizeDelta": total_delta,
            "bunSegmentSizeDelta": total_delta,
            "linkeditFileoffDelta": total_delta,
            "linkeditVmaddrDelta": total_delta,
            "codeSignatureOffsetDelta": total_delta,
        },
        macho_update_details=macho_update_details,
    )
```

- [ ] **Step 3: Implement `reports_v2.py`**

Create `/Users/MAC/Documents/Claude-patch/src/claude_monkey/reports_v2.py`:

```python
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class BuildReportV2:
    schemaVersion: int = 2
    status: str = "failed"
    automatedStatus: str = "failed"
    engine: str = "bun_graph_repack"
    sourceClaudePath: str = ""
    sourceVersion: str = ""
    sourceVersionOutput: str = ""
    sourceSha256: str = ""
    sourceSizeBytes: int = 0
    enabledPatches: list[str] = field(default_factory=list)
    changedModules: list[dict[str, Any]] = field(default_factory=list)
    operationsApplied: list[dict[str, Any]] = field(default_factory=list)
    bunGraphUpdates: dict[str, Any] = field(default_factory=dict)
    machoUpdates: dict[str, Any] = field(default_factory=dict)
    machoUpdateDetails: list[dict[str, Any]] = field(default_factory=list)
    verificationResults: list[dict[str, Any]] = field(default_factory=list)
    outputPath: str | None = None
    outputSha256: str | None = None
    outputSizeBytes: int | None = None
    signingResult: dict[str, Any] = field(default_factory=lambda: {"status": "skipped"})
    postSignInspection: dict[str, Any] = field(default_factory=dict)
    smokeTestResults: list[dict[str, Any]] = field(default_factory=list)
    manualSmoke: dict[str, Any] = field(default_factory=lambda: {"required": False, "status": "not_required"})
    activationEligible: bool = False
    activationBlockers: list[str] = field(default_factory=list)
    activationStatus: str = "skipped"
    failureReason: str | None = None
    skippedGates: list[str] = field(default_factory=list)

    def write(self, path: Path) -> None:
        path.write_text(json.dumps(asdict(self), indent=2, sort_keys=True) + "\n")
```

- [ ] **Step 4: Run repack tests**

```bash
cd /Users/MAC/Documents/Claude-patch
python3 -m pytest tests/test_repack.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit repacker and report model**

```bash
cd /Users/MAC/Documents/Claude-patch
git add src/claude_monkey/repack.py src/claude_monkey/reports_v2.py tests/test_repack.py
git commit -m "Add Bun graph repack orchestration"
```

## Task 9: Strengthen smoke checks to reject Bun runtime help/version

**Files:**
- Modify: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/smoke.py`
- Modify: `/Users/MAC/Documents/Claude-patch/tests/test_smoke.py`

- [ ] **Step 1: Add content-based smoke tests**

Append to `/Users/MAC/Documents/Claude-patch/tests/test_smoke.py`:

```python

def test_content_smoke_rejects_bun_cli_help(tmp_path):
    from claude_monkey.smoke import smoke_claude_code_version_and_help

    binary = tmp_path / "claude"
    binary.write_text("fake")

    def runner(argv):
        if argv[-1] == "--version":
            return CommandResult(argv=argv, returncode=0, stdout="1.4.0\n", stderr="")
        return CommandResult(argv=argv, returncode=0, stdout="Bun is a fast JavaScript runtime\n", stderr="")

    result = smoke_claude_code_version_and_help(binary, "2.1.198 (Claude Code)", runner)
    assert result["passed"] is False
    assert "version_mismatch" in result["errors"]
    assert "bun_help_detected" in result["errors"]


def test_content_smoke_accepts_claude_code_markers(tmp_path):
    from claude_monkey.smoke import smoke_claude_code_version_and_help

    binary = tmp_path / "claude"
    binary.write_text("fake")

    def runner(argv):
        if argv[-1] == "--version":
            return CommandResult(argv=argv, returncode=0, stdout="2.1.198 (Claude Code)\n", stderr="")
        return CommandResult(argv=argv, returncode=0, stdout="Usage: claude [options]\nClaude Code help\n", stderr="")

    result = smoke_claude_code_version_and_help(binary, "2.1.198 (Claude Code)", runner)
    assert result["passed"] is True
    assert result["errors"] == []
```

- [ ] **Step 2: Implement content smoke helper**

Modify `/Users/MAC/Documents/Claude-patch/src/claude_monkey/smoke.py` by adding:

```python
from pathlib import Path
from typing import Any


def smoke_claude_code_version_and_help(binary: Path, expected_version_output: str, runner=run_command) -> dict[str, Any]:
    version = runner([str(binary), "--version"])
    help_result = runner([str(binary), "--help"])
    errors: list[str] = []
    version_text = (version.stdout.strip() or version.stderr.strip()).strip()
    help_text = f"{help_result.stdout}\n{help_result.stderr}"
    if version.returncode != 0:
        errors.append("version_nonzero_exit")
    if version_text != expected_version_output:
        errors.append("version_mismatch")
    if help_result.returncode != 0:
        errors.append("help_nonzero_exit")
    if "Claude Code" not in help_text:
        errors.append("claude_help_marker_missing")
    if "Bun is a fast JavaScript runtime" in help_text or version_text.startswith("1.4.0"):
        errors.append("bun_help_detected")
    return {
        "passed": not errors,
        "errors": errors,
        "commands": [version.__dict__, help_result.__dict__],
    }
```

If `smoke.py` already imports `Path`, do not duplicate the import.

- [ ] **Step 3: Run smoke tests**

```bash
cd /Users/MAC/Documents/Claude-patch
python3 -m pytest tests/test_smoke.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit smoke hardening**

```bash
cd /Users/MAC/Documents/Claude-patch
git add src/claude_monkey/smoke.py tests/test_smoke.py
git commit -m "Harden Claude Code smoke checks"
```

## Task 10: Implement V1.5 builder and build CLI

**Files:**
- Modify: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/builder_v15.py`
- Modify: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/cli.py`
- Create: `/Users/MAC/Documents/Claude-patch/tests/test_builder_v15.py`
- Modify: `/Users/MAC/Documents/Claude-patch/tests/test_cli_v15.py`

- [ ] **Step 1: Write builder tests for copied output, schema v1 rejection, and activation blockers**

Create `/Users/MAC/Documents/Claude-patch/tests/test_builder_v15.py`:

```python
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tests.fixtures_bun import MODULE_0, build_macho_fixture

from claude_monkey.builder_v15 import BuildRequestV15, build_patchset_v15
from claude_monkey.smoke import CommandResult


def write_fixture_package(package: Path, binary: Path, *, manual_smoke: bool = False) -> None:
    old = MODULE_0[: MODULE_0.index(b"function after(){")]
    manifest = {
        "schemaVersion": 2,
        "id": "fixture-v15",
        "name": "Fixture V1.5",
        "description": "Fixture package",
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
                                "opId": "replace-renderer",
                                "label": "Replace renderer",
                                "type": "replace_between",
                                "startMarker": "function render(){",
                                "endMarker": "function after(){",
                                "expectedStartMarkerCount": 1,
                                "expectedEndMarkerCount": 1,
                                "requireWithinRange": ["OLD_RENDER"],
                                "oldRangeSha256": hashlib.sha256(old).hexdigest(),
                                "oldRangeLength": len(old),
                                "replacement": {"inline": "function render(){NEW_RENDER_LONGER}\n"},
                            }
                        ],
                    }
                ],
                "postconditions": [
                    {
                        "type": "module_must_contain",
                        "modulePath": "/$bunfs/root/src/entrypoints/cli.js",
                        "value": "NEW_RENDER_LONGER",
                    }
                ],
                "manualSmoke": {"required": manual_smoke, "reason": "UI" if manual_smoke else None},
            }
        ],
    }
    package.mkdir()
    (package / "patch.json").write_text(json.dumps(manifest))


def successful_runner(argv):
    if argv[0] == "codesign" and "--verify" in argv:
        return CommandResult(argv=argv, returncode=0, stdout="", stderr="valid")
    if argv[0] == "codesign":
        return CommandResult(argv=argv, returncode=0, stdout="", stderr="signed")
    if argv[-1] == "--version":
        return CommandResult(argv=argv, returncode=0, stdout="fixture (Claude Code)\n", stderr="")
    if argv[-1] == "--help":
        return CommandResult(argv=argv, returncode=0, stdout="Usage: claude [options]\nClaude Code help\n", stderr="")
    return CommandResult(argv=argv, returncode=1, stdout="", stderr="unexpected")


def test_build_patchset_v15_writes_copied_output_and_report(tmp_path):
    source = tmp_path / "claude-source"
    source.write_bytes(build_macho_fixture()[0])
    package = tmp_path / "pkg"
    write_fixture_package(package, source)
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
    assert report.automatedStatus == "passed"
    assert report.activationEligible is True
    assert report.outputPath is not None
    assert Path(report.outputPath).exists()
    assert source.read_bytes() == build_macho_fixture()[0]


def test_build_patchset_v15_blocks_activation_for_manual_smoke(tmp_path):
    source = tmp_path / "claude-source"
    source.write_bytes(build_macho_fixture()[0])
    package = tmp_path / "pkg"
    write_fixture_package(package, source, manual_smoke=True)
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
    assert report.status == "manual_smoke_pending"
    assert report.activationEligible is False
    assert "manual_smoke_pending" in report.activationBlockers


def test_schema_v1_package_is_migration_required(tmp_path):
    source = tmp_path / "claude-source"
    source.write_bytes(build_macho_fixture()[0])
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "patch.json").write_text(json.dumps({"schemaVersion": 1}))
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
    assert report.failureReason == "schema_v1_migration_required"
```

- [ ] **Step 2: Implement `BuildRequestV15` and `build_patchset_v15`**

Modify `/Users/MAC/Documents/Claude-patch/src/claude_monkey/builder_v15.py` by adding build orchestration below validation helpers. Use the existing helpers from prior tasks.

Key implementation requirements:

```python
from dataclasses import asdict
from claude_monkey.binary_inspect import inspect_binary_bytes
from claude_monkey.repack import repack_changed_modules
from claude_monkey.reports_v2 import BuildReportV2
from claude_monkey.smoke import CommandResult, codesign_sign, codesign_verify, run_command, smoke_claude_code_version_and_help

CommandRunner = Callable[[list[str]], CommandResult]

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
```

The build function must:

1. Create `output_dir`.
2. Read `source` once and compute SHA/size.
3. Load every package with `load_manifest_v2`; catch `schema_v1_migration_required` and write failed report.
4. Select exactly one matching target per package.
5. Parse graph and validate module identity.
6. Plan operations by module and render changed modules.
7. Run postconditions against changed module bytes before smoke.
8. Call `repack_changed_modules`.
9. Write `output_dir / "claude"` and preserve source mode.
10. Sign if `run_signing`; verify signature.
11. Compute final output SHA/size.
12. Re-inspect final output with `inspect_binary_bytes`.
13. Smoke with `smoke_claude_code_version_and_help` if `run_smoke`.
14. Set `manualSmoke.status` to `pending` when required.
15. Set `activationEligible` false if any blocker exists.
16. If `activate=True`, only update `current_path` when `activationEligible=True`; otherwise leave it untouched and report blocked.
17. Always write `build-report.json`.

Do not call the V1 `plan_patch` or `render_patched_bytes` functions.

- [ ] **Step 3: Wire CLI build to V1.5 package path and remove old bypass flags**

Modify `/Users/MAC/Documents/Claude-patch/src/claude_monkey/cli.py` so `build` accepts `--json` and calls `build_patchset_v15` for active build behavior. Remove `--unverified-candidate` and `--skip-identity-check` from the active `build` parser. For this V1.5 implementation, schema v1 packages should fail with the V1.5 report error rather than silently using V1 slot behavior.

Important: in `handle_build`, resolve `package_dirs` only. Do not call `_load_manifest`, do not construct V1 `Manifest` objects, and do not call the V1 `build_patchset`. Pass `package_dirs` into `BuildRequestV15`; `builder_v15` owns schema v2 parsing and structured `schema_v1_migration_required` failures.

Parser additions for `build`:

```python
build.add_argument("--json", action="store_true")
```

In `handle_build`, after package dirs are resolved, call `build_patchset_v15` instead of the V1 builder for this branch. Print JSON when requested:

```python
if args.json:
    print(json.dumps(asdict(report), indent=2, sort_keys=True))
else:
    print(f"status={report.status}")
```

- [ ] **Step 4: Run builder tests**

```bash
cd /Users/MAC/Documents/Claude-patch
python3 -m pytest tests/test_builder_v15.py -q
```

Expected: PASS.

- [ ] **Step 5: Run CLI V1.5 tests**

```bash
cd /Users/MAC/Documents/Claude-patch
python3 -m pytest tests/test_cli_v15.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit V1.5 builder**

```bash
cd /Users/MAC/Documents/Claude-patch
git add src/claude_monkey/builder_v15.py src/claude_monkey/cli.py tests/test_builder_v15.py tests/test_cli_v15.py
git commit -m "Wire V1.5 Bun graph repack builder"
```

## Task 11: Add a schema v2 reference package proof

**Files:**
- Conditional create only if exact real module evidence is available: `/Users/MAC/Documents/Claude-patch/packages/fable-fallback-v15/README.md`
- Conditional create only if exact real module evidence is available: `/Users/MAC/Documents/Claude-patch/packages/fable-fallback-v15/patch.json`
- Conditional create only if exact real module evidence is available: `/Users/MAC/Documents/Claude-patch/packages/fable-fallback-v15/payloads/gcm-assistant-case.js`
- Modify only if the conditional package is created: `/Users/MAC/Documents/Claude-patch/tests/test_reference_packages.py`

- [ ] **Step 1: Decide whether local real module identity is available**

Run read-only inspection against the real local Claude binary only if the user or implementer has identified a copied source path. If no real binary path is explicitly available, do not invent module hashes. Instead create a fixture reference package under tests only and leave production package migration to a later explicit real-binary pass.

Command when a real source path is available:

```bash
cd /Users/MAC/Documents/Claude-patch
python3 -m claude_monkey.cli inspect-binary --source /path/to/copied-or-official/claude --json > /tmp/claude-monkey-inspect.json
```

Expected: JSON with `/$bunfs/root/src/entrypoints/cli.js` and no validation errors.

- [ ] **Step 2: If exact module hashes are available, create reference package**

Only create `packages/fable-fallback-v15` if exact `contentSha256`, `contentLength`, range markers, `oldRangeSha256`, and `oldRangeLength` are proven from inspection and existing payloads. The package must use schema v2 and must not contain `padding`, `allowGrowth`, `binaryShape`, or whole-binary operation fields.

- [ ] **Step 3: If exact module hashes are not available, document migration deferred**

If no exact real module evidence is available in this implementation thread, add a short note to the implementation final report and do not create a fake production package. Do not commit plausible-looking hashes.

- [ ] **Step 4: Add reference package parser test if package was created**

If `packages/fable-fallback-v15/patch.json` exists, append to `/Users/MAC/Documents/Claude-patch/tests/test_reference_packages.py`:

```python

def test_fable_fallback_v15_manifest_parses_if_present():
    from pathlib import Path
    from claude_monkey.manifest_v2 import load_manifest_v2_dict

    package = Path("packages/fable-fallback-v15/patch.json")
    if not package.exists():
        return
    manifest = load_manifest_v2_dict(json.loads(package.read_text()))
    assert manifest.schema_version == 2
    assert manifest.targets[0].required_engine == "bun_graph_repack"
```

- [ ] **Step 5: Run reference package tests**

```bash
cd /Users/MAC/Documents/Claude-patch
python3 -m pytest tests/test_reference_packages.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit reference package or explicit defer note**

If package exists:

```bash
cd /Users/MAC/Documents/Claude-patch
git add packages/fable-fallback-v15 tests/test_reference_packages.py
git commit -m "Add schema v2 reference package proof"
```

If package is deferred, do not commit fake package files. Continue to final verification.

## Task 12: Full verification and opt-in real smoke gate

**Files:**
- Modify only if verification reveals needed doc/test fixes.

- [ ] **Step 1: Run focused V1.5 test suite**

```bash
cd /Users/MAC/Documents/Claude-patch
python3 -m pytest tests/test_manifest_v2.py tests/test_module_patch.py tests/test_macho.py tests/test_bun_graph.py tests/test_binary_inspect.py tests/test_repack.py tests/test_builder_v15.py tests/test_cli_v15.py tests/test_smoke.py -q
```

Expected: PASS.

- [ ] **Step 2: Run full test suite**

```bash
cd /Users/MAC/Documents/Claude-patch
python3 -m pytest -q
```

Expected: PASS. If existing V1 tests fail because `build` now rejects schema v1 in active V1.5 behavior, update tests to assert migration-required behavior where appropriate rather than reintroducing slot fallback. Also update any tests or help-output expectations that still mention active `--skip-identity-check` or `--unverified-candidate` build flags.

- [ ] **Step 3: Run lint if available**

```bash
cd /Users/MAC/Documents/Claude-patch
python3 -m ruff check src tests
```

Expected: PASS, or skip with a clear note if `ruff` is not installed in the local environment.

- [ ] **Step 4: Optional real copied-binary repack smoke**

Only run when explicitly approved and only against copied output. Do not mutate the official Claude binary.

```bash
cd /Users/MAC/Documents/Claude-patch
CLAUDE_MONKEY_LOCAL_REAL_REPACK=1 python3 -m pytest -m local_real_repack -q
```

Expected if approved/configured: copied-output smoke only, official Claude binary unchanged.

- [ ] **Step 5: Inspect final git diff**

```bash
cd /Users/MAC/Documents/Claude-patch
git status --short
git log --oneline -12
```

Expected: no unrelated worktree dirt introduced by the implementation. Any existing unrelated dirt remains untouched.

- [ ] **Step 6: Final commit for verification fixes if needed**

Only if Step 1-5 required test/doc fixes:

```bash
cd /Users/MAC/Documents/Claude-patch
git add <changed-files>
git commit -m "Finalize V1.5 repack verification"
```

## Implementation handoff notes

- The implementer must not touch the live Claude install.
- The implementer must not vendor public gist/project code.
- The implementer must not reintroduce slot strategy, padding semantics, `allowGrowth`, or `--unverified-candidate`.
- The implementer may keep old V1 modules in the repository only if they are not active V1.5 build behavior.
- If a plan step proves technically wrong during implementation, stop and update the plan or report the contradiction rather than papering over it.
