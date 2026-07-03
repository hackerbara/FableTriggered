# Upstream Attachment Suppression Package Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a ClaudeMonkey package that prevents selected recurring reminder/accounting attachments from being generated, wrapped as transcript rows, projected into chat, sent to the model, or shown in the Hidden Context drawer for future Claude Code turns.

**Architecture:** Use the current schema-v2 ClaudeMonkey package mechanism exactly as it exists today: module-local splice operations (`replace_between`) against `/$bunfs/root/src/entrypoints/cli.js`, with arbitrary positive growth handled by the Bun graph repack layer. Replace the full `ug(label, generator)` helper to gate denied generator labels before their generators run or telemetry is recorded, and replace the full `Hze(...)` generator to filter denied attachment objects before `G("tengu_attachments", ...)` and `li(c,o)`. Do not patch `zsr(...)`, `Jur(...)`, normal-channel projection, or Hidden Context drawer projection paths; those are too late.

**Tech Stack:** Python 3.11+, pytest, Node.js for JavaScript fixture execution, ClaudeMonkey schema-v2 package manifests, Bun standalone graph repack, copied Claude Code `2.1.199` macOS arm64 binary.

---

## Current-code premise

This plan intentionally uses the actual current package engine:

- `/Users/MAC/Documents/Claude-patch/src/claude_monkey/manifest_v2.py` accepts only `replace_between` and `replace_exact` package operation types.
- `/Users/MAC/Documents/Claude-patch/src/claude_monkey/module_patch.py` allows `delta = len(replacement) - len(old)` to be positive.
- `/Users/MAC/Documents/Claude-patch/src/claude_monkey/repack.py` passes the changed full module to the Bun graph repacker.
- `/Users/MAC/Documents/Claude-patch/src/claude_monkey/bun_graph.py` rewrites the module content and updates Bun payload metadata.

So `replace_between` here is not byte-slot padding. It is a module-local splice whose changed module is later repacked by the graph engine.

## Target evidence

Target first and only in this plan:

```text
Claude Code: 2.1.199 (Claude Code)
Source path: /Users/MAC/.local/share/claude/versions/2.1.199
Source sha256: e3cb61abc8a2ec7b98976cee1ffdde5a3fa755c9990bc8d688cd89290e0dcec0
Source size: 232155536
Module path: /$bunfs/root/src/entrypoints/cli.js
Module sha256: e30c857c2e1130ff0fa9d14349a210c588f8115fc8ac86e120c454547efc0c55
Module length: 18593981
```

Patch ranges:

```text
ug range:
  startMarker: async function ug(e,t){
  endMarker: async function XQt(e,t){
  oldRangeLength: 602
  oldRangeSha256: 4c0825d2dcf2d6188b1ff3607cd37398274af2217a4a2ada8a3c2fc274840533

Hze range:
  startMarker: async function*Hze(e,t,n,r,o,s,i,a){
  endMarker: async function i3l(e){
  oldRangeLength: 180
  oldRangeSha256: 528f9c3051a2b003d01023e68c13af05bc7752d96639eb9a34edb272165a36e9
```

Payload hashes:

```text
payloads/filter-labels-before-ug-2.1.199.js
  length: 1075
  sha256: 4c551eb16902a790b15fc4562a28e23bb1b221d88495e15d11734bb296cdbc17

payloads/filter-before-li-2.1.199.js
  length: 226
  sha256: 14934fa13fcfbb326fbdebc44488ff4debb2d8eb25b3cd5b15c08825ed17c284
```

## Suppression policy

Denied generator labels:

```text
todo_reminders
tool_search_usage_reminder
total_tokens_reminder
token_usage
budget_usd
output_token_usage
```

Denied attachment types:

```text
todo_reminder
task_reminder
tool_search_usage_reminder
token_usage
total_tokens_reminder
budget_usd
output_token_usage
```

Explicit keep families that must not be denied by this package:

```text
hook_success
hook_additional_context
hook_blocking_error
hook_stopped_continuation
command_permissions
agent_mention
critical_system_reminder
edited_text_file
opened_file_in_ide
plan_mode
plan_mode_exit
plan_mode_reentry
auto_mode
auto_mode_exit
team_context
memory_update
mcp_instructions_delta
deferred_tools_delta
diagnostics
lsp_diagnostics
queued_command
file_reference
pdf_reference
directory_reference
```

## File structure

Create or modify these files:

```text
/Users/MAC/Documents/Claude-patch/tests/test_upstream_attachment_suppression.py
/Users/MAC/Documents/Claude-patch/packages/upstream-attachment-suppression/README.md
/Users/MAC/Documents/Claude-patch/packages/upstream-attachment-suppression/patch.json
/Users/MAC/Documents/Claude-patch/packages/upstream-attachment-suppression/payloads/filter-labels-before-ug-2.1.199.js
/Users/MAC/Documents/Claude-patch/packages/upstream-attachment-suppression/payloads/filter-before-li-2.1.199.js
/Users/MAC/Documents/Claude-patch/packages/reminder-suppression/README.md
```

Do not modify these files for this package:

