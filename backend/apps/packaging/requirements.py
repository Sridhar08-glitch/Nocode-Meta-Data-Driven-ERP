"""
The ``package`` block of a solution manifest — declarative dependency / compatibility metadata.

A manifest MAY carry a ``package`` object; when absent the package is treated as having no
requirements (so every pre-platform manifest keeps installing unchanged). Shape::

    "package": {
        "slug": "crm", "name": "CRM", "version": "1.0.0", "author": "Sridhar ERP",
        "description": "...",
        "min_core_version": "2.0.0", "max_core_version": "",
        "requires_engines": ["accounting", "numbering"],
        "requires_capabilities": ["workflows", "reports"],
        "requires_packages": [{"slug": "inventory", "version": ">=1.0.0"}],
        "optional_packages": [{"slug": "analytics", "version": "*"}],
        "conflicts_packages": [{"slug": "legacy_crm", "version": "*"}],
        "provides_capabilities": ["crm"],
        "migrations": [ {"version": "1.1.0", "operations": [ ... ]} ]
    }

``extract`` returns a normalised :class:`PackageRequirements`; ``validate`` returns a list of
human-readable errors (empty ⇒ valid). Both are pure — no DB access — so they gate publish too.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import capabilities, semver

SLUG_RE = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass
class PackageRef:
    slug: str
    version: str = "*"


@dataclass
class PackageRequirements:
    slug: str = ""
    name: str = ""
    version: str = "1.0.0"
    author: str = ""
    description: str = ""
    min_core_version: str = ""
    max_core_version: str = ""
    requires_engines: list = field(default_factory=list)
    requires_capabilities: list = field(default_factory=list)
    requires_packages: list = field(default_factory=list)   # list[PackageRef]
    optional_packages: list = field(default_factory=list)    # list[PackageRef]
    conflicts_packages: list = field(default_factory=list)   # list[PackageRef]
    provides_capabilities: list = field(default_factory=list)
    migrations: list = field(default_factory=list)
    present: bool = False    # whether a ``package`` block was supplied at all

    def as_dict(self) -> dict:
        def refs(rs):
            return [{"slug": r.slug, "version": r.version} for r in rs]
        return {
            "slug": self.slug, "name": self.name, "version": self.version,
            "author": self.author, "description": self.description,
            "min_core_version": self.min_core_version,
            "max_core_version": self.max_core_version,
            "requires_engines": list(self.requires_engines),
            "requires_capabilities": list(self.requires_capabilities),
            "requires_packages": refs(self.requires_packages),
            "optional_packages": refs(self.optional_packages),
            "conflicts_packages": refs(self.conflicts_packages),
            "provides_capabilities": list(self.provides_capabilities),
            "migrations": list(self.migrations),
        }


def _refs(raw) -> list:
    out = []
    for item in raw or []:
        if isinstance(item, str):
            out.append(PackageRef(slug=item, version="*"))
        elif isinstance(item, dict) and item.get("slug"):
            out.append(PackageRef(slug=item["slug"], version=item.get("version", "*")))
    return out


def extract(manifest) -> PackageRequirements:
    block = (manifest or {}).get("package") if isinstance(manifest, dict) else None
    if not isinstance(block, dict):
        return PackageRequirements(present=False)
    return PackageRequirements(
        slug=block.get("slug", ""),
        name=block.get("name", ""),
        version=block.get("version", "1.0.0"),
        author=block.get("author", ""),
        description=block.get("description", ""),
        min_core_version=block.get("min_core_version", ""),
        max_core_version=block.get("max_core_version", ""),
        requires_engines=list(block.get("requires_engines", []) or []),
        requires_capabilities=list(block.get("requires_capabilities", []) or []),
        requires_packages=_refs(block.get("requires_packages")),
        optional_packages=_refs(block.get("optional_packages")),
        conflicts_packages=_refs(block.get("conflicts_packages")),
        provides_capabilities=list(block.get("provides_capabilities", []) or []),
        migrations=list(block.get("migrations", []) or []),
        present=True,
    )


def validate(manifest) -> list[str]:
    """Validate the ``package`` block in isolation (structure + known engines/capabilities +
    parseable version constraints). Empty list ⇒ valid. Absent block ⇒ valid (no requirements)."""
    errors: list[str] = []
    if not isinstance(manifest, dict):
        return ["manifest must be a JSON object"]
    block = manifest.get("package")
    if block is None:
        return errors
    if not isinstance(block, dict):
        return ["package must be an object"]

    req = extract(manifest)

    if req.slug and not SLUG_RE.match(req.slug):
        errors.append(f"package.slug {req.slug!r} is not a valid slug")
    if not semver.is_valid(req.version):
        errors.append(f"package.version {req.version!r} is not a valid semantic version")
    for label, val in (("min_core_version", req.min_core_version),
                       ("max_core_version", req.max_core_version)):
        if val and not semver.is_valid(val):
            errors.append(f"package.{label} {val!r} is not a valid semantic version")

    for eng in capabilities.unknown_engines(req.requires_engines):
        errors.append(f"package.requires_engines references unknown engine {eng!r}")
    for cap in capabilities.unknown_capabilities(req.requires_capabilities):
        errors.append(f"package.requires_capabilities references unknown capability {cap!r}")

    for label, refs in (("requires_packages", req.requires_packages),
                        ("optional_packages", req.optional_packages),
                        ("conflicts_packages", req.conflicts_packages)):
        for ref in refs:
            if not SLUG_RE.match(ref.slug or ""):
                errors.append(f"package.{label} has invalid slug {ref.slug!r}")
            try:
                semver.satisfies("1.0.0", ref.version)
            except semver.InvalidVersionError:
                errors.append(
                    f"package.{label} entry {ref.slug!r} has invalid version "
                    f"constraint {ref.version!r}")

    # self-conflict guard
    req_slugs = {r.slug for r in req.requires_packages}
    conflict_slugs = {r.slug for r in req.conflicts_packages}
    overlap = req_slugs & conflict_slugs
    if overlap:
        errors.append(f"package declares the same slug(s) as both required and "
                      f"conflicting: {', '.join(sorted(overlap))}")
    if req.slug and req.slug in conflict_slugs:
        errors.append("package cannot conflict with itself")

    # migrations structure (versions parseable, ascending not required but must be valid semver)
    from .package_migrations import validate_migrations
    errors.extend(validate_migrations(req.migrations))
    return errors
