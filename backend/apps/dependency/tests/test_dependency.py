"""
Dependency & Impact Analysis (Phase P2.14) — discovery delegated to apps.metadata.impact (the
single system of record), plus orchestration: used-by analysis, dependency graph, risk scoring,
safe-delete, change preview, promotion precheck, audit. Covers spec Modules 1/2/18/19/20/22/23/24/
25/28/31.
"""
import uuid

import pytest

from apps.dependency import risk
from apps.dependency.services import AnalysisService
from apps.eventstore.models import DomainEvent
from apps.metadata import impact
from apps.metadata.models import FormDefinition
from apps.reporting.models import Dashboard, DashboardWidget, Report
from apps.schema_registry.services import SchemaRegistryService
from apps.workflows.models import WorkflowDefinition

A = str(uuid.uuid4())


def _entity(ws, slug="customer"):
    return SchemaRegistryService.create_entity(
        workspace_id=ws, slug=slug, name=slug.title(), plural_name=slug.title() + "s",
        fields=[{"slug": "email", "name": "Email", "field_type": "email", "is_promoted": True}])


# ── risk scoring (pure) ───────────────────────────────────────────────────────
def test_risk_thresholds():
    assert risk.score([])["level"] == "low"
    assert risk.score([{"type": "form"}] * 3)["level"] == "low"
    assert risk.score([{"type": "form"}] * 6)["level"] == "medium"
    assert risk.score([{"type": "workflow"}])["level"] == "high"        # automation bump
    assert risk.score([{"type": "form"}] * 20)["level"] == "high"
    assert risk.score([{"type": "form"}] * 50)["level"] == "critical"
    assert risk.is_blocking({"level": "critical"}) and not risk.is_blocking({"level": "high"})


# ── discovery flows through impact.py (system of record) ─────────────────────
@pytest.mark.django_db
def test_dependents_dispatch_uses_impact():
    ws = uuid.uuid4()
    ent = _entity(ws)
    FormDefinition.objects.create(workspace_id=ws, entity_id=ent.id, name="Customer Form",
                                  layout=[{"section": "Main", "fields": ["email"]}])
    WorkflowDefinition.objects.create(workspace_id=ws, entity_id=ent.id, name="Greet",
                                      slug="greet", trigger_type="record_created", status="active")
    Report.objects.create(workspace_id=ws, name="Cust Report", slug="cr", nql_ast={"entity": "customer"},
                          source_entity_ids=[str(ent.id)])
    # impact.dependents is THE discovery; the service uses it verbatim.
    deps = impact.dependents(ws, "entity", ent.id)
    types = {d["type"] for d in deps}
    assert {"form", "workflow", "report"} <= types


@pytest.mark.django_db
def test_analyze_used_by_and_risk_and_audit():
    ws = uuid.uuid4()
    ent = _entity(ws)
    FormDefinition.objects.create(workspace_id=ws, entity_id=ent.id, name="F", layout=[])
    WorkflowDefinition.objects.create(workspace_id=ws, entity_id=ent.id, name="W", slug="w",
                                      trigger_type="record_created", status="active")
    a = AnalysisService.analyze(workspace_id=ws, object_type="entity", object_id=ent.id, actor_id=A)
    assert a["used_by_count"] >= 2
    assert a["risk"]["level"] == "high"            # a workflow depends on it
    assert a["by_type"]["workflow"] == 1
    assert DomainEvent.objects.filter(event_type="dependency.analyzed").exists()


# ── dependency graph (Module 18) ─────────────────────────────────────────────
@pytest.mark.django_db
def test_graph_traverses_report_to_dashboard():
    ws = uuid.uuid4()
    ent = _entity(ws)
    rep = Report.objects.create(workspace_id=ws, name="R", slug="r", nql_ast={"entity": "customer"},
                                source_entity_ids=[str(ent.id)])
    dash = Dashboard.objects.create(workspace_id=ws, name="D", slug="d")
    DashboardWidget.objects.create(workspace_id=ws, dashboard_id=dash.id, widget_type="report",
                                   report_id=rep.id)
    g = AnalysisService.graph(workspace_id=ws, object_type="entity", object_id=ent.id, depth=3)
    node_names = {n["name"] for n in g["nodes"]}
    # entity → report (direct) → dashboard (indirect, via report recursion)
    assert "R" in node_names and "D" in node_names
    assert any(e["to"].startswith("dashboard:") for e in g["edges"])


