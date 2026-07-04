# Footer Drawers Faithful Spike Port Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the broken synthetic `drawers` framework with a faithful `2.1.201` port of the working spike: real footer targets for Hidden Context, Thinking, and Reminders; stock `footerSelection` as the source of truth; drawer-local open state; no runtime drawer registry.

**Architecture:** `footer-drawers` owns the shared exact seams only: target list, selection flags, action-map wrapping, status-bar real drawer segments, overlay composition, and `space` binding. Drawer packages keep only content/state helpers and explicit panel components; they do not register descriptors. The implementation follows the spike chain: real footer target -> normalized `Lm` -> real-target actions -> drawer-local open state -> bar hint from the same target.

**Tech Stack:** Python 3 / pytest package tests, ClaudeMonkey schema-v2 and v3 package manifests, Bun graph repack structured splices targeting Claude Code `2.1.201`, JavaScript payloads injected into `/$bunfs/root/src/entrypoints/cli.js`.

---

## Source authority

Read these before starting implementation:

- Approved spec: `docs/superpowers/specs/2026-07-04-footer-drawers-faithful-spike-port-spec.md`
- Failure report: `docs/superpowers/reports/2026-07-04-footer-drawers-failure-report.md`
- Known-good spike commit: `9e2ef5811bba0957d7b0a9c31b93d2696f3feded`

Do **not** execute the old unsafe plan at `/Users/MAC/Documents/Claude-patch/docs/superpowers/plans/2026-07-04-footer-drawers-framework.md` except to recover already-verified source identity and raw anchor reconnaissance.

## Target identity

Use one source identity across the stack:

- binary: `/Users/MAC/.local/share/claude/versions/2.1.201`
- version output: `2.1.201 (Claude Code)`
- binary SHA-256: `a0852d76afc47b30f5cb0b7625ec9a7714cb189f2eeef6c28c77e2be954fb7fd`
- binary size: `231708784`
- module path: `/$bunfs/root/src/entrypoints/cli.js`
- module SHA-256: `46db617a7b13c062fb31595f6244819b11f7cdc6e6fed8e2c3f74a27fb6da1bd`
- module length: `18700756`

If the local binary or module differs, stop and ask the user whether to retarget.

## File structure

### Create

- `docs/superpowers/plans/2026-07-04-footer-drawers-faithful-spike-port.md` — this plan.
- `packages/footer-drawers/payloads/01-real-target-helpers-and-overlay.js` — pure real-target action helper plus shared overlay composition; no registry.
- `packages/footer-drawers/payloads/02-footer-hiddencontext-state.js` — adds Hidden Context local scroll/open React state in the footer component.
- `packages/footer-drawers/payloads/03-real-drawer-targets.js` — inserts explicit real drawer targets into `ss` and computes the Hidden Context frame same-render.
- `packages/footer-drawers/payloads/04-real-drawer-selection-flags.js` — adds `HC`, `TT`, `RM` selected flags and mirrors selected/open globals.
- `packages/footer-drawers/payloads/05-real-target-action-wrap-open.js` — opens real-target wrapper around the stock footer action map.
- `packages/footer-drawers/payloads/06-real-target-action-wrap-close.js` — closes real-target wrapper around the stock footer action map.
- `packages/footer-drawers/payloads/07-footer-space-binding.js` — `space` maps to `footer:openSelected`.
- `packages/footer-drawers/payloads/08-status-real-drawer-selection-hooks.js` — status-bar raw real-target selected hooks with structural proof tests.
- `packages/footer-drawers/payloads/09-status-real-drawer-bars.js` — explicit Hidden Context / Thinking / Reminders status segments.
- `packages/footer-drawers/payloads/10-status-shortcuts-condition.js` — keeps drawer segments from being masked by shortcuts hint.
- `packages/footer-drawers/payloads/11-status-null-condition.js` — keeps drawer-only status row visible.
- `packages/footer-drawers/payloads/12-status-render-real-drawer-bars.js` — renders real drawer segments among stock status chunks.
- `packages/hidden-context-drawer/payloads/17-panel-real-target.js` — Hidden Context panel component only; no registration.
- `packages/thinking-text-drawer/payloads/17-panel-real-target.js` — Thinking panel component only; no registration.
- `packages/reminders-manager/payloads/rm-panel-real-target-2.1.201.js` — Reminders panel component only; no registration.
- `tests/test_footer_drawers_faithful_spike_port.py` — architecture/regression tests that fail on the current synthetic implementation.

### Modify

- `packages/footer-drawers/patch.json` — replace synthetic op ids/payloads/postconditions with real-target seam ops and no-registry postconditions.
- `packages/footer-drawers/README.md` — document faithful real-target framework and explicitly ban runtime registries.
- `packages/hidden-context-drawer/patch.json` — delete registration op, add panel op, keep content seams, keep `requiresPackages` if the build expects shared footer seams.
- `packages/hidden-context-drawer/README.md` — document same-render frame + real target behavior.
- `packages/hidden-context-drawer/payloads/01-projection-helpers-before-ypr-2.1.201.js` — remove footer registry bump references.
- `packages/hidden-context-drawer/payloads/02-yt-projection-list-drawer-frame.js` — keep rich pre-filter frame publication.
- `packages/thinking-text-drawer/patch.json` — delete registration op, add panel op, update postconditions to remove registry descriptor strings.
- `packages/thinking-text-drawer/README.md` — document real target extension behavior.
- `packages/thinking-text-drawer/payloads/01-thinking-text-helpers.js` — remove `__CODEX_FOOTER_DRAWERS_V1__` / `openId` checks and add local open/key helpers.
- `packages/reminders-manager/patch.json` — delete registration op, add panel op, update postconditions to remove registry descriptor strings.
- `packages/reminders-manager/README.md` — document spike-shaped Reminders wrapper semantics.
- `packages/reminders-manager/payloads/rm-attachment-wrapper-deny-2.1.201.js` — restore spike-shaped `__codexRMWrapActions(actions, selectedTarget)` wrapper in the helper payload; no framework registry bump.
- Existing tests:
  - `tests/test_footer_drawers_package.py`
  - `tests/test_hidden_context_drawer_package.py`
  - `tests/test_thinking_text_drawer_package.py`
  - `tests/test_reminders_manager.py`

### Delete or leave unreferenced

Remove from manifests and delete files if no other package imports them:

- `packages/footer-drawers/payloads/01-bootstrap-and-overlay.js`
- `packages/footer-drawers/payloads/02-footer-render-tick-state.js`
- `packages/footer-drawers/payloads/03-footer-render-tick-effect.js`
- `packages/footer-drawers/payloads/04-footer-target-drawers.js`
- `packages/footer-drawers/payloads/05-footer-target-deps.js`
- `packages/footer-drawers/payloads/06-footer-selection-flag.js`
- `packages/footer-drawers/payloads/07-footer-action-wrap-open.js`
- `packages/footer-drawers/payloads/08-footer-action-wrap-close.js`
- `packages/footer-drawers/payloads/09-footer-space-binding.js` only if replaced by `07-footer-space-binding.js`
- `packages/footer-drawers/payloads/10-footer-bar-var.js`
- `packages/footer-drawers/payloads/11-footer-bar-shortcuts-condition.js`
- `packages/footer-drawers/payloads/12-footer-bar-null-condition.js`
- `packages/footer-drawers/payloads/13-footer-bar-render.js`
- `packages/footer-drawers/payloads/14-footer-bar-selection-state.js`
- `packages/hidden-context-drawer/payloads/17-register-footer-drawer.js`
- `packages/thinking-text-drawer/payloads/17-register-footer-drawer.js`
- `packages/reminders-manager/payloads/rm-register-footer-drawer-2.1.201.js`

Do not delete content collector/filter payloads unrelated to footer UI.

---

## Task 0: Pre-flight source and anchor proof

**Files:**
- Read: `docs/superpowers/specs/2026-07-04-footer-drawers-faithful-spike-port-spec.md`
- Read/Create: `.development/artifacts/claude-2.1.201-framework-source-module0.js`

- [ ] **Step 1: Confirm you are in the isolated worktree**

Run:

```bash
cd /Users/MAC/.config/superpowers/worktrees/Claude-patch/footer-drawers-framework
pwd
git status --short
git branch --show-current
```

Expected:

```text
/Users/MAC/.config/superpowers/worktrees/Claude-patch/footer-drawers-framework
```

The branch should be `codex/footer-drawers-framework`. Preserve existing untracked spec/report/plan files. Do not clean the worktree.

- [ ] **Step 2: Verify the target binary identity**

