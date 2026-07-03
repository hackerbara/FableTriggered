# ClaudeMonkey V3 package, launch-profile, options, and compatibility design

Date: 2026-07-02
Status: draft revised after adversarial review; §16 and refresh-cadence superseded (see note)
Project: ClaudeMonkey
Scope: V3 design only; no runtime implementation in this document

> **Supersession note (2026-07-03):** §16 (menu bar integration) and its
> refresh-cadence rules are superseded by
> `2026-07-03-claude-monkey-v3-gui-design.md` (PySide6 tray + manager window
> + progress window; manual Refresh retained alongside this spec's
> auto-refresh cadence). §§2–15 remain the authoritative package-model
> design and are **implementation phase 1**; the GUI spec is phase 2 and
> builds against this spec's CLI surface.

## 1. Product position

ClaudeMonkey V3 makes the active Claude launch profile explicit and package-driven.

The active launch profile is not a new multi-profile product. It is the existing active profile made coherent enough to describe every local customization that affects a managed Claude launch:

- one prompt package;
- an ordered list of patch packages;
- an ordered list of command-line option packages.

V2's menu bar remains a thin control plane over the CLI/core. Its visible submenus map directly to the active launch profile:

```text
Prompts
Patches
Command Line Options
```

V1.5's Bun graph-aware repack remains the patch engine. V3 does not make the menu parse Bun graphs or patch internals. It makes package state, launch-time state, and compatibility state visible through CLI JSON and build reports.

## 2. Clean storage model

V3 uses one ClaudeMonkey home. There are no separate top-level package roots such as `~/.claude-patches/` or `~/.claude-options/` in the clean design.

```text
~/.claude-monkey/
  config.json
  patches/
    <patch-id>/
      *.json
      payloads/...
      README.md
  prompts/
    <prompt-id>/
      *.json
      prompt.md
      README.md
  options/
    <option-id>/
      *.json
      README.md
  versions/
    <source-version>/
      patchsets/
        <patchset-id>/
          claude
          build-report.json
  current
  bin/
  logs/
```

Package discovery scans child package folders under `patches/`, `prompts/`, and `options/` and loads JSON manifests inside each child folder. Filenames are descriptive and not part of the package contract. The manifest contents are authoritative.

Validation rules:

- `kind` must match the bucket: `patch`, `prompt`, or `option`.
- `id` must match the package folder slug.
- A package folder must contain exactly one valid manifest for its kind.
- Invalid packages are reported with validation errors in list/status output; they must not disappear silently.

## 3. Common package manifest envelope

All package kinds use one common manifest envelope:

```json
{
  "schemaVersion": 1,
  "kind": "patch | prompt | option",
  "id": "package-slug",
  "label": "Human label",
  "description": "Human description",
  "compatibility": {
    "claudeVersions": ["2.1.199"],
    "platforms": ["darwin"],
    "arches": ["arm64"]
  },
  "risk": {
    "level": "low | medium | high",
    "requiresConfirmation": false,
    "statusWarning": null
  }
}
```

Required common fields:

- `schemaVersion`
- `kind`
- `id`
- `label`
- `description`

Optional common fields:

- `compatibility`
- `risk`

Package-level compatibility is optional for every kind. Absence of `compatibility` means unconstrained, not invalid.

Risk metadata is optional. Default risk is `low`, `requiresConfirmation: false`, and no status warning.

### 3.1 Manifest validation details

Common validation rules:

- `id` must be a stable slug matching `^[a-z0-9][a-z0-9._-]*$`.
- `kind` must be exactly `patch`, `prompt`, or `option`.
- The required kind-specific object must be present: `patch`, `prompt`, or `option`.
- Unknown top-level fields are invalid unless the schema explicitly reserves them in a future `x-` extension namespace.
- SHA-256 fields must be 64 lowercase or uppercase hex characters.
- Package-local paths must stay inside the package directory after resolution; `..` traversal is invalid.
- Package-local symlinks are allowed only if their resolved target remains inside the package directory.
- If a package folder contains multiple JSON files, discovery succeeds only when exactly one JSON file validates as the package manifest for that folder. Multiple valid manifests are an error. Zero valid manifests is an invalid-package result with collected parse/validation errors.