```text
/Users/MAC/Documents/Claude-patch/packages/hidden-context-drawer/patch.json
/Users/MAC/Documents/Claude-patch/packages/normal-channel-hidden-context/patch.json
/Users/MAC/Documents/Claude-patch/src/claude_monkey/manifest_v2.py
/Users/MAC/Documents/Claude-patch/src/claude_monkey/module_patch.py
/Users/MAC/Documents/Claude-patch/src/claude_monkey/repack.py
/Users/MAC/Documents/Claude-patch/src/claude_monkey/bun_graph.py
```

The current engine already supports the needed positive-growth module splice.

## Task 1: Add failing upstream suppression tests

**Files:**
- Create: `/Users/MAC/Documents/Claude-patch/tests/test_upstream_attachment_suppression.py`

- [ ] **Step 1: Create the test file**

Create `/Users/MAC/Documents/Claude-patch/tests/test_upstream_attachment_suppression.py` with this complete content:

```python
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from claude_monkey.bun_graph import parse_bun_section
from claude_monkey.builder_v15 import ValidationRequestV15, validate_package
from claude_monkey.macho import find_macho_layout
from claude_monkey.manifest_v2 import load_manifest_v2_dict
from claude_monkey.payloads import load_payload_bytes

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "packages" / "upstream-attachment-suppression"
LIVE_2_1_199 = Path("/Users/MAC/.local/share/claude/versions/2.1.199")
MODULE_PATH = "/$bunfs/root/src/entrypoints/cli.js"
EXPECTED_SOURCE_SHA = "e3cb61abc8a2ec7b98976cee1ffdde5a3fa755c9990bc8d688cd89290e0dcec0"
EXPECTED_MODULE_SHA = "e30c857c2e1130ff0fa9d14349a210c588f8115fc8ac86e120c454547efc0c55"

DENIED_LABELS = [
    "todo_reminders",
    "tool_search_usage_reminder",
    "total_tokens_reminder",
    "token_usage",
    "budget_usd",
    "output_token_usage",
]

DENIED_TYPES = [
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


def _exact_2_1_199_source() -> bytes:
    if not LIVE_2_1_199.exists():
        pytest.skip(f"Claude Code 2.1.199 source missing: {LIVE_2_1_199}")
    source = LIVE_2_1_199.read_bytes()
    actual = hashlib.sha256(source).hexdigest()
    if actual != EXPECTED_SOURCE_SHA:
        pytest.skip(f"live Claude source is not the pinned 2.1.199 target: {actual}")
    return source


def _target_module_text() -> str:
    source = _exact_2_1_199_source()
    layout = find_macho_layout(source)
    section = source[layout.bun_section.offset : layout.bun_section.offset + layout.bun_section.size]
    graph = parse_bun_section(section)
    module = graph.module_by_path(MODULE_PATH)
    assert hashlib.sha256(module.content).hexdigest() == EXPECTED_MODULE_SHA
    return module.content.decode("utf-8")


def _payloads() -> tuple[str, str, str]:
    manifest = load_manifest_v2_dict(json.loads((PACKAGE_DIR / "patch.json").read_text()))
    target = manifest.targets[0]
    module = target.modules[0]
    payload_texts = []
    for operation in module.operations:
        payload_texts.append(load_payload_bytes(operation.replacement, PACKAGE_DIR).decode("utf-8"))
    return payload_texts[0], payload_texts[1], "\n".join(payload_texts)


def test_upstream_attachment_suppression_package_validates_against_real_2_1_199_source():
    _exact_2_1_199_source()
    result = validate_package(
        ValidationRequestV15(
            source_path=LIVE_2_1_199,
            package_dir=PACKAGE_DIR,
            source_version="2.1.199",
            source_version_output="2.1.199 (Claude Code)",
            platform="darwin",
            arch="arm64",
        )
    )
    assert result["ok"] is True, result
    assert result["packageId"] == "upstream-attachment-suppression"
    assert [item["opId"] for item in result["operationsResolved"]] == [
        "ug-drop-denied-labels-2-1-199",
        "hze-filter-before-li-2-1-199",
    ]
    assert result["operationsResolved"][0]["delta"] > 0
    assert result["operationsResolved"][1]["delta"] > 0


def test_upstream_attachment_suppression_payloads_encode_the_policy_and_keep_boundaries():
    ug_payload, hze_payload, all_payload = _payloads()
    assert "function __codexUASDropLabel(e)" in ug_payload
    assert "function __codexUASDropAttachment(e)" in ug_payload
    assert "async function ug(e,t)" in ug_payload
    assert "async function*Hze(e,t,n,r,o,s,i,a)" in hze_payload
    for label in DENIED_LABELS:
        assert label in ug_payload
    for attachment_type in DENIED_TYPES:
        assert attachment_type in ug_payload
    for kept in KEPT_TYPES:
        assert kept not in ug_payload
        assert kept not in hze_payload
    assert "__codexNCHC" not in all_payload
    assert "__CODEX_HIDDEN_CONTEXT_DRAWER" not in all_payload
    assert "function zsr" not in all_payload
    assert "function Jur" not in all_payload


def test_upstream_attachment_suppression_gates_before_compute_telemetry_and_li_wrapping():
    ug_payload, hze_payload, _ = _payloads()
    label_guard = ug_payload.index("if(__codexUASDropLabel(e))return[]")
    start_timer = ug_payload.index("let n=Date.now()")
    await_generator = ug_payload.index("let r=await t()")
    compute_telemetry = ug_payload.index('G("tengu_attachment_compute_duration"')
    assert label_guard < start_timer < await_generator < compute_telemetry

    hze_filter = hze_payload.index("l=l.filter((c)=>!__codexUASDropAttachment(c))")
    hze_empty = hze_payload.index("if(l.length===0)return")
    hze_telemetry = hze_payload.index('G("tengu_attachments"')
    hze_li = hze_payload.index("yield li(c,o)")
    assert hze_filter < hze_empty < hze_telemetry < hze_li


def test_upstream_attachment_suppression_manifest_targets_upstream_only():
    manifest_data = json.loads((PACKAGE_DIR / "patch.json").read_text())
    manifest = load_manifest_v2_dict(manifest_data)
    assert manifest.id == "upstream-attachment-suppression"
    assert len(manifest.targets) == 1
    target = manifest.targets[0]
    assert target.required_engine == "bun_graph_repack"
    assert target.required_binary_format == "bun_standalone_macho64"
    assert target.source_identity.claude_version == "2.1.199"
    assert [module.path for module in target.modules] == [MODULE_PATH]
    operations = target.modules[0].operations
    assert [operation.type for operation in operations] == ["replace_between", "replace_between"]
    assert [operation.start_marker for operation in operations] == [
        "async function ug(e,t){",
        "async function*Hze(e,t,n,r,o,s,i,a){",
    ]
    forbidden_values = [
        "function zsr(e){",
        "function Jur(e){",
        "__codexNCHCProjectList",
        "__CODEX_HIDDEN_CONTEXT_DRAWER_FRAME",
    ]
    serialized = json.dumps(manifest_data, sort_keys=True)
    for value in forbidden_values:
        assert value not in serialized


def test_no_direct_denied_family_li_construction_bypasses_hze_in_target_module():
    module = _target_module_text()
    assert module.count("yield li(c,o)") == 1
    for denied in DENIED_TYPES:
        direct_needles = [
            f'li({{type:"{denied}"',
            f'li({{attachment:{{type:"{denied}"',
            f"li({{type:'{denied}'",
            f"li({{attachment:{{type:'{denied}'",
        ]
        for needle in direct_needles:
            assert needle not in module


def test_upstream_attachment_suppression_fixture_blocks_denied_generators_telemetry_and_rows():
    ug_payload, hze_payload, _ = _payloads()
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
  for (const label of ["todo_reminders","tool_search_usage_reminder","total_tokens_reminder","token_usage","budget_usd","output_token_usage"]) {
    if (!__codexUASDropLabel(label)) throw new Error("label should be denied: "+label);
  }
  for (const type of ["todo_reminder","task_reminder","tool_search_usage_reminder","token_usage","total_tokens_reminder","budget_usd","output_token_usage"]) {
    if (!__codexUASDropAttachment({type})) throw new Error("type should be denied: "+type);
  }
  for (const type of ["hook_additional_context","hook_blocking_error","critical_system_reminder","plan_mode","memory_update","diagnostics","queued_command"]) {
    if (__codexUASDropAttachment({type})) throw new Error("type should be kept: "+type);
  }

  let deniedCalled=false;
  let denied=await ug("todo_reminders", async()=>{deniedCalled=true; return [{type:"todo_reminder"}]});
  if (deniedCalled) throw new Error("denied generator should not run");
  if (denied.length !== 0) throw new Error("denied generator should return empty array");
  if (telemetry.length !== 0) throw new Error("denied generator should not emit telemetry");

  Math.random=()=>0;
  let keptCalled=false;
  let kept=await ug("hook_additional_context", async()=>{keptCalled=true; return [{type:"hook_additional_context",content:["keep"]}]});
  if (!keptCalled) throw new Error("kept generator should run");
  if (kept.length !== 1 || kept[0].type !== "hook_additional_context") throw new Error("kept generator result mismatch");
  if (!telemetry.some((item)=>item.name==="tengu_attachment_compute_duration" && item.payload.label==="hook_additional_context")) {
    throw new Error("kept generator telemetry should remain");
  }

  telemetry=[];
  let wrapped=[];
  W9l=async()=>[
    {type:"todo_reminder",content:[]},
    {type:"hook_additional_context",content:["keep"]},
    {type:"token_usage",used:1,total:10,remaining:9}
  ];
  li=(attachment)=>{wrapped.push(attachment.type); return {type:"attachment",attachment}};
  let yielded=[];
  for await (const row of Hze(null,null,null,null,null,null,null,null)) yielded.push(row);
  if (wrapped.join(",") !== "hook_additional_context") throw new Error("denied objects were wrapped by li: "+wrapped.join(","));
  if (yielded.length !== 1 || yielded[0].attachment.type !== "hook_additional_context") throw new Error("yield mismatch");
  let event=telemetry.find((item)=>item.name==="tengu_attachments");
  if (!event) throw new Error("kept Hze attachment telemetry should remain");
  let types=event.payload.attachment_types;
  for (const deniedType of ["todo_reminder","token_usage"]) {
    if (types.includes(deniedType)) throw new Error("denied Hze type reached telemetry: "+deniedType);
  }
})().catch((err)=>{console.error(err.stack||err.message); process.exit(1)});
''',
        ]
    )
    result = subprocess.run(
        ["node", "-e", script],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    assert result.returncode == 0, result.stderr
```

