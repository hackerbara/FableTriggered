# Footer Drawers Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship one shared `footer-drawers` framework plus thin `hidden-context-drawer`, `thinking-text-drawer`, and `reminders-manager` registrants, all targeting the latest local Claude Code version on this system (`2.1.201` as of 2026-07-04).

**Architecture:** The framework owns every shared footer/overlay seam: registry, toolbar target, hover/open lifecycle, key routing, status-bar drawer segment, and one bottom-overlay renderer. Each drawer keeps only its content seam(s) and registers a descriptor with the framework. The build remains a copied-output-only Bun graph repack using structured splices against original module bytes.

**Tech Stack:** Python 3 stdlib package tooling and pytest; ClaudeMonkey schema-v2 patch manifests plus existing V3 package envelope bridge for `thinking-text-drawer`; JavaScript payloads injected into `/$bunfs/root/src/entrypoints/cli.js`; local Claude Code `2.1.201` at `/Users/MAC/.local/share/claude/versions/2.1.201`.

**Source spec:** `docs/superpowers/specs/2026-07-03-footer-drawers-framework-design.md`. Read it completely before starting.

---

## Global Constraints

- Work in an isolated worktree at execution time unless the user explicitly says otherwise. Use `superpowers:using-git-worktrees` before implementation.
- Preserve unrelated dirt in `/Users/MAC/Documents/Claude-patch`. Do not clean, revert, or stage files outside this plan's file list.
- Target one source identity across all four packages:
  - binary: `/Users/MAC/.local/share/claude/versions/2.1.201`
  - version output: `2.1.201 (Claude Code)`
  - binary SHA-256: `a0852d76afc47b30f5cb0b7625ec9a7714cb189f2eeef6c28c77e2be954fb7fd`
  - binary size: `231708784`
  - module path: `/$bunfs/root/src/entrypoints/cli.js`
  - module SHA-256: `46db617a7b13c062fb31595f6244819b11f7cdc6e6fed8e2c3f74a27fb6da1bd`
  - module length: `18700756`
- If execution starts after the local latest Claude Code changes, stop and update this plan/spec target constants before implementation. Do not mix package target versions.
- Use structured splices; do not reintroduce whole-status-bar restatements for drawer labels or independent footer action wrappers in drawers.
- `x` / `footer:close` is the drawer close path. `escape` / `footer:clearSelection` does not close framework drawers.
- Payloads must be ASCII-safe: no literal non-ASCII UI glyphs. Use `\u2192`, `\u2500`, `\u276F`, `\xB7`, or `String.fromCharCode(...)`.
- Every target anchor must resolve exactly once in the 2.1.201 module. Every package test that checks anchors should skip only when the local source/module dump is unavailable or mismatched, not when a checked-in package is malformed.
- Manual smoke remains required. Automated green output is not manual smoke.

## File Structure

### Create

- `packages/footer-drawers/README.md` — framework package docs, build command, smoke checklist.
- `packages/footer-drawers/patch.json` — schema-v2 framework manifest targeting 2.1.201.
- `packages/footer-drawers/payloads/01-bootstrap-and-overlay.js` — registry helpers plus replacement `Ilc()` bottom-overlay renderer.
- `packages/footer-drawers/payloads/02-footer-render-tick-state.js` — adds footer registry version state in the footer component hook cluster.
- `packages/footer-drawers/payloads/03-footer-render-tick-effect.js` — polls registry version and forces footer re-render.
- `packages/footer-drawers/payloads/04-footer-target-drawers.js` — adds synthetic `"drawers"` target before stock `tasks` in `ss`.
- `packages/footer-drawers/payloads/05-footer-target-deps.js` — adds the framework render tick state to `ss` useMemo deps.
- `packages/footer-drawers/payloads/06-footer-selection-flag.js` — adds selected flag for `Lm === "drawers"`.
- `packages/footer-drawers/payloads/07-footer-action-wrap-open.js` — starts framework action wrapper around `Go({ ... })`.
- `packages/footer-drawers/payloads/08-footer-action-wrap-close.js` — closes action wrapper and passes active selection/setter.
- `packages/footer-drawers/payloads/09-footer-space-binding.js` — adds `space:"footer:openSelected"` to Footer bindings.
- `packages/footer-drawers/payloads/10-footer-bar-var.js` — computes the framework drawer-toolbar segment in the status bar row.
- `packages/footer-drawers/payloads/11-footer-bar-shortcuts-condition.js` — prevents the stock shortcuts hint from hiding an otherwise-visible drawer segment.
- `packages/footer-drawers/payloads/12-footer-bar-null-condition.js` — prevents the status bar from returning null when only the drawer segment is visible.
- `packages/footer-drawers/payloads/13-footer-bar-render.js` — renders the drawer segment between stock task UI and stock shortcut hints.
- `tests/test_footer_drawers_package.py` — manifest/payload/composition tests for the framework package and full matrix.

### Modify

- `packages/thinking-text-drawer/patch.json` — add `requiresPackages`, remove direct footer/overlay/status ops, keep content collector ops, add registration op.
- `packages/thinking-text-drawer/README.md` — document framework dependency and new build command.
- `packages/thinking-text-drawer/payloads/01-thinking-text-helpers.js` — remove direct `__codexTTDWrapFooterActions`, remove the trailing `function Ypr(e){` suffix, add registry bump/open helpers, keep content/frame helpers.
- `packages/thinking-text-drawer/payloads/17-register-footer-drawer.js` — new registration payload; file may be created under the existing package.
- `tests/test_thinking_text_drawer_package.py` — update expected op ids and thin-registrant assertions.
- `packages/hidden-context-drawer/patch.json` — bump to 2.1.201, keep projection/frame content seams, add relationship metadata and registration op, remove direct footer/overlay ops.
- `packages/hidden-context-drawer/README.md` — document framework dependency, 2.1.201 target, x-only close via framework.
- `packages/hidden-context-drawer/payloads/01-projection-helpers-before-ypr-2.1.201.js` — create renamed helper block before the 2.1.201 hidden-filter function and call framework bump when frame changes; do not include a trailing `function Ypr(e){` suffix.
- `packages/hidden-context-drawer/payloads/02-yt-projection-list-drawer-frame.js` — re-anchor projection list seam to 2.1.201 and publish the frame before footer availability.
- `packages/hidden-context-drawer/payloads/17-register-footer-drawer.js` — new registration payload.
- `tests/test_hidden_context_drawer_package.py` — update target identity, retained/moved op assertions, and x/Escape contract expectations.
- `packages/reminders-manager/patch.json` — bump to 2.1.201, keep deny/filter seams, add `requiresPackages` and UAS conflict, add registration op, remove direct footer/overlay ops.
- `packages/reminders-manager/README.md` — document framework dependency, 2.1.201 target, UAS conflict, framework-owned footer UI.
- `packages/reminders-manager/payloads/rm-attachment-wrapper-deny-2.1.201.js` — create renamed/re-anchored retained deny helper payload replacing 2.1.201 `_g`.
- `packages/reminders-manager/payloads/rm-xye-runtime-filter-2.1.201.js` — create renamed/re-anchored retained filter payload replacing 2.1.201 `XYe`.
- `packages/reminders-manager/payloads/rm-register-footer-drawer-2.1.201.js` — new registration/panel descriptor payload.
- `tests/test_reminders_manager.py` — update target identity, retained/moved op assertions, relationship metadata, and framework composition tests.
- `tests/test_reference_packages.py` — update expected package inventory only if the local test currently hard-codes moved op ids; keep changes scoped to footer-drawers package expectations.

### Do Not Touch

- `src/claude_monkey/*` unless a test reveals the already-merged structured-splice engine violates the spec. Engine work is not part of this plan.
- Unrelated visual packages (`hotrod-dragons`, `dvd-cursor-*`, `capybara-onsen`) and unrelated docs.
- The user's live `/Users/MAC/.local/bin/claude` symlink.

---

## Task 0: Pre-flight source proof and module dump

**Files:**
- Read: `/Users/MAC/.local/share/claude/versions/2.1.201`
- Read/Create: `.development/artifacts/claude-2.1.201-framework-source-module0.js`
- Read: `docs/superpowers/specs/2026-07-03-footer-drawers-framework-design.md`

- [ ] **Step 0: Prepare the implementation shell and Python runtime**

After using `superpowers:using-git-worktrees`, set `REPO` to the implementation worktree path. Command blocks in this plan use `${REPO:-/Users/MAC/Documents/Claude-patch}` so they remain copy-pastable, but implementation should run in the worktree, not the dirty source checkout.

Run:

```bash
export REPO="${REPO:-/Users/MAC/Documents/Claude-patch}"
cd "$REPO"
export PY="${PY:-/Users/MAC/Documents/Claude-patch/.venv/bin/python}"
if [ ! -x "$PY" ]; then
  python3 -m venv "$REPO/.venv"
  export PY="$REPO/.venv/bin/python"
  "$PY" -m pip install -e '.[dev]'
fi
"$PY" -m pytest --version
```

Expected: pytest prints its version. Do not use system Python for pytest; on this machine system Python lacks pytest.

- [ ] **Step 1: Verify the source identity before editing**

Run:

```bash
cd "${REPO:-/Users/MAC/Documents/Claude-patch}"
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

Expected output:

```text
a0852d76afc47b30f5cb0b7625ec9a7714cb189f2eeef6c28c77e2be954fb7fd
231708784
```

- [ ] **Step 2: Ensure a 2.1.201 module dump exists**

Run:

```bash
cd "${REPO:-/Users/MAC/Documents/Claude-patch}"
if [ -f .development/artifacts/claude-2.1.201-thinking-text-drawer-source-module0.js ]; then
  cp .development/artifacts/claude-2.1.201-thinking-text-drawer-source-module0.js \
     .development/artifacts/claude-2.1.201-framework-source-module0.js
else
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
out = Path('.development/artifacts/claude-2.1.201-framework-source-module0.js')
out.parent.mkdir(parents=True, exist_ok=True)
out.write_bytes(module.content)
print(out)
PY
fi
shasum -a 256 .development/artifacts/claude-2.1.201-framework-source-module0.js
wc -c .development/artifacts/claude-2.1.201-framework-source-module0.js
```

Expected SHA and byte count:

```text
46db617a7b13c062fb31595f6244819b11f7cdc6e6fed8e2c3f74a27fb6da1bd
18700756
```

- [ ] **Step 3: Verify framework seam anchors are present once**

Run:

```bash
cd "${REPO:-/Users/MAC/Documents/Claude-patch}"
python3 - <<'PY'
from pathlib import Path
src = Path('.development/artifacts/claude-2.1.201-framework-source-module0.js').read_text()
anchors = {
  'footer_state_cluster': 'wt=wo.useRef(!1)',
  'footer_tick_effect_anchor': 'wo.useEffect(()=>()=>{if(Ar.current)Ar.current(),Ar.current=null},[]);',
  'footer_targets': 'ss=wo.useMemo(()=>[Ui&&"tasks",po&&"workflows",Fn&&"tmux",_e&&"bagel",Tr&&"bridge",Ne&&"frame"].filter(Boolean),[Ui,po,Fn,_e,Tr,Ne])',
  'footer_selection_flags': 'let lm=Lm==="tasks",ZE=Lm==="workflows",Hd=Lm==="tmux",Zp=Lm==="bagel",AT=Lm==="bridge",Mm=Lm==="frame";function Rp',
  'footer_action_open': 'Go({"footer:up":By,"footer:down":d0,"footer:next":o6,"footer:previous":IR,"footer:openSelected":()=>{',
  'footer_action_close': 'return!1}},{context:"Footer",isActive:!!Lm&&!se});',
  'bottom_overlay': 'function Ilc(){let e=MXe.c(2),t=clc();if(!t)return null;let n;if(e[0]!==t)n=Xd.jsx(B,{position:"absolute",bottom:"100%",left:0,right:0,opaque:!0,children:t}),e[0]=t,e[1]=n;else n=e[1];return n}',
}
for name, anchor in anchors.items():
    count = src.count(anchor)
    print(name, count)
    assert count == 1, (name, count)
PY
```

Expected: every listed anchor prints count `1`.

- [ ] **Step 4: Commit nothing**

This task creates only a scratch `.development/artifacts/...` module dump. Do not commit it.

---

## Task 1: Framework package tests first

**Files:**
- Create: `tests/test_footer_drawers_package.py`
- Read: `tests/test_builder_v15.py`, `tests/fixtures_bun.py`, `tests/test_thinking_text_drawer_package.py`

- [ ] **Step 1: Write failing tests for the framework manifest and payload contracts**

Create `tests/test_footer_drawers_package.py` with this initial content:

```python
from __future__ import annotations

import hashlib
import json
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
    assert 'return e["footer:clearSelection"]?.()' in clear_handler
    assert "__codexFDClose(\"escape\")" not in text
    assert "__codexFDClose(\"x\")" in text


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
```

- [ ] **Step 2: Run the tests and verify they fail for missing package**

Run:

```bash
cd "${REPO:-/Users/MAC/Documents/Claude-patch}"
PYTHONPATH=src "${PY:-${REPO:-/Users/MAC/Documents/Claude-patch}/.venv/bin/python}" -m pytest tests/test_footer_drawers_package.py -v
```

Expected: failure begins with `FileNotFoundError` for `packages/footer-drawers/patch.json` or `packages/footer-drawers/payloads/01-bootstrap-and-overlay.js`.

- [ ] **Step 3: Commit the failing tests**

```bash
git add tests/test_footer_drawers_package.py
git commit -m "test: define footer drawers framework package contract"
```

---

## Task 2: Create `footer-drawers` package skeleton and registry helper payload

**Files:**
- Create: `packages/footer-drawers/README.md`
- Create: `packages/footer-drawers/patch.json`
- Create: `packages/footer-drawers/payloads/01-bootstrap-and-overlay.js`
- Create: placeholder payload files `02` through `13` with exact contents in this task
- Test: `tests/test_footer_drawers_package.py`

- [ ] **Step 1: Create package directory and README**

Run:

```bash
cd "${REPO:-/Users/MAC/Documents/Claude-patch}"
mkdir -p packages/footer-drawers/payloads
cat > packages/footer-drawers/README.md <<'MD'
# Footer Drawers Framework

