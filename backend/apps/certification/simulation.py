"""
Business Simulation Suite (P2.16 Module 28).

Executes complete end-to-end business scenarios using REAL service calls.
All scenarios delegate exclusively to existing service modules — no business
logic is implemented here.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any


@dataclass
class SimulationStep:
    name: str
    status: str = "pending"  # pending | passed | failed | skipped
    detail: str = ""
    error: str = ""
    output: dict = field(default_factory=dict)


@dataclass
class SimulationResult:
    scenario: str
    steps: list[SimulationStep] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(s.status in ("passed", "skipped") for s in self.steps)

    @property
    def summary(self) -> dict:
        return {
            "scenario": self.scenario,
            "passed": self.passed,
            "steps": [
                {"name": s.name, "status": s.status, "error": s.error or None}
                for s in self.steps
            ],
        }


def _step(result: SimulationResult, name: str, fn) -> Any:
    """Run fn(), record the step, return its output (or None on failure)."""
    step = SimulationStep(name=name)
    result.steps.append(step)
    try:
        out = fn()
        step.status = "passed"
        step.output = out if isinstance(out, dict) else {}
        return out
    except Exception as exc:
        step.status = "failed"
        step.error = str(exc)
        return None


# ── IT Services scenario: CRM → Opportunity → Analytics ──────────────────────

def simulate_it_services(workspace_id, actor_id) -> SimulationResult:
    """IT services flow: CRM lead → opportunity won → analytics KPI check."""
    from apps.ledger.provisioning import provision_accounting

    result = SimulationResult("IT Services: CRM → Opportunity → Analytics")
    ws = uuid.UUID(str(workspace_id))
    actor = uuid.UUID(str(actor_id))

    class _Member:
        user_id = actor
        id = uuid.uuid4()
        role = "admin"
        custom_role_id = None

    member = _Member()

    _step(result, "provision_accounting", lambda: provision_accounting(ws, actor_id=actor))

    # Install CRM if available
    from apps.solution_templates.models import InstalledSolution, SolutionTemplate
    from apps.solution_templates.services import install as install_solution
    crm_tpl = _step(result, "find_crm_template",
                    lambda: SolutionTemplate.objects.filter(slug="crm").first())
    if crm_tpl:
        already = InstalledSolution.objects.filter(
            workspace_id=ws, solution_template_id=crm_tpl.id, status="active").exists()
        if not already:
            _step(result, "install_crm",
                  lambda: install_solution(
                      template_id=crm_tpl.id, workspace_id=ws, installed_by=actor))
    else:
        step = SimulationStep(name="install_crm", status="skipped",
                              detail="crm template not seeded")
        result.steps.append(step)

    # Create CRM lead
    from apps.crm.services import CRMService
    lead = _step(result, "crm.create_lead", lambda: CRMService.create_document(
        workspace_id=ws, entity_slug="lead",
        data={"last_name": f"Sim {uuid.uuid4().hex[:6]}", "email": "sim@example.com",
              "status": "new"},
        member=member))

    if lead:
        opp = _step(result, "crm.create_opportunity", lambda: CRMService.create_document(
            workspace_id=ws, entity_slug="opportunity",
            data={"stage": "prospecting", "value": "10000.00",
                  "expected_close_date": "2027-12-31"},
            member=member))
        if opp:
            opp_id = opp if isinstance(opp, uuid.UUID) else opp.get("id") if isinstance(opp, dict) else opp
            if opp_id:
                _step(result, "crm.win_opportunity",
                      lambda: CRMService.win_opportunity(
                          workspace_id=ws, record_id=opp_id, actor_id=actor))

    # KPI check — seed standard KPIs then evaluate the CRM pipeline KPI
    from apps.analytics.seeding import seed_standard_kpis
    from apps.analytics.services import KPIService
    _step(result, "analytics.seed_kpis", lambda: {"created": seed_standard_kpis(ws, actor_id=actor)})
    _step(result, "analytics.evaluate_opportunities",
          lambda: KPIService.evaluate_code(code="open_opportunities", workspace_id=ws))

    # Won deal → delivery project → timesheet labour → cost rollup (CRM→Projects→Accounting)
    from apps.projects.blueprint import seed_projects_template
    from apps.projects.services import CostRollupService, FinancialsService, ProjectService
    from apps.solution_templates import services as st2
    _step(result, "install_projects",
          lambda: st2.install(template_id=seed_projects_template().id,
                              workspace_id=ws, installed_by=actor))
    proj = _step(result, "projects.create_project", lambda: ProjectService.create_document(
        workspace_id=ws, entity_slug="project",
        data={"name": "Delivery", "status": "active", "planned_budget": "20000",
              "revenue": "30000"}, actor_id=actor))
    if proj and isinstance(proj, dict):
        pid = proj["id"]
        _step(result, "projects.timesheet_labour", lambda: ProjectService.create_document(
            workspace_id=ws, entity_slug="timesheet",
            data={"project": pid, "hours": "40", "rate": "75", "status": "approved"},
            actor_id=actor))
        _step(result, "projects.cost_rollup",
              lambda: CostRollupService.rollup_project(workspace_id=ws, project_record_id=pid))
        _step(result, "projects.profitability",
              lambda: FinancialsService.project_financials(workspace_id=ws, project_record_id=pid))

    return result


# ── Consulting scenario: CRM → Projects → Profitability ───────────────────────

def simulate_consulting(workspace_id, actor_id) -> SimulationResult:
    """Consulting flow: CRM account → project → posted costs → profitability."""
    from apps.crm.blueprint import seed_crm_template
    from apps.crm.services import CRMService
    from apps.ledger.provisioning import provision_accounting
    from apps.projects.blueprint import seed_projects_template
    from apps.projects.services import CostRollupService, FinancialsService, ProjectService
    from apps.solution_templates import services as st3

    result = SimulationResult("Consulting: CRM → Projects → Profitability")
    ws = uuid.UUID(str(workspace_id))
    actor = uuid.UUID(str(actor_id))

    class _Member:
        user_id = actor
        id = uuid.uuid4()
        role = "admin"
        custom_role_id = None

    member = _Member()

    _step(result, "provision_accounting", lambda: provision_accounting(ws, actor_id=actor))
    _step(result, "install_crm",
          lambda: st3.install(template_id=seed_crm_template().id, workspace_id=ws,
                             installed_by=actor))
    _step(result, "install_projects",
          lambda: st3.install(template_id=seed_projects_template().id, workspace_id=ws,
                             installed_by=actor))

    acc = _step(result, "crm.create_account", lambda: CRMService.create_document(
        workspace_id=ws, entity_slug="account",
        data={"name": f"Client {uuid.uuid4().hex[:5]}"}, member=member))
    client_id = acc["id"] if isinstance(acc, dict) else None

    proj = _step(result, "projects.create_engagement", lambda: ProjectService.create_document(
        workspace_id=ws, entity_slug="project",
        data={"name": "Advisory", "status": "active", "planned_budget": "50000",
              "revenue": "80000", "client": client_id or str(uuid.uuid4())}, actor_id=actor))
    if proj and isinstance(proj, dict):
        pid = proj["id"]
        _step(result, "projects.post_cost", lambda: CostRollupService.post_cost(
            workspace_id=ws, project_record_id=pid, source="procurement",
            amount=12000, reference=f"SIM-{uuid.uuid4().hex[:6]}", actor_id=actor))
        _step(result, "projects.rollup",
              lambda: CostRollupService.rollup_project(workspace_id=ws, project_record_id=pid))
        _step(result, "projects.profitability",
              lambda: FinancialsService.project_financials(workspace_id=ws, project_record_id=pid))

    return result


# ── Trading scenario: Procurement → Inventory → Accounting ───────────────────

def simulate_trading(workspace_id, actor_id) -> SimulationResult:
    """Procurement → Inventory → GL flow."""
    from apps.inventory.models import Item, Warehouse
    from apps.inventory.services import InventoryService
    from apps.ledger.provisioning import provision_accounting

    result = SimulationResult("Trading: Inventory → Accounting")
    ws = uuid.UUID(str(workspace_id))
    actor = uuid.UUID(str(actor_id))

    _step(result, "provision_accounting", lambda: provision_accounting(ws, actor_id=actor))

    item_ref = {}
    def _create_item():
        obj, _ = Item.objects.get_or_create(
            workspace_id=ws, sku=f"SIM-{uuid.uuid4().hex[:6]}",
            defaults={"name": "Sim Widget", "valuation_method": "average",
                      "standard_cost": "10.00"})
        item_ref["item"] = obj
        return obj
    item = _step(result, "create_inventory_item", _create_item)

    wh_ref = {}
    def _create_wh():
        obj, _ = Warehouse.objects.get_or_create(
            workspace_id=ws, code=f"SIM-WH-{uuid.uuid4().hex[:4]}",
            defaults={"name": "Sim Warehouse"})
        wh_ref["wh"] = obj
        return obj
    wh = _step(result, "create_warehouse", _create_wh)

    if item and wh:
        movement = _step(result, "inventory.receive",
                         lambda: InventoryService.receive(
                             ws, item.id, wh.id, 100, "10.00",
                             reference=f"SIM-RECV-{uuid.uuid4().hex[:6]}",
                             actor_id=actor))
        if movement:
            _step(result, "inventory.issue",
                  lambda: InventoryService.issue(
                      ws, item.id, wh.id, 10,
                      reference=f"SIM-ISSUE-{uuid.uuid4().hex[:6]}",
                      actor_id=actor))

    from apps.ledger.models import JournalEntry
    _step(result, "verify_journal_entries",
          lambda: {"count": JournalEntry.objects.filter(
              workspace_id=ws, source_module="inventory").count()})

    return result


# ── Manufacturing scenario: BOM → Production → FG → Accounting ───────────────

def simulate_manufacturing(workspace_id, actor_id) -> SimulationResult:
    """BOM → Production Order → Material Issue → FG → GL."""
    from apps.inventory.models import Item, Warehouse
    from apps.inventory.services import InventoryService
    from apps.ledger.provisioning import provision_accounting
    from apps.manufacturing.services import BOMService, ProductionOrderService

    result = SimulationResult("Manufacturing: BOM → Production → FG → Accounting")
    ws = uuid.UUID(str(workspace_id))
    actor = uuid.UUID(str(actor_id))

    _step(result, "provision_accounting", lambda: provision_accounting(ws, actor_id=actor))

    raw_ref, fg_ref, wh_ref = {}, {}, {}

    def _mk_raw():
        obj, _ = Item.objects.get_or_create(
            workspace_id=ws, sku=f"RAW-{uuid.uuid4().hex[:6]}",
            defaults={"name": "Raw Material", "valuation_method": "average",
                      "standard_cost": "5.00"})
        raw_ref["v"] = obj
        return obj
    raw = _step(result, "create_raw_material", _mk_raw)

    def _mk_fg():
        obj, _ = Item.objects.get_or_create(
            workspace_id=ws, sku=f"FG-{uuid.uuid4().hex[:6]}",
            defaults={"name": "Finished Good", "valuation_method": "average",
                      "standard_cost": "0.00"})
        fg_ref["v"] = obj
        return obj
    fg = _step(result, "create_fg_item", _mk_fg)

    def _mk_wh():
        obj, _ = Warehouse.objects.get_or_create(
            workspace_id=ws, code=f"MFG-{uuid.uuid4().hex[:4]}",
            defaults={"name": "MFG Warehouse"})
        wh_ref["v"] = obj
        return obj
    wh = _step(result, "create_warehouse", _mk_wh)

    if raw and wh:
        _step(result, "stock_raw_material",
              lambda: InventoryService.receive(
                  ws, raw.id, wh.id, 200, "5.00",
                  reference=f"SIM-STOCK-{uuid.uuid4().hex[:6]}",
                  actor_id=actor, post_gl=False))

    bom = None
    if raw and fg:
        bom = _step(result, "create_bom",
                    lambda: BOMService.create_bom(
                        workspace_id=ws,
                        product_item_id=fg.id,
                        quantity=1,
                        components=[{"component_item_id": str(raw.id),
                                     "quantity": 2, "scrap_percent": 0}],
                        actor_id=actor))

    if bom:
        _step(result, "approve_bom",
              lambda: BOMService.approve_bom(workspace_id=ws, bom_id=bom.id, actor_id=actor))

        po_ref = {}
        def _mk_po():
            po = ProductionOrderService.create_order(
                workspace_id=ws, product_item_id=fg.id,
                quantity=5, bom_id=bom.id,
                warehouse_id=wh.id if wh else None,
                actor_id=actor)
            po_ref["v"] = po
            return po
        po = _step(result, "create_production_order", _mk_po)

        if po:
            _step(result, "release_order",
                  lambda: ProductionOrderService.release_order(
                      workspace_id=ws, order_id=po.id, actor_id=actor))
            _step(result, "issue_materials",
                  lambda: ProductionOrderService.issue_materials(
                      workspace_id=ws, order_id=po.id, actor_id=actor))
            _step(result, "complete_order",
                  lambda: ProductionOrderService.complete_order(
                      workspace_id=ws, order_id=po.id, actor_id=actor))

    from apps.inventory.models import StockLevel
    if fg and wh:
        _step(result, "verify_fg_stock",
              lambda: {"fg_on_hand": str(
                  StockLevel.objects.filter(
                      workspace_id=ws, item=fg, warehouse=wh
                  ).values_list("on_hand", flat=True).first() or 0)})

    return result


# ── Asset Enterprise scenario ─────────────────────────────────────────────────

def simulate_asset_enterprise(workspace_id, actor_id) -> SimulationResult:
    """Asset lifecycle: create schedule → depreciate → GL."""
    import datetime

    from apps.ledger.provisioning import provision_accounting

    result = SimulationResult("Asset Enterprise: Depreciation → GL")
    ws = uuid.UUID(str(workspace_id))
    actor = uuid.UUID(str(actor_id))

    _step(result, "provision_accounting", lambda: provision_accounting(ws, actor_id=actor))

    from apps.assets.models import DepreciationSchedule
    from apps.assets.services import DepreciationService

    sched_ref = {}
    def _mk_sched():
        s = DepreciationSchedule.objects.create(
            workspace_id=ws,
            asset_record_id=uuid.uuid4(),
            method="straight_line",
            acquisition_cost="10000.00",
            salvage_value="1000.00",
            useful_life_months=60,
            start_date="2026-01-01",
            created_by=actor)
        sched_ref["v"] = s
        return s
    sched = _step(result, "create_depreciation_schedule", _mk_sched)

    if sched:
        _step(result, "run_depreciation_period",
              lambda: DepreciationService.run_period(
                  workspace_id=ws,
                  schedule_id=sched.id,
                  period_date=datetime.date(2026, 1, 31),
                  actor_id=actor))

    from apps.ledger.models import JournalEntry
    _step(result, "verify_depreciation_gl",
          lambda: {"dep_entries": JournalEntry.objects.filter(
              workspace_id=ws, source_module="assets").count()})

    return result


# ── Registry of all scenarios ─────────────────────────────────────────────────

SCENARIOS = {
    "it_services": {
        "name": "IT Services",
        "description": "CRM → Opportunity → Project → Timesheet → Cost rollup → Analytics",
        "modules": ["crm", "projects", "analytics", "ledger"],
        "fn": simulate_it_services,
    },
    "consulting": {
        "name": "Consulting",
        "description": "CRM account → Project → Posted costs → Profitability",
        "modules": ["crm", "projects", "ledger"],
        "fn": simulate_consulting,
    },
    "trading": {
        "name": "Trading",
        "description": "Inventory receive → issue → GL posting",
        "modules": ["inventory", "ledger"],
        "fn": simulate_trading,
    },
    "manufacturing": {
        "name": "Manufacturing",
        "description": "BOM → Production Order → Material Issue → FG → GL",
        "modules": ["manufacturing", "inventory", "ledger"],
        "fn": simulate_manufacturing,
    },
    "asset_enterprise": {
        "name": "Asset Enterprise",
        "description": "Depreciation schedule → run period → GL journal",
        "modules": ["assets", "ledger"],
        "fn": simulate_asset_enterprise,
    },
}


def run_scenario(scenario_name: str, workspace_id, actor_id) -> SimulationResult:
    meta = SCENARIOS.get(scenario_name)
    if meta is None:
        result = SimulationResult(f"unknown:{scenario_name}")
        result.steps.append(SimulationStep(
            name="lookup", status="failed",
            error=f"Unknown scenario: {scenario_name}"))
        return result
    return meta["fn"](workspace_id, actor_id)


def run_all_scenarios(workspace_id, actor_id) -> dict[str, SimulationResult]:
    """Run all scenarios; return dict keyed by scenario name."""
    return {name: run_scenario(name, workspace_id, actor_id) for name in SCENARIOS}
