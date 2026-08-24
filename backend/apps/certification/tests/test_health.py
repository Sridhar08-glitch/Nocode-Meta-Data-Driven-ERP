"""
Health service tests (P2.16 Modules 24, 26, 27, 30).
"""
import uuid

import pytest

from apps.accounts.models import User
from apps.tenancy.models import Workspace


def _ws():
    ws = Workspace.objects.create(
        name=f"Health WS {uuid.uuid4().hex[:6]}",
        slug=f"health-ws-{uuid.uuid4().hex[:6]}",
        is_active=True)
    return ws


def _user():
    return User.objects.create_user(
        email=f"health_{uuid.uuid4().hex[:6]}@test.com",
        password="Pass1234!!", full_name="Health User", is_verified=True)


@pytest.mark.django_db
class TestModuleHealth:
    def test_module_health_returns_all_modules(self):
        from apps.certification.health import MODULE_CHECKS, module_health
        ws = _ws()
        result = module_health(ws.id)
        assert "modules" in result
        assert "overall" in result
        # All defined checks should appear in result
        for check_name in MODULE_CHECKS:
            assert check_name in result["modules"], \
                f"Missing health module: {check_name}"

    def test_module_health_overall_is_valid(self):
        from apps.certification.health import module_health
        ws = _ws()
        result = module_health(ws.id)
        assert result["overall"] in ("healthy", "warning", "failed")

    def test_each_module_has_status(self):
        from apps.certification.health import module_health
        ws = _ws()
        result = module_health(ws.id)
        for name, info in result["modules"].items():
            assert "status" in info, f"Module {name} missing status"
            assert info["status"] in ("healthy", "warning", "failed"), \
                f"Invalid status for {name}: {info['status']}"


@pytest.mark.django_db
class TestIntegrationHealthAPI:
    def test_integration_health_structure(self):
        from apps.certification.health import integration_health
        result = integration_health()
        assert "total_integrations" in result
        assert "certified" in result
        assert "compliance_pct" in result
        assert result["total_integrations"] >= 15
        assert result["certified"] >= 10
        assert result["compliance_pct"] >= 50.0

    def test_integration_health_lists_integrations(self):
        from apps.certification.health import integration_health
        result = integration_health()
        assert isinstance(result["integrations"], list)
        assert len(result["integrations"]) == result["total_integrations"]
        for entry in result["integrations"]:
            assert "source" in entry
            assert "target" in entry
            assert "status" in entry


@pytest.mark.django_db
class TestReadinessSummary:
    def test_readiness_summary_structure(self):
        from apps.certification.health import readiness_summary
        ws = _ws()
        result = readiness_summary(ws.id)
        assert "modules" in result
        assert "readiness_pct" in result
        assert "total_modules" in result
        assert 0 <= result["readiness_pct"] <= 100

    def test_readiness_summary_covers_all_erp_modules(self):
        from apps.certification.health import ERP_MODULES, readiness_summary
        ws = _ws()
        result = readiness_summary(ws.id)
        for module in ERP_MODULES:
            assert module in result["modules"], f"Missing ERP module: {module}"

    def test_readiness_status_values_valid(self):
        from apps.certification.health import readiness_summary
        ws = _ws()
        result = readiness_summary(ws.id)
        valid_statuses = {"active", "ready", "not_installed"}
        for module, info in result["modules"].items():
            assert info["status"] in valid_statuses, \
                f"Invalid status for {module}: {info['status']}"


@pytest.mark.django_db
class TestCertificationReport:
    def test_report_structure(self):
        from apps.certification.report import generate_report
        ws = _ws()
        report = generate_report(ws.id)
        required_keys = [
            "report_title", "generated_at", "workspace_id",
            "overall_readiness_score", "overall_health", "readiness_pct",
            "sections", "integration_health", "architecture_validation",
            "module_health", "executive_readiness", "recommendations", "verdict",
        ]
        for key in required_keys:
            assert key in report, f"Report missing key: {key}"

    def test_report_verdict_is_valid(self):
        from apps.certification.report import generate_report
        ws = _ws()
        report = generate_report(ws.id)
        assert report["verdict"] in (
            "ENTERPRISE_CERTIFIED", "READY_WITH_WARNINGS", "NEEDS_ATTENTION")

    def test_report_score_in_range(self):
        from apps.certification.report import generate_report
        ws = _ws()
        report = generate_report(ws.id)
        assert 0 <= report["overall_readiness_score"] <= 100

    def test_architecture_validation_structure(self):
        from apps.certification.report import validate_architecture
        result = validate_architecture()
        assert "engines" in result
        assert "overall" in result
        assert result["overall"] in ("verified", "warning", "failed")
        assert result["verified_count"] > 0