# ── safe delete + change preview + audit ─────────────────────────────────────
@pytest.mark.django_db
def test_safe_delete_and_change_preview():
    ws = uuid.uuid4()
    ent = _entity(ws)
    WorkflowDefinition.objects.create(workspace_id=ws, entity_id=ent.id, name="W", slug="w",
                                      trigger_type="record_created", status="active")
    sd = AnalysisService.safe_delete(workspace_id=ws, object_type="entity", object_id=ent.id)
    assert sd["safe"] is False and "risk" in sd["message"].lower()
    assert DomainEvent.objects.filter(event_type="impact.checked").exists()

    cp = AnalysisService.change_preview(workspace_id=ws, object_type="entity", object_id=ent.id,
                                        change="rename", actor_id=A)
    assert cp["direct_impact"] >= 1
    assert DomainEvent.objects.filter(event_type="change.previewed").exists()


# ── promotion precheck (Modules 24/25) ───────────────────────────────────────
@pytest.mark.django_db
def test_promotion_precheck_approves_low_risk():
    ws = uuid.uuid4()
    ent = _entity(ws)  # no dependents → low risk
    out = AnalysisService.promotion_precheck(
        workspace_id=ws, objects=[{"object_type": "entity", "object_id": str(ent.id)}], actor_id=A)
    assert out["blocked"] is False and out["decision"] == "approved"
    assert DomainEvent.objects.filter(event_type="promotion.approved").exists()


# ── executive summary (Module 32) ────────────────────────────────────────────
@pytest.mark.django_db
def test_executive_summary():
    ws = uuid.uuid4()
    ent = _entity(ws)
    AnalysisService.analyze(workspace_id=ws, object_type="entity", object_id=ent.id, actor_id=A)
    summ = AnalysisService.executive_summary(workspace_id=ws)
    assert summ["totals"]["entities"] >= 1
    assert isinstance(summ["recent_analyses"], list) and len(summ["recent_analyses"]) >= 1


# ── API object types ─────────────────────────────────────────────────────────
def test_object_types_cover_all_config():
    assert {"entity", "field", "report", "dashboard", "kpi", "role", "view", "workflow",
            "rule", "form"} <= set(impact.OBJECT_TYPES)


# ── Module 23: SINGLE SOURCE OF TRUTH certification ──────────────────────────
@pytest.mark.django_db
def test_ssot_a_new_type_needs_only_impact_changes(monkeypatch):
    """Adding a dependency type requires editing ONLY impact.py's registry — the orchestration
    (analyze/graph/risk/promotion) is type-agnostic and needs ZERO changes."""
    from apps.metadata.models import EntityDefinition

    ws, oid = uuid.uuid4(), uuid.uuid4()

    def fake_scan(workspace_id, object_id):
        return [{"type": "workflow", "name": "W", "detail": "fake dependent",
                 "approximate": False, "id": str(uuid.uuid4())}]

    impact._reg()  # ensure the registry is built
    # Simulate the ONLY edit a new type requires — a registry entry + an OBJECT_TYPES entry.
    monkeypatch.setitem(impact._REGISTRY, "fake_type", (EntityDefinition, fake_scan))
    monkeypatch.setattr(impact, "OBJECT_TYPES", [*impact.OBJECT_TYPES, "fake_type"])

    # The unchanged orchestration handles the brand-new type end-to-end:
    a = AnalysisService.analyze(workspace_id=ws, object_type="fake_type", object_id=oid)
    assert a["used_by_count"] == 1                       # used-by aggregation works
    assert a["risk"]["level"] == "high"                 # risk scoring works (workflow dependent)
    g = AnalysisService.graph(workspace_id=ws, object_type="fake_type", object_id=oid)
    assert len(g["nodes"]) >= 2                          # graph traversal works
    pc = AnalysisService.promotion_precheck(
        workspace_id=ws, objects=[{"object_type": "fake_type", "object_id": str(oid)}])
    assert pc["decision"] in ("approved", "blocked")    # promotion precheck works
