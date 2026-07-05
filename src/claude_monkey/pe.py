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