Run:

```bash
python3 - <<'PY'
import hashlib
from pathlib import Path
source = Path('/Users/MAC/.local/share/claude/versions/2.1.201')
assert source.exists(), source
raw = source.read_bytes()
print(hashlib.sha256(raw).hexdigest())
print(len(raw))
PY
```

Expected:

```text
a0852d76afc47b30f5cb0b7625ec9a7714cb189f2eeef6c28c77e2be954fb7fd
231708784
```

- [ ] **Step 3: Ensure the module dump exists and matches**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
import hashlib, sys
ROOT = Path('/Users/MAC/.config/superpowers/worktrees/Claude-patch/footer-drawers-framework')
out = ROOT / '.development' / 'artifacts' / 'claude-2.1.201-framework-source-module0.js'
if not out.exists():
    sys.path.insert(0, str(ROOT / 'src'))
    from claude_monkey.macho import find_macho_layout
    from claude_monkey.bun_graph import parse_bun_section
    source = Path('/Users/MAC/.local/share/claude/versions/2.1.201')
    raw = source.read_bytes()
    layout = find_macho_layout(raw)
    section = raw[layout.bun_section.offset:layout.bun_section.offset + layout.bun_section.size]
    graph = parse_bun_section(section)
    module = graph.module_by_path('/$bunfs/root/src/entrypoints/cli.js')
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(module.content)
data = out.read_bytes()
print(hashlib.sha256(data).hexdigest())
print(len(data))
PY
```

Expected:

```text
46db617a7b13c062fb31595f6244819b11f7cdc6e6fed8e2c3f74a27fb6da1bd
18700756
```

- [ ] **Step 4: Verify the approved `2.1.201` anchors resolve exactly once**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
src = Path('.development/artifacts/claude-2.1.201-framework-source-module0.js').read_text()
anchors = {
    'footer_state_ref': 'wt=wo.useRef(!1)',
    'footer_targets': 'ss=wo.useMemo(()=>[Ui&&"tasks",po&&"workflows",Fn&&"tmux",_e&&"bagel",Tr&&"bridge",Ne&&"frame"].filter(Boolean),[Ui,po,Fn,_e,Tr,Ne])',
    'selection_flags': 'let lm=Lm==="tasks",ZE=Lm==="workflows",Hd=Lm==="tmux",Zp=Lm==="bagel",AT=Lm==="bridge",Mm=Lm==="frame";',
    'action_open': 'Go({"footer:up":By,"footer:down":d0,"footer:next":o6,"footer:previous":IR,"footer:openSelected":()=>{',
    'action_close': 'return!1}},{context:"Footer",isActive:!!Lm&&!se});',
    'footer_binding': '{context:"Footer",bindings:{up:"footer:up","ctrl+p":"footer:up",down:"footer:down","ctrl+n":"footer:down",right:"footer:next",left:"footer:previous",enter:"footer:openSelected",escape:"footer:clearSelection",x:"footer:close"}}',
    'status_selected_hook': 'k=Tt((Me)=>!1)',
    'status_bar_var': 'ue=x.map((Me)=>di.jsx(ELc,{link:Me},Me.key??Me.url)),de=[...[]],fe=n?tNf(s,L,W,F,R,O):[];',
    'status_shortcuts_condition': 'if(de.length===0&&!we&&!le&&!ie&&ue.length===0&&!ve&&n)',
    'status_null_condition': 'if(de.length===0&&!we&&!le&&!ce&&!ie&&ue.length===0&&!ve)return Ys()?di.jsx(v,{children:" "}):null;',
    'status_render': 'ue.length>0&&di.jsxs(B,{flexShrink:0,children:[di.jsx(qn,{children:ue}),(we||de.length>0)&&di.jsx(v,{dimColor:!0,children:" \\xB7 "})]}),we&&di.jsxs(B,{flexShrink:0,children:[we,de.length>0&&di.jsx(v,{dimColor:!0,children:" \\xB7 "})]}),de.length>0&&di.jsx(v,{wrap:"truncate",children:di.jsx(qn,{children:de})})',
    'overlay': 'function Ilc(){let e=MXe.c(2),t=clc();if(!t)return null;let n;if(e[0]!==t)n=Xd.jsx(B,{position:"absolute",bottom:"100%",left:0,right:0,opaque:!0,children:t}),e[0]=t,e[1]=n;else n=e[1];return n}',
}
for name, needle in anchors.items():
    count = src.count(needle)
    print(name, count)
    assert count == 1, (name, count)
PY
```

Expected: every anchor prints count `1`.

- [ ] **Step 5: Commit nothing**

This task is read-only except for creating the module dump if absent.

---

## Task 1: Add failing architecture tests for the faithful spike port

**Files:**
- Create: `tests/test_footer_drawers_faithful_spike_port.py`
- Modify later: existing package tests listed in later tasks

- [ ] **Step 1: Create the failing regression test file**

Create `tests/test_footer_drawers_faithful_spike_port.py` with this content:

