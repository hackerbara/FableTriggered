# Self-contained local Claude Code reminder-suppression patch

Date: 2026-07-02

This document describes a local monkey patch for a **copied** Claude Code executable that suppresses a narrow set of recurring, model-visible reminder attachments.

It is designed for people who want to reduce noisy harness nudges such as task/todo reminders and token-budget reminders, while leaving safety-, permission-, file-state-, and hook-related reminders intact.

Tested against:

- Claude Code version: `2.1.198`
- Original executable SHA-256: `ab6f7ee109816ede414f7c285446633f805b623aa609f425609a64266451d61e`
- Original executable size: `229328464` bytes
- Platform tested: macOS arm64 standalone Claude Code executable

Do **not** assume this applies to any other Claude Code version. Re-derive the string seams on the target machine.

---

## What this patch suppresses

The patch no-ops the renderers for these attachment/reminder types:

```text
todo_reminder
task_reminder
tool_search_usage_reminder
token_usage
total_tokens_reminder
budget_usd
output_token_usage
```

In Claude Code `2.1.198`, these reminders are converted into model-visible meta user messages by attachment renderers. The patch changes those renderers to return `[]`, so the attachment contributes no message to the next model request.

This patch intentionally does **not** suppress reminders such as:

```text
edited_text_file
file_modified_by_user_or_linter
hook_blocking_error
hook_additional_context
permission / safety / trust-boundary reminders
file truncation or empty-file warnings
plan mode enforcement
```

Those can prevent data loss, preserve user edits, or enforce important workflow boundaries. Patch them only if you have separately inspected and accepted the risk.

---

## Important warning

This is unsupported binary patching.

Safe workflow:

1. Discover the installed Claude executable.
2. Copy it to a separate patch directory.
3. Patch the copy only.
4. Ad-hoc sign the copy on macOS.
5. Smoke test the copy.
6. Run the patched copy explicitly, or install it with a reversible alias/symlink only after testing.

Do **not** patch the live executable in place unless you have a backup and intentionally accept the risk.

---

## What is machine-specific?

Nothing about the original machine is required except the Claude Code version and executable shape.

You must discover these locally:

| Variable | Meaning | Example discovery command |
|---|---|---|
| `CLAUDE_BIN` | the executable used by `claude` | `command -v claude`, then `realpath`/`readlink` |
| `PATCH_DIR` | writable scratch directory for the copy/scripts | any local directory |
| `TARGET_VERSION` | Claude Code version | `claude --version` |
| `TARGET_SHA256` | executable hash before patching | `shasum -a 256 "$CLAUDE_BIN"` |

The scripts below derive seams from unique byte markers rather than hardcoded offsets.

---

## Evidence and seams in 2.1.198

In Claude Code `2.1.198`, the relevant model-context attachment renderer has two useful regions.

### Dynamic attachment switch

A switch near the marker:

```js
if(e.type in f_c)return f_c[e.type](e);switch(e.type)
```

contains cases including:

```text
todo_reminder
task_reminder
tool_search_usage_reminder
agent_listing_delta
mcp_instructions_delta
memory_update
```

The patch no-ops only:

```text
todo_reminder
task_reminder
tool_search_usage_reminder
```

### Direct `f_c` renderer map

A map near the marker:

```js
f_c={directory:
```

contains direct renderers including:

```text
token_usage
total_tokens_reminder
budget_usd
output_token_usage
hook_blocking_error
hook_additional_context
```

The patch no-ops only:

```text
token_usage
total_tokens_reminder
budget_usd
output_token_usage
```

Observed offsets in the tested `2.1.198` executable were:

```text
219788577  todo_reminder
219789181  task_reminder
219789806  tool_search_usage_reminder
219824497  token_usage
219824606  total_tokens_reminder
219824670  budget_usd
219824780  output_token_usage
```

These offsets are **evidence only**. Do not hardcode them for another build.

---

## Step 1: prepare a patch directory and copied binary

```bash
set -euo pipefail

export PATCH_DIR="$HOME/claude-reminder-suppression-patch"
mkdir -p "$PATCH_DIR"

export CLAUDE_BIN="$(python3 - <<'PY'
import os, shutil
p = shutil.which('claude')
if not p:
    raise SystemExit('claude not found on PATH')
print(os.path.realpath(p))
PY
)"

printf 'CLAUDE_BIN=%s\n' "$CLAUDE_BIN"
"$CLAUDE_BIN" --version
shasum -a 256 "$CLAUDE_BIN"

cp -p "$CLAUDE_BIN" "$PATCH_DIR/claude-reminders-muted"
chmod 755 "$PATCH_DIR/claude-reminders-muted"
```

---

## Step 2: create the verifier

This verifier should fail against an unpatched binary and pass after patching.

