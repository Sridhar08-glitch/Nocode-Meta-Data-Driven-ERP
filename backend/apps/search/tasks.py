"""
Search Celery tasks (PROJECT_HANDBOOK.md §26.2).
"""
from __future__ import annotations

from celery import shared_task

from .models import SearchIndex
from .services import SearchService, _entity


@shared_task(name="search.reindex_entity")
def reindex_entity(search_index_id: str) -> dict:
    """Full reindex of an entity's FTS column (PostgreSQL); rebuild + recount."""
    index = SearchIndex.objects.filter(id=search_index_id).first()
    if index is None:
        return {"status": "missing"}
    SearchService.build_tsvector_index(index)
    return {"status": "ok", "rows": index.indexed_row_count}


@shared_task(name="search.reindex_single_record")
def reindex_single_record(entity_slug: str, record_id: str, workspace_id: str) -> dict:
    """Light-weight single-row reindex (called via transaction.on_commit)."""
    entity = _entity(workspace_id, entity_slug)
    if entity is None:
        return {"status": "missing"}
    SearchService.reindex_record(record_id=record_id, entity=entity,
                                 workspace_id=workspace_id)
    return {"status": "ok"}