```python
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from claude_monkey.bun_graph import parse_bun_section
from claude_monkey.builder_v15 import BuildRequestV15, build_patchset_v15, load_manifest_v2
from claude_monkey.macho import find_macho_layout

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = "/$bunfs/root/src/entrypoints/cli.js"
SOURCE = Path("/Users/MAC/.local/share/claude/versions/2.1.201")
MODULE_DUMP = ROOT / ".development" / "artifacts" / "claude-2.1.201-framework-source-module0.js"
FOOTER = ROOT / "packages" / "footer-drawers"
HC = ROOT / "packages" / "hidden-context-drawer"
THINKING = ROOT / "packages" / "thinking-text-drawer"
REMINDERS = ROOT / "packages" / "reminders-manager"

EXPECTED_SOURCE_SHA = "a0852d76afc47b30f5cb0b7625ec9a7714cb189f2eeef6c28c77e2be954fb7fd"
EXPECTED_SOURCE_SIZE = 231708784
EXPECTED_MODULE_SHA = "46db617a7b13c062fb31595f6244819b11f7cdc6e6fed8e2c3f74a27fb6da1bd"
EXPECTED_MODULE_LENGTH = 18700756

FORBIDDEN_RUNTIME_NEEDLES = [
    '"drawers"',
    'footerSelection==="drawers"',
    'footerSelection === "drawers"',
    'id:"drawers"',
    'id: "drawers"',
    '__CODEX_FOOTER_DRAWERS_V1__',
    '__codexFDDrawers',
    '__codexFDRegister',
    '__codexFDLand',
    '__codexFDMove',
    'hoverId',
    'openId',
]

REGISTRATION_PAYLOADS = [
    HC / "payloads" / "17-register-footer-drawer.js",
    THINKING / "payloads" / "17-register-footer-drawer.js",
    REMINDERS / "payloads" / "rm-register-footer-drawer-2.1.201.js",
]


def _manifest(package_dir: Path):
    return load_manifest_v2(package_dir)


def _all_payload_text() -> str:
    parts: list[str] = []
    for package_dir in [FOOTER, HC, THINKING, REMINDERS]:
        for path in sorted((package_dir / "payloads").glob("*.js")):
            parts.append(f"\n/* {path.relative_to(ROOT)} */\n")
            parts.append(path.read_text(encoding="utf-8"))
    return "".join(parts)


def _source_or_skip() -> Path:
    if not SOURCE.exists():
        pytest.skip(f"missing local Claude source: {SOURCE}")
    raw = SOURCE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != EXPECTED_SOURCE_SHA:
        pytest.skip("local Claude source SHA differs from approved 2.1.201 identity")
    if len(raw) != EXPECTED_SOURCE_SIZE:
        pytest.skip("local Claude source size differs from approved 2.1.201 identity")
    return SOURCE


def _module_text_from_binary(binary: Path) -> str:
    raw = binary.read_bytes()
    layout = find_macho_layout(raw)
    section = raw[layout.bun_section.offset:layout.bun_section.offset + layout.bun_section.size]
    graph = parse_bun_section(section)
    module = graph.module_by_path(MODULE_PATH)
    return module.content.decode("utf-8")


def _build_full_stack(tmp_path: Path) -> str:
    source = _source_or_skip()
    request = BuildRequestV15(
        source_path=source,
        output_dir=tmp_path / "claude-footer-real-targets",
        package_dirs=[FOOTER, HC, THINKING, REMINDERS],
        source_version="2.1.201",
        source_version_output="2.1.201 (Claude Code)",
        platform="darwin",
        arch="arm64",
    )
    report = build_patchset_v15(request)
    assert report.failureReason is None, report.failureReason
    assert report.automatedStatus == "passed"
    assert report.status == "manual_smoke_pending"
    assert report.outputPath is not None
    return _module_text_from_binary(Path(report.outputPath))


def test_source_identity_constants_match_approved_spec() -> None:
    assert SOURCE.exists()
    raw = SOURCE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EXPECTED_SOURCE_SHA
    assert len(raw) == EXPECTED_SOURCE_SIZE
    if MODULE_DUMP.exists():
        dump = MODULE_DUMP.read_bytes()
        assert hashlib.sha256(dump).hexdigest() == EXPECTED_MODULE_SHA
        assert len(dump) == EXPECTED_MODULE_LENGTH


def test_payloads_and_manifests_contain_no_runtime_registry_or_synthetic_drawers() -> None:
    text = _all_payload_text()
    for needle in FORBIDDEN_RUNTIME_NEEDLES:
        assert needle not in text
    for descriptor_field in ["available:", "onOpen:", "onClose:", "onKey:", "renderPanel:"]:
        assert descriptor_field not in text
    for path in REGISTRATION_PAYLOADS:
        assert not path.exists(), f"delete or replace bad registrant payload: {path}"


def test_footer_manifest_owns_real_target_seams_not_registry_lifecycle() -> None:
    manifest = _manifest(FOOTER)
    op_ids = {op.op_id for target in manifest.targets for module in target.modules for op in module.operations}
    assert op_ids == {
        "fd-real-target-helpers-and-overlay",
        "fd-footer-hiddencontext-state",
        "fd-real-drawer-targets",
        "fd-real-drawer-selection-flags",
        "fd-real-target-action-wrap-open",
        "fd-real-target-action-wrap-close",
        "fd-footer-space-binding",
        "fd-status-real-drawer-selection-hooks",
        "fd-status-real-drawer-bars",
        "fd-status-shortcuts-condition",
        "fd-status-null-condition",
        "fd-status-render-real-drawer-bars",
    }
    postconditions = {pc.value for target in manifest.targets for pc in target.postconditions}
    assert "__CODEX_FOOTER_DRAWERS_V1__" not in postconditions
    assert "__codexFDWrapActions" not in postconditions
    assert '"drawers"' not in postconditions


def test_drawer_packages_no_longer_ship_descriptor_registrants() -> None:
    for package_dir in [HC, THINKING, REMINDERS]:
        manifest = _manifest(package_dir)
        op_ids = {op.op_id for target in manifest.targets for module in target.modules for op in module.operations}
        assert all("register-footer-drawer" not in op_id for op_id in op_ids)
        assert all("register" not in op_id or "drawer" not in op_id for op_id in op_ids)
    assert "__codexTTDRegisterFooterDrawer" not in _all_payload_text()
    assert "__codexNCHCRegisterFooterDrawer" not in _all_payload_text()
    assert "__codexRMRegisterFooterDrawer" not in _all_payload_text()


def test_full_stack_composed_module_uses_real_targets_and_rejects_prior_failure_mode(tmp_path: Path) -> None:
    module = _build_full_stack(tmp_path)
    for needle in FORBIDDEN_RUNTIME_NEEDLES:
        assert needle not in module
    assert '__CODEX_FOOTER_DRAWERS_V1__' not in module
    assert '"hiddenContext"' in module
    assert '"thinking"' in module
    assert '"reminders"' in module
    target_idx = module.index('__codexHiddenContextFrame?.visible&&"hiddenContext"')
    tasks_idx = module.index('Ui&&"tasks"', target_idx)
    assert target_idx < tasks_idx
    assert 'TT=Lm==="thinking"' in module or 'Lm==="thinking"' in module
    assert 'RM=Lm==="reminders"' in module or 'Lm==="reminders"' in module
    assert '__codexRMWrapActions' in module
    assert 'if(t!=="reminders")return e' in module
    assert '__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__' in module
    assert '__CODEX_THINKING_TEXT_DRAWER_SELECTED_V1__' in module
    assert '__CODEX_THINKING_TEXT_DRAWER_SELECTED_V1__===!0&&globalThis.__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__===!0' in module


def test_hidden_context_target_construction_is_same_render_frame_not_global_callback(tmp_path: Path) -> None:
    module = _build_full_stack(tmp_path)
    assert 'available:()=>!!globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_FRAME_V13__?.visible' not in module
    assert '__codexHiddenContextFrame=typeof __codexNCHCDrawerFrameFromList==="function"?__codexNCHCDrawerFrameFromList(d.current):null' in module
    assert '__codexHiddenContextFrame?.visible&&"hiddenContext"' in module
    assert '__codexHiddenContextFrame?.generation' in module


def test_status_bar_is_explicit_real_segments_not_synthetic_toolbar(tmp_path: Path) -> None:
    module = _build_full_stack(tmp_path)
    assert 'FDbar=__codexFDAvailable' not in module
    assert '__codexFDBar(' not in module
    assert 'footerSelection==="hiddenContext"' in module
    assert 'footerSelection==="thinking"' in module
    assert 'footerSelection==="reminders"' in module
    assert '"Hidden Context "' in module
    assert '"Thinking"' in module
    assert '"Reminders"' in module
    assert '" (enter)"' in module
    assert '" \\u2192"' in module
    assert '3/7' not in module
```

