# ClaudeMonkey north-star design and runbook

Date: 2026-07-02
Status: approved brainstorming draft
Project: ClaudeMonkey, formerly FableTriggered / Claude-patch

## 1. Product frame

ClaudeMonkey is a source-first local customization manager for Claude Code: userscript-style customization, but implemented through a trusted manager rather than arbitrary executable patch scripts.

The product has two first-class surfaces:

1. **Patch manager**: declarative binary customizations, patch stacking, copied-binary builds, verification, signing, and activation.
2. **Prompt manager**: selected system prompt files injected through Claude Code's system-prompt command-line switch by the managed launcher/shim.

The durable spine is a Python CLI/core. The menu bar companion should be a thin optional control surface over the same state and commands, not a second implementation of patching logic.

## 2. Version ladder

### v1: Python CLI patch/prompt manager

Goals:

- Pure/source-first Python core.
- Declarative local patch packages.
- Patch stacking.
- Managed `claude` shim as the default install path.
- Symlink-managed patched Claude binary behind the shim.
- CLI permissions UX with macOS GUI authorization plus terminal `sudo` fallback.
- Prompt manager that injects a selected system prompt through Claude's system-prompt CLI switch.
- Reference packages for the current Fable fallback visibility patch and reminder-suppression patch.
- Advanced, explicit in-place replacement support with strong warnings and backups.

### v2: Rough source-first menu bar companion

Goals:

- Optional menu bar UI over the Python CLI/core.
- Patch enable/disable submenu.
- Prompt picker submenu.
- Rebuild/apply confirmation for binary patch changes.
- Status display for active Claude version, active patch set, current prompt profile, and rebuild-required state.
- Source-first distribution if practical; fall back to Swift only if the lightweight source-first menu bar route proves too awkward.

### v3: Version drift and compatibility workflows

Goals:

- Detect Claude Code version/SHA drift.
- Report exact version and SHA mismatches.
- Build unverified candidate copies when explicitly requested.
- Run smoke checks and static verification against candidates.
- Support publishing or updating verified manifests once compatibility is established.

### v4: Polish and broader UX hardening

Goals:

- Better onboarding.
- Clearer visual status and error surfaces.
- Improved packaging and distribution.
- More polished Mac utility behavior.

## 3. Core architecture

Default installed command flow:

```text
User runs `claude`
  -> ClaudeMonkey managed shim
  -> reads active config/profile
  -> execs active patched Claude binary symlink
  -> injects system-prompt flag if a prompt profile is enabled
  -> passes through all original user args
```

Storage model:

```text
~/.claude-patches/                  # local declarative patch packages
~/.claude-monkey/
  config.json                       # active profile and install state
  prompts/                          # optional managed prompt profiles
  versions/
    2.1.198/
      original-metadata.json        # discovered version, SHA, path
      patchsets/
        <patch-set-id>/
          claude                    # patched, signed binary copy
          build-report.json         # operations, verification, smoke result
  current -> versions/<version>/patchsets/<patch-set-id>/claude
  bin/claude                        # managed `claude` shim when installed in user path
```

Important boundaries:

- Patch packages live in `~/.claude-patches/` and are declarative.
- Manager state and build outputs live in `~/.claude-monkey/`.
- The official Claude binary is treated as source input, not casually mutated.
- The default install is shim plus patched-copy symlink.
- In-place replacement is an advanced explicit mode, not normal operation.

Example config model:

```json
{
  "activeProfile": "default",
  "profiles": {
    "default": {
      "enabledPatches": ["fable-fallback", "reminder-suppression"],
      "promptProfile": "research"
    }
  },
  "installMode": "shim",
  "activePatchSet": "2.1.198-default-fable-reminders"
}
```

The CLI and menu bar may expose direct controls such as "enable patch" or "choose prompt," but internally those mutate the active profile. Users should not have to think in profiles for ordinary use.

## 4. Declarative patch package format

v1 patch packages are local, declarative, and non-executable:

```text
~/.claude-patches/fable-fallback/
  patch.json
  README.md

~/.claude-patches/reminder-suppression/
  patch.json
  README.md
```

Example shape:

```json
{
  "schemaVersion": 1,
  "id": "fable-fallback",
  "name": "Fable fallback visibility",
  "description": "Shows Fable fallback events in resumed history and /resume.",
  "targets": [
    {
      "claudeVersion": "2.1.198",
      "sha256": "ab6f7ee109816ede414f7c285446633f805b623aa609f425609a64266451d61e",
      "operations": [
        {
          "type": "replace_between",
          "startMarker": "case\"assistant\":{let R;if(t[20]!==r.firstTextBlockUuidByMessageID",
          "endMarker": "case\"user\":{",
          "requireWithinRange": ["x=n.message.content.map"],
          "replacement": "<full version-specific replacement JavaScript>",
          "padding": "spaces"
        }
      ],
      "verify": {
        "mustContain": ["Fable classifier triggered"],
        "mustNotContain": []
      }
    }
  ]
}
```

v1 operation vocabulary should stay intentionally narrow:

- `replace_between`
- `replace_exact`
- `must_contain`
- `must_not_contain`

No arbitrary scripts are allowed in patch packages for v1. The trusted ClaudeMonkey manager owns byte editing, padding, signing, verification, smoke testing, activation, and reporting.

