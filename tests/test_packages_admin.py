import json

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
