# HarnessMonkey / ClaudeMonkey — macOS → Windows Porting Audit

## Scope

Audited every module in `src/claude_monkey/` (43 files, including `gui/`), plus `tests/`, `scripts/`, and `.development/`. `.development/` contains only working artifacts (JS module dumps, screenshots, spike code) — **no Windows/portability notes exist anywhere in the repo.** `pyproject.toml` and `CLAUDEMONKEY.md` both state the tool is scoped to "macOS on Apple Silicon (arm64)" and that the repack engine "understands exactly one binary shape."

---

## 1. Per-module classification

| Module | Class | Why |
|---|---|---|
| `macho.py` | **DEEP** | Raw Mach-O 64 load-command/segment/section parser and mutator. No PE equivalent exists. |
| `bun_graph.py` | **PORTABLE** | Pure byte-offset parser of a proprietary Bun trailer format embedded in the binary; format itself is OS-agnostic (Bun uses the same trailer on Windows/Linux builds), but only ever reached via `macho.py`. |
| `repack.py` | **DEEP** | Orchestrates `macho.py` + `bun_graph.py`; the whole file's contract (segment alignment, `__LINKEDIT` shifting, code-signature offset bumping) is Mach-O-specific. |
| `builder_v15.py` | **DEEP** | Calls `find_macho_layout`, and directly shells out to `codesign` for signing. |
| `binary_inspect.py` | **DEEP** | Thin wrapper around `find_macho_layout` + `parse_bun_section`; `"format": "macho64"` is baked into its output schema. |
| `source_discovery.py` | **SHALLOW** | Pure `pathlib`/`shutil.which` logic; only issue is the hardcoded `"claude"` executable name (no `.exe`) and reliance on POSIX `os.X_OK` semantics. |
| `shim.py` | **DEEP** | Renders a `#!/usr/bin/env python3` shebang script and `chmod 0o755`s it. Neither works as a launcher on Windows. |
| `shim_entry.py` | **SHALLOW** | Logic is portable; final launch uses `os.execvpe`, which exists on Windows but is emulated (spawns + waits + exits) rather than a true exec — behavioral, not fatal. |
| `install.py` | **DEEP** | `os.chflags`/`stat.UF_IMMUTABLE` (BSD-only, guarded), `symlink_to()` (needs elevated privilege on Windows by default), and delegates privileged ops to `authorization.py`. |
| `repair.py` | **SHALLOW** | Business logic is portable; depends on `install.py`'s chflags lock/unlock helpers (already correctly no-op off Darwin) and `target_needs_authorization`. |
| `authorization.py` | **DEEP** | Entire privilege-escalation model is `osascript`/`sudo` + POSIX path list. No Windows UAC/elevation path exists. |
| `smoke.py` | **SHALLOW** (code) / **DEEP** (function) | Code is plain `subprocess.run` (no pty/termios/fcntl) — portable machinery — but two of its four functions (`codesign_sign`/`codesign_verify`) invoke a macOS-only tool by design. |
| `launch_agent.py` | **DEEP** | `plistlib` + `~/Library/LaunchAgents` + `launchctl bootstrap/bootout` + unconditional `os.getuid()`. No Windows equivalent wired up at all. |
| `menubar_install.py` | **SHALLOW** | Pure path/venv-provisioning logic (`uv venv`, `uv pip install`), no macOS API calls itself — but every caller path leads into `launch_agent.py`. |
| `menubar_commands.py` | **DEEP** | `os.getpgid`/`os.killpg`/`signal.SIGKILL`/`start_new_session=True` — POSIX process-group semantics, no Windows analog without `CREATE_NEW_PROCESS_GROUP` + `taskkill`/`CTRL_BREAK_EVENT` rewrite. |
| `menubar_state.py` | **PORTABLE** | Pure dataclasses over JSON menu state. |
| `paths.py` | **SHALLOW** | Single `~/.claude-monkey` root via `Path.home()`; works but should move to `%LOCALAPPDATA%` for Windows convention. |
| `config.py` | **PORTABLE** | Pure JSON load/save. |
| `launch_profile.py` | **SHALLOW** | `os.access(path, os.X_OK)` is meaningless on Windows (always true for existing files); `shutil.which` behavior differs (PATHEXT) but works. |
| `authorization.py` (see above) | **DEEP** | — |
| `package_model.py` | **PORTABLE** | Pure manifest validation/dataclasses. |
| `module_patch.py` | **PORTABLE** | Pure JS-text-splice logic over byte ranges; no OS calls. |
| `manifest_v2.py` | **PORTABLE** | Pure dataclasses/validation. |
| `packages_admin.py` | **PORTABLE** | Uses only `shutil.copytree`/`os.replace`/`shutil.rmtree`/`tempfile`/`uuid` — all cross-platform (note: `os.replace` can fail on Windows if the destination is open/locked, a behavioral risk worth flagging but not a coupling per se). |
| `prompts.py` | **PORTABLE** | Text/dataclass only. |
| `payloads.py` | **PORTABLE** | Base64/JSON payload helpers. |
| `progress.py` | **PORTABLE** | Pure event/stage tracker. |
| `reports.py` / `reports_v2.py` | **PORTABLE** | Pure dataclasses → JSON. |
| `cli_json.py` | **PORTABLE** | JSON envelope helpers. |
| `cli.py` | **SHALLOW** | 2100 lines of argparse/orchestration; own code has no direct OS-specific calls beyond `shutil.which("claude")` and `Path.home()`, but wires together every DEEP module above (`launch_agent`, `install`, `builder_v15`). |
| `status.py` | **SHALLOW** | Business logic portable; reads `st_flags`/chflags results from `install.py` (already correctly guarded to return `False` off-Darwin) and reports `sys.platform`/`platform.machine()` verbatim. |
| `authorization.py` | (dup, see above) | — |
| `gui/__init__.py` | **PORTABLE** | Empty. |
| `gui/app.py` | **SHALLOW** | PySide6 is cross-platform; macOS `AppKit`/`LSUIElement`-equivalent calls are correctly `sys.platform`-guarded — **except** one unguarded `os.getuid()` call (bug, see §4). |
| `gui/commands.py` | **PORTABLE** | Pure command-dict builders for the CLI bridge. |
| `gui/icons.py` | **SHALLOW** | `icon.setIsMask(True)` is a macOS "template icon" convention; harmless (documented) no-op on Windows. |
| `gui/pages/*.py` | **PORTABLE** | Pure Qt widget code, no OS calls. |
| `gui/progress_dialog.py` / `gui/progress_model.py` | **PORTABLE** | Pure Qt/dataclass code consuming a JSON event stream. |
| `gui/settings_window.py` | **PORTABLE** | Pure Qt widget code. |
| `gui/tray.py` | **PORTABLE** | `QSystemTrayIcon`/`QMenu` — cross-platform Qt API. |
| `gui/window_model.py` | **SHALLOW** | Pure view-model logic; hardcodes `/usr/local/bin/claude`, `/opt/homebrew/bin/claude` as "common install targets" shown in the UI. |

