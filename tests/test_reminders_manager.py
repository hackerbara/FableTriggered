from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from claude_monkey.builder_v15 import BuildRequestV15, build_patchset_v15
from claude_monkey.manifest_v2 import load_manifest_v2_dict
from claude_monkey.payloads import load_payload_bytes

# NOTE: packages/reminders-manager/patch.json does not exist yet (authored in
# parallel; see docs/superpowers/specs/2026-07-03-reminders-manager-design.md).
# Every test below that needs the manifest calls _skip_if_no_manifest() first
# so this file passes cleanly (skips, not failures/errors) until the manifest
# lands. Tests in section C (deny payload sanity) do not need the manifest and
# run against the two payloads that already exist:
#   payloads/rm-filter-labels-before-ug-2.1.199.js
#   payloads/rm-filter-before-li-2.1.199.js

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "packages" / "reminders-manager"
HIDDEN_CONTEXT_DRAWER_DIR = ROOT / "packages" / "hidden-context-drawer"
NORMAL_CHANNEL_DIR = ROOT / "packages" / "normal-channel-hidden-context"
UPSTREAM_ATTACHMENT_SUPPRESSION_DIR = ROOT / "packages" / "upstream-attachment-suppression"

LIVE_2_1_199 = Path("/Users/MAC/.local/share/claude/versions/2.1.199")
MODULE_DUMP = ROOT / ".development" / "tmp-module0-2.1.199.js"
MODULE_PATH = "/$bunfs/root/src/entrypoints/cli.js"

EXPECTED_SOURCE_SHA = "e3cb61abc8a2ec7b98976cee1ffdde5a3fa755c9990bc8d688cd89290e0dcec0"
EXPECTED_MODULE_SHA = "e30c857c2e1130ff0fa9d14349a210c588f8115fc8ac86e120c454547efc0c55"
EXPECTED_MODULE_LENGTH = 18593981

DENY_FAMILIES = [
    "todo_reminder",
    "task_reminder",
    "tool_search_usage_reminder",
    "token_usage",
    "total_tokens_reminder",
    "budget_usd",
    "output_token_usage",
]

KEPT_TYPES = [
    "hook_success",
    "hook_additional_context",
    "hook_blocking_error",
    "hook_stopped_continuation",
    "command_permissions",
    "agent_mention",
    "critical_system_reminder",
    "edited_text_file",
    "opened_file_in_ide",
    "plan_mode",
    "plan_mode_exit",
    "plan_mode_reentry",
    "auto_mode",
    "auto_mode_exit",
    "team_context",
    "memory_update",
    "mcp_instructions_delta",
    "deferred_tools_delta",
    "diagnostics",
    "lsp_diagnostics",
    "queued_command",
    "file_reference",
    "pdf_reference",
    "directory_reference",
]


def _manifest_path() -> Path:
    return PACKAGE_DIR / "patch.json"


def _skip_if_no_manifest() -> None:
    if not _manifest_path().exists():
        pytest.skip(
            "packages/reminders-manager/patch.json has not been authored yet "
            "(package is being written in parallel); skipping manifest-dependent test"
        )


def _load_manifest():
    return load_manifest_v2_dict(json.loads(_manifest_path().read_text()))


def _live_2_1_199_source_or_skip() -> bytes:
    if not LIVE_2_1_199.exists():
        pytest.skip(f"local Claude Code 2.1.199 source missing: {LIVE_2_1_199}")
    source = LIVE_2_1_199.read_bytes()
    actual = hashlib.sha256(source).hexdigest()
    if actual != EXPECTED_SOURCE_SHA:
        pytest.skip(f"live Claude source is not the pinned 2.1.199 target: {actual}")
    return source


def _build(tmp_path: Path, package_dirs: list[Path]):
    return build_patchset_v15(
        BuildRequestV15(
            source_path=LIVE_2_1_199,
            output_dir=tmp_path / "out",
            package_dirs=package_dirs,
            source_version="2.1.199",
            source_version_output="2.1.199 (Claude Code)",
            platform="darwin",
            arch="arm64",
        )
    )


def _rm_payload_texts() -> tuple[str, str]:
    ug_payload = (
        PACKAGE_DIR / "payloads" / "rm-filter-labels-before-ug-2.1.199.js"
    ).read_text(encoding="utf-8")
    hze_payload = (
        PACKAGE_DIR / "payloads" / "rm-filter-before-li-2.1.199.js"
    ).read_text(encoding="utf-8")
    return ug_payload, hze_payload


# ---------------------------------------------------------------------------
# A. Manifest integrity (skip until patch.json lands)
# ---------------------------------------------------------------------------


