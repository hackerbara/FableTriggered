# Self-contained local Claude 2.1.198 Fable fallback visibility patch plan

Date: 2026-07-02

This is a self-contained plan for locally patching a **copied** Claude Code executable so Fable fallback events become visible in the terminal UI.

The patch has two visible effects:

1. **Resumed transcript history**: an on-chain assistant `fallback` content block renders as a warning-style `model_refusal_fallback` banner instead of disappearing.
2. **`/resume` session picker**: sessions whose JSONL contains a Fable fallback marker show a yellow `Fable classifier triggered` metadata segment.

This document is meant to be pasted as a single file to another GPT/agent. It does **not** assume access to any existing local project, helper scripts, or prior artifacts. All scripts needed to reproduce the patch are included inline below.

---

## Important warning

This is an unsupported local monkey patch of a Claude Code executable.

Do not distribute a modified Claude binary. Do not patch other people’s machines. Do not assume these byte offsets apply to any version except the exact version you verify locally.

The safe workflow is:

1. Discover the installed Claude executable.
2. Copy the executable to a separate local patch directory.
3. Patch the copy only.
4. Ad-hoc sign the copy on macOS.
5. Smoke test the copy.
6. Optionally make your shell’s `claude` command point to the patched copy via a reversible symlink or alias.

Avoid overwriting the official Claude version file unless you have a backup and intentionally accept the risk.

---

## What is machine-specific?

There is nothing special about the original machine except:

- it was macOS arm64;
- Claude Code was installed as a standalone Bun/Mach-O executable;
- macOS required re-signing after byte modification;
- the tested version was exactly Claude Code `2.1.198`;
- the official executable was reachable from the user’s `claude` command.

On another machine, the user must set/discover:

| Variable | Meaning | How to discover |
|---|---|---|
| `CLAUDE_BIN` | the executable used by `claude` | `command -v claude` then `readlink`/`realpath` |
| `PATCH_DIR` | scratch directory for copied binaries/scripts | choose any writable directory |
| `TARGET_VERSION` | expected Claude Code version | `claude --version` |
| `TARGET_SESSION_JSONL` | optional transcript used for validation | find a local Claude session JSONL containing fallback records |

Known-good original test environment:

- Claude Code version: `2.1.198`
- Official binary SHA-256: `ab6f7ee109816ede414f7c285446633f805b623aa609f425609a64266451d61e`
- Official binary size: `229328464` bytes
- Platform: macOS arm64

If the installed Claude version or SHA differs, use the seam-discovery steps below and do not blindly trust the byte offsets.

---

## Conceptual patch overview

### A. Resumed-history fallback banner

Claude Code 2.1.198 contains these relevant minified render functions:

- `gCm`: top-level message renderer.
- `SCm`: assistant content-block renderer.
- `s3(e)`: fallback-block predicate, equivalent to `e.type === "fallback"`.
- `mEl`: system message renderer.

The relevant behavior:

- `gCm` switches on top-level message type.
- For top-level `assistant`, it maps `message.content` through `SCm`.
- `SCm` explicitly drops fallback blocks with `if(s3(n))return null`.
- For top-level `system`, `gCm` calls `mEl`.
- `mEl` already has a renderer for `subtype === "model_refusal_fallback"` that displays warning styling and the `/config` tip.

Patch idea:

- In `gCm`’s top-level `assistant` case, detect an assistant content block with `type === "fallback"`.
- If found, synthesize a top-level system-shaped object with `subtype: "model_refusal_fallback"`.
- Pass that synthesized object to `mEl`.
- Do not change the transcript JSONL or API state.

### B. `/resume` session picker marker

Claude Code 2.1.198 contains these relevant resume-list functions:

- `wpf(e,t)`: enriches lightweight session-log entries for `/resume`.
- `net(e)`: formats metadata like `3m ago · main · 2.8MB`.

Patch idea:

- During lightweight resume-log enrichment, scan the session JSONL for evidence of a Fable fallback.
- Set `fableClassifierTriggered: true` on the session-log object when the JSONL contains:
  - `claude-fable-5`, and
  - either `"type":"fallback"` or `model_refusal_fallback`.
