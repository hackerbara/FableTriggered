# Thinking Text Drawer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a ClaudeMonkey `thinking-text-drawer` package for Claude Code 2.1.201 that exposes Ctrl-O-visible structured thinking text plus live raw thinking deltas in an always-openable footer drawer without changing main chat rendering, Ctrl-O behavior, request assembly, JSONL history, or model-visible context.

**Architecture:** Create a new standalone direct footer/overlay seam owner. The package writes display-only global frame state from structured assistant content blocks, live `thinking_delta.thinking`, cancellation salvage, `signature_delta`, and `system/thinking_tokens` estimate events. Footer controls use an explicit open-state seam and an action wrapper; they do not reuse hidden-context's `frame.visible` availability gate.

**Tech Stack:** Python package tests, Node-based helper fixture tests, ClaudeMonkey manifest v2 (`replace_exact`), JavaScript payloads patched into `/$bunfs/root/src/entrypoints/cli.js`, graph-aware Bun repack validation.

---

## Exact 2.1.201 anchors

These anchors were checked against `/Users/MAC/.local/share/claude/versions/2.1.201`; each count is exactly `1`. Do not substitute approximate anchors. If any count is not `1` during execution, stop and report that the binary changed.

| Payload | opId | Exact anchor |
|---|---|---|
| `01-thinking-text-helpers.js` | `thinking-helpers-before-ypr` | `function Ypr(e){` |
| `02-live-thinking-delta-collector.js` | `thinking-live-delta-collector` | `case"thinking_delta":{let{delta:d}=e.event;if("estimated_tokens"in d&&typeof d.estimated_tokens==="number")o?.({type:"thinking_progress",estimatedTokensDelta:d.estimated_tokens});else if("thinking"in d&&typeof d.thinking==="string"&&d.thinking.length>0)o?.({type:"thinking_progress",estimatedTokensDelta:Kon(d.thinking)});return}` |
| `03-thinking-signature-collector.js` | `thinking-signature-collector` | `case"signature_delta":o?.({type:"thinking_signature",chars:VVe(e.event.delta.signature.length)});return;` |
| `04-structured-thinking-block-collector.js` | `thinking-structured-block-collector` | `case"redacted_thinking":{if(!p&&!i)return null;let S;if(t[40]!==r)S=Lb.jsx(qRl,{addMargin:r}),t[40]=r,t[41]=S;else S=t[41];return S}case"thinking":{if(!p&&!i)return null;let S;if(t[42]!==r||t[43]!==p||t[44]!==n||t[45]!==i)S=Lb.jsx(wtr,{addMargin:r,param:n,isTranscriptMode:p,verbose:i}),t[42]=r,t[43]=p,t[44]=n,t[45]=i,t[46]=S;else S=t[46];return S}` |
| `05-footer-open-state.js` | `thinking-footer-open-state` | `let[Ss,Ms]=wo.useState(!1),[go,Zo]=wo.useState(!1),[oa,Lu]=wo.useState(!1),[Ec,cn]=wo.useState(!1),[Gn,$n]=wo.useState(!1),[K,ye]=wo.useState(!1),[$e,Xe]=wo.useState(!1),wt=wo.useRef(!1)` |
| `06-footer-target-thinking.js` | `thinking-footer-target` | `ss=wo.useMemo(()=>[Ui&&"tasks",po&&"workflows",Fn&&"tmux",_e&&"bagel",Tr&&"bridge",Ne&&"frame"].filter(Boolean),[Ui,po,Fn,_e,Tr,Ne])` |
| `07-footer-selection-flag.js` | `thinking-footer-selection-flag` | `let lm=Lm==="tasks",ZE=Lm==="workflows",Hd=Lm==="tmux",Zp=Lm==="bagel",AT=Lm==="bridge",Mm=Lm==="frame";function Rp` |
| `08-footer-action-wrap-open.js` | `thinking-footer-action-wrap-open` | `Go({"footer:up":By,"footer:down":d0,"footer:next":o6,"footer:previous":IR,"footer:openSelected":()=>{` |
| `09-footer-action-wrap-close.js` | `thinking-footer-action-wrap-close` | `return!1}},{context:"Footer",isActive:!!Lm&&!se});` |
| `10-selected-overlay-globals.js` | `thinking-selected-overlay-globals` | `return qd.jsxs(B,{flexDirection:"column",marginTop:Vt||dY?0:1,children:[Lm&&!se&&qd.jsx(B,{tabIndex:0,autoFocus:!0,onKeyDown:X8}),!Ys()&&qd.jsx(DTr,{}),J&&` |
| `11-bottom-overlay-renderer.js` | `thinking-bottom-overlay-renderer` | `function Ilc(){let e=MXe.c(2),t=clc();if(!t)return null;let n;if(e[0]!==t)n=Xd.jsx(B,{position:"absolute",bottom:"100%",left:0,right:0,opaque:!0,children:t}),e[0]=t,e[1]=n;else n=e[1];return n}` |
| `12-footer-status-bar.js` | `thinking-footer-status-bar` | `ue=x.map((Me)=>di.jsx(ELc,{link:Me},Me.key??Me.url)),de=[...[]],fe=n?tNf(s,L,W,F,R,O):[];` |
| `13-system-thinking-token-estimate.js` | `thinking-system-token-estimate` | `if(es.type==="system"&&es.subtype==="thinking_tokens"&&"estimated_tokens_delta"in es)continue;` |
| `14-cancel-salvage-collector.js` | `thinking-cancel-salvage-collector` | `let en=_t?.thinking?.trim();if(en&&WAe().thinkingStartedAt!==null)kc((_s)=>[..._s,zT({content:[{type:"thinking",thinking:en,signature:""}],isVirtual:!0})]);` |

---

## File map

Create only these files:

- `packages/thinking-text-drawer/README.md`
- `packages/thinking-text-drawer/patch.json`
- `packages/thinking-text-drawer/payloads/01-thinking-text-helpers.js`
- `packages/thinking-text-drawer/payloads/02-live-thinking-delta-collector.js`
- `packages/thinking-text-drawer/payloads/03-thinking-signature-collector.js`
- `packages/thinking-text-drawer/payloads/04-structured-thinking-block-collector.js`
- `packages/thinking-text-drawer/payloads/05-footer-open-state.js`
- `packages/thinking-text-drawer/payloads/06-footer-target-thinking.js`
- `packages/thinking-text-drawer/payloads/07-footer-selection-flag.js`
- `packages/thinking-text-drawer/payloads/08-footer-action-wrap-open.js`
- `packages/thinking-text-drawer/payloads/09-footer-action-wrap-close.js`
- `packages/thinking-text-drawer/payloads/10-selected-overlay-globals.js`
- `packages/thinking-text-drawer/payloads/11-bottom-overlay-renderer.js`
- `packages/thinking-text-drawer/payloads/12-footer-status-bar.js`
- `packages/thinking-text-drawer/payloads/13-system-thinking-token-estimate.js`
- `packages/thinking-text-drawer/payloads/14-cancel-salvage-collector.js`
- `tests/test_thinking_text_drawer_package.py`

Do not modify:

- `packages/hidden-context-drawer/**`
- ClaudeMonkey patch engine files under `src/claude_monkey/**`
- normal chat renderer behavior outside the display-only seams above

Scratch artifact allowed, not committed:

- `.development/artifacts/claude-2.1.201-thinking-text-drawer-source-module0.js`

---

## Task 1: Add failing package and helper tests

**Files:**
- Create: `tests/test_thinking_text_drawer_package.py`

- [ ] **Step 1: Write the test file**

Create `tests/test_thinking_text_drawer_package.py`:

```python
import hashlib
import json
import subprocess
import textwrap
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


def payloads_text() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted((PACKAGE / "payloads").glob("*.js")))


def test_thinking_text_drawer_targets_claude_2_1_201() -> None:
    manifest = json.loads((PACKAGE / "patch.json").read_text(encoding="utf-8"))
    target = manifest["targets"][0]
    identity = target["sourceIdentity"]
    module = target["modules"][0]

    assert manifest["id"] == "thinking-text-drawer"
    assert identity == {
        "claudeVersion": "2.1.201",
        "versionOutput": "2.1.201 (Claude Code)",
        "sha256": EXPECTED_BINARY_SHA,
        "sizeBytes": EXPECTED_BINARY_SIZE,
        "platform": "darwin",
        "arch": "arm64",
    }
    assert module["path"] == "/$bunfs/root/src/entrypoints/cli.js"
    assert module["contentSha256"] == EXPECTED_MODULE_SHA
    assert module["contentLength"] == EXPECTED_MODULE_LENGTH
    assert len(module["operations"]) == 14

    if LIVE_2_1_201.exists():
        assert hashlib.sha256(LIVE_2_1_201.read_bytes()).hexdigest() == EXPECTED_BINARY_SHA


def test_thinking_text_drawer_overlay_only_and_always_available() -> None:
    text = read_rel("README.md") + "\n" + payloads_text()
    footer_target = read_rel("payloads/06-footer-target-thinking.js")

    assert "No thinking captured yet" in text
    assert "request assembly" in read_rel("README.md")
    assert "JSONL" in read_rel("README.md")
    assert "main chat" in read_rel("README.md")
    assert '"thinking"' in footer_target
    assert "frame.visible" not in footer_target
    assert "__CODEX_THINKING_TEXT_DRAWER_FRAME_V1__" in text
    assert "__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__" in text


def test_thinking_text_drawer_x_only_close_contract() -> None:
    text = payloads_text()
    close_payload = read_rel("payloads/09-footer-action-wrap-close.js")
    renderer = read_rel("payloads/11-bottom-overlay-renderer.js")

    assert "footer:close" in read_rel("payloads/01-thinking-text-helpers.js")
    assert "__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__=!1" in read_rel("payloads/01-thinking-text-helpers.js")
    assert "footer:clearSelection" in read_rel("payloads/01-thinking-text-helpers.js")
    assert "return false" in read_rel("payloads/01-thinking-text-helpers.js")
    assert ",Lm,tDp,Rp)" in close_payload
    assert "x closes" in renderer
    assert "inputOwnsEscape" not in text
    assert "escape" not in renderer.lower()


def test_thinking_text_drawer_collectors_cover_required_sources() -> None:
    helpers = read_rel("payloads/01-thinking-text-helpers.js")
    assert "__codexTTDRecordStructuredThinking" in helpers
    assert "__codexTTDRecordLiveThinking" in helpers
    assert "__codexTTDRecordSalvagedThinking" in helpers
    assert "__codexTTDRecordThinkingSignature" in helpers
    assert "__codexTTDRecordThinkingEstimate" in helpers
    assert "preserve both" in helpers
    assert "slice(0,80)" not in helpers
    assert "Levenshtein" not in helpers


def test_structured_collection_runs_before_ctrl_o_guard() -> None:
    structured = read_rel("payloads/04-structured-thinking-block-collector.js")
    before_guard = structured.split('if(!p&&!i)return null', 1)[0]
    assert "__codexTTDRecordRedactedThinking" in before_guard
    assert "__codexTTDRecordStructuredThinking" in structured
    assert "messageId:g" in structured
    assert "blockHash:__codexTTDContentHash" in structured
    assert "blockIndex:r" not in structured


def test_helper_fixture_merge_and_secondary_sources() -> None:
    helper = read_rel("payloads/01-thinking-text-helpers.js")
    helper_prefix = helper.split("\nfunction Ypr(e){", 1)[0]
    script = textwrap.dedent(
        f"""
        {helper_prefix}
        globalThis.__CODEX_THINKING_TEXT_DRAWER_FRAME_V1__ = undefined;
        __codexTTDRecordLiveThinking({{text:'abc', streamKey:'s1', turnKey:'turn'}});
        __codexTTDRecordLiveThinking({{text:'def', streamKey:'s1', turnKey:'turn'}});
        __codexTTDRecordStructuredThinking({{thinking:'abcdef finalized', messageId:'m1', blockHash:'h1', turnKey:'turn'}});
        __codexTTDRecordRedactedThinking({{messageId:'m2', blockHash:'r1'}});
        __codexTTDRecordThinkingSignature({{chars:128, streamKey:'s1'}});
        __codexTTDRecordThinkingEstimate({{estimatedTokensDelta:7, estimatedTokens:21, streamKey:'s1'}});
        const frame = __codexTTDDrawerFrame();
        if (!frame.entries.some(e => e.source === 'structured' && e.sources.includes('live') && e.text === 'abcdef finalized')) throw new Error('structured/live merge failed');
        if (!frame.entries.some(e => e.source === 'redacted')) throw new Error('redacted marker missing');
        if (!frame.entries.some(e => e.source === 'signature')) throw new Error('signature marker missing');
        if (!frame.entries.some(e => e.source === 'estimate')) throw new Error('estimate marker missing');
        if (frame.entries.length < 4) throw new Error('entries unexpectedly discarded');
        """
    )
    subprocess.run(["node", "-e", script], check=True)


if __name__ == "__main__":
    test_thinking_text_drawer_targets_claude_2_1_201()
    test_thinking_text_drawer_overlay_only_and_always_available()
    test_thinking_text_drawer_x_only_close_contract()
    test_thinking_text_drawer_collectors_cover_required_sources()
    test_structured_collection_runs_before_ctrl_o_guard()
    test_helper_fixture_merge_and_secondary_sources()
    print("thinking-text drawer package checks passed")
```