- [ ] **Step 2: Run the new tests and verify they fail because the package does not exist yet**

Run:

```bash
cd /Users/MAC/Documents/Claude-patch
PYTHONPATH=src python3 -m pytest tests/test_upstream_attachment_suppression.py -q
```

Expected: FAIL with a `FileNotFoundError` for `/Users/MAC/Documents/Claude-patch/packages/upstream-attachment-suppression/patch.json` or a missing package directory error.

## Task 2: Create the upstream attachment suppression package

**Files:**
- Create: `/Users/MAC/Documents/Claude-patch/packages/upstream-attachment-suppression/README.md`
- Create: `/Users/MAC/Documents/Claude-patch/packages/upstream-attachment-suppression/patch.json`
- Create: `/Users/MAC/Documents/Claude-patch/packages/upstream-attachment-suppression/payloads/filter-labels-before-ug-2.1.199.js`
- Create: `/Users/MAC/Documents/Claude-patch/packages/upstream-attachment-suppression/payloads/filter-before-li-2.1.199.js`

- [ ] **Step 1: Create package directories**

Run:

```bash
cd /Users/MAC/Documents/Claude-patch
mkdir -p packages/upstream-attachment-suppression/payloads
```

Expected: command exits 0.

- [ ] **Step 2: Create the package README**

