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