Shared footer toolbar framework for ClaudeMonkey drawer packages.

This package owns one synthetic `drawers` footer target, registry lifecycle, drawer hover/open state, key routing, status-bar drawer labels, and one bottom-overlay sibling above the prompt. It ships no drawer content. Drawer packages register with `globalThis.__CODEX_FOOTER_DRAWERS_V1__` and require this package.

Target: Claude Code 2.1.201, darwin/arm64.

Ship set:

- `footer-drawers`
- `hidden-context-drawer`
- `thinking-text-drawer`
- `reminders-manager`

Manual smoke is required. Verify down lands on the drawer toolbar once, left/right moves Hidden Context -> Thinking -> Reminders, enter/space opens, `x` closes, Escape does not close framework drawers, and only one drawer is open at a time.
MD
```

- [ ] **Step 2: Write registry/bootstrap + overlay payload**

Create `packages/footer-drawers/payloads/01-bootstrap-and-overlay.js` with ASCII-only JavaScript. This payload defines the framework helpers before replacing the stock `Ilc()` function:

```js
function __codexFDDrawers(){let e=globalThis.__CODEX_FOOTER_DRAWERS_V1__;if(!e||typeof e!=="object")e={entries:[],hoverId:null,openId:null,version:0,lastError:null},globalThis.__CODEX_FOOTER_DRAWERS_V1__=e;if(!Array.isArray(e.entries))e.entries=[];if(typeof e.version!=="number")e.version=0;e.bump=function(t){try{e.version=(e.version||0)+1,e.lastReason=t||null}catch{}};e.register=function(t){return __codexFDRegister(t)};return e}function __codexFDBump(e){let t=__codexFDDrawers();t.version=(t.version||0)+1;t.lastReason=e||null;return t.version}function __codexFDRegister(e){let t=__codexFDDrawers();if(!e||typeof e.id!=="string")return t;let n=t.entries.findIndex(r=>r&&r.id===e.id);if(n>=0)t.entries=[...t.entries.slice(0,n),e,...t.entries.slice(n+1)];else t.entries=[...t.entries,e];__codexFDBump("register:"+e.id);return t}function __codexFDSafe(e,t,n){try{return typeof e==="function"?e():t}catch(r){try{__codexFDDrawers().lastError=String(n||"callback")+":"+String(r?.message||r)}catch{}return t}}function __codexFDAvailable(){let e=__codexFDDrawers(),t=[];for(let n of e.entries){if(!n||typeof n.id!=="string")continue;if(__codexFDSafe(n.available,!1,n.id+":available"))t.push(n)}t.sort((n,r)=>(Number(n.order)||0)-(Number(r.order)||0));if(t.length===0)e.hoverId=null;else if(!t.some(n=>n.id===e.hoverId))e.hoverId=t[0].id;return t}function __codexFDEntry(e){return __codexFDDrawers().entries.find(t=>t&&t.id===e)||null}function __codexFDHovered(){let e=__codexFDAvailable(),t=__codexFDDrawers();return e.find(n=>n.id===t.hoverId)||e[0]||null}function __codexFDMove(e){let t=__codexFDAvailable(),n=__codexFDDrawers();if(!t.length)return!0;let r=t.findIndex(o=>o.id===n.hoverId);if(r<0)r=0;r=Math.max(0,Math.min(t.length-1,r+e));n.hoverId=t[r].id;__codexFDBump("hover");return!0}function __codexFDOpen(e){let t=__codexFDDrawers(),n=e?__codexFDEntry(e):__codexFDHovered();if(!n)return!0;if(t.openId&&t.openId!==n.id)__codexFDClose("switch");t.openId=n.id;t.hoverId=n.id;__codexFDBump("open:"+n.id);__codexFDSafe(n.onOpen,null,n.id+":onOpen");return!0}function __codexFDClose(e){let t=__codexFDDrawers(),n=t.openId?__codexFDEntry(t.openId):null;if(n)__codexFDSafe(()=>n.onClose?.(e),null,n.id+":onClose");t.openId=null;__codexFDBump("close:"+(e||"unknown"));return!0}function __codexFDWrapActions(e,t,n){let r={...e},o=t==="drawers",s=__codexFDDrawers(),i=()=>{let a=s.openId?__codexFDEntry(s.openId):null;return a};if(!o&&!s.openId)return e;r["footer:previous"]=()=>{let a=i();if(a&&__codexFDSafe(()=>a.onKey?.("previous"),!1,a.id+":previous"))return;return o?__codexFDMove(-1):e["footer:previous"]?.()};r["footer:next"]=()=>{let a=i();if(a&&__codexFDSafe(()=>a.onKey?.("next"),!1,a.id+":next"))return;return o?__codexFDMove(1):e["footer:next"]?.()};r["footer:up"]=()=>{let a=i();if(a&&__codexFDSafe(()=>a.onKey?.("up"),!1,a.id+":up"))return;return e["footer:up"]?.()};r["footer:down"]=()=>{let a=i();if(a&&__codexFDSafe(()=>a.onKey?.("down"),!1,a.id+":down"))return;return e["footer:down"]?.()};r["footer:openSelected"]=()=>{let a=i();if(a){if(__codexFDSafe(()=>a.onKey?.("openSelected"),!1,a.id+":openSelected"))return;return}if(o)return __codexFDOpen();return e["footer:openSelected"]?.()};r["footer:close"]=()=>{if(s.openId)return __codexFDClose("x");return e["footer:close"]?.()};r["footer:clearSelection"]=()=>{let a=i();if(a){if(__codexFDSafe(()=>a.onKey?.("clearSelection"),!1,a.id+":clearSelection"))return;return}return e["footer:clearSelection"]?.()};return r}function __codexFDBarText(){let e=__codexFDAvailable(),t=__codexFDDrawers();return e.map(n=>{let r=__codexFDSafe(n.label,n.id,n.id+":label"),o=__codexFDSafe(n.badge,null,n.id+":badge"),s=__codexFDSafe(n.flash,!1,n.id+":flash"),i=t.openId?"":n.id===t.hoverId?" (enter)":" "+String.fromCharCode(8594);return String(r)+(o?" "+String(o):"")+(s?" *":"")+i}).join(" "+String.fromCharCode(183)+" ")}function __codexFDDrawerPanel(){let e=__codexFDDrawers(),t=e.openId?__codexFDEntry(e.openId):null;if(!t)return null;return __codexFDSafe(t.renderPanel,null,t.id+":renderPanel")}function Ilc(){let e=MXe.c(3),t=clc(),n=__codexFDDrawerPanel();if(!t&&!n)return null;let r;if(e[0]!==t||e[1]!==n)r=Xd.jsx(B,{position:"absolute",bottom:"100%",left:0,right:0,opaque:!0,children:Xd.jsxs(Xd.Fragment,{children:[n,t]})}),e[0]=t,e[1]=n,e[2]=r;else r=e[2];return r}
```

- [ ] **Step 3: Create temporary exact placeholder payloads for remaining operations**

These payloads make tests fail on manifest anchor/hash until the next task fills manifest entries, not on missing files:

```bash
cd "${REPO:-/Users/MAC/Documents/Claude-patch}"
for f in 02-footer-render-tick-state.js 03-footer-render-tick-effect.js 04-footer-target-drawers.js 05-footer-target-deps.js 06-footer-selection-flag.js 07-footer-action-wrap-open.js 08-footer-action-wrap-close.js 09-footer-space-binding.js 10-footer-bar-var.js 11-footer-bar-shortcuts-condition.js 12-footer-bar-null-condition.js 13-footer-bar-render.js; do
  printf '/* footer-drawers payload %s is filled by Task 3 */\n' "$f" > "packages/footer-drawers/payloads/$f"
