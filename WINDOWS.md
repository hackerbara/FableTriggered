# ClaudeMonkey on Windows — status & handoff

**TL;DR:** The hard, novel part — patching the Windows `claude.exe` binary — is **built and tested on macOS against a real downloaded `claude.exe`**. Everything that could be finished and verified without a Windows machine is done. What remains is the OS-integration layer (install/launch/start-at-login) and per-package art re-authoring, none of which can be meaningfully validated off a real Windows box. This file is the map for whoever (or whatever agent) picks that up.

**This is a spike, not shipping Windows support.** No patched binary has ever been *executed* on Windows — a Windows PE can't run on macOS. Treat everything below the "Done" line as unverified until run on real hardware.

---

## Why Windows works at all (the mechanism)

Claude Code ships as a Bun `--compile` standalone executable on every platform. The embedded JS module-graph payload lives in a container section — `__BUN`/`__bun` on macOS Mach-O, a section literally named **`.bun`** on Windows PE — and the payload format (`"\n---- Bun! ----\n"` trailer, 32-byte `Offsets`, 52-byte module records) is **byte-identical across platforms**. So the payload parser (`bun_graph.py`) is reused unchanged; only the outer container differs. The PE patcher is materially *simpler* than the Mach-O one because `.bun` is always the **last section in the file**, so resizing it moves nothing else.

Full background: `docs/windows-port-brief.md` (start here) and the four research reports under `docs/windows-port-research/`.

---

## ✅ Done and tested on macOS

All of this has automated tests. Real-binary tests run against a downloaded Windows `claude.exe` (2.1.201) and pass; they self-skip if the binary is absent.

| Piece | File | What it does |
|---|---|---|
| PE parser | `src/claude_monkey/pe.py` — `find_pe_layout` | Parses PE32+ headers, locates the `.bun` section, exposes Authenticode/checksum offsets. Raises `PEError` (never `struct.error`) on malformed input. |
| Resize repack | `src/claude_monkey/pe.py` — `repack_changed_modules` | Strips Authenticode, applies arbitrary-length module edits, resizes `.bun`, fixes `SizeOfImage`, recomputes the PE checksum. Mirrors the Mach-O `repack.py` interface. |
| PE checksum | `src/claude_monkey/pe.py` — `pe_checksum` | Hand-rolled Microsoft image checksum. Reproduces the real binary's stored checksum exactly. No `pefile` dependency. |
| Format dispatch | `src/claude_monkey/binary_format.py` | `detect_binary_format` / `locate_bun_section` / `repack_for_format` route Mach-O vs PE. The Mach-O path is a pure refactor — unchanged behavior. |
| Payload prefix | `src/claude_monkey/bun_graph.py` | Accepts the Windows bunfs path prefix `B:/~BUN/` (macOS uses `/$bunfs/`). |
| Build hygiene | `src/claude_monkey/builder_v15.py` | PE builds skip macOS `codesign` and emit `claude.exe` instead of `claude`. |
| Manifest format | `src/claude_monkey/manifest_v2.py` | Recognizes `requiredBinaryFormat: "bun_standalone_pe64"`. |
| Platform plumbing | `src/claude_monkey/platform_support.py` | Windows state dir (`%LOCALAPPDATA%\ClaudeMonkey`), executable name (`claude.exe`), install-path discovery (`%USERPROFILE%\.local\bin\claude.exe` + versioned installs), and a real executability check (`os.access(X_OK)` is a no-op on Windows). Wired into `paths.py` and `source_discovery.py`. macOS behavior byte-for-byte unchanged. |
| End-to-end proof | `scripts/win_spike_driver.py`, `tests/fixtures_win_package/`, `tests/test_windows_pipeline.py` | Drives a **real length-changing patch** through the genuine `manifest → module_patch → PE-repack` vocab against the real `claude.exe`, satisfying fail-closed pinning, producing a structurally-valid patched `claude.exe`. |

### Run the spike (on macOS or Windows)

```bash
# 1. Download the pinned Windows binary (never committed):
mkdir -p ~/.local/share/claude-monkey-dev/win32-x64/2.1.201
curl -s -o ~/.local/share/claude-monkey-dev/win32-x64/2.1.201/claude.exe \
  https://downloads.claude.ai/claude-code-releases/2.1.201/win32-x64/claude.exe

# 2. Run the pipeline test + driver:
uv run pytest tests/test_windows_pipeline.py -v
uv run python scripts/win_spike_driver.py      # writes build/win-spike/claude.exe
```

The driver builds a patched `claude.exe`. On macOS you can only inspect it (parse, checksum, confirm the edit is present). On Windows you can actually launch it — that's the next section.

---

## ❌ Not done — needs a real Windows box

Three buckets, most-load-bearing first. None is conceptually blocked; the cost is a Windows machine and an iteration loop.

### 1. Validation (verify the assumptions the whole design rests on)

These are *measurements*, not code. Do them first — they determine how much of bucket 2 you actually need.

- **Does a patched, unsigned `claude.exe` launch under stock Defender/SmartScreen?** Bun binaries have a history of Defender false positives — this is the #1 de-risk. Build one with the driver above, run it, log what happens.
- **Does the official Windows updater clobber a replaced binary/shim?** The entire `repair.py` + shim-locking design on macOS exists because of an *observed macOS behavior*. Do NOT assume Windows behaves the same — measure it. If the updater leaves a replaced launcher alone, you can skip most of `repair.py`.
- **ConPTY animation throughput & glyph fidelity** for the art packages, across Windows Terminal (primary target, 1.24+), WezTerm (backup), Alacritty (fallback). See `docs/windows-port-research/windows-terminals-for-art.md`.

