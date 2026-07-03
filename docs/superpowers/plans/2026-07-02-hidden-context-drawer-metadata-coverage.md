# Hidden Context Drawer Metadata and Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refine the existing Hidden Context Drawer so each projected hidden/model-visible item carries timestamp/source metadata and the drawer covers all supported hidden model-visible attachment families rather than only the first narrow allowlist.

**Architecture:** Keep the existing projection-list seam before `Jlr`; do not touch JSONL, request assembly, or the live install. Extend only the drawer projection helper payload and package metadata/tests, then rebuild through ClaudeMonkey V1.5.

**Tech Stack:** ClaudeMonkey package manifests, Bun standalone graph repack, minified React/Ink payload replacements, Python package validation tests, Node helper fixture tests.

---

### Task 1: Add fixture tests for drawer projection metadata and broader coverage

**Files:**
- Modify: `/Users/MAC/Documents/Claude-patch/tests/test_reference_packages.py`
- Read: `/Users/MAC/Documents/Claude-patch/packages/hidden-context-drawer/payloads/01-projection-helpers-before-jlr.js`

- [x] Add a test that extracts helper functions from payload 01, creates attachment rows for `hook_additional_context`, `hook_blocking_error`, `hook_stopped_continuation`, `plan_mode`, `auto_mode`, `agent_listing_delta`, and `task_reminder`, and asserts the produced frame contains timestamp labels, source labels, full text, reverse chronological order, and non-zero token counts.
- [x] Run the focused test and confirm it fails before payload changes.

### Task 2: Extend the projection helper payload

**Files:**
- Modify: `/Users/MAC/Documents/Claude-patch/packages/hidden-context-drawer/payloads/01-projection-helpers-before-jlr.js`
- Modify: `/Users/MAC/Documents/Claude-patch/packages/hidden-context-drawer/patch.json`

- [x] Add small helper functions inside payload 01: timestamp formatting, safe stringification, text extraction, source labeling, entry detail composition.
- [x] Extend `__codexNCHCProjectionText` for known hidden/model-visible families from the normal-channel inventory: hook errors/stopped continuation/success, plan/auto mode enter/exit/reentry, workflow keyword request, ultra effort enter/exit, task status, async hook response, context efficiency, fold nudge, deferred tools delta, agent listing delta, relevant memories, queued command, diagnostics, and MCP resource summaries.
- [x] Include source labels and timestamps in `entries` and in drawer `lines`.
- [x] Preserve reverse chronological ordering and the existing V13 global names.
- [x] Update payload hash in `patch.json`.

### Task 3: Update package docs and verify

**Files:**
- Modify: `/Users/MAC/Documents/Claude-patch/packages/hidden-context-drawer/README.md`
- Modify: `/Users/MAC/Documents/Claude-patch/.development/docs/hidden-context-drawer-implementation.md`

- [x] Document that this is still a hidden/model-visible attachment audit drawer, not a full request viewer.
- [x] Run helper tests, package validation, a copied binary build from `/Users/MAC/.local/share/claude/versions/2.1.198`, graph validation, codesign, `--version`, and `--help`.
- [x] Report the exact new binary command and any unproven interactive behavior.
