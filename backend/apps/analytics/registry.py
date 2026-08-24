"""
Native KPI evaluators (Phase P2.13).

NQL KPIs cover metadata entities (CRM/Projects/HR/Helpdesk/Assets …). For KPIs whose data lives in
NATIVE engines (Inventory ledger, Payroll, Manufacturing), a module registers a ``native`` evaluator
here — an extension-point registry (like the country-adapter pattern) so analytics aggregates across
modules WITHOUT coupling the registry to every app. Built-in evaluators read native models
best-effort (return 0 when the module isn't installed).
"""
from __future__ import annotations

import contextlib
from decimal import Decimal

_REGISTRY: dict = {}


def register(key, fn):
    _REGISTRY[key] = fn


def get(key):
    return _REGISTRY.get(key)


def keys():
    return sorted(_REGISTRY)


def _d(v):
    try:
        return Decimal(str(v or 0))
    except Exception:  # noqa: BLE001
        return Decimal("0")


# ── built-in cross-module evaluators ─────────────────────────────────────────
def _inventory_value(workspace_id):
    with contextlib.suppress(Exception):
        from django.db.models import Sum

        from apps.inventory.models import StockLevel
        return _d(StockLevel.objects.filter(workspace_id=workspace_id).aggregate(
            s=Sum("value"))["s"])
    return Decimal("0")


def _payroll_cost(workspace_id):
    with contextlib.suppress(Exception):
        from django.db.models import Sum

        from apps.payroll.models import Payslip
        return _d(Payslip.objects.filter(workspace_id=workspace_id).aggregate(
            s=Sum("gross_pay"))["s"])
    return Decimal("0")


def _manufacturing_output(workspace_id):
    with contextlib.suppress(Exception):
        from django.db.models import Sum

        from apps.manufacturing.models import ProductionOrder
        return _d(ProductionOrder.objects.filter(
            workspace_id=workspace_id, status__in=["completed", "closed"]).aggregate(
            s=Sum("good_qty"))["s"])
    return Decimal("0")


def _asset_count(workspace_id):
    with contextlib.suppress(Exception):
        from apps.assets.models import DepreciationSchedule
        return _d(DepreciationSchedule.objects.filter(workspace_id=workspace_id).count())
    return Decimal("0")


register("inventory_value", _inventory_value)
register("payroll_cost", _payroll_cost)
register("manufacturing_output", _manufacturing_output)
register("asset_depreciation_schedules", _asset_count)
