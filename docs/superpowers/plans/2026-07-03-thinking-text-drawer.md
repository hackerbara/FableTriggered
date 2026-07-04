# Thinking Text Drawer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a ClaudeMonkey `thinking-text-drawer` package that exposes Ctrl-O-visible structured thinking text plus live raw thinking deltas in an always-openable footer drawer without changing main chat rendering, Ctrl-O behavior, request assembly, JSONL history, or model-visible context.

**Architecture:** Create a new standalone direct footer/overlay seam owner for Claude Code 2.1.201. Reuse hidden-context drawer mechanics only as a UI/payload pattern; do not copy its `frame.visible` availability gate. Feed a display-only global frame from structured assistant content blocks, live `thinking_delta.thinking` chunks, cancellation salvage, and secondary redacted/estimate evidence.

**Tech Stack:** Python package tests with `pytest`-style assertions, ClaudeMonkey manifest v2 (`replace_exact` / `replace_between`), JavaScript payloads patched into `/$bunfs/root/src/entrypoints/cli.js`, graph-aware Bun repack validation.

---

## File map

Create:

- `packages/thinking-text-drawer/README.md` — package purpose, compatibility, build/smoke commands, and “overlay only” invariant.
- `packages/thinking-text-drawer/patch.json` — manifest v2 pinned to Claude Code 2.1.201 identity.
- `packages/thinking-text-drawer/payloads/01-thinking-text-helpers.js` — global frame helpers and merge/dedupe utilities.
- `packages/thinking-text-drawer/payloads/02-live-thinking-delta-collector.js` — replacement for the selected raw `thinking_delta` seam.
- `packages/thinking-text-drawer/payloads/03-structured-thinking-block-collector.js` — replacement for the assistant content block dispatch seam before transcript-mode suppression.
- `packages/thinking-text-drawer/payloads/04-footer-target-thinking.js` — footer target array replacement that makes Thinking always selectable.
- `packages/thinking-text-drawer/payloads/05-footer-thinking-selection-flag.js` — footer selection flag replacement.
- `packages/thinking-text-drawer/payloads/06-footer-thinking-up-down-scroll.js` — Thinking scroll/open keyboard handling.
- `packages/thinking-text-drawer/payloads/07-footer-thinking-open-clear-close.js` — open selected, clearSelection, and x-only close handling.
- `packages/thinking-text-drawer/payloads/08-thinking-bottom-overlay-globals.js` — selected-only bottom overlay globals/state publication.
- `packages/thinking-text-drawer/payloads/09-thinking-bottom-overlay-renderer.js` — drawer renderer using existing bottom overlay sibling.
- `packages/thinking-text-drawer/payloads/10-footer-thinking-status-bar.js` — footer status segment and unread/flash indicator.
- `tests/test_thinking_text_drawer_package.py` — package invariants, target identity, x-only close, and helper/dedupe string checks.

Modify only if a test proves the path names differ:

- No source-code changes outside `packages/thinking-text-drawer/**` and `tests/test_thinking_text_drawer_package.py`.
- Do not modify `packages/hidden-context-drawer/**`.
- Do not modify ClaudeMonkey patch engine files.

Scratch/read-only artifacts allowed during execution:

- `.development/artifacts/claude-2.1.201-thinking-text-drawer-source-module0.js` — optional local extracted module dump for anchor discovery. Do not commit it unless the user explicitly asks.

---

## Task 1: Add failing package invariant tests

**Files:**
- Create: `tests/test_thinking_text_drawer_package.py`

- [ ] **Step 1: Create the test file**

Write `tests/test_thinking_text_drawer_package.py`:

```python
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "thinking-text-drawer"
LIVE_2_1_201 = Path("/Users/MAC/.local/share/claude/versions/2.1.201")

EXPECTED_BINARY_SHA = "a0852d76afc47b30f5cb0b7625ec9a7714cb189f2eeef6c28c77e2be954fb7fd"
EXPECTED_BINARY_SIZE = 231708784
EXPECTED_MODULE_SHA = "46db617a7b13c062fb31595f6244819b11f7cdc6e6fed8e2c3f74a27fb6da1bd"
EXPECTED_MODULE_LENGTH = 18700756


def read_rel(path: str) -> str:
    return (PACKAGE / path).read_text(encoding="utf-8")


def package_text() -> str:
    paths = [PACKAGE / "README.md", PACKAGE / "patch.json", *sorted((PACKAGE / "payloads").glob("*.js"))]
    return "\n".join(path.read_text(encoding="utf-8") for path in paths if path.exists())


def test_thinking_text_drawer_targets_claude_2_1_201() -> None:
    manifest = json.loads((PACKAGE / "patch.json").read_text(encoding="utf-8"))
    target = manifest["targets"][0]
    identity = target["sourceIdentity"]

    assert manifest["id"] == "thinking-text-drawer"
    assert identity["claudeVersion"] == "2.1.201"
    assert identity["versionOutput"] == "2.1.201 (Claude Code)"
    assert identity["sha256"] == EXPECTED_BINARY_SHA
    assert identity["sizeBytes"] == EXPECTED_BINARY_SIZE
    assert identity["platform"] == "darwin"
    assert identity["arch"] == "arm64"

    module = target["modules"][0]
    assert module["path"] == "/$bunfs/root/src/entrypoints/cli.js"
    assert module["contentSha256"] == EXPECTED_MODULE_SHA
    assert module["contentLength"] == EXPECTED_MODULE_LENGTH
    assert len(module["operations"]) >= 8

    if LIVE_2_1_201.exists():
        assert hashlib.sha256(LIVE_2_1_201.read_bytes()).hexdigest() == EXPECTED_BINARY_SHA


def test_thinking_text_drawer_is_overlay_only_and_always_openable() -> None:
    text = package_text()
    footer_target = read_rel("payloads/04-footer-target-thinking.js")
    renderer = read_rel("payloads/09-thinking-bottom-overlay-renderer.js")

    assert "No thinking captured yet" in text
    assert "Thinking" in footer_target
    assert 'frame.visible' not in footer_target
    assert 'visible&&"thinking"' not in footer_target
    assert "__CODEX_THINKING_TEXT_DRAWER_FRAME_V1__" in text
    assert "__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__" in text
    assert "request assembly" in read_rel("README.md")
    assert "JSONL" in read_rel("README.md")
    assert "main chat" in read_rel("README.md")
    assert "x closes" in renderer


def test_thinking_text_drawer_structured_collection_is_not_ctrl_o_gated() -> None:
    structured = read_rel("payloads/03-structured-thinking-block-collector.js")

    assert "__codexTTDRecordStructuredThinking" in structured
    assert "case\"thinking\"" in structured
    assert "case\"redacted_thinking\"" in structured
    before_guard = structured.split('if(!p&&!i)return null', 1)[0]
    assert "__codexTTDRecordStructuredThinking" in before_guard
    assert "__codexTTDRecordRedactedThinking" in before_guard


def test_thinking_text_drawer_dedupe_preserves_unique_text() -> None:
    helpers = read_rel("payloads/01-thinking-text-helpers.js")

    assert "sources" in helpers
    assert "normalized structured text contains the normalized provisional text" in helpers
    assert "Levenshtein" not in helpers
    assert "close match" not in helpers
    assert "preserve both" in helpers


def test_thinking_text_drawer_x_only_close_contract() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in sorted((PACKAGE / "payloads").glob("*.js")))
    footer_actions = read_rel("payloads/07-footer-thinking-open-clear-close.js")
    overlay = read_rel("payloads/09-thinking-bottom-overlay-renderer.js")

    assert '"footer:close":()=>{if(tD)' in footer_actions
    assert "__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__=!1" in footer_actions
    clear_selection_body = footer_actions.split('"footer:clearSelection":()=>{', 1)[1].split('},"footer:close"', 1)[0]
    assert "__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__" not in clear_selection_body
    assert "tDp(!1)" not in clear_selection_body
    assert "x closes" in overlay
    assert "escape" not in text.lower()
    assert "inputOwnsEscape" not in text


if __name__ == "__main__":
    test_thinking_text_drawer_targets_claude_2_1_201()
    test_thinking_text_drawer_is_overlay_only_and_always_openable()
    test_thinking_text_drawer_structured_collection_is_not_ctrl_o_gated()
    test_thinking_text_drawer_dedupe_preserves_unique_text()
    test_thinking_text_drawer_x_only_close_contract()
    print("thinking-text drawer package checks passed")
```

