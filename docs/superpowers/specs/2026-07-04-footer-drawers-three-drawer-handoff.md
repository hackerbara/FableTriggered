# Handoff: fold the Thinking drawer into the footer-drawers framework spec

**Audience:** a fresh-context agent tasked with updating the footer-drawers framework design spec so it ships **three** drawers (hidden-context, reminders, thinking) on a shared framework, instead of two. **This is a spec-writing task, not an implementation task.** You are producing the updated design doc; a later agent implements it.

**Written:** 2026-07-04, by the agent that wrote the current specs, after reading the thinking-drawer package in full. Handing off because the user stepped away mid-task.

---

## 0. The one decision that is NOT yet made (get the user's answer first)

The three drawers are pinned to **different Claude Code versions**:

| Drawer | Version | Binary sha256 | `cli.js` module sha256 |
|---|---|---|---|
| `thinking-text-drawer` | **2.1.201** | `a0852d76afc47b30f5cb0b7625ec9a7714cb189f2eeef6c28c77e2be954fb7fd` | `46db617a7b13c062fb31595f6244819b11f7cdc6e6fed8e2c3f74a27fb6da1bd` (len 18,700,756) |
| `hidden-context-drawer` | **2.1.199** | `e3cb61abc8a2ec7b98976cee1ffdde5a3fa755c9990bc8d688cd89290e0dcec0` | `e30c857c2e1130ff0fa9d14349a210c588f8115fc8ac86e120c454547efc0c55` (len 18,593,981) |
| `reminders-manager` | **2.1.199** | (same 2.1.199 binary as HC) | (same 2.1.199 module as HC) |

The composition engine plans **every op against one stock module** — so all four packages (framework + 3 drawers) MUST target the **same** Claude Code version in a shared build. Someone has to re-anchor.

**The user was asked this exact question and stepped away before answering.** Do not guess. Re-ask, with this recommendation:

- **Recommended: target 2.1.201**, re-anchor hidden-context + reminders *up* from 2.1.199. Rationale: it's the newest, it's where the freshest drawer (thinking) already lives, and it's the version the user is most likely running now. Re-anchoring two packages' footer/deny/projection seams to a new module is real but bounded work.
- Alternative: target 2.1.199, re-anchor the thinking drawer's 17 ops *down* (more ops to move, moves the newest package backward).
- Alternative: version-agnostic, implementer re-anchors all four to whatever's current at build time.

**Everything structural in the spec is version-independent.** Anchor *strings* and *offsets* differ per version, but the spec already says "re-verify every anchor against the target version at implementation time." So you can write the full spec update now and leave a single clearly-marked "TARGET VERSION: <pending user decision>" placeholder plus a note that all cited anchors are examples from whichever version they came from. Don't block the whole doc on the version answer — block only the final anchor-citation pass.

---

## 1. What this project is (orientation for zero context)

**ClaudeMonkey** is a binary-patch manager for Claude Code. Claude Code ships as a Bun standalone Mach-O executable (~232MB) with a minified JS bundle at module path `/$bunfs/root/src/entrypoints/cli.js` (~18.6MB) inside a Bun module graph. "Patch packages" declare byte-level operations against that module; the builder (`build_patchset_v15`) plans all enabled packages' ops against the **original stock** module, renders one changed module, repacks the Bun graph, re-signs, and smoke-tests. Repo root: `/Users/MAC/Documents/Claude-patch`.

**The drawers** are UI patch packages that add openable panels to Claude Code's footer/status-bar area:
- **hidden-context-drawer** — shows hidden/collapsed context.
- **reminders-manager** — a runtime toggle panel for per-family system-reminder suppression (all off by default), session-scoped.
- **thinking-text-drawer** — shows captured raw + structured thinking text (the newest, just hardened for 2.1.201).

**The problem they share:** each drawer independently owns a slice of Claude Code's footer navigation (the footer-target array, the selection flags, the keybinding action map, the status-bar segment, the overlay mount). Under the *old* whole-span-replacement engine, two drawers composed only because their byte ranges happened to be disjoint, and each had to **restate orthogonal stock logic** to touch a shared statement — e.g. to add one footer flag you copy all six stock flags verbatim. Three drawers that all want "which drawer is hovered / land once / left-right between drawers only" cannot cleanly co-own that shared state — one would have to secretly boss the others.

**The two-part solution:**
1. **Composition engine "structured splices"** (zero-width `insert_before`/`insert_after` with deterministic `insertOrder`, `replace_substring_within`, plus `requiresPackages`/`conflictsWithPackages` relationship metadata). This lets multiple packages co-edit one stock statement without overlapping byte ranges, and lets a framework own shared seams while drawers register thin. **STATUS: implemented, reviewed, being finalized — see §2. Assume merged by the time you read this.**
2. **footer-drawers framework** — a new package that owns all the shared footer/overlay seams once, exposes a `globalThis` registry, and each drawer becomes a thin registrant. **STATUS: designed for two drawers; your job is to extend the design to three.**

