"""
Helpdesk / ITSM services (Phase P2.11).

Thin native lifecycle over the framework metadata entities, delegating numbering + audit to the
reusable ``SolutionDocumentService`` and SLA timers to the P1.19 ``SLAService`` (reused, never
re-implemented). The Assignment, Escalation, Knowledge-recommendation and CSAT engines are
deterministic — NO AI / embeddings / ML (PROJECT_HANDBOOK.md §2): knowledge matching is plain category +
keyword overlap. All metadata reads are bulk (no per-ticket N+1).
"""
from __future__ import annotations

import contextlib
import re

from apps.records.services import RecordService, resolve_entity
from apps.solution_templates.documents import (
    SolutionDocumentService as Docs,
)
from apps.solution_templates.documents import (
    emit_event,
    system_member,
)

from .blueprint import HELPDESK_SEQUENCES

_WAITING = {"waiting_customer", "waiting_vendor"}
_ESCALATION_LADDER = ["l1", "l2", "l3", "manager"]


class HelpdeskError(Exception):  # noqa: N818 — domain error
    pass


def _list(workspace_id, slug, filter_source=None, member=None, limit=2000):
    member = member or system_member(None)
    try:
        entity = resolve_entity(workspace_id, slug)
    except Exception:  # noqa: BLE001 — entity not installed
        return []
    return RecordService.list_records(
        workspace_id=workspace_id, member=member, entity=entity,
        filter_source=filter_source, limit=limit)


def _sla(method, *args):
    """Call the reused P1.19 SLAService, best-effort (never breaks the ticket op)."""
    with contextlib.suppress(Exception):
        from apps.sla.services import SLAService
        return getattr(SLAService, method)(*args)
    return None


# ── ticket lifecycle ──────────────────────────────────────────────────────────
class TicketService:
    @staticmethod
    def ensure_sequences(workspace_id, *, actor_id=None):
        from apps.numbering.services import NumberingService
        for key, defaults in HELPDESK_SEQUENCES.items():
            NumberingService.ensure_sequence(
                workspace_id, key, defaults=defaults, created_by=actor_id)

    @staticmethod
    def create_ticket(*, workspace_id, data, member=None, actor_id=None):
        """Create a ticket (TKT-numbered), emit ticket.created, and attach SLA policies."""
        payload = dict(data or {})
        payload.setdefault("status", "new")
        ticket = Docs.create(
            workspace_id=workspace_id, entity_slug="ticket", data=payload, member=member,
            actor_id=actor_id, sequence_key="ticket",
            sequence_defaults=HELPDESK_SEQUENCES["ticket"], event_type="ticket.created")
        _sla("attach_policies", ticket["id"], "ticket", ticket, workspace_id)
        return ticket

    @staticmethod
    def assign_ticket(*, workspace_id, record_id, agent=None, team="", member=None,
                      actor_id=None):
        updates = {"status": "assigned"}
        if agent is not None:
            updates["assigned_agent"] = agent
        if team:
            updates["assigned_team"] = team
        ticket = Docs.transition(
            workspace_id=workspace_id, entity_slug="ticket", record_id=record_id,
            updates=updates, member=member, actor_id=actor_id, event_type="ticket.assigned",
            event_payload={"agent": str(agent) if agent else None, "team": team})
        return ticket

    @staticmethod
    def set_status(*, workspace_id, record_id, status, member=None, actor_id=None):
        """Status change with SLA pause/resume on waiting states."""
        prior = Docs.retrieve(workspace_id=workspace_id, entity_slug="ticket",
                             record_id=record_id, member=member, actor_id=actor_id)
        ticket = Docs.transition(
            workspace_id=workspace_id, entity_slug="ticket", record_id=record_id,
            updates={"status": status}, member=member, actor_id=actor_id)
        was_waiting = prior.get("status") in _WAITING
        now_waiting = status in _WAITING
        if now_waiting and not was_waiting:
            _sla("pause_record", record_id, workspace_id)
        elif was_waiting and not now_waiting:
            _sla("resume_record", record_id, workspace_id)
        return ticket

    @staticmethod
    def resolve_ticket(*, workspace_id, record_id, member=None, actor_id=None):
        from django.utils import timezone
        ticket = Docs.transition(
            workspace_id=workspace_id, entity_slug="ticket", record_id=record_id,
            updates={"status": "resolved", "closed_date": timezone.now().isoformat()},
            member=member, actor_id=actor_id, event_type="ticket.resolved")
        _sla("mark_met", record_id, "resolution", workspace_id)
        return ticket

    @staticmethod
    def close_ticket(*, workspace_id, record_id, member=None, actor_id=None):
        return Docs.transition(
            workspace_id=workspace_id, entity_slug="ticket", record_id=record_id,
            updates={"status": "closed"}, member=member, actor_id=actor_id,
            event_type="ticket.closed")


