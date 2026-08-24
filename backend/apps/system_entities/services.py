"""
System-Entity Adapter (B0) — generic data access + permission gate. Reads reflect any registered
native model; writes DELEGATE to the engine's own callables (accounting/validation stays in the
engine). Workspace-scoped (ORM filter is the first defense; the engine's tables also carry RLS).
"""
from __future__ import annotations

import datetime as _dt
import uuid
from decimal import Decimal

from . import registry


class SystemEntityError(Exception):  # noqa: N818
    pass


def _scalar(v):
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, uuid.UUID):
        return str(v)
    if isinstance(v, _dt.datetime | _dt.date):
        return v.isoformat()
    return v


def _row(entity, instance) -> dict:
    if entity.row_serializer is not None:
        return entity.row_serializer(instance)
    return {f.name: _scalar(getattr(instance, f.name, None)) for f in entity.fields}


def _member_role(request):
    m = getattr(request, "workspace_member", None)
    return getattr(m, "role", None) if m is not None else None


def can_read(entity, role) -> bool:
    return not entity.read_roles or role in entity.read_roles or role in ("owner", "admin")


def can_write(entity, role) -> bool:
    return role in entity.write_roles


class SystemEntityService:
    @staticmethod
    def list_entities(*, workspace_id, role) -> list[dict]:
        out = []
        for e in registry.all_entities():
            if not can_read(e, role):
                continue
            out.append({"slug": e.slug, "name": e.name, "plural_name": e.plural_name,
                        "module": e.module, "kind": "system",
                        "can_read": True, "can_create": e.can_create and can_write(e, role)})
        return out

    @staticmethod
    def descriptor(*, slug, role) -> dict:
        e = registry.get(slug)
        if e is None or not can_read(e, role):
            raise SystemEntityError("System entity not found.")
        return e.descriptor(can_write=can_write(e, role))

    @staticmethod
    def _base_qs(entity, workspace_id):
        qs = entity.model.objects.filter(workspace_id=workspace_id)
        field_names = {f.name for f in entity.model._meta.concrete_fields}
        if "is_deleted" in field_names:
            qs = qs.filter(is_deleted=False)          # soft-delete aware (skipped if no such field)
        return qs

    @staticmethod
    def list_records(*, slug, workspace_id, role, filters=None, sort=None, page=1,
                     page_size=50) -> dict:
        e = registry.get(slug)
        if e is None or not can_read(e, role):
            raise SystemEntityError("System entity not found.")
        qs = SystemEntityService._base_qs(e, workspace_id)
        filterable = {f.name for f in e.fields if f.filterable}
        for key, val in (filters or {}).items():
            if key in filterable and val not in (None, ""):
                qs = qs.filter(**{key: val})
        sortable = {f.name for f in e.fields if f.sortable}
        order = e.default_ordering
        if sort:
            raw = sort.lstrip("-")
            if raw in sortable:
                order = sort
        qs = qs.order_by(order, "id")
        count = qs.count()
        page = max(1, int(page or 1))
        page_size = min(200, max(1, int(page_size or 50)))
        rows = [_row(e, obj) for obj in qs[(page - 1) * page_size: page * page_size]]
        return {"results": rows, "count": count, "page": page, "page_size": page_size}

    @staticmethod
    def retrieve(*, slug, workspace_id, role, record_id) -> dict:
        e = registry.get(slug)
        if e is None or not can_read(e, role):
            raise SystemEntityError("System entity not found.")
        obj = SystemEntityService._base_qs(e, workspace_id).filter(id=record_id).first()
        if obj is None:
            raise SystemEntityError("Record not found.")
        return _row(e, obj)

    @staticmethod
    def create(*, slug, workspace_id, role, data, actor_id=None) -> dict:
        e = registry.get(slug)
        if e is None:
            raise SystemEntityError("System entity not found.")
        if not (e.can_create and can_write(e, role)):
            raise SystemEntityError("Create not permitted for this system entity.")
        obj = e.create_fn(workspace_id=workspace_id, data=dict(data or {}), actor_id=actor_id)
        return _row(e, obj)

    @staticmethod
    def update(*, slug, workspace_id, role, record_id, data, actor_id=None) -> dict:
        e = registry.get(slug)
        if e is None:
            raise SystemEntityError("System entity not found.")
        if not (e.can_update and can_write(e, role)):
            raise SystemEntityError("Update not permitted for this system entity.")
        obj = e.update_fn(workspace_id=workspace_id, record_id=record_id,
                          data=dict(data or {}), actor_id=actor_id)
        return _row(e, obj)

    @staticmethod
    def delete(*, slug, workspace_id, role, record_id, actor_id=None) -> None:
        e = registry.get(slug)
        if e is None:
            raise SystemEntityError("System entity not found.")
        if not (e.can_delete and can_write(e, role)):
            raise SystemEntityError("Delete not permitted for this system entity.")
        e.delete_fn(workspace_id=workspace_id, record_id=record_id, actor_id=actor_id)
