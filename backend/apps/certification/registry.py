"""
Integration Registry (P2.16 Module 1).

Declares EVERY known cross-module integration in one place.  Nothing is
discovered at runtime here — this is documentation-as-code.  The health
checker and certification reporter read this registry to know what to verify.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Integration:
    source_module: str
    target_module: str
    service: str
    trigger: str
    event: str
    accounting_impact: str = ""
    analytics_impact: str = ""
    audit_events: list[str] = field(default_factory=list)
    notification_slugs: list[str] = field(default_factory=list)
    promotion_impact: str = ""
    idempotency_guard: str = ""
    status: str = "certified"  # certified | deferred | partial


INTEGRATION_REGISTRY: list[Integration] = [
    # ── CRM ────────────────────────────────────────────────────────────────
    Integration(
        source_module="crm",
        target_module="projects",
        service="CRMService.win_opportunity → workflow action_create_record",
        trigger="crm.opportunity.won domain event",
        event="crm.opportunity.won",
        audit_events=["crm.opportunity.won"],
        analytics_impact="revenue KPI increases",
    ),
    Integration(
        source_module="crm",
        target_module="helpdesk",
        service="ticket.customer lookup → CRM account record",
        trigger="TicketService.create_ticket (customer field)",
        event="ticket.created",
        audit_events=["ticket.created"],
    ),
    # ── Procurement → Inventory → Accounting ───────────────────────────────
    Integration(
        source_module="procurement",
        target_module="inventory",
        service="ProcurementService.post_goods_receipt → InventoryService.receive",
        trigger="POST /api/v1/procurement/goods-receipts/{id}/post/",
        event="procurement.receipt.posted",
        accounting_impact="Dr 1300 Inventory / Cr 2050 GRNI",
        audit_events=["procurement.receipt.posted", "inventory.received"],
        idempotency_guard="GoodsReceipt.status==posted guard",
        status="certified",
    ),
    Integration(
        source_module="procurement",
        target_module="ledger",
        service="ProcurementService.post_vendor_bill → GLBus.post_event('vendor_bill.posted')",
        trigger="POST /api/v1/procurement/vendor-bills/{id}/post/",
        event="procurement.bill.posted",
        accounting_impact="Dr 2050 GRNI / Cr 2000 AP",
        audit_events=["procurement.bill.posted", "ledger.journal_entry.posted"],
        idempotency_guard="VendorBill.status==posted guard",
        status="certified",
    ),
    # ── Inventory → Accounting ─────────────────────────────────────────────
    Integration(
        source_module="inventory",
        target_module="ledger",
        service="InventoryService.receive/issue → GLBus.post_event",
        trigger="Any inventory movement with post_gl=True",
        event="inventory.received / inventory.issued / inventory.adjusted",
        accounting_impact="PostingRule-driven journal entries",
        audit_events=["inventory.received", "inventory.issued", "inventory.adjusted",
                      "ledger.journal_entry.posted"],
        idempotency_guard="StockLevel select_for_update",
        status="certified",
    ),
    # ── Manufacturing ──────────────────────────────────────────────────────
    Integration(
        source_module="manufacturing",
        target_module="inventory",
        service="ProductionOrderService → InventoryService.issue + InventoryService.receive",
        trigger="release_order (issue materials) / complete_order (receive FG)",
        event="manufacturing.order.released / manufacturing.order.completed",
        accounting_impact="Dr 1700 WIP / Cr 1300 on issue; Dr 1400 FG / Cr 1700 on complete",
        audit_events=["manufacturing.order.released", "manufacturing.order.completed",
                      "inventory.issued", "inventory.received"],
        idempotency_guard="ProductionOrder.status state machine; post_gl=False to avoid double-post",
        status="certified",
    ),
    Integration(
        source_module="manufacturing",
        target_module="procurement",
        service="MRPService.run_mrp → MRPResult(action=purchase)",
        trigger="POST /api/v1/manufacturing/mrp/run",
        event="manufacturing.mrp.completed",
        audit_events=["manufacturing.mrp.completed"],
        status="certified",
    ),
    # ── HR → Payroll ──────────────────────────────────────────────────────
    Integration(
        source_module="hr",
        target_module="payroll",
        service="EmployeePayrollProfile.employee_record_id → HR employee record",
        trigger="PayrollService.calculate_run reads SalaryStructureAssignment",
        event="hr.employee.created → payroll profile creation",
        audit_events=["hr.employee.created", "payroll.run.calculated"],
        idempotency_guard="SalaryStructureAssignment effective_date ordering",
    ),
    # ── Payroll → Accounting ───────────────────────────────────────────────
    Integration(
        source_module="payroll",
        target_module="ledger",
        service="PayrollService.post_run → GLBus.post (multi-line)",
        trigger="POST /api/v1/payroll/runs/{id}/post/",
        event="payroll.run.posted",
        accounting_impact="Dr 6000 Salaries / Cr 2100 Net Pay + deduction liabilities",
        audit_events=["payroll.run.posted", "ledger.journal_entry.posted"],
        idempotency_guard="PayrollRun.status==posted guard; SoD creator≠approver≠poster",
        status="certified",
    ),
    # ── Projects → Payroll + Accounting ───────────────────────────────────
    Integration(
        source_module="projects",
        target_module="payroll",
        service="CostRollupService.rollup_project reads Payslip.gross_pay for labour",
        trigger="POST /api/v1/projects/projects/{id}/rollup/",
        event="project.cost.rolled_up",
        audit_events=["project.timesheet.approved", "project.cost.rolled_up"],
        idempotency_guard="ProjectCostEntry reference UniqueConstraint",
        status="certified",
    ),
    Integration(
        source_module="projects",
        target_module="ledger",
        service="CostRollupService.post_cost → GLBus.post_event (if PostingRule exists)",
        trigger="CostRollupService.post_cost(post_gl=True)",
        event="project.cost.posted",
        accounting_impact="optional WIP posting",
        audit_events=["project.cost.posted"],
        idempotency_guard="ProjectCostEntry reference get_or_create",
        status="certified",
    ),
    # ── Assets → Accounting ────────────────────────────────────────────────
    Integration(
        source_module="assets",
        target_module="ledger",
        service="DepreciationService.run_period + DisposalService.dispose → GLBus.post",
        trigger="POST /api/v1/assets/depreciation/schedules/{id}/run/",
        event="asset.depreciation.posted / asset.disposed",
        accounting_impact="Dr 6100 Dep Exp / Cr 1600 Acc Dep; Dr cash / Cr asset on disposal",
        audit_events=["asset.depreciation.posted", "asset.disposed", "ledger.journal_entry.posted"],
        idempotency_guard="DepreciationEntry unique(schedule+period); DisposalRecord unique(ws+asset+kind)",
        status="certified",
    ),
    Integration(
        source_module="assets",
        target_module="helpdesk",
        service="ticket.asset lookup → Assets asset record",
        trigger="TicketService.create_ticket (asset field)",
        event="ticket.created",
        audit_events=["ticket.created"],
    ),
    Integration(
        source_module="assets",
        target_module="procurement",
        service="asset.vendor lookup → Procurement vendor record",
        trigger="AssetService.create_asset (vendor field)",
        event="asset.created",
        audit_events=["asset.created"],
    ),
    # ── HR → Projects ──────────────────────────────────────────────────────
    Integration(
        source_module="hr",
        target_module="projects",
        service="project_member.employee lookup → HR employee record",
        trigger="RecordService.create_record on project_member",
        event="record.created (project_member)",
        audit_events=["record.created"],
    ),
    # ── Analytics ← All ────────────────────────────────────────────────────
    Integration(
        source_module="analytics",
        target_module="all_modules",
        service="KPIService.evaluate → execute_nql / native registry",
        trigger="GET /api/v1/analytics/kpis/{code}/value",
        event="analytics.snapshot.created",
        analytics_impact="THE single analytics path; no second engine",
        audit_events=["analytics.report.executed", "analytics.snapshot.created"],
        status="certified",
    ),
    # ── Environments ← Config VCS ──────────────────────────────────────────
    Integration(
        source_module="environments",
        target_module="config_vcs",
        service="PromotionService → vcs.diff_commits / vcs.merge / vcs.rollback",
        trigger="POST /api/v1/environments/packages/{id}/execute/",
        event="promotion.executed",
        audit_events=["promotion.created", "promotion.approved", "promotion.executed",
                      "promotion.rolled_back"],
        idempotency_guard="PromotionPackage.package_hash; PROD requires approved",
        status="certified",
    ),
    Integration(
        source_module="environments",
        target_module="dependency",
        service="PromotionService.create_package → AnalysisService.promotion_precheck",
        trigger="POST /api/v1/environments/packages/",
        event="dependency.promotion.blocked / dependency.promotion.approved",
        audit_events=["dependency.promotion.blocked", "dependency.promotion.approved"],
        status="certified",
    ),
    # ── Solution Templates (install-time provisioning) ─────────────────────
    Integration(
        source_module="solution_templates",
        target_module="ledger",
        service="_install_manifest → provision_accounting (idempotent)",
        trigger="SolutionTemplateService.install",
        event="solution_template.installed",
        accounting_impact="seeds standard chart + PostingRules for every new workspace",
        audit_events=["solution_template.installed"],
        status="certified",
    ),
    # ── SLA → Helpdesk ─────────────────────────────────────────────────────
    Integration(
        source_module="helpdesk",
        target_module="sla",
        service="TicketService.create_ticket → SLAService.attach_policies",
        trigger="POST /api/v1/helpdesk/",
        event="sla.warning / sla.breached (from beat task)",
        audit_events=["ticket.created"],
        notification_slugs=["sla_warning", "sla_breached"],
        status="certified",
    ),
]


# Quick lookup maps
BY_SOURCE: dict[str, list[Integration]] = {}
BY_TARGET: dict[str, list[Integration]] = {}
for _i in INTEGRATION_REGISTRY:
    BY_SOURCE.setdefault(_i.source_module, []).append(_i)
    BY_TARGET.setdefault(_i.target_module, []).append(_i)


def integrations_from(module: str) -> list[Integration]:
    return BY_SOURCE.get(module, [])


def integrations_to(module: str) -> list[Integration]:
    return BY_TARGET.get(module, [])


def all_certified() -> list[Integration]:
    return [i for i in INTEGRATION_REGISTRY if i.status == "certified"]


# ── Certification checklist ────────────────────────────────────────────────────
CERTIFICATION_CHECKLIST: list[dict] = [
    {"id": "INT-01", "name": "Integration Registry exists", "module": "Module 1"},
    {"id": "INT-02", "name": "CRM→Projects linkage", "module": "Module 2"},
    {"id": "INT-03", "name": "Projects→Payroll cost rollup", "module": "Module 3"},
    {"id": "INT-04", "name": "Procurement→Inventory→Accounting", "module": "Module 4"},
    {"id": "INT-05", "name": "Manufacturing E2E MRP→FG→GL", "module": "Module 5"},
    {"id": "INT-06", "name": "HR lifecycle→Payroll", "module": "Module 6"},
    {"id": "INT-07", "name": "Asset depreciation→GL", "module": "Module 7"},
    {"id": "INT-08", "name": "Helpdesk SLA integration", "module": "Module 8"},
    {"id": "INT-09", "name": "Analytics cross-module KPIs", "module": "Module 9"},
    {"id": "INT-10", "name": "Environment promotion DEV→PROD", "module": "Module 10"},
    {"id": "INT-11", "name": "Audit chain complete", "module": "Module 11"},
    {"id": "INT-12", "name": "Master data single source", "module": "Module 12"},
    {"id": "INT-13", "name": "Security RBAC+ABAC+RLS", "module": "Module 13"},
    {"id": "INT-14", "name": "Multi-tenant isolation", "module": "Module 14"},
    {"id": "INT-15", "name": "Failure recovery (no corruption)", "module": "Module 15"},
    {"id": "INT-16", "name": "Idempotency under retry", "module": "Module 16"},
    {"id": "INT-17", "name": "Transaction boundary atomicity", "module": "Module 17"},
    {"id": "INT-18", "name": "Event integrity (domain events)", "module": "Module 18"},
    {"id": "INT-19", "name": "Integration contract validation", "module": "Module 19"},
    {"id": "INT-20", "name": "API consistency conventions", "module": "Module 20"},
    {"id": "INT-21", "name": "Workflow status machine", "module": "Module 21"},
    {"id": "INT-22", "name": "Data integrity (no orphans)", "module": "Module 22"},
    {"id": "INT-23", "name": "Performance architecture (no N+1)", "module": "Module 23"},
    {"id": "INT-24", "name": "Operational health endpoints", "module": "Module 24"},
    {"id": "INT-25", "name": "Upgrade compatibility", "module": "Module 25"},
    {"id": "INT-26", "name": "ERP health dashboard", "module": "Module 26"},
    {"id": "INT-27", "name": "Executive readiness dashboard", "module": "Module 27"},
    {"id": "INT-28", "name": "Business simulation suite", "module": "Module 28"},
    {"id": "INT-29", "name": "Enterprise certification tests", "module": "Module 29"},
    {"id": "INT-30", "name": "Certification report generated", "module": "Module 30"},
    {"id": "INT-31", "name": "Architecture validation (single engines)", "module": "Module 31"},
    {"id": "INT-32", "name": "Production go-live simulation", "module": "Module 32"},
]