def test_reminders_manager_manifest_loads_v15_schema_v2_with_valid_payload_hashes():
    _skip_if_no_manifest()
    manifest = _load_manifest()
    assert manifest.id == "reminders-manager"
    assert manifest.schema_version == 2
    for target in manifest.targets:
        assert target.required_engine == "bun_graph_repack"
        assert target.required_binary_format == "bun_standalone_macho64"
        assert [module.path for module in target.modules] == [MODULE_PATH]
        for module in target.modules:
            assert module.content_sha256
            assert module.content_length > 0
            for operation in module.operations:
                # load_payload_bytes verifies the payload file's sha256 (and,
                # implicitly, that it exists) against the manifest entry.
                payload = load_payload_bytes(operation.replacement, PACKAGE_DIR)
                assert payload
                if operation.replacement.path is not None:
                    on_disk = (PACKAGE_DIR / operation.replacement.path).stat().st_size
                    assert on_disk == len(payload)


def test_reminders_manager_targets_pinned_stock_2_1_199_module_identity():
    """The package should be anchored on the same stock module the rest of the
    repo is pinned to (same source binary / module0 as hidden-context-drawer
    and upstream-attachment-suppression)."""
    _skip_if_no_manifest()
    manifest = _load_manifest()
    target = manifest.targets[0]
    assert target.source_identity.claude_version == "2.1.199"
    assert target.source_identity.sha256 == EXPECTED_SOURCE_SHA
    module = target.modules[0]
    assert module.content_sha256 == EXPECTED_MODULE_SHA
    assert module.content_length == EXPECTED_MODULE_LENGTH


def test_reminders_manager_operation_anchors_are_unique_in_stock_module_dump():
    """Every replace_exact `exact` string, and every replace_between marker
    pair, must resolve unambiguously against the stock 2.1.199 module dump."""
    _skip_if_no_manifest()
    if not MODULE_DUMP.exists():
        pytest.skip(f"stock module dump missing: {MODULE_DUMP}")
    dump_bytes = MODULE_DUMP.read_bytes()
    if hashlib.sha256(dump_bytes).hexdigest() != EXPECTED_MODULE_SHA:
        pytest.skip("stock module dump does not match the pinned 2.1.199 module identity")
    source = dump_bytes.decode("utf-8")

    manifest = _load_manifest()
    for target in manifest.targets:
        if target.source_identity.claude_version != "2.1.199":
            continue
        for module in target.modules:
            for operation in module.operations:
                if operation.type == "replace_exact":
                    assert operation.exact is not None, operation.op_id
                    count = source.count(operation.exact)
                    assert count == 1, f"{operation.op_id}: expected 1 occurrence, found {count}"
                    if operation.old_range_length is not None:
                        assert operation.old_range_length == len(
                            operation.exact.encode("utf-8")
                        ), operation.op_id
                    if operation.old_range_sha256 is not None:
                        assert operation.old_range_sha256 == hashlib.sha256(
                            operation.exact.encode("utf-8")
                        ).hexdigest(), operation.op_id
                elif operation.type == "replace_between":
                    assert operation.start_marker is not None, operation.op_id
                    assert operation.end_marker is not None, operation.op_id
                    start_count = source.count(operation.start_marker)
                    end_count = source.count(operation.end_marker)
                    assert (
                        start_count == operation.expected_start_marker_count
                    ), f"{operation.op_id} startMarker: expected {operation.expected_start_marker_count}, found {start_count}"
                    assert (
                        end_count == operation.expected_end_marker_count
                    ), f"{operation.op_id} endMarker: expected {operation.expected_end_marker_count}, found {end_count}"


def test_reminders_manager_declares_manual_smoke_for_the_drawer_ui():
    """ASSUMPTION (per design spec 'Testing' section): manualSmoke.required is
    true because the row-cursor/toggle interaction has no smoke-tested
    precedent. If the manifest ships with manualSmoke.required=false, update
    this test to match."""
    _skip_if_no_manifest()
    manifest = _load_manifest()
    for target in manifest.targets:
        if target.source_identity.claude_version == "2.1.199":
            assert target.manual_smoke.required is True
            assert target.manual_smoke.reason


def test_reminders_manager_does_not_ship_hidden_context_drawer_internals():
    """The two packages must remain independently installable/disjoint: RM
    payloads should not reference the drawer's private globals/functions, and
    vice versa is covered by the drawer's own tests."""
    _skip_if_no_manifest()
    manifest_data = json.loads(_manifest_path().read_text())
    serialized = json.dumps(manifest_data, sort_keys=True)
    for forbidden in (
        "__CODEX_HIDDEN_CONTEXT_DRAWER",
        "__codexNCHCProjectList",
        "__codexUASDropLabel",
        "__codexUASDropAttachment",
    ):
        assert forbidden not in serialized


# ---------------------------------------------------------------------------
# B. Composition builds (opt-in real-binary builds; skip until patch.json
#    lands and/or the pinned local Claude Code 2.1.199 source is missing).
# ---------------------------------------------------------------------------


