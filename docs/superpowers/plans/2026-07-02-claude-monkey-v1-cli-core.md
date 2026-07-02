# ClaudeMonkey v1 CLI Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the v1 source-first Python CLI/core for ClaudeMonkey: declarative local patch packages, safe patch stacking, prompt profile config, managed shim generation, reports, and hermetic tests.

**Architecture:** Implement a small Python package under `src/claude_monkey/` with pure core modules for manifests, byte patch operations, build reports, config, shim generation, smoke/signing helpers, and CLI commands. Keep real Claude binary interaction behind injectable functions and opt-in smoke tests; normal tests use synthetic fixture binaries and temporary HOME/state paths.

**Tech Stack:** Python 3.11+ standard library, `pytest` for tests, `ruff` for linting, `argparse` for CLI, JSON files for manifests/config/reports. No runtime dependency on Bun/Node/Swift for v1.

---

## Planning decisions from adversarial review

- Prompt profiles support `mode: "append" | "replace"`; default is `append`.
- Use file-based prompt flags when available (`--append-system-prompt-file` / `--system-prompt-file`); fall back to direct string flags only when explicitly allowed by config or command option.
- If the user supplies any system-prompt flag, the shim does not inject a profile flag.
- Patch package replacement payloads may live in external files referenced by SHA-256; this is preferred for large JavaScript payloads.
- All marker and replacement strings are UTF-8 bytes unless an object specifies `encoding: "base64"`.
- `replace_between` uses half-open ranges: `[startMarkerOffset, endMarkerOffset)`.
- Adjacent ranges are allowed. All overlaps are rejected, even if identical.
- Build final bytes from immutable source slices after precomputing all ranges; do not sequentially re-search mutated bytes.
- V1 includes fenced advanced in-place replacement only as a separate command path. The default product path remains shim plus copied patched binary.
- CI/local tests are hermetic fixture tests. Real Claude smoke is opt-in via environment variable.

## Byte operation contract for v1

- Marker and replacement strings decode to UTF-8 bytes unless a payload explicitly sets `encoding: "base64"`.
- No Unicode normalization is applied.
- `replace_between` computes a half-open byte range `[startMarkerOffset, endMarkerOffset)`.
- `endMarker` search begins after `startMarkerOffset + len(startMarker)`.
- `expectedStartMarkerCount` and `expectedEndMarkerCount` default to `1`; any mismatch fails closed.
- `padding: "spaces"` appends ASCII `0x20` bytes until the replacement fits the original range length.
- `padding: "none"` requires the replacement length to exactly equal the original range length.
- `replace_exact` replaces one exact byte sequence and fails unless the sequence appears exactly once.

---

## File structure

Create these files:

```text
pyproject.toml
src/claude_monkey/__init__.py
src/claude_monkey/__main__.py
src/claude_monkey/cli.py
src/claude_monkey/paths.py
src/claude_monkey/manifest.py
src/claude_monkey/payloads.py
src/claude_monkey/patch_ops.py
src/claude_monkey/reports.py
src/claude_monkey/builder.py
src/claude_monkey/config.py
src/claude_monkey/prompts.py
src/claude_monkey/shim.py
src/claude_monkey/install.py
src/claude_monkey/smoke.py
packages/fable-fallback/patch.json
packages/fable-fallback/payloads/gcm-assistant-case.js
packages/fable-fallback/payloads/net-metadata-formatter.js
packages/fable-fallback/payloads/wpf-lite-log-enrichment.js
packages/fable-fallback/README.md
packages/reminder-suppression/patch.json
packages/reminder-suppression/payloads/todo-reminder.js
packages/reminder-suppression/payloads/task-reminder.js
packages/reminder-suppression/payloads/tool-search-usage-reminder.js
packages/reminder-suppression/payloads/token-usage.js
packages/reminder-suppression/payloads/total-tokens-reminder.js
packages/reminder-suppression/payloads/budget-usd.js
packages/reminder-suppression/payloads/output-token-usage.js
packages/reminder-suppression/README.md
tests/conftest.py
tests/fixtures.py
tests/test_manifest.py
tests/test_payloads.py
tests/test_patch_ops.py
tests/test_builder.py
tests/test_config_prompts.py
tests/test_shim.py
tests/test_install.py
tests/test_cli.py
tests/test_reference_packages.py
```

Responsibilities:

- `manifest.py`: parse/validate `patch.json`, normalize targets and operations.
- `payloads.py`: load inline or external SHA-pinned payload bytes.
- `patch_ops.py`: compute ranges, verify preconditions, apply non-overlapping operations.
- `reports.py`: typed build report creation and JSON serialization.
- `builder.py`: orchestrate source identity, manifest target matching, stacking, signing/smoke hooks, symlink activation.
- `config.py`: read/write `~/.claude-monkey/config.json` and profile state.
- `prompts.py`: prompt profile records and shim injection decisions.
- `shim.py`: generate the managed `claude` shim script and compute underlying argv.
- `install.py`: install/uninstall transaction records, ownership checks, rollback/use-official commands.
- `smoke.py`: injectable command runner for `--version`, `--help`, and macOS codesign.
- `cli.py`: `argparse` CLI wired to the core modules.

---

### Task 1: Project scaffold and test harness

**Files:**
- Create: `/Users/MAC/Documents/Claude-patch/pyproject.toml`
- Create: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/__init__.py`
- Create: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/__main__.py`
- Create: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/cli.py`
- Create: `/Users/MAC/Documents/Claude-patch/tests/conftest.py`
- Create: `/Users/MAC/Documents/Claude-patch/tests/fixtures.py`

- [ ] **Step 1: Create the Python package metadata**

Create `/Users/MAC/Documents/Claude-patch/pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "claude-monkey"
version = "0.1.0"
description = "Source-first local userscript-style customization manager for Claude Code"
requires-python = ">=3.11"
dependencies = []

[project.optional-dependencies]
dev = [
  "pytest>=8.2",
  "ruff>=0.5"
]

[project.scripts]
claude-monkey = "claude_monkey.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
markers = [
  "local_real_smoke: opt-in tests that copy and smoke-test the locally installed Claude binary"
]

[tool.ruff]
line-length = 100
src = ["src", "tests"]

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]
```

- [ ] **Step 2: Add package entrypoints**

Create `/Users/MAC/Documents/Claude-patch/src/claude_monkey/__init__.py`:

```python
__version__ = "0.1.0"
```

Create `/Users/MAC/Documents/Claude-patch/src/claude_monkey/__main__.py`:

```python
from claude_monkey.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

Create `/Users/MAC/Documents/Claude-patch/src/claude_monkey/cli.py`:

```python
from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="claude-monkey")
    parser.add_argument("--version", action="store_true", help="print ClaudeMonkey version")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("doctor")
    sub.add_parser("list-patches")
    sub.add_parser("status")
    return parser


def main(argv: list[str] | None = None) -> int:
    from claude_monkey import __version__

    parser = build_parser()
    args = parser.parse_args(argv)
    if args.version:
        print(__version__)
        return 0
    if args.command in {"doctor", "list-patches", "status"}:
        print(f"{args.command}: command shell available")
        return 0
    parser.print_help()
    return 0
```

- [ ] **Step 3: Add test helpers**

Create `/Users/MAC/Documents/Claude-patch/tests/conftest.py`:

```python
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
```

Create `/Users/MAC/Documents/Claude-patch/tests/fixtures.py`:

```python
from __future__ import annotations


def tiny_binary() -> bytes:
    return b"HEAD case\"a\":{OLD_A_BODY} case\"b\":{OLD_B_BODY} TAIL"


def utf8(value: str) -> bytes:
    return value.encode("utf-8")
```

- [ ] **Step 4: Verify the initial CLI imports**

Run:

```bash
python3 -m claude_monkey --version
python3 -m pytest -q
```

Expected:

```text
0.1.0
no tests ran
```

- [ ] **Step 5: Commit scaffold**

