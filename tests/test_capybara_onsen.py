from __future__ import annotations

import json
from pathlib import Path

import pytest

from claude_monkey.builder_v15 import ValidationRequestV15, validate_package

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = ROOT / "packages" / "capybara-onsen"
LIVE_SOURCE = Path("/Users/MAC/.local/share/claude/versions/2.1.199")

EXPECTED_SOURCE_SHA = "e3cb61abc8a2ec7b98976cee1ffdde5a3fa755c9990bc8d688cd89290e0dcec0"
EXPECTED_MODULE_SHA = "e30c857c2e1130ff0fa9d14349a210c588f8115fc8ac86e120c454547efc0c55"


def _manifest() -> dict:
    return json.loads((PACKAGE_DIR / "patch.json").read_text())


def test_capybara_onsen_manifest_shape_and_pins():
    manifest = _manifest()
    assert manifest["id"] == "capybara-onsen"
    assert manifest["schemaVersion"] == 2
    target = manifest["targets"][0]
    assert target["requiredEngine"] == "bun_graph_repack"
    assert target["requiredBinaryFormat"] == "bun_standalone_macho64"
    assert target["sourceIdentity"]["sha256"] == EXPECTED_SOURCE_SHA
    assert target["sourceIdentity"]["claudeVersion"] == "2.1.199"
    assert target["manualSmoke"]["required"] is True

    module = target["modules"][0]
    assert module["path"] == "/$bunfs/root/src/entrypoints/cli.js"
    assert module["contentSha256"] == EXPECTED_MODULE_SHA
    assert module["contentLength"] > 0

    operations = module["operations"]
    assert [op["opId"] for op in operations] == [
        "capy-onsen-scene-helpers-before-v8o-2-1-199",
        "capy-onsen-fullscreen-scene-pe-2-1-199",
        "capy-onsen-composer-flank-ue-2-1-199",
        "capy-onsen-composer-parent-le-2-1-199",
        "capy-onsen-fallback-scene-v-2-1-199",
    ]
    for op in operations:
        assert op["type"] == "replace_exact"
        assert op["oldRangeSha256"] and op["oldRangeLength"] is not None


def test_capybara_onsen_payloads_match_hashes_and_are_mojibake_safe():
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
    assert "function __CodexCapyOnsenSceneV1" in joined
    assert "function __CodexCapyOnsenPoolBottomV1" in joined
    assert '"ink-raw-ansi"' in joined
    assert "String.fromCharCode(9600)" in joined       # half-block generated at runtime
    assert "String.fromCharCode(27)" in joined         # ESC generated at runtime
    assert "%__coPhases),180)" in joined               # water/steam animation tick, 180ms
    assert "codex-capy-onsen-v1-scene" in joined


def test_capybara_onsen_validates_against_live_2_1_199_source():
    if not LIVE_SOURCE.exists():
        pytest.skip(f"local Claude Code 2.1.199 source missing: {LIVE_SOURCE}")
    result = validate_package(
        ValidationRequestV15(
            source_path=LIVE_SOURCE,
            package_dir=PACKAGE_DIR,
            source_version="2.1.199",
            source_version_output="2.1.199 (Claude Code)",
            platform="darwin",
            arch="arm64",
        )
    )
    assert result["ok"] is True, result
    assert result["operationsResolved"]