- [ ] **Step 2: Run the new tests and confirm they fail on the current implementation**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_footer_drawers_faithful_spike_port.py -q
```

Expected now: failures mentioning current synthetic registry/descriptor strings such as `__CODEX_FOOTER_DRAWERS_V1__`, `hoverId`, `openId`, or bad `*-register-footer-drawer*` payloads.

- [ ] **Step 3: Commit nothing yet**

This is the red phase. Do not commit until implementation makes the tests pass.

---

## Task 2: Replace `footer-drawers` with real-target seam payloads

**Files:**
- Modify: `packages/footer-drawers/patch.json`
- Modify: `packages/footer-drawers/README.md`
- Create/delete payloads listed in File Structure
- Test: `tests/test_footer_drawers_faithful_spike_port.py`, `tests/test_footer_drawers_package.py`

- [ ] **Step 1: Replace the bootstrap/overlay payload with pure real-target helper code**

Create `packages/footer-drawers/payloads/01-real-target-helpers-and-overlay.js` with this content:

```js
function __codexFDHiddenContextScroll(e,t){let n=t?.frame;if(!n?.lines||!t?.setScroll)return!1;let r=Math.max(4,Number(t.viewport)||18),o=Math.max(0,(n.lines?.length??1)-r),s=Math.max(0,Math.min(o,(Number(t.scroll)||0)+e));try{if(n)n.flashUntil=0;t.setScroll(s);globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_SCROLL_V13__=s}catch{}return!0}function __codexFDOpenThinking(){try{globalThis.__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__=!0;globalThis.__CODEX_THINKING_TEXT_DRAWER_SELECTED_V1__=!0;if(typeof __codexTTDMarkRead==="function")__codexTTDMarkRead()}catch{}return!0}function __codexFDCloseThinking(){try{globalThis.__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__=!1}catch{}return!0}function __codexFDThinkingKey(e){try{if(typeof __codexTTDDrawerFrame!=="function"||typeof __codexTTDClampScroll!=="function")return!1;let t=__codexTTDDrawerFrame(),n=globalThis.__CODEX_THINKING_TEXT_DRAWER_VIEWPORT_V1__||18;if(e==="up"){__codexTTDClampScroll((t.scroll||0)-3,t.lineCount,n);return!0}if(e==="down"){__codexTTDClampScroll((t.scroll||0)+3,t.lineCount,n);return!0}}catch{}return!1}function __codexFDWrapRealTargetActions(e,t,n,r){if(t==="reminders"&&typeof __codexRMWrapActions==="function")return __codexRMWrapActions(e,t);let o={...e};o["footer:up"]=()=>{if(t==="hiddenContext"&&r?.hiddenOpen&&__codexFDHiddenContextScroll(-3,r))return;if(t==="thinking"&&globalThis.__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__===!0&&__codexFDThinkingKey("up"))return;return e["footer:up"]?.()};o["footer:down"]=()=>{if(t==="hiddenContext"&&r?.hiddenOpen&&__codexFDHiddenContextScroll(3,r))return;if(t==="thinking"&&globalThis.__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__===!0&&__codexFDThinkingKey("down"))return;return e["footer:down"]?.()};o["footer:openSelected"]=()=>{if(t==="hiddenContext"){try{globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_OPEN_V13__=!0;if(r?.frame)r.frame.flashUntil=0;r?.setHiddenOpen?.(!0)}catch{}return}if(t==="thinking")return __codexFDOpenThinking();return e["footer:openSelected"]?.()};o["footer:clearSelection"]=()=>{if(t==="hiddenContext"&&r?.hiddenOpen)return!1;if(t==="thinking"&&globalThis.__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__===!0)return!1;return e["footer:clearSelection"]?.()};o["footer:close"]=()=>{if(t==="hiddenContext"&&r?.hiddenOpen){try{globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_OPEN_V13__=!1;r?.setHiddenOpen?.(!1);n?.(null)}catch{}return}if(t==="thinking"&&globalThis.__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__===!0){__codexFDCloseThinking();n?.(null);return}return e["footer:close"]?.()};return o}function Ilc(){let e=MXe.c(6),t=clc(),n=typeof __codexNCHCPanel==="function"?Xd.jsx(__codexNCHCPanel,{}):null,r=typeof __codexTTDPanel==="function"?Xd.jsx(__codexTTDPanel,{}):null,o=typeof __codexRMPanel==="function"?Xd.jsx(__codexRMPanel,{}):null;if(!t&&!n&&!r&&!o)return null;let s;if(e[0]!==t||e[1]!==n||e[2]!==r||e[3]!==o)s=Xd.jsx(B,{position:"absolute",bottom:"100%",left:0,right:0,opaque:!0,flexDirection:"column",children:Xd.jsxs(Xd.Fragment,{children:[n,r,o,t]})}),e[0]=t,e[1]=n,e[2]=r,e[3]=o,e[4]=s;else s=e[4];return s}
```

This file intentionally has no `__CODEX_FOOTER_DRAWERS_V1__`, `hoverId`, `openId`, descriptor registration, or generic callback table.

- [ ] **Step 2: Add Hidden Context local state in the footer component**

Create `packages/footer-drawers/payloads/02-footer-hiddencontext-state.js`:

```js
wt=wo.useRef(!1),[FDhCi,FDhCs]=wo.useState(0),[FDhCo,FDhCp]=wo.useState(!1)
```

This replaces the same stock `wt=wo.useRef(!1)` seam used by the broken `FDv` polling state. It restores local drawer state instead of a global render-tick registry.

- [ ] **Step 3: Add explicit real targets and same-render Hidden Context frame**

Create `packages/footer-drawers/payloads/03-real-drawer-targets.js`:

```js
Ui=Aa>0||Di,po=no.length>0&&_==="prompt"&&!Oe.show&&!Wn,FDhCh=Math.max(6,Math.min(Math.floor(fn*2/3),Math.max(6,fn-10))),FDhCv=Math.max(4,FDhCh-5),__codexHiddenContextFrame=typeof __codexNCHCDrawerFrameFromList==="function"?__codexNCHCDrawerFrameFromList(d.current):null,ss=wo.useMemo(()=>[__codexHiddenContextFrame?.visible&&"hiddenContext",typeof __codexTTDEnsure==="function"&&"thinking",typeof __codexRMState==="function"&&"reminders",Ui&&"tasks",po&&"workflows",Fn&&"tmux",_e&&"bagel",Tr&&"bridge",Ne&&"frame"].filter(Boolean),[Ui,po,Fn,_e,Tr,Ne,__codexHiddenContextFrame?.generation])
```

This is the core seam. It inserts real target ids and computes Hidden Context frame before target construction.

- [ ] **Step 4: Add real selected flags and mirror drawer-local selected/open globals**

Create `packages/footer-drawers/payloads/04-real-drawer-selection-flags.js`:

```js
HC=Lm==="hiddenContext",TT=Lm==="thinking",RM=Lm==="reminders",lm=Lm==="tasks",ZE=Lm==="workflows",Hd=Lm==="tmux",Zp=Lm==="bagel",AT=Lm==="bridge",Mm=Lm==="frame";globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_SELECTED_V13__=HC;globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_FRAME_V13__=__codexHiddenContextFrame;globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_OPEN_V13__=HC&&FDhCo;globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_SCROLL_V13__=FDhCi;globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_SET_SCROLL_V13__=FDhCs;globalThis.__CODEX_THINKING_TEXT_DRAWER_SELECTED_V1__=TT;globalThis.__CODEX_REMINDERS_SELECTED_V1__=RM
```

The globals here are mirrors of real selected/local state, not a registry. They are allowed because panel components live outside the prompt function and need the same selected/open facts.

- [ ] **Step 5: Wrap the footer action map by real selected target**

Create `packages/footer-drawers/payloads/05-real-target-action-wrap-open.js`:

```js
Go(__codexFDWrapRealTargetActions({"footer:up":By,"footer:down":d0,"footer:next":o6,"footer:previous":IR,"footer:openSelected":()=>{
```

Create `packages/footer-drawers/payloads/06-real-target-action-wrap-close.js`:

```js
return!1}},Lm,Rp,{hiddenOpen:FDhCo,setHiddenOpen:FDhCp,frame:__codexHiddenContextFrame,setScroll:FDhCs,scroll:FDhCi,viewport:FDhCv}),{context:"Footer",isActive:!!Lm&&!se});
```

This wrapper dispatches only from real `Lm`. It preserves Reminders by delegating to the spike-shaped `__codexRMWrapActions(actions, Lm)` when `Lm === "reminders"`.

- [ ] **Step 6: Add the space binding**

Create `packages/footer-drawers/payloads/07-footer-space-binding.js`:

```js
{context:"Footer",bindings:{up:"footer:up","ctrl+p":"footer:up",down:"footer:down","ctrl+n":"footer:down",right:"footer:next",left:"footer:previous",enter:"footer:openSelected",space:"footer:openSelected",escape:"footer:clearSelection",x:"footer:close"}}
```

- [ ] **Step 7: Add explicit real-target status-bar selection hooks**

Create `packages/footer-drawers/payloads/08-status-real-drawer-selection-hooks.js`:

```js
k=Tt((Me)=>!1),FDhSel=Tt((Me)=>Me.footerSelection==="hiddenContext"),FDtSel=Tt((Me)=>Me.footerSelection==="thinking"),FDrSel=Tt((Me)=>Me.footerSelection==="reminders")
```

The test file added in Task 1 proves these raw hooks are real target ids present in the target list, not a stale synthetic state.

- [ ] **Step 8: Add explicit status-bar segments**

Create `packages/footer-drawers/payloads/09-status-real-drawer-bars.js`:

```js
ue=x.map((Me)=>di.jsx(ELc,{link:Me},Me.key??Me.url)),de=[...[]],FDhCf=globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_FRAME_V13__,FDhFlash=!FDhSel&&Date.now()<(FDhCf?.flashUntil??0),FDhBar=FDhCf?.visible?FDhFlash?di.jsxs(v,{color:"white",backgroundColor:"blue",children:["Hidden Context ",FDhCf?.tokenCount??0,"t"]},"fd-hidden-context"):di.jsxs(O1f,{selected:FDhSel,children:["Hidden Context ",FDhCf?.tokenCount??0,"t",FDhSel?" (enter)":" \\u2192"]},"fd-hidden-context"):null,FDtBar=typeof __codexTTDEnsure==="function"?di.jsx(O1f,{selected:FDtSel,children:["Thinking",FDtSel?" (enter)":" \\u2192"]},"fd-thinking"):null,FDrBar=typeof __codexRMState==="function"?di.jsx(O1f,{selected:FDrSel,children:["Reminders",FDrSel?" (enter)":" \\u2192"]},"fd-reminders"):null,FDdrawerBars=[FDhBar,FDtBar,FDrBar].filter(Boolean),fe=n?tNf(s,L,W,F,R,O):[];
```

Do not add Hidden Context event counts or Reminders suppression counts here.

- [ ] **Step 9: Adjust status-bar visibility and render seams**

Create `packages/footer-drawers/payloads/10-status-shortcuts-condition.js`:

```js
if(de.length===0&&FDdrawerBars.length===0&&!we&&!le&&!ie&&ue.length===0&&!ve&&n)
```

Create `packages/footer-drawers/payloads/11-status-null-condition.js`:

```js
if(de.length===0&&FDdrawerBars.length===0&&!we&&!le&&!ce&&!ie&&ue.length===0&&!ve)return Ys()?di.jsx(v,{children:" "}):null;
```

Create `packages/footer-drawers/payloads/12-status-render-real-drawer-bars.js`:

```js
ue.length>0&&di.jsxs(B,{flexShrink:0,children:[di.jsx(qn,{children:ue}),(we||FDdrawerBars.length>0||de.length>0)&&di.jsx(v,{dimColor:!0,children:" \\xB7 "})]}),we&&di.jsxs(B,{flexShrink:0,children:[we,(FDdrawerBars.length>0||de.length>0)&&di.jsx(v,{dimColor:!0,children:" \\xB7 "})]}),FDdrawerBars.length>0&&di.jsxs(B,{flexShrink:0,children:[di.jsx(qn,{children:FDdrawerBars}),de.length>0&&di.jsx(v,{dimColor:!0,children:" \\xB7 "})]}),de.length>0&&di.jsx(v,{wrap:"truncate",children:di.jsx(qn,{children:de})})
```

- [ ] **Step 10: Update `packages/footer-drawers/patch.json` operation ids and postconditions**

Replace the old operation set with these op ids, each pointing at the new payload file from this task:

```json
[
  "fd-real-target-helpers-and-overlay",
  "fd-footer-hiddencontext-state",
  "fd-real-drawer-targets",
  "fd-real-drawer-selection-flags",
  "fd-real-target-action-wrap-open",
  "fd-real-target-action-wrap-close",
  "fd-footer-space-binding",
  "fd-status-real-drawer-selection-hooks",
  "fd-status-real-drawer-bars",
  "fd-status-shortcuts-condition",
  "fd-status-null-condition",
  "fd-status-render-real-drawer-bars"
]
```

Use the exact anchors from Task 0. The overlay op still replaces the full stock `function Ilc(){let e=MXe.c(2),t=clc();...}` anchor from Task 0. The target op replaces the full stock `Ui=Aa>0||Di,po=no.length>0&&_==="prompt"&&!Oe.show&&!Wn,ss=wo.useMemo(...)` statement:

```text
Ui=Aa>0||Di,po=no.length>0&&_==="prompt"&&!Oe.show&&!Wn,ss=wo.useMemo(()=>[Ui&&"tasks",po&&"workflows",Fn&&"tmux",_e&&"bagel",Tr&&"bridge",Ne&&"frame"].filter(Boolean),[Ui,po,Fn,_e,Tr,Ne])
```

Postconditions must include:

```json
[
  {"type":"module_must_contain","modulePath":"/$bunfs/root/src/entrypoints/cli.js","value":"__codexFDWrapRealTargetActions"},
  {"type":"module_must_contain","modulePath":"/$bunfs/root/src/entrypoints/cli.js","value":"__codexHiddenContextFrame?.visible&&\"hiddenContext\""},
  {"type":"module_must_contain","modulePath":"/$bunfs/root/src/entrypoints/cli.js","value":"typeof __codexTTDEnsure===\"function\"&&\"thinking\""},
  {"type":"module_must_contain","modulePath":"/$bunfs/root/src/entrypoints/cli.js","value":"typeof __codexRMState===\"function\"&&\"reminders\""},
  {"type":"module_must_contain","modulePath":"/$bunfs/root/src/entrypoints/cli.js","value":"space:\"footer:openSelected\""},
  {"type":"module_must_contain","modulePath":"/$bunfs/root/src/entrypoints/cli.js","value":"FDdrawerBars=[FDhBar,FDtBar,FDrBar].filter(Boolean)"}
]
```

Do not include postconditions for `__CODEX_FOOTER_DRAWERS_V1__`, `__codexFDDrawers`, `__codexFDWrapActions`, or `"drawers"`.

- [ ] **Step 11: Recompute payload hashes and old range hashes**

Run this script after editing `patch.json` paths/anchors:

```bash
python3 - <<'PY'
import hashlib, json
from pathlib import Path
ROOT = Path('/Users/MAC/.config/superpowers/worktrees/Claude-patch/footer-drawers-framework')
manifest_path = ROOT / 'packages' / 'footer-drawers' / 'patch.json'
module_text = (ROOT / '.development' / 'artifacts' / 'claude-2.1.201-framework-source-module0.js').read_text()
manifest = json.loads(manifest_path.read_text())
for module in manifest['targets'][0]['modules']:
    for op in module['operations']:
        payload_path = ROOT / 'packages' / 'footer-drawers' / op['replacement']['path']
        op['replacement']['sha256'] = hashlib.sha256(payload_path.read_bytes()).hexdigest()
        if op['type'] == 'replace_exact':
            exact = op['exact']
            assert module_text.count(exact) == 1, (op['opId'], module_text.count(exact))
            op['oldRangeLength'] = len(exact.encode())
            op['oldRangeSha256'] = hashlib.sha256(exact.encode()).hexdigest()
        elif op['type'] == 'replace_substring_within':
            start = module_text.index(op['startMarker'])
            end = module_text.index(op['endMarker'], start)
            window = module_text[start:end]
            assert window.count(op['subExact']) == op['expectedSubExactCount'], op['opId']
            op['oldRangeLength'] = len(op['subExact'].encode())
            op['oldRangeSha256'] = hashlib.sha256(op['subExact'].encode()).hexdigest()
        elif op['type'] in {'insert_before','insert_after'}:
            assert module_text.count(op['anchor']) == op['expectedAnchorCount'], op['opId']
        else:
            raise AssertionError(op['type'])
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
PY
```

- [ ] **Step 12: Run focused footer-drawers tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_footer_drawers_faithful_spike_port.py::test_footer_manifest_owns_real_target_seams_not_registry_lifecycle tests/test_footer_drawers_package.py -q
```

