"""
Company platform (F11) certification — the shared legal-entity object.

Proves Company is a platform object (not finance-only), tax registrations are a first-class entity
(not JSON), ownership is a temporal relationship, the workspace Default Company mechanism, and
workspace isolation.
"""
import datetime as dt
import uuid
from decimal import Decimal

import pytest

from apps.companies.models import Company, CompanyOwnership, CompanyTaxRegistration
from apps.companies.services import CompanyError, CompanyService


@pytest.mark.django_db
def test_company_hierarchy_and_default():
    ws = uuid.uuid4()
    group = CompanyService.ensure_company(workspace_id=ws, code="GRP", name="Group",
                                          functional_currency="USD", is_group=True)
    a = CompanyService.ensure_company(workspace_id=ws, code="A", functional_currency="USD",
                                      parent_code="GRP")
    assert a.parent_id == group.id
    default = CompanyService.ensure_default_company(workspace_id=ws)
    assert default.is_default and default.code == "DEFAULT"
    # idempotent
    assert CompanyService.ensure_default_company(workspace_id=ws).id == default.id


@pytest.mark.django_db
def test_tax_registration_is_first_class_not_json():
    ws = uuid.uuid4()
    CompanyService.ensure_company(workspace_id=ws, code="A")
    # Company has NO tax_registrations JSON field
    assert not hasattr(Company(), "tax_registrations") or \
        not isinstance(getattr(Company(), "tax_registrations", None), dict)
    CompanyService.add_tax_registration(workspace_id=ws, company_code="A", tax_type="vat",
                                        authority="HMRC", jurisdiction="UK",
                                        registration_number="GB123")
    CompanyService.add_tax_registration(workspace_id=ws, company_code="A", tax_type="corporate_tax",
                                        registration_number="CT-9")
    regs = CompanyTaxRegistration.objects.filter(workspace_id=ws)
    assert regs.count() == 2 and {r.tax_type for r in regs} == {"vat", "corporate_tax"}


@pytest.mark.django_db
def test_ownership_is_temporal():
    ws = uuid.uuid4()
    CompanyService.ensure_company(workspace_id=ws, code="P")
    CompanyService.ensure_company(workspace_id=ws, code="S")
    CompanyService.set_ownership(workspace_id=ws, parent_code="P", subsidiary_code="S",
                                 ownership_pct="60", effective_from=dt.date(2026, 1, 1))
    CompanyService.set_ownership(workspace_id=ws, parent_code="P", subsidiary_code="S",
                                 ownership_pct="80", effective_from=dt.date(2026, 6, 1))
    sub = Company.objects.get(workspace_id=ws, code="S")
    assert CompanyService.ownership_pct_at(ws, sub.id, on_date=dt.date(2026, 3, 1)) == Decimal("60")
    assert CompanyService.ownership_pct_at(ws, sub.id, on_date=dt.date(2026, 7, 1)) == Decimal("80")
    assert CompanyOwnership.objects.filter(workspace_id=ws).count() == 2


@pytest.mark.django_db
def test_self_ownership_rejected():
    ws = uuid.uuid4()
    CompanyService.ensure_company(workspace_id=ws, code="A")
    with pytest.raises(CompanyError):
        CompanyService.set_ownership(workspace_id=ws, parent_code="A", subsidiary_code="A",
                                     ownership_pct="100")


@pytest.mark.django_db
def test_company_workspace_isolated_and_capability():
    from apps.packaging.capabilities import capability_available
    ws_a, ws_b = uuid.uuid4(), uuid.uuid4()
    CompanyService.ensure_company(workspace_id=ws_a, code="A")
    assert Company.objects.filter(workspace_id=ws_a, code="A").exists()
    assert not Company.objects.filter(workspace_id=ws_b, code="A").exists()
    assert capability_available("companies")


@pytest.mark.django_db
def test_provisioning_creates_default_company():
    """Finance provisioning gives every workspace an explicit Default Company (consolidation-ready)."""
    from apps.ledger.provisioning import provision_accounting
    ws = uuid.uuid4()
    provision_accounting(ws)
    assert Company.objects.filter(workspace_id=ws, is_default=True).exists()
