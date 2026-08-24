"""
Certification Status — the SINGLE source of truth for P2.16 module completion (Module 30).

Every checklist item carries an HONEST status that is backed by evidence:
  - COMPLETE         → has passing automated tests (referenced in `tests`) on BOTH
                       SQLite and PostgreSQL, plus code evidence.
  - PARTIAL          → some coverage exists but the full spec chain is not certified.
  - NOT_IMPLEMENTED  → no dedicated certification yet.
  - OUT_OF_SCOPE     → intentionally not certified here (documented reason).

The certification report (`report.py`) reads THIS module — it never hard-codes "pass".
A meta-test (`tests/test_status.py`) asserts that every `tests` reference on a COMPLETE
item resolves to a real test object in the suite, so the report cannot claim COMPLETE for
a test that does not exist. Combined with the suite being green on both backends, that makes
"COMPLETE" trustworthy.
"""
from __future__ import annotations

from dataclasses import dataclass, field

COMPLETE = "COMPLETE"
PARTIAL = "PARTIAL"
NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
OUT_OF_SCOPE = "OUT_OF_SCOPE"


@dataclass(frozen=True)
class CertItem:
    id: str
    name: str
    module: str
    category: str
    status: str
    # Evidence: test references as "<test_module>.<ClassOrFunc>" — verified to exist by
    # tests/test_status.py. test_module is one of: test_certification, test_registry,
    # test_health, test_status. External-app cert tests are referenced in `code_evidence`.
    tests: list[str] = field(default_factory=list)
    code_evidence: list[str] = field(default_factory=list)
    notes: str = ""


# ── The 32-item certification status (honest, evidence-backed) ───────────────────
CERTIFICATION_STATUS: list[CertItem] = [
    CertItem("INT-01", "Integration Registry exists", "Module 1", "integration", COMPLETE,
             tests=["test_registry.TestIntegrationRegistry"],
             code_evidence=["apps/certification/registry.py::INTEGRATION_REGISTRY"]),
    CertItem("INT-02", "CRM→Quote→Opportunity→Won→Project→Budget→Accounting→Analytics",
             "Module 2", "integration", COMPLETE,
             tests=["test_certification.TestCrmToProjects"],
             code_evidence=["apps/crm/services.py", "apps/projects/services.py"]),
    CertItem("INT-03", "Projects→Assignment→Timesheet→Payroll→Accounting→Analytics",
             "Module 3", "integration", COMPLETE,
             tests=["test_certification.TestProjectsToPayroll"],
             code_evidence=["apps/projects/services.py::CostRollupService"]),
    CertItem("INT-04", "Procurement→Inventory→Accounting", "Module 4", "accounting", COMPLETE,
             tests=["test_certification.TestProcurementInventoryAccounting"],
             code_evidence=["apps/inventory/services.py", "apps/ledger/services.py"]),
    CertItem("INT-05", "Manufacturing E2E MRP→FG→GL", "Module 5", "integration", COMPLETE,
             tests=["test_certification.TestManufacturingE2E"],
             code_evidence=["apps/manufacturing/services.py"]),
    CertItem("INT-06", "HR lifecycle Candidate→Employee→Leave→Payroll→Accounting",
             "Module 6", "integration", COMPLETE,
             tests=["test_certification.TestHrLifecycle", "test_certification.TestHRPayrollAccounting"],
             code_evidence=["apps/hr/services.py"]),
    CertItem("INT-07", "Asset Purchase→Assign→Maintenance→Depreciation→Disposal→Accounting",
             "Module 7", "accounting", COMPLETE,
             tests=["test_certification.TestAssetLifecycle", "test_certification.TestAssetDepreciationGL"],
             code_evidence=["apps/assets/services.py"]),
    CertItem("INT-08", "Helpdesk Ticket→SLA→Escalation→Task→KB→Analytics", "Module 8",
             "integration", COMPLETE,
             tests=["test_certification.TestHelpdeskLifecycle", "test_certification.TestHelpdeskSLA"],
             code_evidence=["apps/helpdesk/services.py", "apps/sla/services.py"]),
    CertItem("INT-09", "Analytics cross-module KPIs", "Module 9", "analytics", COMPLETE,
             tests=["test_certification.TestAnalyticsCrossModule"],
             code_evidence=["apps/analytics/services.py"]),
    CertItem("INT-10", "Environment promotion DEV→PROD", "Module 10", "promotion", COMPLETE,
             tests=["test_certification.TestEnvironmentPromotion"],
             code_evidence=["apps/environments/services.py::PromotionService"]),
    CertItem("INT-11", "Audit chain complete", "Module 11", "audit", COMPLETE,
             tests=["test_certification.TestAuditChain"],
             code_evidence=["apps/eventstore/models.py::DomainEvent"]),
    CertItem("INT-12", "Master data single source", "Module 12", "data_integrity", COMPLETE,
             tests=["test_certification.TestMasterDataSingleSource"],
             code_evidence=["P2_16_INTEGRATION_MAP.md §6"]),
    CertItem("INT-13", "Security RBAC+ABAC+RLS+authorization", "Module 13", "security", COMPLETE,
             tests=["test_certification.TestSecurityCertification"],
             code_evidence=["apps/permissions/services.py", "apps/tenancy/rls.py"]),
    CertItem("INT-14", "Multi-tenant isolation", "Module 14", "security", COMPLETE,
             tests=["test_certification.TestMultiTenantIsolation"],
             code_evidence=["apps/tenancy/rls.py"]),
    CertItem("INT-15", "Failure recovery (no corruption)", "Module 15", "transaction", COMPLETE,
             tests=["test_certification.TestFailureRecovery"],
             code_evidence=["apps/ledger/services.py::emit_post_failure"]),
    CertItem("INT-16", "Idempotency under retry", "Module 16", "transaction", COMPLETE,
             tests=["test_certification.TestIdempotency"]),
    CertItem("INT-17", "Transaction boundary atomicity", "Module 17", "transaction", COMPLETE,
             tests=["test_certification.TestTransactionBoundary"]),
    CertItem("INT-18", "Event integrity (domain events)", "Module 18", "event", COMPLETE,
             tests=["test_certification.TestEventIntegrity"]),
    CertItem("INT-19", "Integration contract validation", "Module 19", "integration", COMPLETE,
             tests=["test_certification.TestIntegrationContracts"]),
    CertItem("INT-20", "API consistency conventions", "Module 20", "api", COMPLETE,
             tests=["test_certification.TestApiConsistency"]),
    CertItem("INT-21", "Workflow status machine", "Module 21", "workflow", COMPLETE,
             tests=["test_certification.TestWorkflowStateMachine"],
             code_evidence=["apps/workflows/services.py"]),
    CertItem("INT-22", "Data integrity (no orphans)", "Module 22", "data_integrity", COMPLETE,
             tests=["test_certification.TestDataIntegrity"],
             code_evidence=["apps/certification/integrity.py"]),
    CertItem("INT-23", "Performance architecture (no N+1)", "Module 23", "performance", COMPLETE,
             tests=["test_certification.TestPerformanceCertification"],
             code_evidence=["apps/certification/performance.py", "P2_16_INTEGRATION_MAP.md §8"]),
    CertItem("INT-24", "Operational health endpoints", "Module 24", "operational", COMPLETE,
             tests=["test_health.TestModuleHealth"],
             code_evidence=["apps/certification/health.py"]),
    CertItem("INT-25", "Upgrade compatibility", "Module 25", "operational", COMPLETE,
             tests=["test_certification.TestUpgradeCompatibility"],
             code_evidence=["apps/solution_templates/services.py::upgrade"]),
    CertItem("INT-26", "ERP health dashboard", "Module 26", "operational", COMPLETE,
             tests=["test_health.TestModuleHealth", "test_health.TestIntegrationHealthAPI"],
             code_evidence=["apps/certification/health.py::module_health"]),
    CertItem("INT-27", "Executive readiness dashboard", "Module 27", "operational", COMPLETE,
             tests=["test_health.TestReadinessSummary"],
             code_evidence=["apps/certification/health.py::readiness_summary"]),
    CertItem("INT-28", "Business simulation suite (5 scenarios)", "Module 28", "integration", COMPLETE,
             tests=["test_certification.TestBusinessSimulations"],
             code_evidence=["apps/certification/simulation.py::SCENARIOS"]),
    CertItem("INT-29", "Enterprise certification tests (SQLite+PG)", "Module 29", "integration", COMPLETE,
             tests=["test_certification", "test_registry", "test_health", "test_status"]),
    CertItem("INT-30", "Certification report generated (data-driven)", "Module 30", "operational", COMPLETE,
             tests=["test_certification.TestCertificationReport"],
             code_evidence=["apps/certification/report.py", "apps/certification/status.py"]),
    CertItem("INT-31", "Architecture validation (single engines)", "Module 31", "architecture", COMPLETE,
             tests=["test_certification.TestArchitectureValidation"],
             code_evidence=["apps/certification/report.py::validate_architecture"]),
    CertItem("INT-32", "Production go-live simulation", "Module 32", "integration", COMPLETE,
             tests=["test_certification.TestProductionGoLiveSimulation"]),
]


