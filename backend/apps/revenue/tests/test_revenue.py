"""
Revenue Recognition engine (F5 / Gap G5) certification.

Proves the reusable deferred-revenue capability: straight-line/immediate/milestone schedules,
period recognition posting Dr Deferred / Cr Revenue through the single GLBus, idempotency, schedule
completion, cancellation (GL reversal), the workflow actions, and workspace isolation. No package
code — every ERP package consumes THIS engine.
"""
import datetime as dt
import types
import uuid
from decimal import Decimal

import pytest

from apps.ledger.models import JournalEntry, LedgerAccount
from apps.ledger.provisioning import provision_accounting
from apps.ledger.services import GLBus
from apps.revenue.models import RevenueSchedule, RevenueScheduleLine
from apps.revenue.services import RevenueService


def _d(v):
    return Decimal(str(v))


def _bal(ws, code):
    acct = LedgerAccount.objects.get(workspace_id=ws, code=code)
    return GLBus.account_balance(ws, acct.id)


@pytest.mark.django_db
def test_straight_line_schedule_builds_equal_periods():
    ws = uuid.uuid4()
    provision_accounting(ws)
    sched = RevenueService.create_schedule(
        workspace_id=ws, total_amount="1200", method="straight_line", num_periods=12,
        start_date=dt.date(2026, 1, 1), source_ref="sub-1", external_ref="rev:sub:1")
    lines = list(RevenueScheduleLine.objects.filter(workspace_id=ws, schedule=sched)
                 .order_by("period_no"))
    assert len(lines) == 12
    assert sum((line.amount for line in lines), _d(0)) == _d("1200.00")   # sums to the total
    assert lines[0].amount == _d("100.00") and lines[0].period_date == dt.date(2026, 1, 1)
    assert lines[1].period_date == dt.date(2026, 2, 1)                    # monthly cadence


@pytest.mark.django_db
def test_rounding_absorbed_on_last_period():
    ws = uuid.uuid4()
    provision_accounting(ws)
    sched = RevenueService.create_schedule(
        workspace_id=ws, total_amount="100", method="straight_line", num_periods=3,
        external_ref="rev:r:1")
    amounts = [line.amount for line in sched.lines.order_by("period_no")]
    assert amounts[:2] == [_d("33.33"), _d("33.33")]
    assert amounts[2] == _d("33.34")                                     # remainder on the last
    assert sum(amounts, _d(0)) == _d("100.00")


@pytest.mark.django_db
def test_recognize_due_posts_deferred_to_revenue_and_completes():
    ws = uuid.uuid4()
    provision_accounting(ws)
    RevenueService.create_schedule(
        workspace_id=ws, total_amount="300", method="straight_line", num_periods=3,
        start_date=dt.date(2026, 1, 1), revenue_account="4000", external_ref="rev:svc:1")
    # recognise the first two periods (Jan + Feb) as of mid-Feb
    out = RevenueService.recognize_due(workspace_id=ws, as_of=dt.date(2026, 2, 15))
    assert out["recognized_lines"] == 2 and out["recognized_amount"] == "200.00"
    # deferred (2400) debited 200, revenue (4000) credited 200
    assert _bal(ws, "2400") == _d("200.00")            # asset-side debit balance on the liability
    assert _bal(ws, "4000") == _d("-200.00")           # revenue credit balance
    # recognising again is idempotent (no double-post)
    again = RevenueService.recognize_due(workspace_id=ws, as_of=dt.date(2026, 2, 15))
    assert again["recognized_lines"] == 0
    # recognise the rest → schedule completes
    RevenueService.recognize_due(workspace_id=ws, as_of=dt.date(2026, 12, 31))
    sched = RevenueSchedule.objects.get(workspace_id=ws, external_ref="rev:svc:1")
    assert sched.status == RevenueSchedule.COMPLETED
    assert sched.recognized_amount == _d("300.00")


@pytest.mark.django_db
def test_immediate_method_recognizes_whole_amount():
    ws = uuid.uuid4()
    provision_accounting(ws)
    RevenueService.create_schedule(workspace_id=ws, total_amount="500", method="immediate",
                                   start_date=dt.date(2026, 1, 1), external_ref="rev:im:1")
    out = RevenueService.recognize_due(workspace_id=ws, as_of=dt.date(2026, 1, 1))
    assert out["recognized_lines"] == 1 and out["recognized_amount"] == "500.00"


