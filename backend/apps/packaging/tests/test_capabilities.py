"""Core capability + engine registry resolves against the LIVE source tree, and stays in
sync with the certified single-engine set."""
from apps.packaging import capabilities as cap


def test_all_engines_resolve_to_real_code():
    """Every declared engine must import — proving the registry never drifts from source."""
    unavailable = [n for n in cap.ENGINES if not cap.engine_available(n)]
    assert unavailable == [], f"engines pointing at missing code: {unavailable}"


def test_all_capabilities_resolve_to_real_code():
    unavailable = [n for n in cap.CAPABILITIES if not cap.capability_available(n)]
    assert unavailable == [], f"capabilities pointing at missing code: {unavailable}"


def test_unknown_engine_and_capability_are_not_available():
    assert not cap.engine_available("warp_drive")
    assert not cap.capability_available("warp_drive")
    assert cap.unknown_engines(["accounting", "ghost"]) == ["ghost"]
    assert cap.unknown_capabilities(["workflows", "ghost"]) == ["ghost"]


def test_engines_match_certification_single_engine_proof():
    """packaging.ENGINES must cover the certified canonical engine set so the package platform
    can never advertise an engine the certification gate doesn't recognise."""
    from apps.certification.report import _ENGINE_LOCATIONS
    cert_locations = set(_ENGINE_LOCATIONS.values())
    packaging_locations = set(cap.ENGINES.values())
    missing = cert_locations - packaging_locations
    assert missing == set(), f"certified engines absent from packaging registry: {missing}"


def test_missing_helpers():
    assert cap.missing_engines(["accounting", "ghost"]) == ["ghost"]
    assert cap.missing_capabilities(["workflows", "ghost"]) == ["ghost"]
    assert cap.missing_engines(["accounting", "numbering"]) == []
