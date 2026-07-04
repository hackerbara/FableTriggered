from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from claude_monkey.builder_v15 import ValidationRequestV15, validate_package
from claude_monkey.manifest_v2 import load_manifest_v2_dict
from claude_monkey.payloads import load_payload_bytes
from tests.claude_binary import claude_bin_candidates, claude_version_path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIRS = [
    ROOT / "packages" / "fable-fallback",
    ROOT / "packages" / "hidden-context-drawer",
    ROOT / "packages" / "hotrod-dragons",
    ROOT / "packages" / "normal-channel-hidden-context",
    ROOT / "packages" / "reminder-suppression",
]


def source_for_identity(identity) -> Path | None:
    candidates = [
        Path.home() / ".claude-monkey" / "sources" / identity.sha256 / "claude",
        *claude_bin_candidates(),
        claude_version_path(identity.claude_version),
    ]
    for candidate in candidates:
        if not candidate.exists():
            continue
        if hashlib.sha256(candidate.read_bytes()).hexdigest() == identity.sha256:
            return candidate
    return None


def test_reference_packages_are_v15_schema_v2_with_valid_payload_hashes():
    for package_dir in PACKAGE_DIRS:
        manifest_data = json.loads((package_dir / "patch.json").read_text())
        manifest = load_manifest_v2_dict(manifest_data)
        assert manifest.id == package_dir.name
        assert manifest.schema_version == 2
        for target in manifest.targets:
            assert target.required_engine == "bun_graph_repack"
            assert target.required_binary_format == "bun_standalone_macho64"
            assert [module.path for module in target.modules] == [
                "/$bunfs/root/src/entrypoints/cli.js"
            ]
            for module in target.modules:
                assert module.content_sha256
                assert module.content_length > 0
                for operation in module.operations:
                    assert operation.old_range_sha256
                    assert operation.old_range_length is not None
                    payload = load_payload_bytes(operation.replacement, package_dir)
                    assert payload


def test_reference_packages_validate_against_current_pinned_source():
    for package_dir in PACKAGE_DIRS:
        manifest = load_manifest_v2_dict(json.loads((package_dir / "patch.json").read_text()))
        identity = manifest.targets[0].source_identity
        source = source_for_identity(identity)
        if source is None:
            pytest.skip(f"local Claude Code source missing for sha {identity.sha256}")
        result = validate_package(
            ValidationRequestV15(
                source_path=source,
                package_dir=package_dir,
                source_version=identity.claude_version,
                source_version_output=identity.version_output,
                platform=identity.platform,
                arch=identity.arch,
            )
        )
        assert result["ok"] is True, result
        assert result["packageId"] == package_dir.name
        assert result["operationsResolved"]


def test_fable_resume_metadata_payload_uses_ascii_escapes_for_terminal_rendering():
    payload_path = (
        ROOT / "packages" / "fable-fallback" / "payloads" / "net-metadata-formatter.js"
    )
    payload = payload_path.read_bytes()
    assert b"\xc2\xb7" not in payload
    assert b"\\xB7" in payload
    assert b"\\x1b[33mFable classifier triggered\\x1b[39m" in payload


def test_normal_channel_hidden_context_projects_hidden_attachments_before_filtering():
    package_dir = ROOT / "packages" / "normal-channel-hidden-context"
    helper_payload = (package_dir / "payloads" / "projection-helpers-before-jlr.js").read_text()
    helper_payload_199 = (
        package_dir / "payloads" / "projection-helpers-before-jur.js"
    ).read_text()
    filter_payload = (package_dir / "payloads" / "project-before-hidden-filter.js").read_text()
    filter_payload_199 = (
        package_dir / "payloads" / "project-before-hidden-filter-2.1.199.js"
    ).read_text()

    for helper in (helper_payload, helper_payload_199):
        assert "function __codexNCHCProjectAttachment(e)" in helper
        assert "function __codexNCHCProjectList(e)" in helper
        assert 'type:"system",subtype:"codex_hidden_context",level:"warning"' in helper
        assert 'content:"[model context] "+t' in helper
    assert "function Jlr(e){" in helper_payload
    assert "function Jur(e){" in helper_payload_199
    assert "Yt=__codexNCHCProjectList(Yt)" in filter_payload
    assert '.filter((Rt)=>Rt.type!=="progress").filter((Rt)=>!Jlr(Rt))' in filter_payload
    assert "Jt=__codexNCHCProjectList(Jt)" in filter_payload_199
    assert '.filter((cr)=>cr.type!=="progress").filter((cr)=>!Jur(cr))' in filter_payload_199


