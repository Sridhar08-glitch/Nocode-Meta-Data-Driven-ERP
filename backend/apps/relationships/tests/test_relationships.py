"""End-to-end tests for the relationship builder (/api/v1/relationships/)."""
import uuid

import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.metadata.models import FieldDefinition
from apps.relationships.models import RecordRelationship, RelationshipDefinition
from apps.schema_registry.services import SchemaRegistryService
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"
BASE = "/api/v1/relationships/"


@pytest.fixture
def user(db):
    return User.objects.create_user(email="rel@example.com", password=PW, is_verified=True)


@pytest.fixture
def workspace(db):
    return Workspace.objects.create(name="Acme", slug="acme", is_active=True)


@pytest.fixture
def client(user, workspace):
    WorkspaceMember.objects.create(workspace=workspace, user=user, role="admin", status="active")
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}",
                  HTTP_X_WORKSPACE_SLUG=workspace.slug)
    return c


@pytest.fixture
def entities(workspace):
    account = SchemaRegistryService.create_entity(
        workspace_id=workspace.id, slug="account", name="Account", plural_name="Accounts")
    contact = SchemaRegistryService.create_entity(
        workspace_id=workspace.id, slug="contact", name="Contact", plural_name="Contacts")
    return account, contact


@pytest.mark.django_db
class TestRelationshipBuilder:
    def test_one_to_many_provisions_fk_on_target(self, client, entities, workspace):
        account, contact = entities
        r = client.post(BASE, {
            "name": "Account Contacts", "slug": "account_contacts",
            "source_entity_id": str(account.id), "target_entity_id": str(contact.id),
            "cardinality": "one_to_many",
        }, format="json")
        assert r.status_code == 201
        # FK lookup column lands on the "many" side (contact), promoted.
        fd = FieldDefinition.objects.get(entity=contact, slug="account_ref")
        assert fd.is_promoted and fd.field_type == "lookup" and fd.column_name
        assert r.data["target_field_slug"] == "account_ref"

    def test_one_to_one_unique_fk_on_source(self, client, entities):
        account, contact = entities
        r = client.post(BASE, {
            "name": "Primary Contact", "slug": "primary_contact",
            "source_entity_id": str(account.id), "target_entity_id": str(contact.id),
            "cardinality": "one_to_one",
        }, format="json")
        assert r.status_code == 201
        fd = FieldDefinition.objects.get(entity=account, slug="contact_ref")
        assert fd.is_promoted and fd.field_type == "lookup"
        # DB-level UNIQUE is applied on PostgreSQL only (SQLite can't ALTER ADD UNIQUE).
        from django.db import connection
        if connection.vendor == "postgresql":
            assert fd.is_unique

    def test_self_ref_fk_on_same_entity(self, client, entities):
        account, _ = entities
        r = client.post(BASE, {
            "name": "Parent Account", "slug": "parent_account",
            "source_entity_id": str(account.id), "target_entity_id": str(account.id),
            "cardinality": "self_ref",
        }, format="json")
        assert r.status_code == 201
        assert r.data["source_field_slug"] == "parent_ref"
        fd = FieldDefinition.objects.get(entity=account, slug="parent_ref")
        assert fd.is_promoted and fd.field_type == "lookup"

    def test_many_to_many_no_column(self, client, entities, workspace):
        account, contact = entities
        r = client.post(BASE, {
            "name": "Related", "slug": "related",
            "source_entity_id": str(account.id), "target_entity_id": str(contact.id),
            "cardinality": "many_to_many",
        }, format="json")
        assert r.status_code == 201
        assert not FieldDefinition.objects.filter(entity=account, field_type="lookup").exists()
        assert RelationshipDefinition.objects.filter(
            workspace_id=workspace.id, slug="related").exists()

    def test_list_and_get_and_delete(self, client, entities, workspace):
        account, contact = entities
        created = client.post(BASE, {
            "name": "Account Contacts", "slug": "account_contacts",
            "source_entity_id": str(account.id), "target_entity_id": str(contact.id),
            "cardinality": "one_to_many"}, format="json").data
        rid = created["id"]
        assert any(r["id"] == rid for r in client.get(BASE).data)
        assert client.get(f"{BASE}{rid}/").status_code == 200
        # delete removes the provisioned FK field
        assert client.delete(f"{BASE}{rid}/").status_code == 204
        assert not FieldDefinition.objects.filter(entity=contact, slug="account_ref").exists()

    def test_m2m_link_unlink(self, client, entities, workspace):
        account, contact = entities
        rid = client.post(BASE, {
            "name": "Related", "slug": "related",
            "source_entity_id": str(account.id), "target_entity_id": str(contact.id),
            "cardinality": "many_to_many"}, format="json").data["id"]
        a_rec, c_rec = uuid.uuid4(), uuid.uuid4()
        link = client.post(f"{BASE}{rid}/links/",
                           {"source_record_id": str(a_rec), "target_record_id": str(c_rec)}, format="json")
        assert link.status_code == 201
        assert RecordRelationship.objects.filter(workspace_id=workspace.id, definition_id=rid).count() == 1
        unlink = client.delete(f"{BASE}{rid}/links/",
                               {"source_record_id": str(a_rec), "target_record_id": str(c_rec)}, format="json")
        assert unlink.status_code == 200 and unlink.data["removed"] == 1

    def test_invalid_cardinality_rejected(self, client, entities):
        account, contact = entities
        r = client.post(BASE, {
            "name": "X", "slug": "x", "source_entity_id": str(account.id),
            "target_entity_id": str(contact.id), "cardinality": "bogus"}, format="json")
        assert r.status_code == 400

    def test_duplicate_slug_rejected(self, client, entities):
        account, contact = entities
        body = {"name": "Rel", "slug": "rel", "source_entity_id": str(account.id),
                "target_entity_id": str(contact.id), "cardinality": "many_to_many"}
        assert client.post(BASE, body, format="json").status_code == 201
        assert client.post(BASE, body, format="json").status_code == 400

    def test_requires_workspace_membership(self, user, workspace, entities):
        c = APIClient()  # not a member
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}",
                      HTTP_X_WORKSPACE_SLUG=workspace.slug)
        assert c.get(BASE).status_code == 403
