# Footer Drawers Framework — Design

Extract a shared footer-toolbar framework that `hidden-context-drawer`, `thinking-text-drawer`, and `reminders-manager` all depend on, replacing per-package footer navigation with a single owner of toolbar layout, hover navigation, overlay mounting, and drawer registration.

**Status:** Design locked for implementation after the composition-engine structured-splice prerequisites are on `main`. Revised 2026-07-04 to fold in the Thinking drawer as a third registrant and to apply the user's target-version decision: **all four packages in the ship set target the latest local Claude Code version available on this system.** On 2026-07-04 that resolved to `/Users/MAC/.local/share/claude/versions/2.1.201`, because `/Users/MAC/.local/bin/claude` points there, `claude --version` reports `2.1.201 (Claude Code)`, the local versions directory tops out at `2.1.201`, and the binary SHA-256 is `a0852d76afc47b30f5cb0b7625ec9a7714cb189f2eeef6c28c77e2be954fb7fd`.

**The framework is required, not just cleaner.** At any single Claude Code version, the direct drawer packages whole-span-own the same footer-target array, selection-flag statement, keybinding action map, status-bar row, and overlay seams. The `thinking-text-drawer` README explicitly says it is expected to conflict with other direct footer drawer packages until structured splices or a reviewed footer-drawer framework exists. The user's desired ship set - Hidden Context + Thinking + Reminders together - cannot be built honestly without one shared footer owner.

## Ship set

One build, one flag-day release, one Claude Code source identity:

| package | role in the ship set |
|---|---|
| `footer-drawers` | framework: registry, synthetic toolbar target, key routing, bar rendering, shared overlay mount |
| `hidden-context-drawer` | thin registrant + hidden-context projection/content seams |
| `thinking-text-drawer` | thin registrant + thinking stream/assistant-content collector seams |
| `reminders-manager` | thin registrant + runtime `ug`/`Hze` deny/filter seams |

All four target **Claude Code 2.1.201** as the current latest local version. If implementation begins after the system has a newer local Claude Code version, re-run the local version check and bump **all four together** to the then-latest local version; do not mix target versions in one framework build.

## Target-version decision

The previous blocker is resolved: do **not** choose between 2.1.199 and 2.1.201 manually, and do **not** keep per-drawer target drift. The target rule is:

> Target the latest available local Claude Code version on the system, and make every package in the framework ship set use that one source identity.

Current evidence, checked 2026-07-04:

| local fact | value |
|---|---|
| `command -v claude` | `/Users/MAC/.local/bin/claude` |
| symlink target | `/Users/MAC/.local/share/claude/versions/2.1.201` |
| `claude --version` | `2.1.201 (Claude Code)` |
| available local versions | `2.1.170`, `2.1.177`, `2.1.193`, `2.1.197`, `2.1.198`, `2.1.199`, `2.1.200`, `2.1.201` |
| target binary SHA-256 | `a0852d76afc47b30f5cb0b7625ec9a7714cb189f2eeef6c28c77e2be954fb7fd` |
| target module path | `/$bunfs/root/src/entrypoints/cli.js` |
| target module SHA-256 | `46db617a7b13c062fb31595f6244819b11f7cdc6e6fed8e2c3f74a27fb6da1bd` |
| target module length | `18,700,756` bytes |

The module SHA/length above come from `packages/thinking-text-drawer/patch.json`, which already targets the same local 2.1.201 source identity. `hidden-context-drawer` and `reminders-manager` are currently pinned to 2.1.199 and must be re-anchored upward to 2.1.201. All 2.1.199 anchors in this document are therefore **historical examples**, not target-version claims.

Minified identifier names are version-scoped. Roles observed in current package files:

| role | 2.1.199 examples from HC/RM | 2.1.201 examples from Thinking |
|---|---|---|
| React namespace near footer state | `Ro` | `wo` |
| footer target array | `ji` | `ss` |
| active footer selection | `Du` | `Lm` |
| keybinding action-map registration | `Wo(` | `Go(` |
| footer down action | `Jk` | `d0` |
| bottom overlay renderer/selector | `qnc` / `bnc` | `Ilc` / `clc` |
| selection flag statement | `let qb=Du==="tasks",...,Ap=Du==="frame";function Sf` | `let lm=Lm==="tasks",...,Mm=Lm==="frame";function Rp` |

Implementation rule: every anchor string and context hash gets re-verified against the selected target module with count/evidence checks (`expectedAnchorCount == 1`, marker counts pinned to 1 where supported, insertion evidence verified by the engine). Never claim that a 2.1.199 identifier survives on 2.1.201 until the target module proves it.

## Prerequisites

Hard prerequisites before implementing this framework:

1. **Composition engine Phase 1:** `insert_before`, `insert_after`, `replace_substring_within`, deterministic same-offset insertion ordering, anchor-evidence disjointness, engine-verified insertion evidence, and sibling-tolerant postcondition rules.
2. **Composition engine Phase 2:** `requiresPackages` and `conflictsWithPackages` validation before planning. Expected failure codes include `patch_conflict:required_package_missing` and `patch_conflict:package_conflict` (or the exact final names from the merged engine).
3. **Structured-splice review fixes R2-R4:** module-scoped postcondition composition-sensitivity checks, marker-count pinning for context-bearing new op types, and duplicate package-id fail-closed behavior.
4. **No implementation in this spec pass:** this document is the implementation-ready design. A separate plan and implementation should follow.

Engine Phases 3-4 are not prerequisites. This framework is the real-seam migration that proves whether the structured primitives pay rent.

## Why this exists

The interaction model is inherently shared state:

- Down from the prompt lands in a **drawer toolbar** once, not in three independent footer stops.
- Left/right moves hover among drawers only.
- The hovered drawer shows `(enter)`; unhovered drawers show an arrow hint.
- Enter/space opens the hovered drawer.
- At most one drawer panel is open.
- `x` is the drawer close action. `escape` remains the stock `footer:clearSelection` path and is not a drawer-close shortcut in V1; this preserves the x-only close invariant from the Hidden Context regression work.

"Which drawer is hovered," "which drawer is open," "how hints render relative to siblings," and "how down lands once" cannot be co-owned by independent patch packages. The framework owns the shared model. Drawers register content and local behavior.

Locked decisions:

1. **Toolbar scope = drawers only.** Tasks, workflows, tmux, bagel, bridge/frame, subagents, and other stock footer targets keep stock behavior.
2. **Single synthetic footer target.** The framework injects one semantic footer target, `"drawers"`, when at least one registered drawer is available.
3. **Toolbar order:** Hidden Context -> Thinking -> Reminders.
4. **Left/right behavior:** clamp at the ends, no wrap in V1.
5. **Drawer without framework:** fail at build time via `requiresPackages`, not silent no-op.
6. **Action contract:** normalized action names (`"up"`, `"down"`, `"previous"`, `"next"`, `"openSelected"`, `"close"`, `"clearSelection"`, `"toggle"` when needed), not raw key events.
7. **Overlay ownership:** one shared bottom-overlay sibling mount owned by the framework, not a per-drawer overlay enum.
8. **Badge/flash:** optional registry fields owned by drawers and rendered consistently by the framework.
9. **Target version:** all four packages target the latest local Claude Code version together; as of this spec, 2.1.201.

There are no remaining product/design open questions for the implementation plan. Implementation still has anchor-discovery work.

## Package topology after the refactor

### `footer-drawers` (new framework package)

Owns:

- registry bootstrap and helpers;
- one synthetic `"drawers"` footer target;
- availability computation and hover state;
- action-map interception for toolbar navigation and open/close;
- optional `space` binding mapped to `footer:openSelected`;
- footer availability/status-bar drawer segment rendering;
- a single bottom-overlay sibling mount above the prompt;
- fail-closed guards so a corrupt/missing registry never throws into stock render paths.

Ships no drawer content and no deny/projection/thinking collectors.

### `hidden-context-drawer` (thin registrant)

Current package evidence: `packages/hidden-context-drawer/patch.json`, schema v2, currently pinned to 2.1.199.

Retains content/data seams, re-anchored to the target 2.1.201 module:

- `projection-helpers-before-jlr` (2.1.199 anchor example: `function Jur(e){`) - helper definitions and hidden/context projection behavior.
- `yt-projection-list-drawer-frame` (2.1.199 anchor example starts `let Jt=r||zs()?Se:Bg(Se,{includeFolded:!0})...`) - computes the drawer frame from the full projection list before hidden rows are filtered.
- Any minimal target-version equivalent needed to publish the fresh frame before footer target availability is computed. This must not depend on a stale global published later in the render path.

Drops or moves to the framework:

- bottom overlay renderer replacement (`uxl-refresh-bottom-overlay` on 2.1.199);
- prop-threading solely needed to reach footer/status-bar/overlay renderer seams;
- selected hook (`footer-hidden-context-selected-hook`);
- availability bar (`footer-availability-bar-hidden-context`);
- footer target insertion (`axf-messagesref-footer-target-frame`);
- selection flag (`footer-hiddencontext-selection-flag`);
- footer up/down/open/clear/close ownership (`footer-hiddencontext-up-down-scroll`, `footer-clearselection-consumes-hiddencontext`);
- selected overlay globals (`selected-only-bottom-overlay-hidden-context-globals`).

Adds one registration op that registers `hiddenContext` with order `100`, `available()` based on the freshly published frame, `label()` including the token/count summary, `badge()/flash()` only if the package still exposes unread state, `onKey()` for scroll/cursor behavior, and `renderPanel()` as an element descriptor.

### `thinking-text-drawer` (thin registrant)

