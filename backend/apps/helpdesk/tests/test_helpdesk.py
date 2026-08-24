"""
Helpdesk / ITSM (Phase P2.11) — framework provisioning, ticket lifecycle + audit, SLA engine
reuse (attach/pause/met), deterministic assignment + escalation + knowledge recommendation
(NO AI), and CSAT. Covers spec Modules 6/9/32/33/34/38.
"""
import uuid

import pytest

from apps.eventstore.models import DomainEvent
from apps.helpdesk.blueprint import build_helpdesk_manifest, seed_helpdesk_template
from apps.helpdesk.services import (
    AssignmentService,
    CSATService,
    EscalationService,
    KnowledgeService,
    TicketService,
)
from apps.metadata.models import EntityDefinition
from apps.permissions.models import Role
from apps.reporting.models import Dashboard
from apps.sla.models import SLAPolicy, SLARecord
from apps.solution_templates import services as st
from apps.solution_templates.documents import SolutionDocumentService as Docs
from apps.solution_templates.validators import validate_solution_manifest
from apps.studio.models import Application
from apps.workflows.models import WorkflowDefinition

A = str(uuid.uuid4())


def test_manifest_validates_clean():
    assert validate_solution_manifest(build_helpdesk_manifest()) == []


@pytest.fixture
def installed_ws(db):
    ws = uuid.uuid4()
    st.install(template_id=seed_helpdesk_template().id, workspace_id=ws, installed_by=None)
    return ws


@pytest.mark.django_db
def test_install_provisions_helpdesk_solution():
    ws = uuid.uuid4()
    st.install(template_id=seed_helpdesk_template().id, workspace_id=ws, installed_by=None)
    for slug in ["ticket", "ticket_category", "kb_article", "problem", "itsm_change",
                 "major_incident", "service_contract", "ticket_csat", "agent_profile"]:
        assert EntityDefinition.objects.filter(workspace_id=ws, slug=slug).exists(), slug
    assert WorkflowDefinition.objects.filter(workspace_id=ws, slug="incident_workflow").exists()
    assert Role.objects.filter(workspace_id=ws, slug="service_desk_manager").exists()
    assert Dashboard.objects.filter(workspace_id=ws).count() == 3
    assert Application.objects.filter(workspace_id=ws, slug="helpdesk").exists()


# ── Module 6: ticket lifecycle + SLA reuse + audit ───────────────────────────
@pytest.mark.django_db
def test_ticket_lifecycle_with_sla_and_audit(installed_ws):
    ws = installed_ws
    ticket_entity = EntityDefinition.objects.get(workspace_id=ws, slug="ticket")
    SLAPolicy.objects.create(
        workspace_id=ws, name="Default", entity_id=ticket_entity.id, is_active=True,
        applies_when_nql="",
        targets=[{"metric": "resolution", "target_minutes": 240, "warning_at_percent": 80}])

    ticket = TicketService.create_ticket(
        workspace_id=ws, data={"title": "Cannot login", "priority": "high"}, actor_id=A)
    assert ticket["number"] == "TKT-000001"
    assert DomainEvent.objects.filter(event_type="ticket.created").exists()
    # SLA engine (P1.19) attached a resolution timer.
    sla = SLARecord.objects.filter(workspace_id=ws, record_id=ticket["id"],
                                   metric_key="resolution").first()
    assert sla is not None and sla.status == "on_track"

    TicketService.assign_ticket(workspace_id=ws, record_id=ticket["id"], agent=A, actor_id=A)
    assert DomainEvent.objects.filter(event_type="ticket.assigned").exists()

    # Waiting on customer → SLA paused.
    TicketService.set_status(workspace_id=ws, record_id=ticket["id"],
                             status="waiting_customer", actor_id=A)
    assert SLARecord.objects.get(id=sla.id).paused_at is not None
    TicketService.set_status(workspace_id=ws, record_id=ticket["id"],
                             status="in_progress", actor_id=A)
    assert SLARecord.objects.get(id=sla.id).paused_at is None  # resumed

    TicketService.resolve_ticket(workspace_id=ws, record_id=ticket["id"], actor_id=A)
    assert SLARecord.objects.get(id=sla.id).status == "met"
    assert DomainEvent.objects.filter(event_type="ticket.resolved").exists()


