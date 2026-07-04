# Composition Engine Structured Splices — Design

**Status:** Draft for user review.  
**Project:** ClaudeMonkey composition engine.  
**Source handoff:** `docs/superpowers/specs/2026-07-03-composition-engine-additive-splice-handoff.md`.  
**Target baseline:** Claude Code `2.1.199`, Bun standalone Mach-O, schema-v2 `bun_graph_repack` packages.  
**Decision:** build a refined Python splicing layer first; defer a named seam layer until this foundation is proven.

## Decision summary

ClaudeMonkey should stay with direct, byte-preserving module splicing in Python, but make the splicing model much more compositional.

We are **not** building a JavaScript AST transformer, whole-module re-printer, patch-owned-module system, trampoline loader, or appended-payload architecture. The current V1.5 graph-aware repacker remains the binary-container layer: it parses the Bun standalone module graph, rewrites changed existing module contents, updates Bun/Mach-O metadata, signs copied output, smokes it, and fails closed.

The next layer should make patch planning more graph-aware without adding a heavy JS tooling dependency. Here, graph-aware means:

- model patch operations as a deterministic operation graph;
- model shared byte locations as composable insertion/replacement points;
- model package relationships and conflicts explicitly where byte overlap alone is too blunt;
- preserve enough seam evidence that frequent Claude Code version updates are easier to retarget manually;
- render changed modules from original module bytes plus precise splices, not from regenerated source.

The immediate goal is to unblock clean composition of packages such as `hidden-context-drawer`, `reminders-manager`, and a future `footer-drawers` framework without repeating unrelated stock logic or relying on downstream reassignment tricks.

## Why this exists

The additive splice handoff verified a real limitation in the current engine:

- `manifest_v2.py` supports only `replace_exact` and `replace_between`.
- `module_patch.py` resolves every op against the original stock module and rejects overlapping byte ranges.
- `builder_v15.py` repeats that overlap check across all enabled packages.
- Two packages that both need to modify the same stock statement must either conflict or route around the statement with fragile downstream logic.

The concrete example is the footer target list in function `VOf`:

```js
ji=Ro.useMemo(()=>[Uo&&"tasks",ro&&"workflows",Jt&&"tmux",be&&"bagel",Hr&&"bridge",Oe&&"frame"].filter(Boolean),[Uo,ro,Jt,be,Hr,Oe])
```

Both the Hidden Context drawer and Reminders drawer want to append a target. Today one package replaces the whole statement and the other reconstructs `ji` downstream. That happens to work, but it encodes accidental package coupling and depends on a convenient later statement existing.

The current whole-span model also forces packages to restate orthogonal stock logic. Adding one footer flag can require copying the entire existing flag statement for tasks, workflows, tmux, bagel, bridge, and frame. A future Claude update to unrelated frame or tmux behavior can therefore break a drawer package.

## Use case and success criteria

Claude Code updates often. User patches should:

1. apply cleanly to a pinned binary when all evidence still matches;
2. compose with other user patches when their edits are intentionally compatible;
3. fail closed when a new binary invalidates a seam;
4. produce enough diagnostics that re-anchoring for the new binary is a minimal, local task;
5. avoid new heavyweight tooling that would make the patch manager harder to install, trust, or maintain.

Success for this design is not “patches automatically survive every upstream update.” Success is “when they do not survive, the tool explains which seam failed and what local evidence changed.”

## Non-goals

This design explicitly excludes:

- patch-owned modules added to the Bun graph;
- JS parser dependencies such as Babel, SWC, Acorn, or tree-sitter in the normal build path;
- whole-module parse-transform-print workflows;
- whole-module minification or reformatting;
- runtime trampolines, appended payload loaders, or eval/import side channels;
- fuzzy semantic migration that silently accepts approximate matches;
- changing the existing copied-output-only and fail-closed safety stance;
- making the future named seam layer part of the first implementation.

## Important terminology

### Whole-module reprint

