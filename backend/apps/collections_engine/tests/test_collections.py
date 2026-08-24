"""
Collections Engine (F2) certification — the generic Core capability for installments / payment
plans / due schedules / reminders / late fees / dunning. Proves: schedule generation (even split
+ remainder + due dates), payment tracking (partial→paid→plan complete), late-fee posting through
the single GL (Dr Receivable / Cr Late-fee income, idempotent, grace-aware), reminders + dunning
events, dashboard, RBAC on the REST layer, and workspace isolation. SQLite + PostgreSQL.
"""
import datetime
import uuid
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.collections_engine.models import Installment, InstallmentPlan
from apps.collections_engine.services import CollectionsError, CollectionsService
from apps.eventstore.models import DomainEvent
from apps.ledger.models import JournalEntry, JournalLine
from apps.ledger.provisioning import provision_accounting
from apps.tenancy.models import Workspace, WorkspaceMember

A = str(uuid.uuid4())
PW = "Sup3rStr0ng!pw"
PAST = datetime.date(2024, 1, 1)


@pytest.fixture
def ws(db):
    w = uuid.uuid4()
    provision_accounting(w)
    return w


# ── schedule generation ──────────────────────────────────────────────────────
@pytest.mark.django_db
def test_create_plan_generates_schedule(ws):
    plan = CollectionsService.create_plan(
        workspace_id=ws, total_amount="300.00", num_installments=3,
        start_date=datetime.date(2026, 1, 15), frequency="monthly", actor_id=A)
    assert plan.number == "PLAN-000001"
    inst = CollectionsService.plan_installments(ws, plan.id)
    assert [i.amount for i in inst] == [Decimal("100.00")] * 3
    assert [i.due_date for i in inst] == [
        datetime.date(2026, 1, 15), datetime.date(2026, 2, 15), datetime.date(2026, 3, 15)]
    assert DomainEvent.objects.filter(event_type="collections.plan.created").exists()


@pytest.mark.django_db
def test_split_puts_remainder_in_last(ws):
    plan = CollectionsService.create_plan(
        workspace_id=ws, total_amount="100.00", num_installments=3,
        start_date=PAST, actor_id=A)
    amts = [i.amount for i in CollectionsService.plan_installments(ws, plan.id)]
    assert amts == [Decimal("33.33"), Decimal("33.33"), Decimal("33.34")]
    assert sum(amts) == Decimal("100.00")


@pytest.mark.django_db
def test_idempotent_on_external_ref(ws):
    a = CollectionsService.create_plan(
        workspace_id=ws, total_amount=200, num_installments=2, start_date=PAST,
        external_ref="school:invoice:7", actor_id=A)
    b = CollectionsService.create_plan(
        workspace_id=ws, total_amount=200, num_installments=2, start_date=PAST,
        external_ref="school:invoice:7", actor_id=A)
    assert a.id == b.id
    assert InstallmentPlan.objects.filter(workspace_id=ws).count() == 1


# ── payment tracking (no GL — payment doc posts the cash) ─────────────────────
@pytest.mark.django_db
def test_record_payment_progresses_and_completes(ws):
    plan = CollectionsService.create_plan(
        workspace_id=ws, total_amount="300.00", num_installments=3, start_date=PAST, actor_id=A)
    CollectionsService.record_payment(workspace_id=ws, plan_id=plan.id, amount="100.00", actor_id=A)
    CollectionsService.record_payment(workspace_id=ws, plan_id=plan.id, amount="150.00", actor_id=A)
    inst = CollectionsService.plan_installments(ws, plan.id)
    assert inst[0].status == Installment.PAID
    assert inst[1].status == Installment.PAID
    assert inst[2].status == Installment.PARTIAL and inst[2].paid_amount == Decimal("50.00")
    # No cash GL is posted by collections (the payment document does that).
    assert not JournalEntry.objects.filter(workspace_id=ws, source_module="collections").exists()
    CollectionsService.record_payment(workspace_id=ws, plan_id=plan.id, amount="50.00", actor_id=A)
    assert InstallmentPlan.objects.get(id=plan.id).status == InstallmentPlan.COMPLETED


# ── late fees (the one GL this engine posts) ─────────────────────────────────
@pytest.mark.django_db
def test_flat_late_fee_posts_balanced_gl(ws):
    plan = CollectionsService.create_plan(
        workspace_id=ws, total_amount="100.00", num_installments=1, start_date=PAST,
        grace_days=0, late_fee_type="flat", late_fee_value="10.00", actor_id=A)
    inst = CollectionsService.plan_installments(ws, plan.id)[0]
    charged = CollectionsService.charge_late_fee(workspace_id=ws, installment_id=inst.id,
                                                 as_of=datetime.date(2026, 6, 1), actor_id=A)
    assert charged.late_fee_amount == Decimal("10.00") and charged.late_fee_charged
    e = JournalEntry.objects.get(id=charged.late_fee_journal_entry_id)
    lines = {ln.account.code: (ln.debit, ln.credit) for ln in
             JournalLine.objects.filter(entry=e).select_related("account")}
    assert lines["1100"][0] == Decimal("10.00")   # Dr Receivable
    assert lines["4900"][1] == Decimal("10.00")   # Cr Late-fee income
    assert DomainEvent.objects.filter(event_type="collections.late_fee.charged").exists()
    # idempotent — a second charge does nothing
    assert CollectionsService.charge_late_fee(workspace_id=ws, installment_id=inst.id) is None


