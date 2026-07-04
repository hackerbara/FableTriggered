import hashlib
import json
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "thinking-text-drawer"
LIVE_2_1_201 = Path("/Users/MAC/.local/share/claude/versions/2.1.201")

EXPECTED_BINARY_SHA = "a0852d76afc47b30f5cb0b7625ec9a7714cb189f2eeef6c28c77e2be954fb7fd"
EXPECTED_BINARY_SIZE = 231708784
EXPECTED_MODULE_SHA = "46db617a7b13c062fb31595f6244819b11f7cdc6e6fed8e2c3f74a27fb6da1bd"
EXPECTED_MODULE_LENGTH = 18700756


def read_rel(path: str) -> str:
    return (PACKAGE / path).read_text(encoding="utf-8")


def payloads_text() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted((PACKAGE / "payloads").glob("*.js")))


def test_thinking_text_drawer_targets_claude_2_1_201() -> None:
    manifest = json.loads((PACKAGE / "patch.json").read_text(encoding="utf-8"))
    target = manifest["targets"][0]
    identity = target["sourceIdentity"]
    module = target["modules"][0]

    assert manifest["id"] == "thinking-text-drawer"
    assert identity == {
        "claudeVersion": "2.1.201",
        "versionOutput": "2.1.201 (Claude Code)",
        "sha256": EXPECTED_BINARY_SHA,
        "sizeBytes": EXPECTED_BINARY_SIZE,
        "platform": "darwin",
        "arch": "arm64",
    }
    assert module["path"] == "/$bunfs/root/src/entrypoints/cli.js"
    assert module["contentSha256"] == EXPECTED_MODULE_SHA
    assert module["contentLength"] == EXPECTED_MODULE_LENGTH
    assert len(module["operations"]) == 14

    if LIVE_2_1_201.exists():
        assert hashlib.sha256(LIVE_2_1_201.read_bytes()).hexdigest() == EXPECTED_BINARY_SHA


def test_thinking_text_drawer_overlay_only_and_always_available() -> None:
    text = read_rel("README.md") + "\n" + payloads_text()
    footer_target = read_rel("payloads/06-footer-target-thinking.js")

    assert "No thinking captured yet" in text
    assert "request assembly" in read_rel("README.md")
    assert "JSONL" in read_rel("README.md")
    assert "main chat" in read_rel("README.md")
    assert '"thinking"' in footer_target
    assert "frame.visible" not in footer_target
    assert "__CODEX_THINKING_TEXT_DRAWER_FRAME_V1__" in text
    assert "__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__" in text


def test_thinking_text_drawer_x_only_close_contract() -> None:
    text = payloads_text()
    close_payload = read_rel("payloads/09-footer-action-wrap-close.js")
    renderer = read_rel("payloads/11-bottom-overlay-renderer.js")

    assert "footer:close" in read_rel("payloads/01-thinking-text-helpers.js")
    assert "__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__=!1" in read_rel("payloads/01-thinking-text-helpers.js")
    assert "footer:clearSelection" in read_rel("payloads/01-thinking-text-helpers.js")
    assert "return false" in read_rel("payloads/01-thinking-text-helpers.js")
    assert "return!1}},Lm,tDp,Rp)" in close_payload
    assert "x closes" in renderer
    assert "inputOwnsEscape" not in text
    assert "escape" not in renderer.lower()


def test_thinking_text_drawer_collectors_cover_required_sources() -> None:
    helpers = read_rel("payloads/01-thinking-text-helpers.js")
    assert "__codexTTDRecordStructuredThinking" in helpers
    assert "__codexTTDRecordLiveThinking" in helpers
    assert "__codexTTDRecordSalvagedThinking" in helpers
    assert "__codexTTDRecordThinkingSignature" in helpers
    assert "__codexTTDRecordThinkingEstimate" in helpers
    assert "preserve both" in helpers
    assert "slice(0,80)" not in helpers
    assert "Levenshtein" not in helpers


def test_structured_collection_runs_before_ctrl_o_guard() -> None:
    structured = read_rel("payloads/04-structured-thinking-block-collector.js")
    assert "__codexTTDScanAssistantMessage(n)" in structured
    assert "n.message.content.map(I)" in structured
    assert "if(!p&&!i)return null" not in structured
    assert "case\"thinking\"" not in structured
    helpers = read_rel("payloads/01-thinking-text-helpers.js")
    assert "function __codexTTDScanAssistantMessage" in helpers
    assert "__codexTTDRecordRedactedThinking" in helpers
    assert "__codexTTDRecordStructuredThinking" in helpers
    assert "blockIndex:o" in helpers
    assert "blockIndex:r" not in helpers


def test_helper_fixture_merge_and_secondary_sources() -> None:
    helper = read_rel("payloads/01-thinking-text-helpers.js")
    helper_prefix = helper.split("\nfunction Ypr(e){", 1)[0]
    script = textwrap.dedent(
        f"""
        {helper_prefix}
        globalThis.__CODEX_THINKING_TEXT_DRAWER_FRAME_V1__ = undefined;
        __codexTTDRecordLiveThinking({{text:'abc', streamKey:'s1', turnKey:'turn'}});
        __codexTTDRecordLiveThinking({{text:'def', streamKey:'s1', turnKey:'turn'}});
        __codexTTDRecordStructuredThinking({{thinking:'abcdef finalized', messageId:'m1', blockHash:'h1', turnKey:'turn'}});
        __codexTTDRecordRedactedThinking({{messageId:'m2', blockHash:'r1'}});
        __codexTTDRecordThinkingSignature({{chars:128, streamKey:'s1'}});
        __codexTTDRecordThinkingEstimate({{estimatedTokensDelta:7, estimatedTokens:21, streamKey:'s1'}});
        __codexTTDScanAssistantMessage({{uuid:'u1', requestId:'req', timestamp:123, message:{{id:'mid', content:[{{type:'thinking', thinking:'parent text'}}, {{type:'redacted_thinking'}}]}}}});
        const frame = __codexTTDDrawerFrame();
        if (!frame.entries.some(e => e.source === 'structured' && e.sources.includes('live') && e.text === 'abcdef finalized')) throw new Error('structured/live merge failed');
        if (!frame.entries.some(e => e.source === 'structured' && e.text === 'parent text')) throw new Error('parent structured missing');
        if (!frame.entries.some(e => e.source === 'redacted')) throw new Error('redacted marker missing');
        if (!frame.entries.some(e => e.source === 'signature')) throw new Error('signature marker missing');
        if (!frame.entries.some(e => e.source === 'estimate')) throw new Error('estimate marker missing');
        if (frame.entries.length < 4) throw new Error('entries unexpectedly discarded');
        """
    )
    subprocess.run(["node", "-e", script], check=True)


if __name__ == "__main__":
    test_thinking_text_drawer_targets_claude_2_1_201()
    test_thinking_text_drawer_overlay_only_and_always_available()
    test_thinking_text_drawer_x_only_close_contract()
    test_thinking_text_drawer_collectors_cover_required_sources()
    test_structured_collection_runs_before_ctrl_o_guard()
    test_helper_fixture_merge_and_secondary_sources()
    print("thinking-text drawer package checks passed")