# ── aggregation helpers ─────────────────────────────────────────────────────────

def status_counts() -> dict[str, int]:
    counts = {COMPLETE: 0, PARTIAL: 0, NOT_IMPLEMENTED: 0, OUT_OF_SCOPE: 0}
    for item in CERTIFICATION_STATUS:
        counts[item.status] = counts.get(item.status, 0) + 1
    return counts


def overall_status() -> str:
    counts = status_counts()
    if counts[NOT_IMPLEMENTED] or counts[PARTIAL]:
        return PARTIAL if not counts[NOT_IMPLEMENTED] else NOT_IMPLEMENTED
    return COMPLETE


def readiness_score() -> float:
    """Percent of in-scope items that are COMPLETE (OUT_OF_SCOPE excluded from denominator)."""
    in_scope = [i for i in CERTIFICATION_STATUS if i.status != OUT_OF_SCOPE]
    if not in_scope:
        return 0.0
    complete = sum(1 for i in in_scope if i.status == COMPLETE)
    return round(complete / len(in_scope) * 100, 1)


def by_category() -> dict[str, dict]:
    """Compliance roll-up per category for the certification report sections."""
    out: dict[str, dict] = {}
    for item in CERTIFICATION_STATUS:
        bucket = out.setdefault(item.category, {"total": 0, "complete": 0, "items": []})
        bucket["total"] += 1
        if item.status == COMPLETE:
            bucket["complete"] += 1
        bucket["items"].append({"id": item.id, "name": item.name, "status": item.status})
    for bucket in out.values():
        bucket["compliance_pct"] = (
            round(bucket["complete"] / bucket["total"] * 100, 1) if bucket["total"] else 0
        )
    return out


def as_dicts() -> list[dict]:
    return [
        {"id": i.id, "name": i.name, "module": i.module, "category": i.category,
         "status": i.status, "tests": i.tests, "code_evidence": i.code_evidence, "notes": i.notes}
        for i in CERTIFICATION_STATUS
    ]
