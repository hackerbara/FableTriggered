# ClaudeMonkey V1.5 Bun graph-aware repack design

Date: 2026-07-02
Status: design direction approved; detailed spec under review; implementation not started
Project: ClaudeMonkey
Scope: V1.5 CLI/core patch-application engine replacement

## 1. Decision summary

ClaudeMonkey V1.5 removes slot-style binary patching from the active patch engine.

The V1 same-size/smaller byte replacement model was useful as spike infrastructure, but it is not the right product abstraction. It patches arbitrary executable byte ranges, depends on preserved offsets as a substitute for understanding the container, and encourages package authors to think in byte budgets rather than source/module identity.

V1.5's patch engine is therefore a clean break:

- No slot strategy.
- No same-size padding path.
- No `allowGrowth` permission flag.
- No `auto` mode that chooses between slot and repack.
- No V1 whole-binary byte-range package compatibility in the V1.5 builder.
- New packages target Bun standalone modules by path and source identity.
- Every V1.5 build parses the Bun standalone graph, applies module-coordinate replacements, rewrites Bun graph metadata, rewrites Mach-O metadata, signs the copied output, smokes it, and writes a report.

The only fallback is failure. If ClaudeMonkey cannot prove the binary shape, module identity, target range, graph rewrite, signing result, and smoke result, it does not activate a build.

## 2. Evidence basis

### 2.1 V1 baseline

V1 merged to `main` as `e89ca31 Merge branch 'codex/claude-monkey-v1-cli-core'`. Its core patch engine currently resolves operations against whole-binary bytes and rejects replacements larger than the old range.

That gave ClaudeMonkey a safe CLI spine: manifest loading, payload hashes, source identity checks, patch stacking, copied output, signing, smoke, activation, config, shim support, and build reports.

V1.5 should reuse that application spine where it is still true, but replace the byte-slot patch engine.

### 2.2 Repack spike result

The successful spike proved direct code-site growth is viable for local Claude Code 2.1.198 on macOS arm64 when both metadata layers are updated:

1. Bun standalone module graph metadata.
2. Mach-O segment/linkedit/code-signature metadata.

Successful artifact:

```text
/Users/MAC/Documents/Claude-patch/.development/repack-spike-20260702-codex/artifacts/claude-2.1.198.graph-repack-floating-blue-box-v4-grow16384
```

Successful test case:

- Target module: `/$bunfs/root/src/entrypoints/cli.js`.
- Real patch site: `Ijo` floating renderer range.
- Old renderer range: `635` bytes.
- Normal v4 replacement: `631` bytes.
- Repacked replacement: `17019` bytes.
- Net growth: `16384` bytes.
- Bun graph validator: `validation_errors []`.
- Static v4 verifier: `PASS`.
- `codesign --verify --strict`: `PASS`.
- `--version`: `2.1.198 (Claude Code)`.
- `--help`: Claude Code help, exit 0.

The failed path is equally important: Mach-O/linkedit-only direct growth signed but launched as the Bun CLI because Bun's standalone module graph retained stale offsets. This proves the V1.5 mechanism must be graph-aware, not merely Mach-O-aware.

Visual UI smoke was not completed for the final artifact, so UI-affecting patches still need a manual/visual smoke gate in reports.

### 2.3 Public research sources

The public sources are useful corroboration and comparison material, not vendored dependencies.