- [ ] **Step 2: Run the test and verify it fails because the package does not exist yet**

Run:

```bash
python3 tests/test_thinking_text_drawer_package.py
```

Expected: `FileNotFoundError` for `packages/thinking-text-drawer/patch.json` or a missing payload file.

- [ ] **Step 3: Commit the failing test**

Run:

```bash
git add tests/test_thinking_text_drawer_package.py
git commit -m "test: add thinking text drawer package invariants"
```

---

## Task 2: Scaffold package, README, and helper payload

**Files:**
- Create: `packages/thinking-text-drawer/README.md`
- Create: `packages/thinking-text-drawer/patch.json`
- Create: `packages/thinking-text-drawer/payloads/01-thinking-text-helpers.js`

- [ ] **Step 1: Create package directories**

Run:

```bash
mkdir -p packages/thinking-text-drawer/payloads
```

- [ ] **Step 2: Write the README**

Write `packages/thinking-text-drawer/README.md`:

````markdown
# Thinking Text Drawer

Projects raw and structured thinking text that Claude Code already has or receives into an integrated footer drawer.

This is a ClaudeMonkey V1.5 package targeting `/$bunfs/root/src/entrypoints/cli.js` with the graph-aware Bun repack engine. It does not patch request assembly, does not mutate transcript JSONL, does not change model-visible context, and does not change the main chat renderer. It is only a pop-up layer the user can open whenever.

The drawer combines:

- structured `thinking` blocks that Ctrl-O transcript mode can already show;
- live `thinking_delta.thinking` chunks when the stream exposes raw text;
- virtual/salvaged thinking blocks created during interruption;
- secondary redacted/signature/estimated-token markers when raw text is unavailable.

The Thinking footer target is always available while the interactive footer is active. If no thinking has been captured, the drawer opens to `No thinking captured yet`. Captured entries affect unread/flash state, not whether the drawer can be opened.

This package is a standalone direct footer/overlay seam owner for Claude Code 2.1.201. It is expected to conflict with other direct footer drawer packages targeting the same source until structured splices or a reviewed footer-drawer framework exists.

Manual smoke is required: select Thinking from the footer, open it, verify entries or the empty state, scroll, and close with x. Ctrl-O transcript mode must continue to work, and normal chat must remain unchanged.

## Build from this checkout

```bash
cd /Users/MAC/Documents/Claude-patch
PYTHONPATH=src python3 -m claude_monkey validate-package \
  --source /Users/MAC/.local/share/claude/versions/2.1.201 \
  --package packages/thinking-text-drawer \
  --source-version 2.1.201 \
  --source-version-output '2.1.201 (Claude Code)' \
  --platform darwin \
  --arch arm64 \
  --json
```
````

- [ ] **Step 3: Write initial manifest shell**

Write `packages/thinking-text-drawer/patch.json` with the source identity and an initially empty operation list. Task 3 fills operations once exact anchors are discovered.

