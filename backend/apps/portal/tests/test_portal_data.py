"""
Portal scoped-data API (Phase 1.34) — SECURITY-CRITICAL isolation.

Proves a portal user can only ever read/write records linked to them, via every path
(list, detail, client-supplied filter), plus capability + portal-type gating.
"""
import uuid

import pytest
from django.contrib.auth.hashers import make_password
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.portal import tokens as ptokens
from apps.portal.models import PortalEntityGrant, PortalUser
from apps.records.services import RecordService
from apps.schema_registry.services import SchemaRegistryService
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "P0rtalStr0ng!pw"
BASE = "/api/v1/portal/data"


@pytest.fixture
def setup(db):
    ws = Workspace.objects.create(name="Acme", slug="acme", is_active=True)
    admin = User.objects.create_user(email="admin@acme.com", password="Sup3rStr0ng!pw",
                                     is_verified=True)
    member = WorkspaceMember.objects.create(workspace=ws, user=admin, role="admin", status="active")

    ticket = SchemaRegistryService.create_entity(
        workspace_id=ws.id, slug="ticket", name="Ticket", plural_name="Tickets")
    for slug, ftype in [("subject", "text"), ("customer", "text")]:
        SchemaRegistryService.add_field(workspace_id=ws.id, entity_slug="ticket", slug=slug,
                                        name=slug.title(), field_type=ftype, is_promoted=True)
    ticket.refresh_from_db()

    cust_a, cust_b = uuid.uuid4(), uuid.uuid4()
    a1 = RecordService.create_record(workspace_id=ws.id, member=member, entity=ticket,
                                     data={"subject": "A ticket", "customer": str(cust_a)})
    b1 = RecordService.create_record(workspace_id=ws.id, member=member, entity=ticket,
                                     data={"subject": "B ticket", "customer": str(cust_b)})

    PortalEntityGrant.objects.create(workspace_id=ws.id, entity_slug="ticket",
                                     link_field="customer", can_read=True, can_create=True)

    user_a = PortalUser.objects.create(
        workspace_id=ws.id, email="a@cust.com", full_name="A", password_hash=make_password(PW),
        is_active=True, is_verified=True, linked_record_id=cust_a, portal_type="customer")
    user_b = PortalUser.objects.create(
        workspace_id=ws.id, email="b@cust.com", full_name="B", password_hash=make_password(PW),
        is_active=True, is_verified=True, linked_record_id=cust_b, portal_type="customer")
    return {"ws": ws, "ticket": ticket, "a": user_a, "b": user_b,
            "a1": a1["id"], "b1": b1["id"]}


def _portal_client(portal_user):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {ptokens.issue_portal_access(portal_user)}")
    return c