```bash
git add pyproject.toml src/claude_monkey tests/conftest.py tests/fixtures.py
git commit -m "Add ClaudeMonkey Python scaffold"
```

---

### Task 2: Manifest models and validation

**Files:**
- Create: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/manifest.py`
- Test: `/Users/MAC/Documents/Claude-patch/tests/test_manifest.py`

- [ ] **Step 1: Write failing manifest validation tests**

Create `/Users/MAC/Documents/Claude-patch/tests/test_manifest.py`:

```python
from __future__ import annotations

import json

import pytest

from claude_monkey.manifest import ManifestError, load_manifest_dict


def valid_manifest() -> dict:
    return {
        "schemaVersion": 1,
        "id": "example-patch",
        "name": "Example Patch",
        "description": "Example declarative patch",
        "packageVersion": "0.1.0",
        "targets": [
            {
                "sourceIdentity": {
                    "claudeVersion": "2.1.198",
                    "versionOutput": "2.1.198 (Claude Code)",
                    "sha256": "a" * 64,
                    "sizeBytes": 100,
                    "platform": "darwin",
                    "arch": "arm64",
                },
                "operations": [
                    {
                        "opId": "replace-a",
                        "label": "Replace A",
                        "type": "replace_between",
                        "startMarker": "case\"a\":{",
                        "endMarker": "case\"b\":{",
                        "expectedStartMarkerCount": 1,
                        "expectedEndMarkerCount": 1,
                        "requireWithinRange": ["OLD_A_BODY"],
                        "replacement": {"inline": "case\"a\":{NEW_A_BODY} "},
                        "padding": "spaces",
                    }
                ],
                "postconditions": [
                    {"type": "must_contain", "scope": "whole_binary", "value": "NEW_A_BODY"}
                ],
            }
        ],
    }


def test_load_manifest_accepts_valid_shape():
    manifest = load_manifest_dict(valid_manifest())
    assert manifest.id == "example-patch"
    assert manifest.targets[0].source_identity.claude_version == "2.1.198"
    assert manifest.targets[0].operations[0].op_id == "replace-a"


@pytest.mark.parametrize("field", ["schemaVersion", "id", "name", "description", "packageVersion", "targets"])
def test_manifest_requires_top_level_fields(field):
    data = valid_manifest()
    del data[field]
    with pytest.raises(ManifestError, match=field):
        load_manifest_dict(data)


def test_manifest_rejects_duplicate_operation_ids():
    data = valid_manifest()
    data["targets"][0]["operations"].append(dict(data["targets"][0]["operations"][0]))
    with pytest.raises(ManifestError, match="duplicate opId"):
        load_manifest_dict(data)


def test_manifest_rejects_unknown_operation_type():
    data = valid_manifest()
    data["targets"][0]["operations"][0]["type"] = "run_shell"
    with pytest.raises(ManifestError, match="unsupported operation type"):
        load_manifest_dict(data)


def test_manifest_can_be_json_serialized_for_digest_stability():
    data = valid_manifest()
    encoded = json.dumps(data, sort_keys=True, separators=(",", ":"))
    assert "example-patch" in encoded
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
python3 -m pytest tests/test_manifest.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'claude_monkey.manifest'`.

- [ ] **Step 3: Implement manifest dataclasses and validation**

Create `/Users/MAC/Documents/Claude-patch/src/claude_monkey/manifest.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

SUPPORTED_OPERATION_TYPES = {"replace_between", "replace_exact"}
SUPPORTED_ASSERTION_TYPES = {"must_contain", "must_not_contain"}
SUPPORTED_SCOPES = {"whole_binary", "range"}
SUPPORTED_PADDING = {"spaces", "none"}


class ManifestError(ValueError):
    pass


@dataclass(frozen=True)
class SourceIdentity:
    claude_version: str
    version_output: str
    sha256: str
    size_bytes: int
    platform: str
    arch: str


@dataclass(frozen=True)
class PayloadRef:
    inline: str | None = None
    path: str | None = None
    sha256: str | None = None
    encoding: Literal["utf-8", "base64"] = "utf-8"


@dataclass(frozen=True)
class Operation:
    op_id: str
    label: str
    type: str
    start_marker: str | None
    end_marker: str | None
    exact: str | None
    expected_start_marker_count: int
    expected_end_marker_count: int
    require_within_range: tuple[str, ...]
    replacement: PayloadRef
    padding: str
    old_range_sha256: str | None = None
    old_range_length: int | None = None
    known_behavior_change: str | None = None


@dataclass(frozen=True)
class Assertion:
    type: str
    scope: str
    value: str
    op_id: str | None = None


@dataclass(frozen=True)
class Target:
    source_identity: SourceIdentity
    operations: tuple[Operation, ...]
    preconditions: tuple[Assertion, ...]
    postconditions: tuple[Assertion, ...]


@dataclass(frozen=True)
class Manifest:
    schema_version: int
    id: str
    name: str
    description: str
    package_version: str
    targets: tuple[Target, ...]
    raw: dict[str, Any]


def require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ManifestError(f"{label} must be an object")
    return value


def require_string(obj: dict[str, Any], field: str) -> str:
    value = obj.get(field)
    if not isinstance(value, str) or value == "":
        raise ManifestError(f"{field} must be a non-empty string")
    return value


def require_int(obj: dict[str, Any], field: str) -> int:
    value = obj.get(field)
    if not isinstance(value, int):
        raise ManifestError(f"{field} must be an integer")
    return value


def optional_string(obj: dict[str, Any], field: str) -> str | None:
    value = obj.get(field)
    if value is None:
        return None
    if not isinstance(value, str):
        raise ManifestError(f"{field} must be a string")
    return value


def parse_payload(value: Any) -> PayloadRef:
    payload = require_mapping(value, "replacement")
    inline = payload.get("inline")
    path = payload.get("path")
    sha256 = payload.get("sha256")
    encoding = payload.get("encoding", "utf-8")
    if encoding not in {"utf-8", "base64"}:
        raise ManifestError("replacement.encoding must be utf-8 or base64")
    if inline is not None and not isinstance(inline, str):
        raise ManifestError("replacement.inline must be a string")
    if path is not None and not isinstance(path, str):
        raise ManifestError("replacement.path must be a string")
    if sha256 is not None and not isinstance(sha256, str):
        raise ManifestError("replacement.sha256 must be a string")
    if (inline is None) == (path is None):
        raise ManifestError("replacement must provide exactly one of inline or path")
    if path is not None and sha256 is None:
        raise ManifestError("replacement.path requires replacement.sha256")
    return PayloadRef(inline=inline, path=path, sha256=sha256, encoding=encoding)


def parse_assertion(value: Any) -> Assertion:
    item = require_mapping(value, "assertion")
    assertion_type = require_string(item, "type")
    if assertion_type not in SUPPORTED_ASSERTION_TYPES:
        raise ManifestError(f"unsupported assertion type: {assertion_type}")
    scope = item.get("scope", "whole_binary")
    if scope not in SUPPORTED_SCOPES:
        raise ManifestError(f"unsupported assertion scope: {scope}")
    return Assertion(
        type=assertion_type,
        scope=scope,
        value=require_string(item, "value"),
        op_id=optional_string(item, "opId"),
    )


def parse_operation(value: Any) -> Operation:
    op = require_mapping(value, "operation")
    op_type = require_string(op, "type")
    if op_type not in SUPPORTED_OPERATION_TYPES:
        raise ManifestError(f"unsupported operation type: {op_type}")
    padding = op.get("padding", "spaces")
    if padding not in SUPPORTED_PADDING:
        raise ManifestError(f"unsupported padding: {padding}")
    require_within = op.get("requireWithinRange", [])
    if not isinstance(require_within, list) or not all(isinstance(x, str) for x in require_within):
        raise ManifestError("requireWithinRange must be a list of strings")
    return Operation(
        op_id=require_string(op, "opId"),
        label=require_string(op, "label"),
        type=op_type,
        start_marker=optional_string(op, "startMarker"),
        end_marker=optional_string(op, "endMarker"),
        exact=optional_string(op, "exact"),
        expected_start_marker_count=int(op.get("expectedStartMarkerCount", 1)),
        expected_end_marker_count=int(op.get("expectedEndMarkerCount", 1)),
        require_within_range=tuple(require_within),
        replacement=parse_payload(op.get("replacement")),
        padding=padding,
        old_range_sha256=optional_string(op, "oldRangeSha256"),
        old_range_length=op.get("oldRangeLength"),
        known_behavior_change=optional_string(op, "knownBehaviorChange"),
    )