```json
{
  "schemaVersion": 2,
  "id": "thinking-text-drawer",
  "name": "Thinking Text Drawer",
  "description": "Projects raw and structured thinking text into an always-openable footer Thinking drawer.",
  "packageVersion": "0.1.0",
  "targets": [
    {
      "sourceIdentity": {
        "claudeVersion": "2.1.201",
        "versionOutput": "2.1.201 (Claude Code)",
        "sha256": "a0852d76afc47b30f5cb0b7625ec9a7714cb189f2eeef6c28c77e2be954fb7fd",
        "sizeBytes": 231708784,
        "platform": "darwin",
        "arch": "arm64"
      },
      "requiredEngine": "bun_graph_repack",
      "requiredBinaryFormat": "bun_standalone_macho64",
      "modules": [
        {
          "path": "/$bunfs/root/src/entrypoints/cli.js",
          "contentSha256": "46db617a7b13c062fb31595f6244819b11f7cdc6e6fed8e2c3f74a27fb6da1bd",
          "contentLength": 18700756,
          "operations": []
        }
      ],
      "preconditions": [
        {
          "type": "module_must_contain",
          "modulePath": "/$bunfs/root/src/entrypoints/cli.js",
          "value": "case\"thinking\""
        },
        {
          "type": "module_must_contain",
          "modulePath": "/$bunfs/root/src/entrypoints/cli.js",
          "value": "thinking_delta"
        }
      ],
      "postconditions": [
        {
          "type": "module_must_contain",
          "modulePath": "/$bunfs/root/src/entrypoints/cli.js",
          "value": "__CODEX_THINKING_TEXT_DRAWER_FRAME_V1__"
        },
        {
          "type": "module_must_contain",
          "modulePath": "/$bunfs/root/src/entrypoints/cli.js",
          "value": "No thinking captured yet"
        }
      ],
      "manualSmoke": {
        "required": true,
        "reason": "Thinking text availability depends on live Claude Code stream behavior and Ctrl-O-visible structured thinking blocks."
      }
    }
  ]
}
```

- [ ] **Step 4: Write helper payload**

Write `packages/thinking-text-drawer/payloads/01-thinking-text-helpers.js` as an insertion-before payload. End it with the anchor selected in Task 3.

Use this helper body before the anchor:

```javascript
function __codexTTDNow(){try{return Date.now()}catch(e){return 0}}
function __codexTTDText(e){return typeof e==="string"?e:""}
function __codexTTDNormalize(e){return __codexTTDText(e).replace(/\s+/g," ").trim()}
function __codexTTDCompactLabel(e){let t=__codexTTDText(e).replace(/\s+/g," ").trim();return t.length>80?`${t.slice(0,80)}…`:t}
function __codexTTDEnsure(){let e=globalThis.__CODEX_THINKING_TEXT_DRAWER_FRAME_V1__;if(!e||typeof e!=="object")e={entries:[],visible:true,unread:false,flashUntil:0,updatedAt:0,scroll:0},globalThis.__CODEX_THINKING_TEXT_DRAWER_FRAME_V1__=e;return e}
function __codexTTDKey(e){return [e.source||"unknown",e.messageId||"",e.requestId||"",e.blockIndex??"",e.streamKey||"",e.status||""].join(":")}
function __codexTTDLines(e){let t=__codexTTDText(e);if(!t)return[];let n=t.split(/\r?\n/);return n.length>400?[...n.slice(0,400),"… displayed text truncated; captured text preserved in frame entry"]:n}
function __codexTTDUpsert(e){let t=__codexTTDEnsure(),n={...e};n.text=__codexTTDText(n.text);n.charCount=n.text.length;n.key=n.key||__codexTTDKey(n);n.updatedAt=__codexTTDNow();n.sources=Array.isArray(n.sources)?Array.from(new Set(n.sources)):[n.source||"unknown"];n.lines=__codexTTDLines(n.text);let r=t.entries.findIndex(o=>o.key===n.key);if(r>=0)t.entries=[...t.entries.slice(0,r),{...t.entries[r],...n,sources:Array.from(new Set([...(t.entries[r].sources||[]),...n.sources]))},...t.entries.slice(r+1)];else t.entries=[n,...t.entries].slice(0,80);t.visible=true;t.unread=true;t.flashUntil=Number.MAX_SAFE_INTEGER;t.updatedAt=n.updatedAt;return t}
function __codexTTDMergeStructured(e){let t=__codexTTDEnsure(),n=__codexTTDNormalize(e.text),r=t.entries.findIndex(o=>o.messageId&&e.messageId&&o.messageId===e.messageId&&o.blockIndex===e.blockIndex);if(r<0){let o=t.entries.filter(s=>s.status==="provisional"&&s.turnKey&&e.turnKey&&s.turnKey===e.turnKey);if(o.length===1){let s=__codexTTDNormalize(o[0].text);if(s&&n.includes(s))r=t.entries.indexOf(o[0])}}if(r>=0){let o=t.entries[r],s={...o,...e,text:__codexTTDText(e.text),status:"final",source:"structured",sources:Array.from(new Set([...(o.sources||[]),"live","structured"])),charCount:__codexTTDText(e.text).length,updatedAt:__codexTTDNow()};s.lines=__codexTTDLines(s.text);t.entries=[...t.entries.slice(0,r),s,...t.entries.slice(r+1)];t.visible=true;t.unread=true;t.flashUntil=Number.MAX_SAFE_INTEGER;t.updatedAt=s.updatedAt;return t}return __codexTTDUpsert({...e,source:"structured",status:"final",sources:["structured"]})}
function __codexTTDRecordStructuredThinking(e){let t=__codexTTDText(e?.thinking);if(!t.trim())return;return __codexTTDMergeStructured({source:"structured",status:"final",text:t,messageId:e?.messageId,requestId:e?.requestId,blockIndex:e?.blockIndex,turnKey:e?.turnKey,timestamp:e?.timestamp})}
function __codexTTDRecordLiveThinking(e){let t=__codexTTDText(e?.text);if(!t)return;let n=__codexTTDEnsure(),r=e?.streamKey||"active",o=n.entries.find(s=>s.source==="live"&&s.status==="provisional"&&s.streamKey===r),s=o?`${o.text}${t}`:t;return __codexTTDUpsert({source:"live",status:"provisional",text:s,streamKey:r,turnKey:e?.turnKey,requestId:e?.requestId,blockIndex:e?.blockIndex,sources:["live"]})}
function __codexTTDRecordRedactedThinking(e){return __codexTTDUpsert({source:"redacted",status:"secondary",text:"[redacted thinking block present]",messageId:e?.messageId,requestId:e?.requestId,blockIndex:e?.blockIndex,turnKey:e?.turnKey,sources:["redacted"]})}
function __codexTTDRecordThinkingEstimate(e){let t=typeof e?.estimatedTokensDelta==="number"?e.estimatedTokensDelta:void 0,n=typeof e?.estimatedTokens==="number"?e.estimatedTokens:void 0;return __codexTTDUpsert({source:"estimate",status:"secondary",text:`thinking active; raw text not exposed${t!==void 0?`, +${t} estimated tokens`:""}${n!==void 0?`, ${n} total estimated`:""}`,streamKey:e?.streamKey,turnKey:e?.turnKey,requestId:e?.requestId,estimatedTokens:n,estimatedTokensDelta:t,sources:["estimate"]})}
function __codexTTDDrawerFrame(){let e=__codexTTDEnsure();return{...e,lineCount:e.entries.reduce((t,n)=>t+(n.lines?.length||1),0),entryCount:e.entries.length,empty:e.entries.length===0}}
// normalized structured text contains the normalized provisional text; otherwise preserve both
```