---

## 2. Detailed findings by investigation area

### 2.1 How the Bun module graph is located inside the binary (macho.py / repack.py / builder_v15.py / bun_graph.py)

This is a **real Mach-O 64 parser**, not a marker/offset scan. `macho.py:75-131` (`find_macho_layout`) walks the Mach-O load-command table explicitly:

```python
# src/claude_monkey/macho.py:75-101
def find_macho_layout(data: bytes | bytearray) -> MachOLayout:
    if len(data) < 32 or u32(data, 0) != MACHO_MAGIC_64_LE:
        raise MachOError("unsupported_macho_magic")
    (... , ncmds, sizeofcmds, ...) = struct.unpack_from("<IiiIIIII", data, 0)
    ...
    for index in range(ncmds):
        cmd, cmdsize = struct.unpack_from("<II", data, off)
        ...
        if cmd == LC_SEGMENT_64:
            name = _name(...)
            ...
            if name == "__BUN":
                bun_segment = segment
            elif name == "__LINKEDIT":
                linkedit_segment = segment
            ... iterate sections looking for segname=="__BUN", sectname=="__bun"
        elif cmd == LC_CODE_SIGNATURE:
            code_signature = LinkeditData(...)
```

So it decodes `mach_header_64`, iterates `LC_SEGMENT_64` commands by name (`__BUN`, `__LINKEDIT`), finds the `__bun`/`__BUN` section, and separately tracks `LC_CODE_SIGNATURE`, `LC_SYMTAB`, `LC_DYSYMTAB`, `LC_DYLD_INFO(_ONLY)`, and a generic `LINKEDIT_DATA_CMDS` set — because `shift_macho_after_bun_change` (`macho.py:143-226`) must patch every one of those load commands' file-offset fields (symtab, string table, dyld rebase/bind/lazy-bind/export tables, indirect-symbol table, code-signature blob offset) after the `__BUN` segment grows or shrinks.

Once the raw `__bun` section bytes are extracted (`repack.py:28-30`, using `layout.bun_section.offset`/`.size`), `bun_graph.py` parses **Bun's own module-graph binary format**, which is a proprietary trailer format independent of Mach-O:

```python
# src/claude_monkey/bun_graph.py:6, 139-150
TRAILER = b"\n---- Bun! ----\n"
...
def parse_bun_section(section: bytes) -> BunGraph:
    declared_len = _u64(section, 0)
    payload = section[8 : 8 + declared_len]
    trailer_offset = payload.rfind(TRAILER)          # <-- marker scan, but only inside the section
    ...
    offsets_struct_offset = trailer_offset - 32       # fixed struct immediately before the trailer
    byte_count = _u64(payload, offsets_struct_offset)
    modules_offset = _u32(payload, offsets_struct_offset + 8)
    ...
```

`bun_graph.py:170-194` then reads a fixed 52-byte (`MODULE_RECORD_SIZE`) record per module containing `path_offset/path_size/content_offset/content_size` (and 5 more `u32` fields per record, `POINTER_PAIR_COUNT = 6` total pointer/size pairs), and validates that every module path starts with `/$bunfs/` or `file:///$bunfs/`.

**Implication for a Windows port:** the `bun_graph.py` layer (finding the trailer, module table, and patching content/pointers) is a **self-contained, OS-agnostic byte-format parser** that would work unchanged on a Windows Bun-compiled executable's embedded `__bun`-equivalent bytes, **provided** you can first locate that byte range inside a PE file. That container-location step is 100% owned by `macho.py`/`repack.py`'s Mach-O-specific code (load commands, segments, `LC_CODE_SIGNATURE`, `__LINKEDIT` shifting) and would need a full **PE-format counterpart**: PE section headers instead of Mach-O segments/sections, `IMAGE_DIRECTORY_ENTRY_*`/relocation tables instead of `LC_DYLD_INFO`/`LC_SYMTAB`/`LC_DYSYMTAB` offsets, and Authenticode signing instead of the Mach-O `LC_CODE_SIGNATURE` blob. This is genuinely non-trivial reverse-engineering work (need to confirm Bun's Windows PE-embedding scheme, likely a custom section or resource, and PE's own size/alignment/checksum rules), but the module boundary is clean: **`bun_graph.py` ports as-is; `macho.py`+`repack.py`'s segment-shifting logic needs a from-scratch PE analog.**

### 2.2 source_discovery.py — finding the installed Claude binary