Expected: old `test_footer_drawers_package.py` will still fail if it expects registry lifecycle. Update those expectations in Task 6 after all package migrations. The new manifest test should pass once `patch.json` is correct.

- [ ] **Step 13: Commit footer-drawers real-target seam replacement**

Run:

```bash
git add packages/footer-drawers tests/test_footer_drawers_faithful_spike_port.py
git commit -m "fix: replace synthetic footer drawer framework with real targets"
```

Expected: commit succeeds. If the user has asked not to commit in the active execution thread, skip the commit and note the exact staged files instead.

---

## Task 3: Restore Hidden Context as a real target and panel component

**Files:**
- Modify: `packages/hidden-context-drawer/patch.json`
- Modify: `packages/hidden-context-drawer/README.md`
- Modify: `packages/hidden-context-drawer/payloads/01-projection-helpers-before-ypr-2.1.201.js`
- Create: `packages/hidden-context-drawer/payloads/17-panel-real-target.js`
- Delete: `packages/hidden-context-drawer/payloads/17-register-footer-drawer.js`
- Test: `tests/test_hidden_context_drawer_package.py`, `tests/test_footer_drawers_faithful_spike_port.py`

- [ ] **Step 1: Remove footer registry bump from Hidden Context helpers**

In `packages/hidden-context-drawer/payloads/01-projection-helpers-before-ypr-2.1.201.js`, delete this function:

```js
function __codexNCHCBumpFooter(){try{globalThis.__CODEX_FOOTER_DRAWERS_V1__?.bump?.("hiddenContext")}catch{}}
```

Also remove this call from `__codexNCHCDrawerFrameFromList`:

```js
__codexNCHCBumpFooter();
```

The frame helper must still assign:

```js
globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_FRAME_V13__=u;
```

- [ ] **Step 2: Replace registration payload with panel-only payload**

Delete `packages/hidden-context-drawer/payloads/17-register-footer-drawer.js` and create `packages/hidden-context-drawer/payloads/17-panel-real-target.js`:

```js
function __codexNCHCPanel(){let[e,t]=A_.useState(0);A_.useEffect(()=>{let c=setInterval(()=>t(Date.now()),250);return()=>clearInterval(c)},[]);let n=globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_FRAME_V13__,r=globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_SELECTED_V13__===!0&&globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_OPEN_V13__===!0&&n?.visible;if(!r)return null;let{rows:o}=Er(),s=Math.max(8,Math.min(Math.floor(o*2/3),Math.max(8,o-8))),i=Math.max(4,s-5);globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_VIEWPORT_V13__=i;let a=Math.max(0,Math.min(globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_SCROLL_V13__??0,Math.max(0,(n?.lines?.length??1)-i)));return Xd.jsxs(B,{flexDirection:"column",width:"100%",height:s,overflow:"hidden",borderStyle:"round",borderColor:"warning",borderText:{content:` Hidden Context ${n?.tokenCount??0} tokens `,position:"top",align:"start",offset:1},paddingX:1,paddingY:1,marginBottom:1,onWheel:l=>{l.preventDefault();let c=Math.max(0,Math.min(Math.max(0,(n?.lines?.length??1)-i),a+(l.deltaY>0?3:-3)));globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_SCROLL_V13__=c;globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_SET_SCROLL_V13__?.(c)},children:[Xd.jsx(v,{dimColor:!0,children:"up/down or mouse wheel scroll | x closes"}),...(n?.lines??[n?.summary??"No hidden context"]).slice(a,a+i).map((l,c)=>Xd.jsx(v,{wrap:"wrap",color:n?.lineKinds?.[a+c]==="header"?"warning":void 0,dimColor:n?.lineKinds?.[a+c]!=="header",children:l},c))]})}
```