Current package evidence: `packages/thinking-text-drawer/patch.json`, V3 envelope (`schemaVersion: 1`, `kind: "patch"`, `x-packageVersion`), already pinned to 2.1.201. Keep the V3 envelope bridge working through `_v3_manifest_as_v2_dict`; do not force the package into schema v2 unless a separate plan chooses that migration.

The current patch has 16 operations. Based on the package file (source of truth), **8 retained content operations** stay with the drawer:

| retained op | 2.1.201 anchor example | role |
|---|---|---|
| `thinking-helpers-before-ypr` | `function Ypr(e){` | content/state helper definitions; prune the current direct footer action-wrapper helper during the thin refactor |
| `thinking-message-start-turn-collector` | `if(e.event.type==="message_start"){...` | live turn identity start |
| `thinking-message-stop-turn-collector` | `if(e.event.type==="message_stop"){...` | live turn identity clear |
| `thinking-live-delta-collector` | `case"thinking_delta":{let{delta:d}=e.event;...` | raw live thinking text |
| `thinking-signature-collector` | `case"signature_delta":o?.({type:"thinking_signature"...` | preserves stock signature handling; no drawer row |
| `thinking-parent-structured-collector` | `k=n.message.content.map(I),t[23]=s,...` | structured thinking blocks from assistant content |
| `thinking-system-token-estimate` | `if(es.type==="system"&&es.subtype==="thinking_tokens"...` | preserves stock token-estimate drop; no drawer row |
| `thinking-cancel-salvage-collector` | `let en=_t?.thinking?.trim();if(en&&WAe()...` | interruption/cancel salvage |

The handoff described this as nine content seams, but the current package file contains eight retained content ops and eight footer/overlay ops. Treat the file as source of truth. The existing payload also defines `__codexTTDWrapFooterActions`; that helper belongs to the direct footer-owner version and must be removed or rendered unused when the framework owns action routing.

Drops or moves to the framework:

- `thinking-footer-open-state`;
- `thinking-footer-target`;
- `thinking-footer-selection-flag`;
- `thinking-footer-action-wrap-open` and `thinking-footer-action-wrap-close`;
- `thinking-selected-overlay-globals`;
- `thinking-bottom-overlay-renderer`;
- `thinking-footer-status-bar` (2,559-byte whole-statement restatement; this is the clearest example of stock logic the framework must stop restating).

Adds one registration op that registers `thinking` with order `200`, `available()` true whenever the interactive footer is active, `label()` plain text such as `Thinking`, optional `badge()`/`flash()` driven by unread/captured-entry state, `onKey()` for scroll behavior, optional `onClose()` cleanup, and `renderPanel()` that opens to `No thinking captured yet` when no entries exist.

### `reminders-manager` (thin registrant)

Current package evidence: `packages/reminders-manager/patch.json`, schema v2, currently pinned to 2.1.199.

Retains content/behavior seams, re-anchored to the target 2.1.201 module:

- `rm-ug-runtime-deny-2-1-199` (2.1.199 range example: `async function ug(e,t){` to `async function XQt(e,t){`) - runtime label gate before generator execution.
- `rm-hze-runtime-filter-2-1-199` (2.1.199 range example: `async function*Hze(e,t,n,r,o,s,i,a){` to `async function i3l(e){`) - runtime attachment filtering before `li` row construction.
- Reminder state/UI helpers currently defined in the `ug` replacement can remain there if that remains the clean target-version seam, or move to a dedicated top-level helper insertion if re-anchoring proves cleaner. Keep the behavior: all families denied by default, toggles session-scoped. Rename target-version op ids to drop the `-2-1-199` suffix once re-anchored, unless preserving an old id is required for a specific migration tool.

Drops or moves to the framework:

- `rm-footer-target-append-2-1-199`;
- `rm-wo-wrap-open-2-1-199` and `rm-wo-wrap-close-2-1-199`;
- `rm-footer-space-binding-2-1-199`;
- `rm-bar-segment-2-1-199`;
- `rm-overlay-default-2-1-199` and `rm-overlay-bde-2-1-199`.

Adds one registration op that registers `reminders` with order `300`, `available()` true whenever the interactive footer is active, `label()` plain text such as `Reminders`, optional `badge()` if useful for denied/enabled counts, `onKey()` for row cursor, enter/space toggle, and master-row toggle, optional `onClose()` cleanup, and `renderPanel()` as an element descriptor.

## Relationship metadata

Engine Phase 2 relationship metadata is part of the design, not decoration:

```json
{
  "id": "hidden-context-drawer",
  "requiresPackages": ["footer-drawers"]
}
```

```json
{
  "id": "thinking-text-drawer",
  "requiresPackages": ["footer-drawers"]
}
```

```json
{
  "id": "reminders-manager",
  "requiresPackages": ["footer-drawers"],
  "conflictsWithPackages": ["upstream-attachment-suppression"]
}
```

Rules:

- A thin drawer without `footer-drawers` fails at build time with `required_package_missing` (exact final code per engine implementation).
- `reminders-manager` still conflicts with `upstream-attachment-suppression`; both own deny/filter seams. UAS remains the static all-off alternative.
- `thinking-text-drawer` should not declare a permanent conflict with HC or reminders after the refactor. Its current direct-package conflict on footer/overlay seams dissolves because those seams move to `footer-drawers`.
- Old direct drawer packages plus the new framework should fail closed if selected together. The likely failure is byte `patch_conflict` on shared footer/overlay seams, but source-identity mismatch or duplicate-package-id failure is also acceptable. Stale installed package versions must not silently compose.
- Duplicate `manifest.id` across selected packages must fail closed before requirements/conflicts are evaluated, per the structured-splice review R4.

## Registry contract

`globalThis.__CODEX_FOOTER_DRAWERS_V1__` is the single shared runtime object. It is created init-guarded by the framework bootstrap and safely re-used by drawer registration payloads.

Shape:

```js
{
  entries: [],          // idempotent by id; sorted by order at read time
  hoverId: null,        // id of the hovered available drawer, or null
  openId: null,         // id of the single open drawer, or null
  version: 0,           // bump on registration/nav/open/close/toggle/badge-affecting changes
  lastError: null,      // optional debug-only field; render path must not throw
  bump: (reason) => {}, // request a footer refresh after drawer-owned state changes
  register: (entry) => {}
}
```

Entry contract:

```js
{
  id: "hiddenContext" | "thinking" | "reminders",
  order: 100 | 200 | 300,
  available: () => boolean,
  label: () => string,
  badge: undefined | (() => string | null),
  flash: undefined | (() => boolean),
  onOpen: undefined | (() => void),
  onClose: undefined | ((reason) => void),
  onKey: (action) => boolean,
  renderPanel: () => element | null
}
```

Semantics:

- Registration is idempotent by `id`. A later registration for the same `id` replaces the entry and bumps `version`.
- `available()` answers whether the drawer should appear in the toolbar, not whether it has rows. Thinking and reminders can simply return true; the framework only evaluates/injects the toolbar from the interactive footer render path. Hidden Context is available when its frame exists/has visible material.
- `label()` returns text without the framework's hint suffix.
- `badge()` is optional and returns short dynamic text or `null`. Use it for unread count, flash glyph, denied/enabled counts, or similar transient state that should be rendered consistently.
- `flash()` is optional and returns whether the framework should style the label/badge with the package's flash/highlight treatment.
- `onOpen()` is called after the framework sets `openId`. Drawers use it for side effects such as Thinking's mark-read/clear-flash behavior.
- `onClose(reason)` is called before the framework clears `openId`. Drawers use it to persist scroll/cursor state or clear open-specific globals. The framework still clears `openId` even if `onClose` throws.
- `onKey(action)` is for drawer-local behavior while open (scroll, row cursor, row toggle). The framework owns universal open/close state and does not let a drawer consume `close` in a way that prevents `openId` from clearing.
- `renderPanel()` returns an element descriptor. If a drawer panel component uses React hooks, the descriptor must be `() => jsx(Panel,{...})`, not a direct call to `Panel()` inside a varying-length `.map()`.
- Drawers call `registry.bump("reason")` after collector/toggle changes that affect `available()`, `label()`, `badge()`, `flash()`, or panel contents. Thinking's retained collectors must call this when they set unread/flash so the footer bar refreshes promptly.
- Open/cursor/scroll state should live in plain objects reachable from registry/drawer globals, not in new footer-scope React hooks. Use the reminders poll pattern (`useState` plus interval on `version`) as the precedent for forcing render refreshes.
- Registry corruption or an exception in a drawer callback must fail closed to "drawer not available / no panel" and must not break stock footer rendering.

## Interaction model

### Availability subset

Each render computes:

```js
avail = registry.entries
  .filter(entry => safeAvailable(entry))
  .sort((a, b) => a.order - b.order)
```

If `avail.length === 0`, the framework does not add the synthetic `"drawers"` target and the footer remains visually stock. This is the framework-alone behavior.

In the full ship set, at least Thinking and Reminders are always available while the interactive footer is active, so the toolbar is usually present even when Hidden Context has no current frame. Thinking's empty state is a feature: opening it with no captured entries shows `No thinking captured yet`.

### Entering the toolbar

The framework inserts one synthetic footer target with semantic id `"drawers"` into the target array (`ss` on 2.1.201, `ji` on 2.1.199 examples) when `avail.length > 0`.

Position: first drawer position. On the 2.1.201 target-array shape, insert `"drawers"` before `Ui&&"tasks"` inside `ss=wo.useMemo(()=>[Ui&&"tasks",po&&"workflows",Fn&&"tmux",_e&&"bagel",Tr&&"bridge",Ne&&"frame"].filter(Boolean),...)`, gated by `avail.length > 0`. Down from prompt should land on the drawer toolbar once. Up/down beyond the toolbar should still traverse stock footer targets normally.

