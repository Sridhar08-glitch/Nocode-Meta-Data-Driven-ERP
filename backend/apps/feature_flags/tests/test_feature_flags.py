"""
Feature flags (Phase 1.29) — resolution precedence, deterministic rollout, API, isolation.
"""
import uuid

import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.feature_flags import services
from apps.feature_flags.models import FeatureFlag, FeatureFlagOverride
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"
BASE = "/api/v1/feature-flags"


# ── service-level ─────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestResolution:
    def test_default_enabled_full_rollout(self):
        ws = uuid.uuid4()
        FeatureFlag.objects.create(workspace_id=ws, key="beta", enabled=True, rollout_percent=100)
        flags = services.resolve_flags(ws, user_id=uuid.uuid4())
        assert flags["beta"]["enabled"] is True

    def test_default_disabled(self):
        ws = uuid.uuid4()
        FeatureFlag.objects.create(workspace_id=ws, key="beta", enabled=False)
        assert services.resolve_flags(ws, user_id=uuid.uuid4())["beta"]["enabled"] is False

    def test_inactive_flag_excluded(self):
        ws = uuid.uuid4()
        FeatureFlag.objects.create(workspace_id=ws, key="beta", enabled=True, is_active=False)
        assert "beta" not in services.resolve_flags(ws, user_id=uuid.uuid4())

    def test_user_override_beats_default(self):
        ws, user = uuid.uuid4(), uuid.uuid4()
        f = FeatureFlag.objects.create(workspace_id=ws, key="beta", enabled=False)
        FeatureFlagOverride.objects.create(workspace_id=ws, flag=f, target_type="user",
                                           target_id=user, enabled=True)
        assert services.is_enabled(ws, "beta", user_id=user) is True
        # a different user still gets the default
        assert services.is_enabled(ws, "beta", user_id=uuid.uuid4()) is False

    def test_precedence_user_over_role_over_workspace(self):
        ws, user, role = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        f = FeatureFlag.objects.create(workspace_id=ws, key="beta", enabled=False)
        FeatureFlagOverride.objects.create(workspace_id=ws, flag=f, target_type="workspace",
                                           target_id=None, enabled=True)
        FeatureFlagOverride.objects.create(workspace_id=ws, flag=f, target_type="role",
                                           target_id=role, enabled=False)
        FeatureFlagOverride.objects.create(workspace_id=ws, flag=f, target_type="user",
                                           target_id=user, enabled=True)
        # user override wins (True) even though role override says False
        assert services.is_enabled(ws, "beta", user_id=user, role_ids=[role]) is True
        # without the user, role override wins (False) over workspace (True)
        assert services.is_enabled(ws, "beta", user_id=uuid.uuid4(), role_ids=[role]) is False
        # no user/role match → workspace-wide override (True)
        assert services.is_enabled(ws, "beta", user_id=uuid.uuid4(), role_ids=[]) is True

    def test_rollout_deterministic_and_partial(self):
        ws = uuid.uuid4()
        FeatureFlag.objects.create(workspace_id=ws, key="beta", enabled=True, rollout_percent=50)
        # deterministic: same subject → same answer across calls
        u = uuid.uuid4()
        first = services.is_enabled(ws, "beta", user_id=u)
        assert first == services.is_enabled(ws, "beta", user_id=u)
        # matches the documented bucket formula
        expected = services.rollout_bucket(ws, "beta", u) < 50
        assert first == expected
        # partial rollout actually splits a population
        results = [services.is_enabled(ws, "beta", user_id=uuid.uuid4()) for _ in range(200)]
        assert 0 < sum(results) < 200

    def test_zero_rollout_is_off_even_when_enabled(self):
        ws = uuid.uuid4()
        FeatureFlag.objects.create(workspace_id=ws, key="beta", enabled=True, rollout_percent=0)
        assert services.is_enabled(ws, "beta", user_id=uuid.uuid4()) is False

    def test_workspace_isolation(self):
        ws_a, ws_b = uuid.uuid4(), uuid.uuid4()
        FeatureFlag.objects.create(workspace_id=ws_a, key="only_a", enabled=True)
        assert "only_a" in services.resolve_flags(ws_a)
        assert "only_a" not in services.resolve_flags(ws_b)