@pytest.mark.local_real_smoke
def test_reminders_manager_builds_alone_against_stock_2_1_199(tmp_path):
    _skip_if_no_manifest()
    _live_2_1_199_source_or_skip()
    report = _build(tmp_path, [PACKAGE_DIR])
    assert report.failureReason is None, report.failureReason
    assert report.automatedStatus == "passed"
    assert report.enabledPatches == ["reminders-manager"]
    # ASSUMPTION: manualSmoke.required=true (see test above), so the build
    # succeeds but activation is blocked pending a manual TUI smoke pass.
    assert report.status == "manual_smoke_pending"
    assert "manual_smoke_pending" in report.activationBlockers
    assert report.activationEligible is False


@pytest.mark.local_real_smoke
def test_reminders_manager_stacks_with_hidden_context_drawer(tmp_path):
    _skip_if_no_manifest()
    _live_2_1_199_source_or_skip()
    report = _build(tmp_path, [PACKAGE_DIR, HIDDEN_CONTEXT_DRAWER_DIR])
    assert report.failureReason is None, report.failureReason
    assert report.automatedStatus == "passed"
    assert set(report.enabledPatches) == {"reminders-manager", "hidden-context-drawer"}
    assert "manual_smoke_pending" in report.activationBlockers


@pytest.mark.local_real_smoke
def test_reminders_manager_stacks_with_normal_channel_hidden_context(tmp_path):
    _skip_if_no_manifest()
    _live_2_1_199_source_or_skip()
    report = _build(tmp_path, [PACKAGE_DIR, NORMAL_CHANNEL_DIR])
    assert report.failureReason is None, report.failureReason
    assert report.automatedStatus == "passed"
    assert set(report.enabledPatches) == {"reminders-manager", "normal-channel-hidden-context"}


@pytest.mark.local_real_smoke
def test_reminders_manager_conflicts_with_upstream_attachment_suppression_by_design(tmp_path):
    """UAS and reminders-manager both own the ug()/Hze() seams; a stacked
    build must fail with patch_conflict. This is documented as intentional in
    the design spec (they are alternative, not composable, packages)."""
    _skip_if_no_manifest()
    _live_2_1_199_source_or_skip()
    report = _build(tmp_path, [PACKAGE_DIR, UPSTREAM_ATTACHMENT_SUPPRESSION_DIR])
    assert report.status == "failed"
    assert report.automatedStatus == "failed"
    assert report.failureReason is not None
    assert "patch_conflict" in report.failureReason


# ---------------------------------------------------------------------------
# C. Deny payload sanity (runs now; no manifest required)
# ---------------------------------------------------------------------------


def test_reminders_manager_deny_payloads_define_expected_state_and_gate_functions():
    ug_payload, hze_payload = _rm_payload_texts()
    assert "function __codexRMState(){" in ug_payload
    assert "function __codexRMDenyLabel(e)" in ug_payload
    assert "function __codexRMDenyAttachment(e)" in ug_payload
    assert "globalThis.__CODEX_REMINDERS_MANAGER_V1__" in ug_payload
    assert "async function ug(e,t){" in ug_payload
    assert "async function*Hze(e,t,n,r,o,s,i,a){" in hze_payload
    for family in DENY_FAMILIES:
        assert family in ug_payload
    for kept in KEPT_TYPES:
        assert kept not in ug_payload
        assert kept not in hze_payload


def test_reminders_manager_deny_payloads_gate_before_telemetry_and_li_wrapping():
    ug_payload, hze_payload = _rm_payload_texts()
    label_guard = ug_payload.index("if(__codexRMDenyLabel(e))return[]")
    start_timer = ug_payload.index("let n=Date.now()")
    await_generator = ug_payload.index("let r=await t()")
    compute_telemetry = ug_payload.index('G("tengu_attachment_compute_duration"')
    assert label_guard < start_timer < await_generator < compute_telemetry

    hze_filter = hze_payload.index("l=l.filter((c)=>!__codexRMDenyAttachment(c))")
    hze_empty = hze_payload.index("if(l.length===0)return")
    hze_telemetry = hze_payload.index('G("tengu_attachments"')
    hze_li = hze_payload.index("yield li(c,o)")
    assert hze_filter < hze_empty < hze_telemetry < hze_li


