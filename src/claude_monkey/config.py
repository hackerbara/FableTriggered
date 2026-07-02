from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class Profile:
    enabledPatches: list[str]
    promptProfile: str | None = None


@dataclass
class ClaudeMonkeyConfig:
    activeProfile: str
    profiles: dict[str, Profile]
    installMode: str = "shim"
    activePatchSet: str | None = None


def default_config() -> ClaudeMonkeyConfig:
    return ClaudeMonkeyConfig(activeProfile="default", profiles={"default": Profile(enabledPatches=[])})


def load_config(path: Path) -> ClaudeMonkeyConfig:
    if not path.exists():
        return default_config()
    raw = json.loads(path.read_text())
    return ClaudeMonkeyConfig(
        activeProfile=raw["activeProfile"],
        profiles={name: Profile(**value) for name, value in raw["profiles"].items()},
        installMode=raw.get("installMode", "shim"),
        activePatchSet=raw.get("activePatchSet"),
    )


def save_config(path: Path, config: ClaudeMonkeyConfig) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(config), indent=2, sort_keys=True) + "\n")
