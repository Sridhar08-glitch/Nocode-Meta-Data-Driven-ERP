"""Reporting REST API (PROJECT_HANDBOOK.md §25.3 / §25.4)."""
import pytest

from apps.tenancy.models import Workspace

from .conftest import make_client

BASE = "/api/v1/reports"


@pytest.mark.django_db
class TestReportApi:
    def test_crud(self, client):
        r = client.post(f"{BASE}/", {"name": "R", "slug": "r", "report_type": "table",
                                     "nql_ast": {"entity": "lead"}}, format="json")
        assert r.status_code == 201, r.content
        rid = r.json()["id"]
        assert client.get(f"{BASE}/").json()["count"] == 1
        assert client.patch(f"{BASE}/{rid}/", {"description": "d"},
                            format="json").json()["description"] == "d"
        assert client.delete(f"{BASE}/{rid}/").status_code == 204

    def test_run(self, client, leads, make_report):
        report = make_report()
        body = client.post(f"{BASE}/{report.id}/run/").json()
        assert body["total_count"] == 3

    def test_run_pivot(self, client, leads, make_report):
        report = make_report(report_type="pivot", display_config={
            "row_field": "status", "value_field": "value", "agg": "sum"})
        body = client.post(f"{BASE}/{report.id}/run/").json()
        assert "matrix" in body

    def test_snapshot_flow(self, client, leads, make_report):
        report = make_report()
        snap = client.post(f"{BASE}/{report.id}/snapshot/")
        assert snap.status_code == 201
        sid = snap.json()["id"]
        assert client.get(f"{BASE}/{report.id}/snapshots/").json()["count"] == 1
        assert client.get(f"{BASE}/{report.id}/snapshots/{sid}/").json()["row_count"] == 3

    def test_export_csv_and_xlsx(self, client, leads, make_report):
        report = make_report()
        csv_resp = client.get(f"{BASE}/{report.id}/export/csv/")
        assert csv_resp.status_code == 200
        assert csv_resp["Content-Type"] == "text/csv"
        xlsx_resp = client.get(f"{BASE}/{report.id}/export/xlsx/")
        assert xlsx_resp.status_code == 200
        assert "spreadsheetml" in xlsx_resp["Content-Type"]

    def test_validate_nql(self, client):
        ok = client.post(f"{BASE}/validate-nql/",
                         {"nql_source": "FROM lead WHERE value > 1"}, format="json").json()
        assert ok["valid"] is True
        bad = client.post(f"{BASE}/validate-nql/",
                          {"nql_source": "FROM lead WHERE (("}, format="json").json()
        assert bad["valid"] is False and bad["errors"]


@pytest.mark.django_db
class TestAuthz:
    def test_viewer_cannot_create(self, ws):
        _, c = make_client(ws, "v@acme.com", role="viewer")
        r = c.post(f"{BASE}/", {"name": "R", "slug": "r", "nql_ast": {"entity": "lead"}},
                   format="json")
        assert r.status_code == 403

    def test_cross_workspace_cannot_run(self, ws, leads, make_report):
        report = make_report()
        other = Workspace.objects.create(name="Other", slug="other", is_active=True)
        _, c2 = make_client(other, "x@other.com", role="admin")
        assert c2.post(f"{BASE}/{report.id}/run/").status_code == 404