Create `/Users/MAC/Documents/Claude-patch/packages/upstream-attachment-suppression/README.md`:

```markdown
# Upstream attachment suppression

Suppresses selected recurring reminder/accounting attachment families before they become Claude Code transcript rows.

This is a ClaudeMonkey V1.5 schema-v2 package. It targets `/$bunfs/root/src/entrypoints/cli.js` in Bun module coordinates and relies on the Bun graph repack engine for positive-growth module splices.

## Target

- Claude Code `2.1.199 (Claude Code)`
- macOS arm64
- Source SHA-256: `e3cb61abc8a2ec7b98976cee1ffdde5a3fa755c9990bc8d688cd89290e0dcec0`

## What it suppresses

The package denies these generator labels before their generators run:

- `todo_reminders`
- `tool_search_usage_reminder`
- `total_tokens_reminder`
- `token_usage`
- `budget_usd`
- `output_token_usage`

It also filters these attachment object types before `li(...)` can wrap them as transcript rows:

- `todo_reminder`
- `task_reminder`
- `tool_search_usage_reminder`
- `token_usage`
- `total_tokens_reminder`
- `budget_usd`
- `output_token_usage`

## What it does not suppress

The package intentionally leaves safety, permission, hook, file-state, plan/auto-mode, team, memory, diagnostics, queued command, and user-provided file reference families intact.

## Why this supersedes reminder-suppression

`packages/reminder-suppression` patched renderer/model-conversion cases after attachment records could already exist. That is too late for the invariant this package targets.

This package patches upstream generation and row construction:

1. `ug(label, generator)` returns `[]` for denied labels before the generator runs and before `tengu_attachment_compute_duration` telemetry can record denied families.
2. `Hze(...)` filters denied attachment objects before `tengu_attachments` telemetry and before `li(c,o)` creates transcript rows.

Historical transcripts are not rewritten. Existing denied rows remain in old session JSONL unless a separate transcript sanitation tool is explicitly built and run.
```

- [ ] **Step 3: Create the `ug(...)` payload**

Run this writer so the file bytes match the pinned SHA-256 exactly and do not include a trailing newline:

```bash
cd /Users/MAC/Documents/Claude-patch
python3 - <<'PY'
from pathlib import Path
Path('packages/upstream-attachment-suppression/payloads/filter-labels-before-ug-2.1.199.js').write_text('function __codexUASDropLabel(e){return e==="todo_reminders"||e==="tool_search_usage_reminder"||e==="total_tokens_reminder"||e==="token_usage"||e==="budget_usd"||e==="output_token_usage"}function __codexUASDropAttachment(e){return!!e&&(e.type==="todo_reminder"||e.type==="task_reminder"||e.type==="tool_search_usage_reminder"||e.type==="token_usage"||e.type==="total_tokens_reminder"||e.type==="budget_usd"||e.type==="output_token_usage")}async function ug(e,t){if(__codexUASDropLabel(e))return[];let n=Date.now();try{let r=await t(),o=Date.now()-n;if(Math.random()<0.05){let s=r.filter((i)=>i!==void 0&&i!==null).reduce((i,a)=>i+Ie(a).length,0);G("tengu_attachment_compute_duration",{label:e,duration_ms:o,attachment_size_bytes:s,attachment_count:r.length})}return r}catch(r){let o=Date.now()-n;if(Math.random()<0.05)G("tengu_attachment_compute_duration",{label:e,duration_ms:o,error:!0});if(r instanceof MM)C(`Attachment image resize failed in ${e}: ${r.message}`,{level:"error"});else He(Bo(sr(r),"attachment generator failed"));return n6(`Attachment error in ${e}`,r),[]}}')
PY
```

