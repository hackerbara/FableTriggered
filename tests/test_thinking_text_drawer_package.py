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
EXPECTED_OPERATION_IDS = {
    "thinking-helpers-before-ypr",
    "thinking-message-start-turn-collector",
    "thinking-message-stop-turn-collector",
    "thinking-live-delta-collector",
    "thinking-signature-collector",
    "thinking-parent-structured-collector",
    "thinking-footer-open-state",
    "thinking-footer-target",
    "thinking-footer-selection-flag",
    "thinking-footer-action-wrap-open",
    "thinking-footer-action-wrap-close",
    "thinking-selected-overlay-globals",
    "thinking-bottom-overlay-renderer",
    "thinking-footer-status-bar",
    "thinking-system-token-estimate",
    "thinking-cancel-salvage-collector",
}


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
    assert {op["opId"] for op in module["operations"]} == EXPECTED_OPERATION_IDS
    assert len(module["operations"]) == len(EXPECTED_OPERATION_IDS)
    postcondition_values = {item["value"] for item in target["postconditions"]}
    for value in [
        "__CODEX_THINKING_TEXT_DRAWER_FRAME_V1__",
        "__CODEX_THINKING_TEXT_DRAWER_OPEN_V1__",
        "__CODEX_THINKING_TEXT_DRAWER_TURN_V1__",
        "No thinking captured yet",
        "x closes",
        "thinking-available",
        "__codexTTDRecordLiveThinking",
        "__codexTTDRecordStructuredThinking",
        "__codexTTDRecordSalvagedThinking",
        "__codexTTDRecordThinkingSignature",
        "__codexTTDRecordThinkingEstimate",
        "__codexTTDRecordRedactedThinking",
    ]:
        assert value in postcondition_values

    if LIVE_2_1_201.exists():
        assert hashlib.sha256(LIVE_2_1_201.read_bytes()).hexdigest() == EXPECTED_BINARY_SHA


def test_manifest_operations_match_source_and_payload_hashes() -> None:
    manifest = json.loads((PACKAGE / "patch.json").read_text(encoding="utf-8"))
    module = manifest["targets"][0]["modules"][0]
    source_path = ROOT / ".development" / "artifacts" / "claude-2.1.201-thinking-text-drawer-source-module0.js"
    assert source_path.exists(), source_path
    source = source_path.read_text(encoding="utf-8")
    for op in module["operations"]:
        exact = op["exact"]
        assert source.count(exact) == 1, op["opId"]
        assert op["oldRangeLength"] == len(exact.encode("utf-8")), op["opId"]
        assert op["oldRangeSha256"] == hashlib.sha256(exact.encode("utf-8")).hexdigest(), op["opId"]
    for op in module["operations"]:
        payload = PACKAGE / op["replacement"]["path"]
        assert payload.exists(), op["opId"]
        assert op["replacement"]["sha256"] == hashlib.sha256(payload.read_bytes()).hexdigest(), op["opId"]


def test_thinking_text_drawer_overlay_only_and_always_available() -> None:
    text = read_rel("README.md") + "\n" + payloads_text()
    footer_target = read_rel("payloads/06-footer-target-thinking.js")

    assert "No thinking captured yet" in text
    assert "request assembly" in read_rel("README.md")
    assert "JSONL" in read_rel("README.md")
    assert "main chat" in read_rel("README.md")
    assert "transcript" in read_rel("README.md")
    assert "model-visible" in read_rel("README.md")
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


def test_operations_stay_out_of_request_and_persistence_surfaces() -> None:
    manifest = json.loads((PACKAGE / "patch.json").read_text(encoding="utf-8"))
    op_ids = {op["opId"] for op in manifest["targets"][0]["modules"][0]["operations"]}
    assert op_ids == EXPECTED_OPERATION_IDS
    forbidden_op_fragments = ["request-assembly", "jsonl", "transcript-persist", "prompt-context"]
    for op_id in op_ids:
        assert not any(fragment in op_id for fragment in forbidden_op_fragments), op_id
    payload_text = payloads_text()
    assert "messages.push" not in payload_text
    assert "appendFile" not in payload_text
    assert "writeFile" not in payload_text
    assert "transcript" not in payload_text.lower()


