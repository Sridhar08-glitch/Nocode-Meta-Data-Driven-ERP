"""
Company — the shared PLATFORM legal-entity object (introduced for F11, but platform-owned).

A ``Company`` is a legal entity INSIDE a workspace (Workspace = Tenant stays frozen; RLS by
``workspace_id`` unchanged — companies never span workspaces). It lives in this foundational app — NOT
inside Finance — and is a PURE ORGANIZATIONAL PRIMITIVE: it carries legal/organizational identity ONLY
(code, name, parent group tree, legal registration, functional currency, fiscal-calendar reference,
active/group/elimination/default flags) plus its ``CompanyOwnership`` + ``CompanyTaxRegistration``
children. It has NO accounting/finance behaviour — no GL accounts, ledgers, journals, posting rules,
statements, budgets or reconciliation. Finance (and HR, Procurement, Manufacturing, Hospital,
Government…) all REFERENCE this one object; none inherits accounting semantics and none invents another
legal-entity model. Per-company GL account mappings belong to Finance (``ledger.AccountingSettings``).

``parent`` builds the group tree (an ``is_group`` node is a consolidation head); ``CompanyOwnership`` is
the TEMPORAL parent→subsidiary ownership relationship (percentages change over time → a first-class
relationship, enabling minority interest).
"""
from django.db import models

from apps.core.models import TenantModel


class Company(TenantModel):
    """A legal entity within a workspace."""

    code = models.CharField(max_length=32)
    name = models.CharField(max_length=200)
    functional_currency = models.CharField(max_length=3, blank=True)   # this entity's books currency
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL,
                               related_name="children")
    is_group = models.BooleanField(default=False)        # a consolidation-group node (not operational)
    is_elimination = models.BooleanField(default=False)  # elimination/adjustment entity
    is_default = models.BooleanField(default=False)      # the workspace's default company (legacy null)

    legal_registration = models.CharField(max_length=64, blank=True)
    # Tax registrations are a first-class child entity (CompanyTaxRegistration), NOT a JSON blob —
    # multiple registrations, effective-dated, per authority/jurisdiction.
    fiscal_calendar_ref = models.CharField(max_length=64, blank=True)  # → an AccountingPeriod fiscal_year
    # NOTE: this platform object carries NO finance/accounting behaviour. Per-company GL account
    # mappings (retained earnings / CTA / intercompany) belong to Finance, resolved from
    # ``ledger.AccountingSettings`` (per-company overrides = a future Finance-side extension), so HR /
    # Procurement / Manufacturing / Hospital / Government can reference a Company without inheriting
    # accounting semantics.
    is_active = models.BooleanField(default=True)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "companies"
        unique_together = [("workspace_id", "code")]
        indexes = [models.Index(fields=["workspace_id", "code"]),
                   models.Index(fields=["workspace_id", "parent"]),
                   models.Index(fields=["workspace_id", "is_default"])]

    def __str__(self):
        return f"{self.code} {self.name}"


class CompanyTaxRegistration(TenantModel):
    """A legal entity's tax registration — a first-class, effective-dated record (NOT JSON), so a
    company can hold many registrations (VAT/GST/corporate/payroll/import/export, country-specific)."""

    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="tax_registrations")
    tax_type = models.CharField(max_length=20, default="vat", choices=[
        ("vat", "VAT"), ("gst", "GST"), ("corporate_tax", "Corporate Tax"),
        ("payroll_tax", "Payroll Tax"), ("import", "Import"), ("export", "Export"),
        ("withholding", "Withholding"), ("other", "Other")])
    authority = models.CharField(max_length=120, blank=True)
    jurisdiction = models.CharField(max_length=64, blank=True)         # country / state
    registration_number = models.CharField(max_length=64, blank=True)
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=12, default="active", choices=[
        ("active", "Active"), ("suspended", "Suspended"), ("expired", "Expired")])
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "company_tax_registrations"
        indexes = [models.Index(fields=["workspace_id", "company", "tax_type"])]

    def __str__(self):
        return f"{self.company_id} {self.tax_type} {self.registration_number}"


class CompanyOwnership(TenantModel):
    """The TEMPORAL ownership of a subsidiary by a parent (percentages change over time). A first-class
    relationship (the Relationship-Review gate): enables minority interest + ownership-as-of-a-date.
    ``relationship_type`` distinguishes subsidiary / associate / joint venture; ``voting_pct`` may
    differ from economic ``ownership_pct``."""

    parent_company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="owns")
    subsidiary = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="owned_by")
    ownership_pct = models.DecimalField(max_digits=7, decimal_places=4, default=100)   # economic %
    voting_pct = models.DecimalField(max_digits=7, decimal_places=4, null=True, blank=True)
    relationship_type = models.CharField(max_length=16, default="subsidiary", choices=[
        ("subsidiary", "Subsidiary"), ("associate", "Associate"),
        ("joint_venture", "Joint Venture"), ("minority", "Minority")])
    is_direct = models.BooleanField(default=True)                      # direct vs indirect holding
    effective_from = models.DateField(null=True, blank=True)
    effective_to = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "company_ownership"
        indexes = [models.Index(fields=["workspace_id", "subsidiary", "effective_from"]),
                   models.Index(fields=["workspace_id", "parent_company"])]

    def __str__(self):
        return f"{self.parent_company_id}→{self.subsidiary_id} {self.ownership_pct}%"