---

## 2. Current state of every moving piece

### Composition engine (structured splices) — DONE, in review closeout
- **Spec:** `docs/superpowers/specs/2026-07-03-composition-engine-structured-splices-design.md` (amended 2026-07-04). Adds insert ops, `replace_substring_within`, deterministic render order, structured `patch_conflict:*` codes, insertion-evidence verification, `requiresPackages`/`conflictsWithPackages`, and sibling-tolerant postcondition rules.
- **Implementation plan:** `docs/superpowers/plans/2026-07-04-composition-engine-structured-splices.md` (12 TDD tasks).
- **Implemented in a worktree:** `/Users/MAC/.config/superpowers/worktrees/Claude-patch/composition-engine-structured-splices` (branch off `main`). Full suite green (408 passed, 1 skipped).
- **Reviewed:** `docs/superpowers/reviews/2026-07-04-structured-splices-implementation-review.md` — high-quality, plan-compliant. 4 required changes (R1 revert an out-of-scope package commit; R2 scope a postcondition heuristic per-module; R3 pin marker counts; R4 fail closed on duplicate package id) + cleanups. The implementer is applying those now.
- **Assume by the time you start:** the engine work is merged to `main` with R1–R4 fixed. If you need to confirm an engine capability, read the engine spec's "Operation model" section and `src/claude_monkey/module_patch.py` / `manifest_v2.py` / `builder_v15.py` on `main`.
- **Original problem statement** (byte-proven, good background): `docs/superpowers/specs/2026-07-03-composition-engine-additive-splice-handoff.md`.

### footer-drawers framework — DESIGNED FOR TWO, needs THREE
- **Spec you will edit:** `docs/superpowers/specs/2026-07-03-footer-drawers-framework-design.md`. It is fully written for **hidden-context + reminders**: registry contract, single synthetic `"drawers"` footer target, land-once/left-right/enter/close interaction, all shared seams expressed as engine-primitive ops (the `ji` cluster, selection flag, `Wo` key-routing wrapper, space binding, availability bar, overlay mounts, helpers/bootstrap, per-drawer registration). All 6 former open questions are resolved in its "Resolved decisions" section. **Read this whole file first — your task is to generalize it from 2 drawers to 3.**

### The three drawer packages (all on `main` as untracked/committed working files)
- `packages/hidden-context-drawer/` — 2.1.199. Footer seams + `Jur` projection content seam.
- `packages/reminders-manager/` — 2.1.199. Footer seams + `ug`/`Hze` deny content seams. Conflicts with `packages/upstream-attachment-suppression/` (both own the deny seams; UAS is the static all-off alternative, stays maintained).
- `packages/thinking-text-drawer/` — 2.1.201. Footer seams + a large set of stream-content collector seams (see §3). `patch.json` is schema-1 V3-envelope shape (note: `"schemaVersion": 1, "kind": "patch"`, with `x-packageVersion`), unlike HC/reminders which are schema-2 `patch.json`. The framework refactor must keep whichever envelope each package uses working through the builder bridge (`_v3_manifest_as_v2_dict`).

---

## 3. Everything you need to know about the Thinking drawer (the new third drawer)

Read `packages/thinking-text-drawer/patch.json` and `README.md` in full. Key facts, already extracted:

### Its seams split into two classes — same pattern as the other drawers
**Content seams (STAY with the drawer — orthogonal to the footer, like HC's projection / reminders' deny):** 9 ops that capture thinking text from the live stream and assistant content:
- `thinking-helpers-before-ypr` (helper definitions + action wrapper — anchor `function Ypr(e){`)
- `thinking-message-start-turn-collector`, `thinking-message-stop-turn-collector` (turn identity)
- `thinking-live-delta-collector` (raw `thinking_delta`), `thinking-signature-collector`, `thinking-parent-structured-collector` (structured blocks), `thinking-system-token-estimate`, `thinking-cancel-salvage-collector` (interrupt salvage)

These publish to globals like `__CODEX_THINKING_TEXT_DRAWER_FRAME_V1__`, `__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__`, `__CODEX_THINKING_TEXT_DRAWER_TURN_V1__` and helpers `__codexTTDRecordLiveThinking` / `RecordStructuredThinking` / `RecordThinkingSignature` / `RecordThinkingEstimate` / `RecordRedactedThinking` / `RecordSalvagedThinking`. None of this is footer-shared; it all stays in the thinking package's registration/content ops.