# ── assignment engine (deterministic) ────────────────────────────────────────
class AssignmentService:
    @staticmethod
    def pick_agent(*, workspace_id, method="load_based", team="", skill="", member=None):
        """Choose an available agent. round_robin/load_based → least loaded; skill_based →
        skill match then least loaded; team_based → team filter then least loaded. Deterministic."""
        agents = [a for a in _list(workspace_id, "agent_profile", None, member)
                  if a.get("is_available") in (True, "true", 1, None)]
        if team:
            agents = [a for a in agents if (a.get("team") or "") == team]
        if skill and method == "skill_based":
            agents = [a for a in agents if skill.lower() in (a.get("skills") or "").lower()]
        if not agents:
            return None

        def _load(a):
            try:
                return int(a.get("open_ticket_count") or 0)
            except (TypeError, ValueError):
                return 0
        agents.sort(key=lambda a: (_load(a), str(a.get("agent"))))
        return agents[0].get("agent")

    @staticmethod
    def auto_assign(*, workspace_id, record_id, method="load_based", team="", skill="",
                    member=None, actor_id=None):
        agent = AssignmentService.pick_agent(
            workspace_id=workspace_id, method=method, team=team, skill=skill, member=member)
        if agent is None:
            raise HelpdeskError("No available agent to assign.")
        return TicketService.assign_ticket(
            workspace_id=workspace_id, record_id=record_id, agent=agent, team=team,
            member=member, actor_id=actor_id)


# ── escalation engine ─────────────────────────────────────────────────────────
class EscalationService:
    @staticmethod
    def escalate(*, workspace_id, record_id, member=None, actor_id=None):
        """Advance the ticket one level up the L1→L2→L3→Manager ladder + emit ticket.escalated."""
        ticket = Docs.retrieve(workspace_id=workspace_id, entity_slug="ticket",
                              record_id=record_id, member=member, actor_id=actor_id)
        try:
            level = int(ticket.get("escalation_level") or 0)
        except (TypeError, ValueError):
            level = 0
        new_level = min(level + 1, len(_ESCALATION_LADDER))
        updated = Docs.transition(
            workspace_id=workspace_id, entity_slug="ticket", record_id=record_id,
            updates={"escalation_level": new_level}, member=member, actor_id=actor_id,
            event_type="ticket.escalated",
            event_payload={"level": new_level, "tier": _ESCALATION_LADDER[new_level - 1]})
        return updated


# ── knowledge recommendation (deterministic — NO AI) ─────────────────────────
_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall((text or "").lower()))


class KnowledgeService:
    @staticmethod
    def recommend(*, workspace_id, category="", keywords="", limit=5, member=None) -> list[dict]:
        """Suggest published KB articles by category match + keyword overlap. Purely deterministic
        text matching — no embeddings/ML (PROJECT_HANDBOOK.md §2)."""
        query = _tokens(keywords) | _tokens(category)
        scored = []
        for art in _list(workspace_id, "kb_article", None, member):
            if (art.get("status") or "") != "published":
                continue
            doc = _tokens(f"{art.get('title', '')} {art.get('tags', '')} "
                          f"{art.get('content', '')} {art.get('category', '')}")
            overlap = len(query & doc)
            cat_match = 2 if category and category.lower() == (art.get("category") or "").lower() \
                else 0
            score = overlap + cat_match
            if score > 0:
                scored.append((score, art))
        scored.sort(key=lambda x: (-x[0], str(x[1].get("id"))))
        return [{"id": a["id"], "title": a.get("title"), "category": a.get("category"),
                 "score": s} for s, a in scored[:limit]]


# ── CSAT engine ───────────────────────────────────────────────────────────────
class CSATService:
    @staticmethod
    def submit(*, workspace_id, ticket_record_id, rating, feedback="", comments="",
               member=None, actor_id=None):
        csat = Docs.create(
            workspace_id=workspace_id, entity_slug="ticket_csat",
            data={"ticket": str(ticket_record_id), "rating": rating, "feedback": feedback,
                  "comments": comments}, member=member, actor_id=actor_id)
        emit_event(workspace_id, "ticket", ticket_record_id, "csat.submitted",
                   {"rating": rating}, actor_id)
        return csat
