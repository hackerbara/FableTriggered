from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from claude_monkey.builder_v15 import BuildRequestV15, build_patchset_v15, load_manifest_v2
from claude_monkey.payloads import load_payload_bytes

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = "/$bunfs/root/src/entrypoints/cli.js"
SOURCE_2_1_201 = Path("/Users/MAC/.local/share/claude/versions/2.1.201")
MODULE_DUMP_2_1_201 = ROOT / ".development" / "artifacts" / "claude-2.1.201-framework-source-module0.js"
FOOTER_DRAWERS = ROOT / "packages" / "footer-drawers"
HC = ROOT / "packages" / "hidden-context-drawer"
THINKING = ROOT / "packages" / "thinking-text-drawer"
REMINDERS = ROOT / "packages" / "reminders-manager"

EXPECTED_BINARY_SHA = "a0852d76afc47b30f5cb0b7625ec9a7714cb189f2eeef6c28c77e2be954fb7fd"
EXPECTED_BINARY_SIZE = 231708784
EXPECTED_MODULE_SHA = "46db617a7b13c062fb31595f6244819b11f7cdc6e6fed8e2c3f74a27fb6da1bd"
EXPECTED_MODULE_LENGTH = 18700756

FRAMEWORK_OP_IDS = {
    "fd-bootstrap-and-overlay",
    "fd-footer-render-tick-state",
    "fd-footer-render-tick-effect",
    "fd-footer-target-drawers",
    "fd-footer-target-deps",
    "fd-footer-selection-flag",
    "fd-footer-action-wrap-open",
    "fd-footer-action-wrap-close",
    "fd-footer-space-binding",
    "fd-footer-bar-var",
    "fd-footer-bar-shortcuts-condition",
    "fd-footer-bar-null-condition",
    "fd-footer-bar-render",
    "fd-footer-bar-selection-state",
}

MOVED_THINKING_OP_IDS = {
    "thinking-footer-open-state",
    "thinking-footer-target",
    "thinking-footer-selection-flag",
    "thinking-footer-action-wrap-open",
    "thinking-footer-action-wrap-close",
    "thinking-selected-overlay-globals",
    "thinking-bottom-overlay-renderer",
    "thinking-footer-status-bar",
}


def _manifest_json(package_dir: Path) -> dict:
    return json.loads((package_dir / "patch.json").read_text(encoding="utf-8"))


def _source_or_skip() -> Path:
    if not SOURCE_2_1_201.exists():
        pytest.skip(f"missing local Claude source: {SOURCE_2_1_201}")
    actual = hashlib.sha256(SOURCE_2_1_201.read_bytes()).hexdigest()
    if actual != EXPECTED_BINARY_SHA:
        pytest.skip(f"local Claude source SHA changed: {actual}")
    return SOURCE_2_1_201


def _module_dump_or_skip() -> str:
    if not MODULE_DUMP_2_1_201.exists():
        pytest.skip(f"missing module dump: {MODULE_DUMP_2_1_201}")
    data = MODULE_DUMP_2_1_201.read_bytes()
    if hashlib.sha256(data).hexdigest() != EXPECTED_MODULE_SHA:
        pytest.skip("module dump SHA does not match 2.1.201 target")
    return data.decode("utf-8")


def test_footer_drawers_manifest_targets_latest_local_2_1_201() -> None:
    manifest = _manifest_json(FOOTER_DRAWERS)
    assert manifest["schemaVersion"] == 2
    assert manifest["id"] == "footer-drawers"
    assert manifest.get("requiresPackages", []) == []
    assert manifest.get("conflictsWithPackages", []) == []
    target = manifest["targets"][0]
    assert target["sourceIdentity"] == {
        "claudeVersion": "2.1.201",
        "versionOutput": "2.1.201 (Claude Code)",
        "sha256": EXPECTED_BINARY_SHA,
        "sizeBytes": EXPECTED_BINARY_SIZE,
        "platform": "darwin",
        "arch": "arm64",
    }
    module = target["modules"][0]
    assert module["path"] == MODULE_PATH
    assert module["contentSha256"] == EXPECTED_MODULE_SHA
    assert module["contentLength"] == EXPECTED_MODULE_LENGTH
    assert {op["opId"] for op in module["operations"]} == FRAMEWORK_OP_IDS