Task 3 chooses the final anchor and appends it to this file.

- [ ] **Step 5: Run tests and verify expected partial failure**

Run:

```bash
python3 tests/test_thinking_text_drawer_package.py
```

Expected: target identity test now reaches the manifest but fails on operation count, and payload-specific tests fail because payloads `02`-`10` are not created yet.

- [ ] **Step 6: Commit scaffold**

Run:

```bash
git add packages/thinking-text-drawer tests/test_thinking_text_drawer_package.py
git commit -m "feat: scaffold thinking text drawer package"
```

---

## Task 3: Discover 2.1.201 anchors and complete manifest metadata

**Files:**
- Modify: `packages/thinking-text-drawer/patch.json`
- Modify: `packages/thinking-text-drawer/payloads/01-thinking-text-helpers.js`
- Create/modify: `packages/thinking-text-drawer/payloads/02-live-thinking-delta-collector.js`
- Create/modify: `packages/thinking-text-drawer/payloads/03-structured-thinking-block-collector.js`
- Create/modify: `packages/thinking-text-drawer/payloads/04-footer-target-thinking.js`
- Create/modify: `packages/thinking-text-drawer/payloads/05-footer-thinking-selection-flag.js`
- Create/modify: `packages/thinking-text-drawer/payloads/06-footer-thinking-up-down-scroll.js`
- Create/modify: `packages/thinking-text-drawer/payloads/07-footer-thinking-open-clear-close.js`
- Create/modify: `packages/thinking-text-drawer/payloads/08-thinking-bottom-overlay-globals.js`
- Create/modify: `packages/thinking-text-drawer/payloads/09-thinking-bottom-overlay-renderer.js`
- Create/modify: `packages/thinking-text-drawer/payloads/10-footer-thinking-status-bar.js`

- [ ] **Step 1: Extract the current module source to a scratch artifact**

Run:

```bash
PYTHONPATH=src python3 - <<'PY'
from pathlib import Path
from claude_monkey.macho import find_macho_layout
from claude_monkey.bun_graph import parse_bun_section
source = Path('/Users/MAC/.local/share/claude/versions/2.1.201')
raw = source.read_bytes()
layout = find_macho_layout(raw)
section = raw[layout.bun_section.offset:layout.bun_section.offset + layout.bun_section.size]
graph = parse_bun_section(section)
module = graph.module_by_path['/$bunfs/root/src/entrypoints/cli.js']
out = Path('.development/artifacts/claude-2.1.201-thinking-text-drawer-source-module0.js')
out.parent.mkdir(parents=True, exist_ok=True)
out.write_bytes(module.content)
print(out)
print(len(module.content))
PY
```

Expected output includes:

```text
.development/artifacts/claude-2.1.201-thinking-text-drawer-source-module0.js
18700756
```

- [ ] **Step 2: Count candidate anchors**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
src = Path('.development/artifacts/claude-2.1.201-thinking-text-drawer-source-module0.js').read_text(encoding='utf-8')
needles = {
  'helper_anchor': 'function Ypr(e){',
  'bottom_overlay': 'function Ilc(){let e=MXe.c(2),t=clc();if(!t)return null;',
  'footer_targets': 'ss=wo.useMemo(()=>[Ui&&"tasks",po&&"workflows",Fn&&"tmux",_e&&"bagel",Tr&&"bridge",Ne&&"frame"].filter(Boolean),[Ui,po,Fn,_e,Tr,Ne])',
  'selection_flags': 'let lm=Lm==="tasks",ZE=Lm==="workflows",Hd=Lm==="tmux",Zp=Lm==="bagel",AT=Lm==="bridge",Mm=Lm==="frame";',
  'structured_case': 'case"thinking":{if(!p&&!i)return null;',
  'redacted_case': 'case"redacted_thinking":{if(!p&&!i)return null;',
  'estimate_drop': 'if(es.type==="system"&&es.subtype==="thinking_tokens"&&"estimated_tokens_delta"in es)continue;',
  'raw_delta': 'case"thinking_delta":{let{delta:d}=e.event;'
}
for name, needle in needles.items():
    print(f'{name}: {src.count(needle)}')
PY
```

Expected: every chosen anchor prints `1`. If any print `0`, inspect nearby source and substitute the exact 2.1.201 text that occurs once. If any print more than `1`, extend the exact snippet until unique.

- [ ] **Step 3: Compute operation hashes after payloads are written**

Use this command after each payload file contains its final replacement text:

```bash
python3 - <<'PY'
import hashlib
from pathlib import Path
src = Path('.development/artifacts/claude-2.1.201-thinking-text-drawer-source-module0.js').read_text(encoding='utf-8')
ops = {
  'thinking-helpers-before-ypr': 'function Ypr(e){',
  'thinking-structured-block-collector': 'case"redacted_thinking":{if(!p&&!i)return null;let S;if(t[40]!==r)S=Lb.jsx(qRl,{addMargin:r}),t[40]=r,t[41]=S;else S=t[41];return S}case"thinking":{if(!p&&!i)return null;let S;if(t[42]!==r||t[43]!==p||t[44]!==n||t[45]!==i)S=Lb.jsx(wtr,{addMargin:r,param:n,isTranscriptMode:p,verbose:i}),t[42]=r,t[43]=p,t[44]=n,t[45]=i,t[46]=S;else S=t[46];return S}',
  'thinking-footer-target': 'ss=wo.useMemo(()=>[Ui&&"tasks",po&&"workflows",Fn&&"tmux",_e&&"bagel",Tr&&"bridge",Ne&&"frame"].filter(Boolean),[Ui,po,Fn,_e,Tr,Ne])'
}
for op_id, exact in ops.items():
    count = src.count(exact)
    print(op_id, 'count', count, 'len', len(exact.encode()), 'sha', hashlib.sha256(exact.encode()).hexdigest())
