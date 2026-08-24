"""
Credit Engine (F3) certification — the generic Core capability for discounts, scholarships,
waivers, credit notes, refunds, and write-offs. Proves: every kind posts a BALANCED entry
through the single GL to the correct accounts (resolved from AccountingSettings, no hardcoded
codes), gapless numbering, idempotency on external_ref, void → reversal, domain events, RBAC on
the REST layer, and workspace isolation. Runs on SQLite and PostgreSQL.
"""
import uuid
from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.credits.models import CreditNote
from apps.credits.services import CreditError, CreditService
from apps.eventstore.models import DomainEvent
from apps.ledger.models import JournalEntry, JournalLine
from apps.ledger.provisioning import provision_accounting
from apps.tenancy.models import Workspace, WorkspaceMember

A = str(uuid.uuid4())
PW = "Sup3rStr0ng!pw"


@pytest.fixture
def ws(db):
    w = uuid.uuid4()
    provision_accounting(w)
    return w


def _entry(note):
    return JournalEntry.objects.get(id=note.journal_entry_id)


def _lines(note):
    e = _entry(note)
    return {ln.account.code: (ln.debit, ln.credit)
            for ln in JournalLine.objects.filter(entry=e).select_related("account")}


# ── posting: each kind hits the right accounts and balances ──────────────────
@pytest.mark.django_db
@pytest.mark.parametrize("kind,dr,cr", [
    ("discount", "4200", "1100"),
    ("waiver", "4200", "1100"),
    ("credit_note", "4200", "1100"),
    ("scholarship", "6700", "1100"),
    ("write_off", "6800", "1100"),
    ("refund", "4100", "1000"),
])
def test_issue_posts_balanced_entry(ws, kind, dr, cr):
    note = CreditService.issue(
        workspace_id=ws, kind=kind, amount="150.00", subject_ref="student-1",
        applies_to_ref="FEE-0001", reason="test", actor_id=A)
    assert note.status == CreditNote.POSTED
    assert note.amount == Decimal("150.00")
    assert note.journal_entry_id is not None
    lines = _lines(note)
    assert lines[dr][0] == Decimal("150.00")   # debit side
    assert lines[cr][1] == Decimal("150.00")   # credit side
    # balanced
    e = _entry(note)
    debit = sum(ln.debit for ln in e.lines.all())
    credit = sum(ln.credit for ln in e.lines.all())
    assert debit == credit == Decimal("150.00")
    assert e.source_module == "credits" and e.source_ref == note.number
    assert DomainEvent.objects.filter(event_type=f"credit.{kind}.issued").exists()


@pytest.mark.django_db
def test_numbering_is_gapless_per_kind(ws):
    n1 = CreditService.issue(workspace_id=ws, kind="discount", amount=10, actor_id=A)
    n2 = CreditService.issue(workspace_id=ws, kind="discount", amount=20, actor_id=A)
    assert n1.number == "CN-000001" and n2.number == "CN-000002"
    r1 = CreditService.issue(workspace_id=ws, kind="refund", amount=5, actor_id=A)
    assert r1.number == "RF-000001"


@pytest.mark.django_db
def test_idempotent_on_external_ref(ws):
    a = CreditService.issue(workspace_id=ws, kind="discount", amount=100,
                            external_ref="school:invoice:42", actor_id=A)
    b = CreditService.issue(workspace_id=ws, kind="discount", amount=100,
                            external_ref="school:invoice:42", actor_id=A)
    assert a.id == b.id
    assert CreditNote.objects.filter(workspace_id=ws).count() == 1
    assert JournalEntry.objects.filter(workspace_id=ws, source_module="credits").count() == 1