Landing on the toolbar sets `hoverId` to the first available drawer id unless the previous `hoverId` is still available. If the hovered drawer disappears, reset to the first available drawer. Store hover by id, not array index, so Hidden Context appearing/disappearing cannot silently move hover to the wrong drawer.

### Moving within the toolbar

When the active footer selection is `"drawers"` and no drawer panel is open:

- `footer:previous` / left moves `hoverId` to the previous available drawer id;
- `footer:next` / right moves `hoverId` to the next available drawer id;
- no wrap in V1;
- `footer:openSelected` opens the drawer identified by `hoverId` (or the first available drawer if `hoverId` is stale);
- `footer:close` clears any open drawer (normally none in this state);
- `footer:clearSelection` delegates to stock clear-selection behavior.

### Opening and open-drawer routing

Opening a drawer is a framework-owned lifecycle operation:

1. Resolve the entry from `hoverId` (or first available if stale).
2. If another drawer is open, call that entry's `onClose("switch")`, then clear `openId`.
3. Set `registry.openId = entry.id` and `registry.hoverId = entry.id`.
4. Bump `version`.
5. Call `entry.onOpen()`; Thinking uses this to mark captured entries read and clear flash.
6. Keep active footer selection on `"drawers"`.

Closing a drawer is also framework-owned:

1. Resolve `openEntry` from `openId`.
2. Call `openEntry.onClose(reason)` if present.
3. Clear `openId`, bump `version`, and keep `hoverId` on the closed drawer if it is still available.
4. Keep active footer selection on `"drawers"`. `x` closes the panel but leaves the toolbar selected so the user can move to another drawer or reopen; Escape/clearSelection remains the stock way out of footer selection.

When a drawer is open, action order is:

- `footer:close` / `x`: framework closes the open drawer with reason `"x"`; drawers do not consume this first.
- `footer:clearSelection` / Escape: framework does not close drawers in V1; if the drawer has a non-close use for clearSelection it may consume it, otherwise delegate stock clear-selection behavior.
- `footer:openSelected` / enter or space: route to `openEntry.onKey("openSelected")` first so Reminders can toggle rows; if not consumed, keep the drawer open.
- Up/down/left/right: route to `openEntry.onKey(action)` first for scrolling/cursor movement; delegate conservatively only when unconsumed.

### Bar rendering

The framework renders one compact segment for the drawer toolbar. For each available entry, render:

1. `label()`;
2. optional `badge()` text;
3. hint suffix: `(enter)` if toolbar active, no drawer open, and this entry id equals `hoverId`; otherwise an arrow hint.

Payload examples must use pure ASCII escapes for non-ASCII glyphs (`\u2192` for arrow, `\xB7` for middle dot, etc.) because the current latin1 repack path corrupts literal multibyte UTF-8 in payload files. Markdown prose can be readable; package payloads must be escaped.

Thinking's unread/flash state belongs in `badge()`/`flash()`, not in availability. Hidden Context's unread/flash may use the same optional fields if retained. Reminders can skip both unless a useful count emerges.

### Overlay rendering

The framework owns **one bottom-overlay sibling strategy**. It should standardize on the 2.1.201 Thinking package's more general surface: the function currently shaped like:

```js
function Ilc(){let e=MXe.c(2),t=clc();if(!t)return null;let n;if(e[0]!==t)n=Xd.jsx(B,{position:"absolute",bottom:"100%",left:0,right:0,opaque:!0,children:t}),e[0]=t,e[1]=n;else n=e[1];return n}
```

Implementation must re-verify the exact target-version equivalent. The framework wrapper should preserve stock `clc()` output when no drawer is open. When a drawer is open, render the active drawer's `renderPanel()` content in the full-width `bottom:"100%"` layer above the prompt. If stock overlay content and drawer content can coexist, render **drawer content first, then stock overlay content**, matching the current HC/Thinking bottom-overlay payload order. If they cannot coexist safely, the drawer panel wins only while a drawer is explicitly open.

Do **not** add a per-entry overlay enum in V1. It increases API and test surface without a proven need. If a future drawer truly needs a different mount, that is a V2 framework decision.

## Seam ownership and operation strategy

The design assumes structured splice primitives, not whole-statement restatements. Use the smallest operation that owns the actual behavior.

### Framework-owned seams

Target-version examples below name 2.1.201 where available. Re-anchor and prove `count == 1` before writing package ops.

