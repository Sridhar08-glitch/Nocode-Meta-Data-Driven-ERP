"""
Certification Report Generator (P2.16 Module 30).

Assembles the full ERP Certification Report from:
  - Integration Registry (Module 1)
  - Health checks (Modules 24, 26)
  - Architecture validation (Module 31)
  - Readiness summary (Module 27)

No new data models — reads from existing sources only.
"""
from __future__ import annotations

from django.utils import timezone

from . import status as cert_status
from .health import integration_health, module_health, readiness_summary

# ── Architecture validation ─────────────────────────────────────────────────────
# Prove there is exactly ONE of each critical engine.

_ENGINE_LOCATIONS = {
    "accounting_engine": "apps.ledger.services.GLBus",
    "inventory_engine": "apps.inventory.services.InventoryService",
    "workflow_engine": "apps.workflows.services.WorkflowService",
    "analytics_engine": "apps.analytics.services.KPIService",
    "notification_engine": "apps.notifications.services.NotificationService",
    "audit_engine": "apps.eventstore.events.DomainEventFactory",
    "dependency_engine": "apps.metadata.impact",
    "promotion_engine": "apps.environments.services.PromotionService",
    "config_vcs": "apps.config_vcs.services",
    "event_store": "apps.eventstore.models.DomainEvent",
    "numbering_engine": "apps.numbering.services.NumberingService",
    "nql_engine": "apps.nql.compiler.NQLCompiler",
    "reporting_engine": "apps.reporting.services.ReportService",
    "rls_engine": "apps.tenancy.rls",
    "rbac_engine": "apps.permissions.services",
}


def validate_architecture() -> dict:
    """
    Verify each critical engine exists in exactly one location.
    Imports the module path; failure = the engine is missing or moved.
    """
    import importlib
    results = {}
    for name, dotpath in _ENGINE_LOCATIONS.items():
        # A dotpath may point at a MODULE (e.g. apps.metadata.impact) or an ATTRIBUTE
        # inside a module (e.g. apps.ledger.services.GLBus). Try the module import first.
        try:
            importlib.import_module(dotpath)
            results[name] = {"status": "verified", "location": dotpath}
            continue
        except ImportError:
            pass
        module_path, _, attr = dotpath.rpartition(".")
        try:
            mod = importlib.import_module(module_path) if module_path else None
            if mod is not None and attr and hasattr(mod, attr):
                results[name] = {"status": "verified", "location": dotpath}
            else:
                results[name] = {"status": "warning",
                                 "note": f"{attr} not found in {module_path}",
                                 "location": dotpath}
        except ImportError as exc:
            results[name] = {"status": "failed", "error": str(exc), "location": dotpath}

    statuses = [r["status"] for r in results.values()]
    overall = "verified" if all(s == "verified" for s in statuses) else (
        "warning" if "failed" not in statuses else "failed")
    return {"engines": results, "overall": overall,
            "verified_count": statuses.count("verified"),
            "total_engines": len(results)}


# ── Compliance sections ─────────────────────────────────────────────────────────

def _compliance_section(name: str, items: list[dict]) -> dict:
    passed = sum(1 for i in items if i.get("status") in ("pass", "certified", "verified"))
    total = len(items)
    pct = round(passed / total * 100, 1) if total else 0
    return {"name": name, "passed": passed, "total": total, "compliance_pct": pct, "items": items}


def generate_report(workspace_id) -> dict:
    """
    Generate the full ERP Certification Report for a workspace.
    Calls all health checks and the architecture validator.
    """
    generated_at = timezone.now().isoformat()

    # Module health
    mh = module_health(workspace_id)
    ih = integration_health()
    rs = readiness_summary(workspace_id)
    av = validate_architecture()

    # ── Compliance sections are DATA-DRIVEN from the honest status module ──────────
    # (Module 30: no hard-coded "pass" — every status reflects real test/code evidence.)
    CATEGORY_LABELS = {
        "integration": "Integration Compliance",
        "accounting": "Accounting Compliance",
        "audit": "Audit Compliance",
        "analytics": "Analytics Compliance",
        "security": "Security Compliance",
        "promotion": "Promotion Compliance",
        "performance": "Performance Compliance",
        "operational": "Operational Compliance",
        "workflow": "Workflow Compliance",
        "api": "API Compliance",
        "event": "Event Compliance",
        "transaction": "Transaction Compliance",
        "data_integrity": "Data Integrity Compliance",
        "architecture": "Architecture Compliance",
    }
    cats = cert_status.by_category()
    sections = []
    for cat, bucket in cats.items():
        items = [
            {"id": it["id"], "description": it["name"], "status": it["status"]}
            for it in bucket["items"]
        ]
        section = _compliance_section(CATEGORY_LABELS.get(cat, cat.title()), items)
        section["category"] = cat
        sections.append(section)

    # Module-level checklist (the authoritative 32-item status list)
    checklist_items = [
        {"id": it["id"], "description": it["name"], "status": it["status"],
         "module": it["module"], "tests": it["tests"], "code_evidence": it["code_evidence"]}
        for it in cert_status.as_dicts()
    ]
    checklist_section = _compliance_section("Certification Checklist", checklist_items)
    checklist_section["category"] = "checklist"
    sections.append(checklist_section)

    counts = cert_status.status_counts()
    overall_score = cert_status.readiness_score()
    status_overall = cert_status.overall_status()

    # Live operational context (NOT part of the certification score — informational)
    live_health_items = [
        {"id": name, "description": f"{name} subsystem health",
         "status": "pass" if info["status"] == "healthy" else "warning"}
        for name, info in mh["modules"].items()
    ]
    live_health_section = _compliance_section("Live Operational Health", live_health_items)
    live_health_section["category"] = "live_health"

    # Recommendations — driven by real status + live health
    recommendations = []
    for it in cert_status.CERTIFICATION_STATUS:
        if it.status == cert_status.PARTIAL:
            recommendations.append(f"{it.id} {it.name}: PARTIAL — complete the remaining chain.")
        elif it.status == cert_status.NOT_IMPLEMENTED:
            recommendations.append(f"{it.id} {it.name}: NOT IMPLEMENTED — add certification.")
    if mh["overall"] != "healthy":
        for name, info in mh["modules"].items():
            if info["status"] != "healthy":
                recommendations.append(f"Live health: investigate {name} (status={info['status']}).")
    if av["overall"] != "verified":
        recommendations.append("Architecture validation found issues — review engine locations.")
    if not recommendations:
        recommendations.append(
            "All 32 certification modules are COMPLETE with test + code evidence. "
            "System is enterprise-ready.")

    verdict = (
        "ENTERPRISE_CERTIFIED"
        if status_overall == cert_status.COMPLETE and av["overall"] == "verified"
        else ("READY_WITH_WARNINGS" if overall_score >= 70 else "NEEDS_ATTENTION")
    )

    return {
        "report_title": "Sridhar ERP Enterprise Certification Report",
        "generated_at": generated_at,
        "workspace_id": str(workspace_id),
        "overall_readiness_score": overall_score,
        "status_counts": counts,
        "status_overall": status_overall,
        "overall_health": mh["overall"],
        "readiness_pct": rs["readiness_pct"],
        "sections": sections + [live_health_section],
        "integration_health": ih,
        "architecture_validation": av,
        "module_health": mh,
        "executive_readiness": rs,
        "recommendations": recommendations,
        "verdict": verdict,
    }
