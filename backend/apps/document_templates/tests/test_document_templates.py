"""Document/PDF templates (Phase 1.33) — render bound record + line items, CRUD, isolation."""
import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.document_templates.models import DocumentTemplate
from apps.document_templates.services import render as render_template
from apps.records.services import RecordService
from apps.schema_registry.services import SchemaRegistryService
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"
BASE = "/api/v1/templates/documents"


@pytest.fixture
def ws(db):
    return Workspace.objects.create(name="Acme", slug="acme", is_active=True)


@pytest.fixture
def member(ws):
    user = User.objects.create_user(email="a@acme.com", password=PW, is_verified=True)
    return WorkspaceMember.objects.create(workspace=ws, user=user, role="admin", status="active")


@pytest.fixture
def client(ws, member):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(member.user)}",
                  HTTP_X_WORKSPACE_SLUG=ws.slug)
    return c


@pytest.fixture
def invoice_data(ws, member):
    """An invoice with two line items in a related entity."""
    inv = SchemaRegistryService.create_entity(
        workspace_id=ws.id, slug="invoice", name="Invoice", plural_name="Invoices")
    SchemaRegistryService.add_field(workspace_id=ws.id, entity_slug="invoice", slug="customer",
                                    name="Customer", field_type="text", is_promoted=True)
    line = SchemaRegistryService.create_entity(
        workspace_id=ws.id, slug="invoice_line", name="Invoice Line", plural_name="Invoice Lines")
    for slug, ftype in [("product", "text"), ("amount", "decimal"), ("invoice", "text")]:
        SchemaRegistryService.add_field(workspace_id=ws.id, entity_slug="invoice_line", slug=slug,
                                        name=slug.title(), field_type=ftype, is_promoted=True)
    inv.refresh_from_db()
    line.refresh_from_db()
    inv_rec = RecordService.create_record(workspace_id=ws.id, member=member, entity=inv,
                                          data={"customer": "Globex"})
    for product, amount in [("Widget", 10), ("Gadget", 20)]:
        RecordService.create_record(workspace_id=ws.id, member=member, entity=line,
                                    data={"product": product, "amount": amount,
                                          "invoice": str(inv_rec["id"])})
    return {"invoice_id": inv_rec["id"]}


def _make_template(ws):
    return DocumentTemplate.objects.create(
        workspace_id=ws.id, name="Invoice PDF", slug="invoice-pdf", entity_slug="invoice",
        page_config={"title": "Invoice", "subtitle": "Thank you"},
        blocks=[{"field": "customer", "label": "Customer"}],
        line_items={"entity_slug": "invoice_line", "relation_field": "invoice",
                    "columns": [{"key": "product", "label": "Product"},
                                {"key": "amount", "label": "Amount"}]})


@pytest.mark.django_db
class TestDocumentTemplates:
    def test_render_service_returns_pdf(self, ws, member, invoice_data):
        tpl = _make_template(ws)
        pdf = render_template(tpl, workspace_id=ws.id,
                              record_id=invoice_data["invoice_id"], member=member)
        assert pdf[:5] == b"%PDF-"

    def test_render_endpoint(self, client, ws, invoice_data):
        tpl = _make_template(ws)
        r = client.get(f"{BASE}/{tpl.id}/render/?record_id={invoice_data['invoice_id']}")
        assert r.status_code == 200
        assert r["Content-Type"] == "application/pdf"
        assert r.content[:5] == b"%PDF-"

    def test_render_requires_record_id(self, client, ws, invoice_data):
        tpl = _make_template(ws)
        assert client.get(f"{BASE}/{tpl.id}/render/").status_code == 400

    def test_crud_and_version_bump(self, client):
        cr = client.post(f"{BASE}/", {"name": "T", "slug": "t", "entity_slug": "invoice"},
                         format="json")
        assert cr.status_code == 201
        tid = cr.data["id"]
        assert DocumentTemplate.objects.get(id=tid).version == 1
        client.patch(f"{BASE}/{tid}/", {"page_config": {"title": "New"}}, format="json")
        assert DocumentTemplate.objects.get(id=tid).version == 2

    def test_duplicate_slug_rejected(self, client):
        client.post(f"{BASE}/", {"name": "A", "slug": "dup", "entity_slug": "x"}, format="json")
        r = client.post(f"{BASE}/", {"name": "B", "slug": "dup", "entity_slug": "x"}, format="json")
        assert r.status_code == 400

    def test_member_cannot_edit(self, ws, member):
        viewer = User.objects.create_user(email="v@acme.com", password=PW, is_verified=True)
        WorkspaceMember.objects.create(workspace=ws, user=viewer, role="member", status="active")
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(viewer)}",
                      HTTP_X_WORKSPACE_SLUG=ws.slug)
        assert c.post(f"{BASE}/", {"name": "X", "slug": "x", "entity_slug": "y"},
                      format="json").status_code == 403

    def test_cross_workspace_isolation(self, client, ws):
        tid = client.post(f"{BASE}/", {"name": "T", "slug": "secret", "entity_slug": "x"},
                          format="json").data["id"]
        other = Workspace.objects.create(name="Other", slug="other", is_active=True)
        ou = User.objects.create_user(email="o@other.com", password=PW, is_verified=True)
        WorkspaceMember.objects.create(workspace=other, user=ou, role="admin", status="active")
        oc = APIClient()
        oc.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(ou)}",
                       HTTP_X_WORKSPACE_SLUG=other.slug)
        assert oc.get(f"{BASE}/{tid}/").status_code == 404
