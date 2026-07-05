# Handoff: capybara-onsen breaks Enter-to-open on footer drawers (UNSOLVED)

**Status:** open bug, user-verified still broken after one attempted fix. Ships as a known issue in v1; this doc is the complete state of knowledge for whoever grinds it next.
**Repo:** /Users/MAC/Documents/Claude-patch (main). Binary: `~/.local/share/claude/versions/2.1.201`.

## Symptom (user-verified on real TUI, twice)

Build combo `footer-drawers + hidden-context-drawer (+ thinking-text-drawer + reminders-manager) + capybara-onsen`:
- Drawer bars render in the footer. Capy scene renders. Everything looks right.
- **Enter does not open any drawer.**
- Same combo WITHOUT capybara-onsen: Enter works.
- Minimal repro: `footer-drawers + hidden-context-drawer + capybara-onsen`.

**Critical:** the symptom was re-verified by the maintainer AFTER commit `9d31dc2` (the memoization fix, below) with a refreshed state dir and rebuild. The first fix did not cure it. Assume the real mechanism is not yet found, or is plural.

## History / evidence

- **2.1.199-era capybara-onsen (V1)** rendered as an absolutely-positioned sibling overlay and coexisted fine with hidden-context-drawer (photographic evidence from the maintainer's live session, 2026-07-04 afternoon).
- **The responsive rework** (`78f2b2c` responsive frame, `3364d04` gutter/breakpoint) restructured capy into an ANCESTOR of the composer/footer: `__coCenterProviderV4` (in `packages/capybara-onsen/payloads/01-capy-onsen-context-frame-helpers-before-vko-2-1-201.js`) re-provides the app's real `fde` (useTerminalSize) and `t4` (modal/scrollbox) React contexts around the main window and bottom stack via `__CodexCapyOnsenMainWindowV4`/`__CodexCapyOnsenBottomStackV4`, with a 180ms art-animation ticker.
- **Footer-drawers' Enter wiring** lives in `packages/footer-drawers/payloads/01-real-target-helpers-and-overlay.js`: `__codexFDWrapRealTargetActions`, with the input gate `Go(..., {context:"Footer", isActive:!!Lm&&!se})`. Host component in the minified bundle: `tFf`. See `tests/test_reference_packages.py` for the wiring contract.
- **hotrod-dragons** shares the identical provider pattern (`__hdCenterProviderV4`, 95ms ticker) — whatever the real fix is, apply to BOTH art packages.

## Attempted fix #1 — insufficient (do not repeat)

Commit `9d31dc2` (+ `afd0c6d` for dragons): the provider value objects were unmemoized object literals, forcing every context consumer to re-render on the art ticker cadence. Fixed with `useMemo` keyed on primitives. Verified by static analysis of the composed module + byte parity + composition-matrix tests. **All of that passed and the user-visible symptom persists.** Conclusion: continuous re-render churn was real but was not (or not solely) what kills Enter.

## Ranked hypotheses for the next investigation

1. **The input gate goes false under capy.** Enter is gated by `isActive:!!Lm&&!se`. Determine what `Lm` (selection state?) and `se` (modal/overlay state?) actually are in the 2.1.201 bundle, and whether capy's re-provided `t4` (modal/scrollbox) context changes them. If capy's provider makes the footer believe a modal/scrollbox is active (`se` truthy) or kills the selection (`Lm` falsy), Enter dies exactly like this while rendering stays fine.
2. **Callback identity through the re-provided context.** Capy's provider passes its own `scrollRef`/`claimScrollBox` (now memoized, but still *different objects* than the original provider's). If the drawer-open path registers/claims through the ORIGINAL context's callbacks, the re-provide severs the chain even with stable identity.
3. **A second, unrelated consumer of the same contexts.** Capy re-provides `fde` AND `t4` around the *bottom stack* specifically — the footer lives there. Diff the composed module (with vs without capy) around `tFf` and every `useContext(t4)` consumer in the bottom stack; look for behavior branches on values capy's synthetic context omits or fakes.
4. **Discriminating experiment (cheap, do first):** does up/down SELECTION between drawer bars still work under capy, with only Enter dead? If selection also dead → input routing/gate (hypothesis 1). If selection works and only Enter fails → open-action path (hypothesis 2/3). The maintainer can answer this in 10 seconds; ask, or drive it via the interactive harness.

## Hard requirements for any fix

- **Interactive verification is mandatory.** Static analysis already produced one plausible-but-wrong fix. Verify by really pressing Enter: the maintainer will test, and/or use the xterm harness (`docs/superpowers/plans/2026-07-02-claude-interactive-xterm-harness.md`) to drive keystrokes and assert drawer-open output in the composed build.
- Capy/dragons changes go through their emitters (`examples/capybara-onsen-generator/generate_package.py`, `examples/hotrod-dragons-generator/generate_package.py`) — NEVER hand-edit `packages/{capybara-onsen,hotrod-dragons}`; `tests/test_generator_parity.py` enforces byte parity.
- Composition matrix (`tests/test_footer_drawers_package.py`: `framework-hidden-capy`, `framework-all-capy`, `framework-hidden-dragons`) and full suite stay green.
- Build debug combos into `.development/debug-builds/` — never touch `~/.claude-monkey` state or the maintainer's shim. `uv run claude-monkey build --help` for flags.
- A debug payload that logs the gate values (`Lm`, `se`, focus context) to a file on keypress is a legitimate instrument — build one if static reading stalls.

## Ship posture

v1 launches with this open: README carries a known-issue note; the demo GIFs are being recorded with drawers-without-capy and capy-solo. Fix lands post-launch (or pre-push if it's fast); it must be interactively verified before merge.
