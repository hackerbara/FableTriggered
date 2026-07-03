import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "hidden-context-drawer"
LIVE_2_1_199 = Path("/Users/MAC/.local/share/claude/versions/2.1.199")


def read_rel(path: str) -> str:
    return (PACKAGE / path).read_text(encoding="utf-8")


def test_hidden_context_drawer_does_not_touch_or_advertise_escape() -> None:
    """Hidden Context close must be owned by footer:x, never by Escape."""
    package_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [PACKAGE / "README.md", PACKAGE / "patch.json", *sorted((PACKAGE / "payloads").glob("*.js"))]
    )
    footer_actions = read_rel("payloads/13-footer-clearselection-consumes-hiddencontext.js")
    overlay = read_rel("payloads/15-uxl-refresh-bottom-overlay.js")

    assert '"footer:close":()=>{if(hC){globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_OPEN_V13__=!1,hCp(!1),Sf(null);return}if(qb&&xs>=1)' in footer_actions
    assert '"footer:clearSelection":()=>{if(hC)return!1;if(Ap' in footer_actions
    clear_selection_body = footer_actions.split('"footer:clearSelection":()=>{', 1)[1].split('},"footer:close"', 1)[0]
    assert 'globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_OPEN_V13__' not in clear_selection_body
    assert 'hCp(!1)' not in clear_selection_body
    assert 'Sf(null)' not in clear_selection_body.split('if(Ap', 1)[0]
    assert "x closes" in overlay
    assert "esc" not in overlay.lower()
    assert "escape" not in package_text.lower()
    assert "inputOwnsEscape" not in package_text
    assert "hCe=Tt" not in package_text


def test_hidden_context_drawer_package_targets_current_2_1_199() -> None:
    """The drawer package should be pinned to the current 2.1.199 module anchors."""
    manifest = json.loads((PACKAGE / "patch.json").read_text(encoding="utf-8"))
    target = manifest["targets"][0]
    identity = target["sourceIdentity"]

    assert identity["claudeVersion"] == "2.1.199"
    assert identity["versionOutput"] == "2.1.199 (Claude Code)"
    assert (
        identity["sha256"]
        == "e3cb61abc8a2ec7b98976cee1ffdde5a3fa755c9990bc8d688cd89290e0dcec0"
    )
    assert identity["sizeBytes"] == 232155536

    module = target["modules"][0]
    assert module["contentSha256"] == "e30c857c2e1130ff0fa9d14349a210c588f8115fc8ac86e120c454547efc0c55"
    assert module["contentLength"] == 18593981

    helper_operation = next(
        op for op in module["operations"] if op["opId"] == "projection-helpers-before-jlr"
    )
    assert helper_operation["exact"] == "function Jur(e){"
    assert read_rel("payloads/01-projection-helpers-before-jlr.js").endswith("function Jur(e){")

    if not LIVE_2_1_199.exists():
        return

    actual_identity_hash = hashlib.sha256(LIVE_2_1_199.read_bytes()).hexdigest()
    if actual_identity_hash != identity["sha256"]:
        return

    # Prefer the checked-in extraction produced by the updater; it keeps this test
    # independent from the Bun graph inspector while still verifying real anchors.
    extracted_module = ROOT / ".development" / "artifacts" / "claude-2.1.199-hidden-context-source-module0.js"
    if not extracted_module.exists():
        return
    source = extracted_module.read_text(encoding="utf-8")

    for operation in module["operations"]:
        exact = operation["exact"]
        assert source.count(exact) == 1, operation["opId"]
        assert operation["oldRangeLength"] == len(exact.encode("utf-8"))
        assert operation["oldRangeSha256"] == hashlib.sha256(exact.encode("utf-8")).hexdigest()

if __name__ == "__main__":
    test_hidden_context_drawer_does_not_touch_or_advertise_escape()
    test_hidden_context_drawer_package_targets_current_2_1_199()
    print("hidden-context drawer package checks passed")