- In `net(e)`, append yellow text when `e.fableClassifierTriggered` is true:
  - `Fable classifier triggered`

This intentionally catches both:

- an on-chain assistant `fallback` block, and
- an off-chain `system/model_refusal_fallback` banner record.

---

## Create a fresh patch workspace

Choose a local scratch directory. Example:

```bash
export PATCH_DIR="$HOME/claude-fable-patch"
mkdir -p "$PATCH_DIR"/artifacts "$PATCH_DIR"/scripts
cd "$PATCH_DIR"
```

Discover the current Claude executable:

```bash
export CLAUDE_CMD="$(command -v claude)"
python3 - <<'PY'
import os
print(os.path.realpath(os.environ['CLAUDE_CMD']))
PY
```

Set `CLAUDE_BIN` to the real executable path:

```bash
export CLAUDE_BIN="$(python3 - <<'PY'
import os
print(os.path.realpath(os.environ['CLAUDE_CMD']))
PY
)"

echo "$CLAUDE_BIN"
"$CLAUDE_BIN" --version
file "$CLAUDE_BIN"
wc -c "$CLAUDE_BIN"
shasum -a 256 "$CLAUDE_BIN"
```

Expected for the known-good target:

```text
2.1.198 (Claude Code)
```

If this is not `2.1.198`, stop and re-derive the patch for the installed version.

Copy the binary:

```bash
cp -p "$CLAUDE_BIN" "$PATCH_DIR/artifacts/claude-unpatched-copy"
chmod u+x "$PATCH_DIR/artifacts/claude-unpatched-copy"
"$PATCH_DIR/artifacts/claude-unpatched-copy" --version
```

---

## Seam-discovery script

Create a local seam-discovery script from this document:

```bash
cat > "$PATCH_DIR/scripts/discover-claude-fable-seams.py" <<'PY'
#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    print('usage: discover-claude-fable-seams.py <claude-binary>', file=sys.stderr)
    sys.exit(2)

p = Path(sys.argv[1])
data = p.read_bytes()
patterns = [
    b'function mEl',
    b'UX()&&n.subtype==="model_refusal_fallback"',
    b'function gCm',
    b'case"assistant":{let R;if(t[20]!==r.firstTextBlockUuidByMessageID',
    b'case"system"',
    b'function SCm',
    b'if(s3(n))return null',
    b'function s3(e){return e.type==="fallback"}',
    b'function net(e){let t=e.fileSize!==void 0?$a(e.fileSize):`${e.messageCount} messages`',
    b'async function wpf(e,t){if(!e.isLite||!e.fullPath)return e;',
    b'function jTa(e,t){return{type:"system",subtype:"model_refusal_fallback"',
]

print(f'binary={p}')
print(f'size={len(data)}')
for pat in patterns:
    offsets = []
    start = 0
    while True:
        i = data.find(pat, start)
        if i < 0:
            break
        offsets.append(i)
        start = i + 1
        if len(offsets) >= 10:
            break
    label = pat.decode('utf-8', 'replace')
    print(f'{offsets[0] if offsets else -1}\tcount={len(offsets)}\t{label}')
PY
chmod +x "$PATCH_DIR/scripts/discover-claude-fable-seams.py"
```

Run it:

```bash
"$PATCH_DIR/scripts/discover-claude-fable-seams.py" \
  "$PATCH_DIR/artifacts/claude-unpatched-copy"
```

Expected discovery result:

- Each core marker should be found in the binary.
- The start markers for the three edited regions should each be unique:
  - `case"assistant":{let R;if(t[20]!==r.firstTextBlockUuidByMessageID`
  - `function net(e){let t=e.fileSize!==void 0?$a(e.fileSize):\`${e.messageCount} messages\``
  - `async function wpf(e,t){if(!e.isLite||!e.fullPath)return e;`