- [ ] **Step 4: Create the `Hze(...)` payload**

Run this writer so the file bytes match the pinned SHA-256 exactly and do not include a trailing newline:

```bash
cd /Users/MAC/Documents/Claude-patch
python3 - <<'PY'
from pathlib import Path
Path('packages/upstream-attachment-suppression/payloads/filter-before-li-2.1.199.js').write_text('async function*Hze(e,t,n,r,o,s,i,a){let l=await W9l(e,t,n,r,s,i,a);l=l.filter((c)=>!__codexUASDropAttachment(c));if(l.length===0)return;G("tengu_attachments",{attachment_types:l.map((c)=>c.type)});for(let c of l)yield li(c,o)}')
PY
```

- [ ] **Step 5: Verify payload hashes before writing the manifest**

Run:

```bash
cd /Users/MAC/Documents/Claude-patch
shasum -a 256 packages/upstream-attachment-suppression/payloads/filter-labels-before-ug-2.1.199.js packages/upstream-attachment-suppression/payloads/filter-before-li-2.1.199.js
```

Expected output:

```text
4c551eb16902a790b15fc4562a28e23bb1b221d88495e15d11734bb296cdbc17  packages/upstream-attachment-suppression/payloads/filter-labels-before-ug-2.1.199.js
14934fa13fcfbb326fbdebc44488ff4debb2d8eb25b3cd5b15c08825ed17c284  packages/upstream-attachment-suppression/payloads/filter-before-li-2.1.199.js
```

If the hashes differ, rewrite the payload files from Steps 3 and 4 exactly and rerun this command before creating the manifest.

- [ ] **Step 6: Create the package manifest**

Create `/Users/MAC/Documents/Claude-patch/packages/upstream-attachment-suppression/patch.json`:

```json
{
  "schemaVersion": 2,
  "id": "upstream-attachment-suppression",
  "name": "Upstream attachment suppression",
  "description": "Suppresses selected recurring reminder/accounting attachments before generator telemetry and transcript row creation.",
  "packageVersion": "0.1.0",
  "targets": [
    {
      "sourceIdentity": {
        "arch": "arm64",
        "claudeVersion": "2.1.199",
        "platform": "darwin",
        "sha256": "e3cb61abc8a2ec7b98976cee1ffdde5a3fa755c9990bc8d688cd89290e0dcec0",
        "sizeBytes": 232155536,
        "versionOutput": "2.1.199 (Claude Code)"
      },
      "requiredEngine": "bun_graph_repack",
      "requiredBinaryFormat": "bun_standalone_macho64",
      "modules": [
        {
          "path": "/$bunfs/root/src/entrypoints/cli.js",
          "contentSha256": "e30c857c2e1130ff0fa9d14349a210c588f8115fc8ac86e120c454547efc0c55",
          "contentLength": 18593981,
          "operations": [
            {
              "opId": "ug-drop-denied-labels-2-1-199",
              "label": "Drop denied attachment generator labels before generator execution and compute telemetry",
              "type": "replace_between",
              "startMarker": "async function ug(e,t){",
              "endMarker": "async function XQt(e,t){",
              "expectedStartMarkerCount": 1,
              "expectedEndMarkerCount": 1,
              "requireWithinRange": [
                "let n=Date.now()",
                "let r=await t()",
                "G(\"tengu_attachment_compute_duration\""
              ],
              "oldRangeSha256": "4c0825d2dcf2d6188b1ff3607cd37398274af2217a4a2ada8a3c2fc274840533",
              "oldRangeLength": 602,
              "replacement": {
                "path": "payloads/filter-labels-before-ug-2.1.199.js",
                "sha256": "4c551eb16902a790b15fc4562a28e23bb1b221d88495e15d11734bb296cdbc17"
              },
              "knownBehaviorChange": "Selected reminder/accounting attachment generators return an empty list before their generator function and compute-duration telemetry run."
            },
            {
              "opId": "hze-filter-before-li-2-1-199",
              "label": "Filter denied attachment objects before attachment telemetry and li row construction",
              "type": "replace_between",
              "startMarker": "async function*Hze(e,t,n,r,o,s,i,a){",
              "endMarker": "async function i3l(e){",
              "expectedStartMarkerCount": 1,
              "expectedEndMarkerCount": 1,
              "requireWithinRange": [
                "let l=await W9l(e,t,n,r,s,i,a)",
                "G(\"tengu_attachments\"",
                "yield li(c,o)"
              ],
              "oldRangeSha256": "528f9c3051a2b003d01023e68c13af05bc7752d96639eb9a34edb272165a36e9",
              "oldRangeLength": 180,
              "replacement": {
                "path": "payloads/filter-before-li-2.1.199.js",
                "sha256": "14934fa13fcfbb326fbdebc44488ff4debb2d8eb25b3cd5b15c08825ed17c284"
              },
              "knownBehaviorChange": "Denied attachment objects are filtered before active attachment telemetry and before li(...) can create transcript rows."
            }
          ]
        }
      ],
      "preconditions": [
        {
          "type": "module_must_contain",
          "modulePath": "/$bunfs/root/src/entrypoints/cli.js",
          "value": "async function ug(e,t){let n=Date.now();try{let r=await t()"
        },
        {
          "type": "module_must_contain",
          "modulePath": "/$bunfs/root/src/entrypoints/cli.js",
          "value": "async function*Hze(e,t,n,r,o,s,i,a){let l=await W9l(e,t,n,r,s,i,a);if(l.length===0)return;G(\"tengu_attachments\""
        }
      ],
      "postconditions": [
        {
          "type": "module_must_contain",
          "modulePath": "/$bunfs/root/src/entrypoints/cli.js",
          "value": "function __codexUASDropLabel(e)"
        },
        {
          "type": "module_must_contain",
          "modulePath": "/$bunfs/root/src/entrypoints/cli.js",
          "value": "function __codexUASDropAttachment(e)"
        },
        {
          "type": "module_must_contain",
          "modulePath": "/$bunfs/root/src/entrypoints/cli.js",
          "value": "if(__codexUASDropLabel(e))return[];let n=Date.now()"
        },
        {
          "type": "module_must_contain",
          "modulePath": "/$bunfs/root/src/entrypoints/cli.js",
          "value": "l=l.filter((c)=>!__codexUASDropAttachment(c));if(l.length===0)return;G(\"tengu_attachments\""
        },
        {
          "type": "module_must_not_contain",
          "modulePath": "/$bunfs/root/src/entrypoints/cli.js",
          "value": "async function ug(e,t){let n=Date.now();try{let r=await t()"
        },
        {
          "type": "module_must_not_contain",
          "modulePath": "/$bunfs/root/src/entrypoints/cli.js",
          "value": "async function*Hze(e,t,n,r,o,s,i,a){let l=await W9l(e,t,n,r,s,i,a);if(l.length===0)return;G(\"tengu_attachments\""
        }
      ],
      "manualSmoke": {
        "required": false
      }
    }
  ]
}
```

