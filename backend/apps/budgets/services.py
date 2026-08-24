"""
Budgets & Forecasts services (Financial Platform — F10).

``BudgetService`` — the single reusable entry point for budget/forecast planning + variance. It REUSES
the platform and adds NO accounting: dimensions validated via F9 ``DimensionService``; ACTUALS come
ONLY from the GL (``financial_reports.StatementService`` line query + ``LedgerAccount`` normal balance)
— budget/forecast-vs-actual never duplicates accounting. Versions are the revision + scenario axis
(segregation of duties on approval; locked versions immutable). Deterministic; no AI.
"""
from __future__ import annotations

import uuid
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from apps.ledger.models import LedgerAccount, normal_balance
from apps.solution_templates.documents import emit_event

from .models import FinancialPlan, PlanLine, PlanVersion

CENTS = Decimal("0.01")


class BudgetError(Exception):  # noqa: N818 — domain error
    pass


def _m(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(CENTS, rounding=ROUND_HALF_UP)


def _uid(actor_id):
    return uuid.UUID(str(actor_id)) if actor_id else None


class BudgetService:
    # ── plan + version lifecycle ────────────────────────────────────────────────
    @staticmethod
    def create_plan(*, workspace_id, code, name="", plan_type="budget", fiscal_year="",
                    period_type="monthly", currency="", is_rolling=False, actor_id=None):
        if FinancialPlan.objects.filter(workspace_id=workspace_id, code=code).exists():
            raise BudgetError(f"Plan {code!r} already exists.")
        plan = FinancialPlan.objects.create(
            workspace_id=workspace_id, code=code, name=name or code, plan_type=plan_type,
            fiscal_year=fiscal_year, period_type=period_type, currency=currency,
            is_rolling=bool(is_rolling), status=FinancialPlan.ACTIVE, created_by=_uid(actor_id))
        emit_event(workspace_id, "financial_plan", plan.id, f"{plan_type}.plan.created",
                   {"code": code, "fiscal_year": fiscal_year}, actor_id)
        return plan

    @staticmethod
    def create_version(*, workspace_id, plan_id, scenario="baseline", revision_note="",
                       copy_from_version=None, actor_id=None) -> PlanVersion:
        """Create the next version for a scenario (a revision). Optionally copy lines from a prior
        version. The new version becomes ``is_current`` for its scenario."""
        with transaction.atomic():
            plan = (FinancialPlan.objects.select_for_update()
                    .filter(workspace_id=workspace_id, id=plan_id).first())
            if plan is None:
                raise BudgetError("Plan not found.")
            last = (PlanVersion.objects.filter(
                workspace_id=workspace_id, plan=plan, scenario=scenario)
                .order_by("-version_no").first())
            next_no = (last.version_no + 1) if last else 1
            PlanVersion.objects.filter(
                workspace_id=workspace_id, plan=plan, scenario=scenario, is_current=True
            ).update(is_current=False)
            version = PlanVersion.objects.create(
                workspace_id=workspace_id, plan=plan, version_no=next_no, scenario=scenario,
                revision_note=revision_note, is_current=True, status=PlanVersion.DRAFT,
                created_by=_uid(actor_id))
            if copy_from_version:
                src = PlanVersion.objects.filter(
                    workspace_id=workspace_id, id=copy_from_version).first()
                if src is not None:
                    for line in src.lines.all():
                        PlanLine.objects.create(
                            workspace_id=workspace_id, version=version,
                            account_code=line.account_code, dimensions=line.dimensions,
                            period=line.period, period_date=line.period_date, amount=line.amount,
                            currency=line.currency, notes=line.notes, created_by=_uid(actor_id))
        emit_event(workspace_id, "plan_version", version.id,
                   f"{plan.plan_type}.version.created",
                   {"scenario": scenario, "version_no": next_no, "note": revision_note}, actor_id)
        return version

    @staticmethod
    def _editable(workspace_id, version_id) -> PlanVersion:
        version = PlanVersion.objects.filter(workspace_id=workspace_id, id=version_id).first()
        if version is None:
            raise BudgetError("Version not found.")
        if version.status == PlanVersion.LOCKED:
            raise BudgetError("Version is locked; create a new revision to change it.")
        return version

    @staticmethod
    def add_line(*, workspace_id, version_id, account_code, amount, dimensions=None, period="",
                 period_date=None, currency="", notes="", actor_id=None) -> PlanLine:
        version = BudgetService._editable(workspace_id, version_id)
        dims = dimensions or {}
        if dims:
            from apps.dimensions.services import DimensionService
            errors = DimensionService.validate_map(workspace_id, dims, on_date=period_date)
            if errors:
                raise BudgetError(f"Invalid dimensions: {'; '.join(errors)}")
        return PlanLine.objects.create(
            workspace_id=workspace_id, version=version, account_code=str(account_code),
            dimensions=dims, period=period, period_date=period_date, amount=_m(amount),
            currency=currency, notes=notes, created_by=_uid(actor_id))

    @staticmethod
    def allocate(*, workspace_id, version_id, account_code, total, periods, dimensions=None,
                 method="even", weights=None, actor_id=None) -> list[PlanLine]:
        """Spread ``total`` across ``periods`` (list of {period, period_date}) → PlanLines. ``even``
        splits equally (remainder on the last); ``weighted`` uses ``weights``. Budget allocation is a
        SERVICE that generates lines — not an entity."""
        periods = list(periods or [])
        if not periods:
            raise BudgetError("allocate requires at least one period.")
        total = _m(total)
        n = len(periods)
        if method == "weighted" and weights:
            wsum = sum(Decimal(str(w)) for w in weights) or Decimal("1")
            amounts = [_m(total * Decimal(str(weights[i])) / wsum) for i in range(n)]
        else:
            per = _m(total / n)
            amounts = [per] * n
        amounts[-1] = _m(total - sum(amounts[:-1], Decimal("0")))     # absorb rounding on the last
        out = []
        for i, p in enumerate(periods):
            out.append(BudgetService.add_line(
                workspace_id=workspace_id, version_id=version_id, account_code=account_code,
                amount=amounts[i], dimensions=dimensions, period=p.get("period", ""),
                period_date=p.get("period_date"), actor_id=actor_id))
        return out

    @staticmethod
    def submit(*, workspace_id, version_id, actor_id=None) -> PlanVersion:
        with transaction.atomic():
            version = BudgetService._editable(workspace_id, version_id)
            version.status = PlanVersion.SUBMITTED
            version.submitted_by = _uid(actor_id)
            version.submitted_at = timezone.now()
            version.save(update_fields=["status", "submitted_by", "submitted_at", "updated_at"])
        return version

    @staticmethod
    def approve(*, workspace_id, version_id, actor_id=None) -> PlanVersion:
        """Approve a submitted version — segregation of duties: the approver must differ from the
        creator and the submitter."""
        with transaction.atomic():
            version = (PlanVersion.objects.select_for_update()
                       .filter(workspace_id=workspace_id, id=version_id).first())
            if version is None:
                raise BudgetError("Version not found.")
            if version.status not in (PlanVersion.SUBMITTED, PlanVersion.DRAFT):
                raise BudgetError(f"Cannot approve a {version.status} version.")
            approver = _uid(actor_id)
            if approver is not None and approver in (version.created_by, version.submitted_by):
                raise BudgetError("Segregation of duties: approver must differ from creator/submitter.")
            version.status = PlanVersion.APPROVED
            version.approved_by = approver
            version.approved_at = timezone.now()
            version.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])
        emit_event(workspace_id, "plan_version", version.id, "budget.version.approved",
                   {"version_no": version.version_no}, actor_id)
        return version

    @staticmethod
    def lock(*, workspace_id, version_id, actor_id=None) -> PlanVersion:
        with transaction.atomic():
            version = (PlanVersion.objects.select_for_update()
                       .filter(workspace_id=workspace_id, id=version_id).first())
            if version is None:
                raise BudgetError("Version not found.")
            version.status = PlanVersion.LOCKED
            version.save(update_fields=["status", "updated_at"])
        emit_event(workspace_id, "plan_version", version.id, "budget.version.locked",
                   {"version_no": version.version_no}, actor_id)
        return version

    # ── actuals from GL (never duplicated) ──────────────────────────────────────
    @staticmethod
    def _actual(workspace_id, account_code, dimensions, from_date, to_date) -> Decimal:
        """The GL actual for an account (+ optional dimension filter) over a period, in the account's
        natural direction (so it is comparable to a positive budget amount)."""
        from apps.financial_reports.services import StatementService
        acct = LedgerAccount.objects.filter(
            workspace_id=workspace_id, code=str(account_code)).first()
        if acct is None:
            return Decimal("0.00")
        movement = Decimal("0")
        for ln in StatementService._line_qs(
                workspace_id, from_date=from_date, to_date=to_date,
                dimensions=dimensions or None).filter(account_id=acct.id).values(
                "base_debit", "base_credit"):
            movement += ln["base_debit"] - ln["base_credit"]
        natural = movement if normal_balance(acct.account_type) == "debit" else -movement
        return _m(natural)

    @staticmethod
    def budget_vs_actual(*, workspace_id, version_id, from_date=None, to_date=None,
                         group_by_dimension=None) -> dict:
        """Budget (or forecast) vs GL actual per account (optionally split by a dimension value),
        with variance + variance %. ``from_date``/``to_date`` default to the lines' period span."""
        version = PlanVersion.objects.filter(workspace_id=workspace_id, id=version_id).first()
        if version is None:
            raise BudgetError("Version not found.")
        lines = list(version.lines.all())
        if not from_date or not to_date:
            dates = [line.period_date for line in lines if line.period_date]
            from_date = from_date or (min(dates) if dates else None)
            to_date = to_date or (max(dates) if dates else None)
        groups: dict = {}
        for line in lines:
            key_dim = line.dimensions.get(group_by_dimension) if group_by_dimension else ""
            key = (line.account_code, key_dim or "")
            g = groups.setdefault(key, {"budget": Decimal("0"),
                                        "dimensions": dict(line.dimensions)})
            g["budget"] += line.amount
        rows, tb, ta = [], Decimal("0"), Decimal("0")
        for (account_code, dim_val), g in sorted(groups.items()):
            actual = BudgetService._actual(
                workspace_id, account_code,
                {group_by_dimension: dim_val} if (group_by_dimension and dim_val) else None,
                from_date, to_date)
            budget = _m(g["budget"])
            variance = _m(budget - actual)
            pct = (float(_m(variance / budget * 100)) if budget else None)
            tb += budget
            ta += actual
            row = {"account_code": account_code, "budget": str(budget), "actual": str(actual),
                   "variance": str(variance), "variance_pct": pct}
            if group_by_dimension:
                row[group_by_dimension] = dim_val
            rows.append(row)
        return {"plan_type": version.plan.plan_type, "version_id": str(version.id),
                "from": str(from_date) if from_date else None,
                "to": str(to_date) if to_date else None, "rows": rows,
                "total_budget": str(_m(tb)), "total_actual": str(_m(ta)),
                "total_variance": str(_m(tb - ta))}

    @staticmethod
    def utilization(*, workspace_id, version_id, from_date=None, to_date=None) -> dict:
        """Budget utilization: actual/budget %, and remaining, over the whole version."""
        bva = BudgetService.budget_vs_actual(
            workspace_id=workspace_id, version_id=version_id, from_date=from_date, to_date=to_date)
        budget = Decimal(bva["total_budget"])
        actual = Decimal(bva["total_actual"])
        pct = float(_m(actual / budget * 100)) if budget else None
        return {"total_budget": str(budget), "total_actual": str(actual),
                "remaining": str(_m(budget - actual)), "utilization_pct": pct}
