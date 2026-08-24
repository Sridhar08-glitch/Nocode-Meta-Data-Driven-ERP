"""The Package SDK: scaffold a package dir, load it to a manifest, and prove it preflights."""
import json
import uuid

import pytest

from apps.packaging import preflight, sdk


def test_scaffold_creates_standard_layout(tmp_path):
    root = tmp_path / "my_pkg"
    manifest = sdk.scaffold(root, slug="my_pkg", name="My Pkg", author="Acme")
    # standard dirs exist
    for d in ("entities", "roles", "workflows", "migrations", "tests"):
        assert (root / d).is_dir()
    assert (root / "package.yaml").exists()
    assert (root / "README.md").exists()
    # assembled manifest
    assert manifest["package"]["slug"] == "my_pkg"
    assert manifest["package"]["author"] == "Acme"
    assert manifest["entities"][0]["slug"] == "my_pkg_item"
    assert sdk.validate_layout(root) == []


def test_load_round_trips_scaffold(tmp_path):
    root = tmp_path / "p"
    built = sdk.scaffold(root, slug="p", name="P")
    assert sdk.load_package(root) == built


@pytest.mark.django_db
def test_scaffolded_package_preflights_clean(tmp_path):
    root = tmp_path / "p"
    manifest = sdk.scaffold(root, slug="p", name="P")
    res = preflight.preflight(manifest, workspace_id=uuid.uuid4())
    assert res.ok, res.errors


def test_section_files_accept_object_or_list(tmp_path):
    root = tmp_path / "p"
    sdk.scaffold(root, slug="p")
    # add a second entities file containing a LIST
    (root / "entities" / "more.json").write_text(json.dumps([
        {"slug": "p_extra", "name": "Extra", "fields": []}]), encoding="utf-8")
    manifest = sdk.load_package(root)
    slugs = {e["slug"] for e in manifest["entities"]}
    assert {"p_item", "p_extra"} <= slugs


def test_migrations_dir_folds_into_package(tmp_path):
    root = tmp_path / "p"
    sdk.scaffold(root, slug="p")
    (root / "migrations" / "0001.json").write_text(json.dumps(
        {"version": "1.1.0", "operations": [{"op": "note", "text": "hi"}]}), encoding="utf-8")
    manifest = sdk.load_package(root)
    assert manifest["package"]["migrations"][0]["version"] == "1.1.0"


def test_validate_layout_flags_missing_package(tmp_path):
    root = tmp_path / "empty"
    root.mkdir()
    errs = sdk.validate_layout(root)
    assert any("package.yaml" in e for e in errs)


def test_manifest_override_merges_last(tmp_path):
    root = tmp_path / "p"
    sdk.scaffold(root, slug="p")
    (root / "manifest.json").write_text(json.dumps({"custom_key": 42}), encoding="utf-8")
    manifest = sdk.load_package(root)
    assert manifest["custom_key"] == 42