The payload contains no descriptor fields and no registration call.

- [ ] **Step 3: Update Hidden Context manifest**

In `packages/hidden-context-drawer/patch.json`, remove operation `hidden-context-register-footer-drawer` and add operation `hidden-context-panel-real-target` with a computed payload SHA by running:

```bash
python3 - <<'PY'
import hashlib, json
from pathlib import Path
pkg = Path('packages/hidden-context-drawer')
manifest_path = pkg / 'patch.json'
manifest = json.loads(manifest_path.read_text())
ops = manifest['targets'][0]['modules'][0]['operations']
ops[:] = [op for op in ops if op['opId'] != 'hidden-context-register-footer-drawer']
payload = pkg / 'payloads' / '17-panel-real-target.js'
ops.append({
    'opId': 'hidden-context-panel-real-target',
    'label': 'Hidden Context real-target panel component',
    'type': 'insert_before',
    'anchor': 'var MXe,A_,Xd,GKo=2,pmr;',
    'expectedAnchorCount': 1,
    'insertOrder': 100,
    'replacement': {
        'path': 'payloads/17-panel-real-target.js',
        'sha256': hashlib.sha256(payload.read_bytes()).hexdigest(),
    },
    'knownBehaviorChange': 'Provides the Hidden Context panel component for the shared real-target overlay without registering a descriptor.',
})
for target in manifest['targets']:
    target['postconditions'] = [pc for pc in target.get('postconditions', []) if pc.get('value') not in {'__codexNCHCRegisterFooterDrawer', 'id:"hiddenContext"'}]
    values = {pc.get('value') for pc in target.get('postconditions', [])}
    if 'function __codexNCHCPanel' not in values:
        target.setdefault('postconditions', []).append({'type':'module_must_contain','modulePath':'/$bunfs/root/src/entrypoints/cli.js','value':'function __codexNCHCPanel'})
manifest_path.write_text(json.dumps(manifest, indent=2) + '
')
PY
```

Postconditions must include `function __codexNCHCPanel` and must not include `__codexNCHCRegisterFooterDrawer` or `id:"hiddenContext"`.

- [ ] **Step 4: Update Hidden Context tests**

In `tests/test_hidden_context_drawer_package.py`, replace any test that asserts registrant behavior with assertions matching this contract:

```python
def test_hidden_context_drawer_is_real_target_panel_not_registrant():
    manifest = load_manifest_v2(PACKAGE_DIR)
    op_ids = {op.op_id for target in manifest.targets for module in target.modules for op in module.operations}
    assert "hidden-context-panel-real-target" in op_ids
    assert "hidden-context-register-footer-drawer" not in op_ids
    text = "\n".join(path.read_text(encoding="utf-8") for path in sorted((PACKAGE_DIR / "payloads").glob("*.js")))
    assert "__codexNCHCRegisterFooterDrawer" not in text
    assert "__CODEX_FOOTER_DRAWERS_V1__" not in text
    assert ".register" not in text
    assert "function __codexNCHCPanel" in text
    assert "__CODEX_HIDDEN_CONTEXT_DRAWER_SELECTED_V13__===!0" in text
    assert "__CODEX_HIDDEN_CONTEXT_DRAWER_OPEN_V13__===!0" in text
    assert "escape" not in (PACKAGE_DIR / "payloads" / "17-panel-real-target.js").read_text(encoding="utf-8").lower()
```

Keep existing projection/frame tests that prove hidden context uses the rich pre-filter source.

- [ ] **Step 5: Run Hidden Context tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_hidden_context_drawer_package.py tests/test_footer_drawers_faithful_spike_port.py::test_payloads_and_manifests_contain_no_runtime_registry_or_synthetic_drawers -q
```

Expected: both pass after this package no longer ships a registrant payload.

- [ ] **Step 6: Commit Hidden Context real-target conversion**

Run:

```bash
git add packages/hidden-context-drawer tests/test_hidden_context_drawer_package.py tests/test_footer_drawers_faithful_spike_port.py
git commit -m "fix: restore hidden context as real footer target"
```

---

## Task 4: Convert Thinking to a real target extension

**Files:**
- Modify: `packages/thinking-text-drawer/patch.json`
- Modify: `packages/thinking-text-drawer/README.md`
- Modify: `packages/thinking-text-drawer/payloads/01-thinking-text-helpers.js`
- Create: `packages/thinking-text-drawer/payloads/17-panel-real-target.js`
- Delete: `packages/thinking-text-drawer/payloads/17-register-footer-drawer.js`
- Test: `tests/test_thinking_text_drawer_package.py`, `tests/test_footer_drawers_faithful_spike_port.py`

- [ ] **Step 1: Remove framework registry references from Thinking helpers**

In `packages/thinking-text-drawer/payloads/01-thinking-text-helpers.js`, replace the current `__codexTTDBumpFooter` and `__codexTTDIsOpen` definitions with:

```js
function __codexTTDBumpFooter(){return}
function __codexTTDIsOpen(){try{return globalThis.__CODEX_THINKING_TEXT_DRAWER_SELECTED_V1__===!0&&globalThis.__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__===!0}catch{return!1}}
function __codexTTDOpenDrawer(){globalThis.__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__=!0;globalThis.__CODEX_THINKING_TEXT_DRAWER_SELECTED_V1__=!0;__codexTTDMarkRead();return!0}
function __codexTTDCloseDrawer(){globalThis.__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__=!1;return!0}
```

Ensure the file contains no `__CODEX_FOOTER_DRAWERS_V1__`, `.openId`, or `openId` string.

- [ ] **Step 2: Replace Thinking registration with panel-only component**

Delete `packages/thinking-text-drawer/payloads/17-register-footer-drawer.js` and create `packages/thinking-text-drawer/payloads/17-panel-real-target.js`:

```js
function __codexTTDPanel(){let[e,t]=A_.useState(0);A_.useEffect(()=>{let c=setInterval(()=>t(Date.now()),250);return()=>clearInterval(c)},[]);let n=globalThis.__CODEX_THINKING_TEXT_DRAWER_SELECTED_V1__===!0&&globalThis.__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__===!0;if(!n)return null;let r=__codexTTDDrawerFrame(),{rows:o}=Er(),s=Math.max(8,Math.min(Math.floor(o*2/3),Math.max(8,o-8))),i=Math.max(4,s-5);globalThis.__CODEX_THINKING_TEXT_DRAWER_VIEWPORT_V1__=i;let a=Math.max(0,Math.min(globalThis.__CODEX_THINKING_TEXT_DRAWER_SCROLL_V1__??0,Math.max(0,(r?.lines?.length??1)-i)));return Xd.jsxs(B,{flexDirection:"column",width:"100%",height:s,overflow:"hidden",borderStyle:"round",borderColor:"permission",borderText:{content:` Thinking ${r?.entryCount??0} entries `,position:"top",align:"start",offset:1},paddingX:1,paddingY:1,marginBottom:1,onWheel:l=>{l.preventDefault();let c=Math.max(0,Math.min(Math.max(0,(r?.lines?.length??1)-i),a+(l.deltaY>0?3:-3)));globalThis.__CODEX_THINKING_TEXT_DRAWER_SCROLL_V1__=c;__codexTTDClampScroll(c,r?.lines?.length??1,i)},children:[Xd.jsx(v,{dimColor:!0,children:"up/down or mouse wheel scroll | x closes"}),...(r?.lines??[r?.summary??"No thinking captured yet"]).slice(a,a+i).map((l,c)=>Xd.jsx(v,{wrap:"wrap",color:r?.lineKinds?.[a+c]==="header"?"permission":void 0,dimColor:r?.lineKinds?.[a+c]!=="header",children:l},c))]})}
```

- [ ] **Step 3: Update Thinking manifest**

In `packages/thinking-text-drawer/patch.json`:

- remove op id `thinking-register-footer-drawer`,
- add op id `thinking-panel-real-target` using anchor `var MXe,A_,Xd,GKo=2,pmr;`, `insertOrder: 200`, and replacement `payloads/17-panel-real-target.js`,
- remove postconditions `__codexTTDRegisterFooterDrawer` and `id:"thinking",order:200`,
- add postcondition `function __codexTTDPanel`.

Recompute replacement SHA for the new panel payload and the helper payload.

- [ ] **Step 4: Update Thinking tests**

In `tests/test_thinking_text_drawer_package.py`:

- remove `thinking-register-footer-drawer` from `EXPECTED_OPERATION_IDS`,
- add `thinking-panel-real-target`,
- remove assertions for `.register`, `id:"thinking"`, `order:200`, `available:()=>!0`, `renderPanel:()=>`,
- add assertions:

```python
assert "__CODEX_FOOTER_DRAWERS_V1__" not in helpers
assert "openId" not in helpers
panel = read_rel("payloads/17-panel-real-target.js")
assert "function __codexTTDPanel" in panel
assert "__CODEX_THINKING_TEXT_DRAWER_SELECTED_V1__===!0&&globalThis.__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__===!0" in panel
assert "escape" not in panel.lower()
```

- [ ] **Step 5: Run Thinking tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_thinking_text_drawer_package.py tests/test_footer_drawers_faithful_spike_port.py::test_payloads_and_manifests_contain_no_runtime_registry_or_synthetic_drawers -q
```