# ── HTTP-level ────────────────────────────────────────────────────────────────
@pytest.fixture
def workspace(db):
    return Workspace.objects.create(name="Acme", slug="acme", is_active=True)


def _client(workspace, role="admin", email=None):
    email = email or f"{role}@example.com"
    user = User.objects.create_user(email=email, password=PW, is_verified=True)
    WorkspaceMember.objects.create(workspace=workspace, user=user, role=role, status="active")
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}",
                  HTTP_X_WORKSPACE_SLUG=workspace.slug)
    return c, user


@pytest.mark.django_db
class TestFeatureFlagAPI:
    def test_admin_crud_flag(self, workspace):
        admin, _ = _client(workspace, "admin")
        cr = admin.post(f"{BASE}/", {"key": "new_ui", "enabled": True, "rollout_percent": 100},
                        format="json")
        assert cr.status_code == 201
        fid = cr.data["id"]
        assert admin.get(f"{BASE}/").status_code == 200
        pr = admin.patch(f"{BASE}/{fid}/", {"enabled": False}, format="json")
        assert pr.status_code == 200 and pr.data["enabled"] is False
        assert admin.delete(f"{BASE}/{fid}/").status_code == 204

    def test_duplicate_key_rejected(self, workspace):
        admin, _ = _client(workspace, "admin")
        admin.post(f"{BASE}/", {"key": "dup"}, format="json")
        r = admin.post(f"{BASE}/", {"key": "dup"}, format="json")
        assert r.status_code == 400

    def test_invalid_rollout_rejected(self, workspace):
        admin, _ = _client(workspace, "admin")
        r = admin.post(f"{BASE}/", {"key": "x", "rollout_percent": 150}, format="json")
        assert r.status_code == 400

    def test_member_cannot_manage_but_can_read_active(self, workspace):
        admin, _ = _client(workspace, "admin", email="a@example.com")
        admin.post(f"{BASE}/", {"key": "beta", "enabled": True}, format="json")
        member, _ = _client(workspace, "member", email="m@example.com")
        assert member.get(f"{BASE}/").status_code == 403          # cannot list raw flags
        assert member.post(f"{BASE}/", {"key": "z"}, format="json").status_code == 403
        act = member.get(f"{BASE}/active/")
        assert act.status_code == 200
        assert act.data["flags"]["beta"]["enabled"] is True

    def test_active_reflects_user_override(self, workspace):
        admin, _ = _client(workspace, "admin", email="a@example.com")
        fid = admin.post(f"{BASE}/", {"key": "beta", "enabled": False}, format="json").data["id"]
        member, muser = _client(workspace, "member", email="m@example.com")
        admin.post(f"{BASE}/{fid}/overrides/",
                   {"target_type": "user", "target_id": str(muser.id), "enabled": True},
                   format="json")
        act = member.get(f"{BASE}/active/")
        assert act.data["flags"]["beta"]["enabled"] is True

    def test_override_validation(self, workspace):
        admin, _ = _client(workspace, "admin")
        fid = admin.post(f"{BASE}/", {"key": "beta"}, format="json").data["id"]
        # role override without target_id → 400
        r = admin.post(f"{BASE}/{fid}/overrides/", {"target_type": "role"}, format="json")
        assert r.status_code == 400

    def test_delete_override(self, workspace):
        admin, _ = _client(workspace, "admin")
        fid = admin.post(f"{BASE}/", {"key": "beta"}, format="json").data["id"]
        oid = admin.post(f"{BASE}/{fid}/overrides/",
                         {"target_type": "workspace", "enabled": True}, format="json").data["id"]
        assert admin.delete(f"{BASE}/{fid}/overrides/{oid}/").status_code == 204

    def test_cross_workspace_flag_not_visible(self, workspace):
        admin, _ = _client(workspace, "admin", email="a@example.com")
        admin.post(f"{BASE}/", {"key": "secret", "enabled": True}, format="json")
        other_ws = Workspace.objects.create(name="Other", slug="other", is_active=True)
        oc, _ = _client(other_ws, "admin", email="o@example.com")
        assert "secret" not in oc.get(f"{BASE}/active/").data["flags"]
        assert oc.get(f"{BASE}/").data == []