## 5. Build, stacking, compatibility, and verification

v1 build flow:

```text
1. Discover official Claude binary.
2. Record displayed Claude version and SHA-256.
3. Load active profile.
4. Resolve enabled patch packages from ~/.claude-patches/.
5. Match each package target against version and SHA.
6. If all targets match, preflight operations against the original binary.
7. Compute byte ranges for every operation.
8. Refuse overlapping ranges.
9. Apply all non-overlapping operations in deterministic original-offset order.
10. Verify package-level mustContain / mustNotContain rules.
11. Ad-hoc sign on macOS.
12. Smoke test: --version, --help, and codesign verification where applicable.
13. Write build-report.json.
14. Activate ~/.claude-monkey/current symlink.
```

Compatibility behavior:

- **Version mismatch**: normal apply is blocked; show expected vs found version.
- **SHA mismatch**: normal apply is blocked even if the displayed version matches; show expected vs found SHA.
- **Explicit unverified candidate mode**: allowed, but must patch a copy only, mark the build as unverified, run verification/smoke checks, require explicit user confirmation before activation, and never publish the result as verified automatically.

Patch stacking rules:

- All ranges are computed against the original source binary.
- Replacement bytes must fit within the original range unless a later schema explicitly supports size-changing rewrites.
- Non-overlapping patches can stack.
- Overlapping ranges are a hard v1 conflict.
- Patch application order is deterministic by original byte offset, not user intuition.

## 6. CLI and menu bar UX

v1 CLI commands should cover the product spine:

```bash
claude-monkey doctor
claude-monkey list-patches
claude-monkey enable <patch-id>
claude-monkey disable <patch-id>
claude-monkey list-prompts
claude-monkey set-prompt <prompt-id-or-path>
claude-monkey clear-prompt
claude-monkey build
claude-monkey install-shim
claude-monkey uninstall-shim
claude-monkey status
```

Default installation:

- `install-shim` installs a managed `claude` launcher.
- The shim reads `~/.claude-monkey/config.json`.
- The shim execs `~/.claude-monkey/current`.
- If a prompt profile is active, the shim injects Claude's system-prompt CLI switch.
- All other user arguments pass through unchanged.

Permissions UX:

- Prefer macOS GUI authorization when modifying protected install locations.
- Fall back to terminal `sudo`.
- Keep patch builds in user-writable storage without elevation.

v2 menu bar companion:

- Source-first and optional.
- Thin wrapper over the CLI/core.
- Shows active Claude version, active patch set, prompt profile, and rebuild-required state.
- Offers patch enable/disable submenu.
- Offers prompt picker submenu.
- Offers build/rebuild, install/uninstall shim, and open build report/log actions.
- Prompt changes write config and take effect on the next Claude launch.
- Patch changes stage desired state and require a Rebuild/Apply confirmation.

## 7. Failure handling, safety, and trust boundaries

ClaudeMonkey should fail closed because it modifies executable bytes.

Core safety rules:

- Never mutate the official Claude binary during normal operation.
- Build from a copied source binary into `~/.claude-monkey/versions/<version>/patchsets/<patch-set-id>/`.
- Never run package-provided executable code in v1.
- Refuse ambiguous markers, duplicate markers, missing required bytes, oversized replacements, and overlapping patch ranges.
- Preserve enough build evidence that a user can understand exactly what changed.

Every build should produce a `build-report.json` containing:

```text
sourceClaudePath
sourceVersion
sourceSha256
enabledPatches
operationsApplied
byteRanges
verificationResults
signingResult
smokeTestResults
verified | unverifiedCandidate
activationStatus
```

Important failure states:

- Patch unavailable for installed version -> show compatible versions.
- Version/SHA mismatch -> block normal build and offer unverified candidate.
- Marker missing or duplicate -> fail closed.
- Patch conflict -> show both patch IDs and overlapping byte ranges.
- Codesign failure -> do not activate.
- Smoke failure -> do not activate.
- Shim install failure -> leave previous command untouched if possible.
- Rebuild required -> CLI/menu bar shows desired state differs from active patch set.

Trust model:

- Local patch packages are user-provided data, not trusted programs.
- ClaudeMonkey's interpreter is the trusted code.
- Remote registries and community distribution are out of v1.
- Advanced in-place replacement is allowed only through explicit commands with scary warnings and backups.

## 8. Follow-on design sessions

This document is the north-star map, not the implementation plan. The next design sessions should be split by surface:

1. **Patch manifest schema**: exact JSON schema, validation rules, byte/string encoding, multi-target representation, and migration of the two current patches.
2. **Python CLI/core**: module boundaries, command behavior, filesystem layout, build pipeline, report format, and tests.
3. **Shim and prompt manager**: system-prompt switch injection, argument passthrough, prompt profile storage, and install/uninstall behavior.
4. **Permissions UX**: macOS GUI authorization, `sudo` fallback, protected path handling, and recovery/rollback.
5. **Menu bar companion**: source-first feasibility, CLI integration, staged rebuild UI, status model, and fallback to Swift if necessary.
6. **Version drift workflow**: candidate builds, mismatch reporting, verification matrix, and verified manifest publication rules.