- [ ] **Step 7: Run the targeted tests and verify they pass**

Run:

```bash
cd /Users/MAC/Documents/Claude-patch
PYTHONPATH=src python3 -m pytest tests/test_upstream_attachment_suppression.py -q
```

Expected: PASS with all tests in `/Users/MAC/Documents/Claude-patch/tests/test_upstream_attachment_suppression.py` passing. Tests that require the exact local Claude Code `2.1.199` source may skip only if `/Users/MAC/.local/share/claude/versions/2.1.199` is missing or its SHA is no longer `e3cb61abc8a2ec7b98976cee1ffdde5a3fa755c9990bc8d688cd89290e0dcec0`.

- [ ] **Step 8: Commit package and tests**

Run:

```bash
cd /Users/MAC/Documents/Claude-patch
git add tests/test_upstream_attachment_suppression.py packages/upstream-attachment-suppression
git commit -m "Add upstream attachment suppression package"
```

Expected: commit succeeds. Do not stage unrelated dirty files.

## Task 3: Mark the old reminder suppression package as superseded

**Files:**
- Modify: `/Users/MAC/Documents/Claude-patch/packages/reminder-suppression/README.md`

- [ ] **Step 1: Replace the README with a supersession notice**

Replace `/Users/MAC/Documents/Claude-patch/packages/reminder-suppression/README.md` with:

```markdown
# Reminder suppression (superseded)

This package is superseded by `packages/upstream-attachment-suppression`.

`reminder-suppression` patched selected renderer/model-conversion cases after attachment records could already exist. That was useful as an early experiment, but it is too late for the stronger invariant: selected recurring reminder/accounting families should never become transcript rows, never enter request assembly, never render in chat, and never appear in the Hidden Context drawer.

Use `packages/upstream-attachment-suppression` for Claude Code `2.1.199`. That package gates denied attachment generator labels before generator execution and filters denied attachment objects before `li(...)` row construction.

This package remains in the repository as historical/reference material for Claude Code `2.1.198`. Do not install it together with `upstream-attachment-suppression` unless a future compatibility test explicitly proves the combination is harmless for a specific Claude Code version.
```

- [ ] **Step 2: Run package tests again**

Run:

```bash
cd /Users/MAC/Documents/Claude-patch
PYTHONPATH=src python3 -m pytest tests/test_upstream_attachment_suppression.py -q
```

Expected: PASS.

- [ ] **Step 3: Commit the supersession notice**

Run:

```bash
cd /Users/MAC/Documents/Claude-patch
git add packages/reminder-suppression/README.md
git commit -m "Mark reminder suppression package superseded"
```

Expected: commit succeeds. Do not stage unrelated dirty files.