A whole-module reprint means parsing the entire `cli.js` module, transforming it, and generating the full module text again. This design rejects that. ClaudeMonkey may still write a whole changed module back into the Bun payload because the container rewrite works at module granularity, but that changed module must be produced as:

```text
original module bytes + precise splice edits
```

not:

```text
regenerated entire module text
```

### Graph-aware concepts

“Graph-aware” in this design does not mean “AST graph.” It means the patcher carries the discipline learned from Bun graph repack into the splice layer:

- nodes: package operations;
- edges: ordering, dependencies, conflicts, and shared insertion points;
- evidence: source identity, module identity, anchor identity, old span hashes, local context hashes;
- deterministic rendering: one merged module pass from original bytes;
- diagnostics: failures point to the graph node or edge that could not be satisfied.

## Architecture overview

The build pipeline should remain layered:

1. **Package selection** — select enabled packages and matching targets by source identity.
2. **Module extraction** — parse the Bun graph and expose existing module contents by path.
3. **Structured splice planning** — resolve package operations into byte-level splice plans against original module bytes.
4. **Operation graph validation** — validate overlaps, shared insertion groups, ordering, dependencies, and conflicts.
5. **Module rendering** — render each changed module once from original bytes plus sorted splice plans.
6. **Bun graph repack** — reuse existing `repack_changed_modules` behavior.
7. **Signing, post-sign inspection, smoke, reports, activation gates** — preserve current V1.5 behavior.

Only step 3 and step 4 are new in spirit. The design should not contaminate `bun_graph.py` or `macho.py` with package-composition concerns.

## Operation model

The current operation shape should be extended, not replaced. Existing schema-v2 packages using `replace_exact` and `replace_between` should continue to work.

### Existing operations

`replace_exact` and `replace_between` remain the full-span operations. They claim a non-zero range and conflict with any other operation whose claimed range overlaps.

They are still appropriate when a package intentionally owns an entire helper function, wrapper expression, or render branch.

### New zero-width insertion operations

Add insertion operations that claim a zero-width point, not a whole span:

- `insert_before`
- `insert_after`

Both locate a unique anchor string in the original module. The insertion point is either the anchor start or anchor end. Multiple packages may insert at the same point if their order is deterministic and non-conflicting.

Suggested manifest fields:

```json
{
  "opId": "append-hidden-context-target",
  "label": "Append hiddenContext to footer target array",
  "type": "insert_after",
  "anchor": "Oe&&\"frame\"",
  "expectedAnchorCount": 1,
  "insertOrder": 100,
  "replacement": { "inline": ",__codexHiddenContextFrame?.visible&&\"hiddenContext\"" },
  "knownBehaviorChange": "Adds hiddenContext as a footer target when the current render frame is visible."
}
```

Rules:

- `anchor` must resolve exactly `expectedAnchorCount` times; default should be 1.
- `moduleStart == moduleEnd` in the planned operation.
- `oldLen == 0`, `oldSha256` is the SHA-256 of empty bytes or omitted by explicit report convention.
- `insertOrder` is required for shared insertion points.
- The sort key for a shared insertion group is `(moduleStart, insertOrder, packageId, opId)`, but duplicate `insertOrder` at the same point should fail by default unless an explicit tie policy is added later.
- A zero-width insertion at a non-zero replacement boundary is allowed only when the insertion point is outside the replacement's claimed range. Inserting inside another operation's claimed range should fail unless the owner operation explicitly exposes a future named seam; named seams are out of phase-1 scope.

### New subspan replacement operation

Add a targeted replacement operation for the common case where a package needs to modify one clause inside a larger stock statement:

- `replace_substring_within`

It locates an outer range for context, then claims and replaces only a unique inner substring inside that range.

Suggested manifest fields:

```json
{
  "opId": "add-hidden-context-selection-flag",
  "label": "Add hiddenContext footer selection flag",
  "type": "replace_substring_within",
  "startMarker": "let qb=Du===\"tasks\"",
  "endMarker": ";function Sf",
  "expectedStartMarkerCount": 1,
  "expectedEndMarkerCount": 1,
  "subExact": "Ap=Du===\"frame\"",
  "expectedSubExactCount": 1,
  "oldRangeSha256": "<sha of claimed subspan>",
  "oldRangeLength": 15,
  "replacement": { "inline": "Ap=Du===\"frame\",hC=Du===\"hiddenContext\"" }
}
```

Rules:

- The outer range gives context but is not claimed.
- Only the inner `subExact` byte range is claimed.
- `oldRangeSha256` and `oldRangeLength` apply to the claimed subspan, not the outer context.
- The outer context may optionally have its own context hash in a new field such as `contextSha256`, but a context hash mismatch should produce a precise diagnostic rather than being confused with claimed-range mismatch.
- If the inner substring is not unique inside the outer range, fail closed.

This operation handles “change one clause without owning siblings” while still keeping the implementation as Python byte searching.

### Optional structured helper operations

Phase 1 may include only the primitives above. If helper operations are added, they must compile down to explicit byte splices and remain small.

Potential helpers:

- `append_to_array_after_item`
- `append_var_declarator_after`
- `insert_case_before`

These are acceptable only if they are implemented as disciplined string/byte scanners for narrow minified patterns. They must not become an ad hoc JavaScript parser.

Recommendation: do **not** implement helper operations in the first engine change. Use primitives first, then decide from real package migrations whether helpers earn their keep.

## Operation graph validation

The planner should produce a list of planned operations with explicit kind:

- `replacement` — non-zero claimed range;
- `insertion` — zero-width insertion point;
- `subspan_replacement` — non-zero claimed subspan inside unclaimed context.

Validation rules:

1. Non-zero claimed ranges may not overlap.
2. Zero-width insertions at the same point may coexist if their `insertOrder` values are valid and unique.
3. A zero-width insertion at the boundary of a replacement is allowed when it is before the replacement start or after the replacement end.
4. A zero-width insertion inside a non-zero claimed range fails.
5. Non-zero subspan replacements behave like any other claimed range for overlap purposes.
6. All operations resolve against original module bytes, never sequentially patched bytes.
7. Rendering remains a single sorted pass over original bytes.

The conflict errors should name the operation graph problem, not just say `overlap`:

- `patch_conflict:range_overlap:<pkgA>:<opA>:<pkgB>:<opB>`
- `patch_conflict:insert_order_duplicate:<modulePath>:<offset>:<order>`
- `patch_conflict:insert_inside_claimed_range:<insertPkg>:<insertOp>:<ownerPkg>:<ownerOp>`
- `patch_conflict:required_package_missing:<pkg>:<requiredPkg>`
- `patch_conflict:package_conflict:<pkgA>:<pkgB>`

The CLI can still map these to friendly messages, but the report should preserve the precise code.

## Package relationship metadata

Byte conflicts are not enough. Some packages are alternatives even if they do not currently overlap; other packages require a framework or shared owner.

Add optional package-level metadata:

```json
{
  "requiresPackages": ["footer-drawers"],
  "conflictsWithPackages": ["upstream-attachment-suppression"],
  "provides": ["footer-drawer:hiddenContext"],
  "consumes": ["footer-drawers:v1"]
}
```

Phase-1 minimum:

- `requiresPackages`
- `conflictsWithPackages`

`provides` and `consumes` are useful for future named seams but can stay informational at first.

Rules:

- Missing required package fails before operation planning.
- Explicit package conflict fails before operation planning.
- Existing byte-overlap conflict remains the final safety net.
- Package relationship metadata must not override byte safety.

This lets the future `footer-drawers` framework express that thin drawer packages need the framework, while static alternatives such as `upstream-attachment-suppression` and runtime managers can declare incompatibility directly.

## Seam evidence without named seams

A full named seam layer is deferred, but this design should produce the evidence that makes it possible later.