`source_discovery.py:146-163` (`discover_official_claude`) tries, in order: `config.officialClaudePath`, the `CLAUDE_MONKEY_SOURCE` env var, then `shutil.which("claude")` (`source_discovery.py:158`). No hardcoded install-directory search list exists in this file (unlike `gui/window_model.py`'s `COMMON_INSTALL_TARGETS`, which is UI-only). Each candidate must pass `_resolve_existing_executable` (`source_discovery.py:50-59`, `os.access(path, os.X_OK)`) and a `meets_plausible_official_size` stat-only check (`source_discovery.py:34-47`, 50 MB floor, since a real Claude binary is ~230 MB). Version detection (`install.py:50-81`, `_version_from_path`) is **path-shape only** — it never executes the binary — matching against a `.../versions/<version>/...` directory segment via regex; it does not parse `--version` output for discovery (that only happens later, in smoke testing).

**Windows implications:** `shutil.which("claude")` will look for `claude`, `claude.exe`, `claude.cmd`, etc. via `PATHEXT` on Windows, so this part largely works. `os.access(path, os.X_OK)` is a no-op check on Windows (always True for any existing file), so the "must be executable" gate silently becomes "must exist" — shallow but real behavior drift.

### 2.3 shim.py / shim_entry.py / install.py / repair.py — the shim mechanism

The shim is a **Python shebang script**, not a native binary or symlink:

```python
# src/claude_monkey/shim.py:7-31
def render_shim_script(state_dir: str) -> str:
    ...
    return f'''#!/usr/bin/env python3
...
from claude_monkey.shim_entry import main
if __name__ == "__main__":
    raise SystemExit(main({state_dir_literal}))
'''

def write_shim(path: Path, state_dir: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_shim_script(str(state_dir)))
    path.chmod(0o755)
```

It's installed by literally overwriting the resolved `claude` binary path (`menubar_install.py:17-18`: `managed_user_target` = `state_dir/bin/claude`) via `install.install_shim_transaction` (`install.py:532-605`). PATH interception is therefore just "the file at the same path the user's `claude` used to resolve to is now this Python script" — no PATH manipulation, no separate `claude` wrapper directory. At runtime the shim computes the real launch target (patched build vs. official fallback) and **replaces the current process**:

```python
# src/claude_monkey/shim_entry.py:79
os.execvpe(str(result.target.path), [str(result.target.path), *result.argv], result.env)
```

Official-update clobbering detection/repair (`repair.py`) works by SHA-256 digest comparison: the install record (`install-record.json`) stores `installedShimSha256`; if the target's current digest no longer matches, `status.py`/`repair.py` treat the target as "reverted by the official installer" and can re-cache the replacement + re-swap the shim back in (`repair.py:217-403`, `repair_shim_action`). To *survive* between official-updater sweeps, `install.py` sets the **BSD/macOS user-immutable flag** as a final step:

```python
# src/claude_monkey/install.py:352-360
if not (sys.platform == "darwin" and hasattr(os, "chflags")):
    return False
try:
    os.chflags(str(target_path), stat.UF_IMMUTABLE)
except OSError:
    return False
```

Elevated-path writes (e.g. `/usr/local/bin/claude`) go through `authorization.py`'s `osascript`/`sudo` wrapper, invoking `/bin/mkdir -p`, `/bin/mv -f`, `/bin/rm -f` as literal absolute paths (`install.py:293-311`).

**Windows implications (this is the single hardest area to port):**
- A file with no extension and a `#!/usr/bin/env python3` shebang is not executable by `cmd.exe`/PowerShell/`CreateProcess` at all. The shim would need to become `claude.cmd` (a batch wrapper calling `python -m claude_monkey.shim_entry`) or a compiled tiny launcher `claude.exe`. `.chmod(0o755)` is a no-op on Windows (`os.chmod` only toggles the read-only bit) — not equivalent to marking something executable, since Windows has no execute permission bit for arbitrary files; execution is determined by extension/association.
- `os.execvpe` exists but is *emulated* on Windows (`spawnve` + wait + `sys.exit(returncode)`), not a true process image replacement — process tree/PID changes, but functionally it launches and waits, so most Claude Code CLI use cases (blocking parent) would still work.
- `os.chflags`/`stat.UF_IMMUTABLE` do not exist on Windows at all (`hasattr(os, "chflags")` is `False`, so the guard is already correct — this degrades gracefully to "shim not locked," which is a **functional regression**, not a crash: on Windows the official-updater clobbering problem this exists to solve would need `SetFileAttributes` with `FILE_ATTRIBUTE_READONLY` or an ACL deny-write rule as the closest analog, neither of which is anywhere near as strong a guarantee as `UF_IMMUTABLE` (which blocks unlink/rename outright, even for root, until cleared).
- `authorization.py`'s elevation model (`/usr/bin/osascript "do shell script ... with administrator privileges"`, falling back to `sudo`) has **zero Windows analog implemented**. `authorization_method_for_target` (`authorization.py:53-56`) would need a UAC equivalent (e.g., relaunch self via `ShellExecuteW` with `runas` verb, or a scheduled task running as admin) — this is new code, not a tweak.
- Protected-path list (`authorization.py:32-39`: `/bin`, `/sbin`, `/usr/bin`, `/usr/sbin`, `/usr/local/bin`, `/opt/homebrew/bin`) is entirely POSIX; Windows equivalents (`C:\Windows\System32`, `C:\Program Files`) aren't present.
- `install.py:685,719` uses `tmp.symlink_to(...)` for the "restore previous symlink" and `use_official` paths — creating symlinks on Windows requires either Developer Mode enabled or elevated privileges (`SeCreateSymbolicLinkPrivilege`), a real deployment friction point.

### 2.4 launch_agent.py / menubar_install.py / gui/ — pyobjc, LaunchAgent, tray

`launch_agent.py` writes a `.plist` via `plistlib` to `~/Library/LaunchAgents/com.hackerbara.claude-monkey.plist` (`launch_agent.py:32-47`) and drives it entirely through `launchctl bootstrap`/`bootout` in the caller's own `gui/<uid>` domain:

```python
# src/claude_monkey/launch_agent.py:50-51, 58-68
def _gui_domain() -> str:
    return f"gui/{os.getuid()}"

def install_agent(gui_executable: Path, home: Path, runner=run_command) -> CommandResult:
    ...
    runner(["launchctl", "bootout", _gui_domain(), str(plist)])
    return runner(["launchctl", "bootstrap", _gui_domain(), str(plist)])
```

This entire module is **DEEP** and has no Windows guard at all (unlike `install.py`'s chflags calls) — calling `install_agent`/`uninstall_agent` on Windows raises `AttributeError: module 'os' has no attribute 'getuid'` immediately, before even reaching the `launchctl` subprocess call (which would also fail with `FileNotFoundError`). The Windows analog is either a Startup-folder `.lnk`/batch shortcut, or a `HKCU\...\Run` registry value, or Task Scheduler (`schtasks`) — a full rewrite, not a shim.

`gui/app.py` correctly guards its two `AppKit` imports behind `sys.platform != "darwin": return` (`gui/app.py:114`, `144`) for `apply_macos_accessory_policy`/`activate_app_for_window` — these are genuinely well-isolated and port cleanly (PySide6's `QSystemTrayIcon` on Windows already does the "no taskbar/only tray" behavior natively, so these functions simply become no-ops on Windows, which is correct). **However**, there is one unguarded POSIX-only call sitting right next to the correctly-guarded `refuse_root()`:

```python
# src/claude_monkey/gui/app.py:235-237, 829
def refuse_root() -> bool:
    return getattr(os, "geteuid", lambda: 1)() == 0   # correctly guarded

...
instance = SingleInstance(f"claude-monkey-gui-{os.getuid()}")   # NOT guarded — AttributeError on Windows
```

`gui/icons.py:26` calls `icon.setIsMask(True)` to get macOS's monochrome "template icon" tray behavior; this is explicitly commented as "harmless on Windows" and is correct (Qt no-ops it there). `gui/window_model.py:18-22` hardcodes `/usr/local/bin/claude` and `/opt/homebrew/bin/claude` as "common install target" suggestions shown in the settings UI — cosmetic/shallow, needs Windows-appropriate suggestions (e.g. `%LOCALAPPDATA%\Programs\claude\claude.exe` or wherever the official Windows installer places it, which needs to be determined).

`menubar_install.py` itself (venv provisioning via `uv venv`/`uv pip install`, `menubar_install.py:85-132`) has no direct OS calls — it's SHALLOW, but exists purely to feed `launch_agent.py`, so it's dead weight without a Windows `launch_agent` counterpart.

`menubar_commands.py` (the GUI's subprocess driver for the CLI) uses **POSIX process-group semantics** for cancelling long-running CLI operations:

```python
# src/claude_monkey/menubar_commands.py:40-59
def cancel(self, grace_seconds: float = 5.0) -> None:
    pgid = os.getpgid(self.process.pid)          # POSIX-only
    os.killpg(pgid, signal.SIGTERM)               # POSIX-only
    ...
    os.killpg(pgid, signal.SIGKILL)               # POSIX-only
```
and `start_new_session=True` (`menubar_commands.py:299`) to create that process group in the first place. None of `os.getpgid`, `os.killpg` exist on Windows. The Windows analog is `subprocess.Popen(..., creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)` at spawn time, then `process.send_signal(signal.CTRL_BREAK_EVENT)` for graceful cancel and `process.terminate()`/`taskkill /T /F` for the hard-kill escalation — a real rewrite of this class's cancel path, not a guard.

### 2.5 smoke.py — how binaries are launched for testing

Confirmed: **no `pty`, `termios`, `fcntl`, `tty`, `resource`, or `os.fork` usage anywhere in `src/claude_monkey/`.** `smoke.py` uses plain `subprocess.run(argv, text=True, capture_output=True, timeout=...)` (`smoke.py:20-28`) — this is fully cross-platform. The only macOS-specific content in this file is that two of its four public functions literally shell out to the `codesign` tool by name:

```python
# src/claude_monkey/smoke.py:56-61
def codesign_sign(binary: Path, runner=run_command) -> CommandResult:
    return runner(["codesign", "--force", "--sign", "-", str(binary)])

def codesign_verify(binary: Path, runner=run_command) -> CommandResult:
    return runner(["codesign", "--verify", "--deep", "--strict", "--verbose=4", str(binary)])
```
`builder_v15.py:430-444` (`_apply_signing_v15`) calls both unconditionally as part of every build; on Windows this needs to become either a no-op (skip signing entirely — likely fine, since ad-hoc codesign here exists only to satisfy macOS Gatekeeper for a locally-modified binary, a concept Windows doesn't have) or a call to `signtool.exe` if a real Authenticode certificate is available (unlikely for this use case). `smoke_version_and_help`/`smoke_claude_code_version_and_help` (the actual functional smoke tests) are already 100% portable.

### 2.6 paths.py / config.py — hardcoded paths

Everything funnels through a single root:
```python
# src/claude_monkey/paths.py:48-50
def default_paths() -> StatePaths:
    home = Path(os.environ.get("HOME", str(Path.home())))
    return StatePaths(state_dir=home / ".claude-monkey")
```
All other state paths (`bin/`, `patches/`, `prompts/`, `options/`, `logs/`, `versions/`, `sources/`) are relative to this one root (`paths.py:20-45`, `install.py:141-143` `sources_root`). `os.environ.get("HOME", ...)` is a POSIX-ism (`HOME` isn't reliably set on Windows — `Path.home()` fallback already handles that correctly via `USERPROFILE`, so this is low-risk, but the convention itself (`~/.claude-monkey`, a dot-prefixed hidden dir at the profile root) is non-idiomatic on Windows, where `%LOCALAPPDATA%\ClaudeMonkey` would be expected. Other hardcoded absolute paths found:
- `authorization.py:32-39` — `/bin`, `/sbin`, `/usr/bin`, `/usr/sbin`, `/usr/local/bin`, `/opt/homebrew/bin` (protected-path detection)
- `authorization.py:56,62` — `/usr/bin/osascript`
- `launch_agent.py:47` — `~/Library/LaunchAgents/...plist`
- `gui/window_model.py:18-22` — `/usr/local/bin/claude`, `/opt/homebrew/bin/claude` (UI suggestion list only)
- `install.py:293-311` — `/bin/mkdir`, `/bin/mv`, `/bin/rm` (literal absolute argv for privileged ops)

### 2.7 All external binaries/tools invoked via subprocess (grepped across the whole package)

| Tool | Where | Purpose | Windows status |
|---|---|---|---|
| `codesign` | `smoke.py:57,61`, called from `builder_v15.py:435-436` | Ad-hoc re-sign patched Mach-O binary + verify signature | No equivalent needed/available; skip or `signtool` |
| `osascript` | `authorization.py:56,62-75` | GUI privilege-elevation prompt (`do shell script ... with administrator privileges`) | No equivalent; needs UAC rewrite |
| `sudo` | `authorization.py:76-88` (fallback if no osascript) | CLI-context privilege elevation | Not present on Windows by default |
| `/bin/mkdir -p`, `/bin/mv -f`, `/bin/rm -f` | `install.py:293-311` | Privileged filesystem ops for protected install targets | Would become PowerShell/`cmd` equivalents or Win32 API calls under elevation |
| `launchctl bootstrap` / `bootout` | `launch_agent.py:67-68,147,154` | Register/unregister the menubar LaunchAgent | No equivalent; needs Task Scheduler/Startup-folder/registry Run key |
| `open` | `menubar_commands.py:233` (`CommandRunner.open_path`) | Open a file/folder in Finder | Windows equivalent: `os.startfile()` or `explorer.exe` |
| `uv venv`, `uv pip install` | `menubar_install.py:105,110-119` | Provision the dedicated app venv for the LaunchAgent | `uv` itself is cross-platform; the venv layout (`bin/` vs `Scripts/`) needs adjusting (`app_gui_executable` at `menubar_install.py:81-82` hardcodes `"bin" / "claude-monkey-menubar"`, which is `Scripts\claude-monkey-menubar.exe` on Windows) |
| `[str(sys.executable), "-m", "claude_monkey"]` | `gui/app.py:811` | GUI drives the CLI as a subprocess | Portable |
| the patched `claude` binary itself (`--version`, `--help`) | `smoke.py:52-53,64-68`, via `builder_v15.py` | Smoke-test the rebuilt binary | Portable subprocess mechanics; binary itself needs to be a Bun/PE Windows build |
| `python3` | `tests/test_smoke.py:44` (`test_run_command_timeout_returns_failure_result`) | Test-only timeout-behavior harness | `python3` is typically not on PATH on Windows (it's `python`/`py`) — test portability hazard |

### 2.8 .development/ notes and test-suite portability hazards

`.development/` contains no design docs about Windows or cross-platform work — it's exclusively build artifacts (temp JS module dumps, `tmp-v*-graph-*.json`, screen recordings, a `pypi-stub/` folder, and several dated experiment folders like `normal-channel-*-codex`). Grepping all of `.development/*.md` for "windows" turns up nothing relevant.

Test-suite hazards found:
- `tests/test_shim_lock.py` and `tests/conftest.py` are **exemplary** — they already guard every `chflags`/`UF_IMMUTABLE` test behind `pytest.mark.skipif(not (sys.platform == "darwin" and hasattr(os, "chflags")), ...)` (`test_shim_lock.py:36-38`), and `conftest.py`'s autouse fixture (`conftest.py:16-41`) that sweeps `UF_IMMUTABLE` off tmp files after each test is itself platform-guarded. This part of the suite would already pass cleanly on Windows (mostly by skipping).
- `tests/test_launch_agent.py:71,89` asserts on literal `["launchctl", "bootstrap"/"bootout"]` argv — these tests mock the runner, so they'd still *pass* mechanically on Windows CI, but they assert macOS-only behavior as if it were the only behavior; a Windows port would need a parallel `launch_agent_windows` test file, not a tweak to this one.
- `tests/test_smoke.py:33-40` and `tests/test_menubar_install.py:22` hardcode `codesign` argv and `/usr/local/bin/claude` respectively — again mocked, so they pass regardless of host OS, but encode macOS-only expectations as the *only* expectations.
- `tests/test_authorization.py:121` tests the `osascript`-quoting logic directly — portable as a unit test (string construction), even though the feature it tests has no Windows equivalent.
- `tests/test_smoke.py:44` (`test_run_command_timeout_returns_failure_result`) spawns `python3` directly — likely to fail on stock Windows where the interpreter is `python`/`py`, not `python3`.
- No test in the suite currently exercises `gui/app.py:829`'s unguarded `os.getuid()` call under a simulated non-POSIX `os` module, so this latent bug isn't caught by CI on macOS.

---

## 3. Full "what would break on Windows and why" summary table

| Mechanism | File:line | Purpose | Windows analog |
|---|---|---|---|
| Mach-O 64 load-command parsing | `macho.py:75-131` | Locate `__BUN`/`__LINKEDIT` segments, `__bun` section, `LC_CODE_SIGNATURE` | Full PE section/directory parser (new code) |
| Mach-O post-patch offset shifting | `macho.py:143-226` | Fix up symtab/dyld-info/dysymtab/linkedit/codesign offsets after resizing | PE relocation-table/section-header fixups (new code) |
| `codesign --force --sign -` / `--verify` | `smoke.py:57,61` | Ad-hoc re-sign + verify patched binary | Skip, or `signtool.exe` with a cert |
| `#!/usr/bin/env python3` + `chmod 0o755` shim | `shim.py:10,31` | Make the shim launchable in place of `claude` | `claude.cmd` batch wrapper or compiled launcher; `chmod` is a no-op on Windows |
| `os.chflags`/`stat.UF_IMMUTABLE` | `install.py:352-360,378-386,416-425` | Lock shim against official-updater clobbering | Not directly portable; `FILE_ATTRIBUTE_READONLY` or ACL deny-write is the closest (weaker) analog |
| `osascript ... with administrator privileges` / `sudo` | `authorization.py:59-88` | Elevate for writes to protected install targets | UAC re-launch (`ShellExecuteW` "runas") — new code |
| `/bin/mkdir`, `/bin/mv`, `/bin/rm` literal argv | `install.py:293-311` | Privileged filesystem ops | Win32 API calls or PowerShell equivalents under elevation |
| `~/Library/LaunchAgents/*.plist` + `launchctl bootstrap/bootout` | `launch_agent.py:32-68,145-154` | Start-at-login menubar app | Startup-folder shortcut / `HKCU\...\Run` / Task Scheduler — new code |
| `os.getuid()` (unguarded) | `launch_agent.py:51`, `gui/app.py:829` | GUI-domain string / single-instance key | `AttributeError` on Windows; needs `getattr(os, "getuid", lambda: <pid or session id>)` guard like `refuse_root()` already has |
| `os.getpgid`/`os.killpg`/`SIGKILL`/`start_new_session` | `menubar_commands.py:42-59,299` | Cancel a running CLI subprocess (graceful → hard kill) | `CREATE_NEW_PROCESS_GROUP` + `CTRL_BREAK_EVENT` + `terminate()`/`taskkill` — real rewrite |
| `tmp.symlink_to(...)` | `install.py:685,719` | Restore previous symlink target / point `current` at official binary | Works but needs Developer Mode or elevation for unprivileged symlink creation on Windows |
| `AppKit`/`NSApplication` (guarded) | `gui/app.py:106-155` | Hide from Dock, force-foreground windows | Already correctly `sys.platform`-guarded; becomes a no-op on Windows (fine, Qt tray already behaves this way there) |
| `icon.setIsMask(True)` | `gui/icons.py:26` | macOS monochrome template-icon convention | Already documented as harmless no-op on Windows |
| Hardcoded `"claude"` (no extension) | `builder_v15.py:613`, `install.py:163`, `menubar_install.py:18`, `status.py:502`, `source_discovery.py:158`, `cli.py:1074` | Output/shim/cache/search filename | Needs `.exe`/`.cmd` extension handling throughout |
| `~/.claude-monkey` state dir | `paths.py:48-50` | All persistent state | Works via `Path.home()`, but non-idiomatic vs. `%LOCALAPPDATA%` |
| `"bin"` venv layout assumption | `menubar_install.py:82` (`app_gui_executable`) | Locate console-script inside provisioned venv | Windows venvs use `Scripts\`, not `bin/` |
| Protected-path list | `authorization.py:32-39` | Detect when a target needs elevation | POSIX paths only; needs `C:\Windows`, `C:\Program Files`, etc. |

---

## 4. Bugs found incidentally (worth fixing regardless of Windows work)

- **`gui/app.py:829`**: `SingleInstance(f"claude-monkey-gui-{os.getuid()}")` is unguarded, unlike the adjacent, correctly-guarded `refuse_root()` (`gui/app.py:235-237`). This will raise `AttributeError` the instant `main()` runs on any non-POSIX platform, before any of the deliberate `sys.platform` guards elsewhere in the same file even get a chance to matter.

---

## 5. Overall judgment: the 5 hardest porting problems, ranked

1. **Mach-O → PE binary-container parsing/rewriting (`macho.py` + `repack.py` + `builder_v15.py`).** This is the load-bearing core of the whole tool. `bun_graph.py`'s module-graph parser is genuinely portable once you can hand it the right byte range, but getting that byte range on a Windows Bun-compiled `claude.exe` requires reverse-engineering exactly how Bun embeds its module graph in a PE file (equivalent segment/section, equivalent to `LC_CODE_SIGNATURE`/`__LINKEDIT` handling for Authenticode and PE checksums/alignment), then writing and validating an entirely new parser/rewriter with the same "shift every offset table after a resize" correctness guarantees `macho.py` currently provides for Mach-O. This is weeks of reverse-engineering + implementation, not a refactor.

2. **Code signing / integrity model (`smoke.py`'s `codesign_sign`/`codesign_verify`, `builder_v15.py`'s `_apply_signing_v15`).** macOS requires ad-hoc re-signing after any binary modification or Gatekeeper (and even unsigned-binary execution checks) will block the patched build; Windows has no equivalent concept for locally-modified executables (no Gatekeeper), but Windows Defender SmartScreen/AV heuristics on a binary-patched executable are a real, if different, risk that this project has no strategy for yet. Likely resolves to "skip signing," but needs explicit validation that a patched, unsigned `claude.exe` actually runs cleanly under default Windows security posture.

3. **Privilege elevation and shim-persistence model (`authorization.py`'s `osascript`/`sudo`, `install.py`'s `chflags`/`UF_IMMUTABLE` lock).** The entire "install into a possibly-root-owned path, then lock it against the official updater silently reverting it" design is built on two macOS-specific primitives (`osascript`'s admin-privileges dialog and BSD's user-immutable flag) that have no Windows equivalents of comparable strength. UAC re-elevation and `FILE_ATTRIBUTE_READONLY`/ACL tricks are the closest analogs but are both weaker (Windows ACLs are more easily overridden/reset by an installer running as admin than a kernel-enforced immutable flag) and would need new field evidence (does the official Windows Claude installer even have a self-heal/reassert behavior at all? Unknown — the whole repair.py design exists because of an observed macOS-specific behavior).

4. **Login-launch / background-service model (`launch_agent.py`).** `~/Library/LaunchAgents` + `launchctl` is a from-scratch rewrite against Windows Startup mechanisms (Startup folder shortcut, `HKCU\...\Run`, or Task Scheduler with "run at logon"), each with different semantics around console-vs-background launch, log redirection, and whether they survive a user-initiated "disable startup item" toggle the way `launchctl bootout` does. `menubar_install.py`'s venv-provisioning half is portable but pointless without this.

5. **Shim launcher + PATH-interception semantics (`shim.py`, `install.py`'s file-lock/replace, executable-name conventions throughout).** Every module that hardcodes the bare name `"claude"` (six call sites found: `builder_v15.py:613`, `install.py:163`, `menubar_install.py:18`, `status.py:502`, `source_discovery.py:158`, `cli.py:1074`) needs conditional `.exe`/`.cmd` handling; the shim itself needs to change from a chmod'd Python shebang script to a `.cmd`/compiled launcher; and the "overwrite the resolved binary path in place" install strategy runs into Windows file-locking (`os.replace`/`Path.replace` fails on Windows if the target executable is currently running/mapped, unlike POSIX's rename-over-open-file semantics) — meaning the exact "safe hot-swap while `claude` might be running" transaction design in `install.py`/`repair.py` may need to change its atomicity story for Windows, not just its file paths.

Rounding out (not top-5 but real work): the POSIX process-group signal handling in `menubar_commands.py` (`os.getpgid`/`os.killpg`/`SIGKILL`), the unguarded `os.getuid()` bug in `gui/app.py:829` and `launch_agent.py:51`, and the `bin/` vs `Scripts/` venv-layout assumption in `menubar_install.py:82`.