## 4. Prompt package schema

A prompt package is a first-class ClaudeMonkey package. There is one active prompt package per launch profile.

```json
{
  "schemaVersion": 1,
  "kind": "prompt",
  "id": "research",
  "label": "Research",
  "description": "Append research-oriented instructions to Claude Code.",
  "prompt": {
    "mode": "append",
    "source": {
      "path": "prompt.md",
      "sha256": "optional"
    }
  },
  "risk": {
    "level": "low"
  }
}
```

Prompt-specific rules:

- `prompt.mode` is `append` or `replace`.
- `prompt.source.path` is package-local.
- `prompt.source.sha256` is optional; if present, it must match the package-local prompt file.
- The shim injects the selected prompt with Claude Code's file-based system prompt flags.
- `mode: "append"` maps to `--append-system-prompt-file <package-local path>`.
- `mode: "replace"` maps to `--system-prompt-file <package-local path>`.
- User-supplied prompt flags always win over active prompt selection; launch preview reports the active prompt as skipped with reason `user_prompt_flag_present`.

The internal prompt-injection channel is protected. Option packages may not declare argv forms that would hijack this channel:

```text
--system-prompt
--system-prompt-file
--append-system-prompt
--append-system-prompt-file
```

## 5. Option package schema

An option package is a local userscript-style package for launch-time argv/env defaults. It is declarative only. It cannot execute scripts, write files, fetch from the network, patch binaries, or provide prompt text.

```json
{
  "schemaVersion": 1,
  "kind": "option",
  "id": "local-session-defaults",
  "label": "Local session defaults",
  "description": "Apply local default argv/env settings for normal Claude sessions.",
  "option": {
    "argv": ["--model", "sonnet"],
    "env": {},
    "conflictsWithArgv": ["--model"],
    "conflictsWithOptions": [],
    "conflictsWithEnv": []
  },
  "risk": {
    "level": "low"
  }
}
```

Option-specific rules:

- `option.argv` is an ordered list of strings.
- The entire `option.argv` list is treated as one argv contribution for conflict skipping. If user argv contains any package-declared `conflictsWithArgv` token, ClaudeMonkey skips that option package's whole argv contribution so paired values cannot dangle.
- `option.env` is an object whose keys are environment variable names.
- `option.conflictsWithArgv` is package-declared. ClaudeMonkey does not maintain a complete Claude flag semantics database.
- `option.conflictsWithOptions` is a list of option package ids that cannot be enabled or merged together.
- `option.conflictsWithEnv` can turn env overlap into an error.
- Exact duplicate argv entries are skipped/warned generically.
- Explicit user argv always wins over configured option defaults.

Environment entries support literal values and launch-time environment references:

```json
{
  "ANTHROPIC_BASE_URL": {
    "value": "http://127.0.0.1:8080",
    "secret": false,
    "allowOverrideProcessEnv": false
  },
  "ANTHROPIC_API_KEY": {
    "valueFromEnv": "CLAUDE_MONKEY_PROXY_API_KEY",
    "secret": true,
    "allowOverrideProcessEnv": false
  }
}
```

Env rules:

- Environment variable names must match `^[A-Za-z_][A-Za-z0-9_]*$`.
- `value` and `valueFromEnv` are mutually exclusive.
- `valueFromEnv` is resolved by the shim at launch time.
- `secret` defaults to `false`.
- `allowOverrideProcessEnv` defaults to `false`.
- Base process environment wins by default: an option package must not overwrite an env var already present in the shim process environment unless that env entry sets `allowOverrideProcessEnv: true`.
- Enabled options are applied in launch-profile order. Later option packages win for env values set by earlier option packages unless a conflict policy errors.
- `conflictsWithEnv` is checked against the base process env and against env values contributed by all enabled option packages in profile order.
- `policy: "error"` errors if the named env var is already present in the base process env or would be set by more than one enabled option package.
- Launch preview redacts values where `secret: true` and reports every env override or skipped env entry with its source.
- `status --json` never exposes env values.
- A package can declare an env conflict with `policy: "error"`:

```json
"conflictsWithEnv": [
  {
    "name": "ANTHROPIC_API_KEY",
    "policy": "error",
    "reason": "Only one API key source should be active."
  }
]
```

Supported conflict policies:

- `override` default;
- `error`.

## 6. Patch package schema

Patch packages use the common package envelope and preserve the V1.5 Bun graph-aware repack target model inside a patch-specific section.

```json
{
  "schemaVersion": 1,
  "kind": "patch",
  "id": "fable-fallback",
  "label": "Fable fallback visibility",
  "description": "Shows Fable fallback events in resumed history and /resume.",
  "patch": {
    "engine": "bun_graph_repack",
    "targets": [
      {
        "sourceIdentity": {
          "claudeVersion": "2.1.199",
          "versionOutput": "2.1.199 (Claude Code)",
          "sha256": "e3cb61abc8a2ec7b98976cee1ffdde5a3fa755c9990bc8d688cd89290e0dcec0",
          "sizeBytes": 232155536,
          "platform": "darwin",
          "arch": "arm64"
        },
        "requiredEngine": "bun_graph_repack",
        "requiredBinaryFormat": "bun_standalone_macho64",
        "modules": []
      }
    ]
  },
  "risk": {
    "level": "medium"
  }
}
```

Patch-specific rules:

- `patch.engine` is initially `bun_graph_repack`.
- Patch targets require exact source identity.
- Patch targets preserve V1.5 module-coordinate operations, package-local payloads, assertions, and manual-smoke metadata.
- Patch package validation and build remain fail-closed.
- Patch invalidity is not skipped at build time.

## 7. Active launch profile config

The clean V3 config shape is:

```json
{
  "schemaVersion": 1,
  "activeProfile": "default",
  "profiles": {
    "default": {
      "prompt": "research",
      "patches": ["fable-fallback", "reminder-suppression"],
      "options": ["local-proxy", "dangerous-permissions"]
    }
  },
  "installMode": "shim",
  "activePatchSet": "...",
  "officialClaudePath": "..."
}
```

Rules:

- V3 persists exactly one profile named `default`. Additional profile keys are invalid in clean V3 config.
- `activeProfile` exists only to identify that `default` profile for the existing launch-profile machinery; it is not a multi-profile feature.
- `prompt` is one prompt id or `null`.
- `patches` is an ordered list of patch ids.
- `options` is an ordered list of option ids.
- Option order is semantically meaningful.
- `activePatchSet` remains build/install state, not package source.
- `officialClaudePath` is durable source-discovery state recorded by install/discovery flows.

## 8. Shared official Claude source discovery

Shim, status, build, fallback, and install must use one shared source-discovery implementation.

Discovery order:

1. durable config/install source path such as `officialClaudePath`;
2. environment discovery candidate such as `CLAUDE_MONKEY_SOURCE`;
3. PATH lookup for `claude`, excluding ClaudeMonkey's own shim path to avoid recursion.

The environment value is intentionally below durable config state in V3. It is a discovery candidate, not an absolute override of an already recorded official source. Install records the discovered official Claude path durably. The shared discovery function must reject paths that resolve to ClaudeMonkey's shim, `~/.claude-monkey/current`, or any path that would recurse into the managed launcher. No command should reimplement its own source-discovery rules.

## 9. Shim merge semantics

The shim applies the active launch profile deterministically.

Launch flow:

```text
1. user argv enters shim
2. shim loads active profile
3. shim starts from user argv
4. if active prompt exists and user did not pass any prompt flag, prepend prompt flag
5. apply enabled option packages in profile order:
   - skip option argv entries whose declared conflict is present in user argv
   - skip exact duplicate argv entries
   - merge env subject to section 5 process-env and conflict rules; later option package wins over earlier option packages unless conflict policy is error
6. choose target Claude binary
7. exec target Claude with final argv/env
```

Explicit user argv always wins.

Management invocations skip both prompt and option injection by default. Option packages may not override this in V3.

Baseline management tokens:

```text
--help
-h
--version
update
upgrade
doctor
auth
mcp
plugin
plugins
install
```

Management classification rules:

- Inspect only the first top-level argv token before any `--` separator.
- Management skip applies only when that first token exactly matches a management token.
- Tokens after `--` are user payload and must never classify the invocation as management.
- Prompt text such as `claude -p "update"` must not count as a management command.

Forbidden prompt-channel argv forms for option manifests:

- arg equals one of the protected prompt flags;
- arg starts with `<protected-flag>=`;
- if an arg equals a protected prompt flag, the following value is part of the invalid declaration.

Option manifests containing forbidden prompt-channel argv are invalid. They are not merely skipped.

If `~/.claude-monkey/current` exists, the shim launches it. If `current` is missing, the shim falls back to the discovered official Claude source. Status must clearly report that no patched build is active; patches must not be represented as active in that state. Prompt and option injection still apply through the shim.

Missing or invalid active prompt/option packages are skipped with warnings. They do not block launch. Patch invalidity remains build/compatibility-gated.

## 10. CLI command surface

V3 uses kind-specific commands rather than generic package-kind commands.

Listing:

```bash
claude-monkey list-patches --json
claude-monkey list-prompts --json
claude-monkey list-options --json
```

Mutation:

```bash
claude-monkey enable-patch <id> --json
claude-monkey disable-patch <id> --json

claude-monkey set-prompt <id> --json
claude-monkey clear-prompt --json

claude-monkey enable-option <id> --json
claude-monkey enable-option <id> --confirm --json
claude-monkey disable-option <id> --json
```

Option ordering:

- `enable-option` appends the option id to the end of the active profile's ordered option list.
- Disabling and re-enabling an option moves it to the end.
- V3 does not require menu reorder controls. If explicit reordering is added later, it must use the same ordered config list and launch-merge core.

Patch ordering:

- `enable-patch` appends the patch id to the end of the active profile's ordered patch list.
- Patch build planning remains responsible for deterministic conflict/range handling. The menu must not infer patch application semantics from visual order.

High-risk option enablement:

- If an option package has `risk.requiresConfirmation: true`, `enable-option <id> --json` returns `ok: false` with `error.code: "confirmation_required"`.
- `enable-option <id> --confirm --json` enables it.
- The menu shows a confirmation dialog before calling the confirmed command.

Launch preview:

```bash
claude-monkey launch-preview --json -- <argv...>
```

Launch preview computes shim behavior without launching Claude. It returns:

- target Claude path;
- final argv after prompt/option merge;
- env additions with secrets redacted;
- skipped prompt/option packages with reasons;
- warnings/errors from merge.

Launch preview is CLI/test/debug surface only. It is not a normal menu item.

List and status commands use stable unwrapped JSON contracts because they are state documents. Mutating commands use the common result envelope below.

All mutating JSON commands return a common envelope:

```json
{
  "schemaVersion": 1,
  "ok": true,
  "status": "ok",
  "summary": "...",
  "error": null,
  "warnings": []
}
```

Failure envelope:

```json
{
  "schemaVersion": 1,
  "ok": false,
  "status": "error",
  "summary": "...",
  "error": {
    "message": "...",
    "code": "confirmation_required"
  },
  "warnings": []
}
```

## 11. List JSON contracts

Each list command returns package records with validation, compatibility, and risk summary.

Example:

```json
{
  "schemaVersion": 1,
  "options": [
    {
      "id": "dangerous-permissions",
      "label": "Dangerous permissions",
      "kind": "option",
      "enabled": true,
      "valid": true,
      "compatibilityStatus": "compatible",
      "riskLevel": "high",
      "errors": []
    }
  ]
}
```

The top-level key is kind-specific: `patches`, `prompts`, or `options`.

## 12. Compatibility model

V3 uses two compatibility levels.

Package-level compatibility is optional for all kinds:

```json
"compatibility": {
  "claudeVersions": ["2.1.199"],
  "platforms": ["darwin"],
  "arches": ["arm64"]
}
```

Patch target source identity is required for patch targets:

```json
"sourceIdentity": {
  "claudeVersion": "2.1.199",
  "versionOutput": "2.1.199 (Claude Code)",
  "sha256": "...",
  "sizeBytes": 232155536,
  "platform": "darwin",
  "arch": "arm64"
}
```

Compatibility status vocabulary:

```text
compatible
unconstrained
version_mismatch
platform_mismatch
arch_mismatch
source_sha_mismatch
source_size_mismatch
graph_inspection_failed
module_identity_mismatch
operation_resolution_failed
patch_conflict
unknown
```

`unconstrained` means no package-level compatibility was declared and no exact target is required for that package kind.

Patch packages normally become `compatible` only when a target matches exact source identity and module/operation validation passes.

Compatibility dimensions:

- `manifestCompatibilityStatus`: coarse package-level compatibility from optional package `compatibility`.
- `sourceIdentityStatus`: exact source version/SHA/size/platform/arch comparison where a patch target requires it.
- `lastBuildCompatibilityStatus`: compatibility recorded in the active build report.
- `liveValidationStatus`: fresh read-only graph/module/operation validation if status actually performed it; otherwise `unknown`.

`status --json` may inspect current source and validate compatibility, but it must not build or mutate state. It must not imply fresh graph/module validation unless that validation actually ran. When no fresh validation ran, status should expose `lastBuildCompatibilityStatus` and `sourceIdentityStatus` rather than greenwashing with a generic `compatible`. Build/repack only happens through an explicit build/rebuild command.

Aggregate compatibility rule:

- `compatibilityStatus` is a summary for display, not a substitute for the specific dimensions.
- Rebuild decisions are driven by desired patch ids, patch manifest digests, source identity comparison, and the active build report.
- `liveValidationStatus: "unknown"` alone does not require rebuild and must not be folded into a false `compatible`; it means no fresh live graph/module validation was performed in that status call.
- If source identity and last build report match the desired patch state, and no validation errors are known, aggregate `compatibilityStatus` may be `compatible` even when `liveValidationStatus` is `unknown`, provided the status payload exposes the unknown dimension explicitly.

## 13. Status JSON

V3 `status --json` includes active launch-profile state, source identity, compatibility summary, and high-risk warnings.

```json
{
  "schemaVersion": 1,
  "status": "ok",
  "activeProfile": "default",

  "activePrompt": "research",
  "desiredPatchIds": ["fable-fallback"],
  "builtPatchIds": ["fable-fallback"],
  "activePatchIds": ["fable-fallback"],
  "patchedBuildActive": true,
  "targetClaudeKind": "patched",
  "activeOptionIds": ["dangerous-permissions"],

  "highRiskOptions": [
    {
      "id": "dangerous-permissions",
      "label": "Dangerous permissions",
      "warning": "Dangerous permissions enabled"
    }
  ],

  "sourceClaudeVersion": "2.1.199",
  "sourceClaudePath": "/Users/MAC/.local/share/claude/versions/2.1.199",
  "sourceSha256": "e3cb61abc8a2ec7b98976cee1ffdde5a3fa755c9990bc8d688cd89290e0dcec0",

  "compatibilityStatus": "compatible",
  "manifestCompatibilityStatus": "compatible",
  "sourceIdentityStatus": "compatible",
  "lastBuildCompatibilityStatus": "compatible",
  "liveValidationStatus": "unknown",
  "compatibilityWarnings": [],

  "rebuildRequired": false,
  "latestBuildReportPath": "...",
  "lastError": null
}
```