- The patcher below derives replacement ranges from marker pairs:
  - assistant case start marker through the next `case"user":{`
  - `function net(e)` start marker through the next `function gte`
  - `async function wpf(e,t)` start marker through the next `async function kJe`

Do not proceed if markers are missing, duplicated unexpectedly, or if the surrounding code does not match the shape described in this document. The point is to re-find the local offsets from markers, not to trust published byte numbers.

---

## Static verifier script

Create a verifier that checks whether a binary contains the expected patch markers:

```bash
cat > "$PATCH_DIR/scripts/verify-claude-fable-patch.py" <<'PY'
#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    print('usage: verify-claude-fable-patch.py <claude-binary>', file=sys.stderr)
    sys.exit(2)

p = Path(sys.argv[1])
data = p.read_bytes()
checks = [
    (b'case"assistant":{let R=n.message.content?.find', 'assistant fallback render-time patch'),
    (b'triggered a model refusal fallback', 'assistant fallback synthesized banner text'),
    (b'fableClassifierTriggered', 'resume log boolean property'),
    (b'Fable classifier triggered', 'resume listing marker text'),
    (b'readFileSync(e.fullPath,"utf8")', 'resume lite-log full-file detector'),
]
missing = [(label, needle) for needle, label in checks if needle not in data]
if missing:
    print(f'FAIL {p}: missing {len(missing)} expected patch markers')
    for label, _ in missing:
        print(f'  - {label}')
    sys.exit(1)
print(f'PASS {p}: all expected patch markers present')
PY
chmod +x "$PATCH_DIR/scripts/verify-claude-fable-patch.py"
```

Run it against the unpatched copy first. It should fail:

```bash
set +e
"$PATCH_DIR/scripts/verify-claude-fable-patch.py" \
  "$PATCH_DIR/artifacts/claude-unpatched-copy"
echo "exit=$?"
set -e
```

Expected: `FAIL`, because the patch has not been applied yet.

---

## Actual JavaScript replacements

This section shows the actual JavaScript source fragments that the patcher installs into the bundled/minified executable. The Python patcher later in this document embeds these same replacements as strings and pads them to the original byte ranges.

These are version-specific to the local minified names in Claude Code 2.1.198. For another version, treat them as a working reference, not proof that the same variable names still apply.

### Replacement 1: `gCm` assistant case

This replacement detects a fallback content block before the normal assistant-content map. When present, it routes a synthesized system-shaped message through the existing `mEl` system fallback renderer.

```js
case"assistant":{let R=n.message.content?.find((O)=>O?.type==="fallback");
if(R){let w=R.from?.model??"original model",k=R.to?.model??"fallback model",
x=`${w} triggered a model refusal fallback. Switched to ${k}.`;
return Ab.jsx(mEl,{message:{type:"system",subtype:"model_refusal_fallback",direction:"retry",
content:x,level:"warning",trigger:"refusal",originalModel:w,fallbackModel:k,requestId:n.requestId,
apiRefusalCategory:R.apiRefusalCategory,apiRefusalExplanation:null,isMeta:!1,timestamp:n.timestamp,uuid:n.uuid},
addMargin:s,verbose:l,isTranscriptMode:h})}
let w=r.firstTextBlockUuidByMessageID.get(n.message.id),k=o??"100%",
x=n.message.content.map((O,M)=>Ab.jsx(SCm,{param:O,addMargin:s,tools:i,commands:a,verbose:l,
inProgressToolUseIDs:c,progressMessagesForMessage:u,shouldAnimate:d,shouldShowDot:p,width:f,
inProgressToolCallCount:c.size,isTranscriptMode:h,lookups:r,onOpenRateLimitOptions:g,
advisorModel:n.advisorModel,messageUuid:n.uuid,apiMessageId:S?void 0:n.message.id,
isFirstTextBlock:w===void 0||w===n.uuid},M));
return Ab.jsx(B,{flexDirection:"column",width:k,children:x})}
```

### Replacement 2: `net(e)` resume-list metadata formatter

This replacement keeps the usual time/branch/size metadata and appends an ANSI-yellow marker when `e.fableClassifierTriggered` is true.

