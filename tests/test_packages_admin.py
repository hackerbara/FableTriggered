import json
import tempfile

from claude_monkey.packages_admin import add_package, scaffold_prompt_package


def _write_pkg(tmp_path, folder, manifest):
    pkg = tmp_path / folder
    pkg.mkdir(parents=True)
    (pkg / "manifest.json").write_text(json.dumps(manifest))
    return pkg


PATCH_MANIFEST = {
    "schemaVersion": 1, "kind": "patch", "id": "demo-patch",
    "label": "Demo", "description": "d", "patch": {"engine": "bun_graph_repack", "targets": []},
}


def test_add_copies_to_manifest_id_dir(tmp_path):
    src = _write_pkg(tmp_path, "src-folder-name", PATCH_MANIFEST)
    home = tmp_path / "home"
    result = add_package(src, "patch", home)
    assert result["ok"] is True
    assert (home / "patches" / "demo-patch" / "manifest.json").exists()
    assert any("basename" in w for w in result["warnings"])  # renamed from src-folder-name


def test_add_rejects_id_collision(tmp_path):
    home = tmp_path / "home"
    src = _write_pkg(tmp_path, "demo-patch", PATCH_MANIFEST)
    assert add_package(src, "patch", home)["ok"] is True
    again = add_package(src, "patch", home)
    assert again["ok"] is False and again["error"]["code"] == "package_exists"


def test_add_rejects_kind_mismatch(tmp_path):
    src = _write_pkg(tmp_path, "demo-patch", PATCH_MANIFEST)
    result = add_package(src, "option", tmp_path / "home")
    assert result["ok"] is False and result["error"]["code"] == "kind_mismatch"


def test_add_rejects_invalid_manifest(tmp_path):
    pkg = tmp_path / "bad"
    pkg.mkdir()
    (pkg / "manifest.json").write_text("{not json")
    result = add_package(pkg, "patch", tmp_path / "home")
    assert result["ok"] is False and result["error"]["code"] == "invalid_package"


def test_scaffold_prompt_package(tmp_path):
    md = tmp_path / "my notes.md"
    md.write_text("be helpful")
    manifest = scaffold_prompt_package(md, "my-notes", None)
    assert manifest["kind"] == "prompt" and manifest["id"] == "my-notes"
    assert manifest["prompt"] == {"mode": "append", "source": {"path": "prompt.md"}}


# --- Attack reproductions (Task 5 review round) -----------------------------


def test_add_rejects_relative_path_traversal_id_with_no_stray_writes(monkeypatch, tmp_path):
    """Manifest id '../evil-traversal-dir' must never be used to build a staging path.

    Regression for Critical-1: pre-fix, `_load_manifest` peeked the RAW (unvalidated)
    id and built `Path(tmp) / peeked_id` before validating it, so this id escaped the
    tempdir via `..` and `shutil.copytree` planted a directory one level up — leaked
    forever since it sits outside the `with tempfile.TemporaryDirectory()` scope.
    """
    # Force the module's staging tempdir to live under tmp_path so the traversal
    # target (one directory above the tempdir) is a precise, assertable location.
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))

    manifest = dict(PATCH_MANIFEST, id="../evil-traversal-dir")
    src = _write_pkg(tmp_path, "src-folder-name", manifest)
    home = tmp_path / "home"

    result = add_package(src, "patch", home)

    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_package"
    # The traversal target (tmp_path/evil-traversal-dir, one level above whatever
    # tempdir got created under tmp_path) must never have been created.
    assert not (tmp_path / "evil-traversal-dir").exists()


def test_add_rejects_absolute_path_id_with_no_stray_writes(tmp_path):
    """Manifest id set to an absolute path must not be planted at that path.

    Regression for Critical-1: `Path(tmp) / "/abs/path"` discards `tmp` entirely
    (pathlib join semantics), so pre-fix the package tree was staged directly at
    the attacker-chosen absolute path.
    """
    traversal_target = tmp_path / "abs-traversal-target"
    manifest = dict(PATCH_MANIFEST, id=str(traversal_target))
    src = _write_pkg(tmp_path, "src-folder-name", manifest)
    home = tmp_path / "home"

    result = add_package(src, "patch", home)

    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_package"
    assert not traversal_target.exists()


def test_add_rejects_package_containing_symlink(tmp_path):
    """A package tree containing a symlink must be rejected, not silently ingested.

    Regression for Important-4: `shutil.copytree` dereferences symlinks by default,
    so a symlink to e.g. a secrets file would have its *content* copied into both
    the staging tempdir and the final installed package.
    """
    secret = tmp_path / "secret.txt"
    secret.write_text("top-secret-content")

    src = _write_pkg(tmp_path, "demo-patch", PATCH_MANIFEST)
    (src / "linked.txt").symlink_to(secret)
    home = tmp_path / "home"

    result = add_package(src, "patch", home)

    assert result["ok"] is False
    assert result["error"]["code"] == "invalid_package"
    installed = home / "patches" / "demo-patch"
    assert not installed.exists()
    # Belt-and-suspenders: the secret content must not have leaked anywhere under home.
    if home.exists():
        for path in home.rglob("*"):
            if path.is_file():
                assert "top-secret-content" not in path.read_text(errors="ignore")


def test_add_renames_with_warning_when_multiple_json_files_present(tmp_path):
    """`_peek_kind_and_id` should align with `load_package_manifest`'s multi-file scan.

    `load_package_manifest` globs all `*.json` files and accepts a folder with more
    than one, provided exactly one parses+validates. The rename-with-warning path
    (source folder name != manifest id) should still work in that case rather than
    bailing out to a folder-slug mismatch.
    """
    src = tmp_path / "src-folder-name"
    src.mkdir()
    (src / "manifest.json").write_text(json.dumps(PATCH_MANIFEST))
    (src / "notes.json").write_text(json.dumps({"unrelated": True}))
    home = tmp_path / "home"

    result = add_package(src, "patch", home)

    assert result["ok"] is True
    assert (home / "patches" / "demo-patch" / "manifest.json").exists()
    assert any("basename" in w for w in result["warnings"])
