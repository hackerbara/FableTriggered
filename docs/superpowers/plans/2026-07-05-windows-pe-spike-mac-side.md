# Windows PE Spike (Mac-Side) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Mac-developable portion of the ClaudeMonkey Windows spike from `docs/windows-port-brief.md` §12 — a resize-capable PE (`.bun`) patcher plus the platform plumbing to drive a real, length-changing patch package through the genuine `manifest → module_patch → repack` vocab against the real downloaded Windows `claude.exe`, producing a structurally-valid patched binary.

**Architecture:** Add a `pe.py` sibling to `macho.py` that parses PE64 headers, locates the last-in-file `.bun` section, and repacks it with arbitrary-length module edits (strip Authenticode, resize the trailing section, fix `SizeOfImage`, recompute the PE checksum). Reuse `bun_graph.py` and `module_patch.py` — which operate on the flat `.bun` payload — with one small change: `bun_graph` must accept the Windows `B:/~BUN/` module-path prefix (empirically the Windows bundle uses that, not `/$bunfs/`). Route the container-format-specific calls in `builder_v15.py` / `binary_inspect.py` through a format sniffer so `build` works on a PE input. Prove the whole chain end-to-end with a thin driver and a real length-changing package that satisfies fail-closed pinning.

**Tech Stack:** Python 3.12, `struct` for binary parsing, `pytest` (with the repo's `tests/fixtures_bun.py` synthetic-payload convention), `uv run` for execution. No new runtime dependencies (the PE checksum is hand-rolled and validated against the real binary — no `pefile` dependency).

## Global Constraints

- **No new runtime dependencies.** The PE checksum is hand-rolled; do not add `pefile` to `pyproject.toml` runtime deps. (`pefile` MAY be used only as an optional test oracle if already importable, never imported at runtime.)
- **`bun_graph.py` and `module_patch.py` stay container-agnostic.** The only permitted change to `bun_graph.py` is broadening module-path prefix acceptance (Task 4). Do not add PE/Mach-O awareness to either file.
- **`pe.py`'s repack entry point mirrors `repack.py`'s exactly:** `repack_changed_modules(source: bytes, changed_modules: dict[str, bytes]) -> RepackResult`, returning the existing `RepackResult` dataclass (fields `output_bytes`, `delta`, `bun_graph_updates`, `macho_updates`, `macho_update_details`). For PE, `macho_updates`/`macho_update_details` carry PE-equivalent reporting (section resize, checksum, cert-strip) — do not rename `BuildReportV2` fields.
- **Fail-closed is sacred.** Never disable a pin check to make a build pass. Re-pin (author correct version + SHA-256 + module identity) instead. The one intentional relaxation is the module-path prefix in Task 4, which is a correctness fix (the Windows payload is legitimate), not a safety bypass.
- **Real-binary tests self-skip when absent.** Follow `tests/claude_binary.py` convention: resolve the pinned binary via an env override, check `.exists()`, `pytest.skip(...)` if missing. Never hardcode a home-directory path in an assertion.
- **Empirically-fixed constants** (verified against the real `claude.exe` 2.1.201 win32-x64 during planning — use these exact values):
  - Windows binary URL: `https://downloads.claude.ai/claude-code-releases/2.1.201/win32-x64/claude.exe`
  - Windows binary SHA-256: `fb804ee019bfbb8d7e85abf965e528e53b5aa5a4e4ebc0f164139dc10a9e0320`
  - Windows binary size: `241591968` bytes
  - Windows `.bun` section: last section (index 11 of 12), name `.bun`, `PointerToRawData=0x4f3f200`, `SizeOfRawData=0x9724c00`, declared payload len `158485274`.
  - Windows `cli.js` module path: `B:/~BUN/root/src/entrypoints/cli.js` (NOT `/$bunfs/root/...`).
  - Windows `cli.js` content: length `18745538`, SHA-256 `63154b978bb29a873e54fa8a622a5f5bce3b5cd3461cfa926cce010cabced1e2`.
  - Authenticode security dir (PE32+ DataDirectory[4]): RVA `0xe663e00`, size `0x28a0`.
  - Stored PE checksum: `0xe67537e` (reproduced exactly by the hand-rolled algorithm in Task 3).
  - PE32+ optional-header field offsets, relative to `opt = e_lfanew + 24`: Magic `opt+0` (u16, `0x020b`), SectionAlignment `opt+32` (u32), FileAlignment `opt+36` (u32), SizeOfImage `opt+56` (u32), CheckSum `opt+64` (u32), DllCharacteristics `opt+70` (u16), NumberOfRvaAndSizes `opt+108` (u32), DataDirectory base `opt+112` (entry `i` at `opt+112+i*8`, so Security = `opt+112+32`). Section table base `= opt + SizeOfOptionalHeader` where `SizeOfOptionalHeader` is at `e_lfanew+20` (u16); NumberOfSections at `e_lfanew+6` (u16). Section header is 40 bytes: VirtualSize `+8`, VirtualAddress `+12`, SizeOfRawData `+16`, PointerToRawData `+20`.

---

## Prerequisite: Download the Windows binary (do this once, before Task 2)

The pinned Windows `claude.exe` is a developer-machine fixture, never committed. Download it to the env-overridable location the tests expect:

```bash
mkdir -p ~/.local/share/claude-monkey-dev/win32-x64/2.1.201
curl -s -o ~/.local/share/claude-monkey-dev/win32-x64/2.1.201/claude.exe \
  https://downloads.claude.ai/claude-code-releases/2.1.201/win32-x64/claude.exe
shasum -a 256 ~/.local/share/claude-monkey-dev/win32-x64/2.1.201/claude.exe
# Expect: fb804ee019bfbb8d7e85abf965e528e53b5aa5a4e4ebc0f164139dc10a9e0320
```

Tests locate it via `CLAUDE_MONKEY_WIN_SOURCE` (added in Task 2's test helper), defaulting to `~/.local/share/claude-monkey-dev/win32-x64/2.1.201/claude.exe`.

---

## Task 1: PE synthetic fixture builder

Mirror `tests/fixtures_bun.py`'s Mach-O fixture builder for PE, so `pe.py` can be TDD'd without the 240 MB real binary. Reuse `build_payload()` unchanged.

**Files:**
- Create: `tests/fixtures_pe.py`
- Test: `tests/test_fixtures_pe.py`

**Interfaces:**
- Consumes: `tests.fixtures_bun.build_payload() -> tuple[bytes, FixtureOffsets]` (returns `u64(len(payload)) + payload`, i.e. an `[u64 len][payload]` `.bun` section).
- Produces:
  - `build_pe_fixture(section: bytes, *, with_authenticode: bool = False) -> bytes` — a minimal but structurally valid PE32+ x64 file with `.text` then `.bun` (last) sections; `.bun` raw data is `section` zero-padded up to `FILE_ALIGNMENT`; if `with_authenticode`, appends a dummy cert blob and sets DataDirectory[4] + `IMAGE_DLLCHARACTERISTICS_FORCE_INTEGRITY` (0x0080) and a stored checksum.
  - Module constants: `FILE_ALIGNMENT = 0x200`, `SECTION_ALIGNMENT = 0x1000`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_fixtures_pe.py
import struct
from tests.fixtures_bun import build_payload
from tests.fixtures_pe import build_pe_fixture, FILE_ALIGNMENT


def test_fixture_is_valid_pe_with_bun_last_section():
    section, _ = build_payload()
    data = build_pe_fixture(section)
    assert data[:2] == b"MZ"
    e = struct.unpack_from("<I", data, 0x3C)[0]
    assert data[e:e + 4] == b"PE\0\0"
    opt = e + 24
    assert struct.unpack_from("<H", data, opt)[0] == 0x020B  # PE32+
    nsections = struct.unpack_from("<H", data, e + 6)[0]
    size_opt = struct.unpack_from("<H", data, e + 20)[0]
    st = opt + size_opt
    last = st + (nsections - 1) * 40
    name = data[last:last + 8].rstrip(b"\0")
    assert name == b".bun"
    rawsize, rawptr = struct.unpack_from("<II", data, last + 16)
    assert rawptr + rawsize == len(data)  # .bun is genuinely last-in-file
    assert data[rawptr:rawptr + len(section)] == section
    assert rawsize % FILE_ALIGNMENT == 0


def test_fixture_with_authenticode_sets_security_dir():
    section, _ = build_payload()
    data = build_pe_fixture(section, with_authenticode=True)
    e = struct.unpack_from("<I", data, 0x3C)[0]
    opt = e + 24
    rva, size = struct.unpack_from("<II", data, opt + 112 + 32)
    assert rva != 0 and size != 0
    dll_chars = struct.unpack_from("<H", data, opt + 70)[0]
    assert dll_chars & 0x0080  # FORCE_INTEGRITY set
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_fixtures_pe.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'tests.fixtures_pe'`

- [ ] **Step 3: Write the fixture builder**

```python
# tests/fixtures_pe.py
"""Synthetic PE32+ fixtures carrying a Bun `.bun` payload as the last section.

Mirrors tests/fixtures_bun.py's Mach-O builders so pe.py can be exercised
without the ~240 MB real claude.exe. The `.bun` section holds the exact
`[u64 len][payload]` bytes build_payload() produces — byte-identical to the
macOS payload — so bun_graph.py parses it unchanged.
"""
from __future__ import annotations

import struct

FILE_ALIGNMENT = 0x200
SECTION_ALIGNMENT = 0x1000
FORCE_INTEGRITY = 0x0080


def _align(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


def build_pe_fixture(section: bytes, *, with_authenticode: bool = False) -> bytes:
    # Header sizes: DOS stub (0x40) + PE sig (4) + COFF header (20) +
    # optional header (240 for PE32+ with 16 data dirs) + 2 section headers (80).
    e_lfanew = 0x40
    opt_size = 240
    n_sections = 2
    headers_end = e_lfanew + 4 + 20 + opt_size + n_sections * 40
    size_of_headers = _align(headers_end, FILE_ALIGNMENT)

    text = b"\xc3" * 0x10  # trivial .text body
    text_rawsize = _align(len(text), FILE_ALIGNMENT)
    text_ptr = size_of_headers
    text_vaddr = SECTION_ALIGNMENT

    bun_rawsize = _align(len(section), FILE_ALIGNMENT)
    bun_ptr = text_ptr + text_rawsize
    bun_vaddr = _align(text_vaddr + text_rawsize, SECTION_ALIGNMENT)
    size_of_image = _align(bun_vaddr + len(section), SECTION_ALIGNMENT)

    out = bytearray(bun_ptr + bun_rawsize)
    out[0:2] = b"MZ"
    struct.pack_into("<I", out, 0x3C, e_lfanew)
    out[e_lfanew:e_lfanew + 4] = b"PE\0\0"
    # COFF header: machine=0x8664, nsections, ..., SizeOfOptionalHeader, chars
    struct.pack_into("<HH", out, e_lfanew + 4, 0x8664, n_sections)
    struct.pack_into("<H", out, e_lfanew + 20, opt_size)
    struct.pack_into("<H", out, e_lfanew + 22, 0x0022)  # EXECUTABLE_IMAGE|LARGE_ADDRESS_AWARE
    opt = e_lfanew + 24
    struct.pack_into("<H", out, opt + 0, 0x020B)  # PE32+
    struct.pack_into("<I", out, opt + 32, SECTION_ALIGNMENT)
    struct.pack_into("<I", out, opt + 36, FILE_ALIGNMENT)
    struct.pack_into("<I", out, opt + 56, size_of_image)
    struct.pack_into("<I", out, opt + 60, size_of_headers)
    struct.pack_into("<I", out, opt + 108, 16)  # NumberOfRvaAndSizes

    st = opt + opt_size
    _write_section(out, st, b".text", len(text), text_vaddr, text_rawsize, text_ptr)
    _write_section(out, st + 40, b".bun", len(section), bun_vaddr, bun_rawsize, bun_ptr)

    out[text_ptr:text_ptr + len(text)] = text
    out[bun_ptr:bun_ptr + len(section)] = section

    if with_authenticode:
        cert = b"\x08\x00\x00\x00" + b"\x02\x02" + b"CERTDATA"  # dummy WIN_CERTIFICATE-ish blob
        cert_off = len(out)
        out.extend(cert)
        struct.pack_into("<II", out, opt + 112 + 32, cert_off, len(cert))  # DataDirectory[4]
        dll = struct.unpack_from("<H", out, opt + 70)[0]
        struct.pack_into("<H", out, opt + 70, dll | FORCE_INTEGRITY)
        struct.pack_into("<I", out, opt + 64, 0x1234)  # nonzero stored checksum

    return bytes(out)


def _write_section(
    buf: bytearray, off: int, name: bytes, vsize: int, vaddr: int, rawsize: int, rawptr: int
) -> None:
    buf[off:off + 8] = name.ljust(8, b"\0")
    struct.pack_into("<IIII", buf, off + 8, vsize, vaddr, rawsize, rawptr)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_fixtures_pe.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add tests/fixtures_pe.py tests/test_fixtures_pe.py
git commit -m "test: add synthetic PE32+ .bun fixture builder for Windows spike"
```

---

## Task 2: `pe.py` — PE layout parser

Parse PE64 headers, locate the `.bun` section (require it be last-in-file), and expose the offsets + Authenticode info the repack needs.

**Files:**
- Create: `src/claude_monkey/pe.py`
- Modify: `tests/claude_binary.py` (add Windows-binary resolver)
- Test: `tests/test_pe.py`

**Interfaces:**
- Consumes: `tests.fixtures_pe.build_pe_fixture`, `tests.fixtures_bun.build_payload`.
- Produces (in `pe.py`):
  - `PE_MAGIC = b"PE\x00\x00"`, `PE32PLUS_MAGIC = 0x020B`, `class PEError(ValueError)`.
  - `@dataclass(frozen=True) class PESection: index:int; name:str; virtual_size:int; virtual_address:int; raw_size:int; raw_pointer:int`
  - `@dataclass(frozen=True) class PELayout: e_lfanew:int; opt_offset:int; section_table_offset:int; num_sections:int; file_alignment:int; section_alignment:int; sections:tuple[PESection,...]; bun_section:PESection; security_rva:int; security_size:int; checksum_offset:int; dll_characteristics_offset:int; size_of_image_offset:int`
  - `find_pe_layout(data: bytes | bytearray) -> PELayout` — raises `PEError` if not PE32+ x64, or if the `.bun` section is missing or not last-in-file.
- Also in `tests/claude_binary.py`:
  - `WIN_CLAUDE_BIN_ENV = "CLAUDE_MONKEY_WIN_SOURCE"`, `def win_claude_bin() -> Path:` returning the env override or `~/.local/share/claude-monkey-dev/win32-x64/2.1.201/claude.exe`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pe.py
import struct
import pytest
from tests.fixtures_bun import build_payload
from tests.fixtures_pe import build_pe_fixture
from tests.claude_binary import win_claude_bin
from claude_monkey.pe import find_pe_layout, PEError


def test_find_pe_layout_on_fixture():
    section, _ = build_payload()
    data = build_pe_fixture(section)
    layout = find_pe_layout(data)
    assert layout.bun_section.name == ".bun"
    assert layout.bun_section.index == layout.num_sections - 1
    assert layout.bun_section.raw_pointer + layout.bun_section.raw_size == len(data)
    assert layout.security_rva == 0  # no Authenticode on plain fixture


def test_find_pe_layout_detects_authenticode():
    section, _ = build_payload()
    data = build_pe_fixture(section, with_authenticode=True)
    layout = find_pe_layout(data)
    assert layout.security_rva != 0 and layout.security_size != 0


def test_rejects_non_pe():
    with pytest.raises(PEError):
        find_pe_layout(b"\x00" * 512)


def test_find_pe_layout_on_real_windows_binary():
    src = win_claude_bin()
    if not src.exists():
        pytest.skip(f"missing Windows claude.exe fixture: {src}")
    data = src.read_bytes()
    layout = find_pe_layout(data)
    assert layout.bun_section.name == ".bun"
    assert layout.bun_section.raw_pointer == 0x4F3F200
    assert layout.bun_section.raw_size == 0x9724C00
    assert layout.security_rva == 0xE663E00
    assert layout.security_size == 0x28A0
    # stored checksum lives at checksum_offset
    assert struct.unpack_from("<I", data, layout.checksum_offset)[0] == 0xE67537E
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_pe.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'claude_monkey.pe'` (and the `win_claude_bin` import error until the helper is added; add the helper in Step 3 alongside `pe.py`).

- [ ] **Step 3: Implement `find_pe_layout` and the test helper**

Add to `tests/claude_binary.py`:

```python
WIN_CLAUDE_BIN_ENV = "CLAUDE_MONKEY_WIN_SOURCE"


def win_claude_bin() -> Path:
    """Location of the pinned Windows claude.exe spike fixture (never committed)."""
    override = os.environ.get(WIN_CLAUDE_BIN_ENV)
    if override:
        return Path(override)
    return (
        Path.home()
        / ".local" / "share" / "claude-monkey-dev" / "win32-x64" / "2.1.201" / "claude.exe"
    )
```

Create `src/claude_monkey/pe.py`:

```python
"""PE32+ container parsing for Bun standalone Windows binaries.

Sibling to macho.py. On Windows the Bun module-graph payload lives in a PE
section named `.bun`, always the last section in the file: [u64 LE length]
[payload][zero-pad to file_alignment]. Because it is last-in-file, resizing
it moves nothing else — there is no analog to Mach-O's __LINKEDIT shifting.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass

PE_MAGIC = b"PE\x00\x00"
PE32PLUS_MAGIC = 0x020B
MACHINE_AMD64 = 0x8664
SECURITY_DIR_INDEX = 4
FORCE_INTEGRITY = 0x0080


class PEError(ValueError):
    pass


@dataclass(frozen=True)
class PESection:
    index: int
    name: str
    virtual_size: int
    virtual_address: int
    raw_size: int
    raw_pointer: int


@dataclass(frozen=True)
class PELayout:
    e_lfanew: int
    opt_offset: int
    section_table_offset: int
    num_sections: int
    file_alignment: int
    section_alignment: int
    sections: tuple[PESection, ...]
    bun_section: PESection
    security_rva: int
    security_size: int
    checksum_offset: int
    dll_characteristics_offset: int
    size_of_image_offset: int


def _u16(data, off): return struct.unpack_from("<H", data, off)[0]
def _u32(data, off): return struct.unpack_from("<I", data, off)[0]


def find_pe_layout(data: bytes | bytearray) -> PELayout:
    if len(data) < 0x40 or data[0:2] != b"MZ":
        raise PEError("not_a_pe_missing_dos_magic")
    e_lfanew = _u32(data, 0x3C)
    if e_lfanew + 24 > len(data) or data[e_lfanew:e_lfanew + 4] != PE_MAGIC:
        raise PEError("not_a_pe_missing_signature")
    machine = _u16(data, e_lfanew + 4)
    num_sections = _u16(data, e_lfanew + 6)
    size_opt = _u16(data, e_lfanew + 20)
    opt = e_lfanew + 24
    if _u16(data, opt) != PE32PLUS_MAGIC:
        raise PEError("unsupported_optional_header_not_pe32plus")
    if machine != MACHINE_AMD64:
        raise PEError(f"unsupported_machine:0x{machine:04x}")

    file_alignment = _u32(data, opt + 36)
    section_alignment = _u32(data, opt + 32)
    checksum_offset = opt + 64
    dll_characteristics_offset = opt + 70
    size_of_image_offset = opt + 56
    security_rva = _u32(data, opt + 112 + SECURITY_DIR_INDEX * 8)
    security_size = _u32(data, opt + 112 + SECURITY_DIR_INDEX * 8 + 4)

    st = opt + size_opt
    sections = []
    for i in range(num_sections):
        off = st + i * 40
        name = data[off:off + 8].rstrip(b"\x00").decode("ascii", "replace")
        vsize, vaddr, rawsize, rawptr = struct.unpack_from("<IIII", data, off + 8)
        sections.append(PESection(i, name, vsize, vaddr, rawsize, rawptr))

    bun = next((s for s in sections if s.name == ".bun"), None)
    if bun is None:
        raise PEError("missing_bun_section")
    if bun.index != num_sections - 1:
        raise PEError("bun_section_not_last")
    if bun.raw_pointer + bun.raw_size != len(data) and security_rva == 0:
        # With Authenticode stripped/absent, .bun raw data must reach EOF.
        raise PEError("bun_section_not_end_of_file")

    return PELayout(
        e_lfanew=e_lfanew,
        opt_offset=opt,
        section_table_offset=st,
        num_sections=num_sections,
        file_alignment=file_alignment,
        section_alignment=section_alignment,
        sections=tuple(sections),
        bun_section=bun,
        security_rva=security_rva,
        security_size=security_size,
        checksum_offset=checksum_offset,
        dll_characteristics_offset=dll_characteristics_offset,
        size_of_image_offset=size_of_image_offset,
    )
```

Note on the real binary: its `.bun` raw data ends at `0xE661800` but the file is `0xE663E60` — the Authenticode cert blob sits *after* `.bun`. That is why the `bun_section_not_end_of_file` guard is skipped when `security_rva != 0`: the cert is stripped first during repack (Task 3), after which `.bun` becomes genuinely last.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_pe.py -v`
Expected: PASS (the real-binary test passes if the fixture is downloaded, else skips).

- [ ] **Step 5: Commit**

```bash
git add src/claude_monkey/pe.py tests/test_pe.py tests/claude_binary.py
git commit -m "feat: add pe.py PE32+ layout parser locating the .bun section"
```

---

## Task 3: `pe.py` — Authenticode strip, checksum, resize repack

Add the resize-capable repack: strip Authenticode, apply module edits via `bun_graph`, resize the trailing `.bun` section, fix `SizeOfImage`, recompute the PE checksum. Mirror `repack.repack_changed_modules`'s signature and `RepackResult` return.

**Files:**
- Modify: `src/claude_monkey/pe.py`
- Test: `tests/test_pe.py`

**Interfaces:**
- Consumes: `find_pe_layout` (Task 2); `claude_monkey.bun_graph.parse_bun_section`, `BunGraph.replace_module_content`; `claude_monkey.repack.RepackResult` (reuse the existing dataclass — import it).
- Produces (in `pe.py`):
  - `def pe_checksum(buf: bytes) -> int` — Microsoft PE checksum (checksum field must be zeroed by the caller before calling).
  - `def strip_authenticode(data: bytearray, layout: PELayout) -> bytearray` — zero DataDirectory[4], clear `FORCE_INTEGRITY`, truncate the cert blob at the security RVA (8-byte aligned).
  - `def repack_changed_modules(source: bytes, changed_modules: dict[str, bytes]) -> RepackResult` — same signature as `repack.repack_changed_modules`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_pe.py
from claude_monkey.pe import pe_checksum, repack_changed_modules
from claude_monkey.bun_graph import parse_bun_section
from tests.fixtures_bun import build_payload, MODULE_PATH_0


def test_pe_checksum_matches_real_binary():
    src = win_claude_bin()
    if not src.exists():
        pytest.skip(f"missing Windows claude.exe fixture: {src}")
    data = bytearray(src.read_bytes())
    layout = find_pe_layout(data)
    struct.pack_into("<I", data, layout.checksum_offset, 0)
    assert pe_checksum(bytes(data)) == 0xE67537E


def _bun_section_bytes(data):
    layout = find_pe_layout(data)
    b = layout.bun_section
    return data[b.raw_pointer:b.raw_pointer + b.raw_size]


def test_repack_grows_module_on_fixture():
    section, _ = build_payload()
    data = build_pe_fixture(section, with_authenticode=True)
    original = parse_bun_section(section)
    mod0 = original.module_by_path(MODULE_PATH_0)
    new_content = mod0.content + b"// PADDING TO GROW THE MODULE"
    result = repack_changed_modules(bytes(data), {MODULE_PATH_0: new_content})

    out = result.output_bytes
    layout = find_pe_layout(out)
    # Authenticode stripped: security dir zeroed, .bun now genuinely last.
    assert layout.security_rva == 0
    assert layout.bun_section.raw_pointer + layout.bun_section.raw_size == len(out)
    # Edited payload re-parses and carries the grown module.
    graph = parse_bun_section(_bun_section_bytes(out))
    assert graph.validation_errors == []
    assert graph.module_by_path(MODULE_PATH_0).content == new_content
    assert result.delta == len(new_content) - mod0.content_size
    # Checksum is valid for the emitted file.
    check = bytearray(out)
    struct.pack_into("<I", check, layout.checksum_offset, 0)
    assert pe_checksum(bytes(check)) == struct.unpack_from("<I", out, layout.checksum_offset)[0]


def test_repack_shrinks_module_on_fixture():
    section, _ = build_payload()
    data = build_pe_fixture(section)
    original = parse_bun_section(section)
    mod0 = original.module_by_path(MODULE_PATH_0)
    new_content = mod0.content[: max(1, mod0.content_size - 4)]
    result = repack_changed_modules(bytes(data), {MODULE_PATH_0: new_content})
    graph = parse_bun_section(_bun_section_bytes(result.output_bytes))
    assert graph.module_by_path(MODULE_PATH_0).content == new_content
    assert graph.validation_errors == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_pe.py -k "checksum or repack" -v`
Expected: FAIL — `ImportError: cannot import name 'pe_checksum'`

- [ ] **Step 3: Implement checksum, strip, and repack**

Append to `src/claude_monkey/pe.py`:

```python
from claude_monkey.bun_graph import parse_bun_section
from claude_monkey.repack import RepackResult


def pe_checksum(buf: bytes) -> int:
    """Microsoft PE image checksum. Caller must zero the CheckSum field first."""
    n = len(buf)
    words = n // 2
    total = sum(struct.unpack_from(f"<{words}H", buf, 0))
    if n & 1:
        total += buf[-1]
    while total >> 16:
        total = (total & 0xFFFF) + (total >> 16)
    return (total + n) & 0xFFFFFFFF


def _align_up(value: int, alignment: int) -> int:
    return (value + alignment - 1) // alignment * alignment


def strip_authenticode(data: bytearray, layout: PELayout) -> bytearray:
    """Remove the Authenticode certificate: zero DataDirectory[4], clear
    FORCE_INTEGRITY, and truncate the trailing cert blob. Returns a new
    bytearray. No-op (copy) if no security directory is present."""
    out = bytearray(data)
    if layout.security_rva == 0:
        return out
    # DataDirectory[4] (SECURITY) rva is a *file offset*, not an RVA, per PE spec.
    cert_offset = layout.security_rva
    struct.pack_into("<II", out, layout.opt_offset + 112 + SECURITY_DIR_INDEX * 8, 0, 0)
    dll = _u16(out, layout.dll_characteristics_offset)
    struct.pack_into("<H", out, layout.dll_characteristics_offset, dll & ~FORCE_INTEGRITY)
    del out[cert_offset:]
    return out


def repack_changed_modules(source: bytes, changed_modules: dict[str, bytes]) -> RepackResult:
    if not changed_modules:
        raise ValueError("changed_modules_required")

    layout = find_pe_layout(source)
    # 1. Strip Authenticode first so .bun is last-in-file for resizing.
    data = strip_authenticode(bytearray(source), layout)
    layout = find_pe_layout(data)  # re-derive after truncation

    bun = layout.bun_section
    section = bytes(data[bun.raw_pointer:bun.raw_pointer + bun.raw_size])
    # The section raw_size is file-aligned and may exceed [u64 len][payload];
    # slice to the declared logical section so parse_bun_section validates.
    declared = struct.unpack_from("<Q", section, 0)[0]
    logical = section[: 8 + declared]

    graph = parse_bun_section(logical)
    original_order = {m.path: m.content_offset for m in graph.modules}
    total_delta = 0
    shifted_pointers = 0
    current = logical
    for path in sorted(changed_modules, key=lambda p: original_order[p]):
        graph = parse_bun_section(current)
        rewrite = graph.replace_module_content(path, changed_modules[path])
        if rewrite.validation_errors:
            raise ValueError(f"bun_graph_validation_failed:{rewrite.validation_errors}")
        current = rewrite.section_bytes
        total_delta += rewrite.delta
        shifted_pointers += rewrite.shifted_pointers

    new_logical_len = len(current)
    new_raw_size = _align_up(new_logical_len, layout.file_alignment)
    new_section = current + b"\x00" * (new_raw_size - new_logical_len)

    out = bytearray(data[: bun.raw_pointer])
    out.extend(new_section)

    # Fix the .bun section header: raw size + virtual size; ptr/vaddr unchanged.
    sect_off = layout.section_table_offset + bun.index * 40
    struct.pack_into("<I", out, sect_off + 8, new_logical_len)   # VirtualSize
    struct.pack_into("<I", out, sect_off + 16, new_raw_size)     # SizeOfRawData

    # Fix SizeOfImage = align_up(bun.vaddr + new virtual size, section_alignment).
    new_size_of_image = _align_up(bun.virtual_address + new_logical_len, layout.section_alignment)
    struct.pack_into("<I", out, layout.size_of_image_offset, new_size_of_image)

    # Recompute PE checksum (zero the field first).
    struct.pack_into("<I", out, layout.checksum_offset, 0)
    checksum = pe_checksum(bytes(out))
    struct.pack_into("<I", out, layout.checksum_offset, checksum)

    pe_updates = {
        "authenticodeStripped": layout.security_rva == 0 and source != bytes(data),
        "bunSectionOldRawSize": bun.raw_size,
        "bunSectionNewRawSize": new_raw_size,
        "sizeOfImage": new_size_of_image,
        "checksum": checksum,
        "shiftedPointers": shifted_pointers,
    }
    return RepackResult(
        output_bytes=bytes(out),
        delta=total_delta,
        bun_graph_updates={"delta": total_delta, "shiftedPointers": shifted_pointers},
        macho_updates=pe_updates,
        macho_update_details=[],
    )
```

**Note on `strip_authenticode` re-detection:** after `del out[cert_offset:]`, calling `find_pe_layout` again must succeed — the DataDirectory[4] is now zero, so the `bun_section_not_end_of_file` guard applies and `.bun` raw data must reach EOF. On the real binary the cert sits immediately after `.bun`'s file-aligned raw data, so truncation makes `.bun` last. If a future binary pads between `.bun` and the cert, this guard will catch it — do not silently relax it.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_pe.py -v`
Expected: PASS (checksum test passes with fixture present, else skips; fixture repack tests always run).

- [ ] **Step 5: Commit**

```bash
git add src/claude_monkey/pe.py tests/test_pe.py
git commit -m "feat: add resize-capable PE .bun repack with Authenticode strip + checksum"
```

---

## Task 4: Broaden `bun_graph` module-path prefix acceptance

The Windows payload's module paths start with `B:/~BUN/`, not `/$bunfs/`. `parse_bun_section` currently flags these as `suspicious path`, which populates `validation_errors`, which makes `inspect_binary_bytes` return `ok=False` and blocks the whole build. Accept the Windows prefix.

**Files:**
- Modify: `src/claude_monkey/bun_graph.py:178`
- Test: `tests/test_bun_graph.py`

**Interfaces:**
- Produces: `parse_bun_section` no longer emits `suspicious path` for paths starting with `B:/~BUN/` or `file:///$bunfs/` or `/$bunfs/`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_bun_graph.py
import struct
from tests.fixtures_bun import TRAILER
from claude_monkey.bun_graph import parse_bun_section


def _payload_with_path(path: bytes) -> bytes:
    content = b"module-body"
    chunks = bytearray()
    path_off = len(chunks); chunks.extend(path)
    content_off = len(chunks); chunks.extend(content)
    modules_off = len(chunks)
    rec = struct.pack("<IIII", path_off, len(path), content_off, len(content))
    rec += struct.pack("<III", 0, 0, 0) + struct.pack("<III", 0, 0, 0x00030201)  # 13 u32 total
    chunks.extend(rec)
    byte_count = len(chunks)
    chunks.extend(struct.pack("<Q", byte_count))
    chunks.extend(struct.pack("<IIIIII", modules_off, len(rec), 0, 0, 0, 0))
    chunks.extend(TRAILER)
    payload = bytes(chunks)
    return struct.pack("<Q", len(payload)) + payload


def test_windows_bunfs_prefix_is_not_suspicious():
    section = _payload_with_path(b"B:/~BUN/root/src/entrypoints/cli.js")
    graph = parse_bun_section(section)
    assert graph.validation_errors == []


def test_unknown_prefix_still_suspicious():
    section = _payload_with_path(b"/etc/passwd")
    graph = parse_bun_section(section)
    assert any("suspicious path" in e for e in graph.validation_errors)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_bun_graph.py -k "windows_bunfs or unknown_prefix" -v`
Expected: FAIL on `test_windows_bunfs_prefix_is_not_suspicious` (Windows prefix currently flagged).

- [ ] **Step 3: Broaden the prefix check**

In `src/claude_monkey/bun_graph.py`, replace line 178:

```python
        if not path.startswith("/$bunfs/") and not path.startswith("file:///$bunfs/"):
```

with:

```python
        _BUNFS_PREFIXES = ("/$bunfs/", "file:///$bunfs/", "B:/~BUN/", "B:\\~BUN\\")
        if not path.startswith(_BUNFS_PREFIXES):
```

(Define `_BUNFS_PREFIXES` as a module-level constant near the top of `bun_graph.py` rather than inside the loop; the inline form above is shown for locality — hoist it.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_bun_graph.py -v`
Expected: PASS (all, including the pre-existing tests).

- [ ] **Step 5: Commit**

```bash
git add src/claude_monkey/bun_graph.py tests/test_bun_graph.py
git commit -m "feat: accept Windows B:/~BUN/ bunfs prefix in bun_graph path validation"
```

---

## Task 5: Container-format detection + dispatch in build path

Route the three Mach-O-specific call sites (`binary_inspect.py`, `builder_v15.py` ×2) through a format sniffer so `build`/`validate` work on a PE input. Add `bun_standalone_pe64` to the supported manifest formats.

**Files:**
- Create: `src/claude_monkey/binary_format.py`
- Modify: `src/claude_monkey/binary_inspect.py`
- Modify: `src/claude_monkey/builder_v15.py` (imports; the two `find_macho_layout` sites at ~172 and ~527; the `repack_changed_modules` call at ~602)
- Modify: `src/claude_monkey/manifest_v2.py:8`
- Test: `tests/test_binary_format.py`, `tests/test_binary_inspect.py`

**Interfaces:**
- Produces (in `binary_format.py`):
  - `def detect_binary_format(data: bytes) -> str` — returns `"macho"` for `0xFEEDFACF` magic, `"pe"` for `MZ`/`PE`, raises `ValueError("unknown_binary_format")` otherwise.
  - `def locate_bun_section(data: bytes) -> tuple[int, int]` — returns `(start, logical_len_including_prefix)` byte range of the `[u64 len][payload]` section, dispatching on format. For PE, slices to `8 + declared_payload_len` (not the file-aligned raw size).
  - `def repack_for_format(source: bytes, changed_modules: dict[str, bytes]) -> RepackResult` — dispatches to `macho.repack`/`pe.repack_changed_modules`. (Note: the Mach-O repack lives in `repack.repack_changed_modules`; import and dispatch.)
- `manifest_v2.SUPPORTED_BINARY_FORMATS` gains `"bun_standalone_pe64"`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_binary_format.py
import pytest
from tests.fixtures_bun import build_payload
from tests.fixtures_pe import build_pe_fixture
from claude_monkey.binary_format import detect_binary_format, locate_bun_section


def test_detect_pe():
    section, _ = build_payload()
    data = build_pe_fixture(section)
    assert detect_binary_format(data) == "pe"


def test_detect_macho():
    from tests.fixtures_bun import build_aligned_macho_fixture
    data = build_aligned_macho_fixture()
    assert detect_binary_format(data) == "macho"


def test_detect_unknown():
    with pytest.raises(ValueError):
        detect_binary_format(b"\x7fELF" + b"\x00" * 100)


def test_locate_bun_section_pe_matches_payload():
    section, _ = build_payload()
    data = build_pe_fixture(section)
    start, length = locate_bun_section(data)
    assert data[start:start + length] == section
```

```python
# append to tests/test_binary_inspect.py  (create if absent)
import pytest
from tests.claude_binary import win_claude_bin
from claude_monkey.binary_inspect import inspect_binary_bytes


def test_inspect_real_windows_binary_ok():
    src = win_claude_bin()
    if not src.exists():
        pytest.skip(f"missing Windows claude.exe fixture: {src}")
    result = inspect_binary_bytes(src.read_bytes(), source_path=str(src))
    assert result["ok"] is True
    assert result["format"] == "pe64"
    assert any(m["path"] == "B:/~BUN/root/src/entrypoints/cli.js" for m in result["modules"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_binary_format.py tests/test_binary_inspect.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'claude_monkey.binary_format'`

- [ ] **Step 3: Implement the dispatcher and wire the call sites**

Create `src/claude_monkey/binary_format.py`:

```python
"""Container-format detection and dispatch (Mach-O vs PE) for the build path."""
from __future__ import annotations

import struct

from claude_monkey.repack import RepackResult

MACHO_MAGIC_64_LE = 0xFEEDFACF


def detect_binary_format(data: bytes) -> str:
    if len(data) >= 4 and struct.unpack_from("<I", data, 0)[0] == MACHO_MAGIC_64_LE:
        return "macho"
    if len(data) >= 2 and data[0:2] == b"MZ":
        return "pe"
    raise ValueError("unknown_binary_format")


def locate_bun_section(data: bytes) -> tuple[int, int]:
    fmt = detect_binary_format(data)
    if fmt == "macho":
        from claude_monkey.macho import find_macho_layout
        layout = find_macho_layout(data)
        return layout.bun_section.offset, layout.bun_section.size
    from claude_monkey.pe import find_pe_layout
    layout = find_pe_layout(data)
    bun = layout.bun_section
    declared = struct.unpack_from("<Q", data, bun.raw_pointer)[0]
    return bun.raw_pointer, 8 + declared


def repack_for_format(source: bytes, changed_modules: dict[str, bytes]) -> RepackResult:
    fmt = detect_binary_format(source)
    if fmt == "macho":
        from claude_monkey.repack import repack_changed_modules
        return repack_changed_modules(source, changed_modules)
    from claude_monkey.pe import repack_changed_modules as pe_repack
    return pe_repack(source, changed_modules)
```

In `src/claude_monkey/binary_inspect.py`, replace the `find_macho_layout` usage with format dispatch and set `format` from the detected container:

```python
from claude_monkey.binary_format import detect_binary_format, locate_bun_section
# remove: from claude_monkey.macho import find_macho_layout

def inspect_binary_bytes(data: bytes, *, source_path: str) -> dict[str, Any]:
    source_sha = hashlib.sha256(data).hexdigest()
    try:
        fmt = detect_binary_format(data)
        start, length = locate_bun_section(data)
        graph = parse_bun_section(data[start:start + length])
    except Exception as exc:
        return {  # unchanged failure dict, but set "format": "unknown"
            ...
        }
    return {
        ...
        "format": "macho64" if fmt == "macho" else "pe64",
        ...
        "bun": {
            "segment": "" ,  # PE has no segment; keep key for schema stability
            "section": ".bun",
            ...
        },
        ...
    }
```

Keep the `bun.segment`/`bun.section` keys present for schema stability: for PE set `segment` to `""` and `section` to `".bun"`; for Mach-O keep the existing `layout.bun_segment.name`/`layout.bun_section.name` (branch on `fmt`). Preserve every other field in the returned dict unchanged.

In `src/claude_monkey/builder_v15.py`:
- Replace `from claude_monkey.macho import MachOError, find_macho_layout` with an added import `from claude_monkey.binary_format import locate_bun_section, repack_for_format` (keep `MachOError`/`find_macho_layout` import only if still referenced elsewhere; remove if not).
- At the `validate_package` site (~line 172) and the `build_patchset_v15` site (~line 527), replace:
  ```python
  layout = find_macho_layout(source)
  graph = parse_bun_section(source[layout.bun_section.offset : layout.bun_section.offset + layout.bun_section.size])
  ```
  with:
  ```python
  start, length = locate_bun_section(source)
  graph = parse_bun_section(source[start : start + length])
  ```
- At the repack site (~line 602), replace `repack = repack_changed_modules(source, changed_modules)` with `repack = repack_for_format(source, changed_modules)`.

In `src/claude_monkey/manifest_v2.py:8`:

```python
SUPPORTED_BINARY_FORMATS = {"bun_standalone_macho64", "bun_standalone_pe64"}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_binary_format.py tests/test_binary_inspect.py tests/test_builder_v15.py tests/test_bun_graph.py -v`
Expected: PASS (existing Mach-O builder tests still green — the dispatcher routes them unchanged).

- [ ] **Step 5: Commit**

```bash
git add src/claude_monkey/binary_format.py src/claude_monkey/binary_inspect.py \
        src/claude_monkey/builder_v15.py src/claude_monkey/manifest_v2.py \
        tests/test_binary_format.py tests/test_binary_inspect.py
git commit -m "feat: dispatch bun section parse/repack by container format (macho|pe)"
```

---

## Task 6: Windows build hygiene — signing no-op, output filename

Make signing a no-op for PE builds and emit `claude.exe` (not `claude`) when the source is a PE binary, so a PE `build` completes without invoking macOS `codesign`.

**Files:**
- Modify: `src/claude_monkey/builder_v15.py` (`_apply_signing_v15` ~line 433; output filename ~line 613)
- Test: `tests/test_builder_v15.py`

**Interfaces:**
- Produces: when the source binary is PE, `_apply_signing_v15` records `{"status": "skipped", "reason": "pe_no_signing"}` and calls no `codesign`; the output file is named `claude.exe`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_builder_v15.py
# (Follow the existing test module's fixture/import conventions — reuse its
#  BuildRequestV15 construction helper and successful_runner from
#  tests/builder_fixtures.py. This test drives a PE fixture through build and
#  asserts the output name + skipped signing.)
```

Concretely, add a test that builds a minimal PE fixture (from `tests/fixtures_pe.py`) with an empty/no-op package set through `build_patchset_v15`, asserting:
- `report.outputPath` ends with `claude.exe`;
- `report.signingResult["status"] == "skipped"`;
- the injected `command_runner` was never called with a `codesign` argv.

Model the request construction on the existing `test_builder_v15.py` cases; if the current suite has no "build with zero changed modules" path, target the Task 7 end-to-end driver instead and fold this assertion there (note in the review that this task's assertion moved to Task 7).

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_builder_v15.py -k "pe" -v`
Expected: FAIL — output named `claude`, signing attempted.

- [ ] **Step 3: Implement the guards**

In `_apply_signing_v15` (~line 433), branch on the source format. Read the source once and detect:

```python
from claude_monkey.binary_format import detect_binary_format

def _apply_signing_v15(report, output, command_runner, *, source_bytes=None):
    fmt = detect_binary_format(source_bytes) if source_bytes is not None else "macho"
    if fmt == "pe":
        report.signingResult = {"status": "skipped", "reason": "pe_no_signing"}
        return
    # ... existing macOS codesign path unchanged ...
```

Thread `source_bytes` (already loaded in `build_patchset_v15` as `source`) into the `_apply_signing_v15` call. If the existing signature can't take a keyword cleanly, detect the format from `request.source_path.read_bytes()[:4]` at the call site and pass a small `format` flag — keep the change minimal and localized.

For the output filename (~line 613):

```python
from claude_monkey.binary_format import detect_binary_format
output_name = "claude.exe" if detect_binary_format(source) == "pe" else "claude"
output = request.output_dir / output_name
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_builder_v15.py -v`
Expected: PASS (all, including pre-existing Mach-O cases which still get `claude` + real signing via the injected runner).

- [ ] **Step 5: Commit**

```bash
git add src/claude_monkey/builder_v15.py tests/test_builder_v15.py
git commit -m "feat: skip codesign and emit claude.exe for PE builds"
```

---

## Task 7: End-to-end pipeline proof — real length-changing patch on the real claude.exe

Prove the whole real vocab on Mac: a thin driver constructs a `BuildRequestV15` pointing at the downloaded `claude.exe`, applies a **real, length-changing** patch package that satisfies fail-closed pinning (correct version + SHA-256 + module identity), and produces a structurally-valid patched `claude.exe`. This is "the capybaras minus the art" — the genuine `manifest_v2 → module_patch → pe repack` chain, end to end.

**Files:**
- Create: `tests/fixtures_win_package/` (a real patch package targeting win32-x64 2.1.201 — a single trivial-but-real `replace_exact` op with a length change on `cli.js`)
- Create: `tests/test_windows_pipeline.py`
- Create: `scripts/win_spike_driver.py` (the ~40-line thin driver from brief §12 Step 1)

**Interfaces:**
- Consumes: `claude_monkey.builder_v15.build_patchset_v15`, `BuildRequestV15`; `tests.claude_binary.win_claude_bin`.
- Produces: `scripts/win_spike_driver.py` with `def build_spike(source: Path, package_dir: Path, out_dir: Path) -> Path` returning the patched binary path.

- [ ] **Step 1: Author the real Windows-target package**

Create `tests/fixtures_win_package/patch.json` with a single module operation on `B:/~BUN/root/src/entrypoints/cli.js`. Choose an anchor that is **unique** in the Windows `cli.js` and whose replacement changes length. A safe, verified-unique anchor from planning is the app-shell function signature `function eKo(e){let t=OJe.c(78)` (the Windows-renamed counterpart of the macOS `VKo`/`MXe`). The operation inserts a harmless marker comment before it (length change, no behavior change):

```json
{
  "schemaVersion": 1,
  "kind": "patch",
  "id": "win-spike-probe",
  "label": "Windows Spike Probe",
  "description": "Minimal real length-changing patch proving the PE pipeline end-to-end.",
  "packageVersion": "0.1.0",
  "compatibility": { "claudeVersions": ["2.1.201"] },
  "patch": {
    "engine": "bun_graph_repack",
    "targets": [
      {
        "sourceIdentity": {
          "claudeVersion": "2.1.201",
          "versionOutput": "2.1.201 (Claude Code)",
          "sha256": "fb804ee019bfbb8d7e85abf965e528e53b5aa5a4e4ebc0f164139dc10a9e0320",
          "sizeBytes": 241591968,
          "platform": "win32",
          "arch": "x64"
        },
        "requiredEngine": "bun_graph_repack",
        "requiredBinaryFormat": "bun_standalone_pe64",
        "modules": [
          {
            "path": "B:/~BUN/root/src/entrypoints/cli.js",
            "contentSha256": "63154b978bb29a873e54fa8a622a5f5bce3b5cd3461cfa926cce010cabced1e2",
            "contentLength": 18745538,
            "operations": [
              {
                "opId": "win-spike-marker-2-1-201",
                "label": "Insert a marker comment before the app-shell function",
                "type": "insert_before",
                "insertBefore": "function eKo(e){let t=OJe.c(78)",
                "requireWithinRange": ["function eKo(e){"],
                "replacement": { "inline": "/*__WIN_SPIKE_MARKER__*/" }
              }
            ]
          }
        ]
      }
    ]
  }
}
```

**Before committing this file, verify the anchor and hashes against the real binary** (they were confirmed during planning, but re-verify — the plan's reviewer cannot):

```bash
uv run python - <<'PY'
import struct, hashlib, sys
sys.path.insert(0, "src")
from pathlib import Path
from claude_monkey.pe import find_pe_layout
from claude_monkey.bun_graph import parse_bun_section
from tests.claude_binary import win_claude_bin
data = win_claude_bin().read_bytes()
print("binary sha256:", hashlib.sha256(data).hexdigest(), "size:", len(data))
lay = find_pe_layout(data)
b = lay.bun_section
declared = struct.unpack_from("<Q", data, b.raw_pointer)[0]
g = parse_bun_section(data[b.raw_pointer:b.raw_pointer + 8 + declared])
m = g.module_by_path("B:/~BUN/root/src/entrypoints/cli.js")
print("cli.js sha256:", hashlib.sha256(m.content).hexdigest(), "len:", m.content_size)
print("anchor count:", m.content.count(b"function eKo(e){let t=OJe.c(78)"))
PY
```

Expected: binary sha `fb804ee0...`, size `241591968`; cli.js sha `63154b97...`, len `18745538`; anchor count `1`. If the anchor count is not 1, pick another unique anchor and update `insertBefore`/`requireWithinRange` before proceeding. (Confirm `insert_before` with an `inline` replacement is a supported `manifest_v2` operation shape by checking `module_patch._resolve_operation` and `manifest_v2.parse_operation`; if `inline` replacements use a different key such as `{"text": ...}` or base64, match the existing schema exactly — read `packages/*/patch.json` and `manifest_v2.py` for the canonical form.)

- [ ] **Step 2: Write the failing end-to-end test**

```python
# tests/test_windows_pipeline.py
import struct
from pathlib import Path
import pytest
from tests.claude_binary import win_claude_bin
from claude_monkey.pe import find_pe_layout
from claude_monkey.bun_graph import parse_bun_section

FIXTURE_PKG = Path(__file__).parent / "fixtures_win_package"


def test_pe_pipeline_end_to_end(tmp_path):
    src = win_claude_bin()
    if not src.exists():
        pytest.skip(f"missing Windows claude.exe fixture: {src}")
    from scripts.win_spike_driver import build_spike
    out = build_spike(src, FIXTURE_PKG, tmp_path)
    assert out.name == "claude.exe"
    data = out.read_bytes()

    # Structurally valid PE with .bun last-in-file, Authenticode stripped.
    layout = find_pe_layout(data)
    assert layout.security_rva == 0
    assert layout.bun_section.raw_pointer + layout.bun_section.raw_size == len(data)

    # Valid checksum.
    check = bytearray(data)
    struct.pack_into("<I", check, layout.checksum_offset, 0)
    from claude_monkey.pe import pe_checksum
    assert pe_checksum(bytes(check)) == struct.unpack_from("<I", data, layout.checksum_offset)[0]

    # The real length-changing edit is present and the graph re-parses cleanly.
    declared = struct.unpack_from("<Q", data, layout.bun_section.raw_pointer)[0]
    section = data[layout.bun_section.raw_pointer:layout.bun_section.raw_pointer + 8 + declared]
    graph = parse_bun_section(section)
    assert graph.validation_errors == []
    cli = graph.module_by_path("B:/~BUN/root/src/entrypoints/cli.js")
    assert b"/*__WIN_SPIKE_MARKER__*/" in cli.content
    assert cli.content_size == 18745538 + len(b"/*__WIN_SPIKE_MARKER__*/")
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_windows_pipeline.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.win_spike_driver'`

- [ ] **Step 4: Write the thin driver**

```python
# scripts/win_spike_driver.py
"""Thin driver for the Windows PE spike: apply a patch package to a PE claude.exe
through the genuine build vocab, skipping CLI plumbing (source auto-discovery,
arg parsing). Mirrors brief §12 Step 1's ~40-line driver.
"""
from __future__ import annotations

from pathlib import Path

from claude_monkey.builder_v15 import BuildRequestV15, build_patchset_v15


def build_spike(source: Path, package_dir: Path, out_dir: Path) -> Path:
    source = Path(source)
    request = BuildRequestV15(
        source_path=source,
        output_dir=Path(out_dir),
        package_dirs=[Path(package_dir)],
        source_version="2.1.201",
        source_version_output="2.1.201 (Claude Code)",
        platform="win32",
        arch="x64",
        run_signing=False,   # PE builds skip signing (Task 6 also no-ops it)
        run_smoke=False,     # cannot execute a Windows PE on macOS — deferred to Windows
        activate=False,
    )
    report = build_patchset_v15(request)
    if report.outputPath is None:
        raise SystemExit(f"build failed: {report.failureReason} ({report.status})")
    return Path(report.outputPath)


if __name__ == "__main__":
    import sys
    from tests.claude_binary import win_claude_bin

    pkg = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("tests/fixtures_win_package")
    out = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("build/win-spike")
    out.mkdir(parents=True, exist_ok=True)
    result = build_spike(win_claude_bin(), pkg, out)
    print(f"patched binary: {result}")
```

**On `run_smoke=False`:** the smoke test executes the output binary (`[binary, "--version"]`). A Windows PE cannot run on macOS, so smoke must be skipped here — this is the one genuine gate the Mac spike cannot exercise, and it is exactly the §9 item deferred to a Windows box. Confirm `build_patchset_v15` honors `run_smoke=False` by skipping the smoke stage (read the smoke-stage guard ~line 689); if it does not, that is a real gap — surface it to the controller rather than working around it.

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_windows_pipeline.py -v`
Expected: PASS (with fixture present). Also run the driver directly for a smoke of the driver itself:

Run: `uv run python scripts/win_spike_driver.py`
Expected: prints `patched binary: build/win-spike/claude.exe`

- [ ] **Step 6: Commit**

```bash
git add tests/fixtures_win_package/ tests/test_windows_pipeline.py scripts/win_spike_driver.py
git commit -m "feat: end-to-end PE pipeline proof — real length-changing patch on real claude.exe"
```

---

## Task 8: Full-suite regression pass

Confirm nothing on the Mach-O path regressed, and the new PE path is green.

**Files:** none (verification only).

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest -q`
Expected: all pass or skip (real-binary tests skip only if fixtures absent). Zero failures. Note in the run summary how many skipped and why (missing macOS/Windows binary fixtures is expected).

- [ ] **Step 2: Confirm the Mach-O generator parity test still passes if its fixture exists**

Run: `uv run pytest tests/test_generator_parity.py tests/test_capybara_onsen.py -v`
Expected: PASS or SKIP (skips if `~/.local/share/claude/versions/2.1.201` absent). If it FAILS, the Task 5 dispatch changed Mach-O behavior — investigate before proceeding.

- [ ] **Step 3: Commit any lint/format fixes**

```bash
uv run ruff check src/claude_monkey/pe.py src/claude_monkey/binary_format.py \
                  tests/fixtures_pe.py tests/test_pe.py tests/test_binary_format.py \
                  tests/test_windows_pipeline.py scripts/win_spike_driver.py
# fix anything ruff reports, then:
git add -A && git commit -m "chore: lint fixes for Windows PE spike modules" || echo "nothing to commit"
```

---

## Deferred to a Windows box (NOT in this plan — handoff notes)

These are explicitly out of scope for the Mac-side spike and must be validated on real Windows hardware (brief §9):

1. **Visual confirmation of the capybaras.** A patched `claude.exe` cannot be executed on macOS. This plan proves the binary is *structurally* correct (parses, checksums, module edits present); launching it and watching the onsen scene is a Windows step.
2. **`capybara-onsen` Windows target re-authoring.** **Critical planning finding:** the brief §12 Step 3 assumes the patch's target module text is platform-identical and only the outer binary differs. This is **empirically false** for 2.1.201: the win32-x64 bundle is minified with *different symbol names* than darwin-arm64 (`VKo`→`eKo`, `MXe`→`OJe`, the `Box` component `B` is a different identifier, `t4`/`HS`/`fde`/`A_` all differ), and `cli.js` differs in both length (18745538 vs 18700756) and SHA-256. Re-pinning capybara-onsen for Windows is therefore **not** a hash swap — it requires re-authoring every anchor in `examples/capybara-onsen-generator/generate_package.py`'s `VERSION_FRAGILE_ANCHORS` and remapping every host identifier referenced in the helper/replacement glue against the Windows bundle's minified names (exactly the maintenance surface that file's header comment warns about). That reverse-engineering can *begin* on Mac (the win32 `cli.js` is extractable), but the resulting TUI's correctness — gutters, modal containment, resize behavior — can only be confirmed by running it in Windows Terminal. Task 7 deliberately proves the pipeline with a minimal real patch instead, so the pipeline is de-risked independently of the anchor re-authoring effort.
3. **Smoke test** (`[claude.exe, "--version"]`), SmartScreen/Defender behavior on an unsigned patched exe, the shim launcher, updater-clobber behavior, GUI, start-at-login (brief §5–§9).

---

## Self-Review Notes (planning)

- **Spec coverage vs brief §12:** Step 1 (CLI far enough to `build`) → Tasks 5, 6, 7 (thin driver + signing no-op + `.exe` output + `CLAUDE_MONKEY_SOURCE` bypassed by direct `BuildRequestV15`). Step 2 (`pe.py`, ~80% of effort) → Tasks 1, 2, 3. Step 3 (re-pin, satisfy fail-closed) → Task 7 (real pins on a real package) + deferred capybara re-authoring (documented as a Windows/RE task, not hand-waved). Step 4 (apply for real) → Task 7. Steps 5–6 (shim, see cappies) → deferred (Windows-only). The `bun_graph` prefix fix (Task 4) is a planning discovery not in the brief — the brief claims `bun_graph` ports untouched; the real Windows payload disproves that.
- **Type consistency:** `find_pe_layout → PELayout`; `repack_changed_modules → RepackResult` (reused from `repack.py`, same field names, so `BuildReportV2.machoUpdates` is populated without schema change); `detect_binary_format`/`locate_bun_section`/`repack_for_format` names consistent across Tasks 5–7 and the driver.
- **No placeholders:** every code step ships runnable code; the one intentionally-open step is Task 6 Step 1's test, which defers to the existing suite's fixture conventions (the plan can't reproduce that module's harness verbatim without over-copying) and gives the reviewer an explicit fold-into-Task-7 fallback.