```bash
cat > "$PATCH_DIR/verify-reminder-patch.py" <<'PY'
#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    print('usage: verify-reminder-patch.py /path/to/claude-copy', file=sys.stderr)
    sys.exit(2)

path = Path(sys.argv[1])
b = path.read_bytes()

removed_patterns = {
    'todo_reminder old case': b'case"todo_reminder":{let n=e.content.map',
    'task_reminder old case': b'case"task_reminder":{if(!iv())return[];let n=e.content.map',
    'tool_search_usage_reminder old case': b'case"tool_search_usage_reminder":{let n=e.undiscoveredToolNames',
    'token_usage old renderer': b'token_usage:(e)=>[In({content:_v(`Token usage:',
    'total_tokens_reminder old renderer': b'total_tokens_reminder:(e)=>[In({content:_v(e.text),isMeta:!0})]',
    'budget_usd old renderer': b'budget_usd:(e)=>[In({content:_v(`USD budget:',
    'output_token_usage old renderer': b'output_token_usage:(e)=>{let t=e.budget!==null?',
}
expected_noops = {
    'todo_reminder no-op': b'case"todo_reminder":return[];',
    'task_reminder no-op': b'case"task_reminder":return[];',
    'tool_search_usage_reminder no-op': b'case"tool_search_usage_reminder":return[];',
    'token_usage no-op': b'token_usage:(e)=>[]',
    'total_tokens_reminder no-op': b'total_tokens_reminder:(e)=>[]',
    'budget_usd no-op': b'budget_usd:(e)=>[]',
    'output_token_usage no-op': b'output_token_usage:(e)=>[]',
}

failures = []
for name, pat in removed_patterns.items():
    off = b.find(pat)
    if off >= 0:
        failures.append(f'old pattern still present: {name} @ {off}')
for name, pat in expected_noops.items():
    off = b.find(pat)
    if off < 0:
        failures.append(f'no-op pattern missing: {name}')

if failures:
    print('FAIL reminder patch verification')
    for item in failures:
        print(' -', item)
    sys.exit(1)

print('PASS reminder patch verification')
for name, pat in expected_noops.items():
    print(f' - {name} @ {b.find(pat)}')
PY
chmod +x "$PATCH_DIR/verify-reminder-patch.py"
```

Confirm it fails before patching:

```bash
python3 "$PATCH_DIR/verify-reminder-patch.py" "$PATCH_DIR/claude-reminders-muted" || true
```

Expected: `FAIL reminder patch verification` with old patterns still present.

---

## Step 3: create and run the patcher

```bash
cat > "$PATCH_DIR/patch-reminder-renderers.py" <<'PY'
#!/usr/bin/env python3
from pathlib import Path
import hashlib, os, shutil, sys

if len(sys.argv) != 3:
    print('usage: patch-reminder-renderers.py /path/to/source-claude /path/to/output-copy', file=sys.stderr)
    sys.exit(2)

SRC = Path(sys.argv[1])
OUT = Path(sys.argv[2])

PATCHES = [
    # Dynamic attachment switch cases. Replace only this case body; leave the next case label intact.
    (b'case"todo_reminder":', b'case"task_reminder":', b'case"todo_reminder":return[];'),
    (b'case"task_reminder":', b'case"tool_search_usage_reminder":', b'case"task_reminder":return[];'),
    (b'case"tool_search_usage_reminder":', b'case"relevant_memories":', b'case"tool_search_usage_reminder":return[];'),

    # Direct f_c renderer map entries. Replace property value up to the next property comma.
    (b'token_usage:(e)=>[In({content:_v(`Token usage:', b',total_tokens_reminder:', b'token_usage:(e)=>[]'),
    (b'total_tokens_reminder:(e)=>[In({content:_v(e.text),isMeta:!0})]', b',budget_usd:', b'total_tokens_reminder:(e)=>[]'),
    (b'budget_usd:(e)=>[In({content:_v(`USD budget:', b',output_token_usage:', b'budget_usd:(e)=>[]'),
    (b'output_token_usage:(e)=>{let t=e.budget!==null?', b',hook_blocking_error:', b'output_token_usage:(e)=>[]'),
]

def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def unique_find(data: bytes, marker: bytes) -> int:
    first = data.find(marker)
    if first < 0:
        raise SystemExit(f'marker not found: {marker[:100]!r}')
    second = data.find(marker, first + 1)
    if second >= 0:
        raise SystemExit(f'marker not unique: {marker[:100]!r} at {first} and {second}')
    return first

def patch_between(data: bytes, start_marker: bytes, end_marker: bytes, replacement: bytes):
    start = unique_find(data, start_marker)
    end = data.find(end_marker, start + len(start_marker))
    if end < 0:
        raise SystemExit(f'end marker not found after {start}: {end_marker[:100]!r}')
    segment = data[start:end]
    if len(replacement) > len(segment):
        raise SystemExit(f'replacement too long: {len(replacement)} > {len(segment)} for {start_marker[:80]!r}')
    padded = replacement + (b' ' * (len(segment) - len(replacement)))
    return data[:start] + padded + data[end:], start, len(segment), len(replacement)