PY
```

For operations whose exact text differs from the sample, update the `ops` dictionary with the final exact anchor before computing length and SHA.

- [ ] **Step 4: Fill `patch.json` operations with computed hashes**

After payload files are written for Tasks 4-7, run this manifest updater. It computes `oldRangeLength`, `oldRangeSha256`, and replacement SHA values from the exact source anchors and payload files.

```bash
python3 - <<'PY'
import hashlib
import json
from pathlib import Path

source_path = Path('.development/artifacts/claude-2.1.201-thinking-text-drawer-source-module0.js')
source = source_path.read_text(encoding='utf-8')
package = Path('packages/thinking-text-drawer')
manifest_path = package / 'patch.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))

operation_specs = [
    {
        'opId': 'thinking-helpers-before-ypr',
        'label': 'Thinking Text Drawer helpers before hidden attachment filter',
        'exact': 'function Ypr(e){',
        'path': 'payloads/01-thinking-text-helpers.js',
        'knownBehaviorChange': 'Adds display-only Thinking drawer frame helpers; does not mutate request assembly, transcript JSONL, or model-visible context.',
    },
    {
        'opId': 'thinking-live-delta-collector',
        'label': 'record live raw thinking_delta text before progress-only conversion',
        'exact': 'case"thinking_delta":{let{delta:d}=e.event;',
        'path': 'payloads/02-live-thinking-delta-collector.js',
        'knownBehaviorChange': 'Records live raw thinking delta text into display-only drawer state when the stream exposes it.',
    },
    {
        'opId': 'thinking-structured-block-collector',
        'label': 'record structured thinking/redacted blocks before transcript-mode suppression',
        'exact': 'case"redacted_thinking":{if(!p&&!i)return null;let S;if(t[40]!==r)S=Lb.jsx(qRl,{addMargin:r}),t[40]=r,t[41]=S;else S=t[41];return S}case"thinking":{if(!p&&!i)return null;let S;if(t[42]!==r||t[43]!==p||t[44]!==n||t[45]!==i)S=Lb.jsx(wtr,{addMargin:r,param:n,isTranscriptMode:p,verbose:i}),t[42]=r,t[43]=p,t[44]=n,t[45]=i,t[46]=S;else S=t[46];return S}',
        'path': 'payloads/03-structured-thinking-block-collector.js',
        'knownBehaviorChange': 'Records structured thinking blocks for the drawer before normal-mode rendering suppresses them.',
    },
    {
        'opId': 'thinking-footer-target',
        'label': 'always add Thinking footer target in interactive footer mode',
        'exact': 'ss=wo.useMemo(()=>[Ui&&"tasks",po&&"workflows",Fn&&"tmux",_e&&"bagel",Tr&&"bridge",Ne&&"frame"].filter(Boolean),[Ui,po,Fn,_e,Tr,Ne])',
        'path': 'payloads/04-footer-target-thinking.js',
        'knownBehaviorChange': 'Makes the Thinking drawer selectable even when no thinking has been captured yet.',
    },
]

# Extend operation_specs with the exact 2.1.201 anchors discovered for payloads 05-10 before running.
# Do not use approximate anchors: each exact string must occur once in source.

ops = []
for spec in operation_specs:
    exact = spec['exact']
    count = source.count(exact)
    if count != 1:
        raise SystemExit(f"{spec['opId']} exact count is {count}, expected 1")
    payload_bytes = (package / spec['path']).read_bytes()
    op = {
        'opId': spec['opId'],
        'label': spec['label'],
        'type': 'replace_exact',
        'exact': exact,
        'requireWithinRange': [],
        'oldRangeSha256': hashlib.sha256(exact.encode('utf-8')).hexdigest(),
        'oldRangeLength': len(exact.encode('utf-8')),
        'replacement': {
            'path': spec['path'],
            'sha256': hashlib.sha256(payload_bytes).hexdigest(),
        },
    }
    if spec.get('knownBehaviorChange'):
        op['knownBehaviorChange'] = spec['knownBehaviorChange']
    ops.append(op)

manifest['targets'][0]['modules'][0]['operations'] = ops
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
print(f'wrote {len(ops)} operations')
PY
```

- [ ] **Step 5: Run package tests and validation**

Run:

```bash
python3 tests/test_thinking_text_drawer_package.py
PYTHONPATH=src python3 -m claude_monkey validate-package \
  --source /Users/MAC/.local/share/claude/versions/2.1.201 \
  --package packages/thinking-text-drawer \
  --source-version 2.1.201 \
  --source-version-output '2.1.201 (Claude Code)' \
  --platform darwin \
  --arch arm64 \
  --json