## Task 4: Build and inspect a copied patched binary

**Files:**
- No source files changed.
- Build output: `/Users/MAC/Documents/Claude-patch/.development/claude-monkey-builds/upstream-attachment-suppression-2.1.199/claude`
- Build report: `/Users/MAC/Documents/Claude-patch/.development/claude-monkey-builds/upstream-attachment-suppression-2.1.199/build-report.json`

- [ ] **Step 1: Validate the package through the CLI**

Run:

```bash
cd /Users/MAC/Documents/Claude-patch
PYTHONPATH=src python3 -m claude_monkey validate-package \
  --source /Users/MAC/.local/share/claude/versions/2.1.199 \
  --package packages/upstream-attachment-suppression \
  --source-version 2.1.199 \
  --source-version-output "2.1.199 (Claude Code)" \
  --platform darwin \
  --arch arm64 \
  --json
```

Expected JSON fields:

```text
"ok": true
"packageId": "upstream-attachment-suppression"
"opId": "ug-drop-denied-labels-2-1-199"
"opId": "hze-filter-before-li-2-1-199"
```

- [ ] **Step 2: Build the copied binary with signing and smoke enabled**

Run:

```bash
cd /Users/MAC/Documents/Claude-patch
rm -rf .development/claude-monkey-builds/upstream-attachment-suppression-2.1.199
PYTHONPATH=src python3 -m claude_monkey build \
  --source /Users/MAC/.local/share/claude/versions/2.1.199 \
  --package packages/upstream-attachment-suppression \
  --output-dir .development/claude-monkey-builds/upstream-attachment-suppression-2.1.199 \
  --source-version 2.1.199 \
  --source-version-output "2.1.199 (Claude Code)" \
  --platform darwin \
  --arch arm64 \
  --json
```

Expected JSON fields:

```text
"status": "verified"
"automatedStatus": "passed"
"activationEligible": true
"enabledPatches": ["upstream-attachment-suppression"]
```

- [ ] **Step 3: Inspect the build report for graph and smoke evidence**

Run:

```bash
cd /Users/MAC/Documents/Claude-patch
python3 - <<'PY'
import json
from pathlib import Path
report = json.loads(Path('.development/claude-monkey-builds/upstream-attachment-suppression-2.1.199/build-report.json').read_text())
assert report['status'] == 'verified', report['status']
assert report['automatedStatus'] == 'passed', report['automatedStatus']
assert report['postSignInspection']['bunGraphValid'] is True, report['postSignInspection']
assert report['postSignInspection']['validationErrors'] == [], report['postSignInspection']
assert report['manualSmoke']['required'] is False, report['manualSmoke']
assert report['smokeTestResults'][0]['passed'] is True, report['smokeTestResults']
ops = {item['opId']: item for item in report['operationsApplied']}
assert ops['ug-drop-denied-labels-2-1-199']['delta'] == 473, ops
assert ops['hze-filter-before-li-2-1-199']['delta'] == 46, ops
print('PASS build report verified')
PY
```

Expected output:

```text
PASS build report verified
```

- [ ] **Step 4: Run direct binary smoke checks**

Run:

```bash
cd /Users/MAC/Documents/Claude-patch
codesign --verify --strict .development/claude-monkey-builds/upstream-attachment-suppression-2.1.199/claude
.development/claude-monkey-builds/upstream-attachment-suppression-2.1.199/claude --version
.development/claude-monkey-builds/upstream-attachment-suppression-2.1.199/claude --help >/tmp/upstream-attachment-suppression-help.out
head -5 /tmp/upstream-attachment-suppression-help.out
```

Expected output includes:

```text
2.1.199 (Claude Code)
Usage: claude [options] [command] [prompt]
```

- [ ] **Step 5: Commit no files for build artifacts**

Run:

```bash
cd /Users/MAC/Documents/Claude-patch
git status --short
```

Expected: no tracked source changes from Task 4. Build artifacts under `.development/` are local verification evidence and must not be staged unless a repository convention explicitly changes.

## Task 5: Controlled future-row smoke against a copied binary

**Files:**
- No source files changed.
- Runtime output file: `/tmp/upstream-attachment-suppression-runtime.json`

This task can call the Claude API. Run it only when a network/API-backed Claude Code smoke is acceptable.

- [ ] **Step 1: Run a new-session print-mode smoke with tools disabled**

Run:

```bash
cd /Users/MAC/Documents/Claude-patch
PATCHED=/Users/MAC/Documents/Claude-patch/.development/claude-monkey-builds/upstream-attachment-suppression-2.1.199/claude
SESSION_ID=$(python3 - <<'PY'
import uuid
print(uuid.uuid4())
PY
)
echo "session_id=$SESSION_ID"
"$PATCHED" \
  --print \
  --output-format json \
  --session-id "$SESSION_ID" \
  --tools "" \
  --permission-mode default \
  "Reply with exactly: OK" | tee /tmp/upstream-attachment-suppression-runtime.json
python3 - <<PY
import json
from pathlib import Path
payload = json.loads(Path('/tmp/upstream-attachment-suppression-runtime.json').read_text())
assert payload.get('session_id') == '$SESSION_ID', payload
print('PASS runtime json captured', payload.get('session_id'))
PY
```

