"""
Environment Promotion (Phase P2.15) — orchestration over Config VCS + P2.14. Environment registry,
promotion packages (diff + precheck + risk), segregation-of-duties approvals, promotion via merge,
rollback via config_vcs.rollback, audit, and the DEV→TEST→UAT→PROD end-to-end certification.
Covers spec Modules 1-13/24.
"""
import uuid

import pytest

from apps.config_vcs import services as vcs
from apps.environments.models import Environment, PromotionApproval, PromotionPackage
from apps.environments.services import PromotionError, PromotionService
from apps.eventstore.models import DomainEvent
from apps.schema_registry.services import SchemaRegistryService

A, B, C = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())


def _envs(ws):
    return {e.env_type: e for e in PromotionService.ensure_environments(
        workspace_id=ws, actor_id=A)}


# ── environment registry (Module 1) ──────────────────────────────────────────
@pytest.mark.django_db
def test_ensure_environments_maps_to_branches():
    ws = uuid.uuid4()
    envs = _envs(ws)
    assert set(envs) == {"dev", "test", "uat", "prod"}
    assert envs["prod"].is_production and envs["dev"].sequence < envs["prod"].sequence
    # Each environment IS a Config VCS branch (reuse, not a new VCS).
    for et in ("dev", "test", "uat", "prod"):
        assert vcs.get_branch(ws, et) is not None
    # idempotent
    PromotionService.ensure_environments(workspace_id=ws, actor_id=A)
    assert Environment.objects.filter(workspace_id=ws).count() == 4


# ── package + diff + precheck (Modules 2-6) ──────────────────────────────────
@pytest.mark.django_db
def test_create_package_runs_precheck_and_audit():
    ws = uuid.uuid4()
    envs = _envs(ws)
    pkg = PromotionService.create_package(
        workspace_id=ws, source_env_id=envs["dev"].id, target_env_id=envs["test"].id,
        name="Sprint 1", objects=[], actor_id=A)
    assert pkg.status == "precheck" and pkg.package_hash
    assert "low" in pkg.risk_summary                     # risk reused from P2.14 precheck
    assert DomainEvent.objects.filter(event_type="promotion.created").exists()


# ── segregation of duties (Module 7) ─────────────────────────────────────────
@pytest.mark.django_db
def test_segregation_of_duties_on_approval():
    ws = uuid.uuid4()
    envs = _envs(ws)
    pkg = PromotionService.create_package(
        workspace_id=ws, source_env_id=envs["dev"].id, target_env_id=envs["test"].id,
        name="P", objects=[], actor_id=A)
    with pytest.raises(PromotionError):           # creator cannot approve
        PromotionService.approve(workspace_id=ws, package_id=pkg.id, actor_id=A)
    pkg = PromotionService.approve(workspace_id=ws, package_id=pkg.id, actor_id=B)
    assert pkg.status == "approved"
    assert PromotionApproval.objects.filter(workspace_id=ws, package_id=pkg.id).count() == 1
    assert DomainEvent.objects.filter(event_type="promotion.approved").exists()


# ── dry run (Module 17) + critical-risk block ────────────────────────────────
@pytest.mark.django_db
def test_dry_run_and_critical_block():
    ws = uuid.uuid4()
    envs = _envs(ws)
    pkg = PromotionService.create_package(
        workspace_id=ws, source_env_id=envs["dev"].id, target_env_id=envs["test"].id,
        name="P", objects=[], actor_id=A)
    dry = PromotionService.execute(workspace_id=ws, package_id=pkg.id, dry_run=True, actor_id=B)
    assert dry["dry_run"] is True and dry["would_merge"] is True
    assert PromotionPackage.objects.get(id=pkg.id).status == "precheck"  # unchanged by dry-run

    pkg.risk_summary = {"critical": 1}
    pkg.save(update_fields=["risk_summary"])
    with pytest.raises(PromotionError):           # critical risk blocks promotion
        PromotionService.execute(workspace_id=ws, package_id=pkg.id, actor_id=B)


# ── Module 24: DEV → TEST → UAT → PROD end-to-end certification ──────────────
@pytest.mark.django_db
def test_e2e_dev_test_uat_prod_with_approval_merge_rollback():
    ws = uuid.uuid4()
    envs = _envs(ws)
    # A real config change makes DEV ahead of the chain (then it propagates down).
    SchemaRegistryService.create_entity(
        workspace_id=ws, slug="widget", name="Widget", plural_name="Widgets",
        fields=[{"slug": "name", "name": "Name", "field_type": "text", "is_promoted": True}])
    vcs.commit(workspace_id=ws, message="add widget", branch="dev")

    last_pkg = None
    for src, tgt in [("dev", "test"), ("test", "uat"), ("uat", "prod")]:
        pkg = PromotionService.create_package(
            workspace_id=ws, source_env_id=envs[src].id, target_env_id=envs[tgt].id,
            name=f"{src}->{tgt}", objects=[], actor_id=A)
        # precheck → approve (B ≠ creator) → execute (C ≠ creator). PROD requires the approval.
        PromotionService.approve(workspace_id=ws, package_id=pkg.id, role="release_manager",
                                 actor_id=B)
        out = PromotionService.execute(workspace_id=ws, package_id=pkg.id, actor_id=C)
        assert out["status"] == "executed" and out["merge_commit"]
        pkg.refresh_from_db()
        assert pkg.status == "executed" and pkg.target_sha_before
        last_pkg = pkg

    # The actual promotion was performed by Config VCS merge (target heads advanced).
    assert vcs.get_branch(ws, "prod").head_sha == last_pkg.merge_commit_sha
    for ev in ["promotion.created", "promotion.approved", "promotion.executed"]:
        assert DomainEvent.objects.filter(event_type=ev).exists(), ev

    # Rollback the PROD promotion via config_vcs.rollback (no own rollback engine).
    rolled = PromotionService.rollback(workspace_id=ws, package_id=last_pkg.id, actor_id=C)
    assert rolled.status == "rolled_back"
    assert DomainEvent.objects.filter(event_type="promotion.rolled_back").exists()


# ── dashboard (Modules 14/22) ────────────────────────────────────────────────
@pytest.mark.django_db
def test_promotion_dashboard():
    ws = uuid.uuid4()
    envs = _envs(ws)
    PromotionService.create_package(
        workspace_id=ws, source_env_id=envs["dev"].id, target_env_id=envs["test"].id,
        name="P", objects=[], actor_id=A)
    dash = PromotionService.dashboard(workspace_id=ws)
    assert "by_status" in dash and "success_rate" in dash and "risk_distribution" in dash
    assert dash["pending"] >= 1
