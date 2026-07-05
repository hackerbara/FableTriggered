# ClaudeMonkey / HarnessMonkey — Windows Port Brief

**Audience:** a fresh coding agent (or engineer) picking this up cold, with no prior context on this repo.
**Status:** research complete, no code written yet. This is a handoff, not a plan of record — adapt as you learn.
**Date compiled:** 2026-07-04.
**Backing research:** four full reports live in [`windows-port-research/`](windows-port-research/) — `codebase-porting-audit.md`, `claude-code-on-windows.md`, `bun-pe-format.md`, `windows-terminals-for-art.md`. (Also mirrored in the gitignored `.development/windows-port-research/` working area.) This brief summarizes and cross-references them; read the source reports before making irreversible design calls in their respective areas.

---

## 1. What this tool is (so you know what you're porting)

ClaudeMonkey is a userscript-style patch manager for the **Claude Code CLI**. Claude Code ships as a single **Bun-compiled standalone executable** (`bun build --compile`) with the entire JS app + Bun runtime + ripgrep embedded (~230 MB). ClaudeMonkey:

1. **Locates** the installed Claude binary (`source_discovery.py`).
2. **Parses** the Bun module graph embedded inside that binary (`macho.py` → `bun_graph.py`).
3. **Applies** declarative JS patch packages — text splices at verified byte ranges — to selected modules (`module_patch.py`, packages in `packages/`).
4. **Repacks** the binary with the edited module graph (`repack.py`, `builder_v15.py`).
5. **Re-signs** it (macOS ad-hoc `codesign`) and **smoke-tests** it (`smoke.py`).
6. **Installs a shim** at the path `claude` resolves to, so `claude` launches the patched build; the original is never modified and everything rolls back (`shim.py`, `install.py`, `repair.py`).
7. Offers a **PySide6 tray/GUI** with **start-at-login** (`gui/`, `launch_agent.py`).

Fail-closed is a core value: packages pin an exact Claude **version + SHA-256**; a mismatch refuses to build rather than producing something weird.

**The porting thesis, one sentence:** the binary-format core and all pure-logic modules port with little-to-no change; the OS-integration layer (shim launcher, start-at-login, elevation, process control) needs Windows-native rewrites; and the single largest *new* piece of code is a PE-container patcher to replace the Mach-O one — which is materially **simpler** than the Mach-O path, not harder.

---

## 2. Ground truth about Claude Code on Windows

(Full detail + sources: `claude-code-on-windows.md`.)