def test_footer_drawers_payloads_are_ascii_safe_and_hashes_match() -> None:
    manifest = load_manifest_v2(FOOTER_DRAWERS)
    for target in manifest.targets:
        for module in target.modules:
            for operation in module.operations:
                payload = load_payload_bytes(operation.replacement, FOOTER_DRAWERS)
                assert payload
                if operation.replacement.path:
                    path = FOOTER_DRAWERS / operation.replacement.path
                    assert operation.replacement.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()
                    text = path.read_text(encoding="utf-8")
                    offenders = [(i, line) for i, line in enumerate(text.splitlines(), 1) if any(ord(ch) > 127 for ch in line)]
                    assert offenders == [], f"non-ascii payload text in {path}: {offenders[:3]}"


def test_footer_drawers_payload_defines_registry_lifecycle_contract() -> None:
    text = (FOOTER_DRAWERS / "payloads" / "01-bootstrap-and-overlay.js").read_text(encoding="utf-8")
    required = [
        "__codexFDDrawers",
        "__codexFDRegister",
        "__codexFDBump",
        "__codexFDAvailable",
        "__codexFDOpen",
        "__codexFDClose",
        "__codexFDWrapActions",
        "__codexFDDrawerPanel",
        "hoverId",
        "openId",
        "onOpen",
        "onClose",
        "badge",
        "flash",
    ]
    for needle in required:
        assert needle in text
    assert "footer:clearSelection" in text
    clear_handler = text.split('r["footer:clearSelection"]=', 1)[1].split(';return r}', 1)[0]
    assert 'if(a){if(__codexFDSafe(()=>a.onKey?.("clearSelection")' in clear_handler
    assert 'l();return}return e["footer:clearSelection"]?.()' in clear_handler
    assert "__codexFDClose(\"escape\")" not in text
    assert "__codexFDClose(\"x\")" in text


def _run_footer_drawers_payload_js(body: str) -> dict:
    bootstrap = FOOTER_DRAWERS / "payloads" / "01-bootstrap-and-overlay.js"
    script = f"""
const fs = require("fs");
const Xd = {{
  Fragment: "Fragment",
  jsx: (type, props, key) => ({{type: typeof type === "function" ? type.name : type, props, key}}),
  jsxs: (type, props, key) => ({{type: typeof type === "function" ? type.name : type, props, key}}),
}};
function B(props) {{ return props; }}
function v(props) {{ return props; }}
const MXe = {{ c: (n) => new Array(n) }};
function clc() {{ return null; }}
eval(fs.readFileSync({str(bootstrap)!r}, "utf8"));
{body}
"""
    result = subprocess.run(["node", "-e", script], check=True, text=True, capture_output=True)
    return json.loads(result.stdout)


def test_footer_drawers_bar_consumes_active_selection_and_renders_per_entry_hints() -> None:
    bar_payload = (FOOTER_DRAWERS / "payloads" / "10-footer-bar-var.js").read_text(encoding="utf-8")
    selection_payload = (FOOTER_DRAWERS / "payloads" / "14-footer-bar-selection-state.js").read_text(encoding="utf-8")
    bootstrap_payload = (FOOTER_DRAWERS / "payloads" / "01-bootstrap-and-overlay.js").read_text(encoding="utf-8")
    assert "FDsel=Tt((Me)=>Me.footerSelection===\"drawers\")" in selection_payload
    assert "Tt((Me)=>Me.footerSelection" not in bar_payload
    assert "__codexFDBar(FDsel)" in bar_payload
    assert "__codexFDBar(FDs)" not in bar_payload
    assert "children:__codexFDBarText()" not in bar_payload
    assert "Xd.jsx(O1f,{selected:o.selected" in bootstrap_payload
    assert 'color:o.selected?"background"' not in bootstrap_payload

    data = _run_footer_drawers_payload_js(
        """
__codexFDDrawers().entries = [];
__codexFDRegister({id:"hidden",order:100,available:()=>true,label:()=>"Hidden",badge:()=>"2"});
__codexFDRegister({id:"thinking",order:200,available:()=>true,label:()=>"Thinking"});
__codexFDRegister({id:"reminders",order:300,available:()=>true,label:()=>"Reminders",flash:()=>true});
__codexFDAvailable();
__codexFDDrawers().hoverId = "thinking";
console.log(JSON.stringify({
  active: __codexFDBarItems(true),
  inactive: __codexFDBarItems(false)
}));
"""
    )

    assert [item["id"] for item in data["active"]] == ["hidden", "thinking", "reminders"]
    assert [item["hintKind"] for item in data["active"]] == ["arrow", "enter", "arrow"]
    assert [item["selected"] for item in data["active"]] == [False, True, False]
    assert [item["hintKind"] for item in data["inactive"]] == ["arrow", "arrow", "arrow"]
    assert [item["selected"] for item in data["inactive"]] == [False, False, False]



