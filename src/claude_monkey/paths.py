from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StatePaths:
    state_dir: Path
    patches_dir: Path

    @property
    def config_path(self) -> Path:
        return self.state_dir / "config.json"

    @property
    def current_path(self) -> Path:
        return self.state_dir / "current"

    @property
    def bin_dir(self) -> Path:
        return self.state_dir / "bin"


def default_paths() -> StatePaths:
    home = Path(os.environ.get("HOME", str(Path.home())))
    return StatePaths(state_dir=home / ".claude-monkey", patches_dir=home / ".claude-patches")
