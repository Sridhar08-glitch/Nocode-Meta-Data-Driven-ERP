"""
Consolidation (Financial Platform — F11) — the group-reporting layer over the shared ``companies``
platform (Company/CompanyOwnership) and the single GL.

Consolidation NEVER modifies operational books: a ``ConsolidationRun`` is a first-class, immutable
SNAPSHOT (reruns → new versions; dry-runs; history; audit) of a group's consolidated position at a
date — it reads company balances from the GL, translates functional→presentation currency via the F7
Currency platform, eliminates intercompany balances and computes minority interest, all in the run's
worksheet ``result`` JSON. No elimination/translation journals are posted to the companies' books.
Workspace-scoped (``TenantModel`` + RLS migration 0002).
"""
from django.db import models

from apps.core.models import TenantModel


class ConsolidationRun(TenantModel):
    """An immutable snapshot of a consolidation. ``result`` holds the full worksheet (per-company
    translated balances, eliminations, CTA, minority interest, consolidated trial balance)."""

    DRY_RUN = "dry_run"
    FINAL = "final"
    STATUS_CHOICES = [(DRY_RUN, "Dry Run"), (FINAL, "Final")]

    group_company_id = models.UUIDField(db_index=True)           # → companies.Company (a group node)
    group_code = models.CharField(max_length=32, blank=True)
    as_of = models.DateField(null=True, blank=True)
    presentation_currency = models.CharField(max_length=3, blank=True)
    version_no = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=8, choices=STATUS_CHOICES, default=FINAL)
    balanced = models.BooleanField(default=False)
    company_count = models.PositiveIntegerField(default=0)
    # A COMPACT SUMMARY of the run (presentation currency, totals, eliminations map, balanced flag).
    # The full worksheet DETAIL — every per-company-per-account cell and every consolidated line — is a
    # first-class, queryable child table (``ConsolidationWorksheetLine``), NOT a JSON blob, so an
    # enterprise consolidation (millions of translated balances) stays queryable / auditable / diffable
    # / partially re-runnable. This JSON holds only the small header summary.
    worksheet = models.JSONField(default=dict, blank=True)
    cta = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    total_minority_interest = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "consolidation_runs"
        indexes = [models.Index(fields=["workspace_id", "group_company_id", "as_of"]),
                   models.Index(fields=["workspace_id", "status"])]

    def __str__(self):
        return f"consolidation {self.group_code} @ {self.as_of} v{self.version_no}"


class ConsolidationWorksheetLine(TenantModel):
    """The immutable worksheet DETAIL — a first-class, queryable row per cell of a consolidation run,
    so large consolidations can be queried / audited / diffed / partially re-run without unpacking a
    JSON blob. ``company_code`` empty = a CONSOLIDATED group line (post-elimination + CTA); otherwise
    it is a single company's per-account cell (functional + translated)."""

    run = models.ForeignKey(ConsolidationRun, on_delete=models.CASCADE, related_name="worksheet_lines")
    company_code = models.CharField(max_length=32, blank=True)   # "" = consolidated group total
    account_code = models.CharField(max_length=32)
    account_type = models.CharField(max_length=12, blank=True)
    functional_balance = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    translated_balance = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    eliminated_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    is_cta = models.BooleanField(default=False)

    class Meta:
        db_table = "consolidation_worksheet_lines"
        indexes = [models.Index(fields=["workspace_id", "run", "company_code"]),
                   models.Index(fields=["workspace_id", "run", "account_code"])]

    def __str__(self):
        return f"{self.company_code or 'CONS'}:{self.account_code} {self.translated_balance}"


class TranslationAdjustment(TenantModel):
    """A first-class, PERSISTED record of a company's currency translation within a consolidation run
    (never lost) — the closing/average rates applied and the CTA it produced."""

    run = models.ForeignKey(ConsolidationRun, on_delete=models.CASCADE, related_name="translations")
    company_id = models.UUIDField()
    company_code = models.CharField(max_length=32, blank=True)
    from_currency = models.CharField(max_length=3, blank=True)
    to_currency = models.CharField(max_length=3, blank=True)
    closing_rate = models.DecimalField(max_digits=20, decimal_places=8, default=1)
    average_rate = models.DecimalField(max_digits=20, decimal_places=8, default=1)
    cta_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)

    class Meta:
        db_table = "translation_adjustments"
        indexes = [models.Index(fields=["workspace_id", "run"])]

    def __str__(self):
        return f"xlate {self.company_code} {self.from_currency}->{self.to_currency}"


class MinorityInterest(TenantModel):
    """A first-class, PERSISTED non-controlling-interest disclosure per subsidiary per run (for
    historical reporting + audit) — NOT compute-only."""

    run = models.ForeignKey(ConsolidationRun, on_delete=models.CASCADE, related_name="minorities")
    company_id = models.UUIDField()
    company_code = models.CharField(max_length=32, blank=True)
    ownership_pct = models.DecimalField(max_digits=7, decimal_places=4, default=100)
    minority_pct = models.DecimalField(max_digits=7, decimal_places=4, default=0)
    net_assets = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    minority_amount = models.DecimalField(max_digits=20, decimal_places=2, default=0)
    as_of = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "minority_interests"
        indexes = [models.Index(fields=["workspace_id", "run"]),
                   models.Index(fields=["workspace_id", "company_id"])]

    def __str__(self):
        return f"MI {self.company_code} {self.minority_amount}"