def test_helper_fixture_review_regressions() -> None:
    helper = read_rel("payloads/01-thinking-text-helpers.js")
    helper_prefix = helper.split("\nfunction Ypr(e){", 1)[0]
    script = textwrap.dedent(
        f"""
        {helper_prefix}
        function assert(cond, msg) {{ if (!cond) throw new Error(msg); }}

        globalThis.__CODEX_THINKING_TEXT_DRAWER_FRAME_V1__ = undefined;
        __codexTTDBeginTurn('turn-a');
        __codexTTDRecordLiveThinking({{text:'first', streamKey:0}});
        __codexTTDEndTurn();
        __codexTTDBeginTurn('turn-b');
        __codexTTDRecordLiveThinking({{text:'second', streamKey:0}});
        let frame = __codexTTDDrawerFrame();
        assert(frame.entries.filter(e => e.source === 'live').length === 2, 'live deltas from separate turns must not merge');
        assert(frame.entries.some(e => e.turnKey === 'turn-a'), 'turn-a missing');
        assert(frame.entries.some(e => e.turnKey === 'turn-b'), 'turn-b missing');

        globalThis.__CODEX_THINKING_TEXT_DRAWER_FRAME_V1__ = undefined;
        __codexTTDBeginTurn('msg-1');
        __codexTTDRecordLiveThinking({{text:'abc', streamKey:0}});
        __codexTTDRecordStructuredThinking({{thinking:'abcdef final', messageId:'msg-1', requestId:'req-1', blockHash:'h-msg'}});
        frame = __codexTTDDrawerFrame();
        assert(frame.entries.length === 1, 'live and structured for same message should merge even when requestId exists');
        assert(frame.entries[0].source === 'structured' && frame.entries[0].sources.includes('live'), 'merged entry should preserve live provenance');
        assert(frame.entries[0].messageId === 'msg-1', 'merged entry should keep assistant message id');

        globalThis.__CODEX_THINKING_TEXT_DRAWER_FRAME_V1__ = undefined;
        __codexTTDRecordLiveThinking({{text:'partial', streamKey:'s1', turnKey:'turn'}});
        __codexTTDRecordStructuredThinking({{thinking:'different final', messageId:'m1', blockHash:'h1', turnKey:'turn'}});
        frame = __codexTTDDrawerFrame();
        assert(frame.entries.some(e => e.source === 'live' && e.text === 'partial'), 'mismatched live text should remain');
        assert(frame.entries.some(e => e.source === 'structured' && e.text === 'different final'), 'mismatched structured text should remain');

        globalThis.__CODEX_THINKING_TEXT_DRAWER_FRAME_V1__ = undefined;
        __codexTTDRecordLiveThinking({{text:'', streamKey:'s1'}});
        __codexTTDRecordStructuredThinking({{thinking:'   ', messageId:'m1'}});
        assert(__codexTTDDrawerFrame().entries.length === 0, 'empty thinking strings should not create rows');

        const longText = 'x'.repeat(50000);
        __codexTTDRecordStructuredThinking({{thinking:longText, messageId:'long', blockHash:'long-h', turnKey:'long-turn'}});
        frame = __codexTTDDrawerFrame();
        const longEntry = frame.entries.find(e => e.messageId === 'long');
        assert(longEntry.text.includes('captured text truncated') || longEntry.lines.some(l => l.includes('displayed text truncated')), 'long rendered text should label truncation');
        assert(longEntry.charCount >= 50000 && longEntry.rawCharCount >= 50000, 'long entry should track original char count');
        assert((longEntry.text.length || 0) < longEntry.rawCharCount, 'long stored display text should be bounded');

        globalThis.__CODEX_THINKING_TEXT_DRAWER_FRAME_V1__ = undefined;
        __codexTTDBeginTurn('long-live');
        for (let i = 0; i < 10; i++) __codexTTDRecordLiveThinking({{text:'y'.repeat(10000), streamKey:1}});
        frame = __codexTTDDrawerFrame();
        const liveLong = frame.entries.find(e => e.source === 'live');
        assert(liveLong.rawCharCount === 100000 && liveLong.charCount === 100000, 'long live raw char count should remain accurate');
        assert(liveLong.text.length < liveLong.rawCharCount, 'long live display text should be bounded');

        globalThis.__CODEX_THINKING_TEXT_DRAWER_FRAME_V1__ = undefined;
        for (let i = 0; i < 100; i++) __codexTTDRecordStructuredThinking({{thinking:'entry-' + i, messageId:'m' + i, blockHash:'h' + i}});
        frame = __codexTTDDrawerFrame();
        assert(__codexTTDEnsure().entries.length <= 80, 'stored entries should be capped');
        assert(frame.droppedEntryCount >= 20, 'dropped entry count should be tracked');

        let opened = false, selected = 'thinking';
        const actions = __codexTTDWrapFooterActions({{}}, 'thinking', (v) => {{ opened = v; }}, (v) => {{ selected = v; }});
        actions['footer:openSelected']();
        assert(opened === true, 'openSelected should open');
        assert(__codexTTDDrawerFrame().unread === false, 'opening drawer should clear unread');
        assert(actions['footer:clearSelection']() === false, 'clearSelection should be ignored for Thinking');
        assert(opened === true && selected === 'thinking', 'clearSelection must not close Thinking');
        for (let i = 0; i < 999; i++) actions['footer:down']();
        frame = __codexTTDDrawerFrame();
        assert(frame.scroll <= Math.max(0, frame.lineCount - 18), 'scroll should clamp to available content');
        actions['footer:close']();
        assert(opened === false && selected === null, 'footer close should close Thinking');
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
    test_manifest_operations_match_source_and_payload_hashes()
    test_operations_stay_out_of_request_and_persistence_surfaces()
    test_helper_fixture_review_regressions()
    print("thinking-text drawer package checks passed")
