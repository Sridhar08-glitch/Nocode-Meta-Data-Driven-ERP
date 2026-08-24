"""Recycle Bin REST API (PROJECT_HANDBOOK.md §31.3 / §31.5)."""
import pytest

from apps.recyclebin.models import RecycleBinEntry
from apps.tenancy.models import Workspace

from .conftest import make_client

BASE = "/api/v1/recyclebin"


@pytest.mark.django_db
class TestRecycleBinApi:
    def test_list_and_restore(self, ws, member, lead, deleted_record, client):
        rid, entry = deleted_record()
        assert client.get(f"{BASE}/").json()["count"] == 1
        assert client.post(f"{BASE}/{entry.id}/restore/").json()["restored"] is True
        assert not RecycleBinEntry.objects.filter(id=entry.id).exists()

    def test_purge_admin_only(self, ws, deleted_record):
        rid, entry = deleted_record()
        _, viewer = make_client(ws, "v@acme.com", role="viewer")
        assert viewer.post(f"{BASE}/{entry.id}/purge/").status_code == 403
        _, admin = make_client(ws, "a2@acme.com", role="admin")
        assert admin.post(f"{BASE}/{entry.id}/purge/").json()["purged"] is True

    def test_bulk_restore(self, ws, deleted_record, client):
        _, e1 = deleted_record("A")
        _, e2 = deleted_record("B")
        r = client.post(f"{BASE}/bulk-restore/",
                        {"entry_ids": [str(e1.id), str(e2.id)]}, format="json")
        assert r.json()["restored"] == 2

    def test_workspace_isolation(self, ws, deleted_record, client):
        rid, entry = deleted_record()
        other = Workspace.objects.create(name="O", slug="o", is_active=True)
        _, c2 = make_client(other, "x@o.com", role="admin")
        assert c2.get(f"{BASE}/{entry.id}/").status_code == 404
        assert c2.post(f"{BASE}/{entry.id}/restore/").status_code == 404
