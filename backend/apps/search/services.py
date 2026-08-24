"""
SearchService (PROJECT_HANDBOOK.md §26.1).

Full-text search over generated entity tables. On PostgreSQL it maintains a
``_fts_vector`` ``tsvector`` column + GIN index and ranks with ``ts_rank_cd``; on
SQLite (tests) it falls back to ``LIKE`` over the indexed promoted columns +
``custom_data`` (no DDL). Everything is workspace-scoped and never returns
soft-deleted rows.
"""
from __future__ import annotations

from django.db import connection
from django.utils import timezone

from apps.records import dal
from apps.schema_registry.exceptions import EntityNotFoundError
from apps.schema_registry.services import SchemaRegistryService

from .models import RecentSearch, SearchIndex

RECENT_KEPT = 20
_WEIGHTS = {"A": "A", "B": "B", "C": "C", "D": "D"}


def _is_pg() -> bool:
    return connection.vendor == "postgresql"


def _entity(workspace_id, slug):
    try:
        return SchemaRegistryService.get_entity(workspace_id=workspace_id, slug=slug)
    except EntityNotFoundError:
        return None


def _indexed_columns(index, entity) -> list[str]:
    """Promoted column names for the index's indexed field slugs."""
    fmap = dal.FieldMap(entity)
    cols = []
    for slug in index.indexed_field_slugs:
        fd = fmap.fields.get(slug)
        if fd is not None and fd.is_promoted:
            cols.append(fd.column_name or slug)
    return cols