- **It's the same Bun `--compile` toolchain as macOS.** Confirmed (not inferred) via Bun's `InternalName: bun` PE metadata surfacing in a real shipped Windows stub (anthropics/claude-code#69884). So the embedded-module-graph approach transfers conceptually intact.
- **Distribution:** native installer is Anthropic's recommended path (`irm https://claude.ai/install.ps1 | iex`). The npm package installs the same native binary via a platform optional-dependency (`@anthropic-ai/claude-code-win32-x64`), **not** JS-under-node. WinGet exists but doesn't auto-update. WSL is supported (runs the Linux binary) but out of scope here — target **native Windows**.
- **Install topology (this is what `source_discovery.py` must find):**
  - Launcher stub: `%USERPROFILE%\.local\bin\claude.exe`
  - Versioned real binaries: `%USERPROFILE%\.local\share\claude\versions\<version>\...`
  - Config/state: `%USERPROFILE%\.claude` and `%USERPROFILE%\.claude.json`
  - **Everything is per-user. No root-owned install path.** (Big simplification — see §5.)
- **Signing:** `claude.exe` is Authenticode-signed by "Anthropic, PBC." **You do not need to re-sign** — see the PE section (§4). There is no Gatekeeper equivalent; unsigned exes run.
- **Windows locks running executables.** You cannot overwrite/rename a running `.exe` the way POSIX lets you replace an open inode. Anthropic's own updater has shipped repeated bugs here (anthropics/claude-code #28285, #51954, #69884). Your install/rebuild/repair flow must use rename-old-then-place-new and detect the locked-file case explicitly.
- **Open unknown — verify on real hardware:** does the official Windows updater silently clobber a replaced stub the way macOS does? The entire `repair.py` + shim-locking design exists because of an *observed macOS behavior*. Don't assume Windows behaves identically; measure it before porting the immutability/repair machinery 1:1.

---

## 3. Per-module port map

(Full table with file:line refs: `codebase-porting-audit.md` §1 and §3. Reproduced here in condensed form.)

**Legend:** PORTABLE = works as-is · SHALLOW = minor fixes (paths, exe names, subprocess flags) · DEEP = needs a Windows-native counterpart.

| Module(s) | Class | Port action |
|---|---|---|
| `bun_graph.py`, `module_patch.py`, `manifest_v2.py`, `package_model.py`, `payloads.py`, `prompts.py`, `progress.py`, `reports*.py`, `cli_json.py`, `config.py`, `menubar_state.py`, all `gui/pages/*`, `gui/commands.py`, `gui/*model*.py`, `gui/settings_window.py`, `gui/tray.py` | **PORTABLE** | None. `bun_graph.py` is the crown jewel — OS-agnostic Bun-format parser, works on the Windows payload untouched. |
| `source_discovery.py` | SHALLOW | Add `.exe` to the executable name; `os.access(_, X_OK)` is a no-op on Windows (becomes "exists") — add a real check or accept the drift. Add Windows install paths (`%USERPROFILE%\.local\...`). |
| `paths.py`, `config.py` | SHALLOW | State root `~/.claude-monkey` works via `Path.home()` but is non-idiomatic; prefer `%LOCALAPPDATA%\ClaudeMonkey`. Drop the `HOME`-first lookup. |
| `smoke.py` | SHALLOW code / DEEP function | Machinery is portable `subprocess.run` (no pty/termios — good). But `codesign_sign`/`codesign_verify` are macOS tools; on Windows these become **no-ops** (skip signing — see §4). |
| `builder_v15.py`, `binary_inspect.py` | DEEP | Swap the Mach-O layout/sign calls for the PE path (§4). Most of the orchestration logic around it is reusable. |
| `macho.py`, `repack.py` | DEEP (replace) | Write a **`pe.py` sibling** (§4). Keep `macho.py`; select by platform. `repack.py`'s Mach-O offset-shifting has no PE analog needed (PE `.bun` is last-in-file). |
| `shim.py`, `shim_entry.py` | DEEP | Shebang+chmod script → Windows launcher (§6). |
| `install.py`, `repair.py` | DEEP | `chflags UF_IMMUTABLE` shim-lock, `symlink_to`, in-place overwrite of a running exe all need Windows rethink (§5, §6). |
| `authorization.py` | DEEP (maybe DELETE) | `osascript`/`sudo` elevation + POSIX protected-path list. **Likely unnecessary on Windows** since installs are per-user (§5). |
| `launch_agent.py`, `menubar_install.py` | DEEP | LaunchAgent plist + `launchctl` → `HKCU\...\Run` / Startup shortcut / Task Scheduler (§7). |
| `menubar_commands.py` | DEEP | `os.getpgid`/`os.killpg`/`SIGKILL`/`start_new_session` → `CREATE_NEW_PROCESS_GROUP` + `CTRL_BREAK_EVENT` + `terminate()`/`taskkill /T /F` (§7). |
| `gui/app.py` | SHALLOW + BUG | AppKit calls already `sys.platform`-guarded. **Fix the unguarded `os.getuid()` at line 829** (and `launch_agent.py:51`) — instant `AttributeError` on Windows. |
| `gui/icons.py`, `gui/window_model.py` | SHALLOW | `setIsMask(True)` no-ops harmlessly. Replace hardcoded `/usr/local/bin/claude`, `/opt/homebrew/bin/claude` UI suggestions with Windows paths. |
| `cli.py`, `status.py` | SHALLOW | ~6 hardcoded bare-name `"claude"` call sites need `.exe` handling (`builder_v15.py:613`, `install.py:163`, `menubar_install.py:18`, `status.py:502`, `source_discovery.py:158`, `cli.py:1074`). |

**Two latent bugs to fix regardless of the port:** unguarded `os.getuid()` in `gui/app.py:829` and `launch_agent.py:51`.

---

## 4. The PE patcher — full spec

This is the biggest new piece and the one most reducible to a precise spec. (Authoritative detail + Bun source refs: `bun-pe-format.md`.)

**Key facts that make this tractable:**
- The embedded module-graph payload format is **byte-identical across macOS/Windows/Linux** — same `"\n---- Bun! ----\n"` 16-byte trailer, same 32-byte `Offsets` struct, same 52-byte `CompiledModuleGraphFile` records, same 8-byte `StringPointer`. Survived Bun's May–June 2026 Zig→Rust rewrite unchanged. **So `bun_graph.py` parses the Windows payload as-is.**
- On Windows the payload lives in a PE section literally named **`.bun`** (`[u64 LE length][payload][zero-pad to file_alignment]`), and Bun **always appends it as the last section in the file**. Growing/shrinking it therefore moves nothing else — no analog to Mach-O's `__LINKEDIT` shifting.
- **No cryptographic re-sign is required.** Bun's own compiler strips Authenticode on every Windows build (`StripMode::StripAlways`). Unsigned exes run.

**What `pe.py` must do (step-by-step):**
1. Parse PE headers: DOS (`e_magic==0x5A4D`) → `e_lfanew` → PE sig (`0x00004550`) → optional header (require PE32+ `magic==0x020B`, x64) → section table.
2. Find the section whose 8-byte name is `.bun\0\0\0\0` (match 4 bytes to be safe).
3. Read payload: `payload_len = u64_le(raw[0:8])`; payload = `raw[8:8+payload_len]`. Hand payload to the existing `bun_graph.py` parser (verify trailer, read `Offsets` from `len-32-16`, decode module table).
4. Apply the module edit in the flat payload buffer. **Same-length swap = overwrite in place** (trivial, mirrors current macOS same-length patching). **Resize** requires: shift bytes after the edit, adjust every downstream `StringPointer.offset`, update `Offsets.byte_count`, re-append `Offsets`+trailer. (Resizing is genuinely feasible on PE — unlike the Mach-O path you may have avoided it on — because `.bun` is last-in-file.)
5. **Strip Authenticode if present** (mirror Bun's order — do this before resizing): if `OptionalHeader.DataDirectory[4]` (SECURITY) is non-zero, zero that directory entry, clear `IMAGE_DLLCHARACTERISTICS_FORCE_INTEGRITY`, truncate the file at the 8-byte-aligned old cert offset.
6. Resize `.bun` if needed: `size_of_raw_data = align_up(new_len+8, file_alignment)`, `virtual_size = new_len+8`; `virtual_address`/`pointer_to_raw_data` unchanged; zero-fill slack.
7. Fix optional header: `size_of_image = align_up(bun.virtual_address + bun.virtual_size, section_alignment)`.
8. **Recompute PE checksum:** zero the field, run Microsoft's 16-bit-word-sum-with-carry-fold + file-length algorithm (identical to `pefile.generate_checksum()` — you may just depend on `pefile`).
9. Write out. No re-sign.

**Prior art to lean on / validate against:** [`vicnaum/bun-demincer`](https://github.com/vicnaum/bun-demincer) round-trips Bun binaries on all three platforms and independently corroborates the format byte-for-byte.

**PE-specific gotcha — bytecode staleness (medium confidence):** if Anthropic ships modules built with `--bytecode`, each such module carries a precompiled JSC bytecode blob matched only by a path string, *not* a content hash. Editing that module's source while leaving stale bytecode could cause silent wrong behavior. Safe default: when you edit a module, zero its `bytecode` and `module_info` `StringPointer`s (`{0,0}`) so JSC re-parses the fresh source. Confirm whether the shipped binary even uses bytecode first.

---

## 5. Install / elevation / locking — how Windows changes the model

- **Elevation probably disappears.** `authorization.py`'s whole reason to exist is writing into root-owned paths like `/usr/local/bin`. Windows Claude installs per-user under `%USERPROFILE%`, writable without UAC. **Recommended: skip elevation entirely on Windows**; only revisit if you discover a machine-wide install variant. This deletes one of the five "hard" macOS subsystems outright.
- **Shim-locking against the official updater** (`chflags UF_IMMUTABLE`) has no strong Windows analog. `FILE_ATTRIBUTE_READONLY` or an ACL deny-write is far weaker (an admin installer overrides it). **Don't build this until you've confirmed the Windows updater actually clobbers the shim** (see §2 open unknown). If it doesn't, you may not need the lock or much of `repair.py`.
- **Running-exe file lock is the real new constraint.** Replacing the shim/binary while `claude` may be running needs: write new file alongside, then `MoveFileEx(..., MOVEFILE_REPLACE_EXISTING)` — or schedule replace-on-reboot (`MOVEFILE_DELAY_UNTIL_REBOOT`) — and surface a clear "close Claude and retry" message on failure rather than silently no-opping. `os.replace()` raises on Windows if the target is open; handle it.
- **Symlinks** (`install.py:685,719`) need Developer Mode or elevation on Windows — prefer a copy or a launcher stub over symlinks.

---

## 6. The shim launcher

The current shim is a `#!/usr/bin/env python3` script `chmod 0o755`'d over the resolved `claude` path. On Windows that's not executable by `CreateProcess`. Options, best first:

1. **Tiny compiled `claude.exe` stub** that resolves the launch target and `CreateProcess`es it. Cleanest UX (one file named `claude.exe` on PATH, behaves like the real thing), but adds a compiled artifact to the build.
2. **`claude.cmd` batch wrapper** calling `python -m claude_monkey.shim_entry`. No compilation, but `.cmd` on PATH has quirks (arg quoting, `Ctrl-C` handling, an extra shell process in the tree).

`shim_entry.py`'s logic is portable; only the final `os.execvpe` differs — on Windows it's emulated (spawn+wait+exit), which is functionally fine for a blocking CLI parent. Note `.chmod(0o755)` only toggles the read-only bit on Windows — it does not "make executable"; execution is by extension/association.

---

## 7. Start-at-login and process control (GUI)

- **Start-at-login:** replace `~/Library/LaunchAgents/*.plist` + `launchctl bootstrap/bootout` with one of: a `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` value (simplest), a Startup-folder `.lnk`, or Task Scheduler `schtasks /create /sc onlogon` (most controllable). `menubar_install.py`'s venv-provisioning half is reusable but note Windows venvs use `Scripts\`, not `bin/` (`app_gui_executable` at `menubar_install.py:82` hardcodes `bin/`).
- **Process cancel:** `menubar_commands.py`'s graceful→hard kill uses POSIX process groups. Windows rewrite: spawn with `creationflags=subprocess.CREATE_NEW_PROCESS_GROUP`, cancel via `send_signal(CTRL_BREAK_EVENT)`, escalate with `terminate()` / `taskkill /T /F /PID`.
- **GUI otherwise ports well:** PySide6 `QSystemTrayIcon` already gives tray-only, no-taskbar behavior on Windows, so the guarded AppKit "accessory policy" calls correctly become no-ops. Fix the unguarded `os.getuid()` (§3).

---

## 8. Terminals for the art packages

Scope is narrowed to the **published cosmetic packages**, which need only: 24-bit truecolor, dense half-block / box-drawing per-cell RGB redraw, good glyph coverage, ordinary keyboard input. **No mouse reporting, no inline images** — those are out of scope, which removes the two features Windows/ConPTY handles worst. (Full matrix + sources: `windows-terminals-for-art.md`.)

- **#1 Windows Terminal (1.24+):** default on Win11, AtlasEngine renders block/box glyphs "pixel-perfect," ConPTY 1.22 rewrite doubled SGR throughput. Best default target.
- **#2 WezTerm:** bundles its own ConPTY (independent of OS build), cross-platform config parity with the Mac setup.
- **#3 Alacritty:** fallback only — multi-year backlog of half-block/box-drawing glyph bugs.
- **Ghostty:** no official Windows build; community fork "Winghostty" is ~2.5 months old — watch-list, not a target.

**Two things to bake into packages:**
1. **Detect via `WT_SESSION` / `TERM_PROGRAM`, not `COLORTERM`** — Windows Terminal renders truecolor but never sets `COLORTERM` (false-negative trap).
2. **Keep grid cells to box-drawing/half-block glyphs** (the scenes already do) — Windows Terminal's Unicode width is user-configurable three ways, and only these glyphs are unambiguously 1-column across all modes.

**Residual risk to benchmark, not assume:** sustained high-frequency animation redraw (flames/water loops) under ConPTY — 2× faster since the rewrite but still a translation layer, not native like Ghostty-on-macOS.

---

## 9. What can be built on a Mac vs. what needs a Windows box

**Developable + testable on macOS right now:**
- `pe.py` and the repack path. The Windows `claude.exe` is a plain download (`downloads.claude.ai/claude-code-releases/<ver>/win32-x64/claude.exe`); PE parsing/patching is pure byte manipulation. Build it against a real downloaded binary with the existing pinned-SHA test style, and validate round-trips against `bun-demincer`.
- All SHALLOW path/exe-name/config changes and the two bug fixes.
- Package/manifest logic.

**Requires a real Windows machine:**
- Does a patched, unsigned `claude.exe` actually launch and run cleanly under default Defender/SmartScreen? (Bun binaries have a history of Defender false positives — this is the #1 thing to de-risk early.)
- Does the official Windows updater clobber the shim? (Determines how much of `repair.py` / shim-locking you need.)
- Shim launcher UX, start-at-login, GUI tray behavior, process-cancel.
- ConPTY animation throughput and glyph fidelity across terminals.

---

## 10. Suggested build order

1. **De-risk the two unknowns that could kill the approach**, on a Windows box, before building much: (a) patch a downloaded `claude.exe` by hand (even with `bun-demincer` + a hex editor), strip signature, confirm it runs under stock Defender; (b) observe whether the official updater reverts a replaced stub.
2. **`pe.py` + repack path** (Mac-developable, TDD against a real binary). Reuse `bun_graph.py` untouched. This proves the core.
3. **Platform-select plumbing**: exe-name handling, `paths.py` to `%LOCALAPPDATA%`, `source_discovery.py` Windows paths, skip `codesign`, fix the two `os.getuid()` bugs.
4. **Shim launcher** (§6) + Windows-safe install/replace with file-lock handling (§5). Decide `repair.py` scope based on step 1(b).
5. **GUI**: fix guards, process-cancel rewrite, start-at-login (§7). Mostly reuse.
6. **Package/terminal validation** (§8): pick 1–2 published art packages, add `WT_SESSION` detection + graceful degradation, benchmark redraw.

**Effort intuition:** the core patcher is *smaller* than the existing Mach-O code, not larger. The real cost is the OS-integration long tail (shim, start-at-login, install locking, GUI process control) and the hands-on Windows validation loop — not the binary format. Elevation likely drops out entirely. Treat steps 1–2 as the go/no-go gate.

---

## 11. Anti-goals / scope guards

- **Native Windows only** — not WSL (WSL runs the Linux binary; a separate, easier story if ever wanted).
- **No re-signing** unless Defender testing (step 1a) proves it's required — and even then, self-signing shows "unknown publisher," so weigh it.
- **Don't port `repair.py` / shim-locking 1:1** until the updater-clobber behavior is confirmed on Windows.
- **Don't build elevation** unless a machine-wide install path turns up.
- **Mouse reporting and inline images are out of scope** for the art — don't reintroduce them.

---

## 12. Fastest spike path — get *a* patched binary built, installed, and shimmed

This is deliberately **not** the productionized path in §10. The goal here is the shortest route to a running, visibly-patched `claude.exe` on a Windows box — no smoke tests, no fail-closed SHA pinning, no GUI, no start-at-login, no rollback machinery. Prove the chain works end to end; harden later. Budget: an afternoon.

**The one trick that collapses the work: patch same-length, in place.** A same-length byte edit inside the `.bun` payload means you touch *nothing else* — no `StringPointer` offsets, no `Offsets.byte_count`, no section resize, no `size_of_image`. For a spike you can even skip the PE checksum recompute (Windows does not enforce the PE checksum for ordinary user-mode EXE launch — it's only checked for drivers/boot images) and skip signature stripping (an invalid Authenticode signature does not block a user-mode exe from *running* — it only affects SmartScreen/AV reputation, which you can dismiss manually during a spike). So the minimal spike is: find a visible string in a JS module, overwrite it with a different string of the exact same byte length, save, run.

**Step 0 — grab the binary (don't touch the installed one yet).**
```
copy "%USERPROFILE%\.local\share\claude\versions\<ver>\claude.exe" "%USERPROFILE%\claude-spike.exe"
```
Work on the copy. (`<ver>` = whatever's in that `versions\` dir.)

**Step 1 — reuse what already ports, hand-roll only the PE locate.** On Windows, `bun_graph.py` and `module_patch.py` from this repo run **unchanged** — they only need the raw `.bun` payload bytes. The only new code is ~30 lines to pull those bytes out of the PE (vs. the Mach-O path `macho.py` does today):
```python
import struct, pathlib
data = bytearray(pathlib.Path(r"%USERPROFILE%\claude-spike.exe".replace("%USERPROFILE%", str(pathlib.Path.home()))).read_bytes())
e_lfanew = struct.unpack_from("<I", data, 0x3C)[0]                 # DOS header -> PE offset
assert data[e_lfanew:e_lfanew+4] == b"PE\0\0"
num_sections = struct.unpack_from("<H", data, e_lfanew+6)[0]
opt_size     = struct.unpack_from("<H", data, e_lfanew+20)[0]
sec_table    = e_lfanew + 24 + opt_size
for i in range(num_sections):
    off = sec_table + i*40
    name = data[off:off+8].rstrip(b"\0")
    if name == b".bun":
        raw_size = struct.unpack_from("<I", data, off+16)[0]      # SizeOfRawData
        raw_ptr  = struct.unpack_from("<I", data, off+20)[0]      # PointerToRawData
        break
payload_len = struct.unpack_from("<Q", data, raw_ptr)[0]          # [u64 LE length][payload...]
payload_start = raw_ptr + 8
payload = data[payload_start : payload_start + payload_len]
# -> hand `payload` to bun_graph.parse_bun_section() to find modules, pick a target
```

**Step 2 — same-length edit.** Use `bun_graph.py` to locate a module's `contents` span, find a harmless visible string in it (grep the decoded module for something that surfaces at runtime — a banner/help/label string), and overwrite it with an equal-length replacement **directly in `data`** at `payload_start + <string offset within payload>`. Same length = done; write `data` back to `claude-spike.exe`. (If you can't resist a length change, that's the §4 resize path — but don't, for the spike.)

**Step 3 — shim it, the lazy way.** Skip the compiled-stub and the immutable-lock entirely. Two options, both a few seconds:
- **Overwrite-in-place** (simplest, most "installed"): close all Claude instances (Windows locks the running exe), then `copy /y claude-spike.exe` over the versioned binary you copied from in Step 0 — the existing `%USERPROFILE%\.local\bin\claude.exe` launcher will now run your patched build with no shim at all. Keep the pristine copy from Step 0 as your manual rollback.
- **`.cmd` shim on PATH** (non-destructive): drop `claude.cmd` in a folder placed *ahead* of `.local\bin` on `PATH`:
  ```bat
  @echo off
  "%USERPROFILE%\claude-spike.exe" %*
  ```
  Now `claude` resolves to your wrapper → patched binary; delete the `.cmd` to revert.

**Step 4 — run it.** `claude --version` / launch it and look for your changed string. If SmartScreen/Defender interrupts on first run, that's the reputation prompt (dismiss it) — a real signal for §9's de-risking, but not a spike blocker.

**What you've proven when this works:** the full chain — locate binary → extract `.bun` → parse module graph (reused code) → edit → repack → launch patched — works on Windows. Everything in §10 after that (resize support, checksum/sig hygiene, fail-closed pinning, a real shim, GUI, start-at-login) is hardening on top of a chain you've already shown runs. **What it deliberately skips and why it's safe to skip for a spike:** checksum recompute (not enforced for user-mode exes), signature stripping (invalid sig doesn't block execution), resize bookkeeping (avoided by same-length editing), rollback tooling (you kept a manual copy).
