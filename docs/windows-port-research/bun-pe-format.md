# Bun `--compile` Standalone Executable Embedding: macOS Mach-O vs Windows PE

**Research date:** 2026-07-04. All source citations point at Bun's `main` branch, commit `fb50cce9285cfc7420ca93382e30872c1588cbe1`.

## Critical context you need first: Bun rewrote this subsystem from Zig to Rust in May–June 2026

`src/StandaloneModuleGraph.zig` **no longer exists** on `main`. PR [oven-sh/bun#30412 "Rewrite Bun in Rust"](https://github.com/oven-sh/bun/pull/30412) (merged 2026‑05‑14) ported the whole runtime, and a follow-up cleanup pass, PR [#31783](https://github.com/oven-sh/bun/pull/31783) (merged 2026‑06‑05), finished draining the port's TODOs. The logic you're used to now lives at:

- [`src/standalone_graph/StandaloneModuleGraph.rs`](https://github.com/oven-sh/bun/blob/fb50cce9285cfc7420ca93382e30872c1588cbe1/src/standalone_graph/StandaloneModuleGraph.rs) — serialization (`to_bytes`), deserialization (`from_bytes`), embedding orchestration (`inject`, `to_executable`)
- [`src/exe_format/macho.rs`](https://github.com/oven-sh/bun/blob/fb50cce9285cfc7420ca93382e30872c1588cbe1/src/exe_format/macho.rs) — Mach-O section writer + ad-hoc signer
- [`src/exe_format/pe.rs`](https://github.com/oven-sh/bun/blob/fb50cce9285cfc7420ca93382e30872c1588cbe1/src/exe_format/pe.rs) — PE section writer / Authenticode stripper
- [`src/exe_format/elf.rs`](https://github.com/oven-sh/bun/blob/fb50cce9285cfc7420ca93382e30872c1588cbe1/src/exe_format/elf.rs) — ELF section writer (Linux/FreeBSD)
- [`src/jsc/bindings/c-bindings.cpp`](https://github.com/oven-sh/bun/blob/fb50cce9285cfc7420ca93382e30872c1588cbe1/src/jsc/bindings/c-bindings.cpp) (lines ~1056–1138) — the C++ runtime-side lookup that finds the embedded section at process startup on each platform

Good news for you: per the rewrite's own description ("architecture and data structures remain largely the same") and cross-checked against [PR #15525](https://github.com/oven-sh/bun/pull/15525) (the original Zig-era commit that introduced the `__BUN,__bun` Mach-O section) and third-party tool [vicnaum/bun-demincer](https://github.com/vicnaum/bun-demincer), **the on-disk container format is unchanged** — same section names, same struct layouts, same magic trailer. Only the implementing language changed. A patcher written against the old Zig-era format should still work against binaries produced by current Bun; you don't need format-level changes, just be aware the reference implementation moved.

Current dev version in `package.json` is `1.4.0-dev`; latest published stable is `1.3.14`.

---

## 1. General mechanism (all platforms)

`StandaloneModuleGraph::to_bytes()` (line 708) serializes everything into one flat `Vec<u8>` "payload":

```
[per-module data: name\0, contents\0, sourcemap blob, bytecode (128-byte aligned), module_info, bytecode_origin_path\0]  × N modules
[module table: CompiledModuleGraphFile[N]]   ← Offsets.modules_ptr points here
[compile_exec_argv\0]                        ← Offsets.compile_exec_argv_ptr points here
[Offsets struct, 32 bytes]
[TRAILER: "\n---- Bun! ----\n", 16 bytes]     ← const at line 530
```

That whole payload is then handed to `inject()` (line 1061), which dispatches per target OS:

| OS | Mechanism | Where |
|---|---|---|
| macOS | Inserts/grows a real Mach-O segment+section named `__BUN,__bun` | `bun_macho::MachoFile::write_section` + `build_and_sign` |
| Windows | Adds a real PE section named `.bun` | `bun_pe::PEFile::add_bun_section` |
| Linux/FreeBSD | Finds and **grows an existing** `.bun` ELF section (already reserved in the template binary at build time) | `bun_elf::ElfFile::write_bun_section` |
| anything else (currently unreachable — only `Wasm` falls through) | Raw append to EOF + trailing 8-byte length | catch-all `_ =>` arm, line 1427 |

At **runtime**, the section is located with a purely platform-native lookup (no scanning trailer bytes at EOF the way very old Bun once did — see the code comment at line 1: "Originally... read the last 4096 bytes... **`-- Bun --\n`**"; that hack is gone):

- **macOS**: a statically-linked symbol `BUN_COMPILED` lives *inside* the `__BUN,__bun` section itself (`c-bindings.cpp` line 1069). Its address is resolved by the linker/loader for free — Bun just dereferences `&BUN_COMPILED.size`.
- **Windows**: `initializePESection()` (`c-bindings.cpp` line 1096) calls `GetModuleHandleA(NULL)`, walks the in-memory `IMAGE_NT_HEADERS` section table with `IMAGE_FIRST_SECTION`, and does `strncmp(name, ".bun", 4)`. It reads the section via the **loaded/mapped image** (`hModule + VirtualAddress`, an RVA), not raw file bytes.
- **Linux/FreeBSD**: same idea via ELF program headers / a linker-provided symbol's vaddr.

Every platform's payload, once located, is validated identically by `from_executable()` (line 1963 onward): check `len >= sizeof(Offsets) + 16`, check the last 16 bytes equal `TRAILER`, then `read_unaligned::<Offsets>()` from `len - 32 - 16`.

## 2. Windows PE specifics

Section added by `PEFile::add_bun_section()` (`pe.rs` line 542):

- **Section name**: exactly `.bun` (`const BUN_SECTION_NAME: [u8; 8] = *b".bun\0\0\0\0"`, line 201) — this is an ASCII, NUL-padded 8-byte COFF name, matched byte-for-byte on lookup, both when Bun's own build tries to avoid duplicates (line 573) and when the C++ runtime side matches (`strncmp(...,4)`).
- **Characteristics**: `IMAGE_SCN_CNT_INITIALIZED_DATA (0x40) | IMAGE_SCN_MEM_READ (0x40000000)` — read-only initialized data, no execute, no write.
- **Placement**: always appended as the **last section** — `new_va`/`new_raw` are computed from `max(VA_end)`/`max(raw_end)` over existing sections (lines 607–631), so nothing follows `.bun` in either the file or the address space.
- **On-disk section content**: `[u64 LE length][payload bytes]` — 8-byte little-endian size prefix, then the raw `StandaloneModuleGraph::to_bytes()` payload, then zero-padding to the section's aligned raw size (lines 664–670, 633–636).
- **Alignment**: raw size is rounded up to `OptionalHeader64.file_alignment`; VA is rounded up to `section_alignment` (both must be powers of two; if `section_alignment < 4096` then `file_alignment == section_alignment`, enforced at `init()` time, lines 344–352).
- **Header bookkeeping updated on every add**: `PEHeader.number_of_sections += 1`; `OptionalHeader64.size_of_headers` bumped if the new section-header table needs more room (must still fit before `first_raw`, i.e. before the first section's raw data — this is why Bun errors `InsufficientHeaderSpace` if there's no header slack, line 604); `size_of_image` recomputed as `align_up(new_va + virtual_size, section_alignment)`; and a full **custom PE checksum** recompute (`recompute_pe_checksum`, line 504 — the classic Microsoft 16-bit-word-sum-with-carry-fold-plus-length algorithm, matching `imagehlp.dll`/`pefile`'s `generate_checksum()`).
- **Authenticode is unconditionally stripped**, not preserved: `inject()` calls `pe_file.add_bun_section(bytes, bun_pe::StripMode::StripAlways)` (line 1346) — every `--compile` build for Windows strips whatever signature the downloaded `bun.exe` template carried, via `strip_authenticode()` (line 416), which zeroes `DataDirectory[IMAGE_DIRECTORY_ENTRY_SECURITY]` (index 4), clears `IMAGE_DLLCHARACTERISTICS_FORCE_INTEGRITY` if set, truncates the trailing cert blob (aligned to 8 bytes) off the file, and recomputes the checksum. Bun does **not** attempt to re-sign Windows executables at all (unlike macOS, where it does ad-hoc codesign — see below). There is no `--bytecode`-cache-style hash check of Authenticode; it's purely "delete it, it's invalid now anyway."
- **No `.rsrc` involvement.** Icon/version-info/manifest resources (`WindowsOptions` — title, publisher, version, description, icon) are a separate, pre-existing PE-resource-editing step; the module graph itself never touches `.rsrc`.
- **Version history**: I could not get real multi-commit blame for `pe.rs` (shallow clone / GitHub Code Search API returned 404 for this session — likely a scope/auth limitation, not a "no results" signal), so I can't hand you exact SemVer ranges for when `.bun`-section-based Windows compile first shipped. What's well corroborated across the old Zig code (via search-engine summaries), `PR #15525`'s description, and `bun-demincer`'s independent documentation is that the `.bun` PE section + 8-byte length-prefix format has been stable for a long time and survived the Rust rewrite unchanged. Treat "exact version PE support landed" as **unverified — low confidence**; you may want to `git log -p` a full (non-shallow) clone or check Bun's CHANGELOG for "Windows" + "compile" entries if you need a precise version.

## 3. On-disk `StandaloneModuleGraph` format

```rust
// pe.rs / macho.rs consumer, StandaloneModuleGraph.rs:508
#[repr(C)]
struct Offsets {              // 32 bytes on 64-bit (repr(C), not packed)
    byte_count: usize,            // offset 0,  8 bytes — total payload length (up to, not including, Offsets+TRAILER)
    modules_ptr: StringPointer,   // offset 8,  8 bytes — {offset:u32, length:u32} span of the module table
    entry_point_id: u32,          // offset 16, 4 bytes — index into module table
    compile_exec_argv_ptr: StringPointer, // offset 20, 8 bytes
    flags: Flags,                 // offset 28, 4 bytes — bitflags (DISABLE_DEFAULT_ENV_FILES, etc.)
}

#[repr(C)]
struct StringPointer { offset: u32, length: u32 }   // 8 bytes, ABI-locked (also used in lockfile/npm-cache formats)

#[repr(C)]
struct CompiledModuleGraphFile {   // 52 bytes, no padding (6×8-byte StringPointers + 4×u8 tag bytes)
    name: StringPointer,               // e.g. "/$bunfs/root/app.js" (or "B:/~BUN/root/app.js" on Windows)
    contents: StringPointer,           // raw source bytes (or binary asset bytes)
    sourcemap: StringPointer,
    bytecode: StringPointer,           // JSC bytecode cache blob, 128-byte aligned in the buffer
    module_info: StringPointer,        // ESM module-record metadata for bytecode
    bytecode_origin_path: StringPointer, // path bytecode was generated against — must match at runtime for cache hit
    encoding: u8,   // Encoding::{Binary=0, Latin1=1(default), Utf8=2}
    loader: u8,     // Loader enum (Jsx=0..Md=20)
    module_format: u8, // ModuleFormat::{None=0, Esm=1, Cjs=2}
    side: u8,       // FileSide::{Server=0, Client=1}
}
```

Both struct sizes (52 and 32 bytes) are corroborated independently by `bun-demincer`'s README, confirming they're publicly known/stable, not something I mis-derived.

Every `StringPointer.offset` is relative to the **start of the payload buffer** (the same base used to locate `Offsets` itself), not to the file or to the module table. All reads in `from_bytes()` (line 533) are `read_unaligned` — the format makes zero alignment guarantees except for the `bytecode` field, which the writer (lines 790–845) deliberately pads so that, once the section is placed at a page-aligned runtime address plus the 8-byte size-prefix header, `bytecode`'s absolute address lands on a 128-byte boundary (JSC's bytecode-cache deserializer requires this or it asserts/segfaults). The magic constant is `target_mod = 128 - 8 = 120`: bytecode is padded so `offset_in_buffer % 128 == 120`.

`contents` for JS/TS/JSX/TSX files that are pure-ASCII is stored `Encoding::Latin1` (zero-copy `ExternalStringImpl` at runtime); anything else (including any non-ASCII JS) is `Encoding::Binary`. If you're rewriting a module's source bytes, keep this in mind if you introduce non-ASCII characters into a module previously flagged Latin1 — nothing in the format enforces it (encoding is just a runtime string-construction hint), but it's worth setting `Encoding::Binary` to be safe if you can't guarantee ASCII-only output.

## 4. Constraints on resizing a module

Because the whole payload is one flat, offset-addressed blob, resizing a module's bytes has effects that are **identical in kind** on macOS and Windows and differ only in the outer-container bookkeeping:

**Inner format changes needed regardless of platform (if content length changes):**
1. Shift every byte after the edited region by the size delta.
2. Update the edited module's own `StringPointer.length` (and `.offset` for every field of every module whose data comes *after* the insertion point in the buffer — `name`, `contents`, `sourcemap`, `bytecode`, `module_info`, `bytecode_origin_path` for potentially every later module).
3. Update `Offsets.modules_ptr.offset` / `Offsets.compile_exec_argv_ptr.offset` if the module table or argv string moved.
4. Update `Offsets.byte_count` (new total payload length before the trailer/Offsets tail).
5. **Bytecode staleness risk**: if you edit `contents` for a module that has a non-empty `bytecode`/`module_info` (i.e., it was compiled with `--bytecode`), that cached bytecode was generated *from the old source*. I found no source-hash/content check gating bytecode reuse in this codebase in the time available — matching happens only via `bytecode_origin_path` string equality (`File::to_wtf_string`/loader path in `StandaloneModuleGraph.rs`), not a hash of `contents`. **Confidence: medium.** Practically: either regenerate bytecode for that module, or zero out `bytecode`/`module_info`'s `StringPointer` (`{0,0}`) so JSC falls back to parsing the new source fresh — don't leave stale bytecode paired with edited source.
6. If you avoid changing total length (pad/truncate the replacement to the exact original `StringPointer.length`), **all of steps 1–4 disappear** — this is the same-length in-place patch your macOS tool presumably already does.

**Outer-container consequences differ a lot:**

| | macOS Mach-O | Windows PE |
|---|---|---|
| Section is last-in-file? | No — `__LINKEDIT` (and the code-signature blob) always trail `__BUN`. Any size delta forces a `memmove` of everything after `__BUN`, plus rewriting `LC_SEGMENT_64.fileoff/vmaddr` for `__LINKEDIT` (`macho.rs` lines 261–269). | **Yes** — Bun always appends `.bun` as the newest, last section. Growing it (up to the resized/aligned raw slot) touches nothing else in the file. |
| Integrity mechanism | Ad-hoc code signature covering **SHA-256 page hashes over the whole file** (`build_and_sign`, `macho.rs` line 499) — any byte change anywhere requires a full re-sign, which Bun already does automatically for arm64 targets (`self.header.cputype == CPU_TYPE_ARM64`) unless `BUN_NO_CODESIGN_MACHO_BINARY` is set. | Only an optional Authenticode signature (already stripped by Bun's own compiler) plus a trivial whole-file 16-bit checksum (`recompute_pe_checksum`) — no cryptographic re-signing is structurally required to produce a loadable binary. |
| **So: is same-length patching materially simpler on PE than resizing?** | N/A (comparison point) | **Not nearly as much as on Mach-O.** On PE, growing the `.bun` section is cheap (append bytes, bump `size_of_raw_data`/`virtual_size`/`size_of_image`, recompute checksum) *because it's the last section and unsigned by default*. Same-length in-place patching is still marginally simpler (skip size-field/checksum math entirely if you also skip checksum recompute — though you should always recompute checksum after any byte edit regardless of length, since content changed) — but it's a convenience simplification, not a structural necessity the way it is on Mach-O. The dominant simplifying factor on PE is "no cryptographic signature to rebuild," not "no resize." |

Practical implication for your PE patcher: you can almost certainly support **resizing** modules (not just same-length swaps) with much less engineering than your Mach-O path needed, *as long as you either (a) know the input PE has no Authenticode signature (true for anything straight out of `bun build --compile`), or (b) strip it first*. If growth requires more than the current aligned raw slot, just extend the file (same as `add_bun_section` does), rewrite the `.bun` section header's `size_of_raw_data`/`virtual_size`/`pointer_to_raw_data` (unchanged) fields, bump `size_of_image`, recompute the checksum, and you're done — no other section moves.

## 5. Windows signing / integrity

- **Modifying the `.bun` payload in a signed exe breaks Authenticode**, unavoidably — Authenticode's digest covers the file minus the checksum field and minus the security-directory/cert blob itself, but it absolutely covers section headers, `size_of_image`, and all section raw data, all of which change when you add/grow a section. There is no way to "patch around" this; the signature will fail validation (`signtool verify` / `WinVerifyTrust`) the instant you touch the file.
- **No runtime integrity check exists in Bun for this.** The lookup path (`c-bindings.cpp` `initializePESection`) reads the section straight from the loaded image with zero cryptographic or checksum verification — the only sanity checks are the `TRAILER` byte match and a length floor in Rust (`StandaloneModuleGraph.rs` lines 1996–2010). Windows' own loader does not enforce Authenticode validity for ordinary user-mode EXE launch (that's an OS-policy/SmartScreen/AV concern, not a hard load-time gate) — so an unsigned or signature-stripped patched exe will run fine.
- **Stripping the signature is exactly Bun's own standard approach** — confirmed directly in source: `pe_file.add_bun_section(bytes, bun_pe::StripMode::StripAlways)` (line 1346). Their `strip_authenticode()` implementation (line 416) is a clean, minimal reference: zero the Security data directory, clear `IMAGE_DLLCHARACTERISTICS_FORCE_INTEGRITY`, truncate the cert blob (8-byte aligned) off the tail, recompute checksum. I'd recommend mirroring this exactly rather than reinventing it.
- **Tooling that does the same thing cleanly**, for your implementation or for validating your own output against:
  - `osslsigncode remove-signature -in in.exe -out out.exe` — purpose-built one-liner for this.
  - Python `pefile`: read `pe.OPTIONAL_HEADER.DATA_DIRECTORY[IMAGE_DIRECTORY_ENTRY.IMAGE_DIRECTORY_ENTRY_SECURITY]`, zero it, truncate the file at the old cert offset, call `pe.OPTIONAL_HEADER.CheckSum = pe.generate_checksum()` (pefile ships the same Microsoft checksum algorithm Bun reimplemented by hand).
  - `signtool remove /s file.exe` (newer Windows SDKs) also works if you have the SDK available.
  - `signify` is a BSD/OpenBSD signing tool unrelated to Authenticode/PE — not applicable here; don't confuse it with Microsoft's Authenticode.
- If your pipeline needs the *output* to be re-signed (e.g., you sign with your own org's cert after patching), that's a separate step after stripping — same shape as what you already do for macOS ad-hoc codesign, just swap `codesign` for `signtool sign` / `osslsigncode sign` / `jsign`.

## 6. Prior art

- **[vicnaum/bun-demincer](https://github.com/vicnaum/bun-demincer)** — the closest existing tool to yours. It documents and round-trips all three platforms: macOS `__BUN`/`__bun`, Linux (appended ELF data + trailer), Windows `.bun` PE section. It extracts source, deobfuscates/renames, and explicitly supports **reassembling modified modules back into a working binary** — i.e., it already solves patch-and-repack, at least for its use case (source deobfuscation rather than arbitrary resizing). Its documented format (8-byte size header, 52-byte `CompiledModuleGraphFile`, 32-byte `Offsets`, `"\n---- Bun! ----\n"` trailer) matches byte-for-byte what I read directly out of current Bun source — strong independent corroboration that the format truly is stable across the Zig→Rust rewrite.
- I found no other public, actively maintained "Bun standalone exe patcher" projects in this session's search radius (the rest of the search results were either Bun's own docs/discussions about `--compile`, or unrelated projects — `theseyan/bkg` packages Bun apps but doesn't patch the module graph binary format, and `Bun/unpack` is an unrelated Linux archive-unpacking tool that just happens to share the "Bun" GitHub username).

---

## PE patcher — step-by-step (my recommendation given the above)

1. **Parse PE headers**: DOS header (`e_magic == 0x5A4D`), `e_lfanew` → PE header (`signature == 0x00004550`), optional header (require `magic == 0x020B`, i.e., PE32+/x64 — Bun's own code only supports 64-bit here), section header array.
2. **Locate `.bun`**: scan section table for `name[0..4] == ".bun"` (match Bun's own 8-byte, NUL-padded comparison to be safe against false positives on longer names).
3. **Parse the section**: `payload_len = u64::from_le_bytes(raw_data[0..8])`; payload = `raw_data[8..8+payload_len]`. Sanity check `payload_len + 8 <= size_of_raw_data`.
4. **Parse the payload** (this part is platform-agnostic — same code as your macOS patcher's inner-format logic): verify last 16 bytes == `b"\n---- Bun! ----\n"`; read `Offsets` from `payload_len_used - 32 - 16`... (careful: the *outer* `payload_len` from the section is the exact `byte_count` from `Offsets` — the trailer+Offsets are appended *after* `byte_count` was captured, so `section_payload_len == byte_count + 32 + 16`; index from the end of the actual bytes present, not from `byte_count`). Read the module table via `Offsets.modules_ptr`, decode each 52-byte `CompiledModuleGraphFile`.
5. **Do your edit** in the flat payload buffer: same-length swap is trivial (overwrite in place); resizing requires the offset-table surgery in §4 above (shift bytes, adjust every downstream `StringPointer`, adjust `Offsets.byte_count`, re-append `Offsets`+`TRAILER`).
6. **Check for an existing Authenticode signature**: read `OptionalHeader64.data_directories[4]` (`IMAGE_DIRECTORY_ENTRY_SECURITY`). If `virtual_address != 0`, strip it: zero that directory entry, clear `IMAGE_DLLCHARACTERISTICS_FORCE_INTEGRITY` if set, truncate the file at the (8-byte-aligned) old cert offset. Do this *before* resizing `.bun`, mirroring Bun's own order of operations.
7. **Resize the `.bun` section** (only needed if new payload doesn't fit the old raw slot): since `.bun` is last-in-file, just grow the file — set `size_of_raw_data = align_up(new_payload_len + 8, file_alignment)`, `virtual_size = new_payload_len + 8`, keep `virtual_address`/`pointer_to_raw_data` unchanged (nothing moved), zero-fill new bytes, write the new `[u64 len][payload]` at the section's raw offset.
8. **Fix up the optional header**: `size_of_image = align_up(section.virtual_address + section.virtual_size, section_alignment)` (only changes if `virtual_size` grew past what was already accounted for); leave `size_of_headers`/`number_of_sections` untouched (you're not adding a section, just resizing the payload inside an existing one).
9. **Recompute the PE checksum**: zero the checksum field, then Microsoft's classic algorithm (sum 16-bit little-endian words with carry-fold, handle odd trailing byte, fold again, add total file length, fold once more) — same algorithm as `pe.rs::recompute_pe_checksum` / `pefile.generate_checksum()`.
10. **Write the file out.** No cryptographic re-signing step is structurally required (Bun ships these unsigned). If your downstream pipeline needs an Authenticode signature on the output, sign as a separate final step with your own cert (`signtool sign` / `osslsigncode sign`), same as you'd do for a re-signed macOS binary with `codesign`.

## Open unknowns / confidence levels

- **High confidence**: section name (`.bun`), section content format (`u64 LE length + payload`), `Offsets`/`CompiledModuleGraphFile`/`StringPointer` layouts, trailer magic, "always strip Authenticode" behavior, PE checksum algorithm, "last section, no shift needed on resize" property — all read directly from current `pe.rs`/`StandaloneModuleGraph.rs`/`c-bindings.cpp` source.
- **Medium confidence**: whether stale bytecode paired with edited source causes a silent-wrong-behavior bug vs. a hard failure at runtime — I did not find a content-hash check, but I did not trace the full JSC-side bytecode deserialization path (that lives in WebKit/JSC C++ that's vendored, not in this Rust crate) in the time available. Recommend zeroing `bytecode`/`module_info` for edited modules as a safe default.
- **Low confidence / unverified**: exact Bun version (SemVer) ranges for when `.bun`-PE-section-based Windows `--compile` support first shipped, and whether any earlier Windows implementation used a different mechanism (e.g., resource-based or trailer-only) before settling on the PE-section approach. GitHub's code-search and contents APIs both 404'd for me this session (looked like an access/scope limitation rather than "no such history"), and my shallow clone only has one commit of history for `pe.rs`. If you need exact version boundaries, a full non-shallow `git clone` + `git log --follow -p -- src/exe_format/pe.rs` (or the pre-rewrite `src/StandaloneModuleGraph.zig` + `src/windows/pe.zig`-equivalent in tags going back to ~1.1.x, where Windows `--compile` support was first announced) would settle it definitively.
