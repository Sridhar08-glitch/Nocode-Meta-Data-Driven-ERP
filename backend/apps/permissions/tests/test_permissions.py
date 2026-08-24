"""RBAC + ABAC + masking engine tests."""
import uuid

import pytest

from apps.metadata.models import EntityDefinition
from apps.permissions import services as perm
from apps.permissions.models import DataMaskingRule, FieldPermission, Permission, Role
from apps.schema_registry.services import SchemaRegistryService


class Member:
    """Lightweight WorkspaceMember stand-in (the engine only reads these attrs)."""
    def __init__(self, role="member", custom_role_id=None, user_id=None):
        self.role = role
        self.custom_role_id = custom_role_id
        self.user_id = user_id or uuid.uuid4()
        self.id = uuid.uuid4()


@pytest.fixture
def ws():
    return uuid.uuid4()


@pytest.fixture
def entity(db, ws):
    return EntityDefinition.objects.create(workspace_id=ws, slug="lead", name="Lead", plural_name="Leads")


@pytest.mark.django_db
class TestRBAC:
    def test_system_roles(self, entity):
        assert perm.check(Member(role="owner"), entity, "delete")
        assert perm.check(Member(role="admin"), entity, "import")
        assert perm.check(Member(role="member"), entity, "create")
        assert not perm.check(Member(role="viewer"), entity, "create")
        assert perm.check(Member(role="viewer"), entity, "read")

    def test_custom_allow_grants(self, entity, ws):
        role = Role.objects.create(workspace_id=ws, name="Auditor", slug="auditor")
        Permission.objects.create(role=role, workspace_id=ws, resource_type="entity",
                                  resource_id=entity.id, action="export")
        m = Member(role="viewer", custom_role_id=role.id)
        assert perm.check(m, entity, "export")     # custom grant beyond viewer base

    def test_explicit_deny_wins(self, entity, ws):
        role = Role.objects.create(workspace_id=ws, name="Limited", slug="limited")
        Permission.objects.create(role=role, workspace_id=ws, resource_type="entity",
                                  resource_id=entity.id, action="delete", is_deny=True)
        m = Member(role="admin", custom_role_id=role.id)   # admin base allows delete...
        assert not perm.check(m, entity, "delete")          # ...but explicit deny wins

    def test_parent_role_inheritance(self, entity, ws):
        parent = Role.objects.create(workspace_id=ws, name="Base", slug="base")
        Permission.objects.create(role=parent, workspace_id=ws, resource_type="entity",
                                  resource_id=entity.id, action="export")
        child = Role.objects.create(workspace_id=ws, name="Child", slug="child", parent_role=parent)
        m = Member(role="viewer", custom_role_id=child.id)
        assert perm.check(m, entity, "export")              # inherited from parent


@pytest.mark.django_db
class TestABAC:
    def test_record_condition(self, entity, ws):
        role = Role.objects.create(workspace_id=ws, name="OwnOnly", slug="ownonly")
        Permission.objects.create(role=role, workspace_id=ws, resource_type="entity",
                                  resource_id=entity.id, action="read",
                                  conditions=[{"field": "owner", "op": "=", "value": "$user.id"}])
        me = uuid.uuid4()
        m = Member(role="member", custom_role_id=role.id, user_id=me)
        assert perm.check_record(m, entity, "read", {"owner": str(me)})
        assert not perm.check_record(m, entity, "read", {"owner": str(uuid.uuid4())})

    def test_list_conditions_injected(self, entity, ws):
        role = Role.objects.create(workspace_id=ws, name="OwnOnly", slug="ownonly2")
        Permission.objects.create(role=role, workspace_id=ws, resource_type="entity",
                                  resource_id=entity.id, action="read",
                                  conditions=[{"field": "owner", "op": "=", "value": "$user.id"}])
        me = uuid.uuid4()
        m = Member(role="member", custom_role_id=role.id, user_id=me)
        cond = perm.abac_list_conditions(m, entity, "read")
        assert cond["op"] == "or"
        assert cond["conditions"][0]["conditions"][0]["value"] == str(me)

    def test_no_custom_role_unrestricted(self, entity):
        assert perm.abac_list_conditions(Member(role="member"), entity, "read") is None


@pytest.mark.django_db
class TestMasking:
    def test_drop_and_mask(self, ws):
        ent = SchemaRegistryService.create_entity(
            workspace_id=ws, slug="cust", name="Cust", plural_name="Custs")
        SchemaRegistryService.add_field(workspace_id=ws, entity_slug="cust",
                                        slug="ssn", name="SSN", field_type="text", is_promoted=True)
        SchemaRegistryService.add_field(workspace_id=ws, entity_slug="cust",
                                        slug="secret", name="Secret", field_type="text", is_promoted=True)
        ssn = ent.fields.get(slug="ssn")
        secret = ent.fields.get(slug="secret")
        role = Role.objects.create(workspace_id=ws, name="Agent", slug="agent")
        DataMaskingRule.objects.create(workspace_id=ws, field_id=ssn.id, role_id=role.id,
                                       mask_type="full", mask_pattern="")
        FieldPermission.objects.create(workspace_id=ws, field_id=secret.id, role_id=role.id,
                                       can_read=False, can_write=False)
        m = Member(role="member", custom_role_id=role.id)
        out = perm.mask_record(m, ent, {"ssn": "123456789", "secret": "x", "name": "ok"})
        assert out["ssn"].startswith("*") and out["ssn"] != "123456789"
        assert "secret" not in out          # dropped (not readable)
        assert out["name"] == "ok"

    def test_admin_not_masked(self, ws):
        ent = SchemaRegistryService.create_entity(
            workspace_id=ws, slug="c2", name="C2", plural_name="C2s")
        out = perm.mask_record(Member(role="admin"), ent, {"ssn": "123"})
        assert out["ssn"] == "123"
