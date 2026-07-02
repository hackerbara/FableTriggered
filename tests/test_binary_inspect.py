from __future__ import annotations

from tests.fixtures_bun import MODULE_PATH_0, build_macho_fixture

from claude_monkey.binary_inspect import inspect_binary_bytes


def test_inspect_binary_bytes_reports_bun_modules():
    data, _ = build_macho_fixture()
    report = inspect_binary_bytes(data, source_path="fixture-claude")
    assert report["ok"] is True
    assert report["format"] == "macho64"
    assert report["bun"]["moduleRecordSize"] == 52
    assert report["modules"][0]["path"] == MODULE_PATH_0
    assert report["validationErrors"] == []