### 2. OS-integration layer (build these; they're Win32 glue that can't run on macOS)

Pointers into the brief for each; the per-file port map is `docs/windows-port-brief.md` §3, and §5–§7 have the detail.

- **Shim launcher** (§6): replace the `#!/usr/bin/env python3` + `chmod` shim with either a tiny compiled `claude.exe` stub (cleanest) or a `claude.cmd` wrapper. For a first pass, a `.cmd` on `PATH` pointing at the patched binary is legitimate:
  ```bat
  @echo off
  "%USERPROFILE%\.claude-monkey\bin\claude.exe" %*
  ```
- **Install / replace with file-lock handling** (§5): Windows locks running `.exe` files — you can't overwrite an open one like POSIX. Use `MoveFileEx(..., MOVEFILE_REPLACE_EXISTING)` (or `MOVEFILE_DELAY_UNTIL_REBOOT`), and surface a clear "close Claude and retry" on failure. `os.replace()` raises if the target is open — handle it. Relevant file: `install.py` (its macOS `chflags`/symlink logic is already `sys.platform == "darwin"`-guarded, so it no-ops rather than crashing on Windows — but it doesn't yet *do* the Windows path).
- **`repair.py` / shim-locking**: don't port 1:1 until validation bucket #1 tells you the updater actually clobbers. The macOS `chflags UF_IMMUTABLE` lock has no strong Windows analog (`FILE_ATTRIBUTE_READONLY`/ACLs are weaker).
- **Start-at-login** (§7): replace the LaunchAgent plist + `launchctl` with `HKCU\...\Run`, a Startup `.lnk`, or `schtasks /create /sc onlogon`. Files: `launch_agent.py`, `menubar_install.py` (note Windows venvs use `Scripts\`, not `bin/`).
- **GUI process-cancel** (§7): `menubar_commands.py` uses POSIX process groups; rewrite with `CREATE_NEW_PROCESS_GROUP` + `CTRL_BREAK_EVENT` + `taskkill /T /F`.
- **Elevation**: probably delete entirely. `authorization.py` exists to write root-owned macOS paths; Windows installs are per-user under `%USERPROFILE%`. Only revisit if a machine-wide install variant turns up.

The GUI (`gui/*`, PySide6 `QSystemTrayIcon`) otherwise ports well — the AppKit calls are already `sys.platform`-guarded and become no-ops. The `os.getuid()` latent bugs were already fixed (commit `77a797b`).

### 3. Per-package art re-authoring (per package, plus visual verification)

**Critical finding — the port brief was wrong about this.** The brief (§12 step 3) assumed a patch's target module text is platform-identical and only the outer binary differs, so re-pinning would be a hash swap. **It is not.** For Claude Code 2.1.201, the win32-x64 bundle is minified with **different symbol names** than darwin-arm64:

- `cli.js` differs in both length (18745538 vs 18700756) and SHA-256.
- Renamed identifiers: the app-shell function `VKo`→`eKo`, `MXe`→`OJe`, the `Box` component `B` is a different name, and `t4`/`HS`/`fde`/`A_` all differ.

So porting a visual package like `capybara-onsen` to Windows means **re-authoring every anchor** in `examples/capybara-onsen-generator/generate_package.py`'s `VERSION_FRAGILE_ANCHORS` and remapping every host identifier referenced in the replacement glue against the Windows bundle's minified names — exactly the maintenance surface that file's header comment warns about. You can *start* this on macOS (extract the win32 `cli.js` and diff the structure), but whether the resulting TUI renders correctly — gutters, modal containment, resize — can only be confirmed by running it in Windows Terminal.

The spike deliberately proves the pipeline with a **minimal marker patch** (`tests/fixtures_win_package/`) instead, so the machinery is de-risked independently of this per-package effort. When you re-author capybara, the build/repack path it flows through is already done.

---

## Key facts a Windows agent must not re-derive

- **No cryptographic re-sign is required.** Bun's compiler strips Authenticode on every Windows build; unsigned exes run. There's no Gatekeeper equivalent. `pe.py` strips the cert as part of repack.
- **`.bun` is the last section in the file** — resizing it moves nothing else. No offset-shifting analog to Mach-O `__LINKEDIT`.
- **Windows module paths use the `B:/~BUN/` prefix**, not `/$bunfs/`.
- **Detect truecolor terminals via `WT_SESSION`/`TERM_PROGRAM`, not `COLORTERM`** — Windows Terminal renders truecolor but never sets `COLORTERM` (false-negative trap). Keep art to box-drawing/half-block glyphs (unambiguously 1-column across Windows Terminal's width modes).
- **Native Windows only** — not WSL (WSL runs the Linux binary; separate, easier story).
- **Install topology** (what discovery targets): launcher `%USERPROFILE%\.local\bin\claude.exe`, versioned binaries `%USERPROFILE%\.local\share\claude\versions\<version>\`, config `%USERPROFILE%\.claude` + `%USERPROFILE%\.claude.json`. Everything per-user — no root-owned path.

---

## Reference material

- `docs/windows-port-brief.md` — the full porting brief (per-module map, PE spec, spike path).
- `docs/windows-port-research/` — four backing reports (codebase audit, Claude-on-Windows ground truth, Bun PE format, terminals).
- `docs/superpowers/plans/2026-07-05-windows-pe-spike-mac-side.md` — the implementation plan this spike executed, with its own "Deferred to a Windows box" section.
- Prior art for the PE format: [`vicnaum/bun-demincer`](https://github.com/vicnaum/bun-demincer) round-trips Bun binaries on all three platforms.
