# Hidden Context Drawer Unread Flash Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a persistent blue/white unread flash to the Hidden Context footer indicator whenever new hidden/model-visible context is projected, and clear it when the user enters the Hidden Context footer target.

**Architecture:** Reuse the existing projection-derived drawer frame and `flashUntil` field instead of adding source-hook timers. A changed projection key list sets `flashUntil` to a persistent future value; the footer bar renders a blue background with white text while unread; the footer selection/open path clears the frame flash synchronously.

**Tech Stack:** ClaudeMonkey schema-v2 package payloads, Bun standalone graph repack, Python package/reference tests, copied Claude Code 2.1.198 binary only.

---

### Task 1: Regression Test for Footer Flash and Clear

**Files:**
- Modify: `/Users/MAC/Documents/Claude-patch/tests/test_reference_packages.py`

- [ ] **Step 1: Write the failing test**

Add a package-level regression test that checks all three contract markers:

```python
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
```

- [ ] **Step 2: Run the regression to verify it fails**

Run a direct assertion script equivalent to the test because this checkout currently lacks `pytest` in both the system Python and `.venv`:

```bash
python3 - <<'PY'
from pathlib import Path
package_dir = Path('packages/hidden-context-drawer')
helper_payload = (package_dir / 'payloads' / '01-projection-helpers-before-jlr.js').read_text()
footer_payload = (package_dir / 'payloads' / '16-footer-availability-bar-hidden-context.js').read_text()
globals_payload = (package_dir / 'payloads' / '14-selected-only-bottom-overlay-hidden-context-globals.js').read_text()
keyboard_payload = (package_dir / 'payloads' / '12-footer-hiddencontext-up-down-scroll.js').read_text()
assert 'flashUntil:o?Number.MAX_SAFE_INTEGER:r?.flashUntil??0' in helper_payload
assert 'hCflash=!hCsel&&Date.now()<(hCf?.flashUntil??0)' in footer_payload
assert 'color:"white",backgroundColor:"blue"' in footer_payload
assert 'Date.now()<(hCf?.flashUntil??0)' in footer_payload
assert 'flashUntil=0' in globals_payload
assert 'flashUntil=0' in keyboard_payload
PY
```

Expected: FAIL on the persistent flash marker before implementation.

### Task 2: Implement Persistent Blue/White Flash and Clear

**Files:**
- Modify: `/Users/MAC/Documents/Claude-patch/packages/hidden-context-drawer/payloads/01-projection-helpers-before-jlr.js`
- Modify: `/Users/MAC/Documents/Claude-patch/packages/hidden-context-drawer/payloads/16-footer-availability-bar-hidden-context.js`
- Modify: `/Users/MAC/Documents/Claude-patch/packages/hidden-context-drawer/payloads/14-selected-only-bottom-overlay-hidden-context-globals.js`
- Modify: `/Users/MAC/Documents/Claude-patch/packages/hidden-context-drawer/payloads/12-footer-hiddencontext-up-down-scroll.js`

- [ ] **Step 1: Make new projected keys persist unread state**

In the projection helper frame object, replace the temporary flash value:

```js
flashUntil:o?Date.now()+1800:r?.flashUntil??0
```

with:

```js
flashUntil:o?Number.MAX_SAFE_INTEGER:r?.flashUntil??0
```

- [ ] **Step 2: Render blue/white footer text while unread**

In the footer payload, compute `hCflash` and render the direct text variant when unread:

```js
hCflash=!hCsel&&Date.now()<(hCf?.flashUntil??0),hCbar=hCf?.visible?hCflash?di.jsxs(v,{color:"white",backgroundColor:"blue",children:["Hidden Context ",hCf?.tokenCount??0,"t ",it.arrowDown]}):di.jsxs(nwf,{selected:hCsel,children:["Hidden Context ",hCf?.tokenCount??0,"t ",it.arrowDown]}):null
```

- [ ] **Step 3: Clear unread state when the hidden target is selected/opened**

In the selected-only globals payload, clear on hiddenContext selection before publishing the frame globally:

```js
if(hC&&__codexHiddenContextFrame)__codexHiddenContextFrame.flashUntil=0;
```

In the keyboard open/scroll payload, clear on direct open/scroll paths with:

```js
if(__codexHiddenContextFrame)__codexHiddenContextFrame.flashUntil=0;
```

### Task 3: Manifest, Build, Verification, Commit

**Files:**
- Modify: `/Users/MAC/Documents/Claude-patch/packages/hidden-context-drawer/patch.json`

- [ ] **Step 1: Update payload hashes and postconditions**

Run a hash refresh for changed payloads, bump `packageVersion` to `0.1.5`, and add postconditions for:

```text
Number.MAX_SAFE_INTEGER
hCflash=!hCsel&&Date.now()<(hCf?.flashUntil??0)
backgroundColor:"blue"
color:"white"
flashUntil=0
```

- [ ] **Step 2: Verify package and build copied binary**

Run:

```bash
PYTHONPATH=src python3 -m claude_monkey validate-package --source /Users/MAC/.local/share/claude/versions/2.1.198 --package packages/hidden-context-drawer --source-version 2.1.198 --source-version-output '2.1.198 (Claude Code)' --platform darwin --arch arm64 --json
PYTHONPATH=src python3 -m claude_monkey build --source /Users/MAC/.local/share/claude/versions/2.1.198 --package packages/hidden-context-drawer --output-dir /Users/MAC/Documents/Claude-patch/.development/claude-monkey-builds/hidden-context-drawer-v18-unread-flash --source-version 2.1.198 --source-version-output '2.1.198 (Claude Code)' --platform darwin --arch arm64 --json
```

- [ ] **Step 3: Run independent binary checks**

Check Bun graph validation, 16KB `__BUN`/`__LINKEDIT` alignment, codesign, `--version`, `--help`, and marker presence in the copied binary.

- [ ] **Step 4: Commit only related files**

Stage the plan, package payloads, manifest, and regression test. Leave unrelated `packages/normal-channel-hidden-context/` and unrelated plan files unstaged.
