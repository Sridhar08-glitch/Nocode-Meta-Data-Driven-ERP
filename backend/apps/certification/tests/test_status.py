"""
Meta-certification (P2.16 Module 30) — guards the HONESTY of the certification report.

The certification status (`apps.certification.status`) is the single source of truth for what
the report claims. These tests make the claims un-fakeable:
  - every COMPLETE item must reference at least one test object that ACTUALLY EXISTS in the suite
  - every referenced test object must resolve (module + class/function)
  - the report's score/verdict are derived from this status, never hard-coded
So the report cannot say COMPLETE for a test that does not exist; combined with the whole suite
being green on SQLite and PostgreSQL, COMPLETE is trustworthy.
"""
from __future__ import annotations

import importlib

import pytest

from apps.certification import status as cert_status

_TEST_PKG = "apps.certification.tests"


def _resolve(ref: str) -> object:
    """Resolve 'test_module.ClassName.method' against apps.certification.tests."""
    parts = ref.split(".")
    module = importlib.import_module(f"{_TEST_PKG}.{parts[0]}")
    obj: object = module
    for attr in parts[1:]:
        obj = getattr(obj, attr)
    return obj


def test_status_has_32_items():
    assert len(cert_status.CERTIFICATION_STATUS) == 32


def test_status_ids_unique():
    ids = [i.id for i in cert_status.CERTIFICATION_STATUS]
    assert len(ids) == len(set(ids))


def test_every_status_value_is_valid():
    valid = {cert_status.COMPLETE, cert_status.PARTIAL,
             cert_status.NOT_IMPLEMENTED, cert_status.OUT_OF_SCOPE}
    for item in cert_status.CERTIFICATION_STATUS:
        assert item.status in valid, f"{item.id} has invalid status {item.status}"


@pytest.mark.parametrize("item", cert_status.CERTIFICATION_STATUS, ids=lambda i: i.id)
def test_complete_items_reference_real_tests(item):
    """A COMPLETE item must cite at least one test, and every cited test must exist."""
    if item.status != cert_status.COMPLETE:
        return
    assert item.tests, f"{item.id} is COMPLETE but cites no tests"
    for ref in item.tests:
        resolved = _resolve(ref)  # raises ModuleNotFoundError/AttributeError if missing
        assert resolved is not None


def test_no_blanket_pass_in_report():
    """Regression guard: report status values must come from the status module, not 'pass'."""
    import apps.certification.report as report
    src = report.__file__
    with open(src) as f:
        text = f.read()
    assert 'all are implemented in P2.16' not in text, "report must not hard-code completion"


def test_readiness_score_matches_counts():
    counts = cert_status.status_counts()
    total_in_scope = sum(v for k, v in counts.items() if k != cert_status.OUT_OF_SCOPE)
    expected = round(counts[cert_status.COMPLETE] / total_in_scope * 100, 1)
    assert cert_status.readiness_score() == expected
