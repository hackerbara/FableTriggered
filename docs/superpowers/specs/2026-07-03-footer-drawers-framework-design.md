# Footer Drawers Framework — Design

Extract a shared footer-toolbar framework that both `hidden-context-drawer` and `reminders-manager` depend on, replacing the current per-package footer navigation with a single owner of toolbar layout, hover navigation, overlay mounting, and drawer registration.

**Status:** Draft — **gated pending a composition-engine decision.** Adversarial review (2026-07-03) byte-verified two blocking issues: (1) footer availability is computed from function-local values at `ji`-construction time and only published to `globalThis` ~31KB later, so a thin drawer's `available()` callback reads a stale global — the "disjoint registration by construction" claim is false for this seam; (2) consolidating shared seams doesn't reduce anchor count, it correlates failure across both drawers and drags orthogonal stock logic (tasks/tmux/bagel/…) into the framework, because `replace_exact` forces restating whole statements. Issue (2) is rooted in a composition-engine limitation — see `2026-07-03-composition-engine-additive-splice-handoff.md`. **Do not implement this framework until the additive-splice question is resolved**; the clean "framework owns seams, drawers register thin" split is not achievable under whole-span replacement without the fragile workarounds it was meant to remove. The current in-place implementation (order + hints, uncommitted) stands as the working state. Targets Claude Code `2.1.199` (stock sha `e3cb61ab…`, module `e30c857c…`).

Design fixes to fold in when unblocked (from the review): compute frame-backed `available()` inline in the `ji`-owning op (not a generic callback); make reminders' refactor atomic with the framework's first build (else old-reminders + new-framework = `patch_conflict` — a flag day for reminders users); `renderPanel` must return an element descriptor `() => zd.jsx(qnc,{})`, never call the hook-bearing function directly; registration ops must anchor on genuine top-level statements, not lazy module-wrapper closures.

## Why this exists

The two drawers work today, but each owns a slice of Claude Code's footer navigation independently. That composes only because their byte ranges are disjoint. The interaction model the user now wants is inherently **cross-package shared state**:

- Down from the prompt lands you in a **drawer toolbar** once (not a per-target rotation).
- Left/right moves the hover **among drawers only** (Hidden Context, Reminders), skipping subagents/tasks.
- The hovered drawer shows `(enter)`; the others show `→`.
- Enter opens the hovered drawer; each drawer renders its own panel.

"Which drawer is hovered," "land on the first available drawer," and "`→`-vs-`(enter)` relative to siblings" cannot be cleanly co-owned by two independent packages — one would have to secretly boss the other. The honest resolution is an explicit framework that owns the shared model, with each drawer as a thin registrant. Re-anchoring on a Claude update then happens **once** in the framework, not per drawer package.

Decisions locked with the user:
- **Toolbar scope = drawers only.** Subagents/tasks/workflows keep their existing stock footer behavior, untouched. The drawer toolbar is a distinct concept layered beside them.
- **In-place UX is frozen** (order: Hidden Context before Reminders; hints: `→` unhovered / `(enter)` hovered). This spec is the extraction that makes the land-once + left/right-between-drawers navigation real.

## Package topology

Three packages after this work:

1. **`footer-drawers`** (new, framework) — owns the toolbar: a `globalThis` drawer registry, the availability-bar rendering for registered drawers, the down-to-toolbar / left-right / enter / close key routing, and the overlay mount points at both `V8o` layout branches. Ships no drawer of its own.
2. **`hidden-context-drawer`** (refactored, thin) — registers a `hiddenContext` drawer entry and provides its projection + panel. Drops its own footer-target, selection-flag, availability-bar, key-routing, and overlay-mount ops.
3. **`reminders-manager`** (refactored, thin) — registers a `reminders` drawer entry and provides its deny-state + checkbox panel. Keeps the `ug`/`Hze` deny seams (unrelated to the toolbar). Drops its footer-target, wrapper, space-binding, bar-segment, and overlay ops.

Dependency: both drawers **require** `footer-drawers` to render as toolbar items. Open question (for review): whether a drawer package installed *without* the framework should fail its precondition, or degrade to a no-op. Recommended: **precondition requires the framework's registry global to exist** — a drawer alone without the framework is a build-time error, not a silent no-op, because a registrant with no registry is meaningless.

## The registry

`globalThis.__CODEX_FOOTER_DRAWERS_V1__` = an ordered structure the framework owns and drawers append to:

```
{
  entries: [ /* ordered; drawers register here */ ],
  hover: number,        // index into the *available* subset, -1 when not in toolbar
  version: number       // bumped on any nav/registration change to drive re-render
}
```

Each entry (registered by a drawer):

```
{
  id: "hiddenContext" | "reminders" | ...,
  order: number,             // sort key; hiddenContext < reminders
  available: () => boolean,   // is this drawer currently showable? (HC: frame visible; reminders: always)
  isOpen: () => boolean,
  setOpen: (b) => void,
  label: () => string,        // bar text WITHOUT the hint suffix ("Hidden Context 1234t", "Reminders")
  onKey: (action) => boolean, // drawer-local key handling when open (row cursor, scroll, toggle); returns true if consumed
  renderPanel: () => element | null  // the overlay panel; returns null when closed
}
```

