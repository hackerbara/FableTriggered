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
