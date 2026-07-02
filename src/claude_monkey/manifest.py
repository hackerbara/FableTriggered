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
