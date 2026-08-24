"""
Environment Promotion service (Phase P2.15) — ORCHESTRATION ONLY.

Reuses the Config VCS (1.28) for all config movement (branch = environment; promotion = merge;
rollback = config_vcs.rollback) and the P2.14 ``AnalysisService.promotion_precheck`` for dependency
+ risk gating. It creates NO new VCS / metadata / dependency / rollback engine. Promotion enforces
segregation of duties (creator ≠ approver ≠ executor) and blocks critical-risk promotions to
production. Audit: promotion.created / approved / executed / failed / rolled_back.
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import uuid

from django.utils import timezone

from apps.config_vcs import services as vcs
from apps.dependency.services import AnalysisService
from apps.eventstore.events import DomainEventData, DomainEventFactory

from .models import Environment, PromotionApproval, PromotionPackage

_ENVS = [("dev", "Development", 0, False), ("test", "Test", 1, False),
         ("uat", "UAT", 2, False), ("prod", "Production", 3, True)]


class PromotionError(Exception):  # noqa: N818 — domain error
    pass


def _uid(actor_id):
    return uuid.UUID(str(actor_id)) if actor_id else None


def _emit(obj, event_type, payload, actor_id=None):
    from apps.eventstore.models import DomainEvent
    version = DomainEvent.objects.filter(
        aggregate_id=obj.id, aggregate_type="promotion_package").count() + 1
    DomainEventFactory.persist_one(DomainEventData(
        event_type=event_type, workspace_id=obj.workspace_id,
        aggregate_type="promotion_package", aggregate_id=obj.id, version=version,
        payload=payload, actor_id=_uid(actor_id) or uuid.UUID(int=0)))


class PromotionService:
    # ── environment registry ──────────────────────────────────────────────────
    @staticmethod
    def ensure_environments(*, workspace_id, actor_id=None) -> list[Environment]:
        """Provision DEV/TEST/UAT/PROD as Config VCS branches off main (idempotent)."""
        with contextlib.suppress(vcs.ConfigVCSError):
            vcs.commit(workspace_id=workspace_id, message="Environment baseline", branch="main")
        envs = []
        for env_type, name, seq, prod in _ENVS:
            with contextlib.suppress(vcs.ConfigVCSError):
                vcs.create_branch(workspace_id=workspace_id, name=env_type, from_branch="main",
                                  created_by=_uid(actor_id))
            env, _ = Environment.objects.get_or_create(
                workspace_id=workspace_id, env_type=env_type,
                defaults={"name": name, "branch": env_type, "sequence": seq,
                          "is_production": prod, "created_by": _uid(actor_id)})
            envs.append(env)
        return sorted(envs, key=lambda e: e.sequence)

    @staticmethod
    def _env(workspace_id, env_id):
        env = Environment.objects.filter(workspace_id=workspace_id, id=env_id).first()
        if env is None:
            raise PromotionError("Environment not found.")
        return env

    # ── package creation + diff + precheck ────────────────────────────────────
    @staticmethod
    def create_package(*, workspace_id, source_env_id, target_env_id, name, objects=None,
                       actor_id=None) -> PromotionPackage:
        src = PromotionService._env(workspace_id, source_env_id)
        tgt = PromotionService._env(workspace_id, target_env_id)
        if src.id == tgt.id:
            raise PromotionError("Source and target environments must differ.")
        src_branch = vcs.get_branch(workspace_id, src.branch)
        tgt_branch = vcs.get_branch(workspace_id, tgt.branch)
        # Diff = what source has that the target does not (Module 4) — reuse Config VCS diff.
        diff = {}
        with contextlib.suppress(Exception):
            diff = vcs.diff_commits(workspace_id=workspace_id, sha_a=tgt_branch.head_sha,
                                    sha_b=src_branch.head_sha)
        objects = objects or []
        precheck = AnalysisService.promotion_precheck(
            workspace_id=workspace_id, objects=objects, actor_id=actor_id)
        risk_summary = PromotionService._risk_summary(precheck)
        pkg = PromotionPackage.objects.create(
            workspace_id=workspace_id, name=name, source_env_id=src.id, target_env_id=tgt.id,
            status="precheck", object_refs=objects, diff=diff, precheck=precheck,
            risk_summary=risk_summary, source_sha=src_branch.head_sha,
            package_hash=PromotionService._hash(objects, src_branch.head_sha, diff),
            created_by=_uid(actor_id))
        _emit(pkg, "promotion.created",
              {"name": name, "source": src.env_type, "target": tgt.env_type,
               "risk": risk_summary}, actor_id)
        return pkg

    @staticmethod
    def _risk_summary(precheck) -> dict:
        levels = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        for o in precheck.get("objects", []):
            lvl = (o.get("risk") or {}).get("level", "low")
            levels[lvl] = levels.get(lvl, 0) + 1
        levels["blocked"] = precheck.get("blocked", False)
        return levels

    @staticmethod
    def _hash(objects, source_sha, diff) -> str:
        blob = json.dumps({"objects": objects, "source_sha": source_sha, "diff": diff},
                          sort_keys=True, default=str)
        return hashlib.sha256(blob.encode()).hexdigest()

    @staticmethod
    def _pkg(workspace_id, package_id):
        pkg = PromotionPackage.objects.filter(workspace_id=workspace_id, id=package_id).first()
        if pkg is None:
            raise PromotionError("Promotion package not found.")
        return pkg

    # ── approvals (segregation of duties) ─────────────────────────────────────
    @staticmethod
    def approve(*, workspace_id, package_id, role="approver", actor_id=None) -> PromotionPackage:
        pkg = PromotionService._pkg(workspace_id, package_id)
        if pkg.status not in {"precheck", "draft"}:
            raise PromotionError(f"Cannot approve a {pkg.status} package.")
        if _uid(actor_id) and pkg.created_by and _uid(actor_id) == pkg.created_by:
            raise PromotionError("Segregation of duties: the package creator cannot approve it.")
        PromotionApproval.objects.create(
            workspace_id=workspace_id, package_id=pkg.id, role=role,
            approver_id=_uid(actor_id), decision="approved", created_by=_uid(actor_id))
        pkg.status = "approved"
        pkg.approved_by = _uid(actor_id)
        pkg.save(update_fields=["status", "approved_by", "updated_at"])
        _emit(pkg, "promotion.approved", {"role": role}, actor_id)
        return pkg

    # ── execute (Dev→Test→UAT→Prod) ───────────────────────────────────────────
    @staticmethod
    def execute(*, workspace_id, package_id, dry_run=False, actor_id=None) -> dict:
        pkg = PromotionService._pkg(workspace_id, package_id)
        tgt = PromotionService._env(workspace_id, pkg.target_env_id)
        src = PromotionService._env(workspace_id, pkg.source_env_id)

        # Production requires an approval; critical risk is always blocked.
        if tgt.is_production and pkg.status != "approved":
            raise PromotionError("Promotion to production requires approval.")
        if pkg.status not in {"approved", "precheck"}:
            raise PromotionError(f"Cannot execute a {pkg.status} package.")
        if pkg.risk_summary.get("critical") or pkg.risk_summary.get("blocked"):
            raise PromotionError("Promotion blocked: critical dependency risk.")
        actor = _uid(actor_id)
        if actor and pkg.created_by and actor == pkg.created_by and tgt.is_production:
            raise PromotionError("Segregation of duties: the creator cannot execute a prod promotion.")

        tgt_branch = vcs.get_branch(workspace_id, tgt.branch)
        if dry_run:
            return {"dry_run": True, "would_merge": True, "source": src.env_type,
                    "target": tgt.env_type, "target_sha_before": tgt_branch.head_sha,
                    "risk": pkg.risk_summary, "diff": pkg.diff}

        pkg.target_sha_before = tgt_branch.head_sha   # rollback point (Module 11)
        pkg.started_at = timezone.now()
        try:
            mr = vcs.open_merge_request(
                workspace_id=workspace_id, source_branch=src.branch, target_branch=tgt.branch,
                title=f"Promote {pkg.name} ({src.env_type}→{tgt.env_type})", opened_by=actor)
            mr, conflicts = vcs.merge(workspace_id=workspace_id, mr_id=mr.id, merged_by=actor)
            if conflicts:
                pkg.status = "failed"
                pkg.ended_at = timezone.now()
                pkg.save()
                _emit(pkg, "promotion.failed", {"reason": "conflicts", "conflicts": conflicts},
                      actor_id)
                return {"status": "failed", "conflicts": conflicts}
            pkg.merge_commit_sha = mr.merge_commit_sha
            pkg.status = "executed"
            pkg.executed_by = actor
            pkg.ended_at = timezone.now()
            pkg.save()
        except vcs.ConfigVCSError as exc:
            pkg.status = "failed"
            pkg.ended_at = timezone.now()
            pkg.save(update_fields=["status", "ended_at", "updated_at"])
            _emit(pkg, "promotion.failed", {"reason": str(exc)}, actor_id)
            raise PromotionError(f"Promotion failed: {exc}") from exc
        _emit(pkg, "promotion.executed",
              {"merge_commit": pkg.merge_commit_sha, "target": tgt.env_type}, actor_id)
        return {"status": "executed", "merge_commit": pkg.merge_commit_sha,
                "rollback_point": pkg.target_sha_before}

    # ── rollback (Module 11) ──────────────────────────────────────────────────
    @staticmethod
    def rollback(*, workspace_id, package_id, actor_id=None) -> PromotionPackage:
        pkg = PromotionService._pkg(workspace_id, package_id)
        if pkg.status != "executed" or not pkg.target_sha_before:
            raise PromotionError("Only an executed promotion with a rollback point can be rolled back.")
        vcs.rollback(workspace_id=workspace_id, sha=pkg.target_sha_before, author_id=_uid(actor_id))
        pkg.status = "rolled_back"
        pkg.save(update_fields=["status", "updated_at"])
        _emit(pkg, "promotion.rolled_back", {"to": pkg.target_sha_before}, actor_id)
        return pkg

    # ── dashboards (Modules 14/22) ────────────────────────────────────────────
    @staticmethod
    def dashboard(*, workspace_id) -> dict:
        from django.db.models import Count
        rows = PromotionPackage.objects.filter(workspace_id=workspace_id).values(
            "status").annotate(n=Count("id"))
        by_status = {r["status"]: r["n"] for r in rows}
        executed = by_status.get("executed", 0) + by_status.get("rolled_back", 0)
        failed = by_status.get("failed", 0)
        total_terminal = executed + failed
        risk = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        for p in PromotionPackage.objects.filter(workspace_id=workspace_id).values_list(
                "risk_summary", flat=True):
            for lvl in risk:
                risk[lvl] += (p or {}).get(lvl, 0)
        return {
            "by_status": by_status,
            "pending": by_status.get("precheck", 0) + by_status.get("draft", 0),
            "approved": by_status.get("approved", 0),
            "rollbacks": by_status.get("rolled_back", 0),
            "success_rate": round(executed / total_terminal * 100, 1) if total_terminal else 0.0,
            "risk_distribution": risk,
            "release_velocity": executed,
        }
