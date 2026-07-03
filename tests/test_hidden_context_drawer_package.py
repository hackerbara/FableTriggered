from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "packages" / "hidden-context-drawer"


def read_rel(path: str) -> str:
    return (PACKAGE / path).read_text(encoding="utf-8")


def test_hidden_context_drawer_does_not_touch_or_advertise_escape() -> None:
    """Hidden Context must not add a ctrl-escape close path."""
    package_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in [
            PACKAGE / "README.md",
            PACKAGE / "patch.json",
            *sorted((PACKAGE / "payloads").glob("*.js")),
        ]
    )
    footer_actions = read_rel("payloads/13-footer-clearselection-consumes-hiddencontext.js")
    overlay = read_rel("payloads/15-uxl-refresh-bottom-overlay.js")

    assert (
        '"footer:close":()=>{if(hC){globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_OPEN_V13__='
        "!1,hCp(!1),Pc(null);return}if(cm&&Os>=1)"
    ) in footer_actions
    assert '"footer:clearSelection":()=>{if(hC)return!1;if(qS' in footer_actions
    clear_selection_body = footer_actions.split('"footer:clearSelection":()=>{', 1)[1].split(
        '},"footer:close"', 1
    )[0]
    assert "globalThis.__CODEX_HIDDEN_CONTEXT_DRAWER_OPEN_V13__" not in clear_selection_body
    assert "hCp(!1)" not in clear_selection_body
    assert "Pc(null)" not in clear_selection_body.split("if(qS", 1)[0]
    assert "x closes" in overlay
    assert "esc" not in overlay.lower()
    assert "ctrl+esc" not in package_text.lower()
    assert 'Bt.ctrl&&Bt.name==="escape"' not in package_text
    assert "inputOwnsEscape" not in package_text
    assert "hCe=Tt" not in package_text


if __name__ == "__main__":
    test_hidden_context_drawer_does_not_touch_or_advertise_escape()
    print("hidden-context drawer package escape regression check passed")