Expected: both pass.

- [ ] **Step 6: Commit Thinking real-target conversion**

Run:

```bash
git add packages/thinking-text-drawer tests/test_thinking_text_drawer_package.py tests/test_footer_drawers_faithful_spike_port.py
git commit -m "fix: add thinking as real footer target"
```

---

## Task 5: Restore Reminders spike wrapper and panel without registration

**Files:**
- Modify: `packages/reminders-manager/patch.json`
- Modify: `packages/reminders-manager/README.md`
- Modify: `packages/reminders-manager/payloads/rm-attachment-wrapper-deny-2.1.201.js`
- Create: `packages/reminders-manager/payloads/rm-panel-real-target-2.1.201.js`
- Delete: `packages/reminders-manager/payloads/rm-register-footer-drawer-2.1.201.js`
- Test: `tests/test_reminders_manager.py`, `tests/test_footer_drawers_faithful_spike_port.py`

- [ ] **Step 1: Restore spike-shaped Reminders wrapper in the deny helper payload**

In `packages/reminders-manager/payloads/rm-attachment-wrapper-deny-2.1.201.js`, keep deny state/filter helpers and add this function before `async function _g(e,t){`:

```js
function __codexRMWrapActions(e,t){if(t!=="reminders")return e;let n=__codexRMUIState(),r=Object.assign({},e);r["footer:up"]=()=>{if(n.open){n.cursor=Math.max(0,n.cursor-1),__codexRMBump();return}return typeof e["footer:up"]==="function"?e["footer:up"]():void 0};r["footer:down"]=()=>{if(n.open){n.cursor=Math.min(7,n.cursor+1),__codexRMBump();return}return typeof e["footer:down"]==="function"?e["footer:down"]():void 0};r["footer:openSelected"]=()=>{if(!n.open){n.open=!0,n.cursor=0,__codexRMBump();return}let o=__codexRMFamilies(),s=__codexRMState().deny;if(n.cursor===0){let i=o.some((a)=>s[a]===!0);for(let a of o)s[a]=!i}else{let i=o[n.cursor-1];s[i]=s[i]!==!0}__codexRMBump();return};r["footer:clearSelection"]=()=>{if(n.open)return;return typeof e["footer:clearSelection"]==="function"?e["footer:clearSelection"]():void 0};r["footer:close"]=()=>{if(n.open){n.open=!1,__codexRMBump();return typeof e["footer:clearSelection"]==="function"?e["footer:clearSelection"]():void 0}return typeof e["footer:close"]==="function"?e["footer:close"]():void 0};return r}
```

Also change `__codexRMBump` so it does not touch `__CODEX_FOOTER_DRAWERS_V1__`:

```js
function __codexRMBump(){let e=__codexRMState();e.version=(e.version||0)+1}
```

- [ ] **Step 2: Replace Reminders registration with panel-only component**

Delete `packages/reminders-manager/payloads/rm-register-footer-drawer-2.1.201.js` and create `packages/reminders-manager/payloads/rm-panel-real-target-2.1.201.js`:

```js
function __codexRMPanel(){let[e,t]=A_.useState(0);A_.useEffect(()=>{let u=setInterval(()=>t(Date.now()),250);return()=>clearInterval(u)},[]);let n=__codexRMUIState(),r=globalThis.__CODEX_REMINDERS_SELECTED_V1__===!0&&n.open;if(!r)return null;let o=__codexRMState().deny,s=__codexRMFamilies(),i=__codexRMLabels(),a=s.some(u=>o[u]===!0),l=s.every(u=>o[u]===!0),c=u=>u===0?l?"[ ]":a?"[~]":"[x]":o[s[u-1]]===!0?"[ ]":"[x]",d=[];for(let u=0;u<8;u++){let p=u===n.cursor;d.push(Xd.jsx(B,{width:"100%",backgroundColor:p?"blue":void 0,children:Xd.jsx(v,{color:p?"white":void 0,bold:p,children:`${p?"\\u276F ":"  "}${c(u)} ${i[u]}`})},u));if(u===0)d.push(Xd.jsx(v,{dimColor:!0,children:"\\u2500".repeat(30)},"rm-sep"))}return Xd.jsx(B,{flexDirection:"column",width:"100%",borderStyle:"round",borderColor:"warning",borderText:{content:" Reminders \\xB7 up/down move \\xB7 enter/space toggles \\xB7 x closes ",position:"top",align:"start",offset:1},paddingX:1,marginBottom:1,children:d})}
```

- [ ] **Step 3: Update Reminders manifest**

In `packages/reminders-manager/patch.json`:

- remove op id `rm-register-footer-drawer`,
- add op id `rm-panel-real-target`,
- use anchor `var MXe,A_,Xd,GKo=2,pmr;`, `insertOrder: 300`, and replacement `payloads/rm-panel-real-target-2.1.201.js`,
- keep deny/filter operations unchanged except for helper payload hash,
- keep `requiresPackages: ["footer-drawers"]`,
- keep conflict with `upstream-attachment-suppression`,
- remove postconditions `function __codexRMRegisterFooterDrawer(` and `id:"reminders"`,
- add postconditions `function __codexRMWrapActions(` and `function __codexRMPanel(`.

Recompute replacement SHAs for the wrapper and panel payloads.

- [ ] **Step 4: Update Reminders tests**

In `tests/test_reminders_manager.py`, replace the thin registrant test with:

```python
def test_reminders_manager_uses_spike_wrapper_and_real_target_panel():
    manifest = load_manifest_v2(PACKAGE_DIR)
    op_ids = {op.op_id for target in manifest.targets for module in target.modules for op in module.operations}
    assert {"rm-attachment-wrapper-deny", "rm-xye-runtime-filter", "rm-panel-real-target"}.issubset(op_ids)
    assert "rm-register-footer-drawer" not in op_ids
    wrapper = (PACKAGE_DIR / "payloads" / "rm-attachment-wrapper-deny-2.1.201.js").read_text(encoding="utf-8")
    panel = (PACKAGE_DIR / "payloads" / "rm-panel-real-target-2.1.201.js").read_text(encoding="utf-8")
    assert "function __codexRMWrapActions(e,t){if(t!==\"reminders\")return e" in wrapper
    assert "__CODEX_FOOTER_DRAWERS_V1__" not in wrapper
    assert "function __codexRMRegisterFooterDrawer" not in wrapper + panel
    assert ".register" not in wrapper + panel
    assert "function __codexRMPanel" in panel
    assert "__CODEX_REMINDERS_SELECTED_V1__===!0&&n.open" in panel
    assert "escape" not in panel.lower()
```

Keep deny/filter tests for attachment suppression behavior.

