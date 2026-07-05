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