```

Expected after all payload tasks: tests pass and validation JSON contains `"ok": true` and `"errors": []`.

- [ ] **Step 6: Commit anchor map and manifest progress**

Run after all payload files referenced by the manifest exist:

```bash
git add packages/thinking-text-drawer tests/test_thinking_text_drawer_package.py
git commit -m "feat: pin thinking text drawer anchors"
```

---

## Task 4: Implement structured thinking collection before Ctrl-O suppression

**Files:**
- Modify: `packages/thinking-text-drawer/payloads/03-structured-thinking-block-collector.js`
- Modify: `packages/thinking-text-drawer/patch.json`

- [ ] **Step 1: Replace the redacted/thinking switch cases**

Create `packages/thinking-text-drawer/payloads/03-structured-thinking-block-collector.js` from the exact 2.1.201 switch-case anchor, inserting the recorder calls before the existing normal-mode guards.

Use this replacement shape, preserving the exact stock variable names from the discovered anchor:

```javascript
case"redacted_thinking":{try{__codexTTDRecordRedactedThinking({block:n,blockIndex:r,turnKey:void 0})}catch(A){}if(!p&&!i)return null;let S;if(t[40]!==r)S=Lb.jsx(qRl,{addMargin:r}),t[40]=r,t[41]=S;else S=t[41];return S}case"thinking":{try{__codexTTDRecordStructuredThinking({thinking:n?.thinking,messageId:n?.id,blockIndex:r,turnKey:void 0})}catch(A){}if(!p&&!i)return null;let S;if(t[42]!==r||t[43]!==p||t[44]!==n||t[45]!==i)S=Lb.jsx(wtr,{addMargin:r,param:n,isTranscriptMode:p,verbose:i}),t[42]=r,t[43]=p,t[44]=n,t[45]=i,t[46]=S;else S=t[46];return S}
```

If the exact anchor uses different cache indexes or variable names, preserve those stock names and only add the two `try{__codexTTD...}catch(A){}` calls before the guards.

- [ ] **Step 2: Verify the collector is before the guard**

Run:

```bash
python3 tests/test_thinking_text_drawer_package.py
```

Expected: `test_thinking_text_drawer_structured_collection_is_not_ctrl_o_gated` passes once payloads `04`-`10` exist; before then, failures are from missing later payloads only.

- [ ] **Step 3: Validate against the source module**

Run:

```bash
PYTHONPATH=src python3 -m claude_monkey validate-package \
  --source /Users/MAC/.local/share/claude/versions/2.1.201 \
  --package packages/thinking-text-drawer \
  --source-version 2.1.201 \
  --source-version-output '2.1.201 (Claude Code)' \
  --platform darwin \
  --arch arm64 \
  --json