def test_reminders_manager_deny_state_defaults_to_all_blocked_and_fails_closed():
    """Missing/undefined global state must re-initialize to all-denied (fail
    closed): a broken or not-yet-rendered UI never accidentally un-suppresses
    a family."""
    ug_payload, _ = _rm_payload_texts()
    script = "\n".join(
        [
            ug_payload,
            r"""
if (globalThis.__CODEX_REMINDERS_MANAGER_V1__ !== undefined) {
  throw new Error("test setup: global should start undefined");
}
let state = __codexRMState();
for (const family of ["todo_reminder","task_reminder","tool_search_usage_reminder","token_usage","total_tokens_reminder","budget_usd","output_token_usage"]) {
  if (state.deny[family] !== true) throw new Error("expected default-deny for " + family);
}
if (globalThis.__CODEX_REMINDERS_MANAGER_V1__ !== state) {
  throw new Error("init guard should publish the default state onto globalThis");
}
if (!__codexRMDenyLabel("todo_reminders")) {
  throw new Error("todo_reminders label should be denied by default (both rows denied)");
}
for (const type of ["todo_reminder","task_reminder","tool_search_usage_reminder","token_usage","total_tokens_reminder","budget_usd","output_token_usage"]) {
  if (!__codexRMDenyAttachment({type})) throw new Error("type should be denied by default: " + type);
}
for (const type of ["hook_additional_context","critical_system_reminder","plan_mode","memory_update","diagnostics","queued_command"]) {
  if (__codexRMDenyAttachment({type})) throw new Error("unrelated type should never be denied: " + type);
}
""",
        ]
    )
    result = subprocess.run(
        ["node", "-e", script], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
    )
    assert result.returncode == 0, result.stderr


def test_reminders_manager_shared_todo_reminders_label_gates_only_when_both_rows_denied():
    """Core semantics from the design doc: ug("todo_reminders", f) drives both
    todo_reminder and task_reminder attachment types from one generator call.
    The label gate must therefore deny the shared label iff BOTH rows are
    denied; if only one row is denied, the generator still runs and the Hze
    object filter drops just the denied type (per-row suppression parity)."""
    ug_payload, hze_payload = _rm_payload_texts()
    script = "\n".join(
        [
            "let telemetry=[];",
            "function G(name,payload){telemetry.push({name,payload})}",
            "function Ie(value){return JSON.stringify(value)}",
            "class MM extends Error {}",
            "function C(){}",
            "function sr(value){return value}",
            "function Bo(value){return value}",
            "function He(){}",
            "function n6(){return undefined}",
            "let W9l;",
            "let li;",
            ug_payload,
            hze_payload,
            r'''
(async()=>{
  // Baseline: both rows denied -> shared label gated, generator never runs.
  let genRan = false;
  let dropped = await ug("todo_reminders", async()=>{genRan=true; return [{type:"todo_reminder"},{type:"task_reminder"}]});
  if (genRan) throw new Error("generator should not run while both todo_reminder and task_reminder are denied");
  if (dropped.length !== 0) throw new Error("gated label should return an empty array");

  // Enable only task_reminder: label must NOT be gated (only one of the pair denied).
  globalThis.__CODEX_REMINDERS_MANAGER_V1__.deny.task_reminder = false;
  if (__codexRMDenyLabel("todo_reminders")) {
    throw new Error("shared label must run once only one of todo_reminder/task_reminder is denied");
  }
  if (!__codexRMDenyAttachment({type:"todo_reminder"})) throw new Error("todo_reminder should still be denied");
  if (__codexRMDenyAttachment({type:"task_reminder"})) throw new Error("task_reminder should now be allowed");

  genRan = false;
  let both = await ug("todo_reminders", async()=>{genRan=true; return [{type:"todo_reminder"},{type:"task_reminder"}]});
  if (!genRan) throw new Error("generator should run once only one of the pair is denied");
  if (both.length !== 2) throw new Error("ug() itself must not drop rows; only the Hze object filter splits todo/task");

  W9l = async () => both;
  let wrapped = [];
  li = (attachment) => { wrapped.push(attachment.type); return {type:"attachment", attachment}; };
  let yielded = [];
  for await (const row of Hze(null,null,null,null,null,null,null,null)) yielded.push(row.attachment.type);
  if (yielded.join(",") !== "task_reminder") {
    throw new Error("Hze must filter out the still-denied todo_reminder and keep only task_reminder, got: " + yielded.join(","));
  }

  // Re-deny task_reminder: both denied again -> shared label gated again.
  globalThis.__CODEX_REMINDERS_MANAGER_V1__.deny.task_reminder = true;
  if (!__codexRMDenyLabel("todo_reminders")) {
    throw new Error("shared label should be gated again once both rows are denied");
  }

  // Single-type families gate directly off their own boolean.
  globalThis.__CODEX_REMINDERS_MANAGER_V1__.deny.token_usage = false;
  if (__codexRMDenyLabel("token_usage")) throw new Error("token_usage label should not be gated once its own flag is false");
  if (__codexRMDenyAttachment({type:"token_usage"})) throw new Error("token_usage type should not be denied once its own flag is false");
})().catch((err)=>{console.error(err.stack||err.message); process.exit(1)});
''',
        ]
    )
    result = subprocess.run(
        ["node", "-e", script], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False
    )
    assert result.returncode == 0, result.stderr
