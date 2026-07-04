import subprocess
import sys
from pathlib import Path

from PIL import Image

ASSETS = Path(__file__).resolve().parents[1] / "assets"


def test_generator_writes_expected_files(tmp_path):
    subprocess.run([sys.executable, "scripts/generate_icons.py"], check=True)
    for name, size in [("monkey-tray-18.png", 18), ("monkey-tray-36.png", 36),
                       ("monkey-color-512.png", 512)]:
        img = Image.open(ASSETS / name)
        assert img.size == (size, size) and img.mode == "RGBA"


def test_tray_icon_is_monochrome_with_alpha():
    img = Image.open(ASSETS / "monkey-tray-18.png").convert("RGBA")
    colors = {px[:3] for px in img.getdata() if px[3] > 0}
    assert colors == {(0, 0, 0)}  # template: pure black + alpha only