```js
function net(e){let t=e.fileSize!==void 0?$a(e.fileSize):e.messageCount+" messages",
n=[Bz(e.modified,{style:"short"})];if(e.gitBranch)n.push(e.gitBranch);n.push(t);
if(e.tag)n.push("#"+e.tag);if(e.agentSetting)n.push("@"+e.agentSetting);
if(e.prNumber)n.push("#"+e.prNumber);
if(e.fableClassifierTriggered)n.push("\x1b[33mFable classifier triggered\x1b[39m");
return n.join(" · ")}
```

Byte-budget tradeoff: this compact formatter omits some rare metadata detail from the original formatter, notably the `bg` segment and PR repository prefix.

### Replacement 3: `wpf(e,t)` resume lite-log enrichment

This replacement scans the session JSONL during `/resume` lite-log enrichment and adds `fableClassifierTriggered` when it sees either an on-chain fallback marker or off-chain `model_refusal_fallback` record associated with `claude-fable-5`.

```js
async function wpf(e,t){if(!e.isLite||!e.fullPath)return e;
let n=await Nmc(e.fullPath,e.fileSize??0,t),b=!1;
try{let l=D$.readFileSync(e.fullPath,"utf8");
b=l.includes("claude-fable-5")&&(l.includes('"type":"fallback"')||l.includes("model_refusal_fallback"))}catch{}
let r=n.projectPath!==void 0&&Dg.dirname(e.fullPath)===t_(n.projectPath),
o=n.relocatedCwd??(r||e.projectPath===void 0?n.projectPath??e.projectPath:e.projectPath),
s={...e,isLite:!1,firstPrompt:n.firstPrompt,gitBranch:n.gitBranch,isSidechain:n.isSidechain,
teamName:n.teamName,sessionKind:n.sessionKind,customTitle:n.customTitle,aiTitle:n.aiTitle,
summary:n.summary,tag:n.tag,agentSetting:n.agentSetting,prNumber:n.prNumber,prUrl:n.prUrl,
prRepository:n.prRepository,projectPath:o,fableClassifierTriggered:b};
if(!s.firstPrompt&&!s.customTitle&&!s.aiTitle)s.firstPrompt="(session)";
if(s.isSidechain||s.teamName||s.sessionKind==="daemon"||s.sessionKind==="daemon-worker")return null;
let i=rgn.has(Tmc()??"");if(!i&&rgn.has(n.entrypoint??""))return null;
if(!i&&n.isLoopSession)return null;return s}
```

The full-file synchronous read is acceptable for a local proof, but a production-quality version should cache or index this flag.

---

## Patch script

Create the patcher from this document:

```bash
cat > "$PATCH_DIR/scripts/patch-claude-fable-visibility.py" <<'PY'
#!/usr/bin/env python3
"""Patch a copied Claude 2.1.198 binary with Fable fallback visibility spikes.

Effects:
1. Assistant fallback content blocks render via the existing system
   model_refusal_fallback banner renderer.
2. /resume list metadata marks sessions whose JSONL contains a Fable fallback
   marker, including off-chain system model_refusal_fallback records.

This script is intentionally marker-based and refuses to overwrite its input.
Run it against a copied binary, then ad-hoc sign the output on macOS.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
import sys

if len(sys.argv) != 3:
    print('usage: patch-claude-fable-visibility.py <input-copy> <output-patched>', file=sys.stderr)
    sys.exit(2)

SRC = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()
if SRC == OUT:
    raise SystemExit('Refusing to patch in place: input and output paths are identical')
if not SRC.exists():
    raise SystemExit(f'Input does not exist: {SRC}')

data = bytearray(SRC.read_bytes())
patches = []

def replace_between(label: str, start_marker: bytes, end_marker: bytes, new: bytes, required: list[bytes] | None = None) -> None:
    start = data.find(start_marker)
    if start < 0:
        raise SystemExit(f'{label}: start marker not found')
    end = data.find(end_marker, start)
    if end < 0:
        raise SystemExit(f'{label}: end marker not found')
    old = bytes(data[start:end])
    for r in required or []:
        if r not in old:
            raise SystemExit(f'{label}: expected bytes missing: {r!r}')
    if len(new) > len(old):
        raise SystemExit(f'{label}: new code too long: new={len(new)} old={len(old)}')
    data[start:end] = new + b' ' * (len(old) - len(new))
    patches.append({
        'label': label,
        'start': start,
        'end': end,
        'old_len': len(old),
        'new_len': len(new),
        'pad_len': len(old) - len(new),
        'old_sha256_16': hashlib.sha256(old).hexdigest()[:16],
    })

assistant_new = (
    'case"assistant":{let R=n.message.content?.find((O)=>O?.type==="fallback");'
    'if(R){let w=R.from?.model??"original model",k=R.to?.model??"fallback model",'
    'x=`${w} triggered a model refusal fallback. Switched to ${k}.`;'
    'return Ab.jsx(mEl,{message:{type:"system",subtype:"model_refusal_fallback",direction:"retry",'
    'content:x,level:"warning",trigger:"refusal",originalModel:w,fallbackModel:k,requestId:n.requestId,'
    'apiRefusalCategory:R.apiRefusalCategory,apiRefusalExplanation:null,isMeta:!1,timestamp:n.timestamp,uuid:n.uuid},'
    'addMargin:s,verbose:l,isTranscriptMode:h})}'
    'let w=r.firstTextBlockUuidByMessageID.get(n.message.id),k=o??"100%",'
    'x=n.message.content.map((O,M)=>Ab.jsx(SCm,{param:O,addMargin:s,tools:i,commands:a,verbose:l,'
    'inProgressToolUseIDs:c,progressMessagesForMessage:u,shouldAnimate:d,shouldShowDot:p,width:f,'
    'inProgressToolCallCount:c.size,isTranscriptMode:h,lookups:r,onOpenRateLimitOptions:g,'
    'advisorModel:n.advisorModel,messageUuid:n.uuid,apiMessageId:S?void 0:n.message.id,'
    'isFirstTextBlock:w===void 0||w===n.uuid},M));'
    'return Ab.jsx(B,{flexDirection:"column",width:k,children:x})}'
).encode('utf-8')
replace_between(
    'assistant fallback banner',
    b'case"assistant":{let R;if(t[20]!==r.firstTextBlockUuidByMessageID',
    b'case"user":{',
    assistant_new,
    [b'D=(O,M)=>Ab.jsx(SCm,{param:O', b'x=n.message.content.map(D)'],
)

# Compact formatter to fit the original byte budget. ANSI color is used for the
# appended marker instead of deeper JSX render surgery.
net_new = (
    'function net(e){let t=e.fileSize!==void 0?$a(e.fileSize):e.messageCount+" messages",'
    'n=[Bz(e.modified,{style:"short"})];if(e.gitBranch)n.push(e.gitBranch);n.push(t);'
    'if(e.tag)n.push("#"+e.tag);if(e.agentSetting)n.push("@"+e.agentSetting);'
    'if(e.prNumber)n.push("#"+e.prNumber);'
    'if(e.fableClassifierTriggered)n.push("\x1b[33mFable classifier triggered\x1b[39m");'
    'return n.join(" · ")}'
).encode('utf-8')
replace_between(
    'formatLogMetadata marker',
    b'function net(e){let t=e.fileSize!==void 0?$a(e.fileSize):`${e.messageCount} messages`',
    b'function gte',
    net_new,
    [b'return n.join(" \\xB7 ")'],
)

wpf_new = (
    'async function wpf(e,t){if(!e.isLite||!e.fullPath)return e;'
    'let n=await Nmc(e.fullPath,e.fileSize??0,t),b=!1;'
    'try{let l=D$.readFileSync(e.fullPath,"utf8");'
    'b=l.includes("claude-fable-5")&&(l.includes(\'"type":"fallback"\')||l.includes("model_refusal_fallback"))}catch{}'
    'let r=n.projectPath!==void 0&&Dg.dirname(e.fullPath)===t_(n.projectPath),'
    'o=n.relocatedCwd??(r||e.projectPath===void 0?n.projectPath??e.projectPath:e.projectPath),'
    's={...e,isLite:!1,firstPrompt:n.firstPrompt,gitBranch:n.gitBranch,isSidechain:n.isSidechain,'
    'teamName:n.teamName,sessionKind:n.sessionKind,customTitle:n.customTitle,aiTitle:n.aiTitle,'
    'summary:n.summary,tag:n.tag,agentSetting:n.agentSetting,prNumber:n.prNumber,prUrl:n.prUrl,'
    'prRepository:n.prRepository,projectPath:o,fableClassifierTriggered:b};'
    'if(!s.firstPrompt&&!s.customTitle&&!s.aiTitle)s.firstPrompt="(session)";'
    'if(s.isSidechain||s.teamName||s.sessionKind==="daemon"||s.sessionKind==="daemon-worker")return null;'
    'let i=rgn.has(Tmc()??"");if(!i&&rgn.has(n.entrypoint??""))return null;'
    'if(!i&&n.isLoopSession)return null;return s}'
).encode('utf-8')
replace_between(
    'resume lite-log fable detector',
    b'async function wpf(e,t){if(!e.isLite||!e.fullPath)return e;',
    b'async function kJe',
    wpf_new,
    [b'let n=await Nmc(e.fullPath,e.fileSize??0,t)', b'projectPath:s'],
)

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_bytes(data)
OUT.chmod(0o755)
print({
    'src': str(SRC),
    'out': str(OUT),
    'patches': patches,
    'out_sha256': hashlib.sha256(data).hexdigest(),
})
PY
chmod +x "$PATCH_DIR/scripts/patch-claude-fable-visibility.py"
```

