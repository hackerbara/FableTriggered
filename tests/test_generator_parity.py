from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CASES = [
    ("capybara-onsen", "capybara-onsen-generator"),
    ("hotrod-dragons", "hotrod-dragons-generator"),
]
SKIP_FILE_NAMES = {"preview.png"}


def _files_under(root: Path) -> dict[Path, bytes]:
    return {
        path.relative_to(root): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file() and path.name not in SKIP_FILE_NAMES
    }


@pytest.mark.parametrize(("pkg", "gen"), CASES)
def test_generator_regenerates_live_package(pkg: str, gen: str, tmp_path: Path) -> None:
    """Generator output must byte-match packages/<pkg> (user decision 2026-07-04)."""
    out = tmp_path / pkg
    env = {**os.environ, "HM_GENERATE_OUT": str(out)}
    subprocess.run(
        [sys.executable, str(ROOT / "examples" / gen / "generate_package.py")],
        check=True,
        env=env,
    )

    live = ROOT / "packages" / pkg
    assert _files_under(out) == _files_under(live)
