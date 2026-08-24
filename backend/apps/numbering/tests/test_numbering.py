"""
Numbering Engine (Phase P2.1) — gapless allocation, period resets, formatting, API, isolation.
"""
import datetime as dt
import uuid

import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.numbering.models import NumberAllocation, NumberSequence
from apps.numbering.services import NumberingError, NumberingService
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"
BASE = "/api/v1/numbering"


@pytest.fixture
def workspace(db):
    return Workspace.objects.create(name="Acme", slug="acme", is_active=True)


def _client(workspace, role="admin", email=None):
    email = email or f"{role}@example.com"
    user = User.objects.create_user(email=email, password=PW, is_verified=True)
    WorkspaceMember.objects.create(workspace=workspace, user=user, role=role, status="active")
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}",
                  HTTP_X_WORKSPACE_SLUG=workspace.slug)
    return c, user


# ── service-level ─────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestAllocation:
    def test_sequential_gapless_allocation(self):
        ws = uuid.uuid4()
        NumberSequence.objects.create(workspace_id=ws, key="invoice", prefix="INV-", padding=6)
        nums = [NumberingService.allocate(ws, "invoice") for _ in range(3)]
        assert nums == ["INV-000001", "INV-000002", "INV-000003"]
        # every allocation is logged (the gapless audit trail)
        assert NumberAllocation.objects.filter(workspace_id=ws, key="invoice").count() == 3

    def test_start_value_and_increment_respected(self):
        ws = uuid.uuid4()
        NumberSequence.objects.create(workspace_id=ws, key="po", prefix="PO-", padding=4,
                                      start_value=100, increment=10)
        assert NumberingService.allocate(ws, "po") == "PO-0100"
        assert NumberingService.allocate(ws, "po") == "PO-0110"

    def test_suffix_and_no_padding(self):
        ws = uuid.uuid4()
        NumberSequence.objects.create(workspace_id=ws, key="batch", prefix="B", suffix="/X", padding=0)
        assert NumberingService.allocate(ws, "batch") == "B1/X"

    def test_yearly_reset_restarts_counter(self):
        ws = uuid.uuid4()
        NumberSequence.objects.create(workspace_id=ws, key="je", prefix="JE-", padding=5,
                                      reset_scope=NumberSequence.RESET_YEARLY,
                                      include_period_in_format=True)
        y2025 = dt.datetime(2025, 12, 31, tzinfo=dt.UTC)
        y2026 = dt.datetime(2026, 1, 1, tzinfo=dt.UTC)
        assert NumberingService.allocate(ws, "je", now=y2025) == "JE-2025-00001"
        assert NumberingService.allocate(ws, "je", now=y2025) == "JE-2025-00002"
        # crossing into the new year restarts at 1 with the new period token
        assert NumberingService.allocate(ws, "je", now=y2026) == "JE-2026-00001"

    def test_monthly_reset(self):
        ws = uuid.uuid4()
        NumberSequence.objects.create(workspace_id=ws, key="rcpt", padding=3,
                                      reset_scope=NumberSequence.RESET_MONTHLY)
        jan = dt.datetime(2026, 1, 15, tzinfo=dt.UTC)
        feb = dt.datetime(2026, 2, 1, tzinfo=dt.UTC)
        assert NumberingService.allocate(ws, "rcpt", now=jan) == "001"
        assert NumberingService.allocate(ws, "rcpt", now=feb) == "001"

    def test_peek_does_not_consume(self):
        ws = uuid.uuid4()
        NumberSequence.objects.create(workspace_id=ws, key="q", prefix="Q-", padding=3)
        assert NumberingService.peek(ws, "q") == "Q-001"
        assert NumberingService.peek(ws, "q") == "Q-001"  # still 001 — not consumed
        assert NumberingService.allocate(ws, "q") == "Q-001"
        assert NumberingService.peek(ws, "q") == "Q-002"

    def test_unknown_sequence_raises(self):
        with pytest.raises(NumberingError):
            NumberingService.allocate(uuid.uuid4(), "nope")

    def test_inactive_sequence_raises(self):
        ws = uuid.uuid4()
        NumberSequence.objects.create(workspace_id=ws, key="x", is_active=False)
        with pytest.raises(NumberingError):
            NumberingService.allocate(ws, "x")

    def test_ensure_sequence_is_idempotent(self):
        ws = uuid.uuid4()
        a = NumberingService.ensure_sequence(ws, "journal_entry", defaults={"prefix": "JE-"})
        b = NumberingService.ensure_sequence(ws, "journal_entry", defaults={"prefix": "ZZ-"})
        assert a.id == b.id and a.prefix == "JE-" and a.is_system is True

    def test_reset_restarts_next_allocation(self):
        ws = uuid.uuid4()
        NumberSequence.objects.create(workspace_id=ws, key="r", prefix="R", padding=2)
        NumberingService.allocate(ws, "r")
        NumberingService.allocate(ws, "r")
        NumberingService.reset(ws, "r")
        assert NumberingService.allocate(ws, "r") == "R01"

    def test_rollback_does_not_consume_a_number(self):
        """Gaplessness tie-in: if the allocating transaction rolls back, the increment does too."""
        from django.db import transaction
        ws = uuid.uuid4()
        NumberSequence.objects.create(workspace_id=ws, key="g", prefix="G", padding=2)
        assert NumberingService.allocate(ws, "g") == "G01"
        try:
            with transaction.atomic():
                NumberingService.allocate(ws, "g")  # would be G02
                raise RuntimeError("boom")
        except RuntimeError:
            pass
        # the rolled-back G02 left no gap — the next number is still G02
        assert NumberingService.allocate(ws, "g") == "G02"


