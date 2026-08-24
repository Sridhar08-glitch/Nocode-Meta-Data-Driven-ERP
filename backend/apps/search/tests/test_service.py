"""SearchService (PROJECT_HANDBOOK.md §26.1 / §26.4)."""
import pytest
from django.db import connection

from apps.search.models import RecentSearch, SearchIndex
from apps.search.services import SearchService


@pytest.mark.django_db
class TestIndex:
    def test_create_index_idempotent(self, ws, lead):
        SearchService.create_index(entity=lead, workspace_id=ws.id,
                                   indexed_field_slugs=["name"])
        SearchService.create_index(entity=lead, workspace_id=ws.id,
                                   indexed_field_slugs=["name", "notes"])
        # one row per entity (unique entity_id)
        idx = SearchIndex.objects.get(entity_id=lead.id)
        assert idx.indexed_field_slugs == ["name", "notes"]

    @pytest.mark.skipif(connection.vendor != "sqlite",
                        reason="tsvector build is a no-op only on SQLite; PG builds the index")
    def test_build_skipped_on_sqlite_no_error(self, ws, lead):
        # SQLite: build_tsvector_index is a no-op and must not raise
        idx = SearchService.create_index(entity=lead, workspace_id=ws.id,
                                         indexed_field_slugs=["name"])
        assert idx.last_reindex_at is None   # skipped on SQLite


@pytest.mark.django_db
class TestSearch:
    def test_finds_and_merges_cross_entity(self, ws, indexed):
        result = SearchService.search(query="acme", workspace_id=ws.id)
        slugs = {r["entity_slug"] for r in result["results"]}
        assert slugs == {"lead", "deal"}     # cross-entity merge
        assert result["total"] == 2
        assert all(r["rank"] >= r2["rank"]
                   for r, r2 in zip(result["results"], result["results"][1:], strict=False))

    def test_entity_filter(self, ws, indexed):
        result = SearchService.search(query="acme", workspace_id=ws.id, entity_slugs=["lead"])
        assert all(r["entity_slug"] == "lead" for r in result["results"])

    def test_empty_query(self, ws, indexed):
        assert SearchService.search(query="  ", workspace_id=ws.id)["results"] == []

    def test_workspace_isolation(self, ws, indexed):
        import uuid
        result = SearchService.search(query="acme", workspace_id=uuid.uuid4())
        assert result["results"] == []


@pytest.mark.django_db
class TestRecent:
    def test_rolling_twenty(self, ws, user):
        for i in range(25):
            SearchService.log_recent_search(
                member_id=user.id, workspace_id=ws.id, query=f"q{i}")
        assert RecentSearch.objects.filter(
            workspace_id=ws.id, member_id=user.id).count() == 20
