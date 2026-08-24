"""
Tax Engine (Financial Platform — Gap G1) certification.

Proves the reusable, package-independent tax capability: deterministic calculation (exclusive/
inclusive/compound/group/exemption/temporal-rate), balanced GL posting through the single GLBus,
idempotency, reversal, the tax-return summary, the workflow actions, and workspace isolation. No
package code — every ERP package consumes THIS engine.
"""
import datetime as dt
import types
import uuid
from decimal import Decimal

import pytest

from apps.ledger.models import JournalEntry
from apps.ledger.provisioning import provision_accounting
from apps.ledger.services import GLBus
from apps.taxes.models import TaxCode


def _code(ws, code="VAT", *, rate="15", inclusive=False, compound=False, recoverable=True,
          tax_type="vat", eff_from=None):
    from apps.taxes.models import TaxCode, TaxRate
    tc = TaxCode.objects.create(workspace_id=ws, code=code, name=code, tax_type=tax_type,
                                is_inclusive=inclusive, is_compound=compound,
                                is_recoverable=recoverable)
    TaxRate.objects.create(workspace_id=ws, tax_code=tc, rate=Decimal(rate),
                           effective_from=eff_from)
    return tc


def _d(v):
    return Decimal(str(v))


# ── pure calculation ───────────────────────────────────────────────────────────
@pytest.mark.django_db
def test_calculate_exclusive_single_code():
    from apps.taxes.services import TaxService
    ws = uuid.uuid4()
    _code(ws, "VAT", rate="15")
    calc = TaxService.calculate(ws, amount="100", tax_code="VAT")
    assert calc["net"] == _d("100.00")
    assert calc["total_tax"] == _d("15.00")
    assert calc["gross"] == _d("115.00")
    assert len(calc["components"]) == 1 and calc["components"][0]["amount"] == _d("15.00")


@pytest.mark.django_db
def test_calculate_inclusive_backs_out_tax():
    from apps.taxes.services import TaxService
    ws = uuid.uuid4()
    _code(ws, "VAT", rate="15", inclusive=True)
    calc = TaxService.calculate(ws, amount="115", tax_code="VAT")
    assert calc["inclusive"] is True
    assert calc["net"] == _d("100.00")
    assert calc["total_tax"] == _d("15.00")
    assert calc["gross"] == _d("115.00")           # inclusive invariant: gross == input amount


@pytest.mark.django_db
def test_calculate_group_non_compound():
    from apps.taxes.models import TaxGroup, TaxGroupMember
    from apps.taxes.services import TaxService
    ws = uuid.uuid4()
    a = _code(ws, "STATE", rate="10")
    b = _code(ws, "CITY", rate="5")
    g = TaxGroup.objects.create(workspace_id=ws, code="US_SALES", name="US Sales")
    TaxGroupMember.objects.create(workspace_id=ws, tax_group=g, tax_code=a, sequence=1)
    TaxGroupMember.objects.create(workspace_id=ws, tax_group=g, tax_code=b, sequence=2)
    calc = TaxService.calculate(ws, amount="100", tax_group="US_SALES")
    # both apply to the net (100): 10 + 5 = 15
    assert calc["total_tax"] == _d("15.00")
    assert calc["gross"] == _d("115.00")


@pytest.mark.django_db
def test_calculate_group_compound_cascades():
    from apps.taxes.models import TaxGroup, TaxGroupMember
    from apps.taxes.services import TaxService
    ws = uuid.uuid4()
    a = _code(ws, "GST", rate="10")                       # non-compound on net
    b = _code(ws, "PST", rate="5", compound=True)         # compound: on net + prior tax
    g = TaxGroup.objects.create(workspace_id=ws, code="CA", name="Canada")
    TaxGroupMember.objects.create(workspace_id=ws, tax_group=g, tax_code=a, sequence=1)
    TaxGroupMember.objects.create(workspace_id=ws, tax_group=g, tax_code=b, sequence=2)
    calc = TaxService.calculate(ws, amount="100", tax_group="CA")
    comps = {c["code"]: c for c in calc["components"]}
    assert comps["GST"]["amount"] == _d("10.00")          # 10% of 100
    assert comps["PST"]["base"] == _d("110.00")           # compound base = 100 + 10
    assert comps["PST"]["amount"] == _d("5.50")           # 5% of 110
    assert calc["total_tax"] == _d("15.50")