def test_footer_drawers_landing_resets_hover_only_when_toolbar_becomes_active() -> None:
    data = _run_footer_drawers_payload_js(
        """
__codexFDDrawers().entries = [];
__codexFDRegister({id:"hidden",order:100,available:()=>true,label:()=>"Hidden"});
__codexFDRegister({id:"thinking",order:200,available:()=>true,label:()=>"Thinking"});
__codexFDRegister({id:"reminders",order:300,available:()=>true,label:()=>"Reminders"});
let state = __codexFDDrawers();
let inactiveItems = __codexFDBarItems(false);
let hoverBefore = state.hoverId;
__codexFDSetActive(true);
let afterLanding = {hoverId: state.hoverId, items: __codexFDBarItems(true)};
__codexFDMove(1);
let afterRight = {hoverId: state.hoverId, items: __codexFDBarItems(true)};
__codexFDSetActive(false);
__codexFDSetActive(true);
let afterReenter = {hoverId: state.hoverId, items: __codexFDBarItems(true)};
console.log(JSON.stringify({hoverBefore, inactiveItems, afterLanding, afterRight, afterReenter}));
"""
    )

    assert data["hoverBefore"] is None
    assert [item["selected"] for item in data["inactiveItems"]] == [False, False, False]
    assert data["afterLanding"]["hoverId"] == "hidden"
    assert [item["hintKind"] for item in data["afterLanding"]["items"]] == ["enter", "arrow", "arrow"]
    assert data["afterRight"]["hoverId"] == "thinking"
    assert [item["hintKind"] for item in data["afterRight"]["items"]] == ["arrow", "enter", "arrow"]
    assert data["afterReenter"]["hoverId"] == "hidden"
    assert [item["hintKind"] for item in data["afterReenter"]["items"]] == ["enter", "arrow", "arrow"]

def test_footer_drawers_open_clear_selection_delegates_without_closing_and_x_keeps_drawers_selected() -> None:
    data = _run_footer_drawers_payload_js(
        """
__codexFDDrawers().entries = [];
let stockClear = 0;
let closedReason = null;
let selected = [];
__codexFDRegister({
  id:"hidden",
  order:100,
  available:()=>true,
  label:()=>"Hidden",
  onKey:(key)=>false,
  onClose:(reason)=>{ closedReason = reason; }
});
__codexFDOpen("hidden");
let actions = __codexFDWrapActions({
  "footer:clearSelection":()=>{ stockClear += 1; },
  "footer:close":()=>{ closedReason = "stock"; }
}, "drawers", (value)=>{ selected.push(value); });
actions["footer:clearSelection"]();
let afterClear = {openId: __codexFDDrawers().openId, stockClear, selected: selected.slice()};
actions["footer:close"]();
console.log(JSON.stringify({
  afterClear,
  afterClose: {openId: __codexFDDrawers().openId, closedReason, selected}
}));
"""
    )

    assert data["afterClear"] == {"openId": "hidden", "stockClear": 0, "selected": ["drawers"]}
    assert data["afterClose"] == {
        "openId": None,
        "closedReason": "x",
        "selected": ["drawers", "drawers"],
    }


def test_footer_drawers_operations_resolve_once_in_2_1_201_module_dump() -> None:
    source = _module_dump_or_skip()
    manifest = _manifest_json(FOOTER_DRAWERS)
    operations = manifest["targets"][0]["modules"][0]["operations"]
    for operation in operations:
        if operation["type"] == "replace_exact":
            exact = operation["exact"]
            assert source.count(exact) == 1, operation["opId"]
            assert len(exact.encode("utf-8")) == operation["oldRangeLength"]
            assert hashlib.sha256(exact.encode("utf-8")).hexdigest() == operation["oldRangeSha256"]
        elif operation["type"] in {"insert_before", "insert_after"}:
            anchor = operation["anchor"]
            assert source.count(anchor) == operation.get("expectedAnchorCount", 1), operation["opId"]
        elif operation["type"] == "replace_substring_within":
            start = operation["startMarker"]
            end = operation["endMarker"]
            assert source.count(start) == operation.get("expectedStartMarkerCount", 1), operation["opId"]
            start_index = source.index(start)
            end_index = source.index(end, start_index + len(start)) + len(end)
            context = source[start_index:end_index]
            assert context.count(operation["subExact"]) == operation.get("expectedSubExactCount", 1), operation["opId"]
        else:
            raise AssertionError(operation)


