"""
Financial Dimension services (Financial Platform — F9).

``DimensionService`` — the single reusable entry point for defining dimensions/values and VALIDATING a
dimension map against them. Pure + deterministic (no AI). GLBus calls ``validate_map`` to reject a
posting that tags an unknown/inactive/out-of-effective-date dimension value; callers/rules can opt into
required-dimension enforcement. Statements/analytics filter on ``JournalLine.dimensions`` directly.
"""
from __future__ import annotations

import uuid

from django.utils import timezone

from .models import FinancialDimension, FinancialDimensionValue


class DimensionError(Exception):  # noqa: N818 — domain error
    pass


def _uid(actor_id):
    return uuid.UUID(str(actor_id)) if actor_id else None


class DimensionService:
    # ── definition ──────────────────────────────────────────────────────────────
    @staticmethod
    def ensure_dimension(*, workspace_id, code, name="", dimension_type="other", is_required=False,
                         is_hierarchical=False, allow_posting=True, sequence=0,
                         actor_id=None) -> FinancialDimension:
        dim, created = FinancialDimension.objects.get_or_create(
            workspace_id=workspace_id, code=str(code),
            defaults={"name": name or code, "dimension_type": dimension_type,
                      "is_required": is_required, "is_hierarchical": is_hierarchical,
                      "allow_posting": allow_posting, "sequence": sequence,
                      "created_by": _uid(actor_id)})
        return dim

    @staticmethod
    def add_value(*, workspace_id, dimension_code, code, name="", parent_code="",
                  effective_from=None, effective_to=None, actor_id=None) -> FinancialDimensionValue:
        dim = FinancialDimension.objects.filter(
            workspace_id=workspace_id, code=str(dimension_code)).first()
        if dim is None:
            raise DimensionError(f"Unknown dimension {dimension_code!r}.")
        parent = None
        if parent_code:
            parent = FinancialDimensionValue.objects.filter(
                workspace_id=workspace_id, dimension=dim, code=str(parent_code)).first()
        val, _ = FinancialDimensionValue.objects.get_or_create(
            workspace_id=workspace_id, dimension=dim, code=str(code),
            defaults={"name": name or code, "parent": parent, "effective_from": effective_from,
                      "effective_to": effective_to, "created_by": _uid(actor_id)})
        return val

    # ── validation (reused by GLBus + rules) ────────────────────────────────────
    @staticmethod
    def validate_map(workspace_id, dimensions: dict, *, on_date=None,
                     enforce_required=False) -> list[str]:
        """Validate a ``{dimension_code: value_code}`` map. Returns a list of errors (empty = valid):
        each dimension must be a known active posting dimension, each value must exist under it, be
        active and effective on ``on_date``. With ``enforce_required`` every ``is_required`` dimension
        must be present."""
        errors: list[str] = []
        day = on_date or timezone.now().date()
        dims = {d.code: d for d in FinancialDimension.objects.filter(workspace_id=workspace_id)}
        for dcode, vcode in (dimensions or {}).items():
            dim = dims.get(dcode)
            if dim is None or not dim.is_active:
                errors.append(f"unknown or inactive dimension '{dcode}'")
                continue
            if not dim.allow_posting:
                errors.append(f"dimension '{dcode}' is not postable")
                continue
            val = FinancialDimensionValue.objects.filter(
                workspace_id=workspace_id, dimension=dim, code=str(vcode)).first()
            if val is None or not val.is_active:
                errors.append(f"unknown or inactive value '{vcode}' for dimension '{dcode}'")
                continue
            if val.effective_from and val.effective_from > day:
                errors.append(f"value '{vcode}' not yet effective for '{dcode}'")
            if val.effective_to and val.effective_to < day:
                errors.append(f"value '{vcode}' expired for '{dcode}'")
        if enforce_required:
            present = set(dimensions or {})
            for dcode, dim in dims.items():
                if dim.is_required and dim.is_active and dcode not in present:
                    errors.append(f"required dimension '{dcode}' missing")
        return errors

    @staticmethod
    def descendants(workspace_id, dimension_code, value_code) -> list[str]:
        """All value codes at/under ``value_code`` in the hierarchy (for roll-up filtering)."""
        dim = FinancialDimension.objects.filter(
            workspace_id=workspace_id, code=str(dimension_code)).first()
        if dim is None:
            return []
        by_parent: dict = {}
        for v in FinancialDimensionValue.objects.filter(workspace_id=workspace_id, dimension=dim):
            by_parent.setdefault(v.parent_id, []).append(v)
        root = FinancialDimensionValue.objects.filter(
            workspace_id=workspace_id, dimension=dim, code=str(value_code)).first()
        if root is None:
            return []
        out, stack = [], [root]
        while stack:
            node = stack.pop()
            out.append(node.code)
            stack.extend(by_parent.get(node.id, []))
        return out
