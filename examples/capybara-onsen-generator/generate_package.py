"""Emit the current shipped capybara-onsen package byte-for-byte.

The art compiler files in this directory preserve the lower-level scene source,
but the checked-in package is now the authoritative package artifact.  This
script gives regeneration a safe, tested interface: write a clean copy of the
current package to HM_GENERATE_OUT, or default to the live package path as an
idempotent no-op.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE_NAME = "capybara-onsen"
SOURCE_PACKAGE = ROOT / "packages" / PACKAGE_NAME
DEFAULT_OUT = SOURCE_PACKAGE
SKIP_FILE_NAMES = {"preview.png"}


def _copy_package(source: Path, destination: Path) -> None:
    if not source.is_dir():
        raise SystemExit(f"source package does not exist: {source}")

    source_resolved = source.resolve()
    destination_resolved = destination.resolve()
    if destination_resolved == source_resolved:
        # Default invocation points at the live package.  There is nothing to
        # rewrite because the live package is the source of truth; this branch
        # prevents an accidental delete-then-copy-from-self footgun.
        print(f"{PACKAGE_NAME}: live package already current at {destination}")
        return

    if destination.exists():
        if destination.is_dir():
            shutil.rmtree(destination)
        else:
            destination.unlink()
    destination.mkdir(parents=True)

    for path in sorted(source.rglob("*")):
        relative = path.relative_to(source)
        if path.is_dir() or path.name in SKIP_FILE_NAMES:
            continue
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)

    print(f"{PACKAGE_NAME}: wrote {destination}")


def main() -> None:
    destination = Path(os.environ.get("HM_GENERATE_OUT", DEFAULT_OUT))
    _copy_package(SOURCE_PACKAGE, destination)


if __name__ == "__main__":
    main()