1. **Bootstrap/helpers:** insert a small framework helper block at a stable top-level anchor. It defines registry creation, safe callback wrappers, sorting, hover/open helpers, and rendering helpers. It should not depend on any drawer package being present.
2. **Footer target cluster:** around the target array (`ss=wo.useMemo(()=>[Ui&&"tasks",po&&"workflows",Fn&&"tmux",_e&&"bagel",Tr&&"bridge",Ne&&"frame"].filter(Boolean),[Ui,po,Fn,_e,Tr,Ne])` on 2.1.201). Publish any live local data needed for availability before computing `avail`, and insert the single `"drawers"` target before `Ui&&"tasks"` using a structured insertion/replacement that does not restate siblings.
3. **Selection flag:** around `let lm=Lm==="tasks",ZE=Lm==="workflows",Hd=Lm==="tmux",Zp=Lm==="bagel",AT=Lm==="bridge",Mm=Lm==="frame";function Rp` on 2.1.201. Add a drawer-toolbar selected flag without owning stock sibling flags.
4. **Action map wrapper:** around `Go({"footer:up":By,"footer:down":d0,"footer:next":o6,"footer:previous":IR,"footer:openSelected":()=>{` and its closing `return!1}},{context:"Footer",isActive:!!Lm&&!se});` on 2.1.201. Intercept only while selection is `"drawers"` or a drawer is open; delegate stock behavior otherwise.
5. **Footer context binding:** add `space:"footer:openSelected"` if absent, using a targeted insertion. Preserve existing `escape:"footer:clearSelection"` and `x:"footer:close"` bindings, but route only `x`/`footer:close` to drawer close behavior.
6. **Availability/status bar:** replace the current per-drawer whole-status restatements with one small framework insertion in the status-bar row. It consumes registry labels/badges/flash and appends one deterministic drawer segment without restating unrelated tasks/tmux/bagel/frame/voice/select logic.
7. **Bottom overlay sibling:** own the target-version equivalent of the `Ilc`/`clc` renderer, or the nearest single bottom-overlay sibling if names move. This retires HC/Thinking direct bottom-overlay replacements and RM children-array overlay injections.
8. **Postconditions:** assert framework helper names and payload markers only. For insertion ops, rely on engine insertion evidence rather than adjacency assertions that would become composition-sensitive.

### Drawer-owned registration seams

Each drawer adds one small registration op. Prefer anchoring registration near a retained package-owned helper/content seam so it remains disjoint from framework-owned footer seams.

- Hidden Context: register after projection helpers or the target-version equivalent of the full projection-list frame helper.
- Thinking: register after `thinking-helpers-before-ypr` helper definitions or another stable retained content helper.
- Reminders: register after the reminders state/helper definitions in the `ug` seam or a new target-version helper insertion.

Registration payloads must be idempotent and safe if evaluated before or after the framework bootstrap. The helper `getRegistry()` pattern can create a placeholder object, and the framework can later normalize it.

### Current shared-seam evidence to retire

These current direct footer/overlay ops must not survive in the thin drawer packages after migration:

| package | current op ids to remove/replace with framework ownership |
|---|---|
| `hidden-context-drawer` | `uxl-refresh-bottom-overlay`, `footer-hidden-context-selected-hook`, `footer-availability-bar-hidden-context`, `axf-messagesref-footer-target-frame`, `footer-hiddencontext-selection-flag`, `footer-hiddencontext-up-down-scroll`, `footer-clearselection-consumes-hiddencontext`, `selected-only-bottom-overlay-hidden-context-globals`, plus prop-threading ops used only for footer/overlay delivery |
| `thinking-text-drawer` | `thinking-footer-open-state`, `thinking-footer-target`, `thinking-footer-selection-flag`, `thinking-footer-action-wrap-open`, `thinking-footer-action-wrap-close`, `thinking-selected-overlay-globals`, `thinking-bottom-overlay-renderer`, `thinking-footer-status-bar` |
| `reminders-manager` | `rm-footer-target-append-2-1-199`, `rm-wo-wrap-open-2-1-199`, `rm-wo-wrap-close-2-1-199`, `rm-footer-space-binding-2-1-199`, `rm-bar-segment-2-1-199`, `rm-overlay-default-2-1-199`, `rm-overlay-bde-2-1-199` |

## Composition matrix

Expected build behavior after migration:

| selection | expected result |
|---|---|
| `footer-drawers` | success; empty toolbar; behavior-neutral binary |
| `footer-drawers` + `hidden-context-drawer` | success; one available drawer when HC frame exists |
| `footer-drawers` + `thinking-text-drawer` | success; Thinking always available; empty state works |
| `footer-drawers` + `reminders-manager` | success; Reminders always available; toggles work |
| `footer-drawers` + HC + Thinking | success |
| `footer-drawers` + HC + Reminders | success |
| `footer-drawers` + Thinking + Reminders | success |
| `footer-drawers` + HC + Thinking + Reminders | success; primary ship set |
| HC alone | fail closed: `required_package_missing` |
| Thinking alone | fail closed: `required_package_missing` |
| Reminders alone | fail closed: `required_package_missing` |
| `footer-drawers` + Reminders + UAS | fail closed: `package_conflict` |
| old direct HC/RM/Thinking package + `footer-drawers` | fail closed; likely `patch_conflict` on shared footer/overlay seams, but source-identity mismatch or duplicate-package-id failure is also acceptable |

