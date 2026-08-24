"""Search REST API (PROJECT_HANDBOOK.md §26.3 / §26.4)."""
import pytest

from apps.search.models import RecentSearch

from .conftest import make_client

BASE = "/api/v1/search"


@pytest.mark.django_db
class TestSearchApi:
    def test_search_and_logs_recent(self, ws, user, indexed, client):
        r = client.get(f"{BASE}/?q=acme")
        assert r.status_code == 200
        assert r.json()["total"] == 2
        assert RecentSearch.objects.filter(member_id=user.id, query_text="acme").exists()

    def test_search_entity_filter(self, ws, indexed, client):
        r = client.get(f"{BASE}/?q=acme&entity=deal")
        assert all(x["entity_slug"] == "deal" for x in r.json()["results"])

    def test_index_crud_and_reindex(self, ws, lead, client):
        r = client.post(f"{BASE}/indexes/",
                        {"entity_slug": "lead", "indexed_field_slugs": ["name"]},
                        format="json")
        assert r.status_code == 201, r.content
        iid = r.json()["id"]
        assert client.get(f"{BASE}/indexes/").json()["count"] == 1
        assert client.post(f"{BASE}/indexes/{iid}/reindex/").status_code == 202
        assert client.delete(f"{BASE}/indexes/{iid}/").status_code == 204

    def test_recent_list_and_clear(self, ws, indexed, client):
        client.get(f"{BASE}/?q=acme")
        assert client.get(f"{BASE}/recent/").json()["count"] >= 1
        assert "cleared" in client.delete(f"{BASE}/recent/").json()
        assert client.get(f"{BASE}/recent/").json()["count"] == 0


@pytest.mark.django_db
class TestSavedSearch:
    def test_create_list_owner_and_shared(self, ws, lead, client):
        r = client.post(f"{BASE}/saved/",
                        {"name": "Hot", "nql_ast": {"entity": "lead"}, "is_shared": False},
                        format="json")
        assert r.status_code == 201
        assert client.get(f"{BASE}/saved/").json()["count"] == 1
        # another member does not see a private saved search
        _, other = make_client(ws, "o@acme.com", role="member")
        assert other.get(f"{BASE}/saved/").json()["count"] == 0

    def test_edit_owner_only(self, ws, lead, client):
        sid = client.post(f"{BASE}/saved/",
                          {"name": "S", "nql_ast": {"entity": "lead"}}, format="json").json()["id"]
        _, other = make_client(ws, "o2@acme.com", role="member")
        assert other.patch(f"{BASE}/saved/{sid}/", {"name": "X"},
                           format="json").status_code == 403


@pytest.mark.django_db
class TestAuthz:
    def test_viewer_cannot_create_index(self, ws):
        _, c = make_client(ws, "v@acme.com", role="viewer")
        r = c.post(f"{BASE}/indexes/", {"entity_slug": "lead"}, format="json")
        assert r.status_code in (403, 404)  # 403 role gate (entity may not exist either)
