"""MarketplaceService + validator + API (PROJECT_HANDBOOK.md §34.5)."""
import pytest

from apps.marketplace.models import InstalledPlugin, MarketplacePlugin, PluginVersion
from apps.marketplace.services import MarketplaceError, MarketplaceService
from apps.marketplace.validators import validate_manifest
from apps.metadata.models import EntityDefinition, FieldDefinition
from apps.rules.models import BusinessRule
from apps.workflows.models import WorkflowDefinition

from .conftest import _make_version, make_manifest

BASE = "/api/v1/marketplace"


class TestValidator:
    def test_valid_manifest_has_no_errors(self):
        assert validate_manifest(make_manifest()) == []

    def test_invalid_field_type(self):
        m = make_manifest()
        m["entities"][0]["fields"][0]["field_type"] = "not_a_type"
        errs = validate_manifest(m)
        assert any("field_type" in e for e in errs)

    def test_duplicate_slug(self):
        m = make_manifest()
        m["entities"].append(m["entities"][0])
        assert any("duplicate entity" in e for e in validate_manifest(m))

    def test_nql_parse_error(self):
        m = make_manifest()
        m["rules"][0]["condition_nql"] = "this is >>> not valid nql @@@"
        assert any("invalid NQL" in e for e in validate_manifest(m))

    def test_manifest_too_large(self):
        m = make_manifest()
        m["blob"] = "x" * (512 * 1024 + 10)
        assert any("too large" in e for e in validate_manifest(m))

    def test_bad_edge_reference(self):
        m = make_manifest()
        m["workflows"][0]["edges"] = [{"source": "s1", "target": "ghost"}]
        assert any("unknown step" in e for e in validate_manifest(m))

    def test_wrong_schema_version(self):
        m = make_manifest()
        m["schema_version"] = 2
        assert any("schema_version" in e for e in validate_manifest(m))


