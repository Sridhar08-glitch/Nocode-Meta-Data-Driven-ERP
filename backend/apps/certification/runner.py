"""
CertificationRunner — single orchestration entry point for all certification views.

Views MUST call CertificationRunner methods only. Direct calls to health/simulation/report
functions from views are prohibited (architecture §8 requirement).
"""
from __future__ import annotations

import uuid


class CertificationRunner:
    """Single orchestration service for P2.16 certification endpoints.

    Every view delegates to one method here. This class contains NO business logic —
    it delegates to health.py, simulation.py, report.py, and registry.py.
    """

    # ── integration registry ──────────────────────────────────────────────────

    @staticmethod
    def get_integration_registry() -> dict:
        """Return full integration registry metadata."""
        from apps.certification.registry import (
            BY_SOURCE,
            BY_TARGET,
            CERTIFICATION_CHECKLIST,
            INTEGRATION_REGISTRY,
            all_certified,
        )
        return {
            "total_integrations": len(INTEGRATION_REGISTRY),
            "certified_count": len(all_certified()),
            "integrations": [
                {
                    "id": f"{i.source_module}__{i.target_module}",
                    "source_module": i.source_module,
                    "target_module": i.target_module,
                    "service": i.service,
                    "trigger": i.trigger,
                    "event": i.event,
                    "accounting_impact": i.accounting_impact,
                    "analytics_impact": i.analytics_impact,
                    "audit_events": i.audit_events,
                    "notification_slugs": i.notification_slugs,
                    "idempotency_guard": i.idempotency_guard,
                    "status": i.status,
                }
                for i in INTEGRATION_REGISTRY
            ],
            "by_source": {src: len(ints) for src, ints in BY_SOURCE.items()},
            "by_target": {tgt: len(ints) for tgt, ints in BY_TARGET.items()},
            "checklist_count": len(CERTIFICATION_CHECKLIST),
        }

    # ── health ────────────────────────────────────────────────────────────────

    @staticmethod
    def get_module_health(workspace_id: uuid.UUID) -> dict:
        """Return module health checks for a workspace."""
        from apps.certification.health import module_health
        return module_health(workspace_id)

    @staticmethod
    def get_integration_health() -> dict:
        """Return integration registry health summary."""
        from apps.certification.health import integration_health
        return integration_health()

    @staticmethod
    def get_readiness_summary(workspace_id: uuid.UUID) -> dict:
        """Return per-module ERP readiness for a workspace."""
        from apps.certification.health import readiness_summary
        return readiness_summary(workspace_id)

    # ── certification report ──────────────────────────────────────────────────

    @staticmethod
    def generate_certification_report(workspace_id: uuid.UUID) -> dict:
        """Generate full certification report for a workspace."""
        from apps.certification.report import generate_report
        return generate_report(workspace_id)

    @staticmethod
    def run_architecture_validation() -> dict:
        """Validate all canonical engine locations are importable."""
        from apps.certification.report import validate_architecture
        return validate_architecture()

    # ── checklist ─────────────────────────────────────────────────────────────

    @staticmethod
    def get_checklist() -> list[dict]:
        """Return the 32-item certification checklist with honest, evidence-backed status."""
        from apps.certification import status as cert_status
        items = cert_status.as_dicts()
        for it in items:
            it["name"] = it["name"]  # keep `name` key for the FE
        return items

    @staticmethod
    def get_status_summary() -> dict:
        """Return the honest status roll-up (counts + per-category compliance)."""
        from apps.certification import status as cert_status
        return {
            "counts": cert_status.status_counts(),
            "overall": cert_status.overall_status(),
            "readiness_score": cert_status.readiness_score(),
            "by_category": cert_status.by_category(),
            "items": cert_status.as_dicts(),
        }

    # ── simulations ───────────────────────────────────────────────────────────

    @staticmethod
    def list_scenarios() -> dict:
        """Return available simulation scenarios."""
        from apps.certification.simulation import SCENARIOS
        return {
            "scenarios": [
                {
                    "key": key,
                    "name": meta["name"],
                    "description": meta.get("description", ""),
                    "modules": meta.get("modules", []),
                }
                for key, meta in SCENARIOS.items()
            ],
            "total": len(SCENARIOS),
        }

    @staticmethod
    def run_scenario(scenario_key: str, workspace_id: uuid.UUID, actor_id: uuid.UUID) -> dict:
        """Execute a single simulation scenario and return the result."""
        from apps.certification.simulation import run_scenario
        result = run_scenario(scenario_key, workspace_id, actor_id)
        return {
            "scenario": scenario_key,
            "passed": result.passed,
            "steps": [
                {
                    "name": step.name,
                    "status": step.status,
                    "detail": step.detail,
                    "error": step.error,
                }
                for step in result.steps
            ],
            "summary": result.summary,
        }

    @staticmethod
    def run_all_scenarios(workspace_id: uuid.UUID, actor_id: uuid.UUID) -> dict:
        """Execute all simulation scenarios and aggregate results."""
        from apps.certification.simulation import run_all_scenarios
        results = run_all_scenarios(workspace_id, actor_id)
        total = len(results)
        passed = sum(1 for r in results.values() if r.passed)
        return {
            "total_scenarios": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate_pct": round(passed / total * 100, 1) if total else 0,
            "scenarios": {
                key: {
                    "passed": r.passed,
                    "step_count": len(r.steps),
                    "failed_steps": [s.name for s in r.steps if s.status == "failed"],
                    "summary": r.summary,
                }
                for key, r in results.items()
            },
        }
