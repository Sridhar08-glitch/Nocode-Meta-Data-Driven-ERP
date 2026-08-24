"""
System-Entity Adapter (B0) — the GENERIC platform capability that lets a native-model REST engine
(treasury, inventory, ledger, cash, payroll, …) publish a metadata-SHAPED descriptor the Generic
Runtime can render exactly like a metadata `EntityDefinition`. Built once, it renders list / detail /
create / edit screens for EVERY native engine — no bespoke React, no per-package UI framework.

A `SystemEntity` reflects a Django model into a field list (type-mapped like the metadata field
registry), declares read/write role gates + capabilities, optional write callables (so writes reuse the
engine's own service — accounting/validation stays in the engine), and lifecycle `actions` (surfaced as
buttons the runtime calls on the engine's existing endpoints). Registered by each engine at app
`ready()`; this app owns ONLY the contract + registry + generic REST (it owns no domain logic).
"""
from __future__ import annotations

from django.db import models as dj

# Django field class → runtime field type (mirrors the FE field-type registry kinds).
_TYPE_MAP = [
    (dj.BooleanField, "boolean"),
    (dj.DecimalField, "decimal"),
    (dj.FloatField, "decimal"),
    (dj.IntegerField, "number"),
    (dj.DateTimeField, "datetime"),
    (dj.DateField, "date"),
    (dj.TextField, "text"),
    (dj.EmailField, "text"),
    (dj.SlugField, "text"),
    (dj.CharField, "text"),
    (dj.UUIDField, "text"),
]

# Never surfaced to the UI (tenant/audit/soft-delete plumbing).
_HIDDEN = {"workspace_id", "is_deleted", "deleted_at", "deleted_by", "created_by", "updated_by",
           "search_vector", "_fts_vector"}
_READONLY = {"id", "created_at", "updated_at"}
DEFAULT_READ_ROLES = ()                       # () = any workspace member
DEFAULT_WRITE_ROLES = ("owner", "admin")


class Field:
    __slots__ = ("name", "label", "type", "readonly", "filterable", "sortable", "choices",
                 "reference")

    def __init__(self, name, *, label=None, type="text", readonly=False, filterable=True,
                 sortable=True, choices=None, reference=None):
        self.name = name
        self.label = label or name.replace("_", " ").title()
        self.type = type
        self.readonly = readonly
        self.filterable = filterable
        self.sortable = sortable
        self.choices = choices
        self.reference = reference

    def to_dict(self):
        d = {"name": self.name, "label": self.label, "type": self.type,
             "readonly": self.readonly, "filterable": self.filterable, "sortable": self.sortable}
        if self.choices:
            d["choices"] = [{"value": v, "label": lbl} for v, lbl in self.choices]
        if self.reference:
            d["reference"] = self.reference
        return d


class Action:
    __slots__ = ("key", "label", "method", "path", "roles")

    def __init__(self, key, label, *, method="POST", path="", roles=DEFAULT_WRITE_ROLES):
        self.key, self.label, self.method, self.path, self.roles = key, label, method, path, roles

    def to_dict(self):
        return {"key": self.key, "label": self.label, "method": self.method, "path": self.path}


def _reflect_fields(model, *, include=None, exclude=(), overrides=None) -> list[Field]:
    overrides = overrides or {}
    exclude = set(exclude) | _HIDDEN
    out = []
    for f in model._meta.concrete_fields:
        name = f.attname                       # FK → "<name>_id"
        base = f.name
        if base in exclude or name in exclude:
            continue
        if include is not None and base not in include and name not in include:
            continue
        if name in overrides:
            out.append(overrides[name])
            continue
        ftype, ref = "text", None
        if getattr(f, "is_relation", False) and getattr(f, "related_model", None) is not None:
            ftype = "reference"
            ref = f.related_model._meta.model_name
        else:
            for cls, t in _TYPE_MAP:
                if isinstance(f, cls):
                    ftype = t
                    break
        choices = list(f.choices) if getattr(f, "choices", None) else None
        if choices:
            ftype = "select"
        out.append(Field(name, type=ftype, readonly=(base in _READONLY or name in _READONLY
                                                     or not f.editable),
                         choices=choices, reference=ref))
    return out


class SystemEntity:
    """A native model published as a runtime-renderable entity."""

    def __init__(self, *, slug, model, name=None, plural_name=None, module="",
                 include=None, exclude=(), field_overrides=None, extra_fields=(),
                 read_roles=DEFAULT_READ_ROLES, write_roles=DEFAULT_WRITE_ROLES,
                 can_create=False, can_update=False, can_delete=False,
                 create_fn=None, update_fn=None, delete_fn=None,
                 default_ordering="-created_at", actions=(), row_serializer=None):
        self.slug = slug
        self.model = model
        self.name = name or model._meta.verbose_name.title()
        self.plural_name = plural_name or f"{self.name}s"
        self.module = module
        self.fields = _reflect_fields(model, include=include, exclude=exclude,
                                      overrides=field_overrides)
        self.fields.extend(extra_fields)
        self.read_roles = tuple(read_roles)
        self.write_roles = tuple(write_roles)
        self.can_create = can_create
        self.can_update = can_update
        self.can_delete = can_delete
        self.create_fn = create_fn
        self.update_fn = update_fn
        self.delete_fn = delete_fn
        self.default_ordering = default_ordering
        self.actions = list(actions)
        self.row_serializer = row_serializer

    @property
    def field_names(self):
        return [f.name for f in self.fields]

    def descriptor(self, *, can_write=False) -> dict:
        return {
            "slug": self.slug, "name": self.name, "plural_name": self.plural_name,
            "module": self.module, "kind": "system",
            "fields": [f.to_dict() for f in self.fields],
            "actions": [a.to_dict() for a in self.actions],
            "capabilities": {"can_create": self.can_create and can_write,
                             "can_update": self.can_update and can_write,
                             "can_delete": self.can_delete and can_write},
            "default_ordering": self.default_ordering,
        }


_REGISTRY: dict[str, SystemEntity] = {}


def register(entity: SystemEntity) -> None:
    _REGISTRY[entity.slug] = entity


def get(slug) -> SystemEntity | None:
    return _REGISTRY.get(slug)


def all_entities() -> list[SystemEntity]:
    return [_REGISTRY[s] for s in sorted(_REGISTRY)]


def slugs() -> list[str]:
    return sorted(_REGISTRY)
