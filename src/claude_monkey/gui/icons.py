from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon

ASSETS_DIR = Path(__file__).resolve().parents[3] / "assets"


def tray_icon() -> QIcon:
    icon = QIcon()
    for size in (18, 36):
        icon.addFile(str(ASSETS_DIR / f"monkey-tray-{size}.png"))
    icon.setIsMask(True)  # macOS template behavior; harmless on Windows
    return icon


def app_icon() -> QIcon:
    icon = QIcon()
    for size in (128, 256, 512):
        icon.addFile(str(ASSETS_DIR / f"monkey-color-{size}.png"))
    return icon
