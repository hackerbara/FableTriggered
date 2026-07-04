"""Package-install admin surface for the `add-patch` / `add-option` / `add-prompt` CLI verbs.

This module never activates/enables anything it installs: `add_package` only copies a
validated package into the per-kind bucket under the ClaudeMonkey state dir
(`~/.claude-monkey/{patches,prompts,options}/<manifest.id>/`). It never touches
`config.json` or `active_profile`.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from claude_monkey.package_model import PackageKind, PackageManifest, load_package_manifest

_BUCKETS = {"patch": "patches", "prompt": "prompts", "option": "options"}


def _envelope(ok: bool, summary: str, *, code: str | None = None, warnings=None) -> dict:
    return {
        "schemaVersion": 1, "ok": ok, "status": "ok" if ok else "error",
        "summary": summary,
        "error": None if ok else {"message": summary, "code": code},
        "warnings": list(warnings or []),
    }


class _KindMismatch(Exception):
    """Raised by `_load_manifest` when the manifest's own kind differs from the target.

    Carries the manifest's actual (validated) kind so `add_package` can report the
    binding `kind_mismatch` error code instead of the generic `invalid_package` one.
    """

    def __init__(self, actual_kind: PackageKind) -> None:
        super().__init__(f"kind {actual_kind.value!r} does not match target")
        self.actual_kind = actual_kind


def _peek_kind_and_id(package_dir: Path) -> tuple[str | None, str | None]:
    """Best-effort, non-validating peek at the sole `*.json` manifest's raw fields.

    This does NOT reimplement any of the schema/slug/local-path enforcement that
    `package_model.load_package_manifest` performs (see `_load_manifest` below) — it
    only reads `kind` and `id` so `_load_manifest` can (a) pick the correct
    `expected_kind` to hand to the real validator and (b) decide whether the source
    folder needs to be staged under an id-named directory before validating (see
    below). Any failure (missing file, bad JSON, multiple manifests, non-dict
    payload) yields `(None, None)` and lets the real validator surface the error.
    """
    json_paths = sorted(path for path in package_dir.glob("*.json") if path.is_file())
    if len(json_paths) != 1:
        return None, None
    try:
        with json_paths[0].open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None, None
    if not isinstance(data, dict):
        return None, None
    raw_kind = data.get("kind")
    raw_id = data.get("id")
    kind = raw_kind if isinstance(raw_kind, str) else None
    package_id = raw_id if isinstance(raw_id, str) else None
    return kind, package_id


def _load_manifest(package_dir: Path, kind: str) -> PackageManifest:
    """Validate `package_dir` by delegating to the phase-1 loader.

    Real validation (schema, id slug, kind enum, exactly-one-manifest, in-package
    local paths, sha256 shapes, id/folder-slug match, prompt/option/patch field
    shape, etc.) is entirely performed by
    `claude_monkey.package_model.load_package_manifest` (package_model.py:429), which
    itself requires an `expected_kind: PackageKind` and raises
    `PackageValidationError` (a `ValueError` subclass, package_model.py:45-46) on any
    failure. This function does not reimplement any of that.

    Two small wrinkles handled here, both using the non-validating peek above purely
    to route into that real validator correctly:

    1. `load_package_manifest`'s own kind-mismatch failure mode is the generic
       `_fail("kind_must_match_bucket")` (package_model.py:395-396), which would be
       indistinguishable from any other `invalid_package` failure. The binding
       contract for `add_package` requires a distinct `kind_mismatch` error code.
       So we peek the manifest's own `kind` field to pick the *manifest's own* kind
       as `expected_kind` for the real validator (so a well-formed manifest of a
       different kind still validates successfully), then compare the validated
       result's kind against the caller's target `kind` afterward and raise
       `_KindMismatch` if they differ. If the peek can't determine a kind, we fall
       back to the caller's target kind and let `PackageValidationError` surface
       naturally as `invalid_package`.
    2. `load_package_manifest_from_dict` requires the manifest's `id` to equal the
       package directory's basename (`id_must_match_folder`,
       package_model.py:390-393) — a check aimed at already-installed packages
       (`~/.claude-monkey/<bucket>/<id>/`), not arbitrary source directories being
       installed. `add_package` is specified to accept a source directory named
       differently from the manifest id (renaming it into place with a warning), so
       when the peeked `id` differs from `package_dir.name`, we stage a throwaway
       copy of the source under a temp directory named after the peeked id purely
       so the real validator's folder-slug check passes; the original `source`
       passed to `add_package` is untouched and is what actually gets copied to the
       final destination.
    """
    target_kind = PackageKind(kind)
    peeked_kind_raw, peeked_id = _peek_kind_and_id(package_dir)

    try:
        expected_kind = PackageKind(peeked_kind_raw) if peeked_kind_raw else target_kind
    except ValueError:
        expected_kind = target_kind

    if peeked_id and peeked_id != package_dir.name:
        with tempfile.TemporaryDirectory() as tmp:
            staged = Path(tmp) / peeked_id
            shutil.copytree(package_dir, staged)
            manifest = load_package_manifest(staged, expected_kind)
    else:
        manifest = load_package_manifest(package_dir, expected_kind)

    if manifest.kind != target_kind:
        raise _KindMismatch(manifest.kind)
    return manifest


def add_package(source: Path, kind: str, home: Path) -> dict:
    source = Path(source)
    home = Path(home)
    try:
        manifest = _load_manifest(source, kind)
    except _KindMismatch as exc:
        return _envelope(
            False,
            f"manifest kind {exc.actual_kind.value!r} does not match {kind!r}",
            code="kind_mismatch",
        )
    except Exception as exc:
        return _envelope(False, f"invalid package: {exc}", code="invalid_package")

    package_id = manifest.id
    dest = home / _BUCKETS[kind] / package_id
    if dest.exists():
        return _envelope(False, f"package already installed: {package_id}", code="package_exists")

    warnings = []
    if source.name != package_id:
        warnings.append(f"source basename {source.name!r} renamed to manifest id {package_id!r}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, dest)
    return _envelope(True, f"installed {kind} package {package_id}", warnings=warnings)


def scaffold_prompt_package(source_file: Path, package_id: str, name: str | None) -> dict:
    return {
        "schemaVersion": 1, "kind": "prompt", "id": package_id,
        "label": name or package_id, "description": f"Imported from {source_file.name}",
        "prompt": {"mode": "append", "source": {"path": "prompt.md"}},
    }