# ── Module 7: escalation ladder ──────────────────────────────────────────────
@pytest.mark.django_db
def test_escalation_advances_level(installed_ws):
    ws = installed_ws
    t = TicketService.create_ticket(workspace_id=ws, data={"title": "Down"}, actor_id=A)
    EscalationService.escalate(workspace_id=ws, record_id=t["id"], actor_id=A)
    out = EscalationService.escalate(workspace_id=ws, record_id=t["id"], actor_id=A)
    assert int(out["escalation_level"]) == 2
    assert DomainEvent.objects.filter(event_type="ticket.escalated").count() == 2


# ── Module 5: assignment engine (deterministic) ──────────────────────────────
@pytest.mark.django_db
def test_assignment_picks_least_loaded_agent(installed_ws):
    ws = installed_ws
    busy, free = str(uuid.uuid4()), str(uuid.uuid4())
    Docs.create(workspace_id=ws, entity_slug="agent_profile",
                data={"agent": busy, "team": "tier1", "is_available": True,
                      "open_ticket_count": 9}, actor_id=A)
    Docs.create(workspace_id=ws, entity_slug="agent_profile",
                data={"agent": free, "team": "tier1", "is_available": True,
                      "open_ticket_count": 1}, actor_id=A)
    picked = AssignmentService.pick_agent(workspace_id=ws, method="load_based")
    assert str(picked) == free


@pytest.mark.django_db
def test_assignment_skill_and_team_filter(installed_ws):
    ws = installed_ws
    net = str(uuid.uuid4())
    Docs.create(workspace_id=ws, entity_slug="agent_profile",
                data={"agent": net, "team": "network", "skills": "vpn,firewall",
                      "is_available": True, "open_ticket_count": 3}, actor_id=A)
    Docs.create(workspace_id=ws, entity_slug="agent_profile",
                data={"agent": str(uuid.uuid4()), "team": "desktop", "skills": "windows",
                      "is_available": True, "open_ticket_count": 0}, actor_id=A)
    picked = AssignmentService.pick_agent(workspace_id=ws, method="skill_based", skill="firewall")
    assert str(picked) == net


# ── Module 9: knowledge recommendation (deterministic, NO AI) ────────────────
@pytest.mark.django_db
def test_knowledge_recommend_keyword_and_category(installed_ws):
    ws = installed_ws
    Docs.create(workspace_id=ws, entity_slug="kb_article",
                data={"title": "Reset VPN password", "content": "vpn login password reset steps",
                      "category": "access", "status": "published"}, actor_id=A)
    Docs.create(workspace_id=ws, entity_slug="kb_article",
                data={"title": "Printer setup", "content": "install printer driver",
                      "category": "hardware", "status": "published"}, actor_id=A)
    Docs.create(workspace_id=ws, entity_slug="kb_article",
                data={"title": "VPN draft", "content": "vpn", "category": "access",
                      "status": "draft"}, actor_id=A)  # excluded — not published

    recs = KnowledgeService.recommend(workspace_id=ws, category="access", keywords="vpn password")
    assert len(recs) == 1
    assert recs[0]["title"] == "Reset VPN password"


# ── Module 22/32: CSAT + change approval audit ───────────────────────────────
@pytest.mark.django_db
def test_csat_and_change_approval(installed_ws):
    ws = installed_ws
    t = TicketService.create_ticket(workspace_id=ws, data={"title": "Q"}, actor_id=A)
    CSATService.submit(workspace_id=ws, ticket_record_id=t["id"], rating=5,
                       feedback="great", actor_id=A)
    assert DomainEvent.objects.filter(event_type="csat.submitted").exists()

    ch = Docs.create(workspace_id=ws, entity_slug="itsm_change",
                     data={"title": "Upgrade DB", "risk": "medium", "status": "pending"},
                     actor_id=A)
    Docs.transition(workspace_id=ws, entity_slug="itsm_change", record_id=ch["id"],
                    updates={"status": "approved"}, event_type="change.approved")
    assert DomainEvent.objects.filter(event_type="change.approved").exists()
