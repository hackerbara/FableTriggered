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
