"""
NQL engine v1 tests — parser, compiler (parameterized SQL), and live execution
against a generated physical table, on whichever DB the suite runs (SQLite/PG).
"""
import json
import uuid

import pytest
from django.db import connection

from apps.nql.compiler import NQLResult
from apps.nql.exceptions import UnknownFieldError
from apps.nql.parser import parse_nql_text
from apps.nql.services import compile_nql, execute_nql
from apps.schema_registry.services import SchemaRegistryService

WS = None


def _add(entity_slug, ws, slug, ftype, promoted):
    SchemaRegistryService.add_field(
        workspace_id=ws, entity_slug=entity_slug, slug=slug, name=slug.title(),
        field_type=ftype, is_promoted=promoted)


@pytest.fixture
def ws(db):
    return uuid.uuid4()


@pytest.fixture
def lead(ws):
    ent = SchemaRegistryService.create_entity(
        workspace_id=ws, slug="lead", name="Lead", plural_name="Leads")
    _add("lead", ws, "status", "text", True)        # promoted column
    _add("lead", ws, "value", "decimal", True)      # promoted numeric column
    _add("lead", ws, "owner", "user", True)         # promoted uuid column
    _add("lead", ws, "source", "text", False)       # JSONB overflow
    ent.refresh_from_db()
    return ent


def _insert(table, ws, *, status=None, value=None, owner=None, source=None):
    pg = connection.vendor == "postgresql"
    uid = "%s::uuid" if pg else "%s"
    cols = ["id", "workspace_id", "status", "value", "owner", "custom_data"]
    phs = [uid, uid, "%s", "%s", (uid if owner else "%s"),
           ("%s::jsonb" if pg else "%s")]
    custom = {"source": source} if source is not None else {}
    params = [str(uuid.uuid4()), str(ws), status, value,
              (str(owner) if owner else None), json.dumps(custom)]
    with connection.cursor() as cur:
        cur.execute(f'INSERT INTO "{table}" ({", ".join(cols)}) VALUES ({", ".join(phs)})', params)


@pytest.mark.django_db
class TestParser:
    def test_text_to_ast(self):
        q = parse_nql_text('SELECT name, value FROM lead WHERE status = "open" OR value < 10 LIMIT 5')
        assert q.entity == "lead" and q.select == ["name", "value"] and q.limit == 5
        assert q.filter.op == "or"

    def test_in_and_contains_and_null(self):
        q = parse_nql_text('FROM lead WHERE status IN ("open", "won") AND name CONTAINS "ac" '
                           'AND source IS NULL')
        ops = {c.op for c in q.filter.conditions}
        assert {"in", "contains", "is null"} <= ops


@pytest.mark.django_db
class TestCompiler:
    def test_parameterized_never_interpolates(self, ws, lead):
        evil = "o'; DROP TABLE lead;--"
        res = compile_nql(workspace_id=ws, source={
            "entity": "lead",
            "filter": {"op": "and", "conditions": [{"field": "status", "op": "=", "value": evil}]}})
        assert isinstance(res, NQLResult)
        assert "DROP TABLE" not in res.sql
        assert evil in res.params

    def test_unknown_field_rejected(self, ws, lead):
        with pytest.raises(UnknownFieldError):
            compile_nql(workspace_id=ws, source={
                "entity": "lead",
                "filter": {"op": "and", "conditions": [{"field": "nope", "op": "=", "value": 1}]}})

    def test_limit_capped(self, ws, lead):
        res = compile_nql(workspace_id=ws, source={"entity": "lead", "limit": 10_000_000})
        assert res.limit == 10000  # NEXUS_NQL_MAX_LIMIT

    def test_jsonb_vs_promoted_resolution(self, ws, lead):
        res = compile_nql(workspace_id=ws, source={"entity": "lead", "select": ["status", "source"]})
        # promoted column referenced directly; overflow field via custom_data path
        assert '"status"' in res.sql
        assert "custom_data" in res.sql