Expected output includes:

```text
PASS runtime json captured
```

- [ ] **Step 2: Locate the session JSONL and assert denied rows are absent**

Run:

```bash
SESSION_ID=$(python3 - <<'PY'
import json
from pathlib import Path
payload = json.loads(Path('/tmp/upstream-attachment-suppression-runtime.json').read_text())
print(payload['session_id'])
PY
)
SESSION_FILE=$(find "$HOME/.claude" -name '*.jsonl' -type f -print0 2>/dev/null | xargs -0 grep -l "$SESSION_ID" | head -1)
if [ -z "$SESSION_FILE" ]; then
  echo "session jsonl not found for $SESSION_ID" >&2
  exit 1
fi
echo "session_file=$SESSION_FILE"
python3 - <<PY
from pathlib import Path
session = Path('$SESSION_FILE')
text = session.read_text(errors='replace')
denied = [
    'todo_reminder',
    'task_reminder',
    'tool_search_usage_reminder',
    'token_usage',
    'total_tokens_reminder',
    'budget_usd',
    'output_token_usage',
]
found = [item for item in denied if item in text]
assert not found, {'session': str(session), 'found': found}
print('PASS no denied attachment family strings in new session jsonl')
PY
```

Expected output:

```text
PASS no denied attachment family strings in new session jsonl
```

- [ ] **Step 3: Do not commit runtime smoke output**

Run:

```bash
cd /Users/MAC/Documents/Claude-patch
git status --short
```

Expected: no tracked source changes from Task 5.

## Task 6: Final verification and review handoff

**Files:**
- No new source files beyond Tasks 1 through 3.

- [ ] **Step 1: Run focused package tests**

Run:

```bash
cd /Users/MAC/Documents/Claude-patch
PYTHONPATH=src python3 -m pytest tests/test_upstream_attachment_suppression.py -q
```

Expected: PASS.

- [ ] **Step 2: Run current reference package tests**

Run:

```bash
cd /Users/MAC/Documents/Claude-patch
PYTHONPATH=src python3 -m pytest tests/test_reference_packages.py -q
```

Expected: PASS or skips only for source artifacts missing on the local machine. Any failure involving unrelated untracked packages must be investigated before claiming completion.

- [ ] **Step 3: Run the builder and graph tests touched by package validation/build behavior**

Run:

```bash
cd /Users/MAC/Documents/Claude-patch
PYTHONPATH=src python3 -m pytest tests/test_manifest_v2.py tests/test_module_patch.py tests/test_bun_graph.py tests/test_repack.py tests/test_builder_v15.py tests/test_cli_v15.py -q
```

Expected: PASS.

- [ ] **Step 4: Run a final diff audit**

Run:

```bash
cd /Users/MAC/Documents/Claude-patch
git status --short
git diff -- packages/upstream-attachment-suppression packages/reminder-suppression/README.md tests/test_upstream_attachment_suppression.py
```

Expected:

- only the intended package, test, and README changes are present after the implementation commits;
- no changes to `src/claude_monkey/manifest_v2.py`, `src/claude_monkey/module_patch.py`, `src/claude_monkey/repack.py`, or `src/claude_monkey/bun_graph.py`;
- no unrelated dirty files are staged or committed.

- [ ] **Step 5: Request code review**

Use `superpowers:requesting-code-review` after implementation commits. The reviewer brief must include:

```text
Review the upstream attachment suppression package for ClaudeMonkey.

Requirements:
- Package must target Claude Code 2.1.199 only.
- It must use current schema-v2 module-local splice operations and Bun graph repack; do not invent a new package engine.
- Denied generator labels must be gated in ug(...) before generator execution and before tengu_attachment_compute_duration telemetry.
- Denied attachment types must be filtered in Hze(...) before tengu_attachments telemetry and before li(c,o).
- It must not patch zsr(...), Jur(...), normal-channel projection, or Hidden Context drawer code.
- It must mark reminder-suppression as superseded.
- It must include static tests, JS fixture behavior tests, direct li(...) bypass audit, package validation against real 2.1.199, and copied-binary build evidence.
```

Expected review status before merge: no Critical or Important findings remain unresolved.

## Spec coverage self-check

This plan covers:

- New package creation: Task 2.
- Superseding `reminder-suppression`: Task 3.
- Primary `ug(...)` pre-compute label gate: Tasks 1 and 2.
- Secondary `Hze(...)` pre-`li(...)` guard: Tasks 1 and 2.
- Denied label/type policy: Tasks 1 and 2.
- Keep-family boundaries: Task 1.
- No renderer/drawer/model-conversion patching: Task 1.
- Direct `li(...)` denied-family bypass audit: Task 1.
- Static package validation: Tasks 1, 4, and 6.
- Fixture behavior for generator execution, telemetry, `li(...)`, and kept objects: Task 1.
- Copied binary build, signing, `--version`, and `--help`: Task 4.
- Future-row runtime smoke: Task 5.
- Historical transcript non-migration: README in Task 2.
