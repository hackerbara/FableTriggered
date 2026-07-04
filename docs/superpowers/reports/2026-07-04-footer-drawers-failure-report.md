# Footer Drawers Failure Report — 2026-07-04

## Scope

This is a failure report, not a patch plan and not a defense brief.

No implementation code is changed by this document. The current footer-drawers framework should be treated as suspect end-to-end until proven otherwise against the known-good spike and against the composed binary behavior.

Current user-visible failure after commit `858bd58 fix: repair footer drawer toolbar focus`:

- Arrowing down can now land on the footer drawer bar.
- Once on the bar, `Enter` does not visibly open the drawer.
- Once on the bar, sideways arrows do not visibly move across drawers.
- The bar/interaction still does not behave like the known-good working artifact.

## Executive conclusion

The current implementation cannot honestly be defended as a faithful port of the working spike.

The working spike used real footer targets and the stock footer-selection/action path as the source of truth. The current framework replaced that with one synthetic footer target, `"drawers"`, plus a separate global registry containing `hoverId`, `openId`, `active`, and `version`. That introduced a second interaction state model. The implementation then failed to prove that every visible consumer of that model — the footer bar, the action wrapper, and the overlay panel — was subscribed to the same state changes.

The result is exactly the kind of failure the user is seeing: entering the synthetic footer target can update the bar selection once, while subsequent left/right/open mutations happen in registry globals that the visible bar and overlay are not reliably forced to re-render from.

The tests and smoke checks I relied on were not adequate. They verified helper functions, build composition, and version execution, but they did not verify the end-to-end interactive contract inside the composed renderer.

## Known-good spike: what it actually did

Evidence source:

- Commit: `9e2ef5811bba0957d7b0a9c31b93d2696f3feded`
- Subject: `Toolbar UX for footer drawers: order, hints, land-once nav; framework spec + engine handoff`
- Artifact: `/Users/MAC/Documents/Claude-patch/.development/claude-monkey-builds/reminders-drawer-stacked/claude`
- Session noted in commit metadata: `https://claude.ai/code/session_018zrBCPwdzsEvrbCsyiJfGz`
- Transcript path: `/Users/MAC/.claude/projects/-Users-MAC-Documents-Claude-patch/ad6525db-553d-4c2d-97b0-364f6fff75b5.jsonl`

Important caveat: the spike was the known-good user-tested behavior for that stage. It should not be overclaimed as a final generalized framework. But it had the interaction behavior that needed to be preserved.

### 1. It used real stock footer targets

Hidden Context was inserted into the actual footer target list:

```js
ji=Ro.useMemo(()=>[
  __codexHiddenContextFrame?.visible&&"hiddenContext",
  Uo&&"tasks",
  ro&&"workflows",
  Jt&&"tmux",
  be&&"bagel",
  Hr&&"bridge",
  Oe&&"frame"
].filter(Boolean),[Uo,ro,Jt,be,Hr,Oe,__codexHiddenContextFrame?.generation])
```

Reminders then inserted itself into that same target list, immediately after Hidden Context when present:

```js
var __rmI=ji.indexOf("hiddenContext");
ji=__rmI>=0?[...ji.slice(0,__rmI+1),"reminders",...ji.slice(__rmI+1)]:["reminders",...ji];
let Ly=Tt((Bt)=>Bt.footerSelection),Du=Ly&&ji.includes(Ly)?Ly:null;
globalThis.__CODEX_REMINDERS_SELECTED_V1__=Du==="reminders";
```

That means the spike did not invent a separate synthetic selection model. It let the stock footer system select real drawer targets.

### 2. It normalized selection through the stock footer-selection path

The stock path was still the source of truth:

```js
Ly=Tt((Bt)=>Bt.footerSelection)
Du=Ly&&ji.includes(Ly)?Ly:null
```

That value controlled Footer context activation:

```js
Wo(__codexRMWrapActions(...,Du),{context:"Footer",isActive:!!Du&&!oe})
```

The key fact: the same normalized selected target that made the footer active also decided which drawer behavior wrapper applied.

### 3. Hidden Context open behavior was a direct target case

Hidden Context added a real `case "hiddenContext"` inside the stock `footer:openSelected` switch:

```js
case"hiddenContext":{
  globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_OPEN_V13__=!0,
  hCp(!0);
  if(__codexHiddenContextFrame)__codexHiddenContextFrame.flashUntil=0;
  break
}
```

