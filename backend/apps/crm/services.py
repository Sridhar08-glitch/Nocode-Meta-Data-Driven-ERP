"""
CRM native services (Phase P2.6) — a THIN lifecycle layer.

Almost everything is provisioned by the framework (``blueprint.py``). The only native code is
the sales pipeline lifecycle, and even that delegates numbering + audit to the reusable
``SolutionDocumentService`` — so CRM adds no numbering/event machinery of its own. This is the
P2.6 thesis: a complete domain solution with <10% native code.
"""
from __future__ import annotations

from apps.solution_templates.documents import SolutionDocumentService as Docs

from .blueprint import CRM_SEQUENCES, EVENT_KEY


class CRMError(Exception):  # noqa: N818 — domain error
    pass


class CRMService:
    @staticmethod
    def ensure_sequences(workspace_id, *, actor_id=None):
        from apps.numbering.services import NumberingService
        for key, defaults in CRM_SEQUENCES.items():
            NumberingService.ensure_sequence(
                workspace_id, key, defaults=defaults, created_by=actor_id)

    @staticmethod
    def create_document(*, workspace_id, entity_slug, data, member=None, actor_id=None):
        """Create a CRM record; lead/account/opportunity get a gapless number (LEAD-/ACC-/OPP-)."""
        event = (f"crm.{EVENT_KEY[entity_slug]}.created"
                 if entity_slug in EVENT_KEY else None)
        return Docs.create(
            workspace_id=workspace_id, entity_slug=entity_slug, data=data,
            member=member, actor_id=actor_id,
            sequence_key=entity_slug if entity_slug in CRM_SEQUENCES else None,
            sequence_defaults=CRM_SEQUENCES.get(entity_slug), event_type=event)

    # ── pipeline lifecycle ────────────────────────────────────────────────────
    @staticmethod
    def qualify_lead(*, workspace_id, record_id, member=None, actor_id=None):
        """Qualify a lead and spin up a linked Opportunity (numbered) — the
        Lead→Qualified→Opportunity step of the pipeline."""
        lead = Docs.transition(
            workspace_id=workspace_id, entity_slug="lead", record_id=record_id,
            updates={"status": "qualified"}, member=member, actor_id=actor_id,
            event_type="crm.lead.qualified")
        opp = CRMService.create_document(
            workspace_id=workspace_id, entity_slug="opportunity",
            data={"stage": "prospecting", "owner": lead.get("owner"),
                  "probability": 10}, member=member, actor_id=actor_id)
        return {"lead": lead, "opportunity": opp}

    @staticmethod
    def win_opportunity(*, workspace_id, record_id, reason="", member=None, actor_id=None):
        return Docs.transition(
            workspace_id=workspace_id, entity_slug="opportunity", record_id=record_id,
            updates={"stage": "won", "close_reason": reason}, member=member, actor_id=actor_id,
            event_type="crm.opportunity.won", event_payload={"reason": reason})

    @staticmethod
    def lose_opportunity(*, workspace_id, record_id, reason="", member=None, actor_id=None):
        return Docs.transition(
            workspace_id=workspace_id, entity_slug="opportunity", record_id=record_id,
            updates={"stage": "lost", "close_reason": reason}, member=member, actor_id=actor_id,
            event_type="crm.opportunity.lost", event_payload={"reason": reason})

    @staticmethod
    def complete_activity(*, workspace_id, record_id, member=None, actor_id=None):
        return Docs.transition(
            workspace_id=workspace_id, entity_slug="activity", record_id=record_id,
            updates={"status": "completed"}, member=member, actor_id=actor_id,
            event_type="crm.activity.completed")