`normal-channel-hidden-context` / upstream attachment visibility work should remain disjoint unless it owns the same projection/deny seams. Re-check actual package metadata before claiming success.

## Migration path

The working checkpoints must leave a buildable system at each step, but the public release is a flag day: users upgrade the framework and all thin drawer packages together.

1. **Framework alone on 2.1.201.** Create `footer-drawers` with bootstrap, target insertion, action wrapper, bar segment, and bottom overlay mount. No registrants. Build succeeds; no visible toolbar; stock footer smoke remains unchanged.
2. **Refactor Hidden Context upward to 2.1.201.** Re-anchor retained projection/content seams, remove footer/overlay ownership, add `requiresPackages`, add registration op. Build framework + HC; smoke HC availability, open, scroll, x close, and verify Escape/clearSelection does not close it or any other framework drawer.
3. **Refactor Reminders upward to 2.1.201.** Re-anchor `ug`/`Hze` deny/filter seams, remove footer/overlay ownership, keep UAS conflict, add registration op. Build framework + HC + Reminders and framework + Reminders alone; smoke rows, enter/space toggle, master row, x close.
4. **Refactor Thinking on 2.1.201.** Keep its retained content collectors, remove footer/overlay/status ownership, add `requiresPackages`, add registration op with optional `badge()`/`flash()`. Build framework + each pair and framework + all three; smoke Thinking empty state, captured entries, unread/flash, scroll, x close.
5. **Release all together.** Update READMEs/package versions/compatibility notes, regenerate build reports, and document that old direct drawer packages cannot be mixed with the framework. If a package manager/CLI can select stale packages, make the failure readable.

The important distinction: implementation can be staged and verified one package at a time; installation/activation should be a flag day so stale direct drawer packages do not try to share framework seams.

## Testing plan

### Automated/package tests

Add or extend tests so they prove behavior at the package/manifest/composition layer, not just payload string presence:

- `tests/test_footer_drawers.py` (new): framework manifest loads, targets 2.1.201, builds alone, has no drawer-specific content collectors, and verifies registry/bar/overlay postconditions.
- Extend `tests/test_hidden_context_drawer_package.py`: after migration, package targets 2.1.201, declares `requiresPackages`, no longer contains moved footer/overlay op ids, retains projection/content op ids, and registration payload exists.
- Extend `tests/test_reminders_manager.py`: package targets 2.1.201, declares `requiresPackages` + UAS conflict, no longer contains moved footer/overlay op ids, retains `ug`/`Hze` behavior seams, and registration payload exists.
- Add/extend Thinking package tests: V3 envelope still loads through the builder bridge, target remains 2.1.201 unless the local latest changed, moved footer/overlay op ids are gone, retained content collector op ids remain, registration payload exists, and `requiresPackages` is honored.
- Composition matrix builds: all success/failure cases listed above, including `footer-drawers + reminders-manager + upstream-attachment-suppression` for the package conflict. Assert structured failure codes, not loose stderr substrings, where the engine exposes them.
- Structured-splice evidence: same-offset insertion ordering is deterministic, duplicate `insertOrder` fails, insertion evidence is recorded, and postconditions do not span shared insertion points.
- Registry lifecycle tests: opening calls `onOpen`, switching calls previous `onClose("switch")`, x close calls `onClose("x")` and clears `openId`, collector-triggered `bump()` refreshes badge/flash, and hover is preserved by `hoverId`.
- Anchor uniqueness: every target-version anchor/context marker used by the four packages resolves exactly once in the selected 2.1.201 module.
- Encoding lint: payload files use ASCII escapes for non-ASCII UI glyphs (`\u2192`, `\u2500`, `\u276F`, `\xB7`, etc.) rather than literal multibyte UTF-8.

### Manual smoke

Manual smoke is required for the final all-three copied binary and should also be run for key partial builds while developing.

Framework/full toolbar:

- Launch the copied binary directly, not by replacing the user's live install unless explicitly requested.
- Down from prompt lands on the drawer toolbar once.
- Order is Hidden Context -> Thinking -> Reminders.
- Left/right clamps at ends and moves only among drawers.
- Hovered drawer shows `(enter)`; unhovered drawers show the arrow hint.
- Enter and space open the hovered drawer.
- Only one drawer is open at a time.
- `x` closes the open drawer, leaves the toolbar selected on the closed drawer, and permits left/right to move to another drawer.
- Escape/clearSelection does not close framework drawers; x remains the close path.

Hidden Context:

- Appears when hidden/model-visible projection frame exists.
- Opens, scrolls, closes with x.
- Uses full projection-list content, not a narrow source-hook/global ping subset.
- Drawer entries use full projection text, not an 80-character summary.

Thinking:

- Always appears while the interactive footer is active, even with zero captured entries.
- Opens to `No thinking captured yet` when empty.
- Captured raw/structured/salvaged thinking entries appear when the stream/content exposes them.
- Progress-only, signature-only, redacted-only, and estimated-token-only events do not create rows.
- Unread/flash state changes badge/flash presentation but not availability.
- Ctrl-O transcript mode and normal chat rendering remain unchanged.
- Drawer-only strings such as `__CODEX_THINKING_TEXT_DRAWER_FRAME_V1__`, `No thinking captured yet`, `thinking-available`, and `x closes` do not appear in transcript persistence, request assembly, or model-visible context.

Reminders:

- Always appears while the interactive footer is active.
- Opens to the runtime toggle panel.
- Row cursor moves; enter/space toggles rows; master row semantics remain intact.
- Denied families remain off by default and session-scoped.
- `ug`/`Hze` filtering works, and UAS conflict still prevents selecting both static and runtime deny packages.

Version/source proof:

- Copied binary reports `2.1.201 (Claude Code)` unless the implementation deliberately bumped all four packages to a newer local latest.
- `codesign --verify --deep --strict --verbose=4` passes on the copied output.
- `inspect-binary`/build report shows one changed module, target module SHA evidence, and all insertion evidence.
- If direct interactive smoke is not possible in the implementation environment, mark the build `manual_smoke_pending` explicitly; do not convert static green checks into a manual-smoke claim.

## Risks and mitigations

### Correlated toolbar failure

Risk: one broken framework anchor can take down all three drawer toolbars at once.

Mitigation: this is an explicit tradeoff. The content seams remain in their packages: HC projection, Reminders deny/filtering, and Thinking collectors do not become framework seams. A framework anchor failure should fail the build closed rather than producing a half-patched UI. The upside is that stock footer logic is no longer restated three times.

### Re-anchoring HC/RM from 2.1.199 to 2.1.201

Risk: HC and Reminders content seams may have moved or changed in 2.1.201.

Mitigation: treat 2.1.199 anchors as historical examples only. Re-discover target-version equivalents from the 2.1.201 module, prove uniqueness/hash evidence, and write package tests that fail closed if those exact seams drift.

### Overlay surface mismatch

Risk: the bottom-overlay sibling seam might differ across terminal modes or future versions.

Mitigation: standardize on one framework mount in V1, but verify it through both default and native-scroll-region layouts if Claude Code still has distinct paths. If 2.1.201 already funnels both through `Ilc`/`clc`, prefer that. Do not revive per-drawer overlay injections unless a smoke-tested target module proves the single mount cannot serve all three.

### React hooks safety

Risk: calling hook-bearing drawer panel functions inside a dynamic `.map()` violates hook ordering.

Mitigation: `renderPanel()` returns an element descriptor like `() => jsx(Panel,{})`. The framework renders only the active open entry, or renders descriptors as elements, never directly calls hook-bearing component bodies in an availability-length-dependent loop.

### Encoding corruption

Risk: literal non-ASCII glyphs in payloads corrupt through the latin1 repack path.

Mitigation: package payloads use ASCII escapes for arrows, box drawing, prompt markers, and middle dots. Add a payload lint.

### Stale package selection

Risk: old direct packages remain installed/selectable and conflict with the framework.

Mitigation: use `requiresPackages`, keep moved op ids absent from thin packages, expect fail-closed behavior for stale direct packages (often byte `patch_conflict`, but source-identity or duplicate-id failure is acceptable), and update README/package versions to make the flag day explicit.

## Source file evidence read for this revision

- `packages/thinking-text-drawer/patch.json` and `README.md` - current 2.1.201 source identity, 16 ops, always-available Thinking behavior, empty state, unread/flash distinction, transcript/request safety notes.
- `packages/hidden-context-drawer/patch.json` - current 2.1.199 hidden projection/content and direct footer/overlay ops to retire.
- `packages/reminders-manager/patch.json` - current 2.1.199 runtime deny/filter seams and direct footer/overlay ops to retire.
- `docs/superpowers/specs/2026-07-03-composition-engine-structured-splices-design.md` - structured splice primitives and postcondition model this framework relies on.
- `docs/superpowers/reviews/2026-07-04-structured-splices-implementation-review.md` - required engine review fixes R2-R4 that affect this framework.
- `docs/superpowers/specs/2026-07-04-footer-drawers-three-drawer-handoff.md` - handoff framing and requested three-drawer deltas.

## Implementation handoff summary

Build the framework first, then make all three drawers thin registrants, all on the latest local Claude Code source identity. As of 2026-07-04, that target is 2.1.201. The framework owns one synthetic `"drawers"` target, one registry, one bar renderer, one key router, and one bottom-overlay mount. Hidden Context keeps projection. Thinking keeps thinking collectors. Reminders keeps runtime deny/filtering. All three require the framework. Reminders still conflicts with UAS. Old direct drawer packages must fail closed instead of silently mixing with the new framework.
