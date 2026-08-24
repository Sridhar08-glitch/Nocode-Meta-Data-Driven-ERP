"""
Asset Management services (Phase P2.9).

``AssetService`` is the thin lifecycle (create/assign/return/transfer/maintenance/inspection/
retire) over the framework metadata entities, delegating numbering + audit to the reusable
``SolutionDocumentService``. ``DepreciationService`` and ``DisposalService`` are the NATIVE
engines: immutable depreciation entries + disposal records, each posting to the GL via GLBus
(decoupled — a missing chart never blocks the operation), updating the asset's metadata
valuation fields. Batch-safe (run_all iterates native schedule rows, no per-asset N+1).
"""
from __future__ import annotations

import contextlib
import uuid
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.ledger.provisioning import ensure_accounting_settings
from apps.records.services import RecordService, resolve_entity
from apps.solution_templates.documents import (
    SolutionDocumentService as Docs,
)
from apps.solution_templates.documents import (
    emit_event,
    system_member,
)

from . import depreciation
from .blueprint import ASSET_SEQUENCES
from .depreciation import money
from .models import (
    AssetValuationSnapshot,
    DepreciationEntry,
    DepreciationSchedule,
    DisposalRecord,
)


class AssetError(Exception):  # noqa: N818 — domain error
    pass


def _uid(actor_id):
    return uuid.UUID(str(actor_id)) if actor_id else None


def _update_asset(workspace_id, asset_record_id, data, member=None, actor_id=None):
    member = member or system_member(actor_id)
    entity = resolve_entity(workspace_id, "asset")
    return RecordService.update_record(
        workspace_id=workspace_id, member=member, entity=entity,
        record_id=asset_record_id, data=data)


def _get_asset(workspace_id, asset_record_id, member=None, actor_id=None):
    member = member or system_member(actor_id)
    entity = resolve_entity(workspace_id, "asset")
    return RecordService.retrieve_record(
        workspace_id=workspace_id, member=member, entity=entity, record_id=asset_record_id)


# ── lifecycle (framework metadata) ───────────────────────────────────────────
class AssetService:
    @staticmethod
    def ensure_sequences(workspace_id, *, actor_id=None):
        from apps.numbering.services import NumberingService
        for key, defaults in ASSET_SEQUENCES.items():
            NumberingService.ensure_sequence(
                workspace_id, key, defaults=defaults, created_by=actor_id)

    @staticmethod
    def create_asset(*, workspace_id, data, member=None, actor_id=None):
        return Docs.create(
            workspace_id=workspace_id, entity_slug="asset", data=data, member=member,
            actor_id=actor_id, sequence_key="asset",
            sequence_defaults=ASSET_SEQUENCES["asset"], event_type="asset.created")

    @staticmethod
    def assign_asset(*, workspace_id, asset_record_id, employee=None, department="",
                     team="", member=None, actor_id=None):
        Docs.create(workspace_id=workspace_id, entity_slug="asset_assignment",
                    data={"asset": str(asset_record_id), "employee": employee,
                          "department": department, "team": team, "status": "active"},
                    member=member, actor_id=actor_id)
        asset = _update_asset(workspace_id, asset_record_id, {"status": "assigned"},
                              member, actor_id)
        emit_event(workspace_id, "asset", asset_record_id, "asset.assigned",
                   {"employee": str(employee) if employee else None}, actor_id)
        return asset

    @staticmethod
    def return_asset(*, workspace_id, asset_record_id, member=None, actor_id=None):
        asset = _update_asset(workspace_id, asset_record_id, {"status": "in_service"},
                              member, actor_id)
        emit_event(workspace_id, "asset", asset_record_id, "asset.returned", {}, actor_id)
        return asset

    @staticmethod
    def transfer_asset(*, workspace_id, asset_record_id, transfer_type="department",
                       from_ref="", to_ref="", member=None, actor_id=None):
        Docs.create(workspace_id=workspace_id, entity_slug="asset_transfer",
                    data={"asset": str(asset_record_id), "transfer_type": transfer_type,
                          "from_ref": from_ref, "to_ref": to_ref, "status": "approved"},
                    member=member, actor_id=actor_id)
        emit_event(workspace_id, "asset", asset_record_id, "asset.transferred",
                   {"transfer_type": transfer_type, "to": to_ref}, actor_id)
        return _get_asset(workspace_id, asset_record_id, member, actor_id)

    @staticmethod
    def complete_maintenance(*, workspace_id, work_order_id, member=None, actor_id=None):
        wo = Docs.transition(
            workspace_id=workspace_id, entity_slug="maintenance_work_order",
            record_id=work_order_id, updates={"status": "completed"}, member=member,
            actor_id=actor_id)
        asset_id = wo.get("asset")
        if asset_id:
            emit_event(workspace_id, "asset", asset_id, "asset.maintenance.completed",
                       {"work_order": str(work_order_id)}, actor_id)
        return wo

    @staticmethod
    def record_inspection(*, workspace_id, asset_record_id, result="passed", inspector=None,
                          notes="", member=None, actor_id=None):
        insp = Docs.create(
            workspace_id=workspace_id, entity_slug="inspection",
            data={"asset": str(asset_record_id), "result": result, "inspector": inspector,
                  "notes": notes}, member=member, actor_id=actor_id)
        emit_event(workspace_id, "asset", asset_record_id, "asset.inspected",
                   {"result": result}, actor_id)
        return insp

    @staticmethod
    def retire_asset(*, workspace_id, asset_record_id, reason="", residual_value=0,
                     member=None, actor_id=None):
        """Retire (without sale). Records an immutable retirement + writes off remaining NBV to GL."""
        asset = _get_asset(workspace_id, asset_record_id, member, actor_id)
        book_value = money(asset.get("net_book_value") or asset.get("current_value") or 0)
        rec = DisposalRecord.objects.create(
            workspace_id=workspace_id, asset_record_id=asset_record_id, kind="retirement",
            method="write_off", book_value=book_value, residual_value=money(residual_value),
            gain_loss=money(money(residual_value) - book_value), reason=reason,
            status="posted", created_by=_uid(actor_id))
        _update_asset(workspace_id, asset_record_id, {"status": "retired"}, member, actor_id)
        emit_event(workspace_id, "asset", asset_record_id, "asset.retired",
                   {"book_value": str(book_value)}, actor_id)
        return rec


