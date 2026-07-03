from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_menubar_icon_asset_exists():
    icon = ROOT / "assets" / "claude-monkey-menubar-template.png"
    assert icon.exists()
    assert icon.stat().st_size > 0
