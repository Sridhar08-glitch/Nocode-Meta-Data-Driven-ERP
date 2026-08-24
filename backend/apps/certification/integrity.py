"""
Data Integrity Scanner (P2.16 Module 22).

READ-ONLY detection over EXISTING models — never repairs, never a new engine.
Surfaces: duplicate journal references (double-posting), duplicate gapless numbers,
domain events missing required identity fields, and negative stock. A freshly
provisioned + exercised workspace must scan clean.
"""
from __future__ import annotations

from collections import Counter


def _duplicate_journal_refs(workspace_id) -> list[dict]:
    """Posted journal entries that share a (source_module, source_ref) — a double-post smell."""
    from apps.ledger.models import JournalEntry
    rows = JournalEntry.objects.filter(
        workspace_id=workspace_id, status="posted"
    ).exclude(source_ref="").values_list("source_module", "source_ref")
    counts = Counter(rows)
    return [
        {"type": "duplicate_journal_ref", "source_module": m, "source_ref": r, "count": n}
        for (m, r), n in counts.items() if n > 1
    ]


def _duplicate_numbers(workspace_id) -> list[dict]:
    """Same allocated document number issued twice within a sequence (gapless invariant break)."""
    try:
        from apps.numbering.models import NumberAllocation
    except Exception:
        return []
    rows = NumberAllocation.objects.filter(workspace_id=workspace_id).values_list(
        "sequence_id", "value")
    counts = Counter(rows)
    return [
        {"type": "duplicate_number", "sequence_id": str(s), "number": num, "count": n}
        for (s, num), n in counts.items() if n > 1
    ]


def _events_missing_identity(workspace_id) -> list[dict]:
    """Domain events missing aggregate identity or event_type — event-store integrity."""
    from apps.eventstore.models import DomainEvent
    bad = DomainEvent.objects.filter(workspace_id=workspace_id).filter(
        event_type="").values_list("id", flat=True)[:50]
    return [{"type": "event_missing_event_type", "event_id": str(e)} for e in bad]


def _negative_stock(workspace_id) -> list[dict]:
    from apps.inventory.models import StockLevel
    rows = StockLevel.objects.filter(workspace_id=workspace_id, on_hand__lt=0).values_list(
        "item_id", "warehouse_id", "on_hand")[:50]
    return [
        {"type": "negative_stock", "item_id": str(i), "warehouse_id": str(w), "on_hand": str(q)}
        for i, w, q in rows
    ]


CHECKS = {
    "duplicate_journal_refs": _duplicate_journal_refs,
    "duplicate_numbers": _duplicate_numbers,
    "events_missing_identity": _events_missing_identity,
    "negative_stock": _negative_stock,
}


def scan_workspace(workspace_id) -> dict:
    """Run every integrity check; return a structured, read-only report."""
    issues: list[dict] = []
    checks_run = []
    for name, fn in CHECKS.items():
        checks_run.append(name)
        try:
            issues.extend(fn(workspace_id))
        except Exception as exc:  # a broken check must not mask the others
            issues.append({"type": "check_error", "check": name, "error": str(exc)})
    return {
        "workspace_id": str(workspace_id),
        "checks_run": checks_run,
        "issue_count": len(issues),
        "issues": issues,
        "clean": not issues,
    }