done
```

- [ ] **Step 4: Create initial manifest with only bootstrap op active**

Compute the bootstrap payload SHA and old-range evidence:

```bash
cd "${REPO:-/Users/MAC/Documents/Claude-patch}"
python3 - <<'PY'
import hashlib, json
from pathlib import Path
source = Path('.development/artifacts/claude-2.1.201-framework-source-module0.js').read_text()
exact = 'function Ilc(){let e=MXe.c(2),t=clc();if(!t)return null;let n;if(e[0]!==t)n=Xd.jsx(B,{position:"absolute",bottom:"100%",left:0,right:0,opaque:!0,children:t}),e[0]=t,e[1]=n;else n=e[1];return n}'
assert source.count(exact) == 1
payload = Path('packages/footer-drawers/payloads/01-bootstrap-and-overlay.js').read_bytes()
manifest = {
  'schemaVersion': 2,
  'id': 'footer-drawers',
  'name': 'Footer Drawers Framework',
  'description': 'Shared footer toolbar, lifecycle, status bar, and bottom-overlay mount for drawer packages.',
  'packageVersion': '0.1.0',
  'targets': [{
    'sourceIdentity': {
      'claudeVersion': '2.1.201',
      'versionOutput': '2.1.201 (Claude Code)',
      'sha256': 'a0852d76afc47b30f5cb0b7625ec9a7714cb189f2eeef6c28c77e2be954fb7fd',
      'sizeBytes': 231708784,
      'platform': 'darwin',
      'arch': 'arm64',
    },
    'requiredEngine': 'bun_graph_repack',
    'requiredBinaryFormat': 'bun_standalone_macho64',
    'modules': [{
      'path': '/$bunfs/root/src/entrypoints/cli.js',
      'contentSha256': '46db617a7b13c062fb31595f6244819b11f7cdc6e6fed8e2c3f74a27fb6da1bd',
      'contentLength': 18700756,
      'operations': [{
        'opId': 'fd-bootstrap-and-overlay',
        'label': 'Footer Drawers registry bootstrap and shared bottom overlay renderer',
        'type': 'replace_exact',
        'exact': exact,
        'requireWithinRange': [],
        'oldRangeSha256': hashlib.sha256(exact.encode()).hexdigest(),
        'oldRangeLength': len(exact.encode()),
        'replacement': {'path': 'payloads/01-bootstrap-and-overlay.js', 'sha256': hashlib.sha256(payload).hexdigest()},
        'knownBehaviorChange': 'Adds shared drawer registry helpers and renders the active registered drawer in the bottom overlay sibling.'
      }],
    }],
    'preconditions': [{'type': 'module_must_contain', 'modulePath': '/$bunfs/root/src/entrypoints/cli.js', 'value': exact}],
    'postconditions': [
      {'type': 'module_must_contain', 'modulePath': '/$bunfs/root/src/entrypoints/cli.js', 'value': '__CODEX_FOOTER_DRAWERS_V1__'},
      {'type': 'module_must_contain', 'modulePath': '/$bunfs/root/src/entrypoints/cli.js', 'value': 'function __codexFDWrapActions'},
      {'type': 'module_must_contain', 'modulePath': '/$bunfs/root/src/entrypoints/cli.js', 'value': 'function Ilc(){let e=MXe.c(3)'},
    ],
    'manualSmoke': {'required': True, 'reason': 'Shared footer drawer toolbar and overlay routing require interactive TUI verification.'},
  }],
}
Path('packages/footer-drawers/patch.json').write_text(json.dumps(manifest, indent=2) + '\n')
PY
```

- [ ] **Step 5: Run narrow tests and observe expected partial failure**

Run:

```bash
cd "${REPO:-/Users/MAC/Documents/Claude-patch}"
PYTHONPATH=src "${PY:-${REPO:-/Users/MAC/Documents/Claude-patch}/.venv/bin/python}" -m pytest tests/test_footer_drawers_package.py -v -k "manifest_targets or payload_defines or payloads_are_ascii"
```

Expected: `test_footer_drawers_payload_defines_registry_lifecycle_contract` and ASCII/hash tests pass. `test_footer_drawers_manifest_targets_latest_local_2_1_201` still fails because only one operation is present; Task 3 fills the remaining framework ops.

- [ ] **Step 6: Commit package skeleton**

```bash
git add packages/footer-drawers tests/test_footer_drawers_package.py
git commit -m "feat: add footer drawers framework skeleton"
```

---

## Task 3: Fill framework footer target, selection, action, binding, and bar operations

**Files:**
- Modify: `packages/footer-drawers/patch.json`
- Modify: `packages/footer-drawers/payloads/02-footer-render-tick-state.js`
- Modify: `packages/footer-drawers/payloads/03-footer-render-tick-effect.js`
- Modify: `packages/footer-drawers/payloads/04-footer-target-drawers.js`
- Modify: `packages/footer-drawers/payloads/05-footer-target-deps.js`
- Modify: `packages/footer-drawers/payloads/06-footer-selection-flag.js`
- Modify: `packages/footer-drawers/payloads/07-footer-action-wrap-open.js`
- Modify: `packages/footer-drawers/payloads/08-footer-action-wrap-close.js`
- Modify: `packages/footer-drawers/payloads/09-footer-space-binding.js`
- Modify: `packages/footer-drawers/payloads/10-footer-bar-var.js`
- Modify: `packages/footer-drawers/payloads/11-footer-bar-shortcuts-condition.js`
- Modify: `packages/footer-drawers/payloads/12-footer-bar-null-condition.js`
- Modify: `packages/footer-drawers/payloads/13-footer-bar-render.js`
- Test: `tests/test_footer_drawers_package.py`

- [ ] **Step 1: Write exact framework payloads**

Replace placeholder payload files with these exact contents:

```bash
cd "${REPO:-/Users/MAC/Documents/Claude-patch}"
cat > packages/footer-drawers/payloads/02-footer-render-tick-state.js <<'JS'
wt=wo.useRef(!1),[FDv,FDsv]=wo.useState(0)
JS
cat > packages/footer-drawers/payloads/03-footer-render-tick-effect.js <<'JS'
wo.useEffect(()=>{let FDjt=setInterval(()=>{try{let FDr=globalThis.__CODEX_FOOTER_DRAWERS_V1__?.version||0;FDsv(FDr)}catch{}},100);return()=>clearInterval(FDjt)},[]);
JS
cat > packages/footer-drawers/payloads/04-footer-target-drawers.js <<'JS'
[__codexFDAvailable().length&&"drawers",Ui&&"tasks"
JS
cat > packages/footer-drawers/payloads/05-footer-target-deps.js <<'JS'
[Ui,po,Fn,_e,Tr,Ne,FDv]
JS
cat > packages/footer-drawers/payloads/06-footer-selection-flag.js <<'JS'
Mm=Lm==="frame",FDs=Lm==="drawers"
JS
cat > packages/footer-drawers/payloads/07-footer-action-wrap-open.js <<'JS'
Go(__codexFDWrapActions({"footer:up":By,"footer:down":d0,"footer:next":o6,"footer:previous":IR,"footer:openSelected":()=>{
JS
cat > packages/footer-drawers/payloads/08-footer-action-wrap-close.js <<'JS'
return!1},Lm,Rp),{context:"Footer",isActive:!!Lm&&!se});
JS
cat > packages/footer-drawers/payloads/09-footer-space-binding.js <<'JS'
{context:"Footer",bindings:{up:"footer:up","ctrl+p":"footer:up",down:"footer:down","ctrl+n":"footer:down",right:"footer:next",left:"footer:previous",enter:"footer:openSelected",space:"footer:openSelected",escape:"footer:clearSelection",x:"footer:close"}}
JS
cat > packages/footer-drawers/payloads/10-footer-bar-var.js <<'JS'
ue=x.map((Me)=>di.jsx(ELc,{link:Me},Me.key??Me.url)),de=[...[]],FDbar=__codexFDAvailable().length>0?di.jsx(v,{dimColor:!0,children:__codexFDBarText()},"footer-drawers"),fe=n?tNf(s,L,W,F,R,O):[];
JS
cat > packages/footer-drawers/payloads/11-footer-bar-shortcuts-condition.js <<'JS'
if(de.length===0&&!FDbar&&!we&&!le&&!ie&&ue.length===0&&!ve&&n)
JS
cat > packages/footer-drawers/payloads/12-footer-bar-null-condition.js <<'JS'
if(de.length===0&&!FDbar&&!we&&!le&&!ce&&!ie&&ue.length===0&&!ve)return Ys()?di.jsx(v,{children:" "}):null;
JS
cat > packages/footer-drawers/payloads/13-footer-bar-render.js <<'JS'
ue.length>0&&di.jsxs(B,{flexShrink:0,children:[di.jsx(qn,{children:ue}),(we||FDbar||de.length>0)&&di.jsx(v,{dimColor:!0,children:" \xB7 "})]}),we&&di.jsxs(B,{flexShrink:0,children:[we,(FDbar||de.length>0)&&di.jsx(v,{dimColor:!0,children:" \xB7 "})]}),FDbar&&di.jsxs(B,{flexShrink:0,children:[FDbar,de.length>0&&di.jsx(v,{dimColor:!0,children:" \xB7 "})]}),de.length>0&&di.jsx(v,{wrap:"truncate",children:di.jsx(qn,{children:de})})
JS
```

- [ ] **Step 2: Regenerate the framework manifest operations**

Run this script to fill all thirteen operations with correct payload hashes and old-range evidence:

```bash
cd "${REPO:-/Users/MAC/Documents/Claude-patch}"
python3 - <<'PY'
import hashlib, json
from pathlib import Path
module_path = '/$bunfs/root/src/entrypoints/cli.js'
source = Path('.development/artifacts/claude-2.1.201-framework-source-module0.js').read_text()
pkg = Path('packages/footer-drawers')

def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()

def payload(name: str) -> dict:
    data = (pkg / 'payloads' / name).read_bytes()
    return {'path': f'payloads/{name}', 'sha256': hashlib.sha256(data).hexdigest()}

def exact_op(op_id, label, exact, payload_name, behavior):
    assert source.count(exact) == 1, (op_id, source.count(exact))
    return {
        'opId': op_id,
        'label': label,
        'type': 'replace_exact',
        'exact': exact,
        'requireWithinRange': [],
        'oldRangeSha256': sha_text(exact),
        'oldRangeLength': len(exact.encode()),
        'replacement': payload(payload_name),
        'knownBehaviorChange': behavior,
    }

def subspan_op(op_id, label, start, end, sub, payload_name, behavior):
    assert source.count(start) == 1, (op_id, 'start', source.count(start))
    start_i = source.index(start)
    end_i = source.index(end, start_i + len(start)) + len(end)
    context = source[start_i:end_i]
    assert context.count(sub) == 1, (op_id, 'sub', context.count(sub))
    return {
        'opId': op_id,
        'label': label,
        'type': 'replace_substring_within',
        'startMarker': start,
        'endMarker': end,
        'expectedStartMarkerCount': 1,
        'expectedEndMarkerCount': 1,
        'subExact': sub,
        'expectedSubExactCount': 1,
        'oldRangeSha256': sha_text(sub),
        'oldRangeLength': len(sub.encode()),
        'replacement': payload(payload_name),
        'knownBehaviorChange': behavior,
    }

bootstrap_exact = 'function Ilc(){let e=MXe.c(2),t=clc();if(!t)return null;let n;if(e[0]!==t)n=Xd.jsx(B,{position:"absolute",bottom:"100%",left:0,right:0,opaque:!0,children:t}),e[0]=t,e[1]=n;else n=e[1];return n}'
state_cluster_start = 'let[Ss,Ms]=wo.useState(!1),[go,Zo]=wo.useState(!1)'
state_cluster_end = 'Ar=wo.useRef(null);'
effect_anchor = 'wo.useEffect(()=>()=>{if(Ar.current)Ar.current(),Ar.current=null},[]);'
target_statement = 'ss=wo.useMemo(()=>[Ui&&"tasks",po&&"workflows",Fn&&"tmux",_e&&"bagel",Tr&&"bridge",Ne&&"frame"].filter(Boolean),[Ui,po,Fn,_e,Tr,Ne])'
target_context_start = 'ss=wo.useMemo(()=>[Ui&&"tasks"'
target_context_end = ']),yi=Tt((jt)=>jt.workflowFooterIndex)'
selection_flag = 'Mm=Lm==="frame"'
action_open = 'Go({"footer:up":By,"footer:down":d0,"footer:next":o6,"footer:previous":IR,"footer:openSelected":()=>{'
action_close = 'return!1}},{context:"Footer",isActive:!!Lm&&!se});'
footer_binding = '{context:"Footer",bindings:{up:"footer:up","ctrl+p":"footer:up",down:"footer:down","ctrl+n":"footer:down",right:"footer:next",left:"footer:previous",enter:"footer:openSelected",escape:"footer:clearSelection",x:"footer:close"}}'
bar_statement = 'ue=x.map((Me)=>di.jsx(ELc,{link:Me},Me.key??Me.url)),de=[...[]],fe=n?tNf(s,L,W,F,R,O):[];'
bar_shortcuts_cond = 'if(de.length===0&&!we&&!le&&!ie&&ue.length===0&&!ve&&n)'
bar_null_cond = 'if(de.length===0&&!we&&!le&&!ce&&!ie&&ue.length===0&&!ve)return Ys()?di.jsx(v,{children:" "}):null;'
bar_render_tail = 'ue.length>0&&di.jsxs(B,{flexShrink:0,children:[di.jsx(qn,{children:ue}),(we||de.length>0)&&di.jsx(v,{dimColor:!0,children:" \\xB7 "})]}),we&&di.jsxs(B,{flexShrink:0,children:[we,de.length>0&&di.jsx(v,{dimColor:!0,children:" \\xB7 "})]}),de.length>0&&di.jsx(v,{wrap:"truncate",children:di.jsx(qn,{children:de})})'
bar_start = bar_statement
bar_end = 'function tNf(e,t,n,r,o,s){' 
operations = [
    exact_op('fd-bootstrap-and-overlay', 'Footer Drawers registry bootstrap and shared bottom overlay renderer', bootstrap_exact, '01-bootstrap-and-overlay.js', 'Adds shared drawer registry helpers and renders the active registered drawer in the bottom overlay sibling.'),
    subspan_op('fd-footer-render-tick-state', 'Add Footer Drawers render tick state', state_cluster_start, state_cluster_end, 'wt=wo.useRef(!1)', '02-footer-render-tick-state.js', 'Adds local footer render tick state driven by the shared registry version.'),
    {'opId': 'fd-footer-render-tick-effect', 'label': 'Poll Footer Drawers registry version in footer render path', 'type': 'insert_after', 'anchor': effect_anchor, 'expectedAnchorCount': 1, 'insertOrder': 100, 'replacement': payload('03-footer-render-tick-effect.js'), 'knownBehaviorChange': 'Polls the registry version so drawer availability, badge, flash, and open state refresh the footer.'},
    subspan_op('fd-footer-target-drawers', 'Add synthetic drawers footer target before tasks', target_context_start, target_context_end, '[Ui&&"tasks"', '04-footer-target-drawers.js', 'Adds one synthetic drawers target when any registered drawer is available.'),
    subspan_op('fd-footer-target-deps', 'Include Footer Drawers render tick in target deps', target_context_start, target_context_end, '[Ui,po,Fn,_e,Tr,Ne]', '05-footer-target-deps.js', 'Makes the footer target useMemo recompute when registry version changes.'),
    exact_op('fd-footer-selection-flag', 'Add drawers selected flag', selection_flag, '06-footer-selection-flag.js', 'Adds a local selected flag for the synthetic drawers footer target.'),
    exact_op('fd-footer-action-wrap-open', 'Wrap footer action object with Footer Drawers router open', action_open, '07-footer-action-wrap-open.js', 'Routes drawer toolbar/open-panel actions through the shared registry while delegating stock footer targets.'),
    exact_op('fd-footer-action-wrap-close', 'Wrap footer action object with Footer Drawers router close', action_close, '08-footer-action-wrap-close.js', 'Passes active footer selection and setter to the shared drawer action wrapper.'),
    exact_op('fd-footer-space-binding', 'Add space binding to Footer context', footer_binding, '09-footer-space-binding.js', 'Maps space to footer:openSelected for drawer row toggles/opening.'),
    exact_op('fd-footer-bar-var', 'Compute Footer Drawers status-bar segment', bar_statement, '10-footer-bar-var.js', 'Computes a compact registry-rendered drawer toolbar segment.'),
    subspan_op('fd-footer-bar-shortcuts-condition', 'Keep shortcuts hint from masking drawer segment', bar_start, bar_end, bar_shortcuts_cond, '11-footer-bar-shortcuts-condition.js', 'Treats a drawer segment as visible status-bar content before adding the stock shortcuts hint.'),
    subspan_op('fd-footer-bar-null-condition', 'Keep status bar visible for drawer-only segment', bar_start, bar_end, bar_null_cond, '12-footer-bar-null-condition.js', 'Treats a drawer segment as visible status-bar content before returning null.'),
    subspan_op('fd-footer-bar-render', 'Render Footer Drawers status-bar segment', bar_start, bar_end, bar_render_tail, '13-footer-bar-render.js', 'Renders the compact drawer toolbar segment in the existing status row without restating unrelated status content.'),
]
manifest = {
  'schemaVersion': 2,
  'id': 'footer-drawers',
  'name': 'Footer Drawers Framework',
  'description': 'Shared footer toolbar, lifecycle, status bar, and bottom-overlay mount for drawer packages.',
  'packageVersion': '0.1.0',
  'targets': [{
    'sourceIdentity': {'claudeVersion': '2.1.201','versionOutput': '2.1.201 (Claude Code)','sha256': 'a0852d76afc47b30f5cb0b7625ec9a7714cb189f2eeef6c28c77e2be954fb7fd','sizeBytes': 231708784,'platform': 'darwin','arch': 'arm64'},
    'requiredEngine': 'bun_graph_repack',
    'requiredBinaryFormat': 'bun_standalone_macho64',
    'modules': [{'path': module_path,'contentSha256': '46db617a7b13c062fb31595f6244819b11f7cdc6e6fed8e2c3f74a27fb6da1bd','contentLength': 18700756,'operations': operations}],
    'preconditions': [{'type': 'module_must_contain','modulePath': module_path,'value': bootstrap_exact}],
    'postconditions': [
      {'type': 'module_must_contain','modulePath': module_path,'value': '__CODEX_FOOTER_DRAWERS_V1__'},
      {'type': 'module_must_contain','modulePath': module_path,'value': 'function __codexFDWrapActions'},
      {'type': 'module_must_contain','modulePath': module_path,'value': 'function Ilc(){let e=MXe.c(3)'},
      {'type': 'module_must_contain','modulePath': module_path,'value': '"drawers"'},
      {'type': 'module_must_contain','modulePath': module_path,'value': 'space:"footer:openSelected"'},
      {'type': 'module_must_contain','modulePath': module_path,'value': 'FDbar=__codexFDAvailable().length>0'},
      {'type': 'module_must_contain','modulePath': module_path,'value': 'FDbar&&di.jsxs'},
    ],
    'manualSmoke': {'required': True, 'reason': 'Shared footer drawer toolbar and overlay routing require interactive TUI verification.'},
  }],
}
(pkg / 'patch.json').write_text(json.dumps(manifest, indent=2) + '\n')
print('wrote', pkg / 'patch.json')
PY
```

- [ ] **Step 3: Run framework tests**

Run:

```bash
cd "${REPO:-/Users/MAC/Documents/Claude-patch}"
PYTHONPATH=src "${PY:-${REPO:-/Users/MAC/Documents/Claude-patch}/.venv/bin/python}" -m pytest tests/test_footer_drawers_package.py -v -k "footer_drawers and not thin and not reminders_conflicts"
```

Expected: framework manifest/payload/anchor/build-alone tests pass or reach `manual_smoke_pending` for the build-alone test. Thin drawer tests still fail until later tasks.

- [ ] **Step 4: Inspect framework-only build report**

Run:

```bash
cd "${REPO:-/Users/MAC/Documents/Claude-patch}"
PYTHONPATH=src "${PY:-${REPO:-/Users/MAC/Documents/Claude-patch}/.venv/bin/python}" -m claude_monkey build \
  --source /Users/MAC/.local/share/claude/versions/2.1.201 \
  --package packages/footer-drawers \
  --output-dir .development/claude-monkey-builds/footer-drawers-framework-alone \
  --source-version 2.1.201 \
  --source-version-output "2.1.201 (Claude Code)" \
  --platform darwin --arch arm64 --json
python3 - <<'PY'
import json
from pathlib import Path
report = json.loads(Path('.development/claude-monkey-builds/footer-drawers-framework-alone/build-report.json').read_text())
assert report['automatedStatus'] == 'passed'
assert report['status'] == 'manual_smoke_pending'
print(report['status'], report['enabledPatches'])
PY
```

Expected: `manual_smoke_pending ['footer-drawers']`.

- [ ] **Step 5: Commit framework package**

```bash
git add packages/footer-drawers tests/test_footer_drawers_package.py
git commit -m "feat: implement footer drawers framework package"
```

---

## Task 4: Refactor Thinking into a thin framework registrant

**Files:**
- Modify: `packages/thinking-text-drawer/patch.json`
- Modify: `packages/thinking-text-drawer/README.md`
- Modify: `packages/thinking-text-drawer/payloads/01-thinking-text-helpers.js`
- Create: `packages/thinking-text-drawer/payloads/17-register-footer-drawer.js`
- Modify: `tests/test_thinking_text_drawer_package.py`
- Test: `tests/test_footer_drawers_package.py`

- [ ] **Step 1: Update tests for thin Thinking package**

Modify `tests/test_thinking_text_drawer_package.py`:

1. Remove the eight moved footer/overlay op ids from `EXPECTED_OPERATION_IDS`.
2. Add `"thinking-register-footer-drawer"` to `EXPECTED_OPERATION_IDS`.
3. In `test_thinking_text_drawer_is_v3_patch_package`, assert the loaded manifest requires the framework:

```python
assert loaded.requires_packages == ("footer-drawers",)
```

4. In `test_thinking_text_drawer_targets_claude_2_1_201`, remove postcondition requirements for direct footer strings `__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__`, `x closes`, and `thinking-available`, and add `__codexTTDRegisterFooterDrawer`.
5. Replace `test_thinking_text_drawer_x_only_close_contract` with:

```python
def test_thinking_text_drawer_is_thin_footer_registrant() -> None:
    manifest = manifest_json()
    assert manifest["requiresPackages"] == ["footer-drawers"]
    op_ids = {op["opId"] for op in patch_targets()[0]["modules"][0]["operations"]}
    assert op_ids.isdisjoint({
        "thinking-footer-open-state",
        "thinking-footer-target",
        "thinking-footer-selection-flag",
        "thinking-footer-action-wrap-open",
        "thinking-footer-action-wrap-close",
        "thinking-selected-overlay-globals",
        "thinking-bottom-overlay-renderer",
        "thinking-footer-status-bar",
    })
    helper_op = next(op for op in patch_targets()[0]["modules"][0]["operations"] if op["opId"] == "thinking-helpers-before-ypr")
    assert helper_op["type"] == "insert_before"
    assert helper_op["anchor"] == "function Ypr(e){"
    assert helper_op["insertOrder"] == 200
    helpers = read_rel("payloads/01-thinking-text-helpers.js")
    assert "function Ypr(e){" not in helpers
    registration = read_rel("payloads/17-register-footer-drawer.js")
    assert "__codexFDDrawers" in registration
    assert ".register" in registration
    assert "id:\"thinking\"" in registration
    assert "order:200" in registration
    assert "available:()=>!0" in registration
    assert "onOpen:()=>{globalThis.__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__=!0" in registration
    assert "renderPanel:()=>" in registration
    assert "__codexTTDIsOpen" in helpers
    assert "globalThis.__CODEX_THINKING_TEXT_DRAWER_SELECTED_V1__&&globalThis.__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__" not in helpers
    assert "footer:close" not in registration
    assert "footer:clearSelection" not in registration
```

- [ ] **Step 2: Run Thinking tests to verify failure**

Run:

```bash
cd "${REPO:-/Users/MAC/Documents/Claude-patch}"
PYTHONPATH=src "${PY:-${REPO:-/Users/MAC/Documents/Claude-patch}/.venv/bin/python}" -m pytest tests/test_thinking_text_drawer_package.py -v
```

Expected: fails because manifest still has moved op ids, lacks `requiresPackages`, and lacks registration payload.

- [ ] **Step 3: Remove direct footer helper from Thinking helpers and add framework bumping**

Edit `packages/thinking-text-drawer/payloads/01-thinking-text-helpers.js`:

- Delete the whole `function __codexTTDWrapFooterActions(e,t,n,r){...}` definition.
- Remove the trailing `function Ypr(e){` suffix from this helper payload. The manifest will insert the helpers before the stock `function Ypr(e){` anchor instead of replacing that byte span.
- Add these helpers after `function __codexTTDEnsure(){...}`:

```js
function __codexTTDBumpFooter(){try{globalThis.__CODEX_FOOTER_DRAWERS_V1__?.bump?.("thinking")}catch{}}function __codexTTDIsOpen(){try{return globalThis.__CODEX_FOOTER_DRAWERS_V1__?.openId==="thinking"||globalThis.__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__===!0}catch{return globalThis.__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__===!0}}
```

- Replace both occurrences of `globalThis.__CODEX_THINKING_TEXT_DRAWER_SELECTED_V1__&&globalThis.__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__` with `__codexTTDIsOpen()`. This keeps unread/flash false when thinking text arrives while the framework drawer is open.

- In `__codexTTDMarkRead()`, after `e.flashUntil=0`, add `;__codexTTDBumpFooter()` before `return e`.
- In `__codexTTDUpsert(...)`, after setting `t.updatedAt=n.updatedAt`, add `;__codexTTDBumpFooter()` before `__codexTTDRefreshScroll(t,p)`.
- In `__codexTTDMergeStructured(...)`, in the merge branch after `t.updatedAt=i.updatedAt`, add `;__codexTTDBumpFooter()` before `__codexTTDRefreshScroll(t,a)`.

Use a small Python rewrite or manual edit, then verify:

```bash
grep -n "__codexTTDWrapFooterActions" packages/thinking-text-drawer/payloads/01-thinking-text-helpers.js && exit 1 || true
grep -n "__codexTTDBumpFooter" packages/thinking-text-drawer/payloads/01-thinking-text-helpers.js
grep -n "function Ypr(e){" packages/thinking-text-drawer/payloads/01-thinking-text-helpers.js && exit 1 || true
```

Expected: no wrapper function, no trailing `function Ypr(e){`, bump helper and `__codexTTDIsOpen` are present, and the old selected/open unread expression is absent.

- [ ] **Step 4: Create Thinking registration payload**

Create `packages/thinking-text-drawer/payloads/17-register-footer-drawer.js`:

```js
function __codexTTDRegisterFooterDrawer(){let e=globalThis.__CODEX_FOOTER_DRAWERS_V1__;if((!e||typeof e.register!=="function")&&typeof __codexFDDrawers==="function")e=__codexFDDrawers();if(!e||typeof e.register!=="function")return;e.register({id:"thinking",order:200,available:()=>!0,label:()=>"Thinking",badge:()=>{let t=__codexTTDDrawerFrame();return t.empty?null:String(t.entryCount||0)},flash:()=>!!__codexTTDEnsure().unread,onOpen:()=>{globalThis.__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__=!0;globalThis.__CODEX_THINKING_TEXT_DRAWER_SELECTED_V1__=!0;__codexTTDMarkRead();__codexFDBump("thinking:open")},onClose:()=>{globalThis.__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__=!1;globalThis.__CODEX_THINKING_TEXT_DRAWER_SELECTED_V1__=!1;__codexFDBump("thinking:close")},onKey:t=>{let n=__codexTTDDrawerFrame(),r=globalThis.__CODEX_THINKING_TEXT_DRAWER_VIEWPORT_V1__||18;if(t==="up"){__codexTTDClampScroll((n.scroll||0)-3,n.lineCount,r);__codexFDBump("thinking:scroll");return!0}if(t==="down"){__codexTTDClampScroll((n.scroll||0)+3,n.lineCount,r);__codexFDBump("thinking:scroll");return!0}return!1},renderPanel:()=>Xd.jsx(__codexTTDPanel,{})})}function __codexTTDPanel(){let[e,t]=A_.useState(0);A_.useEffect(()=>{let c=setInterval(()=>t(Date.now()),250);return()=>clearInterval(c)},[]);let n=__codexTTDDrawerFrame(),{rows:r}=Er(),o=Math.max(8,Math.min(Math.floor(r*2/3),Math.max(8,r-8))),s=Math.max(4,o-5);globalThis.__CODEX_THINKING_TEXT_DRAWER_VIEWPORT_V1__=s;let i=Math.max(0,Math.min(globalThis.__CODEX_THINKING_TEXT_DRAWER_SCROLL_V1__??0,Math.max(0,(n?.lines?.length??1)-s)));return Xd.jsxs(B,{flexDirection:"column",width:"100%",height:o,overflow:"hidden",borderStyle:"round",borderColor:"permission",borderText:{content:` Thinking ${n?.entryCount??0} entries `,position:"top",align:"start",offset:1},paddingX:1,paddingY:1,marginBottom:1,onWheel:a=>{a.preventDefault();let l=Math.max(0,Math.min(Math.max(0,(n?.lines?.length??1)-s),i+(a.deltaY>0?3:-3)));globalThis.__CODEX_THINKING_TEXT_DRAWER_SCROLL_V1__=l;__codexTTDClampScroll(l,n?.lines?.length??1,s);__codexFDBump("thinking:wheel")},children:[Xd.jsx(v,{dimColor:!0,children:"up/down or mouse wheel scroll | x closes"}),...(n?.lines??[n?.summary??"No thinking captured yet"]).slice(i,i+s).map((a,l)=>Xd.jsx(v,{wrap:"wrap",color:n?.lineKinds?.[i+l]==="header"?"permission":void 0,dimColor:n?.lineKinds?.[i+l]!=="header",children:a},l))]})}__codexTTDRegisterFooterDrawer();
```

This payload is inserted before the stable overlay variable declaration `var MXe,A_,Xd,GKo=2,pmr;` with `insertOrder: 200`. The separate `01-thinking-text-helpers.js` operation is also an insertion before `function Ypr(e){` with `insertOrder: 200`; neither payload replaces or includes the `function Ypr(e){` byte span.

- [ ] **Step 5: Rewrite Thinking manifest operation list**

Run:

```bash
cd "${REPO:-/Users/MAC/Documents/Claude-patch}"
python3 - <<'PY'
import hashlib, json
from pathlib import Path
pkg = Path('packages/thinking-text-drawer')
manifest = json.loads((pkg / 'patch.json').read_text())
manifest['requiresPackages'] = ['footer-drawers']
manifest['description'] = 'Projects raw and structured thinking text into a Footer Drawers framework registrant.'
manifest['risk']['notes'] = 'Local display-only collector package for Claude Code internals; requires footer-drawers and manual smoke.'
manifest['compatibility']['notes'] = 'Requires the shared footer-drawers framework and source identity a0852d76afc47b30f5cb0b7625ec9a7714cb189f2eeef6c28c77e2be954fb7fd.'
module = manifest['patch']['targets'][0]['modules'][0]
keep = {
  'thinking-helpers-before-ypr',
  'thinking-message-start-turn-collector',
  'thinking-message-stop-turn-collector',
  'thinking-live-delta-collector',
  'thinking-signature-collector',
  'thinking-parent-structured-collector',
  'thinking-system-token-estimate',
  'thinking-cancel-salvage-collector',
}
ops = [op for op in module['operations'] if op['opId'] in keep]
for op in ops:
    path = pkg / op['replacement']['path']
    op['replacement']['sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    if op['opId'] == 'thinking-helpers-before-ypr':
        for key in ['exact', 'oldRangeSha256', 'oldRangeLength', 'requireWithinRange']:
            op.pop(key, None)
        op['type'] = 'insert_before'
        op['anchor'] = 'function Ypr(e){'
        op['expectedAnchorCount'] = 1
        op['insertOrder'] = 200
        op['label'] = 'Insert Thinking Text Drawer helpers before hidden attachment filter'
        op['knownBehaviorChange'] = 'Adds display-only Thinking collectors and helpers before the stock hidden attachment filter without claiming the Ypr byte span.'
registration_payload = pkg / 'payloads/17-register-footer-drawer.js'
ops.append({
    'opId': 'thinking-register-footer-drawer',
    'label': 'Register Thinking drawer with Footer Drawers framework',
    'type': 'insert_before',
    'anchor': 'var MXe,A_,Xd,GKo=2,pmr;',
    'expectedAnchorCount': 1,
    'insertOrder': 200,
    'replacement': {'path': 'payloads/17-register-footer-drawer.js', 'sha256': hashlib.sha256(registration_payload.read_bytes()).hexdigest()},
    'knownBehaviorChange': 'Registers the display-only Thinking drawer with footer-drawers; footer routing is framework-owned.',
})
module['operations'] = ops
post = manifest['patch']['targets'][0]['postconditions']
post = [p for p in post if p['value'] not in {'__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__','x closes','thinking-available'}]
post.append({'type':'module_must_contain','modulePath':'/$bunfs/root/src/entrypoints/cli.js','value':'__codexTTDRegisterFooterDrawer'})
post.append({'type':'module_must_contain','modulePath':'/$bunfs/root/src/entrypoints/cli.js','value':'id:"thinking",order:200'})
manifest['patch']['targets'][0]['postconditions'] = post
(pkg / 'patch.json').write_text(json.dumps(manifest, indent=2) + '\n')
PY
```

- [ ] **Step 6: Delete obsolete Thinking direct footer/overlay payloads**

Remove payloads that are no longer referenced by the thin manifest so all remaining files match the new package shape:

```bash
cd "${REPO:-/Users/MAC/Documents/Claude-patch}"
rm -f \
  packages/thinking-text-drawer/payloads/05-footer-open-state.js \
  packages/thinking-text-drawer/payloads/06-footer-target-thinking.js \
  packages/thinking-text-drawer/payloads/07-footer-selection-flag.js \
  packages/thinking-text-drawer/payloads/08-footer-action-wrap-open.js \
  packages/thinking-text-drawer/payloads/09-footer-action-wrap-close.js \
  packages/thinking-text-drawer/payloads/10-selected-overlay-globals.js \
  packages/thinking-text-drawer/payloads/11-bottom-overlay-renderer.js \
  packages/thinking-text-drawer/payloads/12-footer-status-bar.js
```

Expected: only Thinking collector/helper payloads plus `17-register-footer-drawer.js` remain.

- [ ] **Step 7: Update Thinking README**

Replace the standalone conflict paragraph with:

```markdown
This package is now a thin registrant for `packages/footer-drawers`. It keeps the thinking collectors and panel renderer, but the footer target, key routing, toolbar label, and bottom-overlay mount are owned by `footer-drawers`. Build it with `--package packages/footer-drawers --package packages/thinking-text-drawer`.
```

Keep the transcript/request safety paragraph.

- [ ] **Step 8: Run Thinking and framework tests**

Run:

```bash
cd "${REPO:-/Users/MAC/Documents/Claude-patch}"
PYTHONPATH=src "${PY:-${REPO:-/Users/MAC/Documents/Claude-patch}/.venv/bin/python}" -m pytest tests/test_thinking_text_drawer_package.py tests/test_footer_drawers_package.py -v -k "thinking or thin or footer_drawers_manifest or payload"
```

Expected: relevant tests pass; composition tests involving HC/RM may still fail until later tasks.

- [ ] **Step 9: Build framework + Thinking**

Run:

```bash
cd "${REPO:-/Users/MAC/Documents/Claude-patch}"
PYTHONPATH=src "${PY:-${REPO:-/Users/MAC/Documents/Claude-patch}/.venv/bin/python}" -m claude_monkey build \
  --source /Users/MAC/.local/share/claude/versions/2.1.201 \
  --package packages/footer-drawers \
  --package packages/thinking-text-drawer \
  --output-dir .development/claude-monkey-builds/footer-drawers-thinking \
  --source-version 2.1.201 \
  --source-version-output "2.1.201 (Claude Code)" \
  --platform darwin --arch arm64 --json
```

Expected: `automatedStatus` is `passed`, `status` is `manual_smoke_pending`.

- [ ] **Step 10: Commit Thinking migration**

```bash
git add packages/thinking-text-drawer tests/test_thinking_text_drawer_package.py tests/test_footer_drawers_package.py
git commit -m "feat: migrate thinking drawer to footer framework"
```

---

## Task 5: Refactor Hidden Context into a 2.1.201 thin framework registrant

**Files:**
- Modify: `packages/hidden-context-drawer/patch.json`
- Modify: `packages/hidden-context-drawer/README.md`
- Modify/Create payloads under `packages/hidden-context-drawer/payloads/`
- Modify: `tests/test_hidden_context_drawer_package.py`
- Test: `tests/test_footer_drawers_package.py`

- [ ] **Step 1: Discover 2.1.201 Hidden Context retained seams**

Run this scanner and save its output in your implementation notes. It does not create committed files:

```bash
cd "${REPO:-/Users/MAC/Documents/Claude-patch}"
python3 - <<'PY'
from pathlib import Path
src = Path('.development/artifacts/claude-2.1.201-framework-source-module0.js').read_text()
needles = [
  'function Ypr(e){',
  'let Fn=r||Ys()?Ee:qg(Ee,{includeFolded:!0}),_e=Klc(Fn.filter((_r)=>_r.type!=="progress").filter((_r)=>!Ypr(_r)).filter((_r)=>Xlc(_r,de)),ue)',
]
for needle in needles:
    print('\nNEEDLE', needle, 'COUNT', src.count(needle))
    i = src.find(needle)
    if i >= 0:
        print(src[max(0, i-240):i+420])
PY
```

Expected:

- `function Ypr(e){` count is `1`. This is the 2.1.201 hidden-attachment filter anchor and replaces the old 2.1.199 `function Jur(e){` anchor.
- The concrete 2.1.201 projection statement count is `1`:
  `let Fn=r||Ys()?Ee:qg(Ee,{includeFolded:!0}),_e=Klc(Fn.filter((_r)=>_r.type!=="progress").filter((_r)=>!Ypr(_r)).filter((_r)=>Xlc(_r,de)),ue)`.


- [ ] **Step 2: Update Hidden Context tests for target and thin contract**

Modify `tests/test_hidden_context_drawer_package.py`:

- Rename `LIVE_2_1_199` to `LIVE_2_1_201` and point it to `/Users/MAC/.local/share/claude/versions/2.1.201`.
- Update expected binary/module identity to the 2.1.201 constants from Global Constraints.
- Replace `test_hidden_context_drawer_does_not_touch_or_advertise_escape` with a thin registrant version:

```python
def test_hidden_context_drawer_thin_package_keeps_x_only_contract() -> None:
    manifest = json.loads((PACKAGE / "patch.json").read_text(encoding="utf-8"))
    assert manifest["requiresPackages"] == ["footer-drawers"]
    ops = manifest["targets"][0]["modules"][0]["operations"]
    op_ids = {op["opId"] for op in ops}
    assert "hidden-context-register-footer-drawer" in op_ids
    assert "footer-clearselection-consumes-hiddencontext" not in op_ids
    assert "footer-hiddencontext-up-down-scroll" not in op_ids
    assert "uxl-refresh-bottom-overlay" not in op_ids
    helper_op = next(op for op in ops if op["opId"] == "projection-helpers-before-ypr")
    assert helper_op["type"] == "insert_before"
    assert helper_op["anchor"] == "function Ypr(e){"
    assert helper_op["insertOrder"] == 100
    helper_payload = (PACKAGE / "payloads" / "01-projection-helpers-before-ypr-2.1.201.js").read_text(encoding="utf-8")
    assert "function Ypr(e){" not in helper_payload
    assert "function Jur(e){" not in helper_payload
    payload_text = "\n".join(path.read_text(encoding="utf-8") for path in sorted((PACKAGE / "payloads").glob("*.js")))
    assert "__codexFDDrawers" in payload_text
    assert ".register" in payload_text
    assert 'id:"hiddenContext"' in payload_text
    assert "footer:clearSelection" not in payload_text
    assert "inputOwnsEscape" not in payload_text
```

- Add retained/moved op id assertions:

```python
assert {"projection-helpers-before-ypr", "yt-projection-list-drawer-frame", "hidden-context-register-footer-drawer"}.issubset(op_ids)
assert op_ids.isdisjoint({
    "uxl-refresh-bottom-overlay",
    "footer-hidden-context-selected-hook",
    "footer-availability-bar-hidden-context",
    "axf-messagesref-footer-target-frame",
    "footer-hiddencontext-selection-flag",
    "footer-hiddencontext-up-down-scroll",
    "footer-clearselection-consumes-hiddencontext",
    "selected-only-bottom-overlay-hidden-context-globals",
})
```

- [ ] **Step 3: Run Hidden Context tests to verify failure**

Run:

```bash
cd "${REPO:-/Users/MAC/Documents/Claude-patch}"
PYTHONPATH=src "${PY:-${REPO:-/Users/MAC/Documents/Claude-patch}/.venv/bin/python}" -m pytest tests/test_hidden_context_drawer_package.py -v
```

Expected: fails because package still targets 2.1.199 and still has direct footer/overlay ops.

- [ ] **Step 4: Update Hidden Context helper payload**

Edit `packages/hidden-context-drawer/payloads/01-projection-helpers-before-ypr-2.1.201.js`:

- Keep all projection helper functions.
- Add this helper after `function __codexNCHCDrawerFrameFromList` starts or before it:

```js
function __codexNCHCBumpFooter(){try{globalThis.__CODEX_FOOTER_DRAWERS_V1__?.bump?.("hiddenContext")}catch{}}
```

- Inside `__codexNCHCDrawerFrameFromList(e)`, after assigning `globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_FRAME_V13__=u`, call `__codexNCHCBumpFooter();` before `return u`.
- Remove the trailing hidden-filter function suffix entirely. The payload must not contain `function Jur(e){` or `function Ypr(e){`; the manifest inserts it before the stock `function Ypr(e){` anchor.

Verify:

```bash
grep -n "__codexNCHCBumpFooter" packages/hidden-context-drawer/payloads/01-projection-helpers-before-ypr-2.1.201.js
grep -n "function Jur(e){\|function Ypr(e){" packages/hidden-context-drawer/payloads/01-projection-helpers-before-ypr-2.1.201.js && exit 1 || true
```

Expected: bump helper is present; neither `function Jur(e){` nor `function Ypr(e){` appears in the helper payload.

- [ ] **Step 5: Update projection-list frame payload to exact 2.1.201 statement**

Replace `packages/hidden-context-drawer/payloads/02-yt-projection-list-drawer-frame.js` with this exact 2.1.201 replacement. It captures the full projection list `Fn` before `Ypr` hidden attachment filtering:

```js
let Fn=r||Ys()?Ee:qg(Ee,{includeFolded:!0});__codexNCHCDrawerFrameFromList(Fn);let _e=Klc(Fn.filter((_r)=>_r.type!=="progress").filter((_r)=>!Ypr(_r)).filter((_r)=>Xlc(_r,de)),ue)
```

The stock exact string it replaces is:

```js
let Fn=r||Ys()?Ee:qg(Ee,{includeFolded:!0}),_e=Klc(Fn.filter((_r)=>_r.type!=="progress").filter((_r)=>!Ypr(_r)).filter((_r)=>Xlc(_r,de)),ue)
```

Verify both strings are ASCII and that the stock exact string occurs once:

```bash
cd "${REPO:-/Users/MAC/Documents/Claude-patch}"
python3 - <<'PY'
from pathlib import Path
src = Path('.development/artifacts/claude-2.1.201-framework-source-module0.js').read_text()
stock = 'let Fn=r||Ys()?Ee:qg(Ee,{includeFolded:!0}),_e=Klc(Fn.filter((_r)=>_r.type!=="progress").filter((_r)=>!Ypr(_r)).filter((_r)=>Xlc(_r,de)),ue)'
replacement = Path('packages/hidden-context-drawer/payloads/02-yt-projection-list-drawer-frame.js').read_text()
assert src.count(stock) == 1, src.count(stock)
assert replacement == 'let Fn=r||Ys()?Ee:qg(Ee,{includeFolded:!0});__codexNCHCDrawerFrameFromList(Fn);let _e=Klc(Fn.filter((_r)=>_r.type!=="progress").filter((_r)=>!Ypr(_r)).filter((_r)=>Xlc(_r,de)),ue)\n'
assert replacement.isascii()
PY
```

- [ ] **Step 6: Create Hidden Context registration payload**

Create `packages/hidden-context-drawer/payloads/17-register-footer-drawer.js`:

```js
function __codexNCHCRegisterFooterDrawer(){let e=globalThis.__CODEX_FOOTER_DRAWERS_V1__;if((!e||typeof e.register!=="function")&&typeof __codexFDDrawers==="function")e=__codexFDDrawers();if(!e||typeof e.register!=="function")return;e.register({id:"hiddenContext",order:100,available:()=>!!globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_FRAME_V13__?.visible,label:()=>{let t=globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_FRAME_V13__;return t?.tokenCount?`Hidden Context ${t.tokenCount}t`:"Hidden Context"},badge:()=>{let t=globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_FRAME_V13__;return t?.eventCount?String(t.eventCount):null},flash:()=>{let t=globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_FRAME_V13__;return Number(t?.flashUntil||0)>Date.now()},onClose:()=>{globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_OPEN_V13__=!1;__codexFDBump("hiddenContext:close")},onKey:t=>{let n=globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_FRAME_V13__,r=globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_VIEWPORT_V13__||18,o=globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_SCROLL_V13__||0,s=Math.max(0,(n?.lines?.length||1)-r);if(t==="up"){globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_SCROLL_V13__=Math.max(0,o-3);__codexFDBump("hiddenContext:scroll");return!0}if(t==="down"){globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_SCROLL_V13__=Math.min(s,o+3);__codexFDBump("hiddenContext:scroll");return!0}return!1},renderPanel:()=>Xd.jsx(__codexNCHCPanel,{})})}function __codexNCHCPanel(){let[e,t]=A_.useState(0);A_.useEffect(()=>{let c=setInterval(()=>t(Date.now()),250);return()=>clearInterval(c)},[]);let n=globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_FRAME_V13__,{rows:r}=Er(),o=Math.max(8,Math.min(Math.floor(r*2/3),Math.max(8,r-8))),s=Math.max(4,o-5);globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_VIEWPORT_V13__=s;let i=Math.max(0,Math.min(globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_SCROLL_V13__??0,Math.max(0,(n?.lines?.length??1)-s)));return Xd.jsxs(B,{flexDirection:"column",width:"100%",height:o,overflow:"hidden",borderStyle:"round",borderColor:"warning",borderText:{content:` Hidden Context ${n?.tokenCount??0} tokens `,position:"top",align:"start",offset:1},paddingX:1,paddingY:1,marginBottom:1,onWheel:a=>{a.preventDefault();let l=Math.max(0,Math.min(Math.max(0,(n?.lines?.length??1)-s),i+(a.deltaY>0?3:-3)));globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_SCROLL_V13__=l;__codexFDBump("hiddenContext:wheel")},children:[Xd.jsx(v,{dimColor:!0,children:"up/down or mouse wheel scroll | x closes"}),...(n?.lines??[n?.summary??"No hidden context"]).slice(i,i+s).map((a,l)=>Xd.jsx(v,{wrap:"wrap",color:n?.lineKinds?.[i+l]==="header"?"warning":void 0,dimColor:n?.lineKinds?.[i+l]!=="header",children:a},l))]})}__codexNCHCRegisterFooterDrawer();
```

- [ ] **Step 7: Rewrite Hidden Context manifest**

Use this script to preserve only retained ops and compute hashes:

```bash
cd "${REPO:-/Users/MAC/Documents/Claude-patch}"
python3 - <<'PY'
import hashlib, json
from pathlib import Path
pkg = Path('packages/hidden-context-drawer')
source = Path('.development/artifacts/claude-2.1.201-framework-source-module0.js').read_text()
module_path = '/$bunfs/root/src/entrypoints/cli.js'

def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()

def payload(name: str) -> dict:
    data = (pkg / 'payloads' / name).read_bytes()
    assert data.isascii(), name
    return {'path': f'payloads/{name}', 'sha256': hashlib.sha256(data).hexdigest()}

def replace_exact(op_id, label, exact, payload_name, behavior):
    assert source.count(exact) == 1, (op_id, source.count(exact))
    return {'opId': op_id, 'label': label, 'type': 'replace_exact', 'exact': exact, 'requireWithinRange': [], 'oldRangeSha256': sha_text(exact), 'oldRangeLength': len(exact.encode()), 'replacement': payload(payload_name), 'knownBehaviorChange': behavior}

def insert_before(op_id, label, anchor, payload_name, behavior, insert_order):
    assert source.count(anchor) == 1, (op_id, source.count(anchor))
    return {'opId': op_id, 'label': label, 'type': 'insert_before', 'anchor': anchor, 'expectedAnchorCount': 1, 'insertOrder': insert_order, 'replacement': payload(payload_name), 'knownBehaviorChange': behavior}

helper_anchor = 'function Ypr(e){'
projection_exact = 'let Fn=r||Ys()?Ee:qg(Ee,{includeFolded:!0}),_e=Klc(Fn.filter((_r)=>_r.type!=="progress").filter((_r)=>!Ypr(_r)).filter((_r)=>Xlc(_r,de)),ue)'
registration_anchor = 'var MXe,A_,Xd,GKo=2,pmr;'
ops = [
    insert_before('projection-helpers-before-ypr', 'Insert Hidden Context projection helpers before 2.1.201 hidden-filter function', helper_anchor, '01-projection-helpers-before-ypr-2.1.201.js', 'Publishes full projection-list drawer frame before hidden-context filtering and bumps the shared footer registry when frame data changes without claiming the Ypr byte span.', 100),
    replace_exact('yt-projection-list-drawer-frame', 'Capture full projection list before hidden filtering', projection_exact, '02-yt-projection-list-drawer-frame.js', 'Stores drawer frame data from the full projection list before Ypr hidden attachment filtering.'),
    insert_before('hidden-context-register-footer-drawer', 'Register Hidden Context drawer with Footer Drawers framework', registration_anchor, '17-register-footer-drawer.js', 'Registers Hidden Context as an x-close framework drawer without owning footer key routing.', 100),
]
manifest = {
  'schemaVersion': 2,
  'id': 'hidden-context-drawer',
  'name': 'Hidden Context Drawer',
  'description': 'Hidden Context drawer content seam plus Footer Drawers registration for Claude Code 2.1.201.',
  'packageVersion': '2.1.201-framework.1',
  'requiresPackages': ['footer-drawers'],
  'targets': [{
    'sourceIdentity': {'claudeVersion': '2.1.201', 'versionOutput': '2.1.201 (Claude Code)', 'sha256': 'a0852d76afc47b30f5cb0b7625ec9a7714cb189f2eeef6c28c77e2be954fb7fd', 'sizeBytes': 231708784, 'platform': 'darwin', 'arch': 'arm64'},
    'requiredEngine': 'bun_graph_repack',
    'requiredBinaryFormat': 'bun_standalone_macho64',
    'modules': [{'path': module_path, 'contentSha256': '46db617a7b13c062fb31595f6244819b11f7cdc6e6fed8e2c3f74a27fb6da1bd', 'contentLength': 18700756, 'operations': ops}],
    'preconditions': [{'type': 'module_must_contain', 'modulePath': module_path, 'value': projection_exact}],
    'postconditions': [
      {'type': 'module_must_contain', 'modulePath': module_path, 'value': '__CODEX_HIDDEN_CONTEXT_DRAWER_FRAME_V13__'},
      {'type': 'module_must_contain', 'modulePath': module_path, 'value': '__codexNCHCRegisterFooterDrawer'},
      {'type': 'module_must_contain', 'modulePath': module_path, 'value': 'id:"hiddenContext"'},
    ],
    'manualSmoke': {'required': True, 'reason': 'Hidden Context drawer UI requires interactive footer/overlay smoke.'},
  }],
}
(pkg / 'patch.json').write_text(json.dumps(manifest, indent=2) + '\n')
print('wrote', pkg / 'patch.json')
PY
```

- [ ] **Step 8: Delete obsolete Hidden Context direct footer/overlay/prop payloads**

Delete stale payload files that are no longer referenced and would violate thin-package scans:

```bash
cd "${REPO:-/Users/MAC/Documents/Claude-patch}"
rm -f \
  packages/hidden-context-drawer/payloads/01-projection-helpers-before-jlr.js \
  packages/hidden-context-drawer/payloads/03-axf-messagesref-footer-target-frame.js \
  packages/hidden-context-drawer/payloads/04-axf-pass-hiddencontextframe-to-cxc.js \
  packages/hidden-context-drawer/payloads/05-vwf-accept-hiddencontextframe-prop.js \
  packages/hidden-context-drawer/payloads/06-vwf-pass-hiddencontextframe-to-exc-cache.js \
  packages/hidden-context-drawer/payloads/07-exc-accept-hiddencontextframe-prop.js \
  packages/hidden-context-drawer/payloads/08-exc-pass-hiddencontextframe-to-bwf-cache.js \
  packages/hidden-context-drawer/payloads/09-bwf-accept-hiddencontextframe-prop.js \
  packages/hidden-context-drawer/payloads/10-footer-hiddencontext-selection-flag.js \
  packages/hidden-context-drawer/payloads/11-footer-hidden-context-selected-hook.js \
  packages/hidden-context-drawer/payloads/12-footer-hiddencontext-up-down-scroll.js \
  packages/hidden-context-drawer/payloads/13-footer-clearselection-consumes-hiddencontext.js \
  packages/hidden-context-drawer/payloads/14-selected-only-bottom-overlay-hidden-context-globals.js \
  packages/hidden-context-drawer/payloads/15-uxl-refresh-bottom-overlay.js \
  packages/hidden-context-drawer/payloads/16-footer-availability-bar-hidden-context.js
```

Expected: Hidden Context payload directory contains only `01-projection-helpers-before-ypr-2.1.201.js`, `02-yt-projection-list-drawer-frame.js`, and `17-register-footer-drawer.js`.

- [ ] **Step 9: Run Hidden Context and framework tests**

Run:

```bash
cd "${REPO:-/Users/MAC/Documents/Claude-patch}"
PYTHONPATH=src "${PY:-${REPO:-/Users/MAC/Documents/Claude-patch}/.venv/bin/python}" -m pytest tests/test_hidden_context_drawer_package.py tests/test_footer_drawers_package.py -v -k "hidden or footer_drawers_manifest or payload or thin"
```

Expected: Hidden Context package tests pass; framework composition tests involving Reminders may still fail.

- [ ] **Step 10: Build framework + Hidden Context**

Run:

```bash
cd "${REPO:-/Users/MAC/Documents/Claude-patch}"
PYTHONPATH=src "${PY:-${REPO:-/Users/MAC/Documents/Claude-patch}/.venv/bin/python}" -m claude_monkey build \
  --source /Users/MAC/.local/share/claude/versions/2.1.201 \
  --package packages/footer-drawers \
  --package packages/hidden-context-drawer \
  --output-dir .development/claude-monkey-builds/footer-drawers-hidden-context \
  --source-version 2.1.201 \
  --source-version-output "2.1.201 (Claude Code)" \
  --platform darwin --arch arm64 --json
```

Expected: `automatedStatus` is `passed`, `status` is `manual_smoke_pending`.

- [ ] **Step 11: Commit Hidden Context migration**

```bash
git add packages/hidden-context-drawer tests/test_hidden_context_drawer_package.py tests/test_footer_drawers_package.py
git commit -m "feat: migrate hidden context drawer to footer framework"
```

---

## Task 6: Refactor Reminders Manager into a 2.1.201 thin framework registrant

**Files:**
- Modify: `packages/reminders-manager/patch.json`
- Modify: `packages/reminders-manager/README.md`
- Create/Rename: `packages/reminders-manager/payloads/rm-attachment-wrapper-deny-2.1.201.js`
- Create/Rename: `packages/reminders-manager/payloads/rm-xye-runtime-filter-2.1.201.js`
- Create: `packages/reminders-manager/payloads/rm-register-footer-drawer-2.1.201.js`
- Modify: `tests/test_reminders_manager.py`
- Test: `tests/test_footer_drawers_package.py`

- [ ] **Step 1: Verify the concrete 2.1.201 retained Reminders seams**

Historical note: the old 2.1.199 `ug` and `Hze` functions are renamed in 2.1.201. The equivalent concrete 2.1.201 seams are:

- attachment label wrapper: `async function _g(e,t){...}`
- attachment generator: `async function*XYe(e,t,n,r,o,s,i,a){...}`

Run:

```bash
cd "${REPO:-/Users/MAC/Documents/Claude-patch}"
python3 - <<'PY'
from pathlib import Path
src = Path('.development/artifacts/claude-2.1.201-framework-source-module0.js').read_text()
anchors = {
  'attachment_wrapper_start': 'async function _g(e,t){',
  'attachment_wrapper_end': 'async function len(e,t){',
  'attachment_generator_start': 'async function*XYe(e,t,n,r,o,s,i,a){',
  'attachment_generator_end': 'async function E5l(e){',
}
for name, value in anchors.items():
    print(name, src.count(value))
    assert src.count(value) == 1, (name, src.count(value))
old_wrapper = src[src.index(anchors['attachment_wrapper_start']):src.index(anchors['attachment_wrapper_end'])]
old_generator = src[src.index(anchors['attachment_generator_start']):src.index(anchors['attachment_generator_end'])]
print('wrapper_sha', __import__('hashlib').sha256(old_wrapper.encode()).hexdigest(), len(old_wrapper.encode()))
print('generator_sha', __import__('hashlib').sha256(old_generator.encode()).hexdigest(), len(old_generator.encode()))
assert 'G("tengu_attachment_compute_duration"' in old_wrapper
assert 'G("tengu_attachments"' in old_generator
assert 'yield ki(c,o)' in old_generator
PY
```

Expected:

```text
attachment_wrapper_start 1
attachment_wrapper_end 1
attachment_generator_start 1
attachment_generator_end 1
wrapper_sha 8d9b098b1d2bcef25a34776a820ee94b7398fcc40de77cf9da68a4d72bffac0f 602
generator_sha 3db820176d27dcac53b2a845322ca30fb882e7ebcf4e8c141ac5c6e423f208e6 180
```

- [ ] **Step 2: Update Reminders tests first**

Modify `tests/test_reminders_manager.py`:

- Update constants to 2.1.201 binary/module identity from Global Constraints.
- Change payload paths from `2.1.199` filenames to `2.1.201` filenames.
- Assert `manifest.requires_packages == ("footer-drawers",)` and `manifest.conflicts_with_packages == ("upstream-attachment-suppression",)`.
- Assert moved footer/overlay op ids are absent and retained op ids are renamed without the `-2-1-199` suffix:

```python
op_ids = {op.op_id for target in manifest.targets for module in target.modules for op in module.operations}
assert {"rm-attachment-wrapper-deny", "rm-xye-runtime-filter", "rm-register-footer-drawer"}.issubset(op_ids)
assert op_ids.isdisjoint({
    "rm-footer-target-append-2-1-199",
    "rm-wo-wrap-open-2-1-199",
    "rm-wo-wrap-close-2-1-199",
    "rm-footer-space-binding-2-1-199",
    "rm-bar-segment-2-1-199",
    "rm-overlay-default-2-1-199",
    "rm-overlay-bde-2-1-199",
})
```

- Add a registration payload assertion:

```python
registration = (PACKAGE_DIR / "payloads" / "rm-register-footer-drawer-2.1.201.js").read_text(encoding="utf-8")
assert "__codexFDDrawers" in registration
assert ".register" in registration
assert 'id:"reminders"' in registration
assert "order:300" in registration
assert "available:()=>!0" in registration
assert "footer:close" not in registration
assert "footer:clearSelection" not in registration
```

- [ ] **Step 3: Run Reminders tests to verify failure**

Run:

```bash
cd "${REPO:-/Users/MAC/Documents/Claude-patch}"
PYTHONPATH=src "${PY:-${REPO:-/Users/MAC/Documents/Claude-patch}/.venv/bin/python}" -m pytest tests/test_reminders_manager.py -v
```

Expected: target identity, payload path, relationship, and moved-op assertions fail.

- [ ] **Step 4: Create retained Reminders payloads for 2.1.201**

Create `packages/reminders-manager/payloads/rm-attachment-wrapper-deny-2.1.201.js`. It must contain the retained session deny helpers, no `__codexRMWrapActions`, no `__codexRMPanel`, and the exact 2.1.201 `_g` function with the deny guard immediately after the opening brace:

```js
function __codexRMState(){let e=globalThis.__CODEX_REMINDERS_MANAGER_V1__;if(!e||!e.deny)e=globalThis.__CODEX_REMINDERS_MANAGER_V1__={deny:{todo_reminder:!0,task_reminder:!0,tool_search_usage_reminder:!0,token_usage:!0,total_tokens_reminder:!0,budget_usd:!0,output_token_usage:!0},version:0};return e}function __codexRMUIState(){let e=__codexRMState();if(e.cursor===void 0)e.cursor=0;return e}function __codexRMFamilies(){return["todo_reminder","task_reminder","tool_search_usage_reminder","token_usage","total_tokens_reminder","budget_usd","output_token_usage"]}function __codexRMLabels(){return["all reminders","todo reminders","task reminders","tool search usage","token usage","total tokens","budget (USD)","output token usage"]}function __codexRMBump(){let e=__codexRMState();e.version=(e.version||0)+1;try{globalThis.__CODEX_FOOTER_DRAWERS_V1__?.bump?.("reminders")}catch{}}function __codexRMDenyLabel(e){let t=__codexRMState().deny;if(e==="todo_reminders")return t.todo_reminder===!0&&t.task_reminder===!0;if(e==="tool_search_usage_reminder")return t.tool_search_usage_reminder===!0;if(e==="token_usage")return t.token_usage===!0;if(e==="total_tokens_reminder")return t.total_tokens_reminder===!0;if(e==="budget_usd")return t.budget_usd===!0;if(e==="output_token_usage")return t.output_token_usage===!0;return!1}function __codexRMDenyAttachment(e){if(!e||typeof e.type!=="string")return!1;let t=__codexRMState().deny;return Object.prototype.hasOwnProperty.call(t,e.type)&&t[e.type]===!0}async function _g(e,t){if(__codexRMDenyLabel(e))return[];let n=Date.now();try{let r=await t(),o=Date.now()-n;if(Math.random()<0.05){let s=r.filter((i)=>i!==void 0&&i!==null).reduce((i,a)=>i+De(a).length,0);G("tengu_attachment_compute_duration",{label:e,duration_ms:o,attachment_size_bytes:s,attachment_count:r.length})}return r}catch(r){let o=Date.now()-n;if(Math.random()<0.05)G("tengu_attachment_compute_duration",{label:e,duration_ms:o,error:!0});if(r instanceof jM)C(`Attachment image resize failed in ${e}: ${r.message}`,{level:"error"});else He(qo(sr(r),"attachment generator failed"));return C6(`Attachment error in ${e}`,r),[]}}
```

Create `packages/reminders-manager/payloads/rm-xye-runtime-filter-2.1.201.js` as the exact 2.1.201 `XYe` generator replacement with the attachment object filter before telemetry/yield:

```js
async function*XYe(e,t,n,r,o,s,i,a){let l=await i5l(e,t,n,r,s,i,a);l=l.filter((c)=>!__codexRMDenyAttachment(c));if(l.length===0)return;G("tengu_attachments",{attachment_types:l.map((c)=>c.type)});for(let c of l)yield ki(c,o)}
```

Verify:

```bash
cd "${REPO:-/Users/MAC/Documents/Claude-patch}"
python3 - <<'PY'
from pathlib import Path
wrapper_payload = Path('packages/reminders-manager/payloads/rm-attachment-wrapper-deny-2.1.201.js').read_text()
filter_payload = Path('packages/reminders-manager/payloads/rm-xye-runtime-filter-2.1.201.js').read_text()
assert wrapper_payload.isascii()
assert filter_payload.isascii()
assert '__codexRMWrapActions' not in wrapper_payload
assert '__codexRMPanel' not in wrapper_payload
assert 'async function _g(e,t){if(__codexRMDenyLabel(e))return[];' in wrapper_payload
assert 'async function*XYe(e,t,n,r,o,s,i,a){let l=await i5l(e,t,n,r,s,i,a);l=l.filter((c)=>!__codexRMDenyAttachment(c));' in filter_payload
PY
```

- [ ] **Step 5: Create Reminders registration/panel payload**

Create `packages/reminders-manager/payloads/rm-register-footer-drawer-2.1.201.js`:

```js
function __codexRMRegisterFooterDrawer(){let e=globalThis.__CODEX_FOOTER_DRAWERS_V1__;if((!e||typeof e.register!=="function")&&typeof __codexFDDrawers==="function")e=__codexFDDrawers();if(!e||typeof e.register!=="function")return;e.register({id:"reminders",order:300,available:()=>!0,label:()=>"Reminders",badge:()=>{let t=__codexRMState().deny,n=__codexRMFamilies(),r=n.filter(o=>t[o]===!0).length;return String(n.length-r)+"/"+String(n.length)},onClose:()=>{__codexRMBump()},onKey:t=>{let n=__codexRMUIState(),r=__codexRMFamilies(),o=__codexRMState().deny;if(t==="up"){n.cursor=Math.max(0,n.cursor-1);__codexRMBump();return!0}if(t==="down"){n.cursor=Math.min(r.length,n.cursor+1);__codexRMBump();return!0}if(t==="openSelected"){if(n.cursor===0){let s=r.some(i=>o[i]===!0);for(let i of r)o[i]=!s}else{let s=r[n.cursor-1];o[s]=o[s]!==!0}__codexRMBump();return!0}return!1},renderPanel:()=>Xd.jsx(__codexRMPanel,{})})}function __codexRMPanel(){let[e,t]=A_.useState(0);A_.useEffect(()=>{let u=setInterval(()=>t(Date.now()),250);return()=>clearInterval(u)},[]);let n=__codexRMUIState(),r=__codexRMState().deny,o=__codexRMFamilies(),s=__codexRMLabels(),i=o.some(u=>r[u]===!0),a=o.every(u=>r[u]===!0),l=u=>u===0?a?"[ ]":i?"[~]":"[x]":r[o[u-1]]===!0?"[ ]":"[x]",c=[];for(let u=0;u<8;u++){let d=u===n.cursor;c.push(Xd.jsx(B,{width:"100%",backgroundColor:d?"blue":void 0,children:Xd.jsx(v,{color:d?"white":void 0,bold:d,children:`${d?"\\u276F ":"  "}${l(u)} ${s[u]}`})},u));if(u===0)c.push(Xd.jsx(v,{dimColor:!0,children:"\\u2500".repeat(30)},"rm-sep"))}return Xd.jsx(B,{flexDirection:"column",width:"100%",borderStyle:"round",borderColor:"warning",borderText:{content:" Reminders \\xB7 up/down move \\xB7 enter/space toggles \\xB7 x closes ",position:"top",align:"start",offset:1},paddingX:1,marginBottom:1,children:c})}__codexRMRegisterFooterDrawer();
```

- [ ] **Step 6: Rewrite Reminders manifest**

Generate the schema-v2 manifest with the concrete 2.1.201 ranges and package relationships:

```bash
cd "${REPO:-/Users/MAC/Documents/Claude-patch}"
python3 - <<'PY'
import hashlib, json
from pathlib import Path
pkg = Path('packages/reminders-manager')
source = Path('.development/artifacts/claude-2.1.201-framework-source-module0.js').read_text()
module_path = '/$bunfs/root/src/entrypoints/cli.js'

def sha_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()

def payload(name: str) -> dict:
    data = (pkg / 'payloads' / name).read_bytes()
    assert data.isascii(), name
    return {'path': f'payloads/{name}', 'sha256': hashlib.sha256(data).hexdigest()}

def replace_between(op_id, label, start, end, payload_name, behavior):
    assert source.count(start) == 1, (op_id, 'start', source.count(start))
    assert source.count(end) == 1, (op_id, 'end', source.count(end))
    start_i = source.index(start)
    end_i = source.index(end, start_i + len(start))
    old = source[start_i:end_i]
    return {'opId': op_id, 'label': label, 'type': 'replace_between', 'startMarker': start, 'endMarker': end, 'expectedStartMarkerCount': 1, 'expectedEndMarkerCount': 1, 'oldRangeSha256': sha_text(old), 'oldRangeLength': len(old.encode()), 'replacement': payload(payload_name), 'knownBehaviorChange': behavior}

def insert_before(op_id, label, anchor, payload_name, behavior, insert_order):
    assert source.count(anchor) == 1, (op_id, source.count(anchor))
    return {'opId': op_id, 'label': label, 'type': 'insert_before', 'anchor': anchor, 'expectedAnchorCount': 1, 'insertOrder': insert_order, 'replacement': payload(payload_name), 'knownBehaviorChange': behavior}

wrapper_start = 'async function _g(e,t){'
wrapper_end = 'async function len(e,t){'
generator_start = 'async function*XYe(e,t,n,r,o,s,i,a){'
generator_end = 'async function E5l(e){'
registration_anchor = 'var MXe,A_,Xd,GKo=2,pmr;'
ops = [
    replace_between('rm-attachment-wrapper-deny', 'Runtime deny gate for reminder attachment labels', wrapper_start, wrapper_end, 'rm-attachment-wrapper-deny-2.1.201.js', 'Suppresses selected reminder/accounting attachment families before attachment generation.'),
    replace_between('rm-xye-runtime-filter', 'Runtime filter for reminder attachment objects', generator_start, generator_end, 'rm-xye-runtime-filter-2.1.201.js', 'Filters selected reminder/accounting attachment objects before telemetry and transcript construction.'),
    insert_before('rm-register-footer-drawer', 'Register Reminders drawer with Footer Drawers framework', registration_anchor, 'rm-register-footer-drawer-2.1.201.js', 'Registers Reminders as an always-available framework drawer with row cursor/toggle handling.', 300),
]
manifest = {
  'schemaVersion': 2,
  'id': 'reminders-manager',
  'name': 'Reminders Manager',
  'description': 'Runtime reminder/accounting suppression plus Footer Drawers registration for Claude Code 2.1.201.',
  'packageVersion': '2.1.201-framework.1',
  'requiresPackages': ['footer-drawers'],
  'conflictsWithPackages': ['upstream-attachment-suppression'],
  'targets': [{
    'sourceIdentity': {'claudeVersion': '2.1.201', 'versionOutput': '2.1.201 (Claude Code)', 'sha256': 'a0852d76afc47b30f5cb0b7625ec9a7714cb189f2eeef6c28c77e2be954fb7fd', 'sizeBytes': 231708784, 'platform': 'darwin', 'arch': 'arm64'},
    'requiredEngine': 'bun_graph_repack',
    'requiredBinaryFormat': 'bun_standalone_macho64',
    'modules': [{'path': module_path, 'contentSha256': '46db617a7b13c062fb31595f6244819b11f7cdc6e6fed8e2c3f74a27fb6da1bd', 'contentLength': 18700756, 'operations': ops}],
    'preconditions': [{'type': 'module_must_contain', 'modulePath': module_path, 'value': 'G("tengu_attachments"'}],
    'postconditions': [
      {'type': 'module_must_contain', 'modulePath': module_path, 'value': 'function __codexRMState('},
      {'type': 'module_must_contain', 'modulePath': module_path, 'value': 'function __codexRMDenyLabel('},
      {'type': 'module_must_contain', 'modulePath': module_path, 'value': 'function __codexRMRegisterFooterDrawer('},
      {'type': 'module_must_contain', 'modulePath': module_path, 'value': 'id:"reminders"'},
    ],
    'manualSmoke': {'required': True, 'reason': 'Runtime reminders drawer rows/toggles require interactive footer smoke.'},
  }],
}
(pkg / 'patch.json').write_text(json.dumps(manifest, indent=2) + '\n')
print('wrote', pkg / 'patch.json')
PY
```

- [ ] **Step 7: Delete obsolete Reminders direct footer/overlay payloads**

Remove old 2.1.199 payload files that are no longer referenced by the 2.1.201 thin manifest:

```bash
cd "${REPO:-/Users/MAC/Documents/Claude-patch}"
rm -f \
  packages/reminders-manager/payloads/rm-filter-before-li-2.1.199.js \
  packages/reminders-manager/payloads/rm-filter-labels-before-ug-2.1.199.js \
  packages/reminders-manager/payloads/rm-footer-target-append-2.1.199.js \
  packages/reminders-manager/payloads/rm-wo-wrap-open-2.1.199.js \
  packages/reminders-manager/payloads/rm-wo-wrap-close-2.1.199.js \
  packages/reminders-manager/payloads/rm-footer-space-binding-2.1.199.js \
  packages/reminders-manager/payloads/rm-bar-segment-2.1.199.js \
  packages/reminders-manager/payloads/rm-overlay-default-2.1.199.js \
  packages/reminders-manager/payloads/rm-overlay-bde-2.1.199.js
```

Expected: Reminders payload directory contains only `rm-attachment-wrapper-deny-2.1.201.js`, `rm-xye-runtime-filter-2.1.201.js`, and `rm-register-footer-drawer-2.1.201.js`.

- [ ] **Step 8: Update Reminders README**

Replace the composition section with:

```markdown
## How it composes

Deny half: two retained seams (`_g` label wrapper gate, `XYe` object filter) made runtime-lookups against `globalThis.__CODEX_REMINDERS_MANAGER_V1__.deny`.

UI half: registered with `packages/footer-drawers`. The framework owns the footer target, left/right toolbar navigation, x close, status-bar label, and bottom overlay mount.

- Requires `footer-drawers`.
- Conflicts with `upstream-attachment-suppression`; both own the reminder attachment deny/filter seam family.
- Can ship with `hidden-context-drawer` and `thinking-text-drawer` through the framework.
```

- [ ] **Step 9: Run Reminders tests and UAS conflict test**

Run:

```bash
cd "${REPO:-/Users/MAC/Documents/Claude-patch}"
PYTHONPATH=src "${PY:-${REPO:-/Users/MAC/Documents/Claude-patch}/.venv/bin/python}" -m pytest tests/test_reminders_manager.py tests/test_footer_drawers_package.py -v -k "reminders or uas"
```

Expected: Reminders package tests pass; the matching 2.1.201 UAS fixture conflict test passes with `patch_conflict:package_conflict:reminders-manager:upstream-attachment-suppression`. The real current UAS package remains out of this implementation scope and may fail earlier with `source_identity_mismatch` until retargeted separately.

- [ ] **Step 10: Build framework + Reminders**

Run:

```bash
cd "${REPO:-/Users/MAC/Documents/Claude-patch}"
PYTHONPATH=src "${PY:-${REPO:-/Users/MAC/Documents/Claude-patch}/.venv/bin/python}" -m claude_monkey build \
  --source /Users/MAC/.local/share/claude/versions/2.1.201 \
  --package packages/footer-drawers \
  --package packages/reminders-manager \
  --output-dir .development/claude-monkey-builds/footer-drawers-reminders \
  --source-version 2.1.201 \
  --source-version-output "2.1.201 (Claude Code)" \
  --platform darwin --arch arm64 --json
```

Expected: `automatedStatus` is `passed`, `status` is `manual_smoke_pending`.

- [ ] **Step 11: Commit Reminders migration**

```bash
git add packages/reminders-manager tests/test_reminders_manager.py tests/test_footer_drawers_package.py
git commit -m "feat: migrate reminders manager to footer framework"
```

---

## Task 7: Full composition matrix and stale-package failure tests

**Files:**
- Modify: `tests/test_footer_drawers_package.py`
- Read: `packages/*/patch.json`

- [ ] **Step 1: Add all-success composition matrix tests**

Append to `tests/test_footer_drawers_package.py`:

```python
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
```

- [ ] **Step 2: Add required-package missing tests**

Append:

```python
@pytest.mark.parametrize(("name", "package_dir"), [("hc", HC), ("thinking", THINKING), ("reminders", REMINDERS)])
def test_thin_drawer_without_framework_fails_required_package_missing(tmp_path, name, package_dir) -> None:
    report = _build_packages(tmp_path, f"missing-framework-{name}", [package_dir])
    assert report.status == "failed"
    assert report.failureReason is not None
    assert "patch_conflict:required_package_missing" in report.failureReason
    assert f":{package_dir.name}:footer-drawers" in report.failureReason
```

- [ ] **Step 3: Add stale direct package fail-closed fixture test**

Append a small fixture package that deliberately owns a framework seam but targets 2.1.201:

```python
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
```

- [ ] **Step 4: Run full footer framework matrix tests**

Run:

```bash
cd "${REPO:-/Users/MAC/Documents/Claude-patch}"
PYTHONPATH=src "${PY:-${REPO:-/Users/MAC/Documents/Claude-patch}/.venv/bin/python}" -m pytest tests/test_footer_drawers_package.py -v
```

Expected: all tests pass or skip only because the local 2.1.201 binary/module dump is unavailable/mismatched.

- [ ] **Step 5: Commit composition matrix tests**

```bash
git add tests/test_footer_drawers_package.py
git commit -m "test: cover footer drawers composition matrix"
```

---

## Task 8: Full build, docs, and verification pass

**Files:**
- Modify: `packages/footer-drawers/README.md`
- Modify: `packages/hidden-context-drawer/README.md`
- Modify: `packages/thinking-text-drawer/README.md`
- Modify: `packages/reminders-manager/README.md`
- Read: build reports under `.development/claude-monkey-builds/`

- [ ] **Step 1: Build the full ship set**

Run:

```bash
cd "${REPO:-/Users/MAC/Documents/Claude-patch}"
PYTHONPATH=src "${PY:-${REPO:-/Users/MAC/Documents/Claude-patch}/.venv/bin/python}" -m claude_monkey build \
  --source /Users/MAC/.local/share/claude/versions/2.1.201 \
  --package packages/footer-drawers \
  --package packages/hidden-context-drawer \
  --package packages/thinking-text-drawer \
  --package packages/reminders-manager \
  --output-dir .development/claude-monkey-builds/footer-drawers-all-three \
  --source-version 2.1.201 \
  --source-version-output "2.1.201 (Claude Code)" \
  --platform darwin --arch arm64 --json
```

Expected: report has `automatedStatus: passed`, `status: manual_smoke_pending`, and enabled patches in the same order as the command.

- [ ] **Step 2: Verify copied binary identity, signing, and report**

Run:

```bash
cd "${REPO:-/Users/MAC/Documents/Claude-patch}"
.development/claude-monkey-builds/footer-drawers-all-three/claude --version
codesign --verify --deep --strict --verbose=4 .development/claude-monkey-builds/footer-drawers-all-three/claude
python3 - <<'PY'
import json
from pathlib import Path
report = json.loads(Path('.development/claude-monkey-builds/footer-drawers-all-three/build-report.json').read_text())
assert report['automatedStatus'] == 'passed'
assert report['status'] == 'manual_smoke_pending'
assert report['activationEligible'] is False
print(report['enabledPatches'])
print(report['status'])
PY
```

Expected:

```text
2.1.201 (Claude Code)
```

Codesign verify exits `0`. Python prints enabled patches and `manual_smoke_pending`.

- [ ] **Step 3: Run targeted package tests**

Run:

```bash
cd "${REPO:-/Users/MAC/Documents/Claude-patch}"
PYTHONPATH=src "${PY:-${REPO:-/Users/MAC/Documents/Claude-patch}/.venv/bin/python}" -m pytest \
  tests/test_footer_drawers_package.py \
  tests/test_hidden_context_drawer_package.py \
  tests/test_thinking_text_drawer_package.py \
  tests/test_reminders_manager.py \
  -v
```

Expected: all tests pass or skip only for missing local live source/module dump. No failure may be ignored.

- [ ] **Step 4: Run a broader safe suite**

Run:

```bash
cd "${REPO:-/Users/MAC/Documents/Claude-patch}"
PYTHONPATH=src "${PY:-${REPO:-/Users/MAC/Documents/Claude-patch}/.venv/bin/python}" -m pytest tests/test_manifest_v2.py tests/test_module_patch.py tests/test_builder_v15.py tests/test_package_model_v3.py tests/test_footer_drawers_package.py -v
```

Expected: pass. If `tests/test_reference_packages.py` is red because unrelated untracked package inventory is dirty, document it and do not fix it in this branch.

- [ ] **Step 5: Update README build commands**

Ensure each README includes the full framework command shape. Example for the full ship set:

```bash
cd "${REPO:-/Users/MAC/Documents/Claude-patch}"
PYTHONPATH=src "${PY:-${REPO:-/Users/MAC/Documents/Claude-patch}/.venv/bin/python}" -m claude_monkey build \
  --source /Users/MAC/.local/share/claude/versions/2.1.201 \
  --package packages/footer-drawers \
  --package packages/hidden-context-drawer \
  --package packages/thinking-text-drawer \
  --package packages/reminders-manager \
  --output-dir .development/claude-monkey-builds/footer-drawers-all-three \
  --source-version 2.1.201 \
  --source-version-output "2.1.201 (Claude Code)" \
  --platform darwin --arch arm64
```

Each drawer README must say:

- Requires `footer-drawers`.
- Does not own footer target/action/status/overlay seams directly.
- Build reports end at `manual_smoke_pending` until interactive smoke is completed.

- [ ] **Step 6: Final diff and no unrelated changes check**

Run:

```bash
cd "${REPO:-/Users/MAC/Documents/Claude-patch}"
git status --short
git diff -- packages/footer-drawers packages/hidden-context-drawer packages/thinking-text-drawer packages/reminders-manager tests/test_footer_drawers_package.py tests/test_hidden_context_drawer_package.py tests/test_thinking_text_drawer_package.py tests/test_reminders_manager.py
```

Expected: diff is limited to files in this plan. Existing unrelated dirty files may remain in `git status`; do not stage them.

- [ ] **Step 7: Commit final docs/verification cleanup**

```bash
git add packages/footer-drawers packages/hidden-context-drawer packages/thinking-text-drawer packages/reminders-manager tests/test_footer_drawers_package.py tests/test_hidden_context_drawer_package.py tests/test_thinking_text_drawer_package.py tests/test_reminders_manager.py
git commit -m "docs: document footer drawers framework ship set"
```

---

## Manual Smoke Checklist

Run this only when the user is ready for interactive verification. Do not mark it complete from automated tests.

Command:

```bash
"${REPO:-/Users/MAC/Documents/Claude-patch}/.development/claude-monkey-builds/footer-drawers-all-three/claude" --dangerously-skip-permissions
```

Checklist:

- [ ] `--version` reports `2.1.201 (Claude Code)`.
- [ ] Down from prompt lands on drawer toolbar once.
- [ ] Order is Hidden Context -> Thinking -> Reminders.
- [ ] Left/right clamps at ends and moves only among drawers.
- [ ] Hovered drawer shows `(enter)`; unhovered drawers show arrow hint.
- [ ] Enter opens hovered drawer.
- [ ] Space opens hovered drawer or toggles Reminders row when Reminders is open.
- [ ] `x` closes open drawer, leaves toolbar selected, and allows left/right to move to another drawer.
- [ ] Escape/clearSelection does not close framework drawers, does not clear footer selection while a drawer is open, and leaves `x` able to close the drawer.
- [ ] Hidden Context appears only when a projection frame exists, uses full projection-list content, scrolls by keyboard/mouse, and closes with x.
- [ ] Thinking is always available while interactive footer is active, opens to `No thinking captured yet` when empty, marks unread/flash through badge/flash without changing availability, scrolls, and closes with x.
- [ ] Thinking drawer-only strings do not appear in transcript JSONL, request assembly, or model-visible context.
- [ ] Reminders is always available, row cursor moves, enter/space toggles rows, master row works, denied families are off by default and session-scoped.
- [ ] Only one drawer is open at a time.
- [ ] Ctrl-O transcript mode and normal chat rendering remain unchanged.

---

## Completion Criteria

Implementation is complete only when:

- `packages/footer-drawers` exists and builds alone on 2.1.201.
- All three drawers require `footer-drawers` and target the same 2.1.201 source identity.
- Direct footer/overlay/status ops are absent from the three thin drawers.
- Thinking retains exactly its content collectors and registration op.
- Hidden Context retains projection/frame content and registration op.
- Reminders retains `_g`/`XYe` deny/filter behavior and registration op; it still conflicts with UAS.
- Composition matrix tests pass.
- Full ship-set build reaches `manual_smoke_pending` with automated checks passed.
- The final report clearly distinguishes automated verification from pending manual smoke.
