"""
Package SDK — one standard on-disk structure every industry package follows, and the loader
that assembles it into a manifest the existing installer understands. The SDK is *real code*,
not just a convention: :func:`load_package` builds the manifest, :func:`scaffold` writes a
valid starter package, and both round-trip through :mod:`apps.packaging.preflight`.

Standard layout::

    my_package/
      package.yaml          # the manifest "package" block (metadata + requirements)  [or .json]
      manifest.json         # OPTIONAL full/override manifest (merged last)
      entities/*.json       # one entity per file (object) or many (list)
      forms/*.json
      views/*.json
      reports/*.json
      dashboards/*.json
      roles/*.json          # roles carry their own permissions/field_permissions/masking
      permissions/*.json    # OPTIONAL advisory permission catalogue
      navigation/*.json     # → manifest "navigations"
      notifications/*.json  # → manifest "notification_templates"
      workflows/*.json
      rules/*.json
      home_layouts/*.json
      applications/*.json
      seed/*.json           # OPTIONAL seed records (passthrough; not auto-applied)
      migrations/*.json      # each file is one {version, operations:[...]} migration
      tests/                # package author's tests
      README.md

Section directories map to manifest keys via ``DIR_TO_SECTION``. A section file may contain a
single object or a list; both are flattened into the section list.
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

DIR_TO_SECTION = {
    "entities": "entities",
    "forms": "forms",
    "views": "views",
    "reports": "reports",
    "dashboards": "dashboards",
    "roles": "roles",
    "permissions": "permissions",
    "navigation": "navigations",
    "notifications": "notification_templates",
    "workflows": "workflows",
    "rules": "rules",
    "home_layouts": "home_layouts",
    "applications": "applications",
    "seed": "seed",
}

STANDARD_DIRS = list(DIR_TO_SECTION) + ["migrations", "tests"]


class SDKError(Exception):  # noqa: N818 — domain error
    pass


def _read_json(path: Path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError) as exc:
        raise SDKError(f"could not read {path.name}: {exc}") from exc


def _read_package_meta(root: Path) -> dict:
    for name in ("package.yaml", "package.yml", "package.json"):
        p = root / name
        if p.exists():
            try:
                with open(p, encoding="utf-8") as fh:
                    data = yaml.safe_load(fh) if p.suffix != ".json" else json.load(fh)
            except (OSError, ValueError, yaml.YAMLError) as exc:
                raise SDKError(f"could not read {name}: {exc}") from exc
            if not isinstance(data, dict):
                raise SDKError(f"{name} must define an object")
            return data
    return {}


def _collect_section(root: Path, dirname: str) -> list:
    d = root / dirname
    if not d.is_dir():
        return []
    items: list = []
    for f in sorted(d.glob("*.json")):
        data = _read_json(f)
        if isinstance(data, list):
            items.extend(data)
        elif isinstance(data, dict):
            items.append(data)
        else:
            raise SDKError(f"{dirname}/{f.name} must be an object or a list")
    return items


def load_package(path) -> dict:
    """Assemble a manifest dict from an SDK package directory."""
    root = Path(path)
    if not root.is_dir():
        raise SDKError(f"package directory not found: {path}")

    manifest: dict = {"schema_version": 1}

    meta = _read_package_meta(root)
    migrations = _collect_section_migrations(root)
    if meta or migrations:
        pkg = dict(meta)
        if migrations:
            pkg.setdefault("migrations", migrations)
        manifest["package"] = pkg

    for dirname, section in DIR_TO_SECTION.items():
        items = _collect_section(root, dirname)
        if items:
            manifest[section] = items

    override = root / "manifest.json"
    if override.exists():
        data = _read_json(override)
        if isinstance(data, dict):
            for k, v in data.items():
                manifest[k] = v

    return manifest


def _collect_section_migrations(root: Path) -> list:
    d = root / "migrations"
    if not d.is_dir():
        return []
    out = []
    for f in sorted(d.glob("*.json")):
        data = _read_json(f)
        if isinstance(data, list):
            out.extend(data)
        elif isinstance(data, dict):
            out.append(data)
    return out


def validate_layout(path) -> list[str]:
    """Structural problems with an SDK package dir (does NOT validate the assembled manifest;
    use preflight for that). Empty list ⇒ layout looks well-formed."""
    root = Path(path)
    errors: list[str] = []
    if not root.is_dir():
        return [f"package directory not found: {path}"]
    if not _read_package_meta(root):
        errors.append("missing package.yaml / package.json")
    has_any = any((root / d).is_dir() and any((root / d).glob("*.json"))
                  for d in DIR_TO_SECTION)
    if not has_any and not (root / "manifest.json").exists():
        errors.append("package has no entities/manifest content")
    return errors


# ── scaffolding ───────────────────────────────────────────────────────────────
def scaffold(path, *, slug: str, name: str = "", author: str = "",
             version: str = "1.0.0") -> dict:
    """Write a minimal, valid starter package at ``path``. Returns the assembled manifest."""
    root = Path(path)
    root.mkdir(parents=True, exist_ok=True)
    name = name or slug.replace("_", " ").title()

    for d in STANDARD_DIRS:
        (root / d).mkdir(exist_ok=True)

    package_meta = {
        "slug": slug, "name": name, "version": version, "author": author or "Unknown",
        "description": f"{name} solution package.",
        "min_core_version": "2.0.0", "max_core_version": "",
        "requires_engines": [], "requires_capabilities": ["metadata", "workflows"],
        "requires_packages": [], "optional_packages": [], "conflicts_packages": [],
        "provides_capabilities": [slug],
    }
    with open(root / "package.yaml", "w", encoding="utf-8") as fh:
        yaml.safe_dump(package_meta, fh, sort_keys=False)

    example_entity = {
        "slug": f"{slug}_item", "name": f"{name} Item", "plural_name": f"{name} Items",
        "fields": [
            {"slug": "name", "name": "Name", "field_type": "text",
             "is_promoted": True, "is_required": True},
            {"slug": "status", "name": "Status", "field_type": "status",
             "is_promoted": True, "config": {"choices": ["open", "closed"]}},
        ],
    }
    with open(root / "entities" / "item.json", "w", encoding="utf-8") as fh:
        json.dump(example_entity, fh, indent=2)

    example_role = {"slug": "administrator", "name": "Administrator",
                    "permissions": [{"resource_type": "entity",
                                     "entity_slug": f"{slug}_item", "action": "manage"}]}
    with open(root / "roles" / "administrator.json", "w", encoding="utf-8") as fh:
        json.dump(example_role, fh, indent=2)

    with open(root / "README.md", "w", encoding="utf-8") as fh:
        fh.write(f"# {name}\n\nSridhar ERP industry solution package.\n\n"
                 f"- Slug: `{slug}`\n- Version: `{version}`\n\n"
                 "Build the manifest with `apps.packaging.sdk.load_package(<dir>)` and install "
                 "it through the Solution Template framework. Run `preflight` before installing.\n")

    return load_package(root)