class SearchService:
    @staticmethod
    def create_index(*, entity, workspace_id, indexed_field_slugs, field_weights=None):
        index, _ = SearchIndex.objects.update_or_create(
            entity_id=entity.id, defaults={
                "workspace_id": workspace_id, "entity_slug": entity.slug,
                "indexed_field_slugs": list(indexed_field_slugs),
                "field_weights": field_weights or {},
                "config_updated_at": timezone.now()})
        SearchService.build_tsvector_index(index)
        return index

    @staticmethod
    def build_tsvector_index(index) -> None:
        """Create the tsvector column + GIN index and populate it (PostgreSQL only)."""
        if not _is_pg():
            return  # SQLite: LIKE fallback needs no index
        entity = _entity(index.workspace_id, index.entity_slug)
        if entity is None or not entity.table_name:
            return
        cols = _indexed_columns(index, entity)
        if not cols:
            return
        table = entity.table_name
        idx_name = f"{table}_fts_idx"[:63]
        expr = SearchService._tsvector_expr(index, cols)
        with connection.cursor() as cur:
            cur.execute(f'ALTER TABLE "{table}" ADD COLUMN IF NOT EXISTS _fts_vector tsvector')
            cur.execute(f'CREATE INDEX IF NOT EXISTS "{idx_name}" '
                        f'ON "{table}" USING GIN(_fts_vector)')
            cur.execute(f'UPDATE "{table}" SET _fts_vector = {expr} WHERE workspace_id = %s',
                        [str(index.workspace_id)])
        index.last_reindex_at = timezone.now()
        with connection.cursor() as cur:
            cur.execute(f'SELECT COUNT(*) FROM "{table}" WHERE workspace_id = %s',
                        [str(index.workspace_id)])
            index.indexed_row_count = cur.fetchone()[0]
        index.save(update_fields=["last_reindex_at", "indexed_row_count"])

    @staticmethod
    def _tsvector_expr(index, cols) -> str:
        parts = []
        for col in cols:
            weight = _WEIGHTS.get((index.field_weights or {}).get(col, ""), None)
            term = f"to_tsvector('english', coalesce(\"{col}\"::text, ''))"
            if weight:
                term = f"setweight({term}, '{weight}')"
            parts.append(term)
        return " || ".join(parts) if parts else "to_tsvector('english', '')"

    @staticmethod
    def reindex_record(*, record_id, entity, workspace_id) -> None:
        if not _is_pg() or not entity.table_name:
            return
        index = SearchIndex.objects.filter(entity_id=entity.id).first()
        if index is None:
            return
        cols = _indexed_columns(index, entity)
        if not cols:
            return
        expr = SearchService._tsvector_expr(index, cols)
        with connection.cursor() as cur:
            cur.execute(f'UPDATE "{entity.table_name}" SET _fts_vector = {expr} '
                        f'WHERE id = %s AND workspace_id = %s',
                        [str(record_id), str(workspace_id)])

    @staticmethod
    def search(*, query, workspace_id, entity_slugs=None, limit=25, offset=0) -> dict:
        query = (query or "").strip()
        if not query:
            return {"results": [], "total": 0}
        indexes = SearchIndex.objects.filter(workspace_id=workspace_id)
        if entity_slugs:
            indexes = indexes.filter(entity_slug__in=list(entity_slugs))
        results = []
        for index in indexes:
            entity = _entity(workspace_id, index.entity_slug)
            if entity is None or not entity.table_name:
                continue
            cols = _indexed_columns(index, entity)
            if not cols:
                continue
            if _is_pg():
                results.extend(SearchService._search_pg(entity, cols, query, workspace_id))
            else:
                results.extend(SearchService._search_sqlite(entity, cols, query, workspace_id))
        results.sort(key=lambda r: r["rank"], reverse=True)
        total = len(results)
        return {"results": results[offset:offset + limit], "total": total}

    @staticmethod
    def _search_pg(entity, cols, query, workspace_id) -> list[dict]:
        table = entity.table_name
        title_col = cols[0]
        sql = (f'SELECT id, "{title_col}"::text AS title, '
               f'ts_rank_cd(_fts_vector, plainto_tsquery(\'english\', %s)) AS rank '
               f'FROM "{table}" WHERE workspace_id = %s AND deleted_at IS NULL '
               f'AND _fts_vector @@ plainto_tsquery(\'english\', %s) ORDER BY rank DESC LIMIT 100')
        out = []
        with connection.cursor() as cur:
            cur.execute(sql, [query, str(workspace_id), query])
            for rid, title, rank in cur.fetchall():
                out.append({"entity_slug": entity.slug, "record_id": str(rid),
                            "title": title or "", "snippet": title or "",
                            "rank": float(rank or 0)})
        return out

    @staticmethod
    def _search_sqlite(entity, cols, query, workspace_id) -> list[dict]:
        table = entity.table_name
        like = f"%{query.lower()}%"
        col_list = ", ".join(f'"{c}"' for c in cols)
        where_cols = " OR ".join(f'LOWER(CAST("{c}" AS TEXT)) LIKE ?' for c in cols)
        where_cols += ' OR LOWER(CAST("custom_data" AS TEXT)) LIKE ?'
        sql = (f'SELECT "id", {col_list}, "custom_data" FROM "{table}" '
               f'WHERE "workspace_id" = ? AND "deleted_at" IS NULL AND ({where_cols}) LIMIT 100')
        params = [str(workspace_id)] + [like] * (len(cols) + 1)
        out = []
        with connection.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall()
        for row in rows:
            rid = row[0]
            values = [str(v) for v in row[1:1 + len(cols)] if v is not None]
            rank = sum(1 for v in values if query.lower() in v.lower())
            title = next((v for v in values if v), "")
            out.append({"entity_slug": entity.slug, "record_id": str(rid),
                        "title": title, "snippet": " ".join(values)[:200],
                        "rank": float(rank) or 0.1})
        return out

    @staticmethod
    def log_recent_search(*, member_id, workspace_id, query, entity_slug=None,
                          result_count=0) -> None:
        if not query:
            return
        RecentSearch.objects.create(
            workspace_id=workspace_id, member_id=member_id, query_text=query[:500],
            entity_slug=entity_slug or "", result_count=result_count)
        stale = (RecentSearch.objects
                 .filter(workspace_id=workspace_id, member_id=member_id)
                 .order_by("-searched_at")
                 .values_list("id", flat=True)[RECENT_KEPT:])
        if stale:
            RecentSearch.objects.filter(id__in=list(stale)).delete()
