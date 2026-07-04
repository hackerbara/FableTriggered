# ClaudeMonkey shim update resilience

**Date:** 2026-07-04  
**Status:** Design stub for later implementation  
**Scope:** Detect and recover when an official Claude install replaces the global `claude` target that ClaudeMonkey had previously managed with a shim.

## Observed failure mode

ClaudeMonkey's patched runtime is still intact, but the shell entrypoint is no longer the managed shim:

- Patched binary/current link is still present: `/Users/MAC/.claude-monkey/current -> /Users/MAC/.claude-monkey/versions/2.1.199/patchsets/default/claude`.
- Global shell target was replaced by a newly installed official Claude: `/Users/MAC/.local/bin/claude` now points into `/Users/MAC/.local/share/claude/versions/2.1.201`.
- New official target digest observed from the main thread: `a0852d76afc47b30f5cb0b7625ec9a7714cb189f2eeef6c28c77e2be954fb7fd`.
- ClaudeMonkey's `install-record.json` still records `targetPath: /Users/MAC/.local/bin/claude` and a managed shim digest, so status correctly reports `shimInstalled: false`: the target exists, but it is no longer the shim ClaudeMonkey installed.
- CMux can override the launched Claude with `automation.claudeBinaryPath` / `CMUX_CUSTOM_CLAUDE_PATH`; when unset, CMux wraps whatever `claude` resolves from `PATH`, so this replacement can silently bypass ClaudeMonkey.

This is not a broken patched build. It is a replaced global target plus stale managed-shim intent.

## Product behavior we want

When an official Claude update replaces a target that ClaudeMonkey had already managed, ClaudeMonkey should:

1. Recognize the target as a new official source, not as an arbitrary corruption.
2. Copy/cache that official source into ClaudeMonkey local state for future rebuilds.
3. Reinstall the existing ClaudeMonkey shim **only if** the install record proves ClaudeMonkey previously managed that target.
4. Notify the user: "New Claude version available; roll it out?" with enough detail to distinguish "shim repaired" from "patched binary updated".
5. Rebuild/apply patches only after a user-triggered rollout path, with validation/smoke gates unchanged.

## Staged architecture

### 1. Detection/status

Extend status computation to compare three identities:

- install-record target path and expected managed shim digest;
- current filesystem target identity/digest;
- known cached official source digests under ClaudeMonkey state.

New status should expose a distinct condition such as `official_update_available` or a structured warning on the existing status payload:

```json
{
  "shimInstalled": false,
  "shimPreviouslyManaged": true,
  "targetReplacedByOfficial": true,
  "detectedOfficialVersion": "2.1.201",
  "detectedOfficialSha256": "a0852d76afc47b30f5cb0b7625ec9a7714cb189f2eeef6c28c77e2be954fb7fd",
  "shimRepairAvailable": true,
  "rolloutRequired": true
}
```

The first implementation can stub version extraction if digest/path detection is reliable.

### 2. Cache official source

Before repairing the shim, copy the detected official source into local state, keyed by digest and version when available, for example:

```text
~/.claude-monkey/sources/<sha256>/claude
~/.claude-monkey/sources/<sha256>/source-record.json
```

The cache is the source of truth for future rebuilds. Do not build from `/Users/MAC/.local/bin/claude` after it may become a shim again.

### 3. Reinstall existing shim only if previously managed

Shim repair is allowed only when:

- an install record exists for the exact target path;
- the record contains ClaudeMonkey's previous managed shim digest/marker;
- the current target is classified as an official Claude source or another safe restoreable source;
- the official source has been cached first.

Repair action: reinstall the ClaudeMonkey shim at the recorded target path, preserving rollback data that can restore the newly cached official source.

### 4. Notify UI

The GUI/menu/status layer should show two separate facts:

- **Shim repaired/repair available:** launches through `PATH` can be routed back through ClaudeMonkey.
- **New Claude available:** active patched binary remains the previous version until the user rolls out the new source.

Suggested label: `Claude 2.1.201 available — shim repair needed` or, after safe repair, `Claude 2.1.201 available — rebuild to roll out`.

### 5. User-triggered rebuild/rollout

Rollout should be a normal mutating operation: select cached official source, rebuild patches, validate/sign/smoke, then update `~/.claude-monkey/current` only on success. Auto-repairing a shim is not the same as auto-activating a newly rebuilt patched binary.

## Non-goals and safety boundaries

- Do not overwrite an arbitrary target just because it differs from the recorded shim digest.
- Do not delete or replace the detected official source before it is cached and restorable.
- Do not rebuild from a live path that may become a shim during the operation.
- Do not auto-activate rebuilt patches without the existing validation/manual smoke requirements for the selected patch set.
- Do not make CMux path overrides magical: if `automation.claudeBinaryPath` / `CMUX_CUSTOM_CLAUDE_PATH` is set, report that it bypasses PATH shim behavior rather than silently changing it.

## CLI/UI surfaces

Stub now:

- `claude-monkey status --json`: add structured fields for `shimPreviouslyManaged`, `targetReplacedByOfficial`, detected source digest/version, `shimRepairAvailable`, and `rolloutRequired`.
- GUI/window/tray status: render a warning/notice for replaced managed shim and new official source available.
- `claude-monkey install-shim --json`: preserve enough result detail to say whether this was a normal install or managed-shim repair after official update.

Implement later:

- `claude-monkey cache-source --target <path> --json` or internal equivalent called by status/repair.
- `claude-monkey repair-shim --target <path> --json` as an explicit command if overloading `install-shim` makes state transitions unclear.
- `claude-monkey rollout-source --source-sha <sha> --json` or equivalent rebuild/apply flow that selects a cached source.
- UI action: "Roll out Claude <version>…" opening the existing long-operation progress window.

## Testing strategy

Likely files to touch when implemented:

- `tests/test_status_v3.py` — status payload for replaced managed shim, new official digest/version, rollout-required warning.
- `tests/test_shim.py` and `tests/test_shim_v3.py` — managed-record detection, shim digest mismatch classification, safe repair gating.
- `tests/test_install.py` and `tests/test_install_progress.py` — transaction behavior: cache source before reinstalling shim; restore path remains safe.
- `tests/test_cli_json_contracts.py` — additive JSON fields stay stable and optional consumers remain compatible.
- `tests/test_menubar_state.py` / `tests/test_menubar_state_v3.py` — warning labels and state parsing for shim repair/new source available.
- `tests/test_gui_window_model.py`, `tests/test_gui_tray.py`, and `tests/test_gui_app.py` — UI affordances for "new version available" and rollout/repair actions.
- `tests/test_menubar_commands.py` or `tests/test_gui_commands.py` — argv builders for any new `repair-shim`, `cache-source`, or rollout command.

Use disposable temp targets and copied fake Claude binaries; no test should mutate `/Users/MAC/.local/bin/claude` or the real `~/.claude-monkey` state.

## Refinements (controller review, 2026-07-04)

### R1. Reconcile with what already exists — the spec must not design past the code

Two pieces of this spec are already partially implemented and the spec must own them, not duplicate them:

- `install.py:94-95` **already writes** `previousSourceCachePath` / `previousSourceSha256` into `install-record.json` at shim install time.
- `launch_profile._install_record_source` **already consumes** those fields as a last-resort launch target (after `official_fallback`), with sha256 + executability gates.

§2's proposed `~/.claude-monkey/sources/<sha256>/` layout is a *second* cache scheme. Decide one: either (a) generalize the existing install-record cache into the `sources/` store and migrate the record fields to reference it, or (b) drop the `sources/` layout and key everything off the install-record cache. Do not ship both. The detection logic (§1) must read whichever store wins.

### R2. Repair is user-triggered — never silent

§Product-behavior 3 ("Reinstall … only if the record proves…") is ambiguous about *who initiates*. Resolved: **repair always requires an explicit user action** (one click from the notice — "Repair shim"). Silently overwriting a freshly installed official Claude, even a provably once-managed target, is hostile to the user who may have intentionally reinstalled to escape the shim. The record proof is a *precondition*, not a trigger.

### R3. Re-verify at swap time (TOCTOU)

Between detection/classification and repair, the target can change again (the official updater runs concurrently and asynchronously). Repair must: (1) re-hash the target immediately before the swap, abort if it no longer matches the digest that was classified; (2) cache-then-swap via rename within the target's directory (atomic on same filesystem), never write-in-place; (3) treat abort as a fresh detection round, not an error.

### R4. Repair must update rollback data, not preserve it

§3 says "preserving rollback data" — under-specified and, as written, wrong in one case: after repair, the install record's previous-source fields must point at the **newly cached official source** (2.1.201), not the stale one (2.1.199). Otherwise `uninstall-shim` after a repair restores an outdated binary. Repair = reinstall shim + rewrite record with new source cache path/digest/version.

### R5. Detection cadence and idempotence

Define when detection runs: on every `status --json` computation (it is a cheap stat + hash of one file; hash can be mtime/size-gated) and therefore on every GUI refresh. No background watcher in v1. Detection must be idempotent and recurring — the official updater will clobber the shim again on every future update; this loop is the steady state, not an edge case. The notice must therefore be dismissable-but-recurring (re-raised per new digest, not per refresh).

### R6. Cache retention

Official binaries are large. Retention policy for the source cache: keep the current rollback source plus the N most recent distinct digests (N=2 default), GC the rest during successful rollout. Never GC the digest referenced by the active install record.

### R7. Version-unknown UX

§1 allows stubbing version extraction, but §4's labels lean on version strings. Fallback label format when version is unknown: `New Claude build available (a0852d76…) — shim repair needed` (first 8 hex of digest). Version extraction failure must not suppress the notice.

### R8. Trust-domain note (record tampering)

`install-record.json` and the source cache live in user-writable state; the sha256 fields are supplied by the same file that names the path — the gate proves internal consistency, not provenance. That is acceptable *within the same trust domain* (an attacker who can write `~/.claude-monkey` can already replace the patched binary), but: the repair path must never elevate (no sudo/auth reuse to write a protected target based on record contents alone — protected targets re-run the normal `authorizationRequired` flow), and status output must not present record-derived "official" classification as verified-Anthropic — digest match against a *known* cached source is the strongest claim we make.

### R9. Additional tests implied by R1–R5

- Launch-target priority order pinned: `install_record_source` stays strictly after `official_fallback` (regression-pin the ordering `select_launch_target` implements today).
- Concurrent-clobber: target digest changes between detect and repair → repair aborts cleanly, no partial write, next status re-detects.
- Corrupt cache: cached source fails sha check → repair refuses, notice degrades to "cache invalid — rebuild required", no fallback execution of the corrupt file (`_install_record_source` must return None — already covered, keep it pinned).
- Repair-then-uninstall: uninstall after repair restores the NEW official source (R4).
- CMux override set (`CMUX_CUSTOM_CLAUDE_PATH`): status reports the bypass; repair notice suppressed or annotated per §Non-goals.
