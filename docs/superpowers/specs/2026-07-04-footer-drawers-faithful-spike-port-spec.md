# Footer Drawers Faithful Spike Port Spec — 2026-07-04

## Scope

This spec replaces the synthetic `drawers` framework approach for the next implementation attempt.

It is intentionally narrow: translate the known-good spike behavior into the current `2.1.201` package stack and centralize shared footer seams only where that does **not** change the spike's interaction model.

No implementation is authorized by this document by itself. Stop after this spec is approved; write the implementation plan separately.

## Supersession

This spec supersedes `/Users/MAC/Documents/Claude-patch/docs/superpowers/plans/2026-07-04-footer-drawers-framework.md` except for source identity and anchor reconnaissance. Do not execute that plan's registry, descriptor, synthetic `drawers`, hover/open, or test instructions.

The previous plan is unsafe because it explicitly instructed the broken concepts now forbidden here:

- one synthetic `"drawers"` footer target,
- runtime drawer registry lifecycle,
- `hoverId` / `openId` / `active` state,
- descriptor callbacks such as `available`, `onOpen`, `onClose`, `onKey`, and `renderPanel`,
- `__codexFDWrapActions` dispatching through a synthetic toolbar mode.

Use the old plan only to recover already-verified `2.1.201` source identity and raw seam locations. Do not use it as behavioral authority.

## Target source identity

All packages in this stack target the same local Claude Code source identity unless the user explicitly authorizes retargeting:

- binary: `/Users/MAC/.local/share/claude/versions/2.1.201`
- version output: `2.1.201 (Claude Code)`
- binary SHA-256: `a0852d76afc47b30f5cb0b7625ec9a7714cb189f2eeef6c28c77e2be954fb7fd`
- binary size: `231708784`
- module path: `/$bunfs/root/src/entrypoints/cli.js`
- module SHA-256: `46db617a7b13c062fb31595f6244819b11f7cdc6e6fed8e2c3f74a27fb6da1bd`
- module length: `18700756`

If the local latest Claude Code changes, stop before implementation planning and ask whether to retarget. Do not mix target versions.

## Non-negotiable requirement

Do not invent a new interaction model.

The working spike's source of truth was the stock footer system:

```text
footerSelection
  -> normalized selected real footer target
  -> Footer context active
  -> target-specific open/scroll/toggle behavior
  -> status bar hint derived from the same real selected target
```

The repaired implementation must preserve that chain.

## Explicitly forbidden

The next implementation must not contain any of these runtime behaviors:

- No synthetic footer target named `"drawers"`.
- No synthetic drawer hover state.
- No synthetic drawer active state.
- No global `hoverId` / `openId` / `active` state for toolbar navigation.
- No `__codexFDLand()` / `__codexFDMove()` land-once toolbar simulator.
- No status-bar selected state derived from `footerSelection === "drawers"`.
- No action wrapper that treats the toolbar as a separate mode from the real selected footer target.
- No fix that depends on registry mutation causing unrelated render surfaces to maybe refresh.
- No runtime drawer registry at all: no `__CODEX_FOOTER_DRAWERS_V1__`, no `__codexFDDrawers`, and no drawer `register(...)` API.
- No descriptor-driven behavior: no `register({id, available, onOpen, onClose, onKey, renderPanel})` or equivalent object table that owns drawer actions.

If a future patch still has `"drawers"` as a footer target, it is wrong for this request.

## What “shared framework” means here

The shared framework may provide pure rendering helpers and shared exact-seam snippets. It must not be a runtime registry.

Allowed shared-framework responsibilities:

- common pure helper functions for formatting drawer status-bar segments,
- common exact-seam payloads that insert real drawer ids into the stock target list,
- common exact-seam payloads that render real drawer status-bar segments,
- common exact-seam payloads that compose panel functions into the existing bottom overlay,
- common `space: "footer:openSelected"` binding,
- tests that prove real target selection and reject synthetic target state.

