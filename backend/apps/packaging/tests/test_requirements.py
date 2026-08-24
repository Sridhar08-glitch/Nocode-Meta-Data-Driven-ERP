"""Parsing + validating the manifest ``package`` block."""
from apps.packaging import requirements as rq


def _pkg(**over):
    base = {"slug": "demo", "name": "Demo", "version": "1.0.0", "author": "Me"}
    base.update(over)
    return {"schema_version": 1, "package": base}


def test_absent_block_means_no_requirements():
    req = rq.extract({"schema_version": 1})
    assert req.present is False
    assert rq.validate({"schema_version": 1}) == []


def test_extract_normalises_refs():
    req = rq.extract(_pkg(
        requires_packages=[{"slug": "inventory", "version": ">=1.0.0"}, "crm"],
        conflicts_packages=[{"slug": "legacy"}]))
    assert req.present
    assert req.requires_packages[0].slug == "inventory"
    assert req.requires_packages[0].version == ">=1.0.0"
    assert req.requires_packages[1].slug == "crm"          # bare string → version "*"
    assert req.requires_packages[1].version == "*"
    assert req.conflicts_packages[0].slug == "legacy"


def test_valid_package_passes():
    assert rq.validate(_pkg(
        min_core_version="2.0.0", requires_engines=["accounting"],
        requires_capabilities=["workflows"],
        requires_packages=[{"slug": "inventory", "version": ">=1.0.0"}])) == []


def test_invalid_slug_version_and_unknown_refs():
    errs = rq.validate(_pkg(slug="Bad Slug", version="not-a-version",
                            requires_engines=["ghost_engine"],
                            requires_capabilities=["telepathy"]))
    joined = " ".join(errs)
    assert "slug" in joined
    assert "version" in joined
    assert "ghost_engine" in joined
    assert "telepathy" in joined


def test_invalid_core_version_and_bad_constraint():
    errs = rq.validate(_pkg(min_core_version="abc",
                            requires_packages=[{"slug": "x", "version": ">>1"}]))
    joined = " ".join(errs)
    assert "min_core_version" in joined
    assert "constraint" in joined


def test_self_conflict_rejected():
    errs = rq.validate(_pkg(slug="demo", conflicts_packages=[{"slug": "demo"}]))
    assert any("itself" in e for e in errs)


def test_required_and_conflicting_same_slug_rejected():
    errs = rq.validate(_pkg(requires_packages=[{"slug": "shared"}],
                            conflicts_packages=[{"slug": "shared"}]))
    assert any("required and" in e for e in errs)


def test_as_dict_round_trips():
    d = rq.extract(_pkg(requires_packages=[{"slug": "a", "version": "*"}])).as_dict()
    assert d["requires_packages"] == [{"slug": "a", "version": "*"}]