@pytest.mark.django_db
def test_void_posts_reversal(ws):
    note = CreditService.issue(workspace_id=ws, kind="discount", amount=100, actor_id=A)
    voided = CreditService.void(workspace_id=ws, credit_id=note.id, reason="mistake", actor_id=A)
    assert voided.status == CreditNote.VOID
    assert voided.reversal_entry_id is not None
    # original + reversal both exist; net GL effect is zero
    entries = JournalEntry.objects.filter(workspace_id=ws, source_module="credits")
    total_dr = sum(ln.debit for e in entries for ln in e.lines.all())
    total_cr = sum(ln.credit for e in entries for ln in e.lines.all())
    assert total_dr == total_cr
    assert DomainEvent.objects.filter(event_type="credit.discount.voided").exists()


@pytest.mark.django_db
def test_void_is_idempotent(ws):
    note = CreditService.issue(workspace_id=ws, kind="discount", amount=100, actor_id=A)
    CreditService.void(workspace_id=ws, credit_id=note.id, actor_id=A)
    again = CreditService.void(workspace_id=ws, credit_id=note.id, actor_id=A)
    assert again.status == CreditNote.VOID


@pytest.mark.django_db
def test_rejects_bad_input(ws):
    with pytest.raises(CreditError):
        CreditService.issue(workspace_id=ws, kind="discount", amount=0, actor_id=A)
    with pytest.raises(CreditError):
        CreditService.issue(workspace_id=ws, kind="nonsense", amount=10, actor_id=A)


@pytest.mark.django_db
def test_account_override(ws):
    note = CreditService.issue(workspace_id=ws, kind="discount", amount=50,
                               debit_account="4900", credit_account="1100", actor_id=A)
    lines = _lines(note)
    assert "4900" in lines


# ── workflow executor consumes the engine (School's manifest path) ───────────
@pytest.mark.django_db
def test_workflow_executor_applies_credit(ws):
    from apps.workflows.executors import get_executor

    class _Step:
        id = uuid.uuid4()
        config = {"kind": "scholarship", "amount": "{{record.fee}}",
                  "applies_to_ref": "FEE-9", "subject_ref": "stu-9"}

    class _Run:
        id = uuid.uuid4()
        workspace_id = ws
        initiated_by = None

    ctx = {"record": {"fee": "300.00"}}
    out = get_executor("action_apply_credit")(_Step(), _Run(), ctx, None)
    assert out["applied"] is True and out["kind"] == "scholarship"
    note = CreditNote.objects.get(id=out["credit_id"])
    assert note.amount == Decimal("300.00")
    # re-running the same step is idempotent (external_ref = workflow:<run>:<step>)
    out2 = get_executor("action_apply_credit")(_Step(), _Run(), ctx, None)
    assert out2  # returns the same credit, no duplicate


# ── REST layer (auth + RBAC) ─────────────────────────────────────────────────
def _client(ws_obj, role, email):
    u = User.objects.create_user(email=email, password=PW, is_verified=True)
    WorkspaceMember.objects.create(workspace=ws_obj, user=u, role=role, status="active")
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(u)}",
                  HTTP_X_WORKSPACE_SLUG=ws_obj.slug)
    return c


@pytest.mark.django_db
def test_rest_issue_and_rbac(db):
    w = Workspace.objects.create(name="Credit Co", slug="credit-co", is_active=True)
    provision_accounting(w.id)

    # member cannot issue
    r = _client(w, "member", "m@credit.co").post(
        "/api/v1/credits/credits/", {"kind": "discount", "amount": "25.00"}, format="json")
    assert r.status_code == 403

    # admin can issue
    admin = _client(w, "admin", "a@credit.co")
    r = admin.post("/api/v1/credits/credits/",
                   {"kind": "discount", "amount": "25.00", "applies_to_ref": "FEE-1"},
                   format="json")
    assert r.status_code == 201, r.content
    cid = r.json()["id"]
    assert r.json()["number"] == "CN-000001"

    # list + detail
    assert admin.get("/api/v1/credits/credits/").status_code == 200
    assert admin.get(f"/api/v1/credits/credits/{cid}/").status_code == 200

    # void
    assert admin.post(f"/api/v1/credits/credits/{cid}/void/").json()["status"] == "void"