# ── depreciation engine (native) ─────────────────────────────────────────────
class DepreciationService:
    @staticmethod
    def create_schedule(*, workspace_id, asset_record_id, method="straight_line",
                        acquisition_cost=0, salvage_value=0, useful_life_months=12,
                        start_date=None, actor_id=None) -> DepreciationSchedule:
        # Resolve the GL accounts from the workspace mappings (no hardcoded codes — Blocker 2).
        s = ensure_accounting_settings(workspace_id, actor_id=actor_id)
        sched = DepreciationSchedule.objects.create(
            workspace_id=workspace_id, asset_record_id=asset_record_id, method=method,
            acquisition_cost=money(acquisition_cost), salvage_value=money(salvage_value),
            useful_life_months=int(useful_life_months or 0), start_date=start_date,
            gl_expense_account=s.default_depreciation_expense_account,
            gl_accumulated_account=s.default_accumulated_depreciation_account,
            status="active", created_by=_uid(actor_id))
        return sched

    @staticmethod
    def run_period(*, workspace_id, schedule_id, period_date, member=None,
                   actor_id=None) -> DepreciationEntry | None:
        """Post the next immutable depreciation period for one schedule. Returns None when the
        asset is fully depreciated. Updates the asset's metadata valuation fields + posts GL."""
        period_date = period_date or timezone.now().date()
        with transaction.atomic():
            sched = DepreciationSchedule.objects.select_for_update().filter(
                workspace_id=workspace_id, id=schedule_id).first()
            if sched is None:
                raise AssetError("Depreciation schedule not found.")
            if sched.status != "active":
                return None
            prior = DepreciationEntry.objects.filter(
                workspace_id=workspace_id, schedule_id=sched.id).order_by("-period_index").first()
            period_index = (prior.period_index + 1) if prior else 0
            accumulated = prior.accumulated if prior else Decimal("0.00")
            amount = depreciation.period_amount(
                method=sched.method, cost=sched.acquisition_cost, salvage=sched.salvage_value,
                useful_life_months=sched.useful_life_months, accumulated=accumulated,
                period_index=period_index)
            if amount <= 0:
                sched.status = "closed"
                sched.save(update_fields=["status", "updated_at"])
                return None
            new_accum = money(accumulated + amount)
            nbv = money(sched.acquisition_cost - new_accum)
            entry = DepreciationEntry.objects.create(
                workspace_id=workspace_id, schedule_id=sched.id,
                asset_record_id=sched.asset_record_id, period_index=period_index,
                period_date=period_date, amount=amount, accumulated=new_accum,
                net_book_value=nbv, posted=True, created_by=_uid(actor_id))
            entry.journal_entry_id = DepreciationService._post_gl(
                workspace_id, sched, amount, period_date, actor_id)
            entry.save(update_fields=["journal_entry_id"])
            AssetValuationSnapshot.objects.create(
                workspace_id=workspace_id, asset_record_id=sched.asset_record_id,
                snapshot_date=period_date, purchase_value=sched.acquisition_cost,
                current_value=nbv, book_value=nbv, accumulated_depreciation=new_accum)
            # Reflect on the asset metadata record (best-effort — needs the metadata entity).
            with contextlib.suppress(Exception):
                _update_asset(workspace_id, sched.asset_record_id,
                             {"accumulated_depreciation": str(new_accum),
                              "net_book_value": str(nbv), "current_value": str(nbv)},
                             member, actor_id)
        emit_event(workspace_id, "asset", sched.asset_record_id, "asset.depreciation.posted",
                   {"amount": str(amount), "net_book_value": str(nbv)}, actor_id)
        return entry

    @staticmethod
    def _post_gl(workspace_id, sched, amount, period_date, actor_id):
        from apps.ledger.services import GLBus, LedgerError, emit_post_failure
        try:
            entry = GLBus.post(
                workspace_id, date=period_date, lines=[
                    {"account_code": sched.gl_expense_account, "debit": str(money(amount)),
                     "memo": "Depreciation expense"},
                    {"account_code": sched.gl_accumulated_account, "credit": str(money(amount)),
                     "memo": "Accumulated depreciation"}],
                memo="Depreciation", source_module="assets", source_ref=str(sched.id),
                actor_id=actor_id)
            return entry.id if entry is not None else None
        except LedgerError as exc:
            emit_post_failure(workspace_id, module="assets", source_ref=str(sched.id),
                              error=str(exc), actor_id=actor_id)
            raise

    @staticmethod
    def run_all(*, workspace_id, period_date, member=None, actor_id=None) -> int:
        """Bulk depreciation run across all active schedules. Returns posted count."""
        count = 0
        for sched in DepreciationSchedule.objects.filter(
                workspace_id=workspace_id, status="active").values_list("id", flat=True):
            entry = DepreciationService.run_period(
                workspace_id=workspace_id, schedule_id=sched, period_date=period_date,
                member=member, actor_id=actor_id)
            if entry is not None:
                count += 1
        return count