# ── API ───────────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestNumberingAPI:
    def test_admin_crud_sequence(self, workspace):
        admin, _ = _client(workspace, "admin")
        cr = admin.post(f"{BASE}/sequences/",
                        {"key": "invoice", "prefix": "INV-", "padding": 6}, format="json")
        assert cr.status_code == 201
        sid = cr.data["id"]
        assert admin.get(f"{BASE}/sequences/").status_code == 200
        pr = admin.patch(f"{BASE}/sequences/{sid}/", {"prefix": "BILL-"}, format="json")
        assert pr.status_code == 200 and pr.data["prefix"] == "BILL-"
        assert admin.delete(f"{BASE}/sequences/{sid}/").status_code == 204

    def test_member_cannot_create_sequence(self, workspace):
        member, _ = _client(workspace, "member")
        r = member.post(f"{BASE}/sequences/", {"key": "x"}, format="json")
        assert r.status_code == 403

    def test_peek_then_allocate(self, workspace):
        admin, _ = _client(workspace, "admin")
        sid = admin.post(f"{BASE}/sequences/",
                         {"key": "so", "prefix": "SO-", "padding": 5}, format="json").data["id"]
        assert admin.get(f"{BASE}/sequences/{sid}/peek/").data["next"] == "SO-00001"
        al = admin.post(f"{BASE}/sequences/{sid}/allocate/", {}, format="json")
        assert al.status_code == 201 and al.data["formatted"] == "SO-00001"
        assert admin.get(f"{BASE}/sequences/{sid}/peek/").data["next"] == "SO-00002"

    def test_member_can_allocate(self, workspace):
        admin, _ = _client(workspace, "admin")
        sid = admin.post(f"{BASE}/sequences/", {"key": "t", "prefix": "T-"}, format="json").data["id"]
        member, _ = _client(workspace, "member", email="m2@example.com")
        assert member.post(f"{BASE}/sequences/{sid}/allocate/", {}, format="json").status_code == 201

    def test_allocations_log_endpoint(self, workspace):
        admin, _ = _client(workspace, "admin")
        sid = admin.post(f"{BASE}/sequences/", {"key": "l", "prefix": "L-"}, format="json").data["id"]
        admin.post(f"{BASE}/sequences/{sid}/allocate/", {"context": {"source_module": "test"}},
                   format="json")
        log = admin.get(f"{BASE}/sequences/{sid}/allocations/")
        assert log.status_code == 200 and len(log.data["results"]) == 1
        assert log.data["results"][0]["context"]["source_module"] == "test"

    def test_reset_endpoint_admin_only(self, workspace):
        admin, _ = _client(workspace, "admin")
        sid = admin.post(f"{BASE}/sequences/", {"key": "rr", "prefix": "R"}, format="json").data["id"]
        admin.post(f"{BASE}/sequences/{sid}/allocate/", {}, format="json")
        assert admin.post(f"{BASE}/sequences/{sid}/reset/", {}, format="json").status_code == 200
        member, _ = _client(workspace, "member", email="m3@example.com")
        assert member.post(f"{BASE}/sequences/{sid}/reset/", {}, format="json").status_code == 403

    def test_workspace_isolation(self, workspace):
        admin, _ = _client(workspace, "admin")
        sid = admin.post(f"{BASE}/sequences/", {"key": "iso", "prefix": "I-"}, format="json").data["id"]
        other = Workspace.objects.create(name="Other", slug="other", is_active=True)
        other_admin, _ = _client(other, "admin", email="other@example.com")
        # the other workspace cannot see this sequence
        assert other_admin.get(f"{BASE}/sequences/{sid}/").status_code == 404
        assert other_admin.get(f"{BASE}/sequences/").data == []