```

Expected during this task: validation may fail for payloads not implemented yet, but it must not fail because the structured collector anchor is missing once the manifest operation is added.

- [ ] **Step 4: Commit structured collector**

Run:

```bash
git add packages/thinking-text-drawer/payloads/03-structured-thinking-block-collector.js packages/thinking-text-drawer/patch.json
git commit -m "feat: collect structured thinking blocks"
```

---

## Task 5: Implement live raw thinking delta collection

**Files:**
- Modify: `packages/thinking-text-drawer/payloads/02-live-thinking-delta-collector.js`
- Modify: `packages/thinking-text-drawer/patch.json`

- [ ] **Step 1: Patch the raw `thinking_delta` seam**

Use the discovered 2.1.201 stream handler anchor that starts with:

```javascript
case"thinking_delta":{let{delta:d}=e.event;
```

Create `packages/thinking-text-drawer/payloads/02-live-thinking-delta-collector.js` by preserving stock behavior and adding display-only recording when `d.thinking` exists.

Replacement shape:

```javascript
case"thinking_delta":{let{delta:d}=e.event;if("thinking"in d&&typeof d.thinking==="string"&&d.thinking.length>0)try{__codexTTDRecordLiveThinking({text:d.thinking,streamKey:e?.message?.id||e?.event?.index||"active",requestId:e?.requestId,blockIndex:e?.event?.index})}catch(p){}if("estimated_tokens"in d&&typeof d.estimated_tokens==="number"){try{__codexTTDRecordThinkingEstimate({estimatedTokensDelta:d.estimated_tokens,streamKey:e?.message?.id||e?.event?.index||"active",requestId:e?.requestId})}catch(p){}o?.({type:"thinking_progress",estimatedTokensDelta:d.estimated_tokens})}else if("thinking"in d&&typeof d.thinking==="string"&&d.thinking.length>0)o?.({type:"thinking_progress",estimatedTokensDelta:Kon(d.thinking)});return}
```

If the stock block contains additional logic, preserve it and add the `__codexTTDRecordLiveThinking` / `__codexTTDRecordThinkingEstimate` calls without changing emitted progress events.

- [ ] **Step 2: Add a postcondition for the live collector marker**

In `packages/thinking-text-drawer/patch.json`, add a module postcondition value:

```json
{
  "type": "module_must_contain",
  "modulePath": "/$bunfs/root/src/entrypoints/cli.js",
  "value": "__codexTTDRecordLiveThinking"
}
```

- [ ] **Step 3: Validate live collector anchor uniqueness**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
src = Path('.development/artifacts/claude-2.1.201-thinking-text-drawer-source-module0.js').read_text(encoding='utf-8')
needle = 'case"thinking_delta":{let{delta:d}=e.event;'
print(src.count(needle))
PY
```

Expected: `1`.

- [ ] **Step 4: Commit live collector**

Run:

```bash
git add packages/thinking-text-drawer/payloads/02-live-thinking-delta-collector.js packages/thinking-text-drawer/patch.json
git commit -m "feat: collect live thinking deltas"
```

---

## Task 6: Implement always-openable footer target and x-only drawer controls

**Files:**
- Modify: `packages/thinking-text-drawer/payloads/04-footer-target-thinking.js`
- Modify: `packages/thinking-text-drawer/payloads/05-footer-thinking-selection-flag.js`
- Modify: `packages/thinking-text-drawer/payloads/06-footer-thinking-up-down-scroll.js`
- Modify: `packages/thinking-text-drawer/payloads/07-footer-thinking-open-clear-close.js`
- Modify: `packages/thinking-text-drawer/payloads/08-thinking-bottom-overlay-globals.js`
- Modify: `packages/thinking-text-drawer/patch.json`

- [ ] **Step 1: Add Thinking to the footer target array unconditionally**

Use the 2.1.201 footer target anchor:

```javascript
ss=wo.useMemo(()=>[Ui&&"tasks",po&&"workflows",Fn&&"tmux",_e&&"bagel",Tr&&"bridge",Ne&&"frame"].filter(Boolean),[Ui,po,Fn,_e,Tr,Ne])
```

Create `payloads/04-footer-target-thinking.js` with:

```javascript
ss=wo.useMemo(()=>[Ui&&"tasks",po&&"workflows",Fn&&"tmux",_e&&"bagel",Tr&&"bridge",Ne&&"frame","thinking"].filter(Boolean),[Ui,po,Fn,_e,Tr,Ne])
```

This is intentionally not gated by frame visibility.

- [ ] **Step 2: Add a Thinking selected flag**

Use the 2.1.201 selection flag anchor:

```javascript
let lm=Lm==="tasks",ZE=Lm==="workflows",Hd=Lm==="tmux",Zp=Lm==="bagel",AT=Lm==="bridge",Mm=Lm==="frame";function Rp
```

Create `payloads/05-footer-thinking-selection-flag.js` with:

```javascript
let lm=Lm==="tasks",ZE=Lm==="workflows",Hd=Lm==="tmux",Zp=Lm==="bagel",AT=Lm==="bridge",Mm=Lm==="frame",tD=Lm==="thinking";function Rp
```

- [ ] **Step 3: Add Thinking scroll/open behavior**

Find the 2.1.201 equivalent of the Hidden Context `By` / `Jk` up/down functions. Preserve stock behavior and insert a Thinking branch:

```javascript
if(tD){let en=__codexTTDDrawerFrame();if(en.entryCount>0){globalThis.__CODEX_THINKING_TEXT_DRAWER_SCROLL_V1__=Math.max(0,(globalThis.__CODEX_THINKING_TEXT_DRAWER_SCROLL_V1__||0)-1)}return}
```

for up, and:

```javascript
if(tD){globalThis.__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__=!0;tDp(!0);return}
```

for down/open. Use the exact stock variable names from the discovered function.

- [ ] **Step 4: Add openSelected, clearSelection, and x-only close**

In `payloads/07-footer-thinking-open-clear-close.js`, preserve stock open/clear/close behavior and add:

```javascript
case"thinking":globalThis.__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__=!0,tDp(!0);break;
```

For clear selection:

```javascript
"footer:clearSelection":()=>{if(tD)return false;
```

For close:

```javascript
"footer:close":()=>{if(tD){globalThis.__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__=!1,tDp(!1),Sf(null);return}
```

Do not add an Escape binding or an `inputOwnsEscape` path.

- [ ] **Step 5: Publish selected-only overlay globals**

Create `payloads/08-thinking-bottom-overlay-globals.js` at the selected-only bottom overlay seam. It should publish:

```javascript
globalThis.__CODEX_THINKING_TEXT_DRAWER_SELECTED_V1__=!!tD;
globalThis.__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__=!!tD&&!!globalThis.__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__;
globalThis.__CODEX_THINKING_TEXT_DRAWER_SCROLL_V1__=globalThis.__CODEX_THINKING_TEXT_DRAWER_SCROLL_V1__||0;
```

Preserve stock children and focus behavior.

- [ ] **Step 6: Run x-only tests**

Run:

```bash
python3 tests/test_thinking_text_drawer_package.py
```

Expected once payloads are complete: `test_thinking_text_drawer_x_only_close_contract` passes.

- [ ] **Step 7: Commit footer controls**

Run:

```bash
git add packages/thinking-text-drawer/payloads/04-footer-target-thinking.js packages/thinking-text-drawer/payloads/05-footer-thinking-selection-flag.js packages/thinking-text-drawer/payloads/06-footer-thinking-up-down-scroll.js packages/thinking-text-drawer/payloads/07-footer-thinking-open-clear-close.js packages/thinking-text-drawer/payloads/08-thinking-bottom-overlay-globals.js packages/thinking-text-drawer/patch.json
git commit -m "feat: add thinking drawer footer controls"
```

---

## Task 7: Implement drawer renderer and footer status segment

**Files:**
- Modify: `packages/thinking-text-drawer/payloads/09-thinking-bottom-overlay-renderer.js`
- Modify: `packages/thinking-text-drawer/payloads/10-footer-thinking-status-bar.js`
- Modify: `packages/thinking-text-drawer/patch.json`

- [ ] **Step 1: Replace bottom overlay renderer**

Use the 2.1.201 bottom overlay anchor beginning with:

```javascript
function Ilc(){let e=MXe.c(2),t=clc();if(!t)return null;
```

Create `payloads/09-thinking-bottom-overlay-renderer.js` preserving stock behavior and adding a Thinking drawer when selected/open:

```javascript
function Ilc(){let e=MXe.c(12),t=clc(),n=globalThis.__CODEX_THINKING_TEXT_DRAWER_SELECTED_V1__&&globalThis.__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__,r=__codexTTDDrawerFrame(),o=globalThis.__CODEX_THINKING_TEXT_DRAWER_SCROLL_V1__||0;if(n){let s=r.entries.length===0?["No thinking captured yet"]:r.entries.flatMap((i)=>{let a=`${i.source||"thinking"}${i.status?` · ${i.status}`:""}${i.charCount?` · ${i.charCount} chars`:""}`;return [a,...(i.lines&&i.lines.length?i.lines:[i.text||""]),""]}),l=s.slice(o,o+18);return MXe.jsxs(B,{position:"absolute",bottom:"100%",left:0,right:0,opaque:!0,borderStyle:"round",borderColor:"permission",paddingX:1,children:[MXe.jsx(v,{bold:!0,children:" Thinking "}),...l.map((i,a)=>MXe.jsx(v,{wrap:"wrap",dimColor:a===0&&r.entries.length>0,children:i},`thinking-${o+a}`)),MXe.jsx(v,{dimColor:!0,children:"x closes"})]})}if(!t)return null;let s;if(e[0]!==t)s=MXe.jsx(B,{position:"absolute",bottom:"100%",left:0,right:0,opaque:!0,children:t}),e[0]=t,e[1]=s;else s=e[1];return s}
```

Adjust JSX namespace variable names (`MXe`, `B`, `v`) to match the exact 2.1.201 function scope. Preserve stock behavior when Thinking is not open.

- [ ] **Step 2: Add footer status segment**

Find the 2.1.201 footer status-bar anchor equivalent to hidden-context `footer-availability-bar-hidden-context`. Insert a Thinking segment that is available even when empty:

```javascript
let tDf=__codexTTDDrawerFrame(),tDsel=globalThis.__CODEX_THINKING_TEXT_DRAWER_SELECTED_V1__,tDflash=!tDsel&&Date.now()<(tDf.flashUntil||0),tDbar=tDsel?pi.jsx(v,{color:"permission",children:tDf.entryCount>0?`Thinking ${tDf.entryCount} (${tDf.lineCount} lines)`:"Thinking empty"},"thinking-selected"):tDflash?pi.jsx(v,{color:"permission",children:"Thinking updated"},"thinking-flash"):pi.jsx(v,{dimColor:!0,children:"Thinking"},"thinking-available");
```

Use the stock JSX namespace in that function. Add `tDbar` into the status line without removing existing stock hints.

- [ ] **Step 3: Verify empty-state availability**

Run the package test:

```bash
python3 tests/test_thinking_text_drawer_package.py
```

Expected: `test_thinking_text_drawer_is_overlay_only_and_always_openable` passes.

- [ ] **Step 4: Validate package**

Run:

```bash
PYTHONPATH=src python3 -m claude_monkey validate-package \
  --source /Users/MAC/.local/share/claude/versions/2.1.201 \
  --package packages/thinking-text-drawer \
  --source-version 2.1.201 \
  --source-version-output '2.1.201 (Claude Code)' \
  --platform darwin \
  --arch arm64 \
  --json
```

Expected: JSON contains `"ok": true` and `"errors": []`.

- [ ] **Step 5: Commit renderer and status segment**

Run:

```bash
git add packages/thinking-text-drawer/payloads/09-thinking-bottom-overlay-renderer.js packages/thinking-text-drawer/payloads/10-footer-thinking-status-bar.js packages/thinking-text-drawer/patch.json tests/test_thinking_text_drawer_package.py
git commit -m "feat: render thinking text drawer"
```

---

## Task 8: Build copied binary and run manual smoke

**Files:**
- Modify only if smoke reveals a bug: `packages/thinking-text-drawer/**`, `tests/test_thinking_text_drawer_package.py`

- [ ] **Step 1: Run full package tests**

Run:

```bash
python3 tests/test_hidden_context_drawer_package.py
python3 tests/test_thinking_text_drawer_package.py
```

Expected:

```text
hidden-context drawer package checks passed
thinking-text drawer package checks passed
```

- [ ] **Step 2: Validate package against stock 2.1.201**

Run:

```bash
PYTHONPATH=src python3 -m claude_monkey validate-package \
  --source /Users/MAC/.local/share/claude/versions/2.1.201 \
  --package packages/thinking-text-drawer \
  --source-version 2.1.201 \
  --source-version-output '2.1.201 (Claude Code)' \
  --platform darwin \
  --arch arm64 \
  --json
```

Expected: JSON contains `"ok": true`, `"errors": []`, and planned operation positions for every operation in `patch.json`.

- [ ] **Step 3: Build copied binary**

Run:

```bash
PYTHONPATH=src python3 -m claude_monkey build \
  --source /Users/MAC/.local/share/claude/versions/2.1.201 \
  --package packages/thinking-text-drawer \
  --output-dir /Users/MAC/Documents/Claude-patch/.development/claude-monkey-builds/thinking-text-drawer-2.1.201 \
  --source-version 2.1.201 \
  --source-version-output '2.1.201 (Claude Code)' \
  --platform darwin \
  --arch arm64
```

Expected built binary:

```text
/Users/MAC/Documents/Claude-patch/.development/claude-monkey-builds/thinking-text-drawer-2.1.201/claude
```

- [ ] **Step 4: Manual smoke empty-state drawer**

Run copied binary:

```bash
/Users/MAC/Documents/Claude-patch/.development/claude-monkey-builds/thinking-text-drawer-2.1.201/claude --dangerously-skip-permissions
```

Verify manually:

- Thinking footer item is selectable before any thinking text exists.
- Opening the drawer shows `No thinking captured yet`.
- x closes the drawer.
- Escape does not close the drawer through a package-owned path.
- Normal chat input still works.

- [ ] **Step 5: Manual smoke thinking capture**

In the copied binary, run a prompt/model configuration selected to produce Ctrl-O-visible thinking. Verify:

- Thinking drawer shows structured thinking text without requiring Ctrl-O to be open.
- Ctrl-O still opens transcript mode and still shows thinking there.
- Live thinking text appears before final assistant text when the stream exposes `thinking_delta.thinking`.
- Redacted/estimate-only events are labeled as secondary evidence, not raw thinking.

- [ ] **Step 6: Verify no transcript/request mutation**

Before and after the smoke run, compare the session transcript path and confirm the package did not add drawer-only rows. If a transcript path is available, run:

```bash
python3 - <<'PY'
from pathlib import Path
path = Path(input('transcript path: ').strip())
text = path.read_text(encoding='utf-8')
for forbidden in ['__CODEX_THINKING_TEXT_DRAWER_FRAME_V1__', 'No thinking captured yet', 'thinking-available']:
    assert forbidden not in text, forbidden
print('transcript has no drawer-only markers')
PY
```

Expected: `transcript has no drawer-only markers`.

- [ ] **Step 7: Commit smoke fixes or final package state**

If smoke required fixes, commit them:

```bash
git add packages/thinking-text-drawer tests/test_thinking_text_drawer_package.py
git commit -m "fix: stabilize thinking text drawer smoke"
```

If no fixes were required, do not create an empty commit.

---

## Completion checks

Run before reporting complete:

```bash
git status --short
python3 tests/test_hidden_context_drawer_package.py
python3 tests/test_thinking_text_drawer_package.py
PYTHONPATH=src python3 -m claude_monkey validate-package \
  --source /Users/MAC/.local/share/claude/versions/2.1.201 \
  --package packages/thinking-text-drawer \
  --source-version 2.1.201 \
  --source-version-output '2.1.201 (Claude Code)' \
  --platform darwin \
  --arch arm64 \
  --json
```

Report:

- commits created;
- tests run and exact result;
- validation result;
- copied-binary smoke status;
- any remaining risk around live raw thinking availability.