Forbidden shared-framework responsibilities:

- owning selection,
- owning hover,
- owning open state,
- accepting drawer descriptor registrations,
- asking drawers for `available`, `onOpen`, `onClose`, `onKey`, or `renderPanel` callbacks,
- dispatching behavior through anything other than explicit real target checks.

Real drawer behavior must be wired through explicit checks such as:

```js
Lm === "hiddenContext"
Lm === "thinking"
Lm === "reminders"
```

Selection remains stock `footerSelection`. Open state remains drawer-local, exactly like the spike:

- Hidden Context: local React state/global bridge equivalent to `hCo` / `__CODEX_HIDDEN_CONTEXT_DRAWER_OPEN_V13__`.
- Reminders: `__codexRMUIState().open`.
- Thinking: `__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__` plus Thinking-local frame/scroll state.

A pure helper is acceptable only if it takes concrete real-target booleans or local drawer state as arguments. It is not acceptable if it discovers drawer behavior from a registry or descriptor list.

## 2.1.201 seam map required before implementation planning

An implementation plan must name these exact `2.1.201` seams and assign each one to a concrete payload. If an anchor is not present exactly once, stop and update the spec/plan before coding.

### Footer target construction seam

Current stock anchor:

```js
ss=wo.useMemo(()=>[Ui&&"tasks",po&&"workflows",Fn&&"tmux",_e&&"bagel",Tr&&"bridge",Ne&&"frame"].filter(Boolean),[Ui,po,Fn,_e,Tr,Ne])
```

Required rewrite shape:

```js
__codexHiddenContextFrame=__codexNCHCDrawerFrameFromList(/* same-render projection source */),
ss=wo.useMemo(()=>[
  __codexHiddenContextFrame?.visible&&"hiddenContext",
  "thinking",
  "reminders",
  Ui&&"tasks",
  po&&"workflows",
  Fn&&"tmux",
  _e&&"bagel",
  Tr&&"bridge",
  Ne&&"frame"
].filter(Boolean),[Ui,po,Fn,_e,Tr,Ne,__codexHiddenContextFrame?.generation])
```

The exact Thinking/Reminders availability expression may be package-presence dependent, but it must be an explicit real target expression in this list, not a registry callback.

### Selection normalization seam

Current stock anchor:

```js
let _h=Tt((jt)=>jt.footerSelection),Lm=_h&&ss.includes(_h)?_h:null;wo.useEffect(()=>{if(_h&&!Lm)St(ors)},[_h,Lm,St]);let lm=Lm==="tasks",ZE=Lm==="workflows",Hd=Lm==="tmux",Zp=Lm==="bagel",AT=Lm==="bridge",Mm=Lm==="frame";
```

Required rewrite shape:

```js
let _h=Tt((jt)=>jt.footerSelection),Lm=_h&&ss.includes(_h)?_h:null;wo.useEffect(()=>{if(_h&&!Lm)St(ors)},[_h,Lm,St]);let HC=Lm==="hiddenContext",TT=Lm==="thinking",RM=Lm==="reminders",lm=Lm==="tasks",ZE=Lm==="workflows",Hd=Lm==="tmux",Zp=Lm==="bagel",AT=Lm==="bridge",Mm=Lm==="frame";
```

Names may follow local minified style, but the comparisons must be explicit real target comparisons.

### Footer movement/action seam

Current stock action-map anchor:

```js
Go({"footer:up":By,"footer:down":d0,"footer:next":o6,"footer:previous":IR,"footer:openSelected":()=>{
```

Current close anchor:

```js
return!1}},{context:"Footer",isActive:!!Lm&&!se});
```

Required behavior:

- `footer:openSelected` has explicit cases for `"hiddenContext"`, `"thinking"`, and `"reminders"` before existing stock cases finish.
- `footer:up` / `footer:down` scroll or row-move only when the selected real drawer is open; otherwise they delegate to existing stock `By` / `d0` movement.
- `footer:next` / `footer:previous` use stock movement among real footer targets when no selected drawer consumes them. Do not implement hover movement.
- `footer:clearSelection` consumes while a real drawer is open and must not close that drawer.
- `footer:close` closes the selected real drawer through drawer-local state and then clears selection consistently with the spike.