def parse_source_identity(value: Any) -> SourceIdentity:
    item = require_mapping(value, "sourceIdentity")
    sha = require_string(item, "sha256")
    if len(sha) != 64:
        raise ManifestError("sha256 must be 64 hex characters")
    return SourceIdentity(
        claude_version=require_string(item, "claudeVersion"),
        version_output=require_string(item, "versionOutput"),
        sha256=sha,
        size_bytes=require_int(item, "sizeBytes"),
        platform=require_string(item, "platform"),
        arch=require_string(item, "arch"),
    )


def parse_target(value: Any) -> Target:
    target = require_mapping(value, "target")
    operations_raw = target.get("operations")
    if not isinstance(operations_raw, list) or not operations_raw:
        raise ManifestError("operations must be a non-empty list")
    operations = tuple(parse_operation(op) for op in operations_raw)
    seen: set[str] = set()
    for op in operations:
        if op.op_id in seen:
            raise ManifestError(f"duplicate opId: {op.op_id}")
        seen.add(op.op_id)
    return Target(
        source_identity=parse_source_identity(target.get("sourceIdentity")),
        operations=operations,
        preconditions=tuple(parse_assertion(a) for a in target.get("preconditions", [])),
        postconditions=tuple(parse_assertion(a) for a in target.get("postconditions", [])),
    )


def load_manifest_dict(data: dict[str, Any]) -> Manifest:
    require_mapping(data, "manifest")
    for field in ["schemaVersion", "id", "name", "description", "packageVersion", "targets"]:
        if field not in data:
            raise ManifestError(f"missing required field: {field}")
    if data["schemaVersion"] != 1:
        raise ManifestError("schemaVersion must be 1")
    targets_raw = data["targets"]
    if not isinstance(targets_raw, list) or not targets_raw:
        raise ManifestError("targets must be a non-empty list")
    return Manifest(
        schema_version=1,
        id=require_string(data, "id"),
        name=require_string(data, "name"),
        description=require_string(data, "description"),
        package_version=require_string(data, "packageVersion"),
        targets=tuple(parse_target(t) for t in targets_raw),
        raw=data,
    )
```

- [ ] **Step 4: Run manifest tests**

Run:

```bash
python3 -m pytest tests/test_manifest.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit manifest validation**

```bash
git add src/claude_monkey/manifest.py tests/test_manifest.py
git commit -m "Add patch manifest validation"
```

---

### Task 3: Payload loading with SHA-pinned external files

**Files:**
- Create: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/payloads.py`
- Test: `/Users/MAC/Documents/Claude-patch/tests/test_payloads.py`

- [ ] **Step 1: Write failing payload tests**

Create `/Users/MAC/Documents/Claude-patch/tests/test_payloads.py`:

```python
from __future__ import annotations

import hashlib

import pytest

from claude_monkey.manifest import PayloadRef
from claude_monkey.payloads import PayloadError, load_payload_bytes


def test_inline_payload_utf8():
    assert load_payload_bytes(PayloadRef(inline="hello", encoding="utf-8"), None) == b"hello"


def test_inline_payload_base64():
    assert load_payload_bytes(PayloadRef(inline="aGVsbG8=", encoding="base64"), None) == b"hello"


def test_external_payload_requires_matching_sha(tmp_path):
    payload = tmp_path / "payload.js"
    payload.write_bytes(b"replacement")
    sha = hashlib.sha256(b"replacement").hexdigest()
    ref = PayloadRef(path="payload.js", sha256=sha, encoding="utf-8")
    assert load_payload_bytes(ref, tmp_path) == b"replacement"


def test_external_payload_rejects_sha_mismatch(tmp_path):
    payload = tmp_path / "payload.js"
    payload.write_bytes(b"replacement")
    ref = PayloadRef(path="payload.js", sha256="0" * 64, encoding="utf-8")
    with pytest.raises(PayloadError, match="sha256 mismatch"):
        load_payload_bytes(ref, tmp_path)
```

- [ ] **Step 2: Run tests to verify failure**

```bash
python3 -m pytest tests/test_payloads.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'claude_monkey.payloads'`.

- [ ] **Step 3: Implement payload loading**

Create `/Users/MAC/Documents/Claude-patch/src/claude_monkey/payloads.py`:

```python
from __future__ import annotations

import base64
import hashlib
from pathlib import Path

from claude_monkey.manifest import PayloadRef


class PayloadError(ValueError):
    pass


def decode_payload_text(text: str, encoding: str) -> bytes:
    if encoding == "utf-8":
        return text.encode("utf-8")
    if encoding == "base64":
        return base64.b64decode(text.encode("ascii"), validate=True)
    raise PayloadError(f"unsupported payload encoding: {encoding}")


def load_payload_bytes(ref: PayloadRef, package_dir: Path | None) -> bytes:
    if ref.inline is not None:
        return decode_payload_text(ref.inline, ref.encoding)
    if ref.path is None or ref.sha256 is None:
        raise PayloadError("external payload requires path and sha256")
    if package_dir is None:
        raise PayloadError("external payload requires package_dir")
    path = (package_dir / ref.path).resolve()
    root = package_dir.resolve()
    if root not in path.parents and path != root:
        raise PayloadError(f"payload path escapes package directory: {ref.path}")
    data = path.read_bytes()
    actual = hashlib.sha256(data).hexdigest()
    if actual != ref.sha256:
        raise PayloadError(f"sha256 mismatch for {ref.path}: expected {ref.sha256}, got {actual}")
    return data
```

- [ ] **Step 4: Run payload tests**

```bash
python3 -m pytest tests/test_payloads.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit payload loader**

```bash
git add src/claude_monkey/payloads.py tests/test_payloads.py
git commit -m "Add SHA-pinned payload loading"
```

---

### Task 4: Byte patch operation engine

**Files:**
- Create: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/patch_ops.py`
- Test: `/Users/MAC/Documents/Claude-patch/tests/test_patch_ops.py`

- [ ] **Step 1: Write failing patch operation tests**

Create `/Users/MAC/Documents/Claude-patch/tests/test_patch_ops.py`:

```python
from __future__ import annotations

import pytest

from claude_monkey.manifest import Operation, PayloadRef
from claude_monkey.patch_ops import PatchError, compute_operation_range, plan_patch, render_patched_bytes
from tests.fixtures import tiny_binary


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
        compute_operation_range(tiny_binary(), op("a", "case\"a\":{", "case\"b\":{", "X" * 1000), b"X" * 1000)


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
```

- [ ] **Step 2: Run tests to verify failure**

```bash
python3 -m pytest tests/test_patch_ops.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'claude_monkey.patch_ops'`.

- [ ] **Step 3: Implement patch operation engine**

Create `/Users/MAC/Documents/Claude-patch/src/claude_monkey/patch_ops.py`:

```python
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


def compute_operation_range(source: bytes, operation: Operation, replacement: bytes, package_id: str = "") -> PlannedOperation:
    if operation.type == "replace_between":
        if operation.start_marker is None or operation.end_marker is None:
            raise PatchError(f"{operation.op_id}: replace_between requires startMarker and endMarker")
        start_marker = b(operation.start_marker)
        end_marker = b(operation.end_marker)
        start_count = count_occurrences(source, start_marker)
        if start_count != operation.expected_start_marker_count:
            raise PatchError(f"{operation.op_id}: start marker count {start_count} != {operation.expected_start_marker_count}")
        start = source.find(start_marker)
        end_count = count_occurrences(source[start + len(start_marker) :], end_marker)
        if end_count != operation.expected_end_marker_count:
            raise PatchError(f"{operation.op_id}: end marker count {end_count} != {operation.expected_end_marker_count}")
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
        raise PatchError(f"{operation.op_id}: replacement too large: {len(replacement)} > {len(old)}")
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