So `Enter` worked because the stock footer target was actually `hiddenContext`, and the open action was in the same stock action path.

### 4. Reminders open behavior wrapped actions only when the real target was selected

Reminders wrapped footer actions only if the selected footer target was exactly `"reminders"`:

```js
function __codexRMWrapActions(e,t){
  if(t!=="reminders")return e;
  let n=__codexRMUIState(),r=Object.assign({},e);
  r["footer:openSelected"]=()=>{
    if(!n.open){
      n.open=!0,n.cursor=0,__codexRMBump();return
    }
    ...
  };
  ...
  return r
}
```

Again, there was no synthetic hover/open target needing synchronization with a separate footer target.

### 5. Bar state was derived from the real selected target

Hidden Context bar selection:

```js
hCsel=Tt((Ne)=>Ne.footerSelection==="hiddenContext")
```

Reminders bar selection:

```js
globalThis.__CODEX_REMINDERS_SELECTED_V1__=Du==="reminders"
```

Then the bar rendered selected/unselected hint text from that real selection state:

```js
children:globalThis.__CODEX_REMINDERS_SELECTED_V1__?"Reminders (enter)":"Reminders →"
```

Hidden Context similarly rendered `"(enter)"` when selected and an arrow hint when not selected.

### 6. The spike’s contract was simple

For the drawer interaction path, the spike effectively had one chain:

```text
footerSelection
  -> normalized selected real target
  -> Footer context active
  -> target-specific footer actions
  -> target-specific open/scroll state
  -> bar hint derived from same selected target
```

That is the important thing I failed to preserve.

## Current framework: what I implemented

Current branch/worktree:

- Worktree: `/Users/MAC/.config/superpowers/worktrees/Claude-patch/footer-drawers-framework`
- Branch: `codex/footer-drawers-framework`
- Current commit: `858bd58 fix: repair footer drawer toolbar focus`

### 1. It created a synthetic stock target

The current framework inserts a single footer target:

```js
__codexFDAvailable().length&&"drawers"
```

So the stock footer system no longer selects `"hiddenContext"`, `"thinking"`, or `"reminders"` as separate targets. It selects only `"drawers"`.

### 2. It created a separate global registry state model

The framework registry stores drawer interaction state separately from stock footer selection:

```js
{
  entries,
  hoverId,
  openId,
  active,
  version
}
```

The current helper functions then mutate that state:

- `__codexFDSetActive(...)`
- `__codexFDLand(...)`
- `__codexFDMove(...)`
- `__codexFDOpen(...)`
- `__codexFDClose(...)`
- `__codexFDBump(...)`

This means the framework has two sources of truth:

```text
stock state: footerSelection === "drawers"
registry state: hoverId/openId/active/version
```

That split is the central architectural risk.

### 3. The action wrapper depends on stock `Lm`

The composed action wrapper is installed as:

```js
Go(__codexFDWrapActions({
  "footer:up":By,
  "footer:down":d0,
  "footer:next":o6,
  "footer:previous":IR,
  "footer:openSelected":()=>{...},
  "footer:clearSelection":()=>{...},
  "footer:close":()=>{...}
},Lm,Rp),{context:"Footer",isActive:!!Lm&&!se});
```

The wrapper only has authority if the stock normalized selected target is `"drawers"` or a drawer is already open.

### 4. The visible bar lives in a different render surface

The bar is rendered in the status-bar/footer-bar surface:

```js
FDsel=Tt((Me)=>Me.footerSelection==="drawers")
FDact=__codexFDSetActive(FDsel)
FDbar=__codexFDAvailable().length>0?__codexFDBar(FDsel):null
```

This improved one bug: it no longer reads an unrelated minified `FDs` binding. But it still means the visible bar subscribes only to `footerSelection === "drawers"`. It does not obviously subscribe to registry `version`, `hoverId`, or `openId`.

Therefore:

- Arrow down can change `footerSelection` and cause the bar to re-render as selected.
- Left/right can mutate registry `hoverId` without causing this bar surface to re-render.
- Enter can mutate registry `openId` without causing this bar surface or overlay surface to re-render.

That matches the current symptom.

### 5. The overlay also reads registry state without a proven subscription

The overlay renderer calls:

```js
__codexFDDrawerPanel()
```

That panel is derived from registry `openId`. But if opening only mutates registry state, the overlay needs a reliable render trigger. The current design does not prove that the overlay render surface subscribes to registry version changes.

