"""Import/Export REST API (PROJECT_HANDBOOK.md §29.3 / §29.4)."""
import pytest

from apps.tenancy.models import Workspace

from .conftest import csv_file, make_client

IMP = "/api/v1/import"
EXP = "/api/v1/export"


@pytest.mark.django_db
class TestImportApi:
    def test_upload_preview_confirm(self, ws, member, lead, client):
        r = client.post(f"{IMP}/jobs/",
                        {"entity_slug": "lead", "file": csv_file("name,value\nA,1\nB,2\n")},
                        format="multipart")
        assert r.status_code == 201, r.content
        jid = r.json()["id"]
        assert r.json()["status"] == "awaiting_confirm"
        assert len(client.get(f"{IMP}/jobs/{jid}/preview/").json()["results"]) == 2
        assert client.post(f"{IMP}/jobs/{jid}/confirm/").json()["status"] == "completed"

    def test_mapping_endpoint(self, ws, member, lead, client):
        jid = client.post(f"{IMP}/jobs/",
                          {"entity_slug": "lead", "file": csv_file("col1,col2\nA,1\n")},
                          format="multipart").json()["id"]
        r = client.patch(f"{IMP}/jobs/{jid}/mapping/",
                         {"column_mapping": {"col1": "name", "col2": "value"}}, format="json")
        assert r.status_code == 200
        assert r.json()["valid_rows"] == 1

    def test_rows_filter(self, ws, member, lead, client):
        jid = client.post(f"{IMP}/jobs/",
                          {"entity_slug": "lead", "file": csv_file("name,value\n,1\nB,2\n")},
                          format="multipart").json()["id"]
        invalid = client.get(f"{IMP}/jobs/{jid}/rows/?status=invalid").json()
        assert invalid["count"] == 1

    def test_viewer_cannot_upload(self, ws, lead):
        _, c = make_client(ws, "v@acme.com", role="viewer")
        r = c.post(f"{IMP}/jobs/", {"entity_slug": "lead", "file": csv_file("name\nA\n")},
                   format="multipart")
        assert r.status_code == 403


@pytest.mark.django_db
class TestExportApi:
    def test_create_and_download(self, ws, member, lead, client):
        from apps.records.services import RecordService
        RecordService.create_record(workspace_id=ws.id, member=member, entity=lead,
                                    data={"name": "A", "value": 1})
        r = client.post(f"{EXP}/jobs/", {"entity_slug": "lead", "format": "csv"},
                        format="json")
        assert r.status_code == 201
        jid = r.json()["id"]
        assert client.get(f"{EXP}/jobs/{jid}/").json()["status"] == "completed"
        assert "url" in client.get(f"{EXP}/jobs/{jid}/download/").json()

    def test_workspace_isolation(self, ws, member, lead, client):
        from apps.records.services import RecordService
        RecordService.create_record(workspace_id=ws.id, member=member, entity=lead,
                                    data={"name": "A", "value": 1})
        jid = client.post(f"{EXP}/jobs/", {"entity_slug": "lead", "format": "csv"},
                          format="json").json()["id"]
        other = Workspace.objects.create(name="O", slug="o", is_active=True)
        _, c2 = make_client(other, "x@o.com", role="admin")
        assert c2.get(f"{EXP}/jobs/{jid}/").status_code == 404