@pytest.mark.django_db
class TestPortalIsolation:
    def test_list_returns_only_own_records(self, setup):
        c = _portal_client(setup["a"])
        r = c.get(f"{BASE}/ticket/")
        assert r.status_code == 200
        subjects = {row["subject"] for row in r.data["results"]}
        assert subjects == {"A ticket"}        # B's ticket never appears

    def test_detail_of_own_record_ok(self, setup):
        c = _portal_client(setup["a"])
        r = c.get(f"{BASE}/ticket/{setup['a1']}/")
        assert r.status_code == 200
        assert r.data["subject"] == "A ticket"

    def test_detail_of_other_users_record_404(self, setup):
        # user A asking for B's record id → 404 (indistinguishable from missing)
        c = _portal_client(setup["a"])
        assert c.get(f"{BASE}/ticket/{setup['b1']}/").status_code == 404

    def test_client_filter_cannot_escape_scope(self, setup):
        # A tries to filter for B's customer value — link filter is AND-ed server-side
        c = _portal_client(setup["a"])
        import json
        flt = json.dumps({"field": "subject", "op": "=", "value": "B ticket"})
        r = c.get(f"{BASE}/ticket/?filter={flt}")
        assert r.status_code == 200
        assert r.data["results"] == []         # still scoped to A's records

    def test_unauthenticated_rejected(self, setup):
        assert APIClient().get(f"{BASE}/ticket/").status_code in (401, 403)

    def test_workspace_token_rejected(self, setup):
        # a workspace (accounts) access token must not work on the portal realm
        from apps.accounts import tokens as atok
        admin = User.objects.get(email="admin@acme.com")
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {atok.issue_access_token(admin)}")
        assert c.get(f"{BASE}/ticket/").status_code in (401, 403)

    def test_create_forces_link_field(self, setup):
        c = _portal_client(setup["a"])
        r = c.post(f"{BASE}/ticket/",
                   {"subject": "New", "customer": str(setup["b"].linked_record_id)},
                   format="json")
        assert r.status_code == 201
        # the spoofed customer is overwritten with A's linked record
        assert r.data["customer"] == str(setup["a"].linked_record_id)

    def test_ungranted_entity_denied(self, setup):
        ws = setup["ws"]
        SchemaRegistryService.create_entity(
            workspace_id=ws.id, slug="secret", name="Secret", plural_name="Secrets")
        c = _portal_client(setup["a"])
        assert c.get(f"{BASE}/secret/").status_code == 403   # no grant

    def test_portal_type_gating(self, setup):
        # a grant only for portal_type="vendor" must not apply to a customer user
        ws = setup["ws"]
        SchemaRegistryService.create_entity(
            workspace_id=ws.id, slug="po", name="PO", plural_name="POs")
        SchemaRegistryService.add_field(workspace_id=ws.id, entity_slug="po", slug="vendor",
                                        name="Vendor", field_type="text", is_promoted=True)
        PortalEntityGrant.objects.create(workspace_id=ws.id, entity_slug="po",
                                         portal_type="vendor", link_field="vendor", can_read=True)
        c = _portal_client(setup["a"])   # a customer
        assert c.get(f"{BASE}/po/").status_code == 403

    def test_unlinked_user_sees_nothing(self, setup):
        setup["a"].linked_record_id = None
        setup["a"].save(update_fields=["linked_record_id"])
        c = _portal_client(setup["a"])
        assert c.get(f"{BASE}/ticket/").data["results"] == []


@pytest.mark.django_db
def test_indirect_scope_matches_via_linked_record_field(db):
    """Phase P3.1A: a grant with ``link_source`` scopes rows by a VALUE on the portal user's own
    linked record (one hop through a parent) — reusable group-membership scoping. A portal user
    linked to a member in team T1 sees only T1 resources, never T2, and cannot spoof it."""
    from apps.portal.data_services import PortalDataService
    ws = Workspace.objects.create(name="Ind", slug="ind", is_active=True)
    admin = User.objects.create_user(email="a@ind.com", password="Sup3rStr0ng!pw", is_verified=True)
    member = WorkspaceMember.objects.create(workspace=ws, user=admin, role="admin", status="active")

    subj = SchemaRegistryService.create_entity(
        workspace_id=ws.id, slug="member", name="Member", plural_name="Members")
    SchemaRegistryService.add_field(workspace_id=ws.id, entity_slug="member", slug="team",
                                    name="Team", field_type="text", is_promoted=True)
    res = SchemaRegistryService.create_entity(
        workspace_id=ws.id, slug="resource", name="Resource", plural_name="Resources")
    SchemaRegistryService.add_field(workspace_id=ws.id, entity_slug="resource", slug="team",
                                    name="Team", field_type="text", is_promoted=True)
    subj.refresh_from_db()
    res.refresh_from_db()

    m1 = RecordService.create_record(workspace_id=ws.id, member=member, entity=subj,
                                     data={"team": "T1"})
    RecordService.create_record(workspace_id=ws.id, member=member, entity=res, data={"team": "T1"})
    RecordService.create_record(workspace_id=ws.id, member=member, entity=res, data={"team": "T2"})

    PortalEntityGrant.objects.create(
        workspace_id=ws.id, entity_slug="resource", portal_type="member",
        link_field="team", link_source="team", can_read=True)
    pu = PortalUser.objects.create(
        workspace_id=ws.id, email="m@ind.com", full_name="M", password_hash=make_password(PW),
        is_active=True, is_verified=True, linked_entity_id=subj.id, linked_record_id=m1["id"],
        portal_type="member")

    rows = PortalDataService.list_records(pu, "resource")
    assert {r["team"] for r in rows} == {"T1"}   # only the member's team; T2 never leaks