### 6. Polling was added in the prompt/footer component, not in every consumer

The current implementation added polling state:

```js
[FDv,FDsv]=wo.useState(0)
```

and a polling effect against registry version. That `FDv` was included in the footer target `useMemo` dependencies.

This may re-render the prompt/footer component. It does not automatically prove that the separate status-bar surface and overlay surface re-render when `hoverId` or `openId` changes. I treated one component’s polling as if it made the whole interaction reactive. That was not proven and is likely false or incomplete.

## Divergences from the spike

| Area | Known-good spike | Current framework | Honest assessment |
|---|---|---|---|
| Footer targets | Real targets: `hiddenContext`, `reminders` | One synthetic target: `drawers` | Major divergence. Not inherently impossible, but not faithful and not proven. |
| Selection source | Stock `footerSelection` selects the actual drawer target | Stock `footerSelection` selects only `drawers`; registry decides hovered drawer | Major added synchronization burden. |
| Bar selected state | Derived from the real selected target | Derived from raw `footerSelection === "drawers"` plus registry hover | Split state. Visual selected can exist while hover/open state does not re-render. |
| Action routing | Stock Footer context and selected real target route actions | Wrapper intercepts actions for synthetic target and global open state | More complex and less directly tied to stock behavior. |
| Left/right | Stock target movement between real targets | Registry hover movement inside synthetic target | Needs separate render subscription; not proven. |
| Enter | Real selected target opens its drawer in stock action path | Registry `openId` changes and drawer `onOpen` fires | Needs overlay/bar re-render; not proven. |
| Hidden Context availability | Function-local frame value in target construction | Global frame availability callback | Reintroduces stale-global risk that the spec itself warned about. |
| Reminders | Direct wrapper around selected `"reminders"` target | Descriptor inside generic registry | Loses the direct proof that selected target and action target are the same. |
| Thinking | Not part of the two-drawer working spike | Added as a third descriptor | New requirement from later plan, but it made faithful porting harder and needed stronger proof. |
| Tests | Interactive behavior was user-tested in artifact | Helper/unit/composition/version smoke | My tests did not exercise the actual composed key-to-render loop. |

## What is completely fucked / undefended

### 1. I defended the synthetic-target design without proving its state model

The synthetic `"drawers"` target may be a valid design, but I did not prove it. The working spike did not require it. By introducing it, I took on responsibility for synchronizing:

```text
stock selected target
registry active state
registry hover state
registry open state
bar render state
overlay render state
Footer context action routing
```

I did not prove that synchronization end-to-end.

### 2. I mistook helper correctness for UI correctness

The helper tests can show that `__codexFDMove()` changes `hoverId` and that `__codexFDOpen()` changes `openId`. They do not show that the composed renderer visibly updates when those globals change.

That was the wrong verification surface.

### 3. I over-trusted build/version smoke

A binary version call only proves that the package composed and the executable starts. It says almost nothing about the interactive footer context, key routing, or visible overlay/bar behavior.

The user explicitly said they would do full interactive testing, but the implementation still needed enough programmatic verification to avoid handing over something whose core interaction loop was unproven.

### 4. I treated the first found bug as the root problem

The prior P0 bug was real:

- `packages/footer-drawers/payloads/10-footer-bar-var.js` used `__codexFDBar(FDs)`.
- In that status-bar surface, `FDs` resolved to an unrelated top-level minified binding, not the prompt/footer selected flag.

Fixing that made arrow-down entry more visible, but it did not establish that the overall design was correct. I let a real bug narrow attention too much.

### 5. I reintroduced a stale-global risk that the spec warned about

The spec warned that footer availability computed from a function-local value and published globally later could go stale. The current Hidden Context descriptor uses:

```js
available:()=>!!globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_FRAME_V13__?.visible
```

That means the framework availability path still depends on global frame publication timing instead of the local value at target-list construction. This is a known risk, not an acceptable settled design.

### 6. I failed to faithfully preserve the spike’s source-of-truth chain

The spike’s source-of-truth chain was:

```text
footerSelection -> real selected drawer target -> action wrapper/case -> open state -> visible drawer
```

The framework chain became:

```text
footerSelection == "drawers"
  -> registry active/hover/open globals
  -> bar/overlay read globals if they happen to re-render
```

That is not a faithful port. It is a new architecture.