def plan_patch(source: bytes, operations: list[tuple[str, Operation, bytes]]) -> list[PlannedOperation]:
    planned = [compute_operation_range(source, op, replacement, package_id) for package_id, op, replacement in operations]
    planned.sort(key=lambda item: (item.start, item.end, item.package_id, item.op_id))
    for left, right in zip(planned, planned[1:]):
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
```

- [ ] **Step 4: Run patch operation tests**

```bash
python3 -m pytest tests/test_patch_ops.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit patch engine**

```bash
git add src/claude_monkey/patch_ops.py tests/test_patch_ops.py
git commit -m "Add byte patch operation engine"
```

---

### Task 5: Build reports and builder orchestration

**Files:**
- Create: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/reports.py`
- Create: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/builder.py`
- Test: `/Users/MAC/Documents/Claude-patch/tests/test_builder.py`

- [ ] **Step 1: Write failing builder/report tests**

Create `/Users/MAC/Documents/Claude-patch/tests/test_builder.py`:

```python
from __future__ import annotations

import json

from claude_monkey.builder import BuildRequest, build_patchset
from claude_monkey.manifest import load_manifest_dict
from tests.test_manifest import valid_manifest


def test_build_patchset_writes_report_and_output(tmp_path):
    source = tmp_path / "claude-source"
    source.write_bytes(b"HEAD case\"a\":{OLD_A_BODY} case\"b\":{OLD_B_BODY} TAIL")
    data = valid_manifest()
    data["targets"][0]["sourceIdentity"]["sha256"] = "ignored-by-test"
    manifest = load_manifest_dict(data)
    out_dir = tmp_path / "out"
    report = build_patchset(
        BuildRequest(
            source_path=source,
            output_dir=out_dir,
            manifests=[(tmp_path, manifest)],
            source_version="2.1.198",
            source_version_output="2.1.198 (Claude Code)",
            source_sha256="ignored-by-test",
            source_size_bytes=source.stat().st_size,
            platform="darwin",
            arch="arm64",
            skip_identity_check=True,
            run_signing=False,
            run_smoke=False,
            activate=False,
        )
    )
    output = out_dir / "claude"
    report_path = out_dir / "build-report.json"
    assert output.exists()
    assert report_path.exists()
    assert b"NEW_A_BODY" in output.read_bytes()
    encoded = json.loads(report_path.read_text())
    assert encoded["activationStatus"] == "skipped"
    assert encoded["enabledPatches"] == ["example-patch"]
    assert report.status == "verified"


def test_identity_mismatch_blocks_normal_build(tmp_path):
    source = tmp_path / "claude-source"
    source.write_bytes(b"HEAD case\"a\":{OLD_A_BODY} case\"b\":{OLD_B_BODY} TAIL")
    manifest = load_manifest_dict(valid_manifest())
    report = build_patchset(
        BuildRequest(
            source_path=source,
            output_dir=tmp_path / "out",
            manifests=[(tmp_path, manifest)],
            source_version="2.1.199",
            source_version_output="2.1.199 (Claude Code)",
            source_sha256="b" * 64,
            source_size_bytes=source.stat().st_size,
            platform="darwin",
            arch="arm64",
            skip_identity_check=False,
            unverified_candidate=False,
            run_signing=False,
            run_smoke=False,
            activate=False,
        )
    )
    assert report.status == "failed"
    assert "identity_mismatch" in report.failureReason
```

- [ ] **Step 2: Run tests to verify failure**

```bash
python3 -m pytest tests/test_builder.py -q
```

Expected: FAIL with missing `builder` module.

- [ ] **Step 3: Implement report serialization**

Create `/Users/MAC/Documents/Claude-patch/src/claude_monkey/reports.py`:

```python
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class BuildReport:
    status: str
    sourceClaudePath: str
    sourceVersion: str
    sourceVersionOutput: str
    sourceSha256: str
    sourceSizeBytes: int
    platform: str
    arch: str
    enabledPatches: list[str]
    manifestDigests: dict[str, str]
    operationsApplied: list[dict[str, Any]] = field(default_factory=list)
    byteRanges: list[dict[str, Any]] = field(default_factory=list)
    verificationResults: list[dict[str, Any]] = field(default_factory=list)
    signingResult: dict[str, Any] = field(default_factory=lambda: {"status": "skipped"})
    smokeTestResults: list[dict[str, Any]] = field(default_factory=list)
    activationStatus: str = "skipped"
    failureReason: str | None = None
    unverifiedCandidate: bool = False

    def write(self, path: Path) -> None:
        path.write_text(json.dumps(asdict(self), indent=2, sort_keys=True) + "\n")
```

- [ ] **Step 4: Implement builder orchestration**

Create `/Users/MAC/Documents/Claude-patch/src/claude_monkey/builder.py`:

```python
from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from claude_monkey.manifest import Assertion, Manifest, Target
from claude_monkey.patch_ops import PatchError, plan_patch, render_patched_bytes
from claude_monkey.payloads import load_payload_bytes
from claude_monkey.reports import BuildReport


@dataclass(frozen=True)
class BuildRequest:
    source_path: Path
    output_dir: Path
    manifests: list[tuple[Path, Manifest]]
    source_version: str
    source_version_output: str
    source_sha256: str
    source_size_bytes: int
    platform: str
    arch: str
    skip_identity_check: bool = False
    unverified_candidate: bool = False
    run_signing: bool = True
    run_smoke: bool = True
    activate: bool = False


def digest_manifest(manifest: Manifest) -> str:
    encoded = json.dumps(manifest.raw, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def select_target(manifest: Manifest, request: BuildRequest) -> Target | None:
    for target in manifest.targets:
        ident = target.source_identity
        if (
            ident.claude_version == request.source_version
            and ident.version_output == request.source_version_output
            and ident.sha256 == request.source_sha256
            and ident.size_bytes == request.source_size_bytes
            and ident.platform == request.platform
            and ident.arch == request.arch
        ):
            return target
    if request.skip_identity_check or request.unverified_candidate:
        return manifest.targets[0]
    return None


def assert_condition(data: bytes, assertion: Assertion) -> dict:
    needle = assertion.value.encode("utf-8")
    found = needle in data
    passed = found if assertion.type == "must_contain" else not found
    return {"type": assertion.type, "scope": assertion.scope, "value": assertion.value, "passed": passed}


def failed_report(request: BuildRequest, reason: str) -> BuildReport:
    return BuildReport(
        status="failed",
        sourceClaudePath=str(request.source_path),
        sourceVersion=request.source_version,
        sourceVersionOutput=request.source_version_output,
        sourceSha256=request.source_sha256,
        sourceSizeBytes=request.source_size_bytes,
        platform=request.platform,
        arch=request.arch,
        enabledPatches=[manifest.id for _, manifest in request.manifests],
        manifestDigests={manifest.id: digest_manifest(manifest) for _, manifest in request.manifests},
        failureReason=reason,
        unverifiedCandidate=request.unverified_candidate,
    )


def build_patchset(request: BuildRequest) -> BuildReport:
    request.output_dir.mkdir(parents=True, exist_ok=True)
    report_path = request.output_dir / "build-report.json"
    source = request.source_path.read_bytes()
    selected: list[tuple[Path, Manifest, Target]] = []
    for package_dir, manifest in request.manifests:
        target = select_target(manifest, request)
        if target is None:
            report = failed_report(request, f"identity_mismatch:{manifest.id}")
            report.write(report_path)
            return report
        selected.append((package_dir, manifest, target))

    try:
        patch_inputs = []
        verification_results = []
        for package_dir, manifest, target in selected:
            for precondition in target.preconditions:
                result = assert_condition(source, precondition)
                verification_results.append({"packageId": manifest.id, **result})
                if not result["passed"]:
                    report = failed_report(request, f"precondition_failed:{manifest.id}")
                    report.verificationResults = verification_results
                    report.write(report_path)
                    return report
            for operation in target.operations:
                replacement = load_payload_bytes(operation.replacement, package_dir)
                patch_inputs.append((manifest.id, operation, replacement))
        planned = plan_patch(source, patch_inputs)
        final = render_patched_bytes(source, planned)
        for _, manifest, target in selected:
            for postcondition in target.postconditions:
                result = assert_condition(final, postcondition)
                verification_results.append({"packageId": manifest.id, **result})
                if not result["passed"]:
                    report = failed_report(request, f"postcondition_failed:{manifest.id}")
                    report.verificationResults = verification_results
                    report.write(report_path)
                    return report
    except (PatchError, ValueError, OSError) as exc:
        report = failed_report(request, f"patch_failed:{exc}")
        report.write(report_path)
        return report

    output = request.output_dir / "claude"
    output.write_bytes(final)
    shutil.copymode(request.source_path, output)
    operations = [
        {
            "packageId": item.package_id,
            "opId": item.op_id,
            "label": item.label,
            "oldLen": item.old_len,
            "newLen": item.new_len,
            "paddingLen": item.padding_len,
            "oldSha256": item.old_sha256,
        }
        for item in planned
    ]
    ranges = [
        {"packageId": item.package_id, "opId": item.op_id, "start": item.start, "end": item.end}
        for item in planned
    ]
    report = BuildReport(
        status="unverified_candidate" if request.unverified_candidate else "verified",
        sourceClaudePath=str(request.source_path),
        sourceVersion=request.source_version,
        sourceVersionOutput=request.source_version_output,
        sourceSha256=request.source_sha256,
        sourceSizeBytes=request.source_size_bytes,
        platform=request.platform,
        arch=request.arch,
        enabledPatches=[manifest.id for _, manifest in request.manifests],
        manifestDigests={manifest.id: digest_manifest(manifest) for _, manifest in request.manifests},
        operationsApplied=operations,
        byteRanges=ranges,
        verificationResults=verification_results,
        activationStatus="skipped",
        unverifiedCandidate=request.unverified_candidate,
    )
    report.write(report_path)
    return report
```