@pytest.mark.django_db
def test_percent_late_fee(ws):
    plan = CollectionsService.create_plan(
        workspace_id=ws, total_amount="200.00", num_installments=1, start_date=PAST,
        grace_days=0, late_fee_type="percent", late_fee_value="5.00", actor_id=A)
    inst = CollectionsService.plan_installments(ws, plan.id)[0]
    charged = CollectionsService.charge_late_fee(workspace_id=ws, installment_id=inst.id,
                                                 as_of=datetime.date(2026, 6, 1), actor_id=A)
    assert charged.late_fee_amount == Decimal("10.00")   # 5% of 200


@pytest.mark.django_db
def test_run_late_fees_respects_grace(ws):
    # due today, grace 5 days → NOT charged when run today
    CollectionsService.create_plan(
        workspace_id=ws, total_amount="100", num_installments=1,
        start_date=datetime.date(2026, 6, 1), grace_days=5, late_fee_type="flat",
        late_fee_value="10", actor_id=A)
    charged = CollectionsService.run_late_fees(workspace_id=ws, as_of=datetime.date(2026, 6, 3))
    assert charged == 0
    # past grace → charged
    charged2 = CollectionsService.run_late_fees(workspace_id=ws, as_of=datetime.date(2026, 6, 30))
    assert charged2 == 1


# ── reminders + dunning ───────────────────────────────────────────────────────
@pytest.mark.django_db
def test_run_reminders_and_dunning(ws):
    CollectionsService.create_plan(
        workspace_id=ws, total_amount="100", num_installments=1, start_date=PAST, actor_id=A)
    sent = CollectionsService.run_reminders(workspace_id=ws, as_of=datetime.date(2026, 6, 1))
    assert sent == 1
    assert DomainEvent.objects.filter(event_type="collections.reminder.sent").exists()
    # reminder is not re-sent
    assert CollectionsService.run_reminders(workspace_id=ws, as_of=datetime.date(2026, 6, 2)) == 0
    esc = CollectionsService.run_dunning(workspace_id=ws, as_of=datetime.date(2026, 6, 1))
    assert esc == 1
    assert DomainEvent.objects.filter(event_type="collections.dunning.escalated").exists()


@pytest.mark.django_db
def test_dashboard(ws):
    CollectionsService.create_plan(
        workspace_id=ws, total_amount="300", num_installments=3, start_date=PAST, actor_id=A)
    CollectionsService.record_payment(workspace_id=ws,
                                      plan_id=InstallmentPlan.objects.get(workspace_id=ws).id,
                                      amount="100", actor_id=A)
    dash = CollectionsService.dashboard(ws)
    assert dash["total_billed"] == "300.00"
    assert dash["total_paid"] == "100.00"
    assert dash["total_outstanding"] == "200.00"


@pytest.mark.django_db
def test_validation(ws):
    with pytest.raises(CollectionsError):
        CollectionsService.create_plan(workspace_id=ws, total_amount=0, num_installments=3,
                                       start_date=PAST, actor_id=A)
    with pytest.raises(CollectionsError):
        CollectionsService.create_plan(workspace_id=ws, total_amount=100, num_installments=0,
                                       start_date=PAST, actor_id=A)


# ── workflow executor (School's manifest path) ───────────────────────────────
@pytest.mark.django_db
def test_workflow_executor_creates_plan(ws):
    from apps.workflows.executors import get_executor

    class _Step:
        id = uuid.uuid4()
        config = {"total_amount": "{{record.fee}}", "num_installments": 4,
                  "frequency": "monthly", "start_date": "2026-01-10",
                  "source_document_ref": "FEE-1"}

    class _Run:
        id = uuid.uuid4()
        workspace_id = ws
        initiated_by = None

    out = get_executor("action_create_installment_plan")(
        _Step(), _Run(), {"record": {"fee": "400.00"}}, None)
    assert out["plan_created"] and out["installments"] == 4
    plan = InstallmentPlan.objects.get(id=out["plan_id"])
    assert plan.total_amount == Decimal("400.00")


# ── REST layer (auth + RBAC) ─────────────────────────────────────────────────
def _client(ws_obj, role, email):
    u = User.objects.create_user(email=email, password=PW, is_verified=True)
    WorkspaceMember.objects.create(workspace=ws_obj, user=u, role=role, status="active")
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(u)}",
                  HTTP_X_WORKSPACE_SLUG=ws_obj.slug)
    return c


@pytest.mark.django_db
def test_rest_plan_lifecycle_and_rbac(db):
    w = Workspace.objects.create(name="Coll Co", slug="coll-co", is_active=True)
    provision_accounting(w.id)

    payload = {"total_amount": "300.00", "num_installments": 3, "start_date": "2024-01-01",
               "grace_days": 0, "late_fee_type": "flat", "late_fee_value": "5.00"}
    # member cannot create
    assert _client(w, "member", "m@coll.co").post(
        "/api/v1/collections/plans/", payload, format="json").status_code == 403

    admin = _client(w, "admin", "a@coll.co")
    r = admin.post("/api/v1/collections/plans/", payload, format="json")
    assert r.status_code == 201, r.content
    body = r.json()
    assert body["number"] == "PLAN-000001" and len(body["installments"]) == 3
    pid = body["id"]
    inst_id = body["installments"][1]["id"]   # a still-unpaid installment

    # detail + dashboard readable by member
    assert admin.get(f"/api/v1/collections/plans/{pid}/").status_code == 200
    assert _client(w, "member", "m2@coll.co").get(
        "/api/v1/collections/dashboard/").status_code == 200

    # record payment + charge late fee
    assert admin.post(f"/api/v1/collections/plans/{pid}/record-payment/",
                      {"amount": "100.00"}, format="json").status_code == 200
    lf = admin.post(f"/api/v1/collections/installments/{inst_id}/charge-late-fee/")
    assert lf.status_code == 200 and lf.json()["charged"] is True
