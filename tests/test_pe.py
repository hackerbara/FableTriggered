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
