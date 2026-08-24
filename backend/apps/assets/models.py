"""
Asset Management native models (Phase P2.9).

Only the integrity-critical pieces are native: immutable depreciation schedules/entries, asset
valuation snapshots, and immutable disposal records — each posting to the GL. Asset master data
itself is a framework metadata entity (``blueprint.py``); these models reference it by record-id
UUID (no FK), mirroring payroll↔HR. Workspace-scoped (TenantModel) with RLS (migration 0002).
"""
from django.db import models

from apps.core.models import TenantModel

MONEY = {"max_digits": 16, "decimal_places": 2, "default": 0}


class DepreciationSchedule(TenantModel):
    asset_record_id = models.UUIDField(db_index=True)
    method = models.CharField(max_length=30, default="straight_line")  # straight_line|declining_balance|double_declining
    acquisition_cost = models.DecimalField(**MONEY)
    salvage_value = models.DecimalField(**MONEY)
    useful_life_months = models.IntegerField(default=12)
    start_date = models.DateField(null=True, blank=True)
    gl_expense_account = models.CharField(max_length=32, default="6100")
    gl_accumulated_account = models.CharField(max_length=32, default="1600")
    status = models.CharField(max_length=20, default="active")  # active|closed

    class Meta:
        db_table = "asset_depreciation_schedules"
        indexes = [models.Index(fields=["workspace_id", "asset_record_id", "status"])]


class DepreciationEntry(TenantModel):
    """One immutable depreciation period. Posted entries are never modified."""
    schedule_id = models.UUIDField(db_index=True)
    asset_record_id = models.UUIDField(db_index=True)
    period_index = models.IntegerField(default=0)
    period_date = models.DateField()
    amount = models.DecimalField(**MONEY)
    accumulated = models.DecimalField(**MONEY)
    net_book_value = models.DecimalField(**MONEY)
    posted = models.BooleanField(default=True)
    journal_entry_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "asset_depreciation_entries"
        unique_together = [("workspace_id", "schedule_id", "period_index")]
        indexes = [models.Index(fields=["workspace_id", "asset_record_id", "period_index"])]


class AssetValuationSnapshot(TenantModel):
    asset_record_id = models.UUIDField(db_index=True)
    snapshot_date = models.DateField()
    purchase_value = models.DecimalField(**MONEY)
    current_value = models.DecimalField(**MONEY)
    book_value = models.DecimalField(**MONEY)
    accumulated_depreciation = models.DecimalField(**MONEY)

    class Meta:
        db_table = "asset_valuation_snapshots"
        indexes = [models.Index(fields=["workspace_id", "asset_record_id", "-snapshot_date"])]


class DisposalRecord(TenantModel):
    """Immutable disposal/retirement record. Posted records are never modified."""
    asset_record_id = models.UUIDField(db_index=True)
    kind = models.CharField(max_length=20, default="disposal")  # disposal|retirement
    method = models.CharField(max_length=20, default="sale")  # sale|scrap|donation|write_off
    disposal_date = models.DateField(null=True, blank=True)
    proceeds = models.DecimalField(**MONEY)
    book_value = models.DecimalField(**MONEY)
    gain_loss = models.DecimalField(**MONEY)
    residual_value = models.DecimalField(**MONEY)
    reason = models.TextField(blank=True)
    status = models.CharField(max_length=20, default="posted")  # posted
    journal_entry_id = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "asset_disposal_records"
        # One disposal/retirement per asset — the DB backstop for dispose() idempotency (P2.15).
        unique_together = [("workspace_id", "asset_record_id", "kind")]
        indexes = [models.Index(fields=["workspace_id", "asset_record_id"])]