- [ ] **Step 2: Run the test and verify the initial failure**

Run:

```bash
python3 tests/test_thinking_text_drawer_package.py
```

Expected: `FileNotFoundError` for `packages/thinking-text-drawer/patch.json`.

- [ ] **Step 3: Commit the failing tests**

Run:

```bash
git status --short
git add tests/test_thinking_text_drawer_package.py
git diff --cached --stat
git commit -m "test: add thinking text drawer invariants"
```

---

## Task 2: Scaffold package and write payloads

**Files:**
- Create all files under `packages/thinking-text-drawer/**`

- [ ] **Step 1: Create package directories**

Run:

```bash
mkdir -p packages/thinking-text-drawer/payloads
```

- [ ] **Step 2: Write README**

Write `packages/thinking-text-drawer/README.md`:

````markdown
# Thinking Text Drawer

Projects raw and structured thinking text that Claude Code already has or receives into an integrated footer drawer.

This is a ClaudeMonkey V1.5 package targeting `/$bunfs/root/src/entrypoints/cli.js` with the graph-aware Bun repack engine. It does not patch request assembly, does not mutate transcript JSONL, does not change model-visible context, and does not change the main chat renderer. It is only a pop-up layer the user can open whenever.

The drawer combines:

- structured `thinking` blocks that Ctrl-O transcript mode can already show;
- live `thinking_delta.thinking` chunks when the stream exposes raw text;
- virtual/salvaged thinking blocks created during interruption;
- secondary redacted, signature, and estimated-token markers when raw text is unavailable.

The Thinking footer target is always available while the interactive footer is active. If no thinking has been captured, the drawer opens to `No thinking captured yet`. Captured entries affect unread/flash state, not whether the drawer can be opened.

This package is a standalone direct footer/overlay seam owner for Claude Code 2.1.201. It is expected to conflict with other direct footer drawer packages targeting the same source until structured splices or a reviewed footer-drawer framework exists.

Manual smoke is required: select Thinking from the footer, open it, verify entries or the empty state, scroll, and close with x. Ctrl-O transcript mode must continue to work, and normal chat must remain unchanged.
````

- [ ] **Step 3: Write manifest shell**

