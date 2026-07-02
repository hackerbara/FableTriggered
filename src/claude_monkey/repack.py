from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from claude_monkey.bun_graph import parse_bun_section
from claude_monkey.macho import find_macho_layout, shift_macho_after_bun_change


@dataclass(frozen=True)
class RepackResult:
    output_bytes: bytes
    delta: int
    bun_graph_updates: dict[str, Any]
    macho_updates: dict[str, Any]
    macho_update_details: list[dict[str, Any]]


def repack_changed_modules(source: bytes, changed_modules: dict[str, bytes]) -> RepackResult:
    if not changed_modules:
        raise ValueError("changed_modules_required")
    layout = find_macho_layout(source)
    section_start = layout.bun_section.offset
    section_end = layout.bun_section.offset + layout.bun_section.size
    graph = parse_bun_section(source[section_start:section_end])
    current_section = graph.section_bytes
    original_section_end = section_end
    original_order = {module.path: module.content_offset for module in graph.modules}
    total_delta = 0
    shifted_pointers = 0
    old_payload_length = graph.declared_payload_len
    old_byte_count = graph.byte_count
    for module_path in sorted(changed_modules, key=lambda path: original_order[path]):
        graph = parse_bun_section(current_section)
        rewrite = graph.replace_module_content(module_path, changed_modules[module_path])
        if rewrite.validation_errors:
            raise ValueError(f"bun_graph_validation_failed:{rewrite.validation_errors}")
        current_section = rewrite.section_bytes
        total_delta += rewrite.delta
        shifted_pointers += rewrite.shifted_pointers
    prefix = source[:section_start]
    suffix_start = section_end
    source_with_section = prefix + current_section + source[suffix_start:]
    shifted, macho_update_details = shift_macho_after_bun_change(
        source_with_section, insert_abs=original_section_end, delta=total_delta
    )
    reparsed_layout = find_macho_layout(shifted)
    reparsed_section = shifted[
        reparsed_layout.bun_section.offset : reparsed_layout.bun_section.offset
        + reparsed_layout.bun_section.size
    ]
    reparsed_graph = parse_bun_section(reparsed_section)
    return RepackResult(
        output_bytes=shifted,
        delta=total_delta,
        bun_graph_updates={
            "oldPayloadLength": old_payload_length,
            "newPayloadLength": reparsed_graph.declared_payload_len,
            "oldByteCount": old_byte_count,
            "newByteCount": reparsed_graph.byte_count,
            "moduleRecordSize": reparsed_graph.module_record_size,
            "moduleCount": len(reparsed_graph.modules),
            "shiftedPointers": shifted_pointers,
            "validationErrors": reparsed_graph.validation_errors,
        },
        macho_updates={
            "bunSectionSizeDelta": total_delta,
            "bunSegmentSizeDelta": total_delta,
            "linkeditFileoffDelta": total_delta,
            "linkeditVmaddrDelta": total_delta,
            "codeSignatureOffsetDelta": total_delta,
        },
        macho_update_details=macho_update_details,
    )
