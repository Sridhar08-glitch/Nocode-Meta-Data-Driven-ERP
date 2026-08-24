"""
Financial Dimension Framework (Financial Platform — F9) — the generic, reusable Core capability for
analytical tagging of financial transactions: cost centers, profit centers, business units, segments,
departments, regions, funds, grants, channels — and ANY custom dimension — WITHOUT per-dimension
entities or schema redesign.

GENERALIZATION (6/7-point): every dimension shares one structure (code, name, hierarchy, effective
dates, active flag) and differs only by TYPE — so there is ONE ``FinancialDimension`` (the type
definition) + ``FinancialDimensionValue`` (its hierarchical values). Cost-center/profit-center/region/
fund/… are seeded dimension INSTANCES, not tables. Dimensions are NOT accounting — GL stays the owner;
dimensions are metadata attached to ``JournalLine.dimensions`` (a JSON map) that Budgets, Forecasts,
Consolidation, Analytics, Reporting and Statements all consume. Workspace-scoped (RLS migration 0002).
"""
from django.db import models

from apps.core.models import TenantModel

# Standard classifiers (a hint for analytics; ``other`` covers any custom dimension).
DIMENSION_TYPES = [
    ("cost_center", "Cost Center"), ("profit_center", "Profit Center"),
    ("business_unit", "Business Unit"), ("department", "Department"), ("division", "Division"),
    ("segment", "Segment"), ("geography", "Geography"), ("fund", "Fund"), ("grant", "Grant"),
    ("program", "Program"), ("project", "Project"), ("channel", "Channel"),
    ("product_line", "Product Line"), ("location", "Location"), ("other", "Custom / Other"),
]


class FinancialDimension(TenantModel):
    """A dimension TYPE definition (e.g. ``cost_center``, ``region``). The single generic entity —
    every analytical axis is a row here, never its own table."""

    code = models.SlugField(max_length=32)               # "cost_center", "region", "fund"
    name = models.CharField(max_length=120)
    dimension_type = models.CharField(max_length=16, choices=DIMENSION_TYPES, default="other")
    is_required = models.BooleanField(default=False)     # must be present on a dimensioned posting
    is_hierarchical = models.BooleanField(default=False)
    allow_posting = models.BooleanField(default=True)    # taggable on journal lines
    sequence = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "financial_dimensions"
        unique_together = [("workspace_id", "code")]
        indexes = [models.Index(fields=["workspace_id", "code"]),
                   models.Index(fields=["workspace_id", "dimension_type"])]

    def __str__(self):
        return f"{self.code} ({self.name})"


class FinancialDimensionValue(TenantModel):
    """A value within a dimension (e.g. cost_center ``CC100 Marketing``), with optional parent for a
    hierarchy and effective dates. Values — not the dimension — are what a transaction is tagged with."""

    dimension = models.ForeignKey(FinancialDimension, on_delete=models.CASCADE,
                                  related_name="values")
    code = models.CharField(max_length=64)
    name = models.CharField(max_length=200)
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="children")
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "financial_dimension_values"
        unique_together = [("workspace_id", "dimension", "code")]
        indexes = [models.Index(fields=["workspace_id", "dimension", "code"]),
                   models.Index(fields=["workspace_id", "dimension", "is_active"])]

    def __str__(self):
        return f"{self.dimension_id}:{self.code}"