Status precedence:

```text
error
rebuild_required
warning
unknown
ok
```

High-risk options produce warnings, not errors. Invalid skipped prompt/options produce warnings, not launch blockers. Patch/source incompatibility may produce `rebuild_required` or `error`, depending on severity. Missing, non-executable, or stale `current` with desired patches must be `rebuild_required` or `warning`, never plain `ok`.

Patch identity fields:

- `desiredPatchIds`: patch ids currently selected in the active launch profile.
- `builtPatchIds`: patch ids recorded in the active/latest build report, if any.
- `activePatchIds`: patch ids actually active for the target Claude binary that the shim would launch. This must be empty when `targetClaudeKind` is `official_fallback`.
- `patchedBuildActive`: true only when `current` resolves to an active patched build and matches the active build/report state.
- `targetClaudeKind`: `patched`, `official_fallback`, or `official_management`.

## 14. Rebuild-required semantics

Rebuild is required when:

- desired patch ids differ from build report patch ids;
- a patch package manifest digest differs from the build report digest;
- current source identity differs from build report source identity;
- source identity or last-build compatibility for desired patch packages is not compatible.

Rebuild is not required when:

- active prompt changes;
- active option changes;
- prompt package manifest changes;
- option package manifest changes.

Prompt and option changes apply on the next managed Claude launch through the shim.

## 15. Build report evolution

V3 build reports expose UI-facing summary fields without making the UI parse Bun internals.

```json
{
  "schemaVersion": 3,
  "packageManifestDigests": {
    "fable-fallback": "sha256..."
  },
  "sourceIdentity": {
    "claudeVersion": "2.1.199",
    "versionOutput": "2.1.199 (Claude Code)",
    "sha256": "...",
    "sizeBytes": 232155536,
    "platform": "darwin",
    "arch": "arm64"
  },
  "buildInputSnapshot": {
    "patches": ["fable-fallback"],
    "promptAtBuildTime": "research",
    "optionsAtBuildTime": ["dangerous-permissions"]
  },
  "compatibility": {
    "status": "compatible",
    "warnings": []
  },
  "engine": "bun_graph_repack",
  "changedModules": []
}
```

Report rules:

- report records build inputs and launch-profile context at build time;
- only `buildInputSnapshot.patches` and patch package manifest digests participate in rebuild drift; prompt/options are historical context only;
- patch package manifest digests support drift detection;
- UI reads compatibility summary fields, not Bun graph internals;
- detailed V1.5 module/repack evidence remains in the report for debugging and audit.

## 16. Menu bar integration

V3 menu baseline:

```text
ClaudeMonkey: <status>
Claude Code: <version>
Prompt: <id or none>
Options: <count active, warning if high-risk>
Patches: <desired/active summary>

Prompts
  None
  <prompt packages>

Patches
  <patch packages>

Command Line Options
  <option packages>

Rebuild / Apply...
Install/Uninstall shim...
Open report/logs/state
Quit
```

Menu behavior:

V3 inherits V2 JSON contracts for build and shim install/uninstall. V3 adds option commands and expanded package/status payloads; it does not redesign install/build command envelopes.

- prompt selection calls `set-prompt <id> --json` and applies next launch;
- option toggle calls `enable-option` / `disable-option` and applies next launch;
- high-risk option enablement uses confirmation before `--confirm`;
- patch toggle calls `enable-patch` / `disable-patch` and marks rebuild required;
- rebuild/apply calls the existing build path;
- top status includes high-risk and compatibility warnings.

Menu refresh cadence:

- refresh when opened/clicked;
- refresh every 10 minutes;
- refresh after mutating commands;
- no manual Refresh item.

V3 has no daemon/watch process. Status/menu refresh is enough for this version.

## 17. Examples

### 17.1 Dangerous permissions option package