@pytest.mark.django_db
def test_milestone_method_uses_supplied_amounts():
    ws = uuid.uuid4()
    provision_accounting(ws)
    sched = RevenueService.create_schedule(
        workspace_id=ws, total_amount="1000", method="milestone",
        milestone_amounts=["400", "600"], start_date=dt.date(2026, 1, 1), external_ref="rev:ms:1")
    amounts = [line.amount for line in sched.lines.order_by("period_no")]
    assert amounts == [_d("400.00"), _d("600.00")]


@pytest.mark.django_db
def test_create_schedule_is_idempotent_on_external_ref():
    ws = uuid.uuid4()
    provision_accounting(ws)
    for _ in range(2):
        RevenueService.create_schedule(workspace_id=ws, total_amount="120", num_periods=12,
                                       external_ref="rev:dup:1")
    assert RevenueSchedule.objects.filter(workspace_id=ws, external_ref="rev:dup:1").count() == 1


@pytest.mark.django_db
def test_cancel_reverses_recognized_periods():
    ws = uuid.uuid4()
    provision_accounting(ws)
    sched = RevenueService.create_schedule(
        workspace_id=ws, total_amount="300", num_periods=3, start_date=dt.date(2026, 1, 1),
        revenue_account="4000", external_ref="rev:cx:1")
    RevenueService.recognize_due(workspace_id=ws, as_of=dt.date(2026, 1, 31))   # 1 period = 100
    assert _bal(ws, "4000") == _d("-100.00")
    RevenueService.cancel(workspace_id=ws, schedule_id=sched.id, reason="refunded")
    assert _bal(ws, "4000") == _d("0.00")               # recognition reversed
    assert RevenueSchedule.objects.get(id=sched.id).status == RevenueSchedule.CANCELLED


# ── the reusable workflow actions ───────────────────────────────────────────────
def _run(ws):
    return types.SimpleNamespace(workspace_id=ws, initiated_by=None, id=uuid.uuid4(),
                                 record_id=None)


@pytest.mark.django_db
def test_action_create_and_recognize_revenue():
    from apps.workflows.executors import exec_create_revenue_schedule, exec_recognize_revenue
    ws = uuid.uuid4()
    provision_accounting(ws)
    create = types.SimpleNamespace(config={
        "total_amount": "240", "num_periods": 12, "start_date": "2026-01-01",
        "revenue_account": "4000", "source_ref": "mem-1"}, id="s1")
    out = exec_create_revenue_schedule(create, _run(ws), {}, None)
    assert out["created"] is True and out["periods"] == 12
    rec = types.SimpleNamespace(config={"as_of": "2026-03-31"}, id="s2")
    rout = exec_recognize_revenue(rec, _run(ws), {}, None)
    assert rout["recognized_lines"] == 3 and rout["recognized_amount"] == "60.00"


@pytest.mark.django_db
def test_schedules_are_workspace_isolated():
    ws_a, ws_b = uuid.uuid4(), uuid.uuid4()
    provision_accounting(ws_a)
    RevenueService.create_schedule(workspace_id=ws_a, total_amount="100", external_ref="x")
    assert RevenueSchedule.objects.filter(workspace_id=ws_a).exists()
    assert not RevenueSchedule.objects.filter(workspace_id=ws_b).exists()


def test_revenue_recognition_registered_as_capability_and_actions():
    from apps.packaging.capabilities import capability_available
    from apps.workflows.executors import REGISTRY
    assert capability_available("revenue_recognition")
    for action in ["action_create_revenue_schedule", "action_recognize_revenue"]:
        assert action in REGISTRY


# keep JournalEntry import meaningful (posted entries exist after recognition)
@pytest.mark.django_db
def test_recognition_creates_posted_entries():
    ws = uuid.uuid4()
    provision_accounting(ws)
    RevenueService.create_schedule(workspace_id=ws, total_amount="100", method="immediate",
                                   start_date=dt.date(2026, 1, 1), external_ref="rev:pe:1")
    RevenueService.recognize_due(workspace_id=ws, as_of=dt.date(2026, 1, 1))
    assert JournalEntry.objects.filter(workspace_id=ws, source_module="revenue",
                                       status=JournalEntry.POSTED).count() == 1