Run the patcher:

```bash
"$PATCH_DIR/scripts/patch-claude-fable-visibility.py" \
  "$PATCH_DIR/artifacts/claude-unpatched-copy" \
  "$PATCH_DIR/artifacts/claude-fable-visibility-patched"
```

Expected patcher output:

- The patcher should print three patch records:
  - `assistant fallback banner`
  - `formatLogMetadata marker`
  - `resume lite-log fable detector`
- Each record should include the locally discovered `start`, `end`, old length, new length, and padding length.
- Treat those printed ranges as local evidence for that executable only. Do not copy ranges from another machine or another Claude version.

---

## Re-sign and verify

On macOS, the modified Mach-O will not run correctly until it is re-signed. Create a signed copy:

```bash
cp -p "$PATCH_DIR/artifacts/claude-fable-visibility-patched" \
  "$PATCH_DIR/artifacts/claude-fable-visibility-patched.adhoc"
chmod u+x "$PATCH_DIR/artifacts/claude-fable-visibility-patched.adhoc"

codesign --force --sign - \
  "$PATCH_DIR/artifacts/claude-fable-visibility-patched.adhoc"
```

Verify:

```bash
"$PATCH_DIR/scripts/verify-claude-fable-patch.py" \
  "$PATCH_DIR/artifacts/claude-fable-visibility-patched.adhoc"

codesign --verify --strict --verbose=4 \
  "$PATCH_DIR/artifacts/claude-fable-visibility-patched.adhoc"

"$PATCH_DIR/artifacts/claude-fable-visibility-patched.adhoc" --version
"$PATCH_DIR/artifacts/claude-fable-visibility-patched.adhoc" --help >/tmp/claude-fable-help.txt
```

Expected:

- static verifier passes;
- code signature verifies;
- `--version` prints `2.1.198 (Claude Code)`;
- `--help` exits successfully.

---

## Validate against a local fallback transcript

Find or choose a local Claude session JSONL that contains a Fable fallback event. Do not print private prompt/tool contents.

A metadata-only validation script:

```bash
cat > "$PATCH_DIR/scripts/check-fable-transcript-metadata.py" <<'PY'
#!/usr/bin/env python3
from pathlib import Path
import json
import sys

if len(sys.argv) != 2:
    print('usage: check-fable-transcript-metadata.py <session.jsonl>', file=sys.stderr)
    sys.exit(2)

path = Path(sys.argv[1])
records = []
by_uuid = {}
latest_leaf = None
latest_last_prompt_line = None
for i, line in enumerate(path.open(), 1):
    obj = json.loads(line)
    obj['_line'] = i
    records.append(obj)
    if obj.get('uuid'):
        by_uuid[obj['uuid']] = obj
    if obj.get('type') == 'last-prompt':
        latest_leaf = obj.get('leafUuid')
        latest_last_prompt_line = i

chain_lines = set()
seen = set()
cur = latest_leaf
while cur and cur in by_uuid and cur not in seen:
    seen.add(cur)
    obj = by_uuid[cur]
    chain_lines.add(obj['_line'])
    cur = obj.get('parentUuid')

print(f'latest_last_prompt_line={latest_last_prompt_line}')
print(f'latest_leaf={latest_leaf}')
print('fallback-like records:')
for obj in records:
    msg = obj.get('message') if isinstance(obj.get('message'), dict) else None
    content = msg.get('content') if msg else obj.get('content')
    content_types = []
    if isinstance(content, list):
        content_types = [c.get('type') for c in content if isinstance(c, dict)]
    is_assistant_fallback = obj.get('type') == 'assistant' and 'fallback' in content_types
    is_system_fallback = obj.get('type') == 'system' and obj.get('subtype') == 'model_refusal_fallback'
    if is_assistant_fallback or is_system_fallback:
        print({
            'line': obj['_line'],
            'on_latest_chain': obj['_line'] in chain_lines,
            'type': obj.get('type'),
            'subtype': obj.get('subtype'),
            'uuid': obj.get('uuid'),
            'parentUuid': obj.get('parentUuid'),
            'requestId': obj.get('requestId'),
            'content_types': content_types if content_types else type(content).__name__,
            'originalModel': obj.get('originalModel'),
            'fallbackModel': obj.get('fallbackModel'),
            'apiRefusalCategory': obj.get('apiRefusalCategory'),
        })
PY
chmod +x "$PATCH_DIR/scripts/check-fable-transcript-metadata.py"
```

Run it:

```bash
export TARGET_SESSION_JSONL="/path/to/local/session.jsonl"
"$PATCH_DIR/scripts/check-fable-transcript-metadata.py" "$TARGET_SESSION_JSONL"
```

For this patch, either of these should be enough for the `/resume` marker:

- JSONL contains `claude-fable-5` plus `"type":"fallback"`;
- JSONL contains `claude-fable-5` plus `model_refusal_fallback`.

---

## Interactive validation

### Validate `/resume` picker marker

Run the patched copy directly from a working directory where Claude normally runs:

```bash
cd /path/to/your/project
"$PATCH_DIR/artifacts/claude-fable-visibility-patched.adhoc"
```

Then type:

```text
/resume
```

Expected:

- A session containing a Fable fallback shows yellow metadata text:

```text
Fable classifier triggered
```

### Validate resumed-history banner

If you know the session ID, validate with a forked resume:

```bash
cd /path/to/your/project
"$PATCH_DIR/artifacts/claude-fable-visibility-patched.adhoc" \
  --resume <session-id> \
  --fork-session
```

Expected:

- The on-chain assistant fallback marker renders as a warning-style fallback banner in resumed history.

Exit without sending a prompt unless you intentionally want to continue the session.

---

## Make this your normal local `claude`

There are three options. The recommended option is a reversible symlink or wrapper. Do not overwrite the official version file unless you intentionally accept the risk. 

IMPORTANT: YOU SHOULD ASK THE USER WHICH OPTION THEY PREFER BEFORE PROCEEDING 

### Option A: opt-in alias

Safest. Leaves the normal `claude` command unchanged.

```bash
cat >> ~/.zshrc <<SH
alias claude-fable='$PATCH_DIR/artifacts/claude-fable-visibility-patched.adhoc'
SH
source ~/.zshrc

claude-fable --version
```

