# Manifest schema-v2 operation reference

Operation types accepted in `patch.json` `targets[].modules[].operations[]`.
All ops resolve against ORIGINAL stock module bytes; rendering is one pass
sorted by `(moduleStart, moduleEnd, insertOrder, packageId, opId)`.

## replace_exact
Claims the byte range of a unique `exact` substring; replaces it whole.
Fields: `exact` (must occur exactly once), `requireWithinRange`,
`oldRangeSha256`, `oldRangeLength`, `replacement`.

## replace_between
Claims start-of-`startMarker` → start-of-`endMarker` (endMarker excluded).
Fields: `startMarker`, `endMarker`, `expectedStartMarkerCount`,
`expectedEndMarkerCount`, plus the evidence fields above.

## insert_before / insert_after
Claims a ZERO-WIDTH point at the start (insert_before) or end (insert_after)
of a unique `anchor`. Multiple packages may target the same point when each
supplies a distinct `insertOrder`; the merged bytes render in ascending order.
- `anchor` (required, must resolve exactly once in scope)
- `insertOrder` (required when the point is shared; omit for sole inserts)
- optional `startMarker`+`endMarker` context: anchor uniqueness is evaluated
  inside the context span (start of startMarker → END of endMarker)
- `seamHint` (informational, surfaces in build reports)
- old-range evidence fields are REJECTED (the claimed range is empty)
- anchor and context-marker bytes must be disjoint from every claimed
  replacement range in the build (fail-closed)
- POSTCONDITIONS: assert your own payload marker only. Never assert
  anchor+payload adjacency — a sibling package's insertion at the same
  point makes it order-dependent, and the builder fails such postconditions
  as `postcondition_composition_sensitive`.

## replace_substring_within
Resolves an outer context via `startMarker`/`endMarker`, then claims and
replaces only the unique `subExact` inside it. Use for editing one owned
clause without restating siblings. For additive clauses that other packages
may also extend, prefer insert_before/insert_after.
- `subExact` (must occur exactly once inside the context)
- `oldRangeSha256`/`oldRangeLength` apply to the claimed subspan
- `contextSha256` (optional): hard-fail hash of the full context span

## Package relationships (top level, both manifest surfaces)
- `requiresPackages`: build fails with
  `patch_conflict:required_package_missing:<pkg>:<required>` unless every
  named package is enabled in the same build.
- `conflictsWithPackages`: build fails with
  `patch_conflict:package_conflict:<pkgA>:<pkgB>` when both are enabled.
Relationship checks run before byte planning; byte-overlap checking remains
the final safety net and is never overridden by metadata.

## Conflict codes
- `patch_conflict:range_overlap:<pkgA>:<opA>:<pkgB>:<opB>`
- `patch_conflict:insert_inside_claimed_range:<pkgA>:<opA>:<pkgB>:<opB>`
- `patch_conflict:insert_order_required:<modulePath>:<offset>`
- `patch_conflict:insert_order_duplicate:<modulePath>:<offset>:<order>`
- `patch_conflict:insert_anchor_inside_claimed_range:<insertPkg>:<insertOp>:<ownerPkg>:<ownerOp>`
- `patch_conflict:required_package_missing:<pkg>:<required>`
- `patch_conflict:package_conflict:<pkgA>:<pkgB>`
