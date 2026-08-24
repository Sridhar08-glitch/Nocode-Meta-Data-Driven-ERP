"""Saved Views (master spec §49) — a member's personalized view configuration."""
from __future__ import annotations

import uuid

from .models import SavedView

_FIELDS = ["name", "hidden_field_slugs", "column_widths", "personal_filters",
           "sort_overrides", "group_by_override", "is_pinned"]


def create_saved_view(*, workspace_id, member_id, entity_id, data: dict) -> SavedView:
    return SavedView.objects.create(
        workspace_id=workspace_id, member_id=member_id, entity_id=entity_id,
        view_definition_id=data.get("view_definition_id") or uuid.uuid4(),
        name=data.get("name", ""),
        hidden_field_slugs=data.get("hidden_field_slugs", []),
        column_widths=data.get("column_widths", {}),
        personal_filters=data.get("personal_filters", []),
        sort_overrides=data.get("sort_overrides", []),
        group_by_override=data.get("group_by_override", ""),
        is_pinned=data.get("is_pinned", False))


def list_for_member(*, workspace_id, member_id, entity_id=None):
    qs = SavedView.objects.filter(workspace_id=workspace_id, member_id=member_id)
    if entity_id:
        qs = qs.filter(entity_id=entity_id)
    return list(qs.order_by("-is_pinned", "name"))


def get_owned(*, workspace_id, member_id, view_id):
    return SavedView.objects.filter(
        workspace_id=workspace_id, member_id=member_id, id=view_id).first()


def update_saved_view(view: SavedView, data: dict) -> SavedView:
    changed = [f for f in _FIELDS if f in data]
    for f in changed:
        setattr(view, f, data[f])
    if changed:
        view.save(update_fields=changed)
    return view
