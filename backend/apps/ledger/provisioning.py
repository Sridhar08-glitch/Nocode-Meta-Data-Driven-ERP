"""
Accounting auto-provisioning (Phase P2.15 remediation — Blocker 1).

A workspace that installs any finance-touching solution gets a ready-to-post accounting setup
with NO manual API calls: the standard chart of accounts, the default account mappings
(``AccountingSettings``), and the default ``PostingRule`` set for the event-driven posters
(inventory + vendor bill). Everything here is idempotent and safe to re-run.

This REUSES the existing ledger primitives (``seeding.seed_standard_chart``, ``PostingRule``,
``AccountingSettings``) — it is wiring, not a new engine.
"""
from __future__ import annotations

from .models import AccountingSettings, PostingRule
from .seeding import ACCOUNT_DEFAULTS, seed_standard_chart


def ensure_accounting_settings(workspace_id, *, actor_id=None) -> AccountingSettings:
    """Idempotently return the workspace ``AccountingSettings`` row, seeded with the standard
    account mapping defaults. Finance services call this to resolve the codes they post to."""
    settings, _ = AccountingSettings.objects.get_or_create(
        workspace_id=workspace_id,
        defaults={**ACCOUNT_DEFAULTS,
                  "created_by": actor_id if actor_id else None})
    return settings


def _default_rules(settings: AccountingSettings) -> dict[str, list[dict]]:
    """The default journal templates for the event-driven posters, built from the workspace's
    account mappings. ``account_field`` lets a per-item account override the mapped default when
    present in the event context (e.g. ``Item.inventory_account_code``)."""
    inv = settings.default_inventory_account
    cogs = settings.default_cogs_account
    grni = settings.default_grni_account
    ap = settings.default_payable_account
    return {
        # Stock received → Dr Inventory / Cr GRNI (clearing; the vendor bill clears GRNI→AP).
        "inventory.received": [
            {"account_field": "inventory_account_code", "account_code": inv,
             "side": "debit", "amount_field": "amount"},
            {"account_code": grni, "side": "credit", "amount_field": "amount"},
        ],
        # Stock issued/consumed → Dr COGS / Cr Inventory.
        "inventory.issued": [
            {"account_field": "cogs_account_code", "account_code": cogs,
             "side": "debit", "amount_field": "amount"},
            {"account_field": "inventory_account_code", "account_code": inv,
             "side": "credit", "amount_field": "amount"},
        ],
        # Positive stock adjustment → Dr Inventory / Cr COGS.
        "inventory.adjusted": [
            {"account_code": inv, "side": "debit", "amount_field": "amount"},
            {"account_code": cogs, "side": "credit", "amount_field": "amount"},
        ],
        # Vendor bill posted → Dr GRNI / Cr Accounts Payable (clears the receipt accrual).
        "vendor_bill.posted": [
            {"account_code": grni, "side": "debit", "amount_field": "amount"},
            {"account_code": ap, "side": "credit", "amount_field": "amount"},
        ],
    }


def ensure_default_posting_rules(workspace_id, *, actor_id=None) -> int:
    """Idempotently create the default ``PostingRule`` set. Returns the number created.
    An existing rule for an event type is left untouched (admins may customise it)."""
    settings = ensure_accounting_settings(workspace_id, actor_id=actor_id)
    created = 0
    for event_type, template in _default_rules(settings).items():
        _, was_created = PostingRule.objects.get_or_create(
            workspace_id=workspace_id, event_type=event_type,
            defaults={"name": event_type, "template": template, "is_active": True,
                      "created_by": actor_id if actor_id else None})
        if was_created:
            created += 1
    return created


def provision_accounting(workspace_id, *, actor_id=None) -> dict:
    """THE single entry point: make a workspace ready to post to the GL with zero manual setup.
    Seeds the standard chart, the account mappings, and the default posting rules. Idempotent.

    Fiscal periods are intentionally NOT seeded here — ``GLBus`` posts without a period (the
    period covering a date is optional), and a wrongly-closed seeded period would block posting.
    Fiscal years are managed explicitly via the ledger API."""
    chart = seed_standard_chart(workspace_id, created_by=actor_id if actor_id else None)
    ensure_accounting_settings(workspace_id, actor_id=actor_id)
    rules_created = ensure_default_posting_rules(workspace_id, actor_id=actor_id)
    # F11 — every finance workspace gets an explicit DEFAULT legal entity (the company that
    # ``company_id=NULL`` journals belong to), so it is consolidation-ready with zero manual setup.
    try:
        from apps.companies.services import CompanyService
        CompanyService.ensure_default_company(workspace_id=workspace_id, actor_id=actor_id)
    except Exception:  # noqa: BLE001 — companies app optional; provisioning must not fail on it
        pass
    return {"accounts_created": chart["created"], "posting_rules_created": rules_created}