A helper wrapper is allowed only if its signature is explicitly real-target-based and local-state-based, for example `__codexFDWrapRealTargetActions(actions, Lm, localDrawerState)`. It must not read a global registry or descriptors.

### Footer binding seam

Current stock binding anchor:

```js
{context:"Footer",bindings:{up:"footer:up","ctrl+p":"footer:up",down:"footer:down","ctrl+n":"footer:down",right:"footer:next",left:"footer:previous",enter:"footer:openSelected",escape:"footer:clearSelection",x:"footer:close"}}
```

Required rewrite: add `space:"footer:openSelected"` only. Do not bind `escape` to close.

### Status-bar selection/status seam

Current status-bar selected-hook anchor:

```js
k=Tt((Me)=>!1)
```

Current status-bar segment anchor:

```js
ue=x.map((Me)=>di.jsx(ELc,{link:Me},Me.key??Me.url)),de=[...[]],fe=n?tNf(s,L,W,F,R,O):[];
```

Required behavior:

- The status-bar selected state must derive from normalized real target selection when that value is available in the status-bar function.
- If the status-bar function cannot access normalized `Lm`, raw `footerSelection` may be used only with a companion proof/test that the real target is in the current target list and cannot be stale.
- Do not use raw `footerSelection === "drawers"`.
- Do not render a single synthetic `FDbar` segment.
- Render explicit real-target segments for Hidden Context, Thinking, and Reminders.

### Status-bar visibility/render seams

Current shortcut/null/render anchors include:

```js
if(de.length===0&&!we&&!le&&!ie&&ue.length===0&&!ve&&n)
```

```js
if(de.length===0&&!we&&!le&&!ce&&!ie&&ue.length===0&&!ve)return Ys()?di.jsx(v,{children:" "}):null;
```

```js
ue.length>0&&di.jsxs(B,{flexShrink:0,children:[di.jsx(qn,{children:ue}),(we||de.length>0)&&di.jsx(v,{dimColor:!0,children:" \xB7 "})]}),we&&di.jsxs(B,{flexShrink:0,children:[we,de.length>0&&di.jsx(v,{dimColor:!0,children:" \xB7 "})]}),de.length>0&&di.jsx(v,{wrap:"truncate",children:di.jsx(qn,{children:de})})
```

Required behavior: these conditions/render fragments may be adjusted only to keep explicit real drawer segments visible. They must not introduce a synthetic drawer toolbar component.

### Bottom-overlay seam

Current stock overlay anchor:

```js
function Ilc(){let e=MXe.c(2),t=clc();if(!t)return null;let n;if(e[0]!==t)n=Xd.jsx(B,{position:"absolute",bottom:"100%",left:0,right:0,opaque:!0,children:t}),e[0]=t,e[1]=n;else n=e[1];return n}
```

Required behavior: compose stock `clc()` overlay with explicit panel functions. Each panel function returns null unless its own drawer-local open state is true and its real target is selected.

## Known-good spike behavior to preserve

Reference commit:

- `9e2ef5811bba0957d7b0a9c31b93d2696f3feded`

Important spike facts:

- Hidden Context inserted real target `"hiddenContext"` into the target list from same-render frame availability.
- Reminders inserted real target `"reminders"` into the same target list, after Hidden Context when present.
- Selection normalized through the stock selected target list.
- Hidden Context open behavior was a direct `case "hiddenContext"` in `footer:openSelected`.
- Reminders action behavior was a wrapper that returned unchanged actions unless selected target was exactly `"reminders"`.
- Status-bar hints came from the real selected target.
- Escape/clearSelection did not close an open drawer; `x`/close did.