**Footer/overlay seams (the framework RE-OWNS these — this is the whole point):**
- `thinking-footer-open-state` (React open-state hook)
- `thinking-footer-target` (adds `"thinking"` to the footer-target `useMemo` array — at 2.1.201 the array var is `ss`, deps `[Ui,po,Fn,_e,Tr,Ne]`; the 2.1.199 equivalent is `ji`)
- `thinking-footer-selection-flag` (adds `Lm==="thinking"` beside the six stock flags — at 2.1.201 selection var is `Lm`; 2.1.199 equiv is `Du`)
- `thinking-footer-action-wrap-open` / `-close` (wraps the footer keybinding action map — at 2.1.201 the register fn is `Go` and actions are `footer:up/down/next/previous/openSelected`; 2.1.199 equiv is `Wo`)
- `thinking-selected-overlay-globals` + `thinking-bottom-overlay-renderer` (see overlay note below)
- `thinking-footer-status-bar` (a **2,559-byte** whole-statement restatement — the textbook Finding-2 forced-restatement the structured-splice engine exists to kill; under the framework this becomes a small insert)

### Three things the current (two-drawer) framework model does NOT yet handle — you must generalize for these:
1. **Always-available drawers.** Thinking's footer target is present **whenever the interactive footer is active, even with zero captured entries** (opens to `No thinking captured yet`). Contrast HC, which is available only when its frame is visible, and reminders, which is effectively always-on. The registry's `available()` contract already supports this (thinking's `available()` just returns true when the footer is interactive), but the spec's prose and examples assume conditional availability — broaden them.
2. **Unread / flash state.** Captured thinking entries drive an unread/flash indicator that is independent of whether the drawer can be opened. The registry entry contract (currently `id/order/available/label/onKey/renderPanel`) has no notion of per-drawer transient badge/flash state. Decide whether to (a) add an optional `badge()`/`flash()` to the entry contract that the framework's bar renderer consumes, or (b) leave flash entirely inside the drawer's own `label()`/panel and have the framework treat the label as opaque. Recommend (a) as a thin optional field so the framework's single bar renderer can show consistent hint + badge; but keep it OPTIONAL so HC/reminders don't need it. Note this as a small addition to the "Entry contract" section with rationale.
3. **A different overlay mechanism.** HC + reminders mount panels at the two `V8o` caller sites (`children:[…]` arrays). The thinking drawer instead renders a **bottom-overlay sibling** — it replaces a stock function (`Ilc`/`clc` at 2.1.201) that returns `position:"absolute", bottom:"100%"` full-width content above the prompt. So "the overlay mount" is not one uniform seam across all three drawers. Your spec must decide the framework's overlay ownership model:
   - Option A (recommended): the framework owns **one** overlay mount strategy and all drawers render through `renderPanel()` into it. Pick the mount that works for all three (the bottom-overlay-sibling approach is the more general "full-width above prompt" surface; the `V8o` panel sites are an alternative). The thinking drawer's richer bottom-overlay is likely the model to standardize on. Verify at implementation which mount the target version exposes.
   - Option B: the framework supports a small enum of overlay styles per entry. More flexible, more surface area. Probably YAGNI for three drawers — call it out and recommend A.

### Ordering
The framework uses numeric `order` (doubling as `insertOrder` band). Current: hiddenContext=100, reminders=200. Add **thinking** — pick its slot per the user's desired left-to-right footer order. The prior UX decision was "Hidden Context before Reminders." Ask or infer where Thinking sits; a sensible default is thinking after reminders (300) unless the user wants thinking adjacent to the prompt. Flag as a small open question if unsure (it's a one-line change, low cost to defer).

---

## 4. Your task, concretely

Produce an updated `docs/superpowers/specs/2026-07-03-footer-drawers-framework-design.md` (edit in place; keep its structure) that:

1. **Adds thinking-text-drawer as a third registrant** everywhere the spec enumerates drawers: package topology, registry examples, seam plan, composition matrix, migration path, testing, resolved decisions.
2. **Generalizes the registry entry contract** for always-available drawers and (optionally) unread/flash badge state — §3 items 1 and 2.
3. **Resolves the overlay ownership model** for the fact that thinking uses a bottom-overlay sibling while HC/reminders use `V8o` panel sites — §3 item 3. Make a clear recommendation, don't leave it open.
4. **States the target-version decision** (§0) at the top, with the user's answer once you have it, and re-frames all cited anchors as version-scoped examples to be re-verified.
5. **Documents that thinking's content seams stay in its package** (the 9 stream collectors) and only its footer/overlay seams move to the framework — mirror the HC-projection / reminders-deny "retained content seams" treatment.
6. **Updates the relationship metadata**: all three drawers `requiresPackages: ["footer-drawers"]`; reminders keeps `conflictsWithPackages: ["upstream-attachment-suppression"]`; note whether thinking has any conflicts (it currently conflicts with any direct footer-drawer package on the shared seams — that conflict *dissolves* once it's a thin registrant, which is exactly the win).
7. **Updates the migration path** to a four-step "leaves a working system at each step" sequence: build framework alone (behavior-neutral) → refactor HC → refactor reminders → refactor thinking → release all together. Note the flag-day (old drawer versions + framework = `patch_conflict`, fail-closed, upgrade all together).
8. **Updates the testing matrix**: framework+all-three, framework+each pair, framework+each alone, framework alone (empty toolbar), each drawer without framework (expect `required_package_missing`), reminders+UAS (expect `package_conflict`), plus the manual-smoke checklist covering all three drawers' open/scroll/close and thinking's always-available + empty-state + unread/flash.

Keep the doc's honest-risk section: correlated failure (all three now depend on framework anchors — one broken framework seam takes down all three toolbars, but not the content seams / deny / projection / thinking collectors), mitigated because framework seams become small inserts not restatements.

---

## 5. Ground rules (how this project wants specs written)

- **Read the actual package files before writing** — `patch.json` for each drawer is the source of truth for seam locations and anchors, not memory. Cite op ids and anchor strings from the files.
- **Anchors are version-specific.** 2.1.201 identifiers differ from 2.1.199 (`ss`≠`ji`, `Lm`≠`Du`, `Go`≠`Wo`, `wo.useState`≠`Ro.useState`). Never claim an anchor without noting its version. Every anchor gets re-verified (`count==1` in the target module) at implementation time — say so.
- **Encoding constraint** (matters for any payload examples): literal multibyte UTF-8 in payloads gets corrupted to `â…` by the latin1 repack path. Use pure-ASCII escapes: `→` for →, `─` for ─, `❯` for ❯, `\xB7` for ·.
- **React hooks safety:** `renderPanel` must return an element *descriptor* (`() => zd.jsx(Panel,{})`), never call a hook-bearing function directly in a varying-length `.map()`.
- **The framework is gated on the engine.** It cannot be implemented until structured-splice engine Phases 1–2 are merged (assume done). The spec should state that prerequisite.
- **Do not implement anything.** No code, no package edits. Spec only. A separate agent writes the implementation plan from your spec, and another implements it.
- The user uses voice narration; parse intent loosely, prefer their exact terms (drawer, footer, thinking drawer, shared script/framework).

---

## 6. File map (everything referenced)

**Edit:**
- `docs/superpowers/specs/2026-07-03-footer-drawers-framework-design.md` — the spec to extend to three drawers.

**Read for context (in priority order):**
- `docs/superpowers/specs/2026-07-03-footer-drawers-framework-design.md` — current two-drawer design (read fully first).
- `packages/thinking-text-drawer/patch.json` + `README.md` — the new drawer's seams (§3).
- `packages/hidden-context-drawer/patch.json`, `packages/reminders-manager/patch.json` — the two existing drawers' seams.
- `docs/superpowers/specs/2026-07-03-composition-engine-structured-splices-design.md` — what engine primitives you can rely on.
- `docs/superpowers/reviews/2026-07-04-structured-splices-implementation-review.md` — engine review; note R2 (postcondition scoping) and R3/R4 as engine behaviors your spec's postconditions/relationships depend on.
- `docs/superpowers/plans/2026-07-04-composition-engine-structured-splices.md` — if you need exact op-field names (`anchor`, `insertOrder`, `subExact`, `contextSha256`, `seamHint`, `requiresPackages`, conflict codes).
- `docs/superpowers/specs/2026-07-03-composition-engine-additive-splice-handoff.md` — byte-proven background on why the engine change was needed.

**Do NOT touch:** any `src/` code, any `packages/*` files, the engine worktree. Spec doc only.

---

## 7. First moves when you pick this up

1. Ask the user the §0 target-version question (recommend 2.1.201) — you need it before the final anchor-citation pass, but you can draft everything structural first.
2. Read the current framework spec end-to-end.
3. Read the thinking-drawer `patch.json` + README, and skim the other two `patch.json`s to confirm the shared-seam list.
4. Decide the three generalizations (always-available, unread/flash badge, overlay model) with clear recommendations.
5. Rewrite the spec in place. Keep it implementation-ready — resolve open questions, don't accumulate them.
6. Optionally have a subagent adversarially review the updated spec as a valued co-collaborator (the user likes this — a Sonnet subagent, rich context, clear guidance), then fold in findings.