def test_thin_drawers_require_footer_drawers_after_migration() -> None:
    for package_dir in [HC, THINKING, REMINDERS]:
        manifest = load_manifest_v2(package_dir)
        assert "footer-drawers" in manifest.requires_packages, package_dir


def test_thinking_direct_footer_ops_are_removed_after_migration() -> None:
    manifest = load_manifest_v2(THINKING)
    op_ids = {op.op_id for target in manifest.targets for module in target.modules for op in module.operations}
    assert op_ids.isdisjoint(MOVED_THINKING_OP_IDS)
    assert "thinking-register-footer-drawer" in op_ids
    assert {
        "thinking-helpers-before-ypr",
        "thinking-message-start-turn-collector",
        "thinking-message-stop-turn-collector",
        "thinking-live-delta-collector",
        "thinking-signature-collector",
        "thinking-parent-structured-collector",
        "thinking-system-token-estimate",
        "thinking-cancel-salvage-collector",
    }.issubset(op_ids)


def test_build_framework_alone_reaches_manual_smoke_pending(tmp_path) -> None:
    source = _source_or_skip()
    report = build_patchset_v15(
        BuildRequestV15(
            source_path=source,
            output_dir=tmp_path / "framework-alone",
            package_dirs=[FOOTER_DRAWERS],
            source_version="2.1.201",
            source_version_output="2.1.201 (Claude Code)",
            platform="darwin",
            arch="arm64",
        )
    )
    assert report.automatedStatus == "passed"
    assert report.status == "manual_smoke_pending"
    assert report.activationEligible is False


