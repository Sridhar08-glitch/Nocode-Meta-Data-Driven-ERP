"""
Dashboard API + PDF export (Phase 1.31). Reuses the shared reporting conftest
(ws / user / member / lead / leads / make_report / client).
"""
import pytest

from apps.reporting.models import Dashboard, DashboardWidget
from apps.reporting.services import DashboardService, ReportService
from apps.tenancy.models import Workspace

from .conftest import make_client

BASE_R = "/api/v1/reports"
BASE_D = "/api/v1/dashboards"


# ── PDF export ────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestReportPdf:
    def test_service_returns_pdf_bytes(self, ws, leads, make_report):
        pdf = ReportService.export_to_pdf(make_report(), ws.id)
        assert pdf[:5] == b"%PDF-"

    def test_export_pdf_endpoint(self, client, leads, make_report):
        report = make_report()
        r = client.get(f"{BASE_R}/{report.id}/export/pdf/")
        assert r.status_code == 200
        assert r["Content-Type"] == "application/pdf"
        assert r.content[:5] == b"%PDF-"

    def test_pdf_with_branding_watermark(self, ws, leads, make_report):
        from apps.branding.models import WorkspaceBranding
        WorkspaceBranding.objects.create(workspace_id=ws.id, app_name="Acme Inc")
        pdf = ReportService.export_to_pdf(make_report(), ws.id)
        assert pdf[:5] == b"%PDF-"


# ── Dashboard CRUD + run ──────────────────────────────────────────────────────
@pytest.mark.django_db
class TestDashboardApi:
    def test_crud(self, client):
        cr = client.post(f"{BASE_D}/", {"name": "Sales", "slug": "sales"}, format="json")
        assert cr.status_code == 201
        did = cr.data["id"]
        assert client.get(f"{BASE_D}/").data["count"] == 1
        pr = client.patch(f"{BASE_D}/{did}/", {"name": "Sales v2"}, format="json")
        assert pr.status_code == 200 and pr.data["name"] == "Sales v2"
        assert client.delete(f"{BASE_D}/{did}/").status_code == 204

    def test_duplicate_slug_rejected(self, client):
        client.post(f"{BASE_D}/", {"name": "A", "slug": "dup"}, format="json")
        r = client.post(f"{BASE_D}/", {"name": "B", "slug": "dup"}, format="json")
        assert r.status_code == 400

    def test_widget_crud(self, client, leads, make_report):
        report = make_report()
        did = client.post(f"{BASE_D}/", {"name": "D", "slug": "d"}, format="json").data["id"]
        wc = client.post(f"{BASE_D}/{did}/widgets/",
                         {"widget_type": "report", "title": "Leads", "report_id": str(report.id)},
                         format="json")
        assert wc.status_code == 201
        assert len(client.get(f"{BASE_D}/{did}/widgets/").data) == 1
        wid = wc.data["id"]
        assert client.delete(f"{BASE_D}/{did}/widgets/{wid}/").status_code == 204

    def test_run_resolves_report_widget(self, client, ws, leads, make_report):
        report = make_report()
        dash = Dashboard.objects.create(workspace_id=ws.id, name="D", slug="d")
        DashboardWidget.objects.create(workspace_id=ws.id, dashboard_id=dash.id,
                                       widget_type="report", title="Leads", report_id=report.id)
        r = client.post(f"{BASE_D}/{dash.id}/run/", {}, format="json")
        assert r.status_code == 200
        widget = r.data["widgets"][0]
        assert widget["widget_type"] == "report"
        assert widget["result"]["total_count"] == 3

    def test_run_static_widget_echoes_config(self, client, ws):
        dash = Dashboard.objects.create(workspace_id=ws.id, name="D", slug="d")
        DashboardWidget.objects.create(workspace_id=ws.id, dashboard_id=dash.id,
                                       widget_type="text", title="Notes",
                                       config={"markdown": "hello"})
        r = client.post(f"{BASE_D}/{dash.id}/run/", {}, format="json")
        assert r.data["widgets"][0]["config"]["markdown"] == "hello"

    def test_dashboard_pdf_export(self, client, ws, leads, make_report):
        report = make_report()
        dash = Dashboard.objects.create(workspace_id=ws.id, name="D", slug="d")
        DashboardWidget.objects.create(workspace_id=ws.id, dashboard_id=dash.id,
                                       widget_type="report", title="Leads", report_id=report.id)
        r = client.get(f"{BASE_D}/{dash.id}/export/pdf/")
        assert r.status_code == 200 and r.content[:5] == b"%PDF-"

    def test_run_service_isolates_bad_widget(self, ws, leads, make_report):
        import uuid
        dash = Dashboard.objects.create(workspace_id=ws.id, name="D", slug="d")
        DashboardWidget.objects.create(workspace_id=ws.id, dashboard_id=dash.id,
                                       widget_type="report", report_id=uuid.uuid4())  # missing report
        out = DashboardService.run(dash, ws.id)
        assert out["widgets"][0]["error"] == "report not found"

    def test_viewer_cannot_create(self, ws):
        _, viewer = make_client(ws, "viewer@acme.com", role="viewer")
        r = viewer.post(f"{BASE_D}/", {"name": "X", "slug": "x"}, format="json")
        assert r.status_code == 403

    def test_cross_workspace_isolation(self, client, ws):
        did = client.post(f"{BASE_D}/", {"name": "Secret", "slug": "secret"},
                          format="json").data["id"]
        other = Workspace.objects.create(name="Other", slug="other", is_active=True)
        _, oc = make_client(other, "o@other.com", role="admin")
        assert oc.get(f"{BASE_D}/{did}/").status_code == 404
        assert oc.get(f"{BASE_D}/").data["count"] == 0