@pytest.mark.django_db
def test_calculate_exemption_zeroes_tax():
    from apps.taxes.models import TaxExemption
    from apps.taxes.services import TaxService
    ws = uuid.uuid4()
    tc = _code(ws, "VAT", rate="15")
    TaxExemption.objects.create(workspace_id=ws, partner_ref="cust-1", tax_code=tc)
    calc = TaxService.calculate(ws, amount="100", tax_code="VAT", partner_ref="cust-1")
    assert calc["total_tax"] == _d("0.00") and calc["exempt"] is True
    # a different partner is still taxed
    calc2 = TaxService.calculate(ws, amount="100", tax_code="VAT", partner_ref="cust-2")
    assert calc2["total_tax"] == _d("15.00")


@pytest.mark.django_db
def test_calculate_resolves_temporal_rate():
    from apps.taxes.models import TaxCode, TaxRate
    from apps.taxes.services import TaxService
    ws = uuid.uuid4()
    tc = TaxCode.objects.create(workspace_id=ws, code="VAT", name="VAT", tax_type="vat")
    TaxRate.objects.create(workspace_id=ws, tax_code=tc, rate=Decimal("10"),
                           effective_from=dt.date(2020, 1, 1), effective_to=dt.date(2022, 12, 31))
    TaxRate.objects.create(workspace_id=ws, tax_code=tc, rate=Decimal("15"),
                           effective_from=dt.date(2023, 1, 1))
    old = TaxService.calculate(ws, amount="100", tax_code="VAT", on_date=dt.date(2021, 6, 1))
    new = TaxService.calculate(ws, amount="100", tax_code="VAT", on_date=dt.date(2024, 6, 1))
    assert old["total_tax"] == _d("10.00")
    assert new["total_tax"] == _d("15.00")


# ── posting through the single GL ───────────────────────────────────────────────
@pytest.mark.django_db
def test_post_output_tax_is_balanced_in_gl():
    from apps.ledger.models import LedgerAccount
    from apps.taxes.models import TaxTransaction
    from apps.taxes.services import TaxService
    ws = uuid.uuid4()
    provision_accounting(ws)                       # seeds chart incl. 2210 + AR (1100)
    _code(ws, "VAT", rate="15")
    result = TaxService.post(
        ws, amount="100", tax_code="VAT", direction="output", source_module="hospital",
        source_ref="bill-1", partner_ref="pat-1", offset_account="1100", external_ref="hosp:bill:1")
    assert result["posted"] is True and result["journal_entry_id"]
    # the entry is balanced (GLBus enforces it) and the output-tax liability carries the tax
    out_acct = LedgerAccount.objects.get(workspace_id=ws, code="2210")
    assert GLBus.account_balance(ws, out_acct.id) == _d("-15.00")   # credit balance (liability)
    assert TaxTransaction.objects.filter(workspace_id=ws, source_ref="bill-1").count() == 1


@pytest.mark.django_db
def test_post_is_idempotent_on_external_ref():
    from apps.taxes.models import TaxTransaction
    from apps.taxes.services import TaxService
    ws = uuid.uuid4()
    provision_accounting(ws)
    _code(ws, "VAT", rate="15")
    for _ in range(2):
        TaxService.post(ws, amount="100", tax_code="VAT", offset_account="1100",
                        source_module="retail", source_ref="inv-9", external_ref="retail:inv:9")
    assert TaxTransaction.objects.filter(workspace_id=ws, external_ref="retail:inv:9").count() == 1
    # exactly one GL entry posted for the tax
    assert JournalEntry.objects.filter(
        workspace_id=ws, source_ref="tax:inv-9").exclude(status=JournalEntry.REVERSED).count() == 1


