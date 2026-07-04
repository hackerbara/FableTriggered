# Hidden Context Drawer

Projects hidden/otherwise-suppressed model-visible attachment context into an integrated Claude Code footer drawer.

This is a ClaudeMonkey V1.5 package targeting `/$bunfs/root/src/entrypoints/cli.js` with the graph-aware Bun repack engine. It does not patch request assembly, does not mutate transcript JSONL, and does not depend on the normal transcript renderer.

The drawer uses the projection-list seam before Claude Code filters hidden attachment rows, adds a non-preemptive `hiddenContext` footer target, and renders the opened drawer through the existing bottom overlay sibling above the composer/footer (`qnc` in Claude Code 2.1.199; this was `UXl` in the prior target).

Each drawer entry now includes:

- a compact event timestamp when the attachment row has one;
- a source label such as `attachment:hook_additional_context · hook:SessionStart`;
- a title/type label and approximate token count;
- the projected hidden/model-visible text.

This is intentionally **not** a full request viewer. It does not duplicate ordinary visible transcript/user/tool content; it audits hidden or abbreviated attachment families that are candidates for model-visible context.

Manual smoke is required: arrow down to select Hidden Context, arrow down again to open it, verify the header appears, arrow keys scroll, and x closes the drawer without using the prompt cancellation key.

## Compatibility

This package is V1.5 merge-domain compatible with non-overlapping packages such as `fable-fallback` and `reminder-suppression`.

It intentionally conflicts with `normal-channel-hidden-context`: both packages own the same projection seam before Claude Code's hidden-attachment filter. Use this drawer package instead of the normal-channel projection package when you want the integrated footer drawer UI.

## Build from this checkout

```bash
cd /Users/MAC/Documents/Claude-patch
PYTHONPATH=src python3 - <<'PY'
from claude_monkey.cli import main
raise SystemExit(main([
    "build",
    "--source", "/Users/MAC/.local/share/claude/versions/2.1.199",
    "--package", "hidden-context-drawer",
    "--output-dir", "/Users/MAC/Documents/Claude-patch/.development/claude-monkey-builds/hidden-context-drawer-2.1.199",
    "--source-version", "2.1.199",
    "--source-version-output", "2.1.199 (Claude Code)",
    "--platform", "darwin",
    "--arch", "arm64",
]))
PY
```

The built binary will be:

```bash
/Users/MAC/Documents/Claude-patch/.development/claude-monkey-builds/hidden-context-drawer-2.1.199/claude
```

Run it for manual smoke:

```bash
/Users/MAC/Documents/Claude-patch/.development/claude-monkey-builds/hidden-context-drawer-2.1.199/claude --dangerously-skip-permissions
```

## Footer Drawers framework migration

This package is now a thin registrant for `packages/footer-drawers` targeting Claude Code 2.1.201. It keeps the Hidden Context projection/frame content seams, but the footer target, key routing, toolbar label, and bottom-overlay mount are owned by `footer-drawers`.

Build it with `--package packages/footer-drawers --package packages/hidden-context-drawer`. Build reports remain `manual_smoke_pending` until interactive footer smoke confirms x-only close and full projection-list content.
