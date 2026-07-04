from __future__ import annotations

import json
from pathlib import Path

import pytest

from claude_monkey.builder_v15 import ValidationRequestV15, validate_package

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "packages" / "hotrod-dragons"
LIVE_SOURCE = Path("/Users/MAC/.local/share/claude/versions/2.1.201")

EXPECTED_SOURCE_SHA = "a0852d76afc47b30f5cb0b7625ec9a7714cb189f2eeef6c28c77e2be954fb7fd"
EXPECTED_MODULE_SHA = "46db617a7b13c062fb31595f6244819b11f7cdc6e6fed8e2c3f74a27fb6da1bd"


def _manifest() -> dict:
    return json.loads((PACKAGE_DIR / "patch.json").read_text())


def test_hotrod_dragons_manifest_shape_and_pins():
    manifest = _manifest()
    assert manifest["id"] == "hotrod-dragons"
    assert manifest["schemaVersion"] == 2
    target = manifest["targets"][0]
    assert target["requiredEngine"] == "bun_graph_repack"
    assert target["requiredBinaryFormat"] == "bun_standalone_macho64"
    assert target["sourceIdentity"]["sha256"] == EXPECTED_SOURCE_SHA
    assert target["sourceIdentity"]["claudeVersion"] == "2.1.201"
    assert target["manualSmoke"]["required"] is True

    module = target["modules"][0]
    assert module["path"] == "/$bunfs/root/src/entrypoints/cli.js"
    assert module["contentSha256"] == EXPECTED_MODULE_SHA
    assert module["contentLength"] > 0

    operations = module["operations"]
    assert [op["opId"] for op in operations] == [
        "hotrod-dragons-context-frame-helpers-before-vko-2-1-201",
        "hotrod-dragons-center-columns-a-2-1-201",
        "hotrod-dragons-main-window-me-2-1-201",
        "hotrod-dragons-bottom-stack-de-2-1-201",
        "hotrod-dragons-fullscreen-modal-center-fe-2-1-201",
        "hotrod-dragons-qde-bottom-stack-ee-2-1-201",
        "hotrod-dragons-qde-overlay-center-te-2-1-201",
        "hotrod-dragons-fallback-window-v-2-1-201",
    ]
    for op in operations:
        assert op["type"] == "replace_exact"
        assert op["oldRangeSha256"] and op["oldRangeLength"] is not None


def test_hotrod_dragons_payloads_match_hashes_and_are_mojibake_safe():
    manifest = _manifest()
    operations = manifest["targets"][0]["modules"][0]["operations"]
    import hashlib
    joined = ""
    for op in operations:
        data = (PACKAGE_DIR / op["replacement"]["path"]).read_bytes()
        assert data, f"empty payload {op['opId']}"
        assert hashlib.sha256(data).hexdigest() == op["replacement"]["sha256"]
        text = data.decode("utf-8")
        # v1 mojibake rule: no literal half-block glyph or ESC byte in source
        assert "▀" not in text, f"literal half-block in {op['opId']}"
        assert "\x1b" not in text, f"literal ESC byte in {op['opId']}"
        joined += "\n" + text

    # the scene contract lives entirely in the payloads
    assert "function __CodexHotrodSpriteSceneV11" in joined
    assert "function __hdCenterProviderV4" in joined
    assert "function __CodexHotrodMainWindowV4" in joined
    assert "function __CodexHotrodBottomStackV4" in joined
    assert "__hdResponsiveBreakpointV6=130" in joined
    assert "function __hdRightWidthV6" in joined
    assert "codex-hotrod-v12-right-responsive" in joined
    assert "codex-hotrod-v12-tower-right-responsive" in joined
    assert "A=__hdCenterColumns(T,f)" in joined
    assert "Xd.jsx(fde,{value:s,children:Xd.jsx(t4,{value:i,children:o})})" in joined
    assert '"ink-raw-ansi"' in joined
    assert "String.fromCharCode(9600)" in joined       # half-block generated at runtime
    assert "String.fromCharCode(27)" in joined         # ESC generated at runtime
    assert "setInterval(()=>setPh" in joined           # fire animation tick
    assert "codex-hotrod-v11-scene" in joined
    assert "codex-hotrod-v12-main-window" in joined
    assert "codex-hotrod-v12-bottom-stack" in joined


def test_hotrod_dragons_validates_against_live_2_1_201_source():
    if not LIVE_SOURCE.exists():
        pytest.skip(f"local Claude Code 2.1.201 source missing: {LIVE_SOURCE}")
    result = validate_package(
        ValidationRequestV15(
            source_path=LIVE_SOURCE,
            package_dir=PACKAGE_DIR,
            source_version="2.1.201",
            source_version_output="2.1.201 (Claude Code)",
            platform="darwin",
            arch="arm64",
        )
    )
    assert result["ok"] is True, result
    assert result["operationsResolved"]