- [ ] **Step 5: Run builder tests**

```bash
python3 -m pytest tests/test_builder.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit builder/report**

```bash
git add src/claude_monkey/builder.py src/claude_monkey/reports.py tests/test_builder.py
git commit -m "Add patchset builder and build reports"
```

---

### Task 6: Prompt profiles and config state

**Files:**
- Create: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/config.py`
- Create: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/prompts.py`
- Test: `/Users/MAC/Documents/Claude-patch/tests/test_config_prompts.py`

- [ ] **Step 1: Write failing config/prompt tests**

Create `/Users/MAC/Documents/Claude-patch/tests/test_config_prompts.py`:

```python
from __future__ import annotations

from claude_monkey.config import ClaudeMonkeyConfig, Profile, load_config, save_config
from claude_monkey.prompts import PromptProfile, prompt_args_for_invocation


def test_config_round_trip(tmp_path):
    config = ClaudeMonkeyConfig(
        activeProfile="default",
        profiles={"default": Profile(enabledPatches=["fable-fallback"], promptProfile="research")},
        installMode="shim",
        activePatchSet="2.1.198-default",
    )
    path = tmp_path / "config.json"
    save_config(path, config)
    loaded = load_config(path)
    assert loaded.profiles["default"].enabledPatches == ["fable-fallback"]


def test_prompt_append_file_injected_for_session_invocation(tmp_path):
    prompt = tmp_path / "prompt.md"
    prompt.write_text("extra prompt")
    profile = PromptProfile(id="research", name="Research", path=prompt, mode="append")
    args = prompt_args_for_invocation(["--resume"], profile, supports_file_flags=True)
    assert args == ["--append-system-prompt-file", str(prompt), "--resume"]


def test_user_prompt_flags_override_profile(tmp_path):
    prompt = tmp_path / "prompt.md"
    prompt.write_text("extra prompt")
    profile = PromptProfile(id="research", name="Research", path=prompt, mode="append")
    args = prompt_args_for_invocation(["--system-prompt", "mine", "hello"], profile, supports_file_flags=True)
    assert args == ["--system-prompt", "mine", "hello"]


def test_no_injection_for_management_invocation(tmp_path):
    prompt = tmp_path / "prompt.md"
    prompt.write_text("extra prompt")
    profile = PromptProfile(id="research", name="Research", path=prompt, mode="append")
    assert prompt_args_for_invocation(["--version"], profile, supports_file_flags=True) == ["--version"]
    assert prompt_args_for_invocation(["mcp", "list"], profile, supports_file_flags=True) == ["mcp", "list"]
```

- [ ] **Step 2: Run tests to verify failure**

```bash
python3 -m pytest tests/test_config_prompts.py -q
```

Expected: FAIL with missing modules.

- [ ] **Step 3: Implement config state**

Create `/Users/MAC/Documents/Claude-patch/src/claude_monkey/config.py`:

```python
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Profile:
    enabledPatches: list[str]
    promptProfile: str | None = None


@dataclass
class ClaudeMonkeyConfig:
    activeProfile: str
    profiles: dict[str, Profile]
    installMode: str = "shim"
    activePatchSet: str | None = None


def default_config() -> ClaudeMonkeyConfig:
    return ClaudeMonkeyConfig(activeProfile="default", profiles={"default": Profile(enabledPatches=[])})


def load_config(path: Path) -> ClaudeMonkeyConfig:
    if not path.exists():
        return default_config()
    raw = json.loads(path.read_text())
    return ClaudeMonkeyConfig(
        activeProfile=raw["activeProfile"],
        profiles={name: Profile(**value) for name, value in raw["profiles"].items()},
        installMode=raw.get("installMode", "shim"),
        activePatchSet=raw.get("activePatchSet"),
    )


def save_config(path: Path, config: ClaudeMonkeyConfig) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(config), indent=2, sort_keys=True) + "\n")
```

- [ ] **Step 4: Implement prompt injection rules**

Create `/Users/MAC/Documents/Claude-patch/src/claude_monkey/prompts.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PROMPT_FLAG_PREFIXES = {
    "--system-prompt",
    "--system-prompt-file",
    "--append-system-prompt",
    "--append-system-prompt-file",
}
MANAGEMENT_TOKENS = {"--help", "-h", "--version", "update", "mcp", "plugin"}


@dataclass(frozen=True)
class PromptProfile:
    id: str
    name: str
    path: Path
    mode: str = "append"


def has_user_prompt_flag(argv: list[str]) -> bool:
    return any(arg in PROMPT_FLAG_PREFIXES for arg in argv)


def is_management_invocation(argv: list[str]) -> bool:
    if not argv:
        return False
    return argv[0] in MANAGEMENT_TOKENS


def prompt_args_for_invocation(argv: list[str], profile: PromptProfile | None, supports_file_flags: bool) -> list[str]:
    if profile is None or has_user_prompt_flag(argv) or is_management_invocation(argv):
        return list(argv)
    if supports_file_flags:
        flag = "--append-system-prompt-file" if profile.mode == "append" else "--system-prompt-file"
        return [flag, str(profile.path), *argv]
    text = profile.path.read_text()
    flag = "--append-system-prompt" if profile.mode == "append" else "--system-prompt"
    return [flag, text, *argv]
```

- [ ] **Step 5: Run config/prompt tests**

```bash
python3 -m pytest tests/test_config_prompts.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit config and prompt support**

```bash
git add src/claude_monkey/config.py src/claude_monkey/prompts.py tests/test_config_prompts.py
git commit -m "Add config and prompt profile rules"
```

---

### Task 7: Shim generation and bypass behavior

**Files:**
- Create: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/paths.py`
- Create: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/shim.py`
- Test: `/Users/MAC/Documents/Claude-patch/tests/test_shim.py`