### Option B: wrapper earlier in `PATH`

This makes `claude` run the patched executable without modifying the official Claude install.

```bash
mkdir -p "$HOME/bin"
cat > "$HOME/bin/claude" <<SH
#!/bin/sh
exec "$PATCH_DIR/artifacts/claude-fable-visibility-patched.adhoc" "\$@"
SH
chmod +x "$HOME/bin/claude"
```

Ensure `$HOME/bin` appears before the official Claude directory in `PATH`:

```bash
case ":$PATH:" in
  *":$HOME/bin:"*) ;;
  *) echo 'export PATH="$HOME/bin:$PATH"' >> ~/.zshrc ;;
esac
source ~/.zshrc

which claude
claude --version
```

Rollback:

```bash
rm "$HOME/bin/claude"
hash -r 2>/dev/null || true
which claude
claude --version
```

### Option C: repoint the existing Claude symlink

Use only if your `claude` command is itself a symlink you control.

Inspect first:

```bash
CLAUDE_CMD="$(command -v claude)"
ls -l "$CLAUDE_CMD"
readlink "$CLAUDE_CMD" || true
```

If it is safe to repoint:

```bash
readlink "$CLAUDE_CMD" > "$PATCH_DIR/original-claude-symlink-target.txt"
ln -sfn "$PATCH_DIR/artifacts/claude-fable-visibility-patched.adhoc" "$CLAUDE_CMD"
claude --version
```

Rollback:

```bash
ln -sfn "$(cat "$PATCH_DIR/original-claude-symlink-target.txt")" "$CLAUDE_CMD"
claude --version
```

### Option D: overwrite the official version file

Not recommended.

Only do this if you understand the risk, have a backup, and accept that future Claude updates may replace or conflict with the patch.

```bash
OFFICIAL="$CLAUDE_BIN"
BACKUP="$CLAUDE_BIN.official-backup-$(date +%Y%m%d-%H%M%S)"
PATCHED="$PATCH_DIR/artifacts/claude-fable-visibility-patched.adhoc"

cp -p "$OFFICIAL" "$BACKUP"
cp -p "$PATCHED" "$OFFICIAL"
chmod u+x "$OFFICIAL"
codesign --force --sign - "$OFFICIAL"
claude --version
```

Rollback:

```bash
cp -p "$BACKUP" "$OFFICIAL"
chmod u+x "$OFFICIAL"
claude --version
```

Prefer Option A or B.

---

## Updating after Claude changes versions

When Claude updates, the minified code and byte offsets may change.

After any update:

```bash
export CLAUDE_CMD="$(command -v claude)"
CLAUDE_BIN="$(python3 - <<'PY'
import os
print(os.path.realpath(os.environ['CLAUDE_CMD']))
PY
)"
"$CLAUDE_BIN" --version
shasum -a 256 "$CLAUDE_BIN"
```

Then re-run seam discovery:

```bash
"$PATCH_DIR/scripts/discover-claude-fable-seams.py" "$CLAUDE_BIN"
```

If markers moved but the local code shape is still equivalent, update the patcher’s markers/ranges. If the local code shape changed materially, re-understand the render path before patching.

---

## Known limitations

- Version-specific to Claude Code 2.1.198 as tested.
- Uses byte-level replacement in a minified bundled executable.
- Uses synchronous full-file reads during `/resume` lite-log enrichment.
- Uses ANSI text color in a metadata string rather than a deeper JSX render patch.
- The compact metadata formatter omits some rare metadata detail to fit the original byte budget, notably the `bg` segment and PR repository prefix.
- The resumed-history fallback banner uses synthesized compact text from the fallback block models; it does not recover richer off-chain banner copy unless a deeper request-ID correlation patch is added.

---

## Privacy guidance

When validating against real transcripts:

- Do not dump long prompts, tool arguments, tool outputs, or private content.
- Inspect only structured metadata, UUIDs, request IDs, model names, content block types, short prefixes, and hashes.
- Prefer `--fork-session` for resumed-history UI validation.