Local Claude evidence checked on 2026-07-02 from `claude --help` for Claude Code `2.1.199`:

- `--dangerously-skip-permissions`: bypasses all permission checks;
- `--allow-dangerously-skip-permissions`: enables bypassing all permission checks as an option without enabling it by default;
- `--permission-mode <mode>` includes `bypassPermissions` among the choices.

Example local package:

```json
{
  "schemaVersion": 1,
  "kind": "option",
  "id": "dangerous-permissions",
  "label": "Dangerous permissions",
  "description": "Launch Claude Code with permission checks bypassed.",
  "compatibility": {
    "claudeVersions": ["2.1.199"],
    "platforms": ["darwin"],
    "arches": ["arm64"]
  },
  "option": {
    "argv": ["--dangerously-skip-permissions"],
    "env": {},
    "conflictsWithArgv": [
      "--dangerously-skip-permissions",
      "--allow-dangerously-skip-permissions",
      "--permission-mode"
    ],
    "conflictsWithOptions": [],
    "conflictsWithEnv": []
  },
  "risk": {
    "level": "high",
    "requiresConfirmation": true,
    "statusWarning": "Dangerous permissions enabled"
  }
}
```

This is only an example local package. It is not a built-in registry entry, not a repo-level package, and not shipped through any remote/community source.

### 17.2 Local proxy option package

This example demonstrates env configuration and secret redaction. It does not assert exact Claude proxy environment variable semantics unless separately verified.

```json
{
  "schemaVersion": 1,
  "kind": "option",
  "id": "local-proxy",
  "label": "Local API proxy",
  "description": "Route Claude through a local API proxy using user-local environment settings.",
  "option": {
    "argv": [],
    "env": {
      "ANTHROPIC_BASE_URL": {
        "value": "http://127.0.0.1:8080",
        "secret": false,
        "allowOverrideProcessEnv": false
      },
      "ANTHROPIC_API_KEY": {
        "valueFromEnv": "CLAUDE_MONKEY_PROXY_API_KEY",
        "secret": true,
        "allowOverrideProcessEnv": false
      }
    },
    "conflictsWithArgv": [],
    "conflictsWithOptions": [],
    "conflictsWithEnv": [
      {
        "name": "ANTHROPIC_API_KEY",
        "policy": "error",
        "reason": "Only one API key source should be active."
      }
    ]
  },
  "risk": {
    "level": "medium"
  }
}
```

## 18. Verification requirements for implementation

V3 implementation should include tests for:

- package discovery and validation across patches, prompts, and options;
- common manifest envelope validation;
- prompt package loading and prompt flag injection;
- option argv/env merge;
- explicit user argv override;
- forbidden prompt flags in option packages;
- option ordering and env override/error policy;
- high-risk enable confirmation;
- launch preview redaction;
- shared official Claude source discovery and shim recursion avoidance;
- missing-current fallback to official Claude;
- management-command injection skipping;
- status compatibility summaries;
- list JSON contracts;
- menu state parsing for prompts, patches, options, warnings, and compatibility;
- rebuild-required semantics;
- build report schema v3 summary fields.

## 19. Non-goals for V3

V3 does not include:

- remote or community package marketplace;
- executable package hooks;
- repo-level package source, registry, or discovery model;
- multiple-profile management UX;
- menu Launch Preview item;
- manual menu Refresh item;
- background daemon/watch process;
- UI parsing of Bun graph internals;
- in-place mutation of the live Claude install in the normal path.

## 20. Open implementation notes

These are implementation notes, not open product decisions:

- The implementation should keep package parsing, launch merge, source discovery, status derivation, and menu parsing as separate testable units.
- The shim should call the same launch-merge core used by `launch-preview` so preview and launch cannot drift.
- Status should be useful even when packages are invalid; validation errors should be data, not terminal crashes.
- All command output intended for the menu should use stable JSON contracts. Mutating commands use envelopes; list/status commands use documented unwrapped state payloads.