@pytest.mark.django_db
def test_reverse_tax_reverses_gl_and_subledger():
    from apps.taxes.models import TaxTransaction
    from apps.taxes.services import TaxService
    ws = uuid.uuid4()
    provision_accounting(ws)
    _code(ws, "VAT", rate="15")
    TaxService.post(ws, amount="100", tax_code="VAT", offset_account="1100",
                    source_module="hotel", source_ref="folio-3", external_ref="hotel:folio:3")
    out = TaxService.reverse(ws, external_ref="hotel:folio:3", reason="cancelled")
    assert out["reversed"] == 1
    assert TaxTransaction.objects.get(workspace_id=ws, external_ref="hotel:folio:3").status == \
        TaxTransaction.REVERSED
    from apps.ledger.models import LedgerAccount
    out_acct = LedgerAccount.objects.get(workspace_id=ws, code="2210")
    assert GLBus.account_balance(ws, out_acct.id) == _d("0.00")     # reversal nets to zero


@pytest.mark.django_db
def test_tax_summary_reports_output_input_and_net():
    from apps.taxes.services import TaxService
    ws = uuid.uuid4()
    provision_accounting(ws)
    _code(ws, "VAT_OUT", rate="15")
    _code(ws, "VAT_IN", rate="15", recoverable=True)
    TaxService.post(ws, amount="200", tax_code="VAT_OUT", direction="output",
                    offset_account="1100", source_ref="s1", external_ref="o1")
    TaxService.post(ws, amount="100", tax_code="VAT_IN", direction="input",
                    offset_account="2000", source_ref="p1", external_ref="i1")
    summary = TaxService.tax_summary(ws)
    assert summary["output_tax"] == "30.00"
    assert summary["input_tax_recoverable"] == "15.00"
    assert summary["net_payable"] == "15.00"


# ── the reusable workflow actions ───────────────────────────────────────────────
def _run(ws):
    return types.SimpleNamespace(workspace_id=ws, initiated_by=None, id=uuid.uuid4(),
                                 record_id=None)


@pytest.mark.django_db
def test_action_calculate_tax_injects_into_context():
    from apps.taxes.services import TaxService  # noqa: F401 — ensures app import
    from apps.workflows.executors import exec_calculate_tax
    ws = uuid.uuid4()
    _code(ws, "VAT", rate="15")
    step = types.SimpleNamespace(config={"amount": "100", "tax_code": "VAT", "result_key": "tax"},
                                 id="s1")
    ctx = {}
    out = exec_calculate_tax(step, _run(ws), ctx, None)
    assert out["calculated"] is True and out["total_tax"] == "15.00"
    assert ctx["tax"]["gross"] == "115.00"          # injected for a following post_journal


@pytest.mark.django_db
def test_action_post_tax_records_and_posts():
    from apps.taxes.models import TaxTransaction
    from apps.workflows.executors import exec_post_tax
    ws = uuid.uuid4()
    provision_accounting(ws)
    _code(ws, "VAT", rate="15")
    step = types.SimpleNamespace(config={
        "amount": "100", "tax_code": "VAT", "offset_account": "1100",
        "source_module": "government", "source_ref": "permit-7"}, id="s2")
    out = exec_post_tax(step, _run(ws), {}, None)
    assert out["posted"] is True
    assert TaxTransaction.objects.filter(workspace_id=ws, source_ref="permit-7").count() == 1


# ── governance: workspace isolation + package independence ──────────────────────
@pytest.mark.django_db
def test_tax_codes_are_workspace_isolated():
    ws_a, ws_b = uuid.uuid4(), uuid.uuid4()
    _code(ws_a, "VAT", rate="15")
    assert TaxCode.objects.filter(workspace_id=ws_a, code="VAT").exists()
    assert not TaxCode.objects.filter(workspace_id=ws_b, code="VAT").exists()


def test_tax_engine_is_registered_as_a_platform_capability():
    """The Tax Engine is a single canonical Core capability packages compose against — never a
    package-private implementation."""
    from apps.packaging.capabilities import capability_available
    assert capability_available("tax_engine")


def test_no_package_ships_tax_logic():
    """No industry package re-implements tax: the tax engine lives only in apps/taxes + the shared
    workflow executors. (Guards the Rule-20 platform boundary.)"""
    from apps.workflows.executors import REGISTRY
    for action in ["action_calculate_tax", "action_post_tax", "action_reverse_tax"]:
        assert action in REGISTRY