Registration is idempotent by `id` and init-guarded (a drawer can register before or after the framework's own module-scope code runs; whichever touches the global first creates it). Fail-closed: a missing/corrupt registry yields an empty toolbar and never throws into the footer render path.

## Interaction model (the real one)

**Availability subset:** the framework computes `avail = entries.filter(e => e.available()).sort(by order)` each render.

**Entering the toolbar:** the framework injects a single synthetic footer target (call it `"drawers"`) into `ji` when `avail.length > 0`, positioned where the drawers currently sit (after tasks/workflows or wherever the user settles — see Open Questions). Down/up from the prompt treats the whole drawer toolbar as **one** footer stop. Landing sets `hover = 0` (first available drawer).

**Moving within the toolbar:** when the `"drawers"` target is the active footer selection and no drawer is open, **left/right** move `hover` within `avail` (clamped, no wrap — or wrap; see Open Questions). Up/down continue to exit the toolbar to the next/previous footer target (so you can still reach subagents below).

**Opening:** enter (or space) on the hovered drawer calls `avail[hover].setOpen(true)`. While open, up/down/left/right/enter/space/x route through `avail[hover].onKey(action)` first; if it returns false, fall back to framework/stock behavior. `x` closes.

**Bar rendering:** the framework renders one bar segment per `avail` entry: `label()` plus a hint suffix — `" (enter)"` when this entry is `hover` and the toolbar is active, `" →"` otherwise. This replaces both drawers' individual bar ops.

**Overlay:** the framework renders `avail.map(e => e.renderPanel())` (each null unless open) at both `V8o` caller sites. Only one drawer is open at a time (opening one closes others — framework enforces).

## Seam ownership (framework)

The framework claims the footer/overlay seams currently split between the two packages. From the verified 2.1.199 anchor work:

- **Footer targets list** — inject the `"drawers"` synthetic target (the `Ly`/`Du`/`ji` region, currently reminders' `rm-footer-target-append` seam).
- **Actions map wrapper** — `Wo(...)` open/close wrap (currently reminders' `rm-wo-wrap-open/close`) for left/right/enter/close routing to the registry.
- **Space binding** — add `space` to the Footer context (currently reminders' `rm-footer-space-binding`).
- **Availability bar** — render registered entries (currently the drawer's `footer-availability-bar-hidden-context` op16 *and* reminders' `rm-bar-segment`; the framework subsumes both).
- **Overlay mounts** — both `V8o` branches (currently reminders' `rm-overlay-default` / `rm-overlay-bde`).
- **Down-to-open removal** — the drawer's `Jk` no-longer-opens-on-down change moves into the framework's key routing.

Each drawer package keeps only: its content generation (HC's projection helpers / `Jur` filter seam; reminders' `ug`/`Hze` deny seams) and a small **registration op** that appends its entry to `globalThis.__CODEX_FOOTER_DRAWERS_V1__.entries` and supplies `renderPanel`/`onKey`.

Because the framework owns all the shared seams in one package, `_check_overlaps` is satisfied trivially (one owner per byte range), and the drawers' registration ops anchor on their own content seams — disjoint from the framework by construction.

## Composition & conflicts

- `footer-drawers` + `hidden-context-drawer` + `reminders-manager` — the full stack, one build.
- `footer-drawers` + either drawer alone — works; toolbar shows one item.
- `footer-drawers` alone — builds, empty toolbar (no registrants), no visible change. Harmless.
- Either drawer **without** `footer-drawers` — precondition failure (recommended) — the registry seam it needs isn't present.
- `reminders-manager` still **conflicts with** `upstream-attachment-suppression` on the `ug`/`Hze` seams (unchanged; UAS stays the static all-off option).
- `normal-channel-hidden-context` still composes (disjoint `Jur`).

## Migration path (leaves a working system at each step)

1. Create `footer-drawers` with the shared seams, moving the current op *bodies* into it, generalized to iterate the registry. Test it builds alone (empty toolbar) and the postconditions hold.
2. Refactor `hidden-context-drawer`: remove its footer/overlay ops, add a registration op. Build `footer-drawers` + `hidden-context-drawer`; smoke HC opens/scrolls/closes as before.
3. Refactor `reminders-manager`: same. Build the full stack; smoke the true land-once + left/right model.
4. Update all three READMEs and the composition test matrix.

Each step yields a buildable, smoke-testable binary; no step requires all three refactors landed at once.

## Testing

- `tests/test_footer_drawers.py` — manifest integrity, registry postconditions, builds alone.
- Extend `test_reminders_manager.py` / `test_hidden_context_drawer_package.py` — assert each ships a registration op and no longer ships the moved footer/overlay ops.
- Composition matrix builds: framework+both, framework+each, framework-alone, drawer-without-framework (expect precondition failure), reminders+UAS (expect `patch_conflict`), +normal-channel (expect success).
- Manual smoke (the framework's whole point): down lands on the first drawer once; left/right moves hover between HC and Reminders only (subagents reachable via up/down past the toolbar); hovered shows `(enter)`, others `→`; enter opens; open-drawer keys (HC scroll, reminders row cursor/toggle) work; x closes; only one open at a time.

## Open questions (for review)

1. **Toolbar position in `ji`.** Where does the single `"drawers"` stop sit relative to tasks/workflows/subagents? The user wants down-from-prompt to land on drawers; does that mean drawers are the *first* footer stop (before subagents), or their current position? Current in-place code puts HC/Reminders first — carry that (drawers = first stop)?
2. **Left/right wrap.** At the ends of the drawer list, do left/right wrap around or clamp?
3. **Drawer-without-framework.** Precondition failure (recommended) vs. silent no-op.
4. **`onKey` contract granularity.** Does the framework pass a normalized action name (`"up"`, `"toggle"`, `"close"`) or the raw key event? Normalized is cleaner but requires the framework to own the mapping; raw keeps drawers flexible.
5. **Registration timing / ordering.** If both drawers register, the framework sorts by `order`. Is a numeric `order` field enough, or do we want explicit before/after relationships?
6. **Is the synthetic single `"drawers"` target the right mechanism,** or should each drawer stay a distinct `ji` entry and the framework instead reinterpret left/right among consecutive drawer entries? (The single-target approach is cleaner for "land once"; the multi-entry approach reuses more stock behavior. Real tradeoff.)