Write `packages/thinking-text-drawer/patch.json`:

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
        {"type": "module_must_contain", "modulePath": "/$bunfs/root/src/entrypoints/cli.js", "value": "thinking_delta"},
        {"type": "module_must_contain", "modulePath": "/$bunfs/root/src/entrypoints/cli.js", "value": "case\"thinking\""},
        {"type": "module_must_contain", "modulePath": "/$bunfs/root/src/entrypoints/cli.js", "value": "thinking_tokens"}
      ],
      "postconditions": [
        {"type": "module_must_contain", "modulePath": "/$bunfs/root/src/entrypoints/cli.js", "value": "__CODEX_THINKING_TEXT_DRAWER_FRAME_V1__"},
        {"type": "module_must_contain", "modulePath": "/$bunfs/root/src/entrypoints/cli.js", "value": "No thinking captured yet"},
        {"type": "module_must_contain", "modulePath": "/$bunfs/root/src/entrypoints/cli.js", "value": "__codexTTDRecordSalvagedThinking"}
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

Write `packages/thinking-text-drawer/payloads/01-thinking-text-helpers.js`:

```javascript
function __codexTTDNow(){try{return Date.now()}catch(e){return 0}}
function __codexTTDText(e){return typeof e==="string"?e:""}
function __codexTTDNormalize(e){return __codexTTDText(e).replace(/\s+/g," ").trim()}
function __codexTTDContentHash(e){let t=__codexTTDText(e),n=0;for(let r=0;r<t.length;r++)n=(n*31+t.charCodeAt(r))>>>0;return `${t.length}:${n.toString(16)}`}
function __codexTTDEnsure(){let e=globalThis.__CODEX_THINKING_TEXT_DRAWER_FRAME_V1__;if(!e||typeof e!=="object")e={entries:[],visible:true,unread:false,flashUntil:0,updatedAt:0,scroll:0},globalThis.__CODEX_THINKING_TEXT_DRAWER_FRAME_V1__=e;return e}
function __codexTTDKey(e){return [e.source||"unknown",e.messageId||"",e.requestId||"",e.blockHash||"",e.streamKey||"",e.status||""].join(":")}
function __codexTTDLines(e){let t=__codexTTDText(e).split(/\r?\n/);return t.length>400?[...t.slice(0,400),"… displayed text truncated; captured text preserved in frame entry"]:t}
function __codexTTDUpsert(e){let t=__codexTTDEnsure(),n={...e};n.text=__codexTTDText(n.text);n.charCount=n.text.length;n.key=n.key||__codexTTDKey(n);n.updatedAt=__codexTTDNow();n.sources=Array.isArray(n.sources)?Array.from(new Set(n.sources)):[n.source||"unknown"];n.lines=__codexTTDLines(n.text);let r=t.entries.findIndex(o=>o.key===n.key);if(r>=0)t.entries=[...t.entries.slice(0,r),{...t.entries[r],...n,sources:Array.from(new Set([...(t.entries[r].sources||[]),...n.sources]))},...t.entries.slice(r+1)];else t.entries=[n,...t.entries];t.visible=true;t.unread=true;t.flashUntil=Number.MAX_SAFE_INTEGER;t.updatedAt=n.updatedAt;return t}
function __codexTTDMergeStructured(e){let t=__codexTTDEnsure(),n=__codexTTDNormalize(e.text),r=t.entries.findIndex(o=>o.messageId&&e.messageId&&o.messageId===e.messageId&&o.blockHash&&e.blockHash&&o.blockHash===e.blockHash);if(r<0){let o=t.entries.filter(s=>s.status==="provisional"&&s.turnKey&&e.turnKey&&s.turnKey===e.turnKey);if(o.length===1){let s=__codexTTDNormalize(o[0].text);if(s&&n.includes(s))r=t.entries.indexOf(o[0])}}if(r>=0){let o=t.entries[r],s={...o,...e,text:__codexTTDText(e.text),status:"final",source:"structured",sources:Array.from(new Set([...(o.sources||[]),"live","structured"])),charCount:__codexTTDText(e.text).length,updatedAt:__codexTTDNow()};s.lines=__codexTTDLines(s.text);t.entries=[...t.entries.slice(0,r),s,...t.entries.slice(r+1)];t.visible=true;t.unread=true;t.flashUntil=Number.MAX_SAFE_INTEGER;t.updatedAt=s.updatedAt;return t}return __codexTTDUpsert({...e,source:"structured",status:"final",sources:["structured"]})}
function __codexTTDRecordStructuredThinking(e){let t=__codexTTDText(e?.thinking);if(!t.trim())return;return __codexTTDMergeStructured({source:"structured",status:"final",text:t,messageId:e?.messageId,requestId:e?.requestId,blockHash:e?.blockHash||__codexTTDContentHash(t),turnKey:e?.turnKey,timestamp:e?.timestamp})}
function __codexTTDRecordLiveThinking(e){let t=__codexTTDText(e?.text);if(!t)return;let n=__codexTTDEnsure(),r=e?.streamKey||"active",o=n.entries.find(s=>s.source==="live"&&s.status==="provisional"&&s.streamKey===r),s=o?`${o.text}${t}`:t;return __codexTTDUpsert({source:"live",status:"provisional",text:s,streamKey:r,turnKey:e?.turnKey,requestId:e?.requestId,blockHash:__codexTTDContentHash(s),sources:["live"]})}
function __codexTTDRecordSalvagedThinking(e){let t=__codexTTDText(e?.thinking);if(!t.trim())return;return __codexTTDUpsert({source:"salvaged",status:"final",text:t,messageId:e?.messageId,requestId:e?.requestId,turnKey:e?.turnKey,blockHash:e?.blockHash||__codexTTDContentHash(t),sources:["salvaged"]})}
function __codexTTDRecordRedactedThinking(e){return __codexTTDUpsert({source:"redacted",status:"secondary",text:"[redacted thinking block present]",messageId:e?.messageId,requestId:e?.requestId,blockHash:e?.blockHash||"redacted",turnKey:e?.turnKey,sources:["redacted"]})}
function __codexTTDRecordThinkingSignature(e){let t=typeof e?.chars==="number"?e.chars:0;return __codexTTDUpsert({source:"signature",status:"secondary",text:`thinking signature received (${t} chars)`,streamKey:e?.streamKey,requestId:e?.requestId,blockHash:`signature:${t}`,sources:["signature"]})}
function __codexTTDRecordThinkingEstimate(e){let t=typeof e?.estimatedTokensDelta==="number"?e.estimatedTokensDelta:void 0,n=typeof e?.estimatedTokens==="number"?e.estimatedTokens:void 0;return __codexTTDUpsert({source:"estimate",status:"secondary",text:`thinking active; raw text not exposed${t!==void 0?`, +${t} estimated tokens`:""}${n!==void 0?`, ${n} total estimated`:""}`,streamKey:e?.streamKey,turnKey:e?.turnKey,requestId:e?.requestId,estimatedTokens:n,estimatedTokensDelta:t,blockHash:`estimate:${n??""}:${t??""}`,sources:["estimate"]})}
function __codexTTDDrawerFrame(){let e=__codexTTDEnsure();return{...e,lineCount:e.entries.reduce((t,n)=>t+(n.lines?.length||1),0),entryCount:e.entries.length,empty:e.entries.length===0}}
function __codexTTDWrapFooterActions(e,t,n,r){return{...e,"footer:up":()=>{if(t==="thinking"){let o=__codexTTDEnsure();o.scroll=Math.max(0,(o.scroll||0)-1);globalThis.__CODEX_THINKING_TEXT_DRAWER_SCROLL_V1__=o.scroll;return}return e["footer:up"]?.()},"footer:down":()=>{if(t==="thinking"){globalThis.__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__=!0;n(!0);let o=__codexTTDEnsure();o.scroll=(o.scroll||0)+1;globalThis.__CODEX_THINKING_TEXT_DRAWER_SCROLL_V1__=o.scroll;return}return e["footer:down"]?.()},"footer:openSelected":()=>{if(t==="thinking"){globalThis.__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__=!0;n(!0);return}return e["footer:openSelected"]?.()},"footer:clearSelection":()=>{if(t==="thinking")return false;return e["footer:clearSelection"]?.()},"footer:close":()=>{if(t==="thinking"){globalThis.__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__=!1;n(!1);r(null);return}return e["footer:close"]?.()}}}
// normalized structured text contains the normalized provisional text; otherwise preserve both
function Ypr(e){
```

- [ ] **Step 5: Write collector/control/render payloads**

Write these payload files exactly.

`packages/thinking-text-drawer/payloads/02-live-thinking-delta-collector.js`:

```javascript
case"thinking_delta":{let{delta:d}=e.event;if("thinking"in d&&typeof d.thinking==="string"&&d.thinking.length>0)try{__codexTTDRecordLiveThinking({text:d.thinking,streamKey:e?.event?.index??"active",requestId:e?.request_id})}catch(p){}if("estimated_tokens"in d&&typeof d.estimated_tokens==="number"){try{__codexTTDRecordThinkingEstimate({estimatedTokensDelta:d.estimated_tokens,streamKey:e?.event?.index??"active",requestId:e?.request_id})}catch(p){}o?.({type:"thinking_progress",estimatedTokensDelta:d.estimated_tokens})}else if("thinking"in d&&typeof d.thinking==="string"&&d.thinking.length>0)o?.({type:"thinking_progress",estimatedTokensDelta:Kon(d.thinking)});return}
```

`packages/thinking-text-drawer/payloads/03-thinking-signature-collector.js`:

```javascript
case"signature_delta":try{__codexTTDRecordThinkingSignature({chars:VVe(e.event.delta.signature.length),streamKey:e?.event?.index??"active",requestId:e?.request_id})}catch(d){}o?.({type:"thinking_signature",chars:VVe(e.event.delta.signature.length)});return;
```

`packages/thinking-text-drawer/payloads/04-structured-thinking-block-collector.js`:

```javascript
case"redacted_thinking":{try{__codexTTDRecordRedactedThinking({messageId:g,blockHash:"redacted",turnKey:g})}catch(A){}if(!p&&!i)return null;let S;if(t[40]!==r)S=Lb.jsx(qRl,{addMargin:r}),t[40]=r,t[41]=S;else S=t[41];return S}case"thinking":{try{__codexTTDRecordStructuredThinking({thinking:n?.thinking,messageId:g,blockHash:__codexTTDContentHash(n?.thinking),turnKey:g})}catch(A){}if(!p&&!i)return null;let S;if(t[42]!==r||t[43]!==p||t[44]!==n||t[45]!==i)S=Lb.jsx(wtr,{addMargin:r,param:n,isTranscriptMode:p,verbose:i}),t[42]=r,t[43]=p,t[44]=n,t[45]=i,t[46]=S;else S=t[46];return S}
```

`packages/thinking-text-drawer/payloads/05-footer-open-state.js`:

```javascript
let[Ss,Ms]=wo.useState(!1),[go,Zo]=wo.useState(!1),[oa,Lu]=wo.useState(!1),[Ec,cn]=wo.useState(!1),[Gn,$n]=wo.useState(!1),[K,ye]=wo.useState(!1),[$e,Xe]=wo.useState(!1),[tDo,tDp]=wo.useState(!1),wt=wo.useRef(!1)
```

`packages/thinking-text-drawer/payloads/06-footer-target-thinking.js`:

```javascript
ss=wo.useMemo(()=>[Ui&&"tasks",po&&"workflows",Fn&&"tmux",_e&&"bagel",Tr&&"bridge",Ne&&"frame","thinking"].filter(Boolean),[Ui,po,Fn,_e,Tr,Ne])
```

`packages/thinking-text-drawer/payloads/07-footer-selection-flag.js`:

```javascript
let lm=Lm==="tasks",ZE=Lm==="workflows",Hd=Lm==="tmux",Zp=Lm==="bagel",AT=Lm==="bridge",Mm=Lm==="frame",tD=Lm==="thinking";function Rp
```

`packages/thinking-text-drawer/payloads/08-footer-action-wrap-open.js`:

```javascript
Go(__codexTTDWrapFooterActions({"footer:up":By,"footer:down":d0,"footer:next":o6,"footer:previous":IR,"footer:openSelected":()=>{
```

`packages/thinking-text-drawer/payloads/09-footer-action-wrap-close.js`:

```javascript
return!1},Lm,tDp,Rp),{context:"Footer",isActive:!!Lm&&!se});
```

`packages/thinking-text-drawer/payloads/10-selected-overlay-globals.js`:

```javascript
globalThis.__CODEX_THINKING_TEXT_DRAWER_SELECTED_V1__=!!tD;globalThis.__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__=!!tD&&!!tDo;globalThis.__CODEX_THINKING_TEXT_DRAWER_SCROLL_V1__=__codexTTDEnsure().scroll||0;return qd.jsxs(B,{flexDirection:"column",marginTop:Vt||dY?0:1,children:[Lm&&!se&&qd.jsx(B,{tabIndex:0,autoFocus:!0,onKeyDown:X8}),!Ys()&&qd.jsx(DTr,{}),J&&
```

`packages/thinking-text-drawer/payloads/11-bottom-overlay-renderer.js`:

```javascript
function Ilc(){let e=MXe.c(12),[t,n]=A_.useState(0);A_.useEffect(()=>{let l=setInterval(()=>n(Date.now()),250);return()=>clearInterval(l)},[]);let r=clc(),o=globalThis.__CODEX_THINKING_TEXT_DRAWER_SELECTED_V1__&&globalThis.__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__,s=__codexTTDDrawerFrame(),i=globalThis.__CODEX_THINKING_TEXT_DRAWER_SCROLL_V1__||s.scroll||0;if(o){let a=s.entries.length===0?["No thinking captured yet"]:s.entries.flatMap((c)=>{let u=`${c.source||"thinking"}${c.status?` · ${c.status}`:""}${c.charCount?` · ${c.charCount} chars`:""}`;return[u,...(c.lines&&c.lines.length?c.lines:[c.text||""]),""]}),l=a.slice(i,i+18);return Xd.jsxs(B,{position:"absolute",bottom:"100%",left:0,right:0,opaque:!0,borderStyle:"round",borderColor:"permission",paddingX:1,children:[Xd.jsx(v,{bold:!0,children:" Thinking "}),...l.map((c,u)=>Xd.jsx(v,{wrap:"wrap",dimColor:u===0&&s.entries.length>0,children:c},`thinking-${i+u}`)),Xd.jsx(v,{dimColor:!0,children:"x closes"})]})}if(!r)return null;let a;if(e[0]!==r||e[1]!==t)a=Xd.jsx(B,{position:"absolute",bottom:"100%",left:0,right:0,opaque:!0,children:r}),e[0]=r,e[1]=t,e[2]=a;else a=e[2];return a}
```

`packages/thinking-text-drawer/payloads/12-footer-status-bar.js`:

```javascript
ue=x.map((Me)=>di.jsx(ELc,{link:Me},Me.key??Me.url)),de=[...[]],tDf=__codexTTDDrawerFrame(),tDbar=di.jsx(v,{dimColor:!globalThis.__CODEX_THINKING_TEXT_DRAWER_SELECTED_V1__,color:globalThis.__CODEX_THINKING_TEXT_DRAWER_SELECTED_V1__?"permission":void 0,children:tDf.entryCount>0?`Thinking ${tDf.entryCount}`:"Thinking"},"thinking-available"),fe=n?tNf(s,L,W,F,R,O):[];de.push(tDbar);
```

`packages/thinking-text-drawer/payloads/13-system-thinking-token-estimate.js`:

```javascript
if(es.type==="system"&&es.subtype==="thinking_tokens"&&"estimated_tokens_delta"in es){try{__codexTTDRecordThinkingEstimate({estimatedTokens:es.estimated_tokens,estimatedTokensDelta:es.estimated_tokens_delta,streamKey:es.uuid,requestId:es.request_id})}catch(TN){}continue;}
```

`packages/thinking-text-drawer/payloads/14-cancel-salvage-collector.js`:

```javascript
let en=_t?.thinking?.trim();if(en&&WAe().thinkingStartedAt!==null){try{__codexTTDRecordSalvagedThinking({thinking:en,turnKey:M9.current,requestId:M9.current})}catch(_s){}kc((_s)=>[..._s,zT({content:[{type:"thinking",thinking:en,signature:""}],isVirtual:!0})]);}
```

- [ ] **Step 6: Run tests and verify expected manifest-operation failure**

Run:

```bash
python3 tests/test_thinking_text_drawer_package.py
```

Expected: tests reach the manifest and fail because operation count is still `0`.

- [ ] **Step 7: Commit scaffold and payloads**

Run:

```bash
git status --short
git add packages/thinking-text-drawer tests/test_thinking_text_drawer_package.py
git diff --cached --stat
git commit -m "feat: scaffold thinking text drawer payloads"
```

---

## Task 3: Extract source, verify anchors, and finalize manifest operations

**Files:**
- Modify: `packages/thinking-text-drawer/patch.json`

- [ ] **Step 1: Extract current source module**

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
module = graph.module_by_path('/$bunfs/root/src/entrypoints/cli.js')
out = Path('.development/artifacts/claude-2.1.201-thinking-text-drawer-source-module0.js')
out.parent.mkdir(parents=True, exist_ok=True)
out.write_bytes(module.content)
print(out)
print(len(module.content))
PY
```

Expected:

```text
.development/artifacts/claude-2.1.201-thinking-text-drawer-source-module0.js
18700756
```

- [ ] **Step 2: Verify every exact anchor count is one**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
src = Path('.development/artifacts/claude-2.1.201-thinking-text-drawer-source-module0.js').read_text(encoding='utf-8')
anchors = {
'01': 'function Ypr(e){',
'02': 'case"thinking_delta":{let{delta:d}=e.event;if("estimated_tokens"in d&&typeof d.estimated_tokens==="number")o?.({type:"thinking_progress",estimatedTokensDelta:d.estimated_tokens});else if("thinking"in d&&typeof d.thinking==="string"&&d.thinking.length>0)o?.({type:"thinking_progress",estimatedTokensDelta:Kon(d.thinking)});return}',
'03': 'case"signature_delta":o?.({type:"thinking_signature",chars:VVe(e.event.delta.signature.length)});return;',
'04': 'case"redacted_thinking":{if(!p&&!i)return null;let S;if(t[40]!==r)S=Lb.jsx(qRl,{addMargin:r}),t[40]=r,t[41]=S;else S=t[41];return S}case"thinking":{if(!p&&!i)return null;let S;if(t[42]!==r||t[43]!==p||t[44]!==n||t[45]!==i)S=Lb.jsx(wtr,{addMargin:r,param:n,isTranscriptMode:p,verbose:i}),t[42]=r,t[43]=p,t[44]=n,t[45]=i,t[46]=S;else S=t[46];return S}',
'05': 'let[Ss,Ms]=wo.useState(!1),[go,Zo]=wo.useState(!1),[oa,Lu]=wo.useState(!1),[Ec,cn]=wo.useState(!1),[Gn,$n]=wo.useState(!1),[K,ye]=wo.useState(!1),[$e,Xe]=wo.useState(!1),wt=wo.useRef(!1)',
'06': 'ss=wo.useMemo(()=>[Ui&&"tasks",po&&"workflows",Fn&&"tmux",_e&&"bagel",Tr&&"bridge",Ne&&"frame"].filter(Boolean),[Ui,po,Fn,_e,Tr,Ne])',
'07': 'let lm=Lm==="tasks",ZE=Lm==="workflows",Hd=Lm==="tmux",Zp=Lm==="bagel",AT=Lm==="bridge",Mm=Lm==="frame";function Rp',
'08': 'Go({"footer:up":By,"footer:down":d0,"footer:next":o6,"footer:previous":IR,"footer:openSelected":()=>{',
'09': 'return!1}},{context:"Footer",isActive:!!Lm&&!se});',
'10': 'return qd.jsxs(B,{flexDirection:"column",marginTop:Vt||dY?0:1,children:[Lm&&!se&&qd.jsx(B,{tabIndex:0,autoFocus:!0,onKeyDown:X8}),!Ys()&&qd.jsx(DTr,{}),J&&',
'11': 'function Ilc(){let e=MXe.c(2),t=clc();if(!t)return null;let n;if(e[0]!==t)n=Xd.jsx(B,{position:"absolute",bottom:"100%",left:0,right:0,opaque:!0,children:t}),e[0]=t,e[1]=n;else n=e[1];return n}',
'12': 'ue=x.map((Me)=>di.jsx(ELc,{link:Me},Me.key??Me.url)),de=[...[]],fe=n?tNf(s,L,W,F,R,O):[];',
'13': 'if(es.type==="system"&&es.subtype==="thinking_tokens"&&"estimated_tokens_delta"in es)continue;',
'14': 'let en=_t?.thinking?.trim();if(en&&WAe().thinkingStartedAt!==null)kc((_s)=>[..._s,zT({content:[{type:"thinking",thinking:en,signature:""}],isVirtual:!0})]);',
}
for key, anchor in anchors.items():
    count = src.count(anchor)
    print(key, count)
    if count != 1:
        raise SystemExit(f'anchor {key} count {count}, expected 1')
PY
```

Expected: every line prints `<key> 1` and the command exits `0`.

- [ ] **Step 3: Generate manifest operations from exact anchors and payload hashes**

Run:

```bash
python3 - <<'PY'
import hashlib
import json
from pathlib import Path

source = Path('.development/artifacts/claude-2.1.201-thinking-text-drawer-source-module0.js').read_text(encoding='utf-8')
package = Path('packages/thinking-text-drawer')
manifest_path = package / 'patch.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))

specs = [
('thinking-helpers-before-ypr','Thinking Text Drawer helpers before hidden attachment filter','function Ypr(e){','payloads/01-thinking-text-helpers.js','Adds display-only Thinking drawer helpers and action wrapper.'),
('thinking-live-delta-collector','Record live raw thinking_delta text before progress-only conversion','case"thinking_delta":{let{delta:d}=e.event;if("estimated_tokens"in d&&typeof d.estimated_tokens==="number")o?.({type:"thinking_progress",estimatedTokensDelta:d.estimated_tokens});else if("thinking"in d&&typeof d.thinking==="string"&&d.thinking.length>0)o?.({type:"thinking_progress",estimatedTokensDelta:Kon(d.thinking)});return}','payloads/02-live-thinking-delta-collector.js','Records live raw thinking delta text into display-only drawer state.'),
('thinking-signature-collector','Record thinking signature marker','case"signature_delta":o?.({type:"thinking_signature",chars:VVe(e.event.delta.signature.length)});return;','payloads/03-thinking-signature-collector.js','Records thinking signature events as secondary evidence.'),
('thinking-structured-block-collector','Record structured thinking and redacted blocks before transcript-mode suppression','case"redacted_thinking":{if(!p&&!i)return null;let S;if(t[40]!==r)S=Lb.jsx(qRl,{addMargin:r}),t[40]=r,t[41]=S;else S=t[41];return S}case"thinking":{if(!p&&!i)return null;let S;if(t[42]!==r||t[43]!==p||t[44]!==n||t[45]!==i)S=Lb.jsx(wtr,{addMargin:r,param:n,isTranscriptMode:p,verbose:i}),t[42]=r,t[43]=p,t[44]=n,t[45]=i,t[46]=S;else S=t[46];return S}','payloads/04-structured-thinking-block-collector.js','Records structured thinking before normal-mode rendering suppresses it.'),
('thinking-footer-open-state','Add Thinking drawer React open state','let[Ss,Ms]=wo.useState(!1),[go,Zo]=wo.useState(!1),[oa,Lu]=wo.useState(!1),[Ec,cn]=wo.useState(!1),[Gn,$n]=wo.useState(!1),[K,ye]=wo.useState(!1),[$e,Xe]=wo.useState(!1),wt=wo.useRef(!1)','payloads/05-footer-open-state.js','Adds a local open-state setter used by the footer action wrapper.'),
('thinking-footer-target','Always add Thinking footer target','ss=wo.useMemo(()=>[Ui&&"tasks",po&&"workflows",Fn&&"tmux",_e&&"bagel",Tr&&"bridge",Ne&&"frame"].filter(Boolean),[Ui,po,Fn,_e,Tr,Ne])','payloads/06-footer-target-thinking.js','Makes Thinking selectable even when no entries exist.'),
('thinking-footer-selection-flag','Add Thinking selected flag','let lm=Lm==="tasks",ZE=Lm==="workflows",Hd=Lm==="tmux",Zp=Lm==="bagel",AT=Lm==="bridge",Mm=Lm==="frame";function Rp','payloads/07-footer-selection-flag.js','Publishes a local Thinking selection boolean.'),
('thinking-footer-action-wrap-open','Wrap footer action object open','Go({"footer:up":By,"footer:down":d0,"footer:next":o6,"footer:previous":IR,"footer:openSelected":()=>{','payloads/08-footer-action-wrap-open.js','Starts wrapper around footer actions so Thinking can open/scroll/close without changing stock actions for other targets.'),
('thinking-footer-action-wrap-close','Wrap footer action object close','return!1}},{context:"Footer",isActive:!!Lm&&!se});','payloads/09-footer-action-wrap-close.js','Closes wrapper around footer actions and passes selection/open-state setter.'),
('thinking-selected-overlay-globals','Publish selected/open globals for bottom overlay','return qd.jsxs(B,{flexDirection:"column",marginTop:Vt||dY?0:1,children:[Lm&&!se&&qd.jsx(B,{tabIndex:0,autoFocus:!0,onKeyDown:X8}),!Ys()&&qd.jsx(DTr,{}),J&&','payloads/10-selected-overlay-globals.js','Publishes display-only globals for the bottom overlay renderer.'),
('thinking-bottom-overlay-renderer','Render Thinking drawer in bottom overlay sibling','function Ilc(){let e=MXe.c(2),t=clc();if(!t)return null;let n;if(e[0]!==t)n=Xd.jsx(B,{position:"absolute",bottom:"100%",left:0,right:0,opaque:!0,children:t}),e[0]=t,e[1]=n;else n=e[1];return n}','payloads/11-bottom-overlay-renderer.js','Renders the Thinking drawer when selected/open; otherwise preserves stock overlay.'),
('thinking-footer-status-bar','Add Thinking footer status segment','ue=x.map((Me)=>di.jsx(ELc,{link:Me},Me.key??Me.url)),de=[...[]],fe=n?tNf(s,L,W,F,R,O):[];','payloads/12-footer-status-bar.js','Adds a Thinking footer segment without gating availability on entries.'),
('thinking-system-token-estimate','Record system thinking_tokens as estimate marker','if(es.type==="system"&&es.subtype==="thinking_tokens"&&"estimated_tokens_delta"in es)continue;','payloads/13-system-thinking-token-estimate.js','Records system thinking_tokens as secondary estimate evidence before dropping the event.'),
('thinking-cancel-salvage-collector','Record cancel-salvaged thinking','let en=_t?.thinking?.trim();if(en&&WAe().thinkingStartedAt!==null)kc((_s)=>[..._s,zT({content:[{type:"thinking",thinking:en,signature:""}],isVirtual:!0})]);','payloads/14-cancel-salvage-collector.js','Records interrupted in-flight thinking as salvaged display-only drawer text while preserving stock virtual block behavior.'),
]

ops = []
for op_id, label, exact, path, change in specs:
    if source.count(exact) != 1:
        raise SystemExit(f'{op_id}: anchor count {source.count(exact)}')
    payload = (package / path).read_bytes()
    ops.append({
        'opId': op_id,
        'label': label,
        'type': 'replace_exact',
        'exact': exact,
        'requireWithinRange': [],
        'oldRangeSha256': hashlib.sha256(exact.encode('utf-8')).hexdigest(),
        'oldRangeLength': len(exact.encode('utf-8')),
        'replacement': {'path': path, 'sha256': hashlib.sha256(payload).hexdigest()},
        'knownBehaviorChange': change,
    })
manifest['targets'][0]['modules'][0]['operations'] = ops
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
print(f'wrote {len(ops)} operations')
PY
```

Expected: `wrote 14 operations`.

- [ ] **Step 4: Run tests and validation**

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

Expected: tests pass; validation JSON contains `"ok": true` and `"errors": []`.

- [ ] **Step 5: Commit finalized manifest**

Run:

```bash
git status --short
git add packages/thinking-text-drawer tests/test_thinking_text_drawer_package.py
git diff --cached --stat
git commit -m "feat: pin thinking text drawer anchors"
```

---

## Task 4: Build copied binary and run smoke checks

**Files:**
- Modify only if smoke reveals a bug: `packages/thinking-text-drawer/**`, `tests/test_thinking_text_drawer_package.py`

- [ ] **Step 1: Run package regression tests**

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

- [ ] **Step 2: Inspect and validate target binary**

Run:

```bash
PYTHONPATH=src python3 -m claude_monkey inspect-binary \
  --source /Users/MAC/.local/share/claude/versions/2.1.201 \
  --json
PYTHONPATH=src python3 -m claude_monkey validate-package \
  --source /Users/MAC/.local/share/claude/versions/2.1.201 \
  --package packages/thinking-text-drawer \
  --source-version 2.1.201 \
  --source-version-output '2.1.201 (Claude Code)' \
  --platform darwin \
  --arch arm64 \
  --json
```

Expected: inspect JSON reports module length `18700756` and module sha `46db617a7b13c062fb31595f6244819b11f7cdc6e6fed8e2c3f74a27fb6da1bd`; validation JSON contains `"ok": true` and `"errors": []`.

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

Expected binary:

```text
/Users/MAC/Documents/Claude-patch/.development/claude-monkey-builds/thinking-text-drawer-2.1.201/claude
```

- [ ] **Step 4: Verify build identity and codesign state**

Run:

```bash
shasum -a 256 /Users/MAC/Documents/Claude-patch/.development/claude-monkey-builds/thinking-text-drawer-2.1.201/claude
codesign -dv /Users/MAC/Documents/Claude-patch/.development/claude-monkey-builds/thinking-text-drawer-2.1.201/claude 2>&1 | sed -n '1,20p'
```

Expected: a SHA-256 different from stock 2.1.201 and codesign output that does not indicate an unsigned/truncated binary.

- [ ] **Step 5: Manual smoke empty-state drawer**

Run:

```bash
/Users/MAC/Documents/Claude-patch/.development/claude-monkey-builds/thinking-text-drawer-2.1.201/claude --dangerously-skip-permissions
```

Verify manually:

- Thinking footer item is selectable before any thinking text exists.
- Opening the drawer shows `No thinking captured yet`.
- x closes the drawer.
- Escape does not close the drawer through a package-owned path.
- Normal chat input still works.

- [ ] **Step 6: Manual smoke thinking capture**

In the copied binary, run a prompt/model configuration selected to produce Ctrl-O-visible thinking. Verify:

- Thinking drawer shows structured thinking text without requiring Ctrl-O to be open.
- Ctrl-O still opens transcript mode and still shows thinking there.
- Live thinking text appears before final assistant text when the stream exposes `thinking_delta.thinking`.
- Redacted/signature/estimate-only events are labeled as secondary evidence, not raw thinking.

- [ ] **Step 7: Verify no JSONL/request/model-visible mutation**

Before the smoke prompt, copy the current transcript JSONL file and record its line count. After the smoke prompt, copy the transcript again. Then run:

```bash
python3 - <<'PY'
from pathlib import Path
before = Path(input('before transcript copy: ').strip())
after = Path(input('after transcript copy: ').strip())
b = before.read_text(encoding='utf-8').splitlines()
a = after.read_text(encoding='utf-8').splitlines()
assert len(a) >= len(b)
new = a[len(b):]
for line in new:
    for forbidden in ['__CODEX_THINKING_TEXT_DRAWER_FRAME_V1__', 'No thinking captured yet', 'thinking-available', 'x closes']:
        assert forbidden not in line, forbidden
print(f'checked {len(new)} new transcript lines; no drawer-only markers')
PY
```

Also verify during smoke that no prompt/request preview or model-visible context contains drawer-only strings. If there is no request-preview tool available in the copied binary, report that limitation explicitly and rely on the transcript diff plus code review of payloads showing no request assembly seam is touched.

Expected: no drawer-only markers appear in new transcript lines; no request/model-visible path contains drawer state.

- [ ] **Step 8: Commit smoke fixes or final package state**

If smoke required fixes, run:

```bash
git status --short
git add packages/thinking-text-drawer tests/test_thinking_text_drawer_package.py
git diff --cached --stat
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
PYTHONPATH=src python3 -m claude_monkey inspect-binary \
  --source /Users/MAC/.local/share/claude/versions/2.1.201 \
  --json
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
- test commands and exact results;
- inspect and validation results;
- copied-binary path and smoke status;
- transcript/request mutation check result;
- remaining risk around whether the live stream exposes raw `thinking_delta.thinking` for the chosen model.