- [ ] **Step 1: Write failing shim tests**

Create `/Users/MAC/Documents/Claude-patch/tests/test_shim.py`:

```python
from __future__ import annotations

from claude_monkey.shim import render_shim_script


def test_shim_script_uses_exec_and_bypass():
    script = render_shim_script("/tmp/state")
    assert "CLAUDE_MONKEY_BYPASS" in script
    assert "os.execv" in script
    assert "/tmp/state" in script
    assert "shell=True" not in script
```

- [ ] **Step 2: Run tests to verify failure**

```bash
python3 -m pytest tests/test_shim.py -q
```

Expected: FAIL with missing `shim` module.

- [ ] **Step 3: Implement paths**

Create `/Users/MAC/Documents/Claude-patch/src/claude_monkey/paths.py`:

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StatePaths:
    state_dir: Path
    patches_dir: Path

    @property
    def config_path(self) -> Path:
        return self.state_dir / "config.json"

    @property
    def current_path(self) -> Path:
        return self.state_dir / "current"

    @property
    def bin_dir(self) -> Path:
        return self.state_dir / "bin"


def default_paths() -> StatePaths:
    home = Path(os.environ.get("HOME", str(Path.home())))
    return StatePaths(state_dir=home / ".claude-monkey", patches_dir=home / ".claude-patches")
```

- [ ] **Step 4: Implement shim rendering**

Create `/Users/MAC/Documents/Claude-patch/src/claude_monkey/shim.py`:

```python
from __future__ import annotations

import json
from pathlib import Path


def render_shim_script(state_dir: str) -> str:
    return f'''#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

STATE_DIR = Path({state_dir!r})
CURRENT = STATE_DIR / "current"
CONFIG = STATE_DIR / "config.json"
PROMPT_FLAGS = {{"--system-prompt", "--system-prompt-file", "--append-system-prompt", "--append-system-prompt-file"}}
MANAGEMENT = {{"--help", "-h", "--version", "update", "mcp", "plugin"}}


def is_management(argv):
    return bool(argv) and argv[0] in MANAGEMENT


def has_prompt_flag(argv):
    return any(arg in PROMPT_FLAGS for arg in argv)


def active_prompt_args(argv):
    if os.environ.get("CLAUDE_MONKEY_BYPASS") == "1" or is_management(argv) or has_prompt_flag(argv):
        return argv
    if not CONFIG.exists():
        return argv
    config = json.loads(CONFIG.read_text())
    profile_name = config.get("profiles", {{}}).get(config.get("activeProfile", "default"), {{}}).get("promptProfile")
    if not profile_name:
        return argv
    profile_path = STATE_DIR / "prompts" / (profile_name + ".json")
    if not profile_path.exists():
        return argv
    profile = json.loads(profile_path.read_text())
    mode = profile.get("mode", "append")
    source = profile["sourcePath"]
    flag = "--append-system-prompt-file" if mode == "append" else "--system-prompt-file"
    return [flag, source, *argv]


def main():
    argv = sys.argv[1:]
    target = os.environ.get("CLAUDE_MONKEY_OFFICIAL") if os.environ.get("CLAUDE_MONKEY_BYPASS") == "1" else None
    if target is None:
        if not CURRENT.exists():
            print("ClaudeMonkey: no active Claude binary at " + str(CURRENT), file=sys.stderr)
            print("Run: claude-monkey use-official or claude-monkey build", file=sys.stderr)
            return 127
        target = str(CURRENT.resolve())
    os.execv(target, [target, *active_prompt_args(argv)])

if __name__ == "__main__":
    raise SystemExit(main())
'''


def write_shim(path: Path, state_dir: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_shim_script(str(state_dir)))
    path.chmod(0o755)
```

- [ ] **Step 5: Run shim tests**

```bash
python3 -m pytest tests/test_shim.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Commit shim support**

```bash
git add src/claude_monkey/paths.py src/claude_monkey/shim.py tests/test_shim.py
git commit -m "Add managed Claude shim generator"
```

---

### Task 8: Install transaction, rollback, and use-official primitives

**Files:**
- Create: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/install.py`
- Test: `/Users/MAC/Documents/Claude-patch/tests/test_install.py`

- [ ] **Step 1: Write failing install tests**

Create `/Users/MAC/Documents/Claude-patch/tests/test_install.py`:

```python
from __future__ import annotations

import json

from claude_monkey.install import install_shim_transaction, restore_install_transaction, use_official
from claude_monkey.shim import render_shim_script


def test_install_records_previous_symlink_and_owner(tmp_path):
    target = tmp_path / "claude"
    previous = tmp_path / "official"
    previous.write_text("official")
    target.symlink_to(previous)
    record = install_shim_transaction(target, tmp_path / "state", dry_run=False)
    assert target.exists()
    assert "ClaudeMonkey" in target.read_text()
    raw = json.loads(record.read_text())
    assert raw["targetPath"] == str(target)
    assert raw["previousType"] == "symlink"


def test_restore_refuses_without_record(tmp_path):
    target = tmp_path / "claude"
    target.write_text(render_shim_script(str(tmp_path / "state")))
    assert restore_install_transaction(target, tmp_path / "missing.json", force=False) is False


def test_use_official_points_current_symlink(tmp_path):
    current = tmp_path / "current"
    official = tmp_path / "official"
    official.write_text("official")
    use_official(current, official)
    assert current.resolve() == official.resolve()
```

- [ ] **Step 2: Run tests to verify failure**

```bash
python3 -m pytest tests/test_install.py -q
```

Expected: FAIL with missing module.

- [ ] **Step 3: Implement install primitives**

Create `/Users/MAC/Documents/Claude-patch/src/claude_monkey/install.py`:

```python
from __future__ import annotations

import json
import os
from pathlib import Path
from time import time

from claude_monkey.shim import write_shim

OWNER_MARKER = "ClaudeMonkey managed shim"


def describe_existing(path: Path) -> dict:
    if not path.exists() and not path.is_symlink():
        return {"previousType": "missing"}
    if path.is_symlink():
        return {"previousType": "symlink", "previousTarget": os.readlink(path)}
    return {"previousType": "file", "previousContent": path.read_text(errors="replace")}


def install_shim_transaction(target_path: Path, state_dir: Path, dry_run: bool) -> Path:
    state_dir.mkdir(parents=True, exist_ok=True)
    record_path = state_dir / "install-record.json"
    record = {
        "owner": OWNER_MARKER,
        "targetPath": str(target_path),
        "stateDir": str(state_dir),
        "timestamp": time(),
        **describe_existing(target_path),
    }
    if not dry_run:
        tmp = target_path.with_suffix(target_path.suffix + ".claude-monkey.tmp")
        write_shim(tmp, state_dir)
        tmp.replace(target_path)
    record_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return record_path


def restore_install_transaction(target_path: Path, record_path: Path, force: bool) -> bool:
    if not record_path.exists():
        return False
    record = json.loads(record_path.read_text())
    if record.get("owner") != OWNER_MARKER and not force:
        return False
    previous_type = record.get("previousType")
    if previous_type == "missing":
        target_path.unlink(missing_ok=True)
    elif previous_type == "symlink":
        target_path.unlink(missing_ok=True)
        target_path.symlink_to(record["previousTarget"])
    elif previous_type == "file":
        target_path.write_text(record["previousContent"])
    else:
        return False
    return True


def use_official(current_path: Path, official_path: Path) -> None:
    current_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = current_path.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    tmp.symlink_to(official_path)
    tmp.replace(current_path)
```

- [ ] **Step 4: Run install tests**

```bash
python3 -m pytest tests/test_install.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit install primitives**

```bash
git add src/claude_monkey/install.py tests/test_install.py
git commit -m "Add shim install and restore primitives"
```

---

### Task 9: CLI commands wired to core behavior

**Files:**
- Modify: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/cli.py`
- Test: `/Users/MAC/Documents/Claude-patch/tests/test_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Create `/Users/MAC/Documents/Claude-patch/tests/test_cli.py`:

```python
from __future__ import annotations

from claude_monkey.cli import main


def test_cli_version(capsys):
    assert main(["--version"]) == 0
    assert "0.1.0" in capsys.readouterr().out


def test_status_prints_state_dir(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert main(["status"]) == 0
    out = capsys.readouterr().out
    assert ".claude-monkey" in out


def test_enable_and_disable_patch_mutate_default_profile(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert main(["enable", "fable-fallback"]) == 0
    assert main(["disable", "fable-fallback"]) == 0
```

- [ ] **Step 2: Run tests to verify failure**

```bash
python3 -m pytest tests/test_cli.py -q
```

Expected: FAIL because `enable` and `disable` are not wired.

- [ ] **Step 3: Replace CLI scaffold with v1 command shell**

Modify `/Users/MAC/Documents/Claude-patch/src/claude_monkey/cli.py`:

```python
from __future__ import annotations

import argparse

from claude_monkey import __version__
from claude_monkey.config import load_config, save_config
from claude_monkey.paths import default_paths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="claude-monkey")
    parser.add_argument("--version", action="store_true", help="print ClaudeMonkey version")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("doctor")
    sub.add_parser("list-patches")
    sub.add_parser("status")
    enable = sub.add_parser("enable")
    enable.add_argument("patch_id")
    disable = sub.add_parser("disable")
    disable.add_argument("patch_id")
    sub.add_parser("list-prompts")
    set_prompt = sub.add_parser("set-prompt")
    set_prompt.add_argument("prompt")
    sub.add_parser("clear-prompt")
    sub.add_parser("build")
    sub.add_parser("install-shim")
    sub.add_parser("uninstall-shim")
    sub.add_parser("rollback")
    sub.add_parser("use-official")
    return parser


def active_profile(config):
    return config.profiles.setdefault(config.activeProfile, type(next(iter(config.profiles.values())))(enabledPatches=[]))


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.version:
        print(__version__)
        return 0
    paths = default_paths()
    config = load_config(paths.config_path)
    if args.command == "status":
        print(f"stateDir={paths.state_dir}")
        print(f"patchesDir={paths.patches_dir}")
        print(f"activeProfile={config.activeProfile}")
        print(f"activePatchSet={config.activePatchSet}")
        return 0
    if args.command == "enable":
        profile = active_profile(config)
        if args.patch_id not in profile.enabledPatches:
            profile.enabledPatches.append(args.patch_id)
        save_config(paths.config_path, config)
        print(f"enabled {args.patch_id}; rebuild required")
        return 0
    if args.command == "disable":
        profile = active_profile(config)
        profile.enabledPatches = [item for item in profile.enabledPatches if item != args.patch_id]
        save_config(paths.config_path, config)
        print(f"disabled {args.patch_id}; rebuild required")
        return 0
    if args.command in {
        "doctor",
        "list-patches",
        "list-prompts",
        "set-prompt",
        "clear-prompt",
        "build",
        "install-shim",
        "uninstall-shim",
        "rollback",
        "use-official",
    }:
        print(f"{args.command}: command shell available")
        return 0
    parser.print_help()
    return 0
```

- [ ] **Step 4: Run CLI tests**

```bash
python3 -m pytest tests/test_cli.py -q
```

Expected: all tests pass.

- [ ] **Step 5: Commit CLI shell**

```bash
git add src/claude_monkey/cli.py tests/test_cli.py
git commit -m "Wire basic ClaudeMonkey CLI state commands"
```

---

### Task 10: Reference declarative patch packages

**Files:**
- Create package files under `/Users/MAC/Documents/Claude-patch/packages/fable-fallback/`
- Create package files under `/Users/MAC/Documents/Claude-patch/packages/reminder-suppression/`
- Test: `/Users/MAC/Documents/Claude-patch/tests/test_reference_packages.py`

- [ ] **Step 1: Write package validation test**

Create `/Users/MAC/Documents/Claude-patch/tests/test_reference_packages.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from claude_monkey.manifest import load_manifest_dict
from claude_monkey.payloads import load_payload_bytes

ROOT = Path(__file__).resolve().parents[1]


def test_reference_packages_load_and_payload_hashes_match():
    package_dirs = [ROOT / "packages" / "fable-fallback", ROOT / "packages" / "reminder-suppression"]
    for package_dir in package_dirs:
        manifest = load_manifest_dict(json.loads((package_dir / "patch.json").read_text()))
        assert manifest.id == package_dir.name
        for target in manifest.targets:
            assert target.operations
            for operation in target.operations:
                payload = load_payload_bytes(operation.replacement, package_dir)
                assert payload
```

- [ ] **Step 2: Run package test to verify failure**

```bash
python3 -m pytest tests/test_reference_packages.py -q
```

Expected: FAIL because package files do not exist.

- [ ] **Step 3: Create Fable fallback payload files from existing doc**

Create `/Users/MAC/Documents/Claude-patch/packages/fable-fallback/payloads/gcm-assistant-case.js` with the exact replacement currently documented in `/Users/MAC/Documents/Claude-patch/claude-fable-fallback-patch.md` under “Replacement 1: `gCm` assistant case”.

Create `/Users/MAC/Documents/Claude-patch/packages/fable-fallback/payloads/net-metadata-formatter.js` with the exact replacement currently documented under “Replacement 2: `net(e)` resume-list metadata formatter”.

Create `/Users/MAC/Documents/Claude-patch/packages/fable-fallback/payloads/wpf-lite-log-enrichment.js` with the exact replacement currently documented under “Replacement 3: `wpf(e,t)` resume lite-log enrichment”.

After creating each file, compute SHA values:

```bash
shasum -a 256 packages/fable-fallback/payloads/*.js
```

- [ ] **Step 4: Create Fable fallback patch manifest with computed payload SHA values**

Create `/Users/MAC/Documents/Claude-patch/packages/fable-fallback/write_manifest.py`:

```python
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def sha(rel: str) -> str:
    return hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()

manifest = {
    "schemaVersion": 1,
    "id": "fable-fallback",
    "name": "Fable fallback visibility",
    "description": "Shows Fable fallback events in resumed history and /resume.",
    "packageVersion": "0.1.0",
    "targets": [
        {
            "sourceIdentity": {
                "claudeVersion": "2.1.198",
                "versionOutput": "2.1.198 (Claude Code)",
                "sha256": "ab6f7ee109816ede414f7c285446633f805b623aa609f425609a64266451d61e",
                "sizeBytes": 229328464,
                "platform": "darwin",
                "arch": "arm64",
            },
            "operations": [
                {
                    "opId": "gcm-assistant-fallback-banner",
                    "label": "Render assistant fallback as system warning banner",
                    "type": "replace_between",
                    "startMarker": "case\"assistant\":{let R;if(t[20]!==r.firstTextBlockUuidByMessageID",
                    "endMarker": "case\"user\":{",
                    "expectedStartMarkerCount": 1,
                    "expectedEndMarkerCount": 1,
                    "requireWithinRange": ["D=(O,M)=>Ab.jsx(SCm,{param:O", "x=n.message.content.map(D)"],
                    "replacement": {
                        "path": "payloads/gcm-assistant-case.js",
                        "sha256": sha("payloads/gcm-assistant-case.js"),
                    },
                    "padding": "spaces",
                },
                {
                    "opId": "net-resume-marker",
                    "label": "Append Fable classifier marker to resume metadata",
                    "type": "replace_between",
                    "startMarker": "function net(e){let t=e.fileSize!==void 0?$a(e.fileSize):`${e.messageCount} messages`",
                    "endMarker": "function gte",
                    "expectedStartMarkerCount": 1,
                    "expectedEndMarkerCount": 1,
                    "requireWithinRange": ["return n.join(\" \\xB7 \")"],
                    "replacement": {
                        "path": "payloads/net-metadata-formatter.js",
                        "sha256": sha("payloads/net-metadata-formatter.js"),
                    },
                    "padding": "spaces",
                    "knownBehaviorChange": "This compact formatter omits rare bg metadata and PR repository prefix to fit the original byte budget.",
                },
                {
                    "opId": "wpf-lite-log-detector",
                    "label": "Detect Fable fallback during resume lite-log enrichment",
                    "type": "replace_between",
                    "startMarker": "async function wpf(e,t){if(!e.isLite||!e.fullPath)return e;",
                    "endMarker": "async function kJe",
                    "expectedStartMarkerCount": 1,
                    "expectedEndMarkerCount": 1,
                    "requireWithinRange": ["let n=await Nmc(e.fullPath,e.fileSize??0,t)", "projectPath:s"],
                    "replacement": {
                        "path": "payloads/wpf-lite-log-enrichment.js",
                        "sha256": sha("payloads/wpf-lite-log-enrichment.js"),
                    },
                    "padding": "spaces",
                },
            ],
            "postconditions": [
                {"type": "must_contain", "scope": "whole_binary", "value": "Fable classifier triggered"},
                {"type": "must_contain", "scope": "whole_binary", "value": "fableClassifierTriggered"},
            ],
        }
    ],
}

(ROOT / "patch.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
```