@pytest.mark.django_db
class TestExecution:
    def test_filter_and_sort(self, ws, lead):
        t = lead.table_name
        _insert(t, ws, status="open", value=500)
        _insert(t, ws, status="open", value=1500)
        _insert(t, ws, status="won", value=3000)
        rows = execute_nql(workspace_id=ws, source={
            "entity": "lead",
            "filter": {"op": "and", "conditions": [{"field": "value", "op": ">=", "value": 1000}]},
            "sort": [{"field": "value", "direction": "desc"}]})
        assert [int(r["value"]) for r in rows] == [3000, 1500]

    def test_text_surface_execution(self, ws, lead):
        t = lead.table_name
        _insert(t, ws, status="open", value=10)
        _insert(t, ws, status="closed", value=20)
        rows = execute_nql(workspace_id=ws, source='FROM lead WHERE status = "open"')
        assert len(rows) == 1 and rows[0]["status"] == "open"

    def test_jsonb_overflow_filter(self, ws, lead):
        t = lead.table_name
        _insert(t, ws, status="open", value=1, source="web")
        _insert(t, ws, status="open", value=1, source="referral")
        rows = execute_nql(workspace_id=ws, source={
            "entity": "lead",
            "filter": {"op": "and", "conditions": [{"field": "source", "op": "=", "value": "web"}]}})
        assert len(rows) == 1

    def test_in_contains_isnull(self, ws, lead):
        t = lead.table_name
        _insert(t, ws, status="open", value=1, source="web")
        _insert(t, ws, status="won", value=1)
        assert len(execute_nql(workspace_id=ws, source={
            "entity": "lead",
            "filter": {"op": "and", "conditions": [{"field": "status", "op": "in",
                                                    "value": ["open", "won"]}]}})) == 2
        assert len(execute_nql(workspace_id=ws, source={
            "entity": "lead",
            "filter": {"op": "and", "conditions": [{"field": "source", "op": "is null"}]}})) == 1

    def test_me_magic(self, ws, lead):
        t = lead.table_name
        me = uuid.uuid4()
        _insert(t, ws, status="open", value=1, owner=me)
        _insert(t, ws, status="open", value=1, owner=uuid.uuid4())
        rows = execute_nql(workspace_id=ws, user_id=me, source={
            "entity": "lead",
            "filter": {"op": "and", "conditions": [{"field": "owner", "op": "=", "value": "@me"}]}})
        assert len(rows) == 1

    def test_aggregation_group_by(self, ws, lead):
        t = lead.table_name
        _insert(t, ws, status="open", value=100)
        _insert(t, ws, status="open", value=200)
        _insert(t, ws, status="won", value=50)
        rows = execute_nql(workspace_id=ws, source={
            "entity": "lead",
            "aggregations": [{"func": "count"}, {"func": "sum", "field": "value", "alias": "total"}],
            "groupBy": ["status"]})
        by = {r["status"]: r for r in rows}
        assert int(by["open"]["total"]) == 300
        assert int(by["won"]["count_all"]) == 1

    def test_workspace_isolation(self, ws, lead):
        t = lead.table_name
        _insert(t, ws, status="open", value=1)
        _insert(t, uuid.uuid4(), status="open", value=1)   # different workspace
        rows = execute_nql(workspace_id=ws, source={"entity": "lead"})
        assert len(rows) == 1


@pytest.mark.django_db
class TestApiEndpoint:
    def test_query_endpoint_full_stack(self):
        from rest_framework.test import APIClient

        from apps.accounts import tokens
        from apps.accounts.models import User
        from apps.tenancy.models import Workspace, WorkspaceMember

        user = User.objects.create_user(email="nql@example.com", password="Sup3rStr0ng!pw", is_verified=True)
        wsp = Workspace.objects.create(name="Acme", slug="acme", is_active=True)
        WorkspaceMember.objects.create(workspace=wsp, user=user, role="admin", status="active")
        ent = SchemaRegistryService.create_entity(
            workspace_id=wsp.id, slug="lead", name="Lead", plural_name="Leads")
        _add("lead", wsp.id, "status", "text", True)
        _add("lead", wsp.id, "value", "decimal", True)
        _add("lead", wsp.id, "owner", "user", True)
        _add("lead", wsp.id, "source", "text", False)
        ent.refresh_from_db()
        _insert(ent.table_name, wsp.id, status="open", value=42)

        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}",
                      HTTP_X_WORKSPACE_SLUG="acme")
        r = c.post("/api/v1/nql/query/", {
            "entity": "lead",
            "filter": {"op": "and", "conditions": [{"field": "status", "op": "=", "value": "open"}]},
        }, format="json")
        assert r.status_code == 200
        assert r.data["count"] == 1 and int(r.data["rows"][0]["value"]) == 42

    def test_text_surface_endpoint(self):
        from rest_framework.test import APIClient

        from apps.accounts import tokens
        from apps.accounts.models import User
        from apps.tenancy.models import Workspace, WorkspaceMember

        user = User.objects.create_user(email="nql2@example.com", password="Sup3rStr0ng!pw", is_verified=True)
        wsp = Workspace.objects.create(name="Beta", slug="beta", is_active=True)
        WorkspaceMember.objects.create(workspace=wsp, user=user, role="admin", status="active")
        ent = SchemaRegistryService.create_entity(
            workspace_id=wsp.id, slug="lead", name="Lead", plural_name="Leads")
        _add("lead", wsp.id, "status", "text", True)
        _add("lead", wsp.id, "value", "decimal", True)
        _add("lead", wsp.id, "owner", "user", True)
        _add("lead", wsp.id, "source", "text", False)
        ent.refresh_from_db()
        _insert(ent.table_name, wsp.id, status="open", value=7)

        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}",
                      HTTP_X_WORKSPACE_SLUG="beta")
        r = c.post("/api/v1/nql/query/", {"text": 'FROM lead WHERE status = "open"'}, format="json")
        assert r.status_code == 200 and r.data["count"] == 1
