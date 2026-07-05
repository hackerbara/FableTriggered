from __future__ import annotations

import json
from pathlib import Path

import pytest

from claude_monkey.builder_v15 import ValidationRequestV15, validate_package
from tests.claude_binary import claude_version_path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "packages" / "capybara-onsen"
LIVE_SOURCE = claude_version_path("2.1.201")

EXPECTED_SOURCE_SHA = "a0852d76afc47b30f5cb0b7625ec9a7714cb189f2eeef6c28c77e2be954fb7fd"
EXPECTED_MODULE_SHA = "46db617a7b13c062fb31595f6244819b11f7cdc6e6fed8e2c3f74a27fb6da1bd"


def _manifest() -> dict:
    return json.loads((PACKAGE_DIR / "patch.json").read_text())


def test_capybara_onsen_manifest_shape_and_pins():
    manifest = _manifest()
    assert manifest["id"] == "capybara-onsen"
    assert manifest["schemaVersion"] == 1
    assert manifest["kind"] == "patch"
    assert manifest["patch"]["engine"] == "bun_graph_repack"
    target = manifest["patch"]["targets"][0]
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
        "capy-onsen-context-frame-helpers-before-vko-2-1-201",
        "capy-onsen-center-columns-a-2-1-201",
        "capy-onsen-main-window-me-2-1-201",
        "capy-onsen-bottom-stack-de-2-1-201",
        "capy-onsen-fullscreen-modal-center-fe-2-1-201",
        "capy-onsen-qde-bottom-stack-ee-2-1-201",
        "capy-onsen-qde-overlay-center-te-2-1-201",
        "capy-onsen-fallback-window-v-2-1-201",
    ]
    for op in operations:
        assert op["type"] == "replace_exact"
        assert op["oldRangeSha256"] and op["oldRangeLength"] is not None


def test_capybara_onsen_payloads_match_hashes_and_are_mojibake_safe():
    manifest = _manifest()
    operations = manifest["patch"]["targets"][0]["modules"][0]["operations"]
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
    assert "function __coCenterProviderV4" in joined
    assert "function __CodexCapyOnsenMainWindowV4" in joined
    assert "function __CodexCapyOnsenBottomStackV4" in joined
    assert "__coResponsiveBreakpointV6=140" in joined
    assert "__coClipColsV7=2" in joined
    assert "__coW=__coArtW-__coClipColsV7" in joined
    assert "function __coCropRunsV7" in joined
    assert "function __coRightWidthV6" in joined
    assert "codex-capy-onsen-v6-right-responsive" in joined
    assert "codex-capy-onsen-v6-pool-right-responsive" in joined
    assert "codex-capy-onsen-v5-width-readout" not in joined
    assert "Xd.jsx(fde,{value:s,children:Xd.jsx(t4,{value:i,children:o})})" in joined
    assert '"ink-raw-ansi"' in joined
    assert "String.fromCharCode(9600)" in joined       # half-block generated at runtime
    assert "String.fromCharCode(27)" in joined         # ESC generated at runtime
    assert "%__coPhases),180)" in joined               # water/steam animation tick, 180ms
    assert "codex-capy-onsen-v4-main-window" in joined
    assert "codex-capy-onsen-v4-bottom-stack" in joined


def test_capybara_onsen_validates_against_live_2_1_201_source():
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