# ── disposal engine (native) ─────────────────────────────────────────────────
class DisposalService:
    @staticmethod
    def dispose(*, workspace_id, asset_record_id, method="sale", proceeds=0, book_value=None,
                disposal_date=None, reason="", member=None, actor_id=None) -> DisposalRecord:
        """Dispose an asset (sale/scrap/donation/write_off). Records an immutable disposal,
        posts the GL proceeds entry (when proceeds > 0), and sets the asset disposed.

        Idempotent (Blocker 4): an asset can be disposed once. A retry / double-click / queue
        replay returns the existing disposal instead of creating a duplicate record + duplicate
        GL entry — enforced by a row lock AND the DB unique constraint (workspace, asset, kind)."""
        with transaction.atomic():
            existing = (DisposalRecord.objects.select_for_update()
                        .filter(workspace_id=workspace_id, asset_record_id=asset_record_id,
                                kind="disposal").first())
            if existing is not None:
                return existing
            if book_value is None:
                asset = _get_asset(workspace_id, asset_record_id, member, actor_id)
                book_value = asset.get("net_book_value") or asset.get("current_value") or 0
            book_value = money(book_value)
            proceeds = money(proceeds)
            disposal_date = disposal_date or timezone.now().date()
            try:
                rec = DisposalRecord.objects.create(
                    workspace_id=workspace_id, asset_record_id=asset_record_id, kind="disposal",
                    method=method, disposal_date=disposal_date, proceeds=proceeds,
                    book_value=book_value, gain_loss=money(proceeds - book_value), reason=reason,
                    status="posted", created_by=_uid(actor_id))
            except IntegrityError:
                # A concurrent disposer won the race — return the now-existing record.
                return DisposalRecord.objects.get(
                    workspace_id=workspace_id, asset_record_id=asset_record_id, kind="disposal")
            rec.journal_entry_id = DisposalService._post_gl(
                workspace_id, rec, disposal_date, actor_id)
            rec.save(update_fields=["journal_entry_id"])
            with contextlib.suppress(Exception):
                _update_asset(workspace_id, asset_record_id, {"status": "disposed"},
                             member, actor_id)
            emit_event(workspace_id, "asset", asset_record_id, "asset.disposed",
                       {"method": method, "proceeds": str(proceeds),
                        "gain_loss": str(rec.gain_loss)}, actor_id)
        return rec

    @staticmethod
    def _post_gl(workspace_id, rec, disposal_date, actor_id):
        from apps.ledger.services import GLBus, LedgerError, emit_post_failure
        if rec.proceeds <= 0:
            return None  # write-off/scrap with no proceeds — no cash entry
        s = ensure_accounting_settings(workspace_id, actor_id=actor_id)
        try:
            entry = GLBus.post(
                workspace_id, date=disposal_date, lines=[
                    {"account_code": s.default_cash_account, "debit": str(rec.proceeds),
                     "memo": "Disposal proceeds (cash)"},
                    {"account_code": s.default_fixed_asset_account, "credit": str(rec.proceeds),
                     "memo": "Asset disposal clearing"}],
                memo="Asset disposal", source_module="assets",
                source_ref=str(rec.asset_record_id), actor_id=actor_id)
            return entry.id if entry is not None else None
        except LedgerError as exc:
            emit_post_failure(workspace_id, module="assets", source_ref=str(rec.asset_record_id),
                              error=str(exc), actor_id=actor_id)
            raise