### 7. I added a third drawer before proving the two-drawer behavior

The later plan wanted footer + hidden context + reminders + thinking together. But the known-good spike that needed faithful translation was a two-drawer Hidden Context + Reminders artifact. Adding Thinking as another descriptor was not wrong by itself, but doing it before proving the core interaction model increased the number of moving parts while the model was still unverified.

### 8. The action context and bar context can diverge

The visible bar currently checks raw store state:

```js
footerSelection === "drawers"
```

The action context uses normalized local selection:

```js
Lm = selected target if included in current footer target list, else null
```

If availability/timing makes raw `footerSelection` equal `"drawers"` while normalized `Lm` is null, the bar can look selected while Footer actions are not active for the drawer wrapper. I have not proven this is the current exact failure, but the design permits it.

### 9. The reportable current symptom points to missing render subscription, not a one-line action bug

The symptom sequence matters:

```text
Down works enough to show entry.
Sideways does not visibly move.
Enter does not visibly open.
```

That pattern is consistent with:

```text
footerSelection update causes one render
registry hover/open updates do not cause the visible surfaces to render
```

So the failure is not honestly reducible to a missing `case`, a missing key binding, or one wrong variable. It is a state ownership/render subscription failure unless disproven by deeper composed inspection.

## What a defensible repair would need to prove

No repair should be attempted until one of these designs is explicitly chosen and defended.

### Option A: Return to real footer targets

This is closest to the working spike.

Under this design:

- `hiddenContext`, `thinking`, and `reminders` become real footer targets.
- Stock `footerSelection` remains the source of truth.
- Bar hints derive from the real selected target.
- `Enter` routes through target-specific cases/wrappers.
- Left/right either uses stock target movement or a thin wrapper over stock target movement.

This would reduce the amount of synthetic state that has to be synchronized.

### Option B: Keep one synthetic `drawers` target, but make state ownership real

If the synthetic target is kept, it must not rely on ad-hoc global mutation plus hope of re-render. It needs a real subscription path for every consumer:

- The action wrapper must consume the same active/hover/open state as the bar.
- The status bar must re-render when hover/open/version changes.
- The overlay must re-render when open/version changes.
- The target availability must not depend on stale global publication unless that timing is proven safe.
- Tests must exercise the composed key-to-visible-output loop, not only helper mutation.

This option is more architecture than the spike had. It may be worthwhile only if the framework abstraction is truly needed.

## Minimum required verification before another binary handoff

The previous verification was insufficient. A future handoff should not be called ready unless these are covered somehow.

### 1. Composed action-chain verification

A test or diagnostic must prove, against the composed output, that:

1. When the footer target is `"drawers"`, the Footer context is active.
2. `footer:next` / `footer:previous` changes the drawer selected/hovered item used by the visible bar.
3. `footer:openSelected` causes the selected drawer panel to become visible.
4. `footer:clearSelection` / close behavior matches the intended contract.

### 2. Render-subscription verification

A test or static assertion must prove that every component reading registry `hoverId` or `openId` also has a render trigger tied to registry `version` or equivalent React state.

At minimum this includes:

- the footer drawer bar renderer,
- the overlay drawer panel renderer,
- the prompt/footer action owner if it computes availability from registry state.

### 3. Faithfulness check against the spike

Before another build, the implementation should be checked against the spike’s end-to-end chain:

```text
target construction
selection normalization
bar selected/hint rendering
Footer context activation
action routing
open/close side effects
scroll behavior
render invalidation
```

Every intentional divergence must have a reason. Every unintentional divergence should be treated as a bug.

### 4. Actual interactive smoke before asking the user to fully test

The user can still do full interactive testing, but the implementation owner should at least smoke the core path before handoff:

```text
arrow down to drawer bar
sideways across drawer items
enter opens selected drawer
up/down scrolls open drawer where applicable
close exits drawer without corrupting footer selection
```

If that cannot be performed programmatically, it should be stated as unverified, not implied by a version call.

## Bottom line

The current implementation is not a careful faithful port of the known-good working spike. It is a partially working new framework whose central state model was not proven. The most likely fundamental failure is that registry hover/open state is mutated by actions but not reliably subscribed to by the visible bar and overlay render surfaces.

The next correct move is not another local one-line fix. The next correct move is to choose whether the framework should return to the spike’s real-target model or make the synthetic-target model genuinely reactive and then verify the entire interaction chain before another binary handoff.