Each operation may include optional seam evidence fields:

```json
{
  "seamHint": "footer.targets.afterFrame",
  "contextBefore": "Hr&&\"bridge\",",
  "contextAfter": "].filter(Boolean),[Uo,ro,Jt,be,Hr,Oe])",
  "contextSha256": "<sha of small surrounding context>"
}
```

In phase 1, `seamHint` is informational and report-facing. It does not route to a central registry. The planner uses explicit operation fields (`anchor`, `subExact`, `startMarker`, `endMarker`) as the source of truth.

This creates a path to a later named seam registry without needing to design that registry now.

## Retarget diagnostics for frequent Claude updates

When a source or module identity changes, package validation should offer better local diagnostics where safe. This is not auto-migration; it is evidence for the maintainer.

Suggested `validate-package --json` behavior:

- If source identity mismatches, report current source SHA/version/size as today.
- If module SHA mismatches but the module path still exists, optionally attempt read-only operation diagnostics against the current module.
- For each operation, report:
  - anchor found/missing;
  - anchor count;
  - claimed subspan found/missing;
  - outer context found/missing;
  - old claimed-range hash matched/mismatched;
  - candidate offset if unambiguous;
  - no candidate if ambiguous.

Example diagnostic:

```json
{
  "opId": "append-hidden-context-target",
  "status": "candidate_found_context_hash_changed",
  "anchorCount": 1,
  "candidateModuleStart": 15099551,
  "contextSha256Matched": false,
  "action": "manual_review_required"
}
```

This supports the real workflow: Claude Code updates often; patch maintainers need to know which small seams changed.

## Build reports

`operationsApplied` should be extended so future readers can inspect composition evidence:

```json
{
  "packageId": "hidden-context-drawer",
  "opId": "append-hidden-context-target",
  "type": "insert_after",
  "modulePath": "/$bunfs/root/src/entrypoints/cli.js",
  "moduleStart": 15099551,
  "moduleEnd": 15099551,
  "oldLen": 0,
  "newLen": 42,
  "delta": 42,
  "insertOrder": 100,
  "anchor": "Oe&&\"frame\"",
  "seamHint": "footer.targets.afterFrame"
}
```

For `replace_substring_within`, reports should distinguish context range from claimed range:

```json
{
  "type": "replace_substring_within",
  "moduleStart": 15100267,
  "moduleEnd": 15100282,
  "contextStart": 15100179,
  "contextEnd": 15100294,
  "oldLen": 15,
  "newLen": 41
}
```

Reports should preserve enough detail to answer: did this package own a stock range, insert beside a stock range, or change one subspan inside a context?

## Footer drawer implications

With structured splices, a future footer framework can avoid the worst current compromises:

- Drawer packages can append to a shared footer target insertion point instead of replacing the whole `ji` statement or reconstructing it downstream.
- A package can add one selection flag without restating all stock sibling flags.
- A framework package can own genuinely shared behavior while thin drawer packages contribute small registration and content seams.
- If a drawer depends on the framework, that dependency can be explicit instead of implied by marker presence.

This does not solve the data-flow issue from the footer framework review: availability computed from function-local render values cannot be fixed by a clever splice if a package publishes the needed value too late. That remains a framework/data-flow design issue. The composition engine should not absorb it.

## Compatibility and migration

Existing schema-v2 packages should continue to load. The schema version can remain `2` if the parser treats new fields and operation types as additive, but the build report should expose enough information for compatibility.

Possible compatibility stance:

- Keep `schemaVersion: 2`.
- Add supported operation types in `manifest_v2.py`.
- Reject unknown operation types as today.
- Add package relationship fields as optional.
- Existing manifests need no change.

If the team wants a cleaner marker, use `schemaVersion: 2` plus `requiredEngineVersion` or `minimumEngineFeatures`, but do not create a V3 manifest unless a real incompatibility appears.

## Testing plan

### Unit tests

Add tests for:

- `insert_after` resolves a zero-width point after a unique anchor.
- `insert_before` resolves a zero-width point before a unique anchor.
- Multiple insertions at the same point render deterministically by `insertOrder`.
- Duplicate `insertOrder` at the same point fails closed.
- Insertion inside a claimed replacement range fails.
- Insertion adjacent to a claimed replacement boundary behaves as specified.
- `replace_substring_within` claims only the subspan, not the whole context.
- Non-unique subspan inside context fails.
- Old-range SHA and length apply to the claimed subspan.
- Existing `replace_exact` and `replace_between` behavior is unchanged.

### Builder tests

Add tests for:

- cross-package shared insertion point succeeds;
- cross-package non-zero overlap still fails;
- explicit `requiresPackages` failure;
- explicit `conflictsWithPackages` failure;
- build report serializes operation type, insertion order, seam hint, and context range.

### Package/reference tests

Add a focused scratch or fixture package pair that reproduces the footer target collision without using real drawer packages:

- package A inserts one array entry at the same footer-like anchor;
- package B inserts another entry at the same anchor with a higher order;
- build proves both land in deterministic order.

Then migrate one real package seam, preferably the smallest current workaround, only after the engine tests pass.

### Local real-binary smoke

Real Claude Code tests remain opt-in and copied-output-only. Required checks stay the same:

- source identity;
- module identity;
- operation resolution;
- Bun graph validation;
- Mach-O alignment;
- signing;
- post-sign inspection;
- `--version` and `--help` Claude Code smoke;
- manual smoke for UI-affecting patches.

## Phased delivery

### Phase 1 — structured splice primitives

Implement:

- `insert_before`;
- `insert_after`;
- `replace_substring_within`;
- deterministic insertion ordering;
- richer operation conflict errors;
- build-report extensions;
- tests.

No package migrations required in this phase except small fixture packages.

### Phase 2 — package relationship metadata

Implement:

- `requiresPackages`;
- `conflictsWithPackages`;
- structured pre-planning validation;
- report and CLI error messages.

Use this to model known alternatives and future framework dependencies.

### Phase 3 — migrate real seams

Migrate selected current packages away from fragile workarounds:

1. Replace downstream `ji` reassignment in `reminders-manager` with ordered insertion if the data-flow design supports it.
2. Replace Hidden Context selection flag whole-statement restatement with `replace_substring_within`.
3. Revisit footer framework design only after these migrations prove the engine primitives.

### Phase 4 — named seam layer design

Only after phases 1-3, design the named seam layer. It should build on observed repeated patterns and operation evidence, not on an imagined registry.

The named seam layer can map stable names such as `footer.targets.afterFrame` to locator rules per Claude Code version, but it should not be part of the first implementation.

## Open questions for implementation planning

1. Should duplicate `insertOrder` at the same point always fail, or should package ID be an accepted tie-breaker? Recommendation: fail.
2. Should `oldRangeSha256` be allowed to be omitted for zero-width insertions? Recommendation: yes, because the claimed range is empty; use anchor/context evidence instead.
3. Should `contextSha256` be warning-only or hard-fail? Recommendation: hard-fail during build, diagnostic-only during retarget analysis.
4. Should package relationship metadata live top-level or per target? Recommendation: top-level for package relationships; target-level only if source-version-specific relationships become necessary.
5. Should retarget diagnostics run automatically on identity mismatch? Recommendation: only in `validate-package`, not normal `build`, to keep build failure simple and fail-closed.

## Final stance

The right next move is not a full code-graph patcher. The right next move is a better Python splice algebra with graph-aware discipline:

- explicit operation nodes;
- explicit shared insertion points;
- explicit package edges;
- precise claimed ranges;
- deterministic rendering;
- evidence-rich diagnostics;
- no whole-module reprint;
- no new JS tooling dependency.

This foundation should make the future named seam layer possible without prematurely building a stale abstraction. It improves the current package setup now, while preserving the V1.5 safety posture that made graph-aware repack trustworthy.