- [TheCjw `extract_bun.js` gist](https://gist.github.com/TheCjw/2665020a559c1e980fa10f2a5c2aa621): strongest current public corroboration for Bun standalone payload parsing, trailer validation, and 52-byte module records. No explicit reusable license was found in the checked gist evidence on 2026-07-02. It is extractor-only, not a repacker.
- [sorrycc `unbundle-claude-code.ts` gist](https://gist.github.com/sorrycc/27944a584ad9c22e5ffc0c90fa33f007): useful Claude Code download/unbundle workflow reference. No explicit reusable license was found in the checked gist evidence on 2026-07-02. Some parser assumptions conflict with local 2.1.198 evidence, especially hardcoded module-table/header and content `+8` assumptions.
- `lafkpages/bun-decompile`: actual repo found by research, but not linked from the gists, not clearly licensed from visible evidence checked on 2026-07-02, and extraction/decompile-oriented rather than repack-oriented.
- `@shepherdjerred/bun-decompile`: actual packaged project with GPL-3.0 license observed on 2026-07-02 and historical Bun decompile work, but its module-entry size assumptions conflict with the local 2.1.198 graph evidence. It should not be vendored into ClaudeMonkey.

Recommendation: build a clean-room production core informed by local spike evidence and public format corroboration. Do not copy unlicensed gist code. Do not vendor GPL code into ClaudeMonkey's core. Consider publishing or upstreaming evidence only after ClaudeMonkey has its own validator/repacker and fixtures.

## 3. Product stance

ClaudeMonkey is source-first local customization for Claude Code. In V1.5, "source-first" means patch authors work against named Bun standalone modules and module-local source ranges, not absolute executable offsets.

The patch author should describe:

- which Claude source binary shape is expected;
- which Bun module is targeted;
- which module bytes identify the source;
- which module-local range should be replaced;
- what postconditions prove the patch landed;
- whether the patch affects UI and therefore needs manual/visual smoke.

The patch author should not describe:

- absolute Mach-O offsets;
- code-signature offsets;
- `__LINKEDIT` shift rules;
- Bun trailer positions;
- module table record offsets;
- padding bytes;
- same-size byte budgets.

Those are ClaudeMonkey implementation details.

## 4. Non-goals

V1.5 does not include:

- A slot-mode builder.
- Same-size/smaller byte replacement as an application path.
- Padding semantics.
- Arbitrary whole-binary patch operations.
- Live mutation of the official Claude binary.
- Runtime trampolines or appended-payload loaders.
- Remote patch registry behavior.
- A GUI rewrite.
- Support for non-Bun Claude Code package formats beyond fail-closed inspection.
- Vendoring public gist/project code without explicit license and technical fit.

## 5. Patch package format

V1.5 introduces a new package schema for module-coordinate patches. Use `schemaVersion: 2` to make the break explicit.

Example package shape:

```json
{
  "schemaVersion": 2,
  "id": "floating-renderer-overlay",
  "name": "Floating renderer overlay",
  "description": "Adds a visible renderer overlay in Claude Code history rendering.",
  "packageVersion": "0.1.0",
  "targets": [
    {
      "sourceIdentity": {
        "claudeVersion": "2.1.198",
        "versionOutput": "2.1.198 (Claude Code)",
        "sha256": "<official-source-sha256>",
        "sizeBytes": 229328464,
        "platform": "darwin",
        "arch": "arm64"
      },
      "requiredEngine": "bun_graph_repack",
      "requiredBinaryFormat": "bun_standalone_macho64",
      "modules": [
        {
          "path": "/$bunfs/root/src/entrypoints/cli.js",
          "contentSha256": "<original-module-content-sha256>",
          "contentLength": 18439743,
          "operations": [
            {
              "opId": "renderer-overlay",
              "label": "Patch Ijo renderer overlay",
              "type": "replace_between",
              "startMarker": "let pe;if(t[47]!==T",
              "endMarker": "return Ae}",
              "expectedStartMarkerCount": 1,
              "expectedEndMarkerCount": 1,
              "requireWithinRange": ["sXm", "bjo"],
              "oldRangeSha256": "<old-range-sha256>",
              "oldRangeLength": 635,
              "replacement": {
                "path": "payloads/renderer-overlay.js",
                "sha256": "<replacement-sha256>",
                "encoding": "utf-8"
              },
              "knownBehaviorChange": "Adds a renderer overlay; requires visual smoke."
            }
          ]
        }
      ],
      "preconditions": [],
      "postconditions": [
        {
          "type": "module_must_contain",
          "modulePath": "/$bunfs/root/src/entrypoints/cli.js",
          "value": "Patch overlay"
        }
      ],
      "manualSmoke": {
        "required": true,
        "reason": "UI-affecting renderer patch"
      }
    }
  ]
}
```

### 5.1 Schema rules

Required target identity:

- `sourceIdentity.claudeVersion`
- `sourceIdentity.versionOutput`
- `sourceIdentity.sha256`
- `sourceIdentity.sizeBytes`
- `sourceIdentity.platform`
- `sourceIdentity.arch`

Required engine constraints:

- `requiredEngine`: initially `bun_graph_repack`.
- `requiredBinaryFormat`: initially `bun_standalone_macho64`.

Packages identify source binaries and Bun modules. They do not encode Bun container mechanics such as trailer bytes, module record sizes, section names, or pointer-table layout. The engine owns binary-shape validation and reports the observed shape through `inspect-binary --json` and `build-report.json`.

All concrete numeric examples in this document are fixture-derived and must match the named fixture. If a value is illustrative, it must be a placeholder, not a plausible-looking number.

Required module identity:

- `path` must match exactly one Bun graph module path.
- `contentSha256` must match the extracted module content bytes before patching.
- `contentLength` must match the extracted module content length before patching.

Required operation identity:

- `opId`
- `label`
- `type`
- range markers or exact bytes, depending on operation type;
- `replacement` as inline or SHA-pinned external payload;
- optional but strongly recommended `oldRangeSha256` and `oldRangeLength`.

There is no growth flag. A module replacement may be shorter, same length, or longer. Repacking is the only V1.5 application mechanism.

### 5.2 Operation and assertion vocabulary

Initial V1.5 mutating operation types:

- `replace_between`: module-local range `[startMarker start, endMarker start)` using the first matching `endMarker` after the unique `startMarker`, with marker-count assertions. The start marker bytes are included, the end marker bytes are excluded, and `oldRangeSha256` hashes exactly that selected range.
- `replace_exact`: module-local exact byte/string replacement with uniqueness assertion.

Initial V1.5 assertion and postcondition types:

- `module_must_contain`
- `module_must_not_contain`
- `binary_must_contain`
- `binary_must_not_contain`

Mutating operations always carry `replacement`. Assertions never carry `replacement`.

All text markers are UTF-8 encoded for matching against module bytes. Future binary marker encodings can be added only if a real package needs them.

## 6. Build pipeline

V1.5 build flow:

```text
1. Discover or receive source Claude binary path.
2. Copy no bytes yet; first inspect the source.
3. Run source identity checks: version output, SHA-256, size, platform, arch.
4. Parse Mach-O enough to find exactly one __BUN/__bun section.
5. Parse Bun standalone payload:
   - length prefix;
   - payload bytes;
   - trailer;
   - offsets struct;
   - module table;
   - module records;
   - pointer-pair bounds.
6. Validate graph shape against the engine-owned `bun_standalone_macho64` requirements.
7. Extract an in-memory module map keyed by Bun module path.
8. Match every enabled package target against source identity and module identity.
9. Resolve every operation against original module content.
10. Reject duplicate/missing markers and overlapping ranges within a module.
11. Apply replacements once per module against original module coordinates.
12. Build changed module payloads.
13. Rewrite Bun graph metadata for changed module sizes and shifted payload offsets.
14. Rewrite Mach-O metadata for grown/shrunk __BUN bytes and shifted __LINKEDIT/code-signature data.
15. Write copied output under ClaudeMonkey state/output directory.
16. Preserve executable mode.
17. Ad-hoc sign copied output on macOS.
18. Verify code signature.
19. Recompute final output SHA-256 and size after signing.
20. Re-inspect the signed output's Mach-O and Bun graph; fail if post-sign inspection changes or invalidates the Bun graph.
21. Run static postconditions against changed modules and/or output binary.
22. Smoke copied output with --version and --help using content-based Claude Code checks.
23. Write build-report.json.
24. Activate current symlink only if identity checks, graph validation, operation resolution, static postconditions, signing, post-sign inspection, content-smoke, and required manual smoke all pass, and activation was requested.
```

No step mutates the official source binary.

## 7. Patch stacking model

Patch stacking happens above the packer and is deterministic. In this section, `modulePath` means the same value as the containing module object's `path`: the exact Bun graph module path such as `/$bunfs/root/src/entrypoints/cli.js`.

Rules:

- Group operations by `modulePath`.
- Resolve every operation against the original module content, not against incrementally patched content.
- Sort resolved operations by module path, start offset, end offset, package ID, and op ID.
- Reject overlaps within the same module.
- Allow independent operations in different modules.
- Apply all replacements to each module in one render pass.
- Repack the binary once per build.
- Sign and smoke once per build.

This avoids offset drift between patches and keeps build reports explainable.

## 8. Core module boundaries

V1.5 should keep the application builder separate from binary-format mechanics.

Suggested Python modules:

```text
src/claude_monkey/binary_inspect.py
src/claude_monkey/macho.py
src/claude_monkey/bun_graph.py
src/claude_monkey/module_patch.py
src/claude_monkey/repack.py
src/claude_monkey/build_reports.py
```

### 8.1 `binary_inspect.py`

Responsibilities:

- inspect a source binary without mutation;
- classify supported/unsupported format;
- return source size, SHA-256, Mach-O summary, Bun graph summary, module summaries;
- produce JSON for `inspect-binary --json`.

### 8.2 `macho.py`

Responsibilities:

- parse thin little-endian Mach-O 64-bit initially;
- find `LC_SEGMENT_64` commands;
- locate `__BUN` and `__LINKEDIT`;
- locate `__bun` section;
- locate `LC_CODE_SIGNATURE`;
- locate linkedit data commands whose file offsets shift;
- update segment sizes, section size, `__LINKEDIT` file/vm address, linkedit data offsets, and code-signature offset;
- validate alignment and bounds.

Initial support is macOS arm64 Claude Code's observed thin Mach-O shape. Fat Mach-O or other platforms should fail closed until explicitly implemented.

### 8.3 `bun_graph.py`

Responsibilities:

- parse `__bun` section bytes;
- validate length prefix and trailer;
- parse offsets struct immediately before trailer;
- parse module table records;
- expose modules by path;
- validate pointer-pair bounds against payload length and `byte_count`;
- rewrite module content size and shifted pointer offsets after changed module bytes;
- rewrite offsets struct, payload length, and graph summary.

The parser must not hardcode disputed public-parser assumptions such as unconditional module-table headers or unconditional content pointer `+8`. It should validate the local binary's actual pointer semantics and fail closed when the graph cannot be interpreted unambiguously.

### 8.4 `module_patch.py`

Responsibilities:

- load schema v2 package operations;
- load replacement payloads with SHA checks;
- resolve module-local ranges;
- validate `requireWithinRange`, `oldRangeSha256`, and `oldRangeLength`;
- reject overlaps;
- render changed module bytes;
- return a module patch plan for reporting and repacking.

### 8.5 `repack.py`

Responsibilities:

- orchestrate graph rewrite and Mach-O rewrite;
- write copied output only;
- preserve mode bits;
- return a structured `RepackResult` with graph shifts, Mach-O shifts, changed modules, and validation evidence.

`repack.py` does not own package selection, source identity policy, signing, smoke, activation, or CLI UX. The builder owns those application concerns.

## 9. CLI UX

V1.5 CLI additions:

```bash
claude-monkey inspect-binary --source /path/to/claude --json
claude-monkey validate-package --source /path/to/claude --package /path/to/package --json
claude-monkey build --source /path/to/claude --package /path/to/package --json
```

### 9.1 `inspect-binary --json`

Read-only. Does not write output. Does not sign. Does not smoke.

Minimum JSON shape:

```json
{
  "schemaVersion": 1,
  "ok": true,
  "sourcePath": "/path/to/claude",
  "sourceSha256": "...",
  "sourceSizeBytes": 229328464,
  "format": "macho64",
  "supported": true,
  "bun": {
    "segment": "__BUN",
    "section": "__bun",
    "payloadLength": 165364729,
    "trailerOffset": 165364715,
    "moduleRecordSize": 52,
    "moduleCount": 11,
    "entryPointId": 0
  },
  "modules": [
    {
      "index": 0,
      "path": "/$bunfs/root/src/entrypoints/cli.js",
      "contentLength": 18439743,
      "contentSha256": "...",
      "loader": "js",
      "moduleFormat": "cjs"
    }
  ],
  "validationErrors": []
}
```

### 9.2 `validate-package --source ... --json`

Read-only. Validates that an enabled package can target the source binary and resolve operations, but does not write output.

Minimum JSON shape:

```json
{
  "schemaVersion": 1,
  "ok": true,
  "packageId": "floating-renderer-overlay",
  "sourceMatched": true,
  "modulesMatched": true,
  "operationsResolved": [
    {
      "modulePath": "/$bunfs/root/src/entrypoints/cli.js",
      "opId": "renderer-overlay",
      "moduleStart": 12720354,
      "moduleEnd": 12720989,
      "oldLen": 635,
      "newLen": 17019,
      "delta": 16384,
      "debugCoordinates": {
        "payloadStart": 155038386,
        "absoluteFileStart": 218329786
      }
    }
  ],
  "manualSmokeRequired": true,
  "errors": []
}
```

Machine-readable operation coordinates are always module-local and must be named `moduleStart` and `moduleEnd`. Payload-relative or absolute-file coordinates are optional debug fields and must be named `payloadStart`, `payloadEnd`, `absoluteFileStart`, or `absoluteFileEnd`.

### 9.3 `build --json`

Builds copied output only. Signs and smokes by default. Activates only when requested by the existing activation/config flow.

There is no `--strategy` flag for slots. The V1.5 strategy is Bun graph-aware module repack.

Useful build flags may include:

```bash
--skip-signing       # tests only; never activation eligible
--skip-smoke         # tests only; never activation eligible
--output-dir PATH
--activate
```

V1.5 does not define `--unverified-candidate`. Development builds may skip signing or smoke only through explicit test-only skip flags, and those outputs are never activation eligible. Skip flags must not bypass source identity, module identity, graph validation, operation resolution, static postconditions, or copied-output-only behavior.

If signing or smoke is skipped, the build report must mark the output as not activation eligible.

## 10. Build report

V1.5 extends `build-report.json` with module/repack evidence.

Minimum report fields:

```json
{
  "schemaVersion": 2,
  "status": "manual_smoke_pending",
  "automatedStatus": "passed",
  "engine": "bun_graph_repack",
  "sourceClaudePath": "/path/to/claude",
  "sourceVersion": "2.1.198",
  "sourceVersionOutput": "2.1.198 (Claude Code)",
  "sourceSha256": "...",
  "sourceSizeBytes": 229328464,
  "enabledPatches": ["floating-renderer-overlay"],
  "changedModules": [
    {
      "modulePath": "/$bunfs/root/src/entrypoints/cli.js",
      "oldSize": 18439743,
      "newSize": 18456127,
      "delta": 16384,
      "oldSha256": "...",
      "newSha256": "..."
    }
  ],
  "operationsApplied": [
    {
      "packageId": "floating-renderer-overlay",
      "opId": "renderer-overlay",
      "modulePath": "/$bunfs/root/src/entrypoints/cli.js",
      "moduleStart": 12720354,
      "moduleEnd": 12720989,
      "oldLen": 635,
      "newLen": 17019,
      "delta": 16384,
      "oldSha256": "...",
      "debugCoordinates": {
        "payloadStart": 155038386,
        "absoluteFileStart": 218329786
      }
    }
  ],
  "bunGraphUpdates": {
    "oldPayloadLength": 165364729,
    "newPayloadLength": 165381113,
    "moduleRecordSize": 52,
    "moduleCount": 11,
    "shiftedPointers": 0,
    "shiftedModulesOffset": true,
    "validationErrors": []
  },
  "machoUpdates": {
    "bunSectionSizeDelta": 16384,
    "bunSegmentSizeDelta": 16384,
    "linkeditFileoffDelta": 16384,
    "linkeditVmaddrDelta": 16384,
    "codeSignatureOffsetDelta": 16384
  },
  "verificationResults": [],
  "outputPath": "/path/to/output/claude",
  "outputSha256": "...",
  "outputSizeBytes": 229344848,
  "signingResult": {
    "status": "passed"
  },
  "postSignInspection": {
    "bunGraphValid": true,
    "validationErrors": []
  },
  "smokeTestResults": [],
  "manualSmoke": {
    "required": true,
    "status": "pending",
    "reason": "UI-affecting renderer patch"
  },
  "activationEligible": false,
  "activationBlockers": ["manual_smoke_pending"],
  "activationStatus": "blocked",
  "failureReason": null,
  "skippedGates": []
}
```

Report rules:

- `engine` must be `bun_graph_repack` for V1.5 builds.
- Failed builds still write a report when possible.
- Manual/visual smoke status is visible and separate from automated smoke.
- `status` is the overall build status. `automatedStatus` records automated gate results. A UI-affecting build with pending manual smoke must not be reported simply as `verified`.
- `activationEligible` must be false whenever signing, automated smoke, post-sign inspection, source/module identity, or required manual smoke is incomplete or failed.
- The report should include enough graph/Mach-O update evidence for future debugging, but V2 UI should not branch on internal update details.

## 11. Safety and fail-closed behavior

Hard safety rules:

- Never mutate the official Claude binary.
- Never patch an unrecognized binary shape.
- Never activate an output that was not signed, post-sign inspected, content-smoked successfully, and cleared of required manual-smoke blockers.
- Never treat successful signing as proof of correct Bun graph metadata.
- Never treat `--version` alone as sufficient smoke; `--help` must also show Claude Code behavior, not Bun runtime help.
- Never silently continue after graph validation errors.
- Never infer module paths from fuzzy string scans when graph records are ambiguous.
- Never accept duplicate target modules for a package operation.
- Never run package-provided build hooks, install hooks, shell scripts, or arbitrary package executables during build. Automated smoke is different: it executes the copied candidate binary only after source identity, module identity, graph validation, operation resolution, static postconditions, signing, and post-sign inspection have passed.

Automated smoke passes only if:

- `--version` exits 0 and exactly matches `sourceIdentity.versionOutput`.
- `--help` exits 0.
- Help output contains Claude Code-specific markers.
- Help output does not match Bun runtime help.

Failure examples:

- Missing `__BUN/__bun`: fail `unsupported_binary_shape`.
- Multiple `__BUN/__bun`: fail until multi-arch/multi-section support is designed.
- Payload length/trailer mismatch: fail `bun_payload_invalid`.
- Module table size not divisible by 52: fail `bun_module_table_invalid`.
- Module path not found exactly once: fail `module_identity_failed`.
- Module content SHA mismatch: fail `module_identity_failed`.
- Operation marker duplicate/missing: fail `operation_resolution_failed`.
- Overlapping operations in one module: fail `patch_conflict`.
- Codesign failure: fail `signing_failed`.
- Smoke returns Bun CLI help/version rather than Claude Code: fail `smoke_failed`.

## 12. V2 menu bar integration

V2 remains thin and strategy-agnostic. Since V1.5 removes strategy choice, V2 should display build engine/result but not expose packer internals.

V2 JSON contract additions:

`status --json` should include, when known:

```json
{
  "latestBuildEngine": "bun_graph_repack",
  "latestBuildStatus": "manual_smoke_pending",
  "latestBuildReportPath": "/Users/example/.claude-monkey/.../build-report.json",
  "manualSmokeRequired": true,
  "activationEligible": false,
  "rebuildRequired": false
}
```

`build --json` result envelope should include:

```json
{
  "schemaVersion": 1,
  "ok": true,
  "status": "ok",
  "summary": "Built copied Claude binary with Bun graph repack engine",
  "engine": "bun_graph_repack",
  "reportPath": "/Users/example/.claude-monkey/.../build-report.json",
  "manualSmokeRequired": true,
  "activationEligible": false,
  "error": null
}
```

The menu bar should not know how Bun graph records, Mach-O segments, or code-signature offsets work. It calls CLI commands, refreshes state, opens reports, and shows build/manual-smoke status.

## 13. Migration implications

V1 packages authored as whole-binary slot replacements do not run under the V1.5 build engine.

Required migration path for each package:

1. Inspect the target Claude binary with `inspect-binary --json`.
2. Identify the Bun module containing the existing patch site.
3. Re-express the operation as a module-local operation.
4. Add module content length and SHA identity.
5. Add old range length and SHA identity.
6. Move replacement payloads unchanged if still correct.
7. Add module-level postconditions.
8. Mark manual/visual smoke requirements for UI-affecting patches.
9. Validate package against source.
10. Build with the V1.5 repack engine.

A future `suggest-module-migration-from-v1` helper may assist package authors by reading a V1 package and suggesting module coordinates. That helper would be a migration aid, not a runtime compatibility path.

## 14. Testing and verification plan

### 14.1 Unit tests

Test areas:

- Mach-O parser finds `__BUN`, `__bun`, `__LINKEDIT`, and `LC_CODE_SIGNATURE` in synthetic fixtures.
- Mach-O updater shifts expected load-command offsets in synthetic fixtures.
- Bun graph parser validates length prefix, trailer, offsets struct, module table size, pointer bounds, and module paths.
- Bun graph parser rejects header/content-pointer assumptions that are not proven by the fixture shape.
- Module operation planner resolves ranges inside module bytes.
- Module operation planner rejects duplicate markers, missing markers, old range hash mismatch, and overlaps.
- Repacker updates changed module size and shifted pointers.
- Build report serializes changed modules, graph updates, Mach-O updates, output identity, signing, post-sign inspection, content-based smoke, manual smoke, activation eligibility, and failure reasons.
- CLI `inspect-binary --json` and `validate-package --json` are read-only.

### 14.2 Fixture tests

Use synthetic fixture binaries for normal tests. Fixtures should be small but structurally representative:

- minimal thin Mach-O-like fixture with `__BUN`/`__bun` and `__LINKEDIT` metadata;
- minimal Bun payload fixture with trailer, offsets struct, module records, and two modules;
- fixture where module 0 grows and shifts later pointers;
- fixture where no module grows but the same repack engine still renders output;
- invalid fixtures for each fail-closed condition.

### 14.3 Local real-binary tests

Real Claude Code tests remain opt-in and copied-output-only.

Suggested environment gate:

```bash
CLAUDE_MONKEY_LOCAL_REAL_REPACK=1 python3 -m pytest -m local_real_repack -q
```

Real-binary acceptance checks:

- source SHA/size/version match expected target;
- `inspect-binary --json` finds expected module path and no validation errors;
- `validate-package --json` resolves operations;
- `build --json` writes copied output only;
- `codesign --verify --strict` passes;
- output `--version` exits 0 and exactly matches the expected Claude Code version output;
- output `--help` exits 0, contains Claude Code-specific help markers, and does not match Bun runtime help;
- build report records manual smoke requirement for UI patches;
- smoke rejects a copied binary that exits 0 but reports Bun runtime version/help;
- signed output is re-inspected and the graph remains valid;
- official Claude binary hash remains unchanged.

### 14.4 Manual visual smoke

For UI-affecting patches, automated smoke is necessary but not sufficient.

Manual smoke should verify:

- patched binary launches in an interactive terminal;
- relevant Claude Code UI path renders;
- patch-specific visual behavior appears;
- no obvious layout regression blocks normal use.

Manual smoke completion can be recorded later in a report note or separate verification artifact, but V1.5 should not fake it as automated proof.

## 15. Implementation sequence after spec approval

1. Update the active builder contract so schema v1 whole-binary packages are rejected with a migration-required error in V1.5 builds. The V1 same-size patch code may remain only as archived legacy code or test fixture support, not as an active build strategy.
2. Add schema v2 manifest models and validators for module-coordinate packages.
3. Add read-only Bun/Mach-O inspection and `inspect-binary --json`.
4. Add module operation planner and package validation.
5. Add synthetic Bun graph repack fixture and failing tests.
6. Implement Bun graph rewrite for changed modules.
7. Implement Mach-O update for changed `__BUN` size and shifted `__LINKEDIT`/code-signature offsets.
8. Wire builder to use only the V1.5 repack engine for schema v2 packages.
9. Extend build reports with output identity, post-sign inspection, content-smoke evidence, manual-smoke state, and activation eligibility.
10. Add signing, post-sign inspection, content-smoke, and manual-smoke activation eligibility rules.
11. Migrate one reference package to schema v2 as proof.
12. Run synthetic tests.
13. Run opt-in copied real-binary smoke only with explicit approval.
14. Update V2 JSON/status contract docs if needed.

Stop before implementation if the user wants an implementation plan first. This document is the design surface, not a code-change plan.