def test_normal_channel_hidden_context_projection_payload_handles_known_records():
    package_dir = ROOT / "packages" / "normal-channel-hidden-context"
    helper_payload = (package_dir / "payloads" / "projection-helpers-before-jlr.js").read_text()
    helper_block = helper_payload.removesuffix("function Jlr(e){\n").removesuffix(
        "function Jlr(e){"
    )
    script = f"""
{helper_block}
const rows = [
  {{
    type: "attachment",
    uuid: "hook-row",
    timestamp: "2026-07-02T22:13:14.365Z",
    sessionId: "session",
    parentUuid: "parent",
    attachment: {{
      type: "hook_additional_context",
      hookName: "SessionStart",
      content: ["using-superpowers skill block"]
    }}
  }},
  {{
    type: "attachment",
    uuid: "task-row",
    timestamp: "2026-07-02T22:14:17.825Z",
    sessionId: "session",
    parentUuid: "parent",
    attachment: {{ type: "task_reminder", content: [], itemCount: 0 }}
  }}
];
const projected = __codexNCHCProjectList(rows).filter(
  (row) => row.type === "system" && row.subtype === "codex_hidden_context"
);
if (projected.length !== 2) throw new Error("expected two projected rows");
if (!projected.every((row) => row.level === "warning")) throw new Error("expected warning rows");
if (!projected[0].content.includes("[model context] SessionStart hook additional context:")) {{
  throw new Error("missing SessionStart projection label");
}}
if (!projected[0].content.includes("using-superpowers")) {{
  throw new Error("missing hook content");
}}
if (projected[1].content !== "[model context] Task reminder: task tools have not been used recently (0 tasks)") {{
  throw new Error("task projection mismatch: " + projected[1].content);
}}
"""
    result = subprocess.run(
        ["node", "-e", script],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_hidden_context_drawer_package_uses_footer_overlay_without_global_ijo_cap_patch():
    package_dir = ROOT / "packages" / "hidden-context-drawer"
    manifest_data = json.loads((package_dir / "patch.json").read_text())
    operations = manifest_data["targets"][0]["modules"][0]["operations"]
    payloads = {
        operation["opId"]: (package_dir / operation["replacement"]["path"]).read_text()
        for operation in operations
    }

    assert "__CODEX_HIDDEN_CONTEXT_DRAWER_FRAME_V13__" in payloads[
        "projection-helpers-before-jlr"
    ]
    assert 'function qnc(){let e=KJe.c(12),[t,n]=S_.useState(0)' in payloads[
        "uxl-refresh-bottom-overlay"
    ]
    assert "Zc(()=>n(Date.now()),100)" in payloads["uxl-refresh-bottom-overlay"]
    assert 'bottom:"100%"' in payloads["uxl-refresh-bottom-overlay"]
    assert 'position:"absolute",marginTop:-(hCh+1)' not in "".join(payloads.values())
    assert any(
        assertion["value"]
        == 'function qnc(){let e=KJe.c(12),[t,n]=S_.useState(0);Zc(()=>n(Date.now()),100)'
        for assertion in manifest_data["targets"][0]["postconditions"]
    )


def test_hidden_context_drawer_scroll_step_is_three_for_keyboard_and_mouse():
    package_dir = ROOT / "packages" / "hidden-context-drawer"
    keyboard_payload = (
        package_dir / "payloads" / "12-footer-hiddencontext-up-down-scroll.js"
    ).read_text()
    overlay_payload = (
        package_dir / "payloads" / "15-uxl-refresh-bottom-overlay.js"
    ).read_text()

    assert "Bt-3" in keyboard_payload
    assert "Bt+3" in keyboard_payload
    assert "d.deltaY>0?3:-3" in overlay_payload
    assert "Bt-1" not in keyboard_payload.split("if(qb&&oa>0&&xs>br)")[0]
    assert "Bt+1" not in keyboard_payload.split("if(qb&&oa>0)")[0]


def test_hidden_context_drawer_footer_flashes_blue_until_selection_clears():
    package_dir = ROOT / "packages" / "hidden-context-drawer"
    helper_payload = (
        package_dir / "payloads" / "01-projection-helpers-before-jlr.js"
    ).read_text()
    footer_payload = (
        package_dir / "payloads" / "16-footer-availability-bar-hidden-context.js"
    ).read_text()
    globals_payload = (
        package_dir / "payloads" / "14-selected-only-bottom-overlay-hidden-context-globals.js"
    ).read_text()
    keyboard_payload = (
        package_dir / "payloads" / "12-footer-hiddencontext-up-down-scroll.js"
    ).read_text()

    assert "flashUntil:o?Number.MAX_SAFE_INTEGER:r?.flashUntil??0" in helper_payload
    assert "hCflash=!hCsel&&Date.now()<(hCf?.flashUntil??0)" in footer_payload
    assert 'color:"white",backgroundColor:"blue"' in footer_payload
    assert "Date.now()<(hCf?.flashUntil??0)" in footer_payload
    assert "flashUntil=0" in globals_payload
    assert "flashUntil=0" in keyboard_payload


def test_hidden_context_drawer_footer_x_closes_and_enter_opens():
    package_dir = ROOT / "packages" / "hidden-context-drawer"
    globals_payload = (
        package_dir / "payloads" / "14-selected-only-bottom-overlay-hidden-context-globals.js"
    ).read_text()
    open_close_payload = (
        package_dir / "payloads" / "13-footer-clearselection-consumes-hiddencontext.js"
    ).read_text()
    overlay_payload = (
        package_dir / "payloads" / "15-uxl-refresh-bottom-overlay.js"
    ).read_text()

    assert not (
        package_dir / "payloads" / "17-main-keydown-ctrl-period-hiddencontext.js"
    ).exists()
    assert 'onKeyDown:(Bt)=>{if(hC&&Bt.ctrl&&Bt.key===".")' not in globals_payload
    assert 'Bt.ctrl&&Bt.name==="escape"' not in globals_payload
    assert 'case"hiddenContext"' in open_close_payload
    assert "globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_OPEN_V13__=!0" in open_close_payload
    assert "hCp(!0)" in open_close_payload
    assert "globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_OPEN_V13__=!1" in open_close_payload
    assert "hCp(!1)" in open_close_payload
    assert "Sf(null)" in open_close_payload
    assert '"footer:clearSelection":()=>{if(hC)return!1;' in open_close_payload
    assert "x closes" in overlay_payload
    assert "ctrl+. closes" not in overlay_payload
    assert "ctrl+esc closes" not in overlay_payload
    assert "| esc closes" not in overlay_payload


def test_hidden_context_drawer_payload_avoids_utf8_separator_mojibake_and_uses_warning_header():
    package_dir = ROOT / "packages" / "hidden-context-drawer"
    helper_payload = (
        package_dir / "payloads" / "01-projection-helpers-before-jlr.js"
    ).read_bytes()
    overlay_payload = (
        package_dir / "payloads" / "15-uxl-refresh-bottom-overlay.js"
    ).read_text()

    assert b"\xc2\xb7" not in helper_payload
    assert b"\\xB7" in helper_payload
    assert 'borderColor:"warning"' in overlay_payload
    assert "borderText:{content:` Hidden Context " in overlay_payload
    assert 'lineKinds' in helper_payload.decode()
    assert 'color:s?.lineKinds?.[c+p]==="header"?"warning":void 0' in overlay_payload
    assert 'color:d===""?void 0:"warning"' not in overlay_payload
    assert 'Xd.jsx(v,{bold:!0,children:["Hidden Context  "' not in overlay_payload


def test_hidden_context_drawer_projection_frame_has_timestamps_sources_and_broader_model_context():
    package_dir = ROOT / "packages" / "hidden-context-drawer"
    helper_payload = (
        package_dir / "payloads" / "01-projection-helpers-before-jlr.js"
    ).read_text()
    helper_block = helper_payload.removesuffix("function Jur(e){\n").removesuffix(
        "function Jur(e){"
    )
    script = f"""
{helper_block}
globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_FRAME_V13__ = undefined;
const rows = [
  {{
    type: "attachment",
    uuid: "hook-additional",
    timestamp: "2026-07-02T22:13:14.365Z",
    attachment: {{
      type: "hook_additional_context",
      hookName: "SessionStart",
      content: ["full hidden context line one", "full hidden context line two"]
    }}
  }},
  {{
    type: "attachment",
    uuid: "hook-blocking",
    timestamp: "2026-07-02T22:14:15.000Z",
    attachment: {{
      type: "hook_blocking_error",
      hookEvent: "UserPromptSubmit",
      message: "blocked command details"
    }}
  }},
  {{
    type: "attachment",
    uuid: "hook-stopped",
    timestamp: "2026-07-02T22:15:16.000Z",
    attachment: {{
      type: "hook_stopped_continuation",
      hookEvent: "Stop",
      content: ["continue with hidden instruction"]
    }}
  }},
  {{
    type: "attachment",
    uuid: "plan-mode",
    timestamp: "2026-07-02T22:16:17.000Z",
    attachment: {{
      type: "plan_mode",
      content: "plan mode model-visible reminder"
    }}
  }},
  {{
    type: "attachment",
    uuid: "auto-mode",
    timestamp: "2026-07-02T22:17:18.000Z",
    attachment: {{
      type: "auto_mode",
      content: "auto mode model-visible reminder"
    }}
  }},
  {{
    type: "attachment",
    uuid: "task-reminder",
    timestamp: "2026-07-02T22:18:19.000Z",
    attachment: {{ type: "task_reminder", content: [], itemCount: 0 }}
  }},
  {{
    type: "attachment",
    uuid: "agent-listing",
    timestamp: "2026-07-02T22:19:20.000Z",
    attachment: {{
      type: "agent_listing_delta",
      added: ["researcher"],
      removed: ["old-agent"],
      content: "agent listing changed for model"
    }}
  }}
];
const frame = __codexNCHCDrawerFrameFromList(rows);
if (!frame.visible) throw new Error("frame should be visible");
if (frame.eventCount !== rows.length) throw new Error("expected all model-visible hidden rows, got " + frame.eventCount);
if (frame.entries[0].key !== "agent-listing") throw new Error("expected reverse chronological order");
if (!frame.entries.every((entry) => entry.timeLabel && entry.sourceLabel && entry.text)) {{
  throw new Error("entries must include timeLabel, sourceLabel, and text: " + JSON.stringify(frame.entries));
}}
if (frame.entries[0].timeLabel !== "22:19:20Z") throw new Error("bad time label: " + frame.entries[0].timeLabel);
if (frame.entries[0].sourceLabel !== "attachment:agent_listing_delta") {{
  throw new Error("bad source label: " + frame.entries[0].sourceLabel);
}}
const allText = frame.lines.join("\\n");
if (frame.lineKinds[0] !== "header" || frame.lineKinds[1] !== "body") throw new Error("expected header/body line kinds: " + JSON.stringify(frame.lineKinds.slice(0,4)));
for (const expected of [
  "22:19:20Z",
  "attachment:agent_listing_delta",
  "Agent listing",
  "22:17:18Z",
  "attachment:auto_mode",
  "auto mode model-visible reminder",
  "22:16:17Z",
  "attachment:plan_mode",
  "plan mode model-visible reminder",
  "22:15:16Z",
  "attachment:hook_stopped_continuation",
  "continue with hidden instruction",
  "22:14:15Z",
  "attachment:hook_blocking_error",
  "blocked command details",
  "22:13:14Z",
  "attachment:hook_additional_context \xB7 hook:SessionStart",
  "full hidden context line two"
]) {{
  if (!allText.includes(expected)) throw new Error("missing expected drawer text: " + expected + "\\n" + allText);
}}
if (!(frame.tokenCount > 0)) throw new Error("expected non-zero token count");
"""
    result = subprocess.run(
        ["node", "-e", script],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0, result.stderr