def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SRC, OUT)
    data = OUT.read_bytes()
    original_hash = sha256_bytes(data)
    rows = []
    for start_marker, end_marker, replacement in PATCHES:
        data, offset, old_len, new_len = patch_between(data, start_marker, end_marker, replacement)
        rows.append((offset, old_len, new_len, replacement.decode('utf-8', 'replace')))
    OUT.write_bytes(data)
    os.chmod(OUT, 0o755)
    patched_hash = sha256_file(OUT)
    notes = OUT.with_suffix('.patch-notes.txt')
    notes.write_text('\n'.join([
        f'source={SRC}',
        f'output={OUT}',
        f'original_sha256={original_hash}',
        f'patched_sha256_pre_sign={patched_hash}',
        'patches:',
        *[f'- offset={o} old_len={ol} replacement_len={nl} replacement={r}' for o, ol, nl, r in rows],
        '',
    ]))
    print(notes.read_text())

if __name__ == '__main__':
    main()
PY
chmod +x "$PATCH_DIR/patch-reminder-renderers.py"

python3 "$PATCH_DIR/patch-reminder-renderers.py" \
  "$CLAUDE_BIN" \
  "$PATCH_DIR/claude-reminders-muted"
```

---

## Step 4: verify the patched bytes

```bash
python3 "$PATCH_DIR/verify-reminder-patch.py" "$PATCH_DIR/claude-reminders-muted"
```

Expected output includes:

```text
PASS reminder patch verification
```

---

## Step 5: sign on macOS

Any byte modification invalidates the original signature. On macOS, ad-hoc sign the copied binary:

```bash
codesign --force --sign - "$PATCH_DIR/claude-reminders-muted"
codesign --verify --deep --strict --verbose=4 "$PATCH_DIR/claude-reminders-muted"
SIGNED_SHA=$(shasum -a 256 "$PATCH_DIR/claude-reminders-muted" | awk '{print $1}')
printf 'signed_sha256=%s\n' "$SIGNED_SHA" >> "$PATCH_DIR/claude-reminders-muted.patch-notes.txt"
```

On non-macOS systems, skip `codesign`.

---

## Step 6: smoke test without launching an uncontrolled session

```bash
"$PATCH_DIR/claude-reminders-muted" --version
"$PATCH_DIR/claude-reminders-muted" --help > "$PATCH_DIR/help.txt"
head -40 "$PATCH_DIR/help.txt"
```

Known-good smoke output from the tested copy:

```text
2.1.198 (Claude Code)
Usage: claude [options] [command] [prompt]
```

Also confirm the official executable is unchanged:

```bash
shasum -a 256 "$CLAUDE_BIN" "$PATCH_DIR/claude-reminders-muted"
```

---

## Step 7: run the copied binary explicitly

For the first real trial, run the copied binary directly:

```bash
"$PATCH_DIR/claude-reminders-muted"
```

If it behaves well, create a reversible alias instead of overwriting the official Claude install:

```bash
alias claude-muted="$PATCH_DIR/claude-reminders-muted"
```

You can add that alias to your shell profile after you are comfortable with the patched copy.

---

## Installing over your normal `claude` command, if you accept the risk

Safer options, in order:

1. Keep using the explicit copied binary path.
2. Add a shell alias such as `claude-muted`.
3. Put a wrapper script named `claude` earlier on your `PATH` that execs the patched copy.
4. Replace a symlink you control.

Avoid overwriting the official versioned binary. Claude Code updates may replace it, and a bad patch could leave your normal CLI unusable.

Example wrapper directory approach:

```bash
mkdir -p "$HOME/.local/claude-patched-bin"
cat > "$HOME/.local/claude-patched-bin/claude" <<EOF
#!/bin/sh
exec "$PATCH_DIR/claude-reminders-muted" "\$@"
EOF
chmod +x "$HOME/.local/claude-patched-bin/claude"

# Then prepend this directory to PATH in your shell profile:
# export PATH="$HOME/.local/claude-patched-bin:$PATH"
```

Confirm which binary is active:

```bash
command -v claude
claude --version
```

---

## Expected limits and risks

- This only no-ops the selected renderer paths. Other reminders still exist.
- Some prompt guidance lives in tool descriptions or system prompt sections rather than these attachment renderers.
- Claude Code updates will likely move or rewrite these seams.
- A copied binary may need re-signing after every patch.
- Suppressing task/todo nudges may reduce workflow guidance for agents that benefit from explicit task tracking.
- Suppressing token/budget reminders may make long-context or cost behavior less visible to the model.

If a marker is missing or not unique, stop and re-inspect the binary rather than weakening the patcher.

---

## Public references used for discovery

- Piebald Claude Code system prompt extraction inventory: <https://github.com/Piebald-AI/claude-code-system-prompts>
- Piebald task reminder fragment: <https://github.com/Piebald-AI/claude-code-system-prompts/blob/main/system-prompts/system-reminder-task-tools-reminder.md>
- Claude Code hooks docs, including `additionalContext` delivery as system reminders: <https://code.claude.com/docs/en/hooks>
- Anthropic issue discussing task-tool reminder injection and false-positive prompt-injection reports: <https://github.com/anthropics/claude-code/issues/52018>
- Anthropic issue discussing `tengu_heron_brook` / bootstrap prompt-section injection concerns: <https://github.com/anthropics/claude-code/issues/62061>
