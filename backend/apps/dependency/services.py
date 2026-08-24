"""
Dependency / Impact analysis service (Phase P2.14).

A read-only change-safety platform over the EXISTING config (no new config storage). ORCHESTRATION
ONLY — it performs NO dependency discovery itself. Every "what references X?" call delegates to
``apps.metadata.impact`` (the single discovery system of record, extended in P2.14). This layer adds
the cross-cutting concerns: used-by aggregation, dependency-graph BFS, risk scoring, safe-delete/
rename validation, change preview, and the Config-VCS / environment-promotion precheck. Audit:
dependency.analyzed / impact.checked / change.previewed / promotion.blocked / promotion.approved.
Visibility is workspace-scoped (RLS/RBAC apply upstream).
"""
from __future__ import annotations

import uuid

from apps.eventstore.events import DomainEventData, DomainEventFactory
from apps.metadata import impact  # the SINGLE system of record for dependency discovery

from . import risk


def _emit(workspace_id, event_type, payload, actor_id=None):
    from apps.eventstore.models import DomainEvent
    agg = uuid.UUID(int=0)
    version = DomainEvent.objects.filter(
        aggregate_id=agg, aggregate_type="dependency").count() + 1
    DomainEventFactory.persist_one(DomainEventData(
        event_type=event_type, workspace_id=uuid.UUID(str(workspace_id)),
        aggregate_type="dependency", aggregate_id=agg, version=version,
        payload=payload, actor_id=uuid.UUID(str(actor_id)) if actor_id else uuid.UUID(int=0)))


def _by_type(deps: list[dict]) -> dict:
    out: dict = {}
    for d in deps:
        out[d["type"]] = out.get(d["type"], 0) + 1
    return out


class AnalysisService:
    @staticmethod
    def analyze(*, workspace_id, object_type, object_id, actor_id=None) -> dict:
        """Used-by analysis + risk for one object."""
        deps = impact.dependents(workspace_id, object_type, object_id)
        r = risk.score(deps)
        result = {
            "object_type": object_type, "object_id": str(object_id),
            "name": impact.resolve_name(workspace_id, object_type, object_id),
            "used_by_count": len(deps), "by_type": _by_type(deps),
            "dependents": deps, "risk": r,
        }
        _emit(workspace_id, "dependency.analyzed",
              {"object_type": object_type, "used_by": len(deps), "risk": r["level"]}, actor_id)
        return result

    @staticmethod
    def graph(*, workspace_id, object_type, object_id, depth=2) -> dict:
        """BFS dependency graph (nodes + edges) up to ``depth`` levels."""
        root = f"{object_type}:{object_id}"
        nodes = {root: {"id": root, "object_type": object_type, "object_id": str(object_id),
                        "name": impact.resolve_name(workspace_id, object_type, object_id)}}
        edges = []
        frontier = [(object_type, str(object_id), root)]
        seen = {root}
        for _ in range(max(depth, 1)):
            nxt = []
            for otype, oid, key in frontier:
                for d in impact.dependents(workspace_id, otype, oid):
                    nkey = f"{d['type']}:{d.get('id')}"
                    nodes.setdefault(nkey, {
                        "id": nkey, "object_type": d["type"], "object_id": d.get("id"),
                        "name": d["name"], "approximate": d.get("approximate", False)})
                    edges.append({"from": key, "to": nkey, "detail": d["detail"]})
                    rec = impact.RECURSE_TYPE.get(d["type"])
                    if rec and d.get("id") and nkey not in seen:
                        seen.add(nkey)
                        nxt.append((rec, d["id"], nkey))
            frontier = nxt
            if not frontier:
                break
        return {"nodes": list(nodes.values()), "edges": edges}

    @staticmethod
    def safe_delete(*, workspace_id, object_type, object_id, actor_id=None) -> dict:
        a = AnalysisService.analyze(
            workspace_id=workspace_id, object_type=object_type, object_id=object_id,
            actor_id=actor_id)
        _emit(workspace_id, "impact.checked",
              {"object_type": object_type, "action": "delete"}, actor_id)
        blocking = a["risk"]["level"] in ("high", "critical")
        return {**a, "action": "delete", "safe": not blocking,
                "message": (f"Used by {a['used_by_count']} object(s) — "
                            f"{a['risk']['level']} risk. Review before deleting."
                            if a["used_by_count"] else "No dependents — safe to delete.")}

    @staticmethod
    def change_preview(*, workspace_id, object_type, object_id, change="rename",
                       actor_id=None) -> dict:
        direct = impact.dependents(workspace_id, object_type, object_id)
        g = AnalysisService.graph(workspace_id=workspace_id, object_type=object_type,
                                 object_id=object_id, depth=2)
        indirect = max(0, len(g["nodes"]) - 1 - len(direct))
        r = risk.score(direct)
        _emit(workspace_id, "change.previewed",
              {"object_type": object_type, "change": change, "risk": r["level"]}, actor_id)
        return {"object_type": object_type, "object_id": str(object_id), "change": change,
                "direct_impact": len(direct), "indirect_impact": indirect,
                "direct": direct, "risk": r}

    @staticmethod
    def promotion_precheck(*, workspace_id, objects, actor_id=None) -> dict:
        """objects: [{object_type, object_id}]. Risk per object; blocked if any is critical."""
        items = []
        blocked = False
        for o in objects or []:
            deps = impact.dependents(workspace_id, o["object_type"], o["object_id"])
            r = risk.score(deps)
            blocked = blocked or risk.is_blocking(r)
            items.append({"object_type": o["object_type"], "object_id": str(o["object_id"]),
                          "name": impact.resolve_name(
                              workspace_id, o["object_type"], o["object_id"]),
                          "used_by_count": len(deps), "risk": r})
        decision = "blocked" if blocked else "approved"
        _emit(workspace_id, f"promotion.{decision}",
              {"objects": len(items), "blocked": blocked}, actor_id)
        return {"blocked": blocked, "decision": decision, "objects": items}

    @staticmethod
    def executive_summary(*, workspace_id) -> dict:
        """Module 32: change-safety executive view — config counts + high-risk + recent analyses."""
        from apps.eventstore.models import DomainEvent
        from apps.metadata.models import EntityDefinition, FieldDefinition
        from apps.reporting.models import Dashboard, Report
        from apps.workflows.models import WorkflowDefinition

        recent = list(DomainEvent.objects.filter(
            workspace_id=workspace_id, aggregate_type="dependency",
            event_type="dependency.analyzed").order_by("-occurred_at")[:10].values(
            "event_type", "payload", "occurred_at"))
        return {
            "totals": {
                "entities": EntityDefinition.objects.filter(workspace_id=workspace_id).count(),
                "fields": FieldDefinition.objects.filter(workspace_id=workspace_id).count(),
                "reports": Report.objects.filter(workspace_id=workspace_id).count(),
                "dashboards": Dashboard.objects.filter(workspace_id=workspace_id).count(),
                "workflows": WorkflowDefinition.objects.filter(workspace_id=workspace_id).count(),
            },
            "recent_analyses": [
                {"object_type": (e["payload"] or {}).get("object_type"),
                 "used_by": (e["payload"] or {}).get("used_by"),
                 "risk": (e["payload"] or {}).get("risk"),
                 "at": e["occurred_at"].isoformat()} for e in recent],
            "high_risk_recent": sum(
                1 for e in recent if (e["payload"] or {}).get("risk") in ("high", "critical")),
        }