Run:

```bash
python3 packages/fable-fallback/write_manifest.py
rm packages/fable-fallback/write_manifest.py
python3 -m json.tool packages/fable-fallback/patch.json >/dev/null
```

Expected: `patch.json` exists and parses as JSON.

- [ ] **Step 5: Create reminder suppression payloads and manifest**

Create seven files under `/Users/MAC/Documents/Claude-patch/packages/reminder-suppression/payloads/`, each containing the replacement bytes from `/Users/MAC/Documents/Claude-patch/claude-reminder-suppression-patch.md`:

```text
todo-reminder.js                  -> case"todo_reminder":return[];
task-reminder.js                  -> case"task_reminder":return[];
tool-search-usage-reminder.js     -> case"tool_search_usage_reminder":return[];
token-usage.js                    -> token_usage:(e)=>[]
total-tokens-reminder.js          -> total_tokens_reminder:(e)=>[]
budget-usd.js                     -> budget_usd:(e)=>[]
output-token-usage.js             -> output_token_usage:(e)=>[]
```

Create `/Users/MAC/Documents/Claude-patch/packages/reminder-suppression/patch.json` using the operation markers from `/Users/MAC/Documents/Claude-patch/claude-reminder-suppression-patch.md` lines that define the `PATCHES` list. Include the same source identity as the Fable package, and set each payload SHA from `shasum -a 256 packages/reminder-suppression/payloads/*.js`.

- [ ] **Step 6: Add package README files**

Create `/Users/MAC/Documents/Claude-patch/packages/fable-fallback/README.md`:

```markdown
# Fable fallback visibility

Shows Fable fallback events in resumed Claude Code history and marks affected sessions in `/resume`.

This package injects executable JavaScript bytes into a copied Claude Code binary. It is declarative, but the replacement payload still executes inside Claude Code after patching.
```

Create `/Users/MAC/Documents/Claude-patch/packages/reminder-suppression/README.md`:

```markdown
# Reminder suppression

Suppresses selected recurring model-visible reminder attachments in a copied Claude Code binary.

This package intentionally leaves safety, permission, hook, file-state, and trust-boundary reminders intact.
```

- [ ] **Step 7: Run reference package tests**

```bash
python3 -m pytest tests/test_reference_packages.py -q
```

Expected: all tests pass.

- [ ] **Step 8: Commit reference packages**

```bash
git add packages tests/test_reference_packages.py
git commit -m "Add declarative reference patch packages"
```

---

### Task 11: Smoke/signing helpers with opt-in local real smoke

**Files:**
- Create: `/Users/MAC/Documents/Claude-patch/src/claude_monkey/smoke.py`
- Test: extend `/Users/MAC/Documents/Claude-patch/tests/test_builder.py`

- [ ] **Step 1: Add smoke helper tests**

Append to `/Users/MAC/Documents/Claude-patch/tests/test_builder.py`:

```python
from claude_monkey.smoke import CommandResult, smoke_version_and_help


def test_smoke_runner_records_commands(tmp_path):
    binary = tmp_path / "claude"
    binary.write_text("fake")
    calls = []

    def runner(argv):
        calls.append(argv)
        return CommandResult(argv=argv, returncode=0, stdout="ok", stderr="")

    results = smoke_version_and_help(binary, runner)
    assert [r.argv[-1] for r in results] == ["--version", "--help"]
    assert calls[0] == [str(binary), "--version"]
```

- [ ] **Step 2: Run test to verify failure**

```bash
python3 -m pytest tests/test_builder.py::test_smoke_runner_records_commands -q
```

Expected: FAIL with missing `smoke` module.

- [ ] **Step 3: Implement smoke helpers**

Create `/Users/MAC/Documents/Claude-patch/src/claude_monkey/smoke.py`:

```python
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CommandResult:
    argv: list[str]
    returncode: int
    stdout: str
    stderr: str


def run_command(argv: list[str]) -> CommandResult:
    proc = subprocess.run(argv, text=True, capture_output=True, check=False)
    return CommandResult(argv=argv, returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)


def smoke_version_and_help(binary: Path, runner=run_command) -> list[CommandResult]:
    return [runner([str(binary), "--version"]), runner([str(binary), "--help"])]


def codesign_verify(binary: Path, runner=run_command) -> CommandResult:
    return runner(["codesign", "--verify", "--deep", "--strict", "--verbose=4", str(binary)])
```

- [ ] **Step 4: Run smoke helper tests**

```bash
python3 -m pytest tests/test_builder.py::test_smoke_runner_records_commands -q
```

Expected: PASS.

- [ ] **Step 5: Commit smoke helpers**

```bash
git add src/claude_monkey/smoke.py tests/test_builder.py
git commit -m "Add injectable smoke test helpers"
```

---

### Task 12: Final verification and docs update

**Files:**
- Modify: `/Users/MAC/Documents/Claude-patch/README.md` only if still intended by current branch state.
- Possibly create: `/Users/MAC/Documents/Claude-patch/docs/claude-monkey-v1.md`

- [ ] **Step 1: Run the hermetic test suite**

Run:

```bash
python3 -m pytest -q
```

Expected: all tests pass.

- [ ] **Step 2: Run lint**

Run:

```bash
python3 -m ruff check .
```

Expected: no lint errors.

- [ ] **Step 3: Optional local real smoke**

Only run this if the user explicitly approves real local Claude smoke for this task. Do not mutate the official Claude binary.

```bash
CLAUDE_MONKEY_LOCAL_REAL_SMOKE=1 python3 -m pytest -m local_real_smoke -q
```

Expected: copied-binary smoke only; official Claude binary unchanged.

- [ ] **Step 4: Check git status and preserve existing dirt**

Run:

```bash
git status --short
```

Expected: implementation files are either committed or intentionally unstaged. Preserve any pre-existing unrelated changes, especially:

```text
 M README.md
?? claude-reminder-suppression-patch.md
```

unless the user explicitly asks to include them.

- [ ] **Step 5: Commit final docs if created**

```bash
git add docs/claude-monkey-v1.md README.md
git commit -m "Document ClaudeMonkey v1 CLI usage"
```

Only run this commit if those docs were actually created/modified as part of this plan.

---

## Self-review checklist for implementers

Before reporting completion:

- [ ] `python3 -m pytest -q` was run and passed.
- [ ] `python3 -m ruff check .` was run and passed, or ruff was unavailable and that is reported honestly.
- [ ] No package-provided executable scripts are run by the manager.
- [ ] Normal build path never writes over the source Claude binary.
- [ ] In-place replacement is fenced behind a separate explicit command path or left unimplemented with clear CLI messaging.
- [ ] Prompt profile injection defaults to append mode.
- [ ] User-supplied prompt flags override profile injection.
- [ ] All overlaps are rejected, including identical overlaps.
- [ ] Build reports are written for both success and failure.
- [ ] Existing unrelated worktree dirt is preserved.