@pytest.mark.django_db
class TestInstall:
    def test_install_creates_all_objects(self, ws, member, plugin):
        p, v = plugin
        ip = MarketplaceService.install_plugin(
            plugin_id=p.id, version_id=v.id, workspace_id=ws.id, installed_by=member.user_id)
        assert ip.status == "active"
        entity = EntityDefinition.objects.get(workspace_id=ws.id, slug="ticket")
        assert entity.has_physical_table and entity.table_name
        assert FieldDefinition.objects.filter(entity=entity, slug="subject").exists()
        wf = WorkflowDefinition.objects.get(workspace_id=ws.id, slug="notify")
        assert wf.status == "active"
        assert BusinessRule.objects.get(workspace_id=ws.id, slug="auto_high").is_active is True
        p.refresh_from_db()
        assert p.install_count == 1

    def test_install_rolls_back_on_failure(self, ws, member, plugin, monkeypatch):
        p, v = plugin
        from apps.marketplace import services
        monkeypatch.setattr(services, "_apply_rules",
                            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
        with pytest.raises(Exception):  # noqa: B017
            MarketplaceService.install_plugin(
                plugin_id=p.id, version_id=v.id, workspace_id=ws.id, installed_by=member.user_id)
        # transaction rolled back — no entity, no InstalledPlugin row left behind
        assert not EntityDefinition.objects.filter(workspace_id=ws.id, slug="ticket").exists()
        assert not InstalledPlugin.objects.filter(workspace_id=ws.id, plugin_slug=p.slug).exists()

    def test_cannot_install_unpublished(self, ws, member):
        p = MarketplacePlugin.objects.create(
            slug="draft1", name="Draft", tagline="t", description="d",
            category="utility", status="draft")
        v = _make_version(p, "1.0.0", make_manifest())
        with pytest.raises(MarketplaceError):
            MarketplaceService.install_plugin(
                plugin_id=p.id, version_id=v.id, workspace_id=ws.id, installed_by=member.user_id)

    def test_double_install_rejected(self, ws, member, plugin):
        p, v = plugin
        MarketplaceService.install_plugin(
            plugin_id=p.id, version_id=v.id, workspace_id=ws.id, installed_by=member.user_id)
        with pytest.raises(MarketplaceError):
            MarketplaceService.install_plugin(
                plugin_id=p.id, version_id=v.id, workspace_id=ws.id, installed_by=member.user_id)


@pytest.mark.django_db
class TestUninstall:
    def test_soft_uninstall_preserves_entities(self, ws, member, plugin):
        p, v = plugin
        ip = MarketplaceService.install_plugin(
            plugin_id=p.id, version_id=v.id, workspace_id=ws.id, installed_by=member.user_id)
        MarketplaceService.uninstall_plugin(
            installed_plugin_id=ip.id, workspace_id=ws.id, actor_id=member.user_id, hard=False)
        wf = WorkflowDefinition.objects.get(workspace_id=ws.id, slug="notify")
        assert wf.status == "archived"
        assert not BusinessRule.objects.get(workspace_id=ws.id, slug="auto_high").is_active
        # entity preserved + still active
        assert EntityDefinition.objects.get(workspace_id=ws.id, slug="ticket").is_active is True

    def test_hard_uninstall_soft_deletes_entities(self, ws, member, plugin):
        p, v = plugin
        ip = MarketplaceService.install_plugin(
            plugin_id=p.id, version_id=v.id, workspace_id=ws.id, installed_by=member.user_id)
        MarketplaceService.uninstall_plugin(
            installed_plugin_id=ip.id, workspace_id=ws.id, actor_id=member.user_id, hard=True)
        assert EntityDefinition.objects.get(workspace_id=ws.id, slug="ticket").is_active is False


@pytest.mark.django_db
class TestUpgradeRollback:
    def test_upgrade_adds_new_fields_keeps_existing(self, ws, member, plugin):
        p, v = plugin
        ip = MarketplaceService.install_plugin(
            plugin_id=p.id, version_id=v.id, workspace_id=ws.id, installed_by=member.user_id)
        v2 = _make_version(p, "2.0.0", make_manifest(extra_field=True))
        ip = MarketplaceService.upgrade_plugin(
            installed_plugin_id=ip.id, new_version_id=v2.id, actor_id=member.user_id)
        assert ip.installed_version == "2.0.0"
        entity = EntityDefinition.objects.get(workspace_id=ws.id, slug="ticket")
        assert FieldDefinition.objects.filter(entity=entity, slug="category").exists()  # new
        assert FieldDefinition.objects.filter(entity=entity, slug="subject").exists()   # kept
        # old workflow not deleted
        assert WorkflowDefinition.objects.filter(workspace_id=ws.id, slug="notify").exists()

    def test_rollback_restores_version_keeps_schema(self, ws, member, plugin):
        p, v = plugin
        ip = MarketplaceService.install_plugin(
            plugin_id=p.id, version_id=v.id, workspace_id=ws.id, installed_by=member.user_id)
        v2 = _make_version(p, "2.0.0", make_manifest(extra_field=True))
        ip = MarketplaceService.upgrade_plugin(
            installed_plugin_id=ip.id, new_version_id=v2.id, actor_id=member.user_id)
        ip = MarketplaceService.rollback_plugin(
            installed_plugin_id=ip.id, actor_id=member.user_id)
        assert str(ip.plugin_version_id) == str(v.id)
        assert ip.installed_version == "1.0.0"
        # schema addition from the upgrade is NOT undone (data safety)
        entity = EntityDefinition.objects.get(workspace_id=ws.id, slug="ticket")
        assert FieldDefinition.objects.filter(entity=entity, slug="category").exists()


@pytest.mark.django_db
class TestBrowseAndManageApi:
    def test_public_browse_lists_published(self, plugin):
        from rest_framework.test import APIClient
        p, _ = plugin
        anon = APIClient()
        r = anon.get(f"{BASE}/plugins/")
        assert r.status_code == 200
        assert any(item["slug"] == "helpdesk" for item in r.json()["results"])

    def test_install_via_api(self, client, ws, plugin):
        p, v = plugin
        r = client.post(f"{BASE}/plugins/{p.id}/install/",
                        {"version_id": str(v.id)}, format="json")
        assert r.status_code == 201 and r.json()["status"] == "active"
        assert client.get(f"{BASE}/installed/").json()["results"]

    def test_install_unpublished_via_api_400(self, client, ws):
        p = MarketplacePlugin.objects.create(
            slug="d2", name="D", tagline="t", description="d", category="utility",
            status="draft")
        v = _make_version(p, "1.0.0", make_manifest())
        r = client.post(f"{BASE}/plugins/{p.id}/install/",
                        {"version_id": str(v.id)}, format="json")
        assert r.status_code == 400

    def test_publisher_only_staff_can_publish(self, client, staff_client):
        # non-staff member is forbidden
        draft = {"slug": "newp", "name": "New", "tagline": "t", "description": "d",
                 "category": "utility"}
        assert client.post(f"{BASE}/manage/plugins/", draft, format="json").status_code == 403
        # staff can create + publish
        r = staff_client.post(f"{BASE}/manage/plugins/", draft, format="json")
        assert r.status_code == 201
        pid = r.json()["id"]
        pub = staff_client.post(f"{BASE}/manage/plugins/{pid}/publish/")
        assert pub.status_code == 200 and pub.json()["status"] == "published"

    def test_publisher_submit_version_validates_manifest(self, staff_client):
        r = staff_client.post(f"{BASE}/manage/plugins/",
                              {"slug": "vp", "name": "VP", "tagline": "t",
                               "description": "d", "category": "utility"}, format="json")
        pid = r.json()["id"]
        bad = make_manifest()
        bad["entities"][0]["fields"][0]["field_type"] = "nope"
        assert staff_client.post(f"{BASE}/manage/plugins/{pid}/versions/",
                                 {"version": "1.0.0", "manifest": bad},
                                 format="json").status_code == 400
        ok = staff_client.post(f"{BASE}/manage/plugins/{pid}/versions/",
                               {"version": "1.0.0", "manifest": make_manifest()},
                               format="json")
        assert ok.status_code == 201
        assert PluginVersion.objects.filter(plugin_id=pid, version="1.0.0").exists()