- [ ] **Step 5: Run Reminders tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest tests/test_reminders_manager.py tests/test_footer_drawers_faithful_spike_port.py::test_payloads_and_manifests_contain_no_runtime_registry_or_synthetic_drawers -q
```

Expected: both pass.

- [ ] **Step 6: Commit Reminders real-target conversion**

Run:

```bash
git add packages/reminders-manager tests/test_reminders_manager.py tests/test_footer_drawers_faithful_spike_port.py
git commit -m "fix: restore reminders spike footer wrapper"
```

---

## Task 6: Update package-level tests and docs for the real-target contract

**Files:**
- Modify: `tests/test_footer_drawers_package.py`
- Modify: `tests/test_hidden_context_drawer_package.py`
- Modify: `tests/test_thinking_text_drawer_package.py`
- Modify: `tests/test_reminders_manager.py`
- Modify: package README files

- [ ] **Step 1: Replace old footer-drawers registry lifecycle tests**

In `tests/test_footer_drawers_package.py`, delete tests that execute `__codexFDDrawers`, `__codexFDAvailable`, `__codexFDBarItems`, `__codexFDMove`, or `__codexFDOpen`.

Replace them with:

```python
def test_footer_drawers_payloads_have_no_registry_or_descriptor_contract() -> None:
    text = "\n".join(path.read_text(encoding="utf-8") for path in sorted((FOOTER_DRAWERS / "payloads").glob("*.js")))
    for needle in [
        "__CODEX_FOOTER_DRAWERS_V1__",
        "__codexFDDrawers",
        "__codexFDRegister",
        "hoverId",
        "openId",
        "__codexFDLand",
        "__codexFDMove",
        '"drawers"',
        'footerSelection==="drawers"',
    ]:
        assert needle not in text
    assert "function __codexFDWrapRealTargetActions" in text
    assert 't==="reminders"&&typeof __codexRMWrapActions==="function"' in text
    assert "__codexHiddenContextFrame?.visible&&\"hiddenContext\"" in text
    assert "FDdrawerBars=[FDhBar,FDtBar,FDrBar].filter(Boolean)" in text
```

Update `FRAMEWORK_OP_IDS` to the real-target op ids from Task 2.

- [ ] **Step 2: Update README language**

For each package README, replace framework descriptor language with real-target language:

- `packages/footer-drawers/README.md` must say: `This package owns shared real-target footer seams. It does not provide a runtime registry and must not create a synthetic drawers target.`
- `packages/hidden-context-drawer/README.md` must say: `Hidden Context is selected through the real footer target hiddenContext. Escape is not a close affordance; x closes.`
- `packages/thinking-text-drawer/README.md` must say: `Thinking is a real footer target extension copied from the Hidden Context open/scroll shape. It does not register a descriptor.`
- `packages/reminders-manager/README.md` must say: `Reminders uses the spike-shaped __codexRMWrapActions(actions, selectedTarget) path and activates only when selectedTarget is reminders.`

- [ ] **Step 3: Add one guard against descriptor-like static object tables**

Add this test to `tests/test_footer_drawers_faithful_spike_port.py`:

```python
def test_no_descriptor_like_static_drawer_table_exists() -> None:
    text = _all_payload_text()
    forbidden_combinations = [
        ('id:"hiddenContext"', 'onOpen:', 'renderPanel:'),
        ('id:"thinking"', 'onOpen:', 'renderPanel:'),
        ('id:"reminders"', 'onOpen:', 'renderPanel:'),
        ('available:()=>', 'onKey:', 'renderPanel:'),
    ]
    for combo in forbidden_combinations:
        assert not all(piece in text for piece in combo), combo
```

- [ ] **Step 4: Run all non-smoke package tests**

Run:

```bash
PYTHONPATH=src python3 -m pytest \
  tests/test_footer_drawers_faithful_spike_port.py \
  tests/test_footer_drawers_package.py \
  tests/test_hidden_context_drawer_package.py \
  tests/test_thinking_text_drawer_package.py \
  tests/test_reminders_manager.py \
  -q -m 'not local_real_smoke'
```

Expected: all selected non-smoke tests pass.

- [ ] **Step 5: Commit tests and docs**

Run:

```bash
git add tests packages/*/README.md packages/*/patch.json
git commit -m "test: lock footer drawers to real target contract"
```

---

## Task 7: Full composition build and final verification

**Files:**
- Read: all modified manifests/payloads/tests
- Build output: `.development/claude-monkey-builds/footer-drawers-faithful-spike-port/claude`

- [ ] **Step 1: Run the full focused test suite including local real smokes**

Run:

```bash
PYTHONPATH=src python3 -m pytest \
  tests/test_footer_drawers_faithful_spike_port.py \
  tests/test_footer_drawers_package.py \
  tests/test_hidden_context_drawer_package.py \
  tests/test_thinking_text_drawer_package.py \
  tests/test_reminders_manager.py \
  -q
```

Expected: all tests pass or local real-smoke tests report `manual_smoke_pending` by assertion. No test should skip because of missing source identity on this machine unless the binary was moved.

- [ ] **Step 2: Build the full package stack**

Run the exact CLI build command:

```bash
PYTHONPATH=src python3 -m claude_monkey build \
  --source /Users/MAC/.local/share/claude/versions/2.1.201 \
  --source-version 2.1.201 \
  --source-version-output '2.1.201 (Claude Code)' \
  --platform darwin \
  --arch arm64 \
  --package packages/footer-drawers \
  --package packages/hidden-context-drawer \
  --package packages/thinking-text-drawer \
  --package packages/reminders-manager \
  --output-dir .development/claude-monkey-builds/footer-drawers-faithful-spike-port \
  --json
```

Expected:

- build succeeds,
- enabled packages are exactly `footer-drawers`, `hidden-context-drawer`, `thinking-text-drawer`, `reminders-manager`,
- status is `manual_smoke_pending` if the report includes status,
- activation is not treated as complete without manual smoke.

- [ ] **Step 3: Smoke the built binary version only after tests/build pass**

Run:

```bash
.development/claude-monkey-builds/footer-drawers-faithful-spike-port/claude --version
```

Expected:

```text
2.1.201 (Claude Code)
```

- [ ] **Step 4: Run static grep guards on the composed output if available**

If the build command writes a patched module artifact, run grep on that module. If it does not, use the composed module extracted in the pytest build helper. The guard must prove:

```bash
! grep -R '__CODEX_FOOTER_DRAWERS_V1__\|__codexFDDrawers\|hoverId\|openId\|footerSelection==="drawers"\|id:"drawers"' .development/claude-monkey-builds/footer-drawers-faithful-spike-port
```

Expected: no matches. If the directory includes unrelated logs that quote forbidden strings from tests/docs, restrict grep to the patched module/binary extraction, not docs.

- [ ] **Step 5: Record manual smoke status honestly**

Do not claim interactive behavior is fully verified unless someone actually performs the TUI smoke. The final report should say:

```text
Programmatic verification passed; binary version smoke passed. Full interactive TUI smoke remains pending for: down to Hidden Context, right/left among real drawer targets, enter opens selected real drawer, up/down scrolls or moves rows, x closes, escape does not close.
```

- [ ] **Step 6: Final diff review**

Run:

```bash
git status --short
git diff --stat
git diff -- packages/footer-drawers packages/hidden-context-drawer packages/thinking-text-drawer packages/reminders-manager tests docs/superpowers/specs docs/superpowers/reports docs/superpowers/plans | sed -n '1,260p'
```

Expected: only scoped files changed. No unrelated package changes.

- [ ] **Step 7: Commit final verification updates if needed**

If Task 7 only produced build artifacts under ignored `.development`, do not commit them. If README/test/report text changed, commit:

```bash
git add packages tests docs/superpowers/specs/2026-07-04-footer-drawers-faithful-spike-port-spec.md docs/superpowers/reports/2026-07-04-footer-drawers-failure-report.md docs/superpowers/plans/2026-07-04-footer-drawers-faithful-spike-port.md
git commit -m "docs: add footer drawers faithful spike port plan"
```

---

## Review gates

After Task 1 red tests and before implementation, request adversarial review if the tests do not fail for the current synthetic implementation.

After Task 6, request adversarial review of the modified payloads/manifests/tests before Task 7 full build. The reviewer prompt must ask specifically:

- Did any runtime registry/descriptors survive?
- Does target construction use real target ids before `tasks`?
- Does Hidden Context availability come from same-render frame construction?
- Does Reminders still use `__codexRMWrapActions(actions, selectedTarget)` and only activate for `selectedTarget === "reminders"`?
- Is Thinking constrained to local selected/open state?
- Do the tests catch the previous failure mode?

Do not proceed to final handoff with unresolved blocking review feedback.

## Self-review checklist for the executor

Before final response, verify each line is true:

- No synthetic `"drawers"` target remains in runtime payloads or composed module.
- No `__CODEX_FOOTER_DRAWERS_V1__` registry remains.
- No drawer descriptor registration payload remains.
- Hidden Context frame is computed same-render before target construction.
- Real target order is Hidden Context, Thinking, Reminders, then stock targets.
- Bar hints use real selected target ids.
- Enter opens selected real target.
- `x` closes; Escape does not close.
- Tests and binary version smoke have run.
- Interactive TUI smoke status is reported honestly.
