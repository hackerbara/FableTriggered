# Handoff: additive/insertion splices for multi-package composition

**Audience:** an agent designing improvements to the ClaudeMonkey composition engine. **Not a solution** — a verified problem statement so you can reproduce, confirm, and design fixes. Everything here is byte-checkable against stock Claude Code 2.1.199 (`cli.js` module sha `e30c857c2e1130ff0fa9d14349a210c588f8115fc8ac86e120c454547efc0c55`, 18,593,981 bytes; dump at `.development/tmp-module0-2.1.199.js`).

## The one-paragraph version

The engine only has **whole-span replacement** ops (`replace_exact`, `replace_between`). Two packages that both want to modify the *same stock statement* cannot — `_check_overlaps` hard-rejects overlapping byte ranges. Today we work around this with fragile "downstream reassignment" tricks and by making one package restate orthogonal stock logic it doesn't own. This blocks a clean "shared framework + thin registrants" architecture. The likely fix is an **additive/insertion op type**: multiple packages declaring "insert these bytes at anchor point P" (a zero-width point, deterministically ordered), so co-editing a shared statement needs no overlapping ranges.

## How the engine composes today (verify in code)

- `src/claude_monkey/module_patch.py` — `plan_module_operations()` locates each op's byte range in the **original stock module**; `render_changed_module()` splices replacements by cursor. Overlap check at ~line 120: any `left.module_end > right.module_start` raises `overlap:`.
- `src/claude_monkey/builder_v15.py` — `_check_overlaps()` (~line 281) does the same across ALL enabled packages' planned ops. Every op anchors in **stock** text; there is no sequential application (package B never sees package A's output).
- Op types (`manifest_v2.py`): `replace_exact` (range = the exact anchor substring) and `replace_between` (range = startMarker start → endMarker start). **Both replace a whole contiguous span.** There is no "insert at offset," no "replace sub-match within a range," no shared insertion point.

**Consequence:** to change one clause of a statement, a package must restate the whole statement. Two packages wanting to touch the same statement necessarily claim overlapping ranges → build fails.

## Byte-proven example A — the `ji` footer-targets array (shared-append collision)

Stock, offset **15,099,459**, inside function `VOf` `[15094473, 15131813]`:

```
ji=Ro.useMemo(()=>[Uo&&"tasks",ro&&"workflows",Jt&&"tmux",be&&"bagel",Hr&&"bridge",Oe&&"frame"].filter(Boolean),[Uo,ro,Jt,be,Hr,Oe])
```

Both drawers want to add an entry (`"hiddenContext"`, `"reminders"`) to this array. They cannot both `replace_exact` this statement. Current shipping workaround:
- `hidden-context-drawer` op `axf-messagesref-footer-target-frame` replaces the whole `ji=...` statement, hardcoding `"hiddenContext"` into the array literal.
- `reminders-manager` op `rm-footer-target-append` anchors on the **downstream** `let Ly=...,Du=...` statement and does a bare reassignment `var __rmI=ji.indexOf("hiddenContext");ji=[...slice, "reminders", ...slice];` — i.e. it rebuilds the array *after the fact* because it can't touch the original literal.

This works but: (a) reminders depends on HC's `"hiddenContext"` string appearing, an implicit cross-package coupling the engine doesn't model or protect; (b) it only works because a convenient downstream statement existed to hijack. A third drawer may not find one.

**What an additive engine would allow:** both drawers declare `insert_after: '"frame"]' → ',"hiddenContext"' / ',"reminders"'` with an order key. No overlapping ranges; no downstream hijack; no implicit string coupling.

## Byte-proven example B — bundled orthogonal logic (forced restatement)

Stock, HC op `footer-hiddencontext-selection-flag`, a 115-byte anchor:

```
let qb=Du==="tasks",Pu=Du==="workflows",Uf=Du==="tmux",eC=Du==="bagel",iy=Du==="bridge",Ap=Du==="frame";function Sf
```

To add `hC=Du==="hiddenContext"`, HC restates all six orthogonal stock flags (tasks/workflows/tmux/bagel/bridge/frame) verbatim. Same pattern in op13 (581 bytes bundling `case"hiddenContext"` with tmux/bagel/bridge/frame cases and the whole clearSelection/close handlers) and op16 (1988 bytes bundling the hC bar segment with shortcuts/voice/copy hints).

**Why this matters for a framework:** if a shared `footer-drawers` package "owns" these seams, it must reproduce all that unrelated stock logic, so a future Claude change to *tmux dispatch* would force a change to the *drawers* package. And because both drawers would hard-depend on the framework, one broken anchor takes down both features at once. (This is Finding 2 of the framework review, `2026-07-03-footer-drawers-framework-design.md`.)

**What a sub-span/insertion engine would allow:** insert `,hC=Du==="hiddenContext"` right after `Oe==="frame"` without restating the other flags — the orthogonal stock bytes stay untouched stock, owned by no package.

## What is NOT a patcher problem (don't over-scope the fix)

The framework review's **Finding 1** looks related but isn't an engine issue: stock computes footer availability from function-**local** values (`Uo,ro,Jt,be,Hr,Oe`) at `ji`-construction time, and HC only publishes its frame state to a `globalThis` ~31KB later (op14, end of `VOf`, before `return`). So a drawer `available()` callback located anywhere outside `VOf` reads a **stale** (previous-render) global no matter how clever the splice is. That's a data-flow ordering fact of the stock code — an additive engine does not fix it. (Fix belongs in the framework design: compute availability inline in the array-owning op.) Flagging so the engine work doesn't try to absorb it.

## Suggested shape to evaluate (for the next agent, not prescriptive)

- A `insert_at` / `insert_after` / `insert_before` op: anchor = a unique stock substring; the op contributes bytes at that zero-width point, not a span replacement. Multiple packages may target the **same** anchor; a required integer `order` (or explicit before/after) makes the merge deterministic. `_check_overlaps` would treat insertion points as non-conflicting when ranges are zero-width and distinctly ordered.
- Optionally a `replace_submatch`: within a located range, replace a unique sub-substring — lets a package edit one clause without restating siblings, while still failing loudly if the sub-substring isn't unique in range.
- Open risk to think about: ordering determinism across packages built in different `--package` orders; how postconditions assert on merged output; and whether insertion adjacency (two inserts at the same point) needs the same anti-coupling guarantees `_check_overlaps` gives today.

## How to verify this handoff independently

1. `python3` over the stock dump: confirm the offsets and anchor uniqueness above (`data.count(needle)==1`).
2. Read `module_patch.py` / `builder_v15.py` overlap logic; confirm no additive op type exists in `manifest_v2.py`.
3. Try to author two `replace_exact` ops on the `ji` statement in a scratch package and build — observe the `patch_conflict` / `overlap:` failure. That failure IS the limitation.
4. Cross-read the framework spec (`2026-07-03-footer-drawers-framework-design.md`) Findings 1–3 for the design consequences.
