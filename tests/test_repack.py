from __future__ import annotations

from tests.fixtures_bun import MODULE_PATH_0, MODULE_PATH_1, build_macho_fixture

from claude_monkey.binary_inspect import inspect_binary_bytes
from claude_monkey.bun_graph import parse_bun_section
from claude_monkey.macho import find_macho_layout
from claude_monkey.repack import repack_changed_modules


def test_repack_changed_modules_updates_module_and_preserves_inspectability():
    source, _ = build_macho_fixture()
    layout = find_macho_layout(source)
    graph = parse_bun_section(
        source[layout.bun_section.offset : layout.bun_section.offset + layout.bun_section.size]
    )
    new_module = b"function render(){NEW_RENDER_LONGER}\nfunction after(){return 1}\n"
    result = repack_changed_modules(source, {MODULE_PATH_0: new_module})
    assert result.delta > 0
    inspected = inspect_binary_bytes(result.output_bytes, source_path="fixture-output")
    assert inspected["ok"] is True
    assert inspected["validationErrors"] == []
    layout2 = find_macho_layout(result.output_bytes)
    graph2 = parse_bun_section(
        result.output_bytes[layout2.bun_section.offset : layout2.bun_section.offset + layout2.bun_section.size]
    )
    assert graph2.module_by_path(MODULE_PATH_0).content == new_module
    assert graph2.declared_payload_len == graph.declared_payload_len + result.delta


def test_repack_changed_modules_is_deterministic_for_two_modules():
    source, _ = build_macho_fixture()
    changed = {
        MODULE_PATH_1: b"x=1;\n",
        MODULE_PATH_0: b"function render(){NEW_RENDER_LONGER}\nfunction after(){return 1}\n",
    }
    first = repack_changed_modules(source, changed)
    second = repack_changed_modules(source, dict(reversed(list(changed.items()))))
    assert first.output_bytes == second.output_bytes
    inspected = inspect_binary_bytes(first.output_bytes, source_path="fixture-output")
    assert inspected["ok"] is True