def _write_matching_uas_conflict_fixture(tmp_path: Path) -> Path:
    fixture = tmp_path / "upstream-attachment-suppression-fixture"
    payload_dir = fixture / "payloads"
    payload_dir.mkdir(parents=True)
    payload = b"/* unused: package conflict is checked before operation planning */\n"
    (payload_dir / "noop.js").write_bytes(payload)
    manifest = {
        "schemaVersion": 2,
        "id": "upstream-attachment-suppression",
        "name": "UAS Conflict Fixture",
        "description": "2.1.201 identity fixture used only to verify Reminders package relationship conflicts.",
        "packageVersion": "2.1.201-fixture",
        "targets": [{
            "sourceIdentity": {
                "claudeVersion": "2.1.201",
                "versionOutput": "2.1.201 (Claude Code)",
                "sha256": EXPECTED_BINARY_SHA,
                "sizeBytes": EXPECTED_BINARY_SIZE,
                "platform": "darwin",
                "arch": "arm64",
            },
            "requiredEngine": "bun_graph_repack",
            "requiredBinaryFormat": "bun_standalone_macho64",
            "modules": [{
                "path": MODULE_PATH,
                "contentSha256": EXPECTED_MODULE_SHA,
                "contentLength": EXPECTED_MODULE_LENGTH,
                "operations": [{
                    "opId": "uas-conflict-fixture-noop",
                    "label": "Unused fixture operation",
                    "type": "replace_exact",
                    "exact": "__uas_conflict_fixture_never_reaches_planning__",
                    "replacement": {"path": "payloads/noop.js", "sha256": hashlib.sha256(payload).hexdigest()},
                    "knownBehaviorChange": "Never planned; relationship conflict should fail first.",
                }],
            }],
            "preconditions": [],
            "postconditions": [],
            "manualSmoke": {"required": False, "reason": None},
        }],
    }
    (fixture / "patch.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return fixture


def test_reminders_conflicts_with_matching_uas_fixture_when_framework_is_present(tmp_path) -> None:
    source = _source_or_skip()
    uas_fixture = _write_matching_uas_conflict_fixture(tmp_path)
    report = build_patchset_v15(
        BuildRequestV15(
            source_path=source,
            output_dir=tmp_path / "reminders-uas",
            package_dirs=[FOOTER_DRAWERS, REMINDERS, uas_fixture],
            source_version="2.1.201",
            source_version_output="2.1.201 (Claude Code)",
            platform="darwin",
            arch="arm64",
        )
    )
    assert report.status == "failed"
    assert report.failureReason is not None
    assert "patch_conflict:package_conflict:reminders-manager:upstream-attachment-suppression" in report.failureReason
import itertools


def _build_packages(tmp_path: Path, name: str, packages: list[Path]):
    source = _source_or_skip()
    return build_patchset_v15(
        BuildRequestV15(
            source_path=source,
            output_dir=tmp_path / name,
            package_dirs=packages,
            source_version="2.1.201",
            source_version_output="2.1.201 (Claude Code)",
            platform="darwin",
            arch="arm64",
        )
    )


@pytest.mark.parametrize(
    ("name", "packages"),
    [
        ("framework-thinking", [FOOTER_DRAWERS, THINKING]),
        ("framework-hidden", [FOOTER_DRAWERS, HC]),
        ("framework-reminders", [FOOTER_DRAWERS, REMINDERS]),
        ("framework-hidden-thinking", [FOOTER_DRAWERS, HC, THINKING]),
        ("framework-hidden-reminders", [FOOTER_DRAWERS, HC, REMINDERS]),
        ("framework-thinking-reminders", [FOOTER_DRAWERS, THINKING, REMINDERS]),
        ("framework-all", [FOOTER_DRAWERS, HC, THINKING, REMINDERS]),
    ],
)
def test_footer_drawers_successful_composition_matrix(tmp_path, name, packages) -> None:
    report = _build_packages(tmp_path, name, packages)
    assert report.automatedStatus == "passed", report.failureReason
    assert report.status == "manual_smoke_pending"
    assert report.activationEligible is False
    assert report.enabledPatches == [p.name for p in packages]
    if name == "framework-all":
        registrations = [
            (op["packageId"], op["opId"], op["insertOrder"], op.get("insertionVerified"))
            for op in report.operationsApplied
            if op["opId"] in {
                "hidden-context-register-footer-drawer",
                "thinking-register-footer-drawer",
                "rm-register-footer-drawer",
            }
        ]
        assert registrations == [
            ("hidden-context-drawer", "hidden-context-register-footer-drawer", 100, True),
            ("thinking-text-drawer", "thinking-register-footer-drawer", 200, True),
            ("reminders-manager", "rm-register-footer-drawer", 300, True),
        ]


@pytest.mark.parametrize(("name", "package_dir"), [("hc", HC), ("thinking", THINKING), ("reminders", REMINDERS)])
def test_thin_drawer_without_framework_fails_required_package_missing(tmp_path, name, package_dir) -> None:
    report = _build_packages(tmp_path, f"missing-framework-{name}", [package_dir])
    assert report.status == "failed"
    assert report.failureReason is not None
    assert "patch_conflict:required_package_missing" in report.failureReason
    assert f":{package_dir.name}:footer-drawers" in report.failureReason

def test_old_direct_footer_owner_with_framework_fails_closed(tmp_path) -> None:
    source = _source_or_skip()
    stale = tmp_path / "thinking-text-drawer"
    stale.mkdir()
    exact = 'ss=wo.useMemo(()=>[Ui&&"tasks",po&&"workflows",Fn&&"tmux",_e&&"bagel",Tr&&"bridge",Ne&&"frame"].filter(Boolean),[Ui,po,Fn,_e,Tr,Ne])'
    replacement = exact.replace('[Ui&&"tasks"', '["thinking",Ui&&"tasks"')
    manifest = {
        "schemaVersion": 2,
        "id": "stale-direct-thinking",
        "name": "Stale Direct Thinking",
        "description": "Fixture direct footer owner",
        "packageVersion": "0.0.0",
        "targets": [{
            "sourceIdentity": {"claudeVersion":"2.1.201","versionOutput":"2.1.201 (Claude Code)","sha256":EXPECTED_BINARY_SHA,"sizeBytes":EXPECTED_BINARY_SIZE,"platform":"darwin","arch":"arm64"},
            "requiredEngine": "bun_graph_repack",
            "requiredBinaryFormat": "bun_standalone_macho64",
            "modules": [{"path":MODULE_PATH,"contentSha256":EXPECTED_MODULE_SHA,"contentLength":EXPECTED_MODULE_LENGTH,"operations":[{"opId":"stale-footer-target","label":"Stale footer target","type":"replace_exact","exact":exact,"requireWithinRange":[],"oldRangeSha256":hashlib.sha256(exact.encode()).hexdigest(),"oldRangeLength":len(exact.encode()),"replacement":{"inline":replacement}}]}],
        }],
    }
    (stale / "patch.json").write_text(json.dumps(manifest))
    report = build_patchset_v15(BuildRequestV15(source_path=source, output_dir=tmp_path / "stale", package_dirs=[FOOTER_DRAWERS, stale], source_version="2.1.201", source_version_output="2.1.201 (Claude Code)", platform="darwin", arch="arm64"))
    assert report.status == "failed"
    assert report.failureReason is not None
    assert "patch_conflict" in report.failureReason