Thinking is an extension in this stack, not evidence from the spike. It must copy the Hidden Context real-target/open/scroll shape without changing the Hidden Context or Reminders behavior.

## Required real footer targets

The footer target list must contain real drawer target ids, in drawer order, before stock task/workflow targets:

```text
hiddenContext
thinking
reminders
tasks
workflows
tmux
bagel
bridge
frame
```

Availability rules:

- `hiddenContext` appears only when the same-render Hidden Context frame is visible.
- `thinking` appears when the Thinking drawer package contributes its explicit target-list payload; the panel may display an empty state.
- `reminders` appears when the Reminders package contributes its explicit target-list payload.
- Existing stock targets keep their existing availability rules.

The important point is that `footerSelection` must become one of the real drawer ids. It must never become a synthetic parent target.

## Hidden Context availability rule

No global availability callback is allowed for Hidden Context target construction.

In the `2.1.201` footer target seam, compute the frame immediately before `ss=wo.useMemo(...)`, insert `__codexHiddenContextFrame?.visible && "hiddenContext"` in that same target list, and include `__codexHiddenContextFrame?.generation` in that same dependency array.

The repair must restore the spike's local frame/prop-threading pattern for Hidden Context and pass that frame to both the target-list and status-bar seams. A generic callback like this is forbidden for target construction:

```js
available:()=>!!globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_FRAME_V13__?.visible
```

## Selection flags

After stock normalization:

```js
let _h = Tt((state)=>state.footerSelection)
let Lm = _h && ss.includes(_h) ? _h : null
```

add real drawer flags:

```js
let HC = Lm === "hiddenContext"
let TT = Lm === "thinking"
let RM = Lm === "reminders"
```

Do not create `FDs = Lm === "drawers"`.

Status-bar selection must come from the same real-target source of truth:

```js
hiddenContextSelected = Lm === "hiddenContext"
thinkingSelected = Lm === "thinking"
remindersSelected = Lm === "reminders"
```

If the status-bar render function cannot access `Lm`, it may use raw `footerSelection` only if tests prove the raw target is present in the current target list and cannot be stale. The plan must call this out explicitly if it chooses that fallback.

## Key routing contract

### Closed drawer targets

When a real drawer target is selected and the drawer is closed:

- `enter` opens that selected drawer.
- `space` opens that selected drawer.
- `left` / `right` use the stock footer target movement path.
- `up` / `down` use the stock footer target movement path.
- `escape` / `footer:clearSelection` does not close a drawer because no drawer is open.
- `x` / `footer:close` may fall through to stock close behavior.

### Open Hidden Context

When `hiddenContext` is selected and open:

- `up` scrolls up inside the Hidden Context panel.
- `down` scrolls down inside the Hidden Context panel.
- `enter` does not invent a second mode.
- `space` does not invent a second mode.
- `escape` / `footer:clearSelection` is consumed and must not close the drawer.
- `x` / `footer:close` closes the drawer and clears footer selection, as in the spike.

### Open Thinking

Thinking follows the Hidden Context shape as a deliberate extension:

- `up` / `down` scroll the Thinking panel.
- `enter` / `space` do not invent a second toolbar mode.
- `escape` / `footer:clearSelection` is consumed and must not close the drawer.
- `x` / `footer:close` closes the drawer and clears footer selection.

Thinking must not check `__CODEX_FOOTER_DRAWERS_V1__?.openId === "thinking"`. Open/selected state must come from `TT = Lm === "thinking"` plus Thinking-local open state.

### Open Reminders

Reminders follows the spike's wrapper behavior:

- `up` / `down` move the reminders row cursor.
- `enter` / `space` toggles the selected row when already open.
- `escape` / `footer:clearSelection` is consumed and must not close the drawer.
- `x` / `footer:close` closes the drawer, then delegates to clear selection like the spike.

## Status-bar contract

The status bar renders one segment per available real drawer target.

The segment text mirrors the spike and must not add framework badges:

```text
Hidden Context <tokens>t (enter)    when selected
Hidden Context <tokens>t \u2192     when not selected
Thinking (enter)                    when selected
Thinking \u2192                     when not selected
Reminders (enter)                   when selected
Reminders \u2192                    when not selected
```

Rules:

- The selected segment is the segment whose real target id equals normalized `Lm` or a proved-equivalent real target selection value.
- Unselected segments show `\u2192`.
- The selected segment shows ` (enter)`.
- Hidden Context unread/flash styling follows the spike: flash only when not selected; clear flash on open/scroll.
- Thinking unread/flash may follow the existing Thinking drawer state, but it must not change navigation semantics.
- Reminders dimming/selection follows the spike's `__CODEX_REMINDERS_SELECTED_V1__` equivalent and must derive from the real selected target.
- Do not add descriptor-produced counts such as Hidden Context event count or Reminders `3/7` suppression count to the status-bar segment unless the user explicitly asks later.

The status bar must not be a single synthetic `FDbar` whose internal selected item is separate from footer selection.

## Overlay contract

The bottom overlay may be shared, but each panel must decide whether it is visible from its own real open/selected state.

Required behavior:

- Hidden Context panel renders only when `hiddenContext` is selected, Hidden Context local open state is true, and the frame is visible.
- Thinking panel renders only when `thinking` is selected and Thinking local open state is true.
- Reminders panel renders only when `reminders` is selected and Reminders local open state is true.
- Stock overlay content remains present.
- Only one drawer panel may be visible. Do not enforce this with shared open state; each panel returns null unless its own local open state is true and its real footer target is selected.

Allowed shared-framework implementation:

```text
shared overlay mount
  -> stock overlay
  -> Hidden Context panel function, returns null unless local open + selected real target
  -> Thinking panel function, returns null unless local open + selected real target
  -> Reminders panel function, returns null unless local open + selected real target
```

Forbidden shared-framework implementation:

```text
global openId
  -> render descriptor matching openId
```

## Package responsibilities

### `packages/footer-drawers`

This package should become the owner of shared exact seams, but only in a spike-faithful way.

It may own:

- pure helper functions for formatting real-target drawer segments,
- exact-seam payloads for target list, selection flags, action map, status bar, overlay, and space binding,
- tests proving there is no synthetic `drawers` target and no runtime drawer registry.

It must not own:

- synthetic toolbar selection,
- hover state,
- open state,
- drawer availability callbacks,
- drawer descriptors,
- drawer registration.

### `packages/hidden-context-drawer`

Restore the spike's behavior, ported to `2.1.201` names/anchors:

- Keep projection-list frame construction from the rich pre-filter source.
- Restore local frame availability at the footer target seam. Do not use a global availability callback.
- Add real target `"hiddenContext"` to the footer target list.
- Add real selected flag `HC = Lm === "hiddenContext"`.
- Add openSelected case for `"hiddenContext"`.
- Keep `escape` off-limits; `x` is close.
- Render the status-bar segment from the actual frame and actual real-target selection.
- Delete/replace `packages/hidden-context-drawer/payloads/17-register-footer-drawer.js`.

### `packages/thinking-text-drawer`

Add Thinking as a real drawer target, not as a synthetic framework descriptor:

- Keep current thinking text collectors.
- Add real target `"thinking"` in the shared real-target order.
- Add real selected flag `TT = Lm === "thinking"`.
- Add openSelected behavior for `"thinking"`.
- Use Hidden Context's scroll/open/close shape for the panel.
- Render `Thinking (enter)` / `Thinking \u2192` from real target selection.
- Remove all `__CODEX_FOOTER_DRAWERS_V1__` / `openId` checks from Thinking helpers.
- Delete/replace `packages/thinking-text-drawer/payloads/17-register-footer-drawer.js`.

### `packages/reminders-manager`

Restore the spike's behavior, ported to `2.1.201` names/anchors:

- Keep runtime deny/filter seams.
- Add real target `"reminders"` after `hiddenContext`/`thinking` and before stock tasks.
- Derive reminders selected state from normalized real target selection.
- Use the spike wrapper shape: `__codexRMWrapActions(actions, selectedTarget)` where it activates only when `selectedTarget === "reminders"`.
- Render `Reminders (enter)` / `Reminders \u2192` from real target selection.
- Delete/replace `packages/reminders-manager/payloads/rm-register-footer-drawer-2.1.201.js`.

## Concrete current implementation reversals

The next patch must remove or replace the current synthetic-framework payload concepts.

### Required deletions/replacements

- Delete/replace `packages/hidden-context-drawer/payloads/17-register-footer-drawer.js`.
- Delete/replace `packages/thinking-text-drawer/payloads/17-register-footer-drawer.js`.
- Delete/replace `packages/reminders-manager/payloads/rm-register-footer-drawer-2.1.201.js`.
- Remove every runtime reference to `__CODEX_FOOTER_DRAWERS_V1__`.
- Remove every runtime reference to `__codexFDDrawers`.
- Remove every runtime reference to `__codexFDRegister` or `.register({id:` drawer descriptors.
- Remove every runtime reference to framework `hoverId`, framework `openId`, and framework `active`.
- Remove every runtime reference to `__codexFDLand` and `__codexFDMove`.

### Footer-drawers payload replacements

- Replace `packages/footer-drawers/payloads/01-bootstrap-and-overlay.js` with pure real-target helpers/overlay composition. It must have no `hoverId`, `openId`, `active`, `__codexFDLand`, `__codexFDMove`, registry, or descriptor API.
- Delete/replace `packages/footer-drawers/payloads/02-footer-render-tick-state.js` and `03-footer-render-tick-effect.js` unless a render tick is needed for drawer-local data and is proven to be read by the exact render surface using it.
- Replace `packages/footer-drawers/payloads/04-footer-target-drawers.js`; it must insert real ids, not `"drawers"`.
- Replace `packages/footer-drawers/payloads/05-footer-target-deps.js`; dependencies must match actual local frame/state inputs, especially Hidden Context frame generation.
- Replace `packages/footer-drawers/payloads/06-footer-selection-flag.js`; it must add real drawer flags, not `FDs`.
- Replace `packages/footer-drawers/payloads/07-footer-action-wrap-open.js` and `08-footer-action-wrap-close.js`; wrapping must dispatch by real `Lm`, not synthetic toolbar mode.
- Keep `packages/footer-drawers/payloads/09-footer-space-binding.js` only if exact anchor still matches and behavior remains `space -> footer:openSelected`.
- Replace `packages/footer-drawers/payloads/10-footer-bar-var.js`, `13-footer-bar-render.js`, and `14-footer-bar-selection-state.js`; they must render real-target drawer segments, not one synthetic segment.
- Keep/adjust `11` and `12` only to prevent real drawer segments from being hidden by stock status-bar null/shortcut logic.

## Required pre-plan decisions

The implementation plan must resolve these before code is touched:

1. Which package owns each exact seam in the 2.1.201 seam map.
2. How Hidden Context's same-render frame is threaded into target construction and status-bar rendering.
3. Whether the status-bar function can access normalized `Lm`; if not, what proof makes raw real-target `footerSelection` safe.
4. How Thinking local open state is represented without `__CODEX_FOOTER_DRAWERS_V1__` or `openId`.
5. How the Reminders wrapper from the spike is ported without descriptor callbacks.

Do not answer these by inventing a runtime registry. The answer must be explicit real-target wiring.

## Required implementation sequence for the future plan

The future implementation plan must follow this behavioral order:

1. **Freeze the known-good reference.** Use commit `9e2ef5811bba0957d7b0a9c31b93d2696f3feded` as the behavioral reference for Hidden Context + Reminders. Do not infer behavior from the broken current framework.
2. **Port the real-target target-list behavior to `2.1.201`.** Get `hiddenContext`, `thinking`, and `reminders` into the real footer target list in the required order.
3. **Port selected flags and status-bar hints.** Prove the bar text changes from `\u2192` to `(enter)` solely because the real target id is selected.
4. **Port action routing.** Prove `enter` opens the selected real target and `x` closes it. Do not implement drawer hover.
5. **Port open-panel behavior.** Prove each panel returns null unless its own selected/open state is active.
6. **Only then factor repeated code into pure helpers.** If factoring changes semantics, reject the factoring.
7. **Build the combined package stack.** Use the target source identity above unless the user authorizes retargeting.
8. **Run structural tests before handoff.** A version call alone is not enough.

## Required tests before another binary handoff

### Structural no-synthetic tests

The composed module must satisfy:

- Contains real target ids: `"hiddenContext"`, `"thinking"`, `"reminders"` in footer target/action/bar surfaces.
- Does not contain `"drawers"` as a footer target.
- Does not contain `footerSelection==="drawers"` or `footerSelection === "drawers"`.
- Does not contain `id:"drawers"` or `id: "drawers"`.
- Does not contain `__CODEX_FOOTER_DRAWERS_V1__`.
- Does not contain `__codexFDDrawers`.
- Does not contain `__codexFDRegister`.
- Does not contain descriptor fields `available:`, `onOpen:`, `onClose:`, `onKey:`, or `renderPanel:` as part of a drawer registration object.
- Does not contain `hoverId`.
- Does not contain framework `openId`.
- Does not contain framework `active`.
- Does not contain `__codexFDLand`.
- Does not contain `__codexFDMove`.
- Does not contain `FDsel=Tt((...footerSelection==="drawers"...))` or any equivalent selected-state hook for `"drawers"`.

### Source-of-truth tests

Add tests that inspect the composed module and prove:

- target construction includes real drawer ids before `tasks`,
- Hidden Context target construction uses same-render frame generation dependency,
- selected flags compare `Lm` to real drawer ids,
- status bar compares against normalized real target selection or a proved-equivalent raw real target selection,
- action routing dispatches by real selected target id,
- Reminders wrapper still activates only for `selectedTarget === "reminders"`,
- Hidden Context clearSelection consumes without closing,
- Thinking does not read `__CODEX_FOOTER_DRAWERS_V1__?.openId`,
- `x` close exists for all three drawer panels,
- no panel can render unless its local open state and real selected target are both true.

### Build/smoke

Before user handoff:

1. Run the relevant package/composition test subset.
2. Build the full stack with footer-drawers + hidden-context-drawer + thinking-text-drawer + reminders-manager.
3. Smoke the binary with `--version` only after structural tests pass.
4. State clearly that full interactive testing remains with the user unless we have performed the interactive smoke ourselves.

## Acceptance criteria

The implementation is acceptable only if all of these are true:

- Down from the prompt lands on the first available real drawer target.
- The highlighted segment is the segment whose real target id is selected.
- Right/left move between drawer segments through stock footer target movement.
- Enter opens the selected real drawer.
- There is no separate hover model to synchronize.
- Hidden Context, Thinking, and Reminders panels open and close through their real target plus local drawer state.
- Escape does not close drawers.
- `x` closes drawers.
- The composed module contains no synthetic `drawers` footer target.
- The composed module contains no runtime drawer registry or descriptor registration.

## Implementation-plan readiness checklist

This spec is ready to become an implementation plan only when review agrees that it has:

- fully superseded the synthetic old plan,
- banned runtime registries/descriptors without loopholes,
- required Hidden Context same-render frame availability,
- named the exact `2.1.201` seams,
- required deletion/replacement of all current bad registrant payloads,
- handled Thinking as an extension without corrupting spike behavior,
- required tests that fail hard on the previous synthetic framework failure mode.

## Bottom line

The correct fix is not to repair the synthetic framework. The correct fix is to delete the synthetic interaction model and port the spike's real-target model faithfully into the shared package layout.
