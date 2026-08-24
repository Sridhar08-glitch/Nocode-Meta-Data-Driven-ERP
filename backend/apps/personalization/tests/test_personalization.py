"""
Personalization (Phase P0) — registry validation, resolver precedence, admin lock
policy, accessibility non-lockability, reset, API, and workspace isolation.
"""
import uuid

import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.branding.models import WorkspaceBranding
from apps.personalization import registry, services
from apps.personalization.models import UserPreference
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"
BASE = "/api/v1/me"


# ── registry validation ───────────────────────────────────────────────────────
@pytest.mark.django_db
class TestRegistry:
    def test_unknown_key_rejected(self):
        with pytest.raises(registry.PersonalizationError):
            registry.validate_values({"nope": "x"})

    def test_enum_out_of_set_rejected(self):
        with pytest.raises(registry.PersonalizationError):
            registry.validate_values({"theme": "neon"})

    def test_int_range_enforced(self):
        with pytest.raises(registry.PersonalizationError):
            registry.validate_values({"font_scale": 300})
        assert registry.validate_values({"font_scale": 120}) == {"font_scale": 120}

    def test_bool_type_enforced(self):
        with pytest.raises(registry.PersonalizationError):
            registry.validate_values({"high_contrast": "yes"})
        assert registry.validate_values({"high_contrast": True}) == {"high_contrast": True}

    def test_color_must_be_hex(self):
        with pytest.raises(registry.PersonalizationError):
            registry.validate_values({"accent": "blue-ish"})
        assert registry.validate_values({"accent": "#abc"}) == {"accent": "#abc"}

    def test_accessibility_keys_never_lockable(self):
        for key in registry.ACCESSIBILITY_KEYS:
            assert registry.is_lockable(key) is False


# ── resolver ───────────────────────────────────────────────────────────────────
@pytest.mark.django_db
class TestResolver:
    def test_system_defaults_when_no_branding_no_prefs(self):
        ws, user = uuid.uuid4(), uuid.uuid4()
        res = services.resolve_appearance(ws, user_id=user)
        assert res["appearance"]["theme"] == "system"
        assert res["appearance"]["density"] == "comfortable"
        assert res["appearance"]["font_scale"] == 100
        assert res["locked"] == []

    def test_workspace_branding_supplies_defaults(self):
        ws, user = uuid.uuid4(), uuid.uuid4()
        WorkspaceBranding.objects.create(workspace_id=ws, ui_density="compact",
                                         border_radius="lg", default_theme="dark")
        res = services.resolve_appearance(ws, user_id=user)
        assert res["appearance"]["density"] == "compact"
        assert res["appearance"]["radius"] == "lg"
        assert res["appearance"]["theme"] == "dark"
        assert res["sources"]["density"] == "workspace"

    def test_user_override_beats_workspace_default(self):
        ws, user = uuid.uuid4(), uuid.uuid4()
        WorkspaceBranding.objects.create(workspace_id=ws, ui_density="compact")
        services.set_user_values(ws, user, {"density": "comfortable"})
        res = services.resolve_appearance(ws, user_id=user)
        assert res["appearance"]["density"] == "comfortable"
        assert res["sources"]["density"] == "user"

    def test_locked_field_ignores_user_override(self):
        ws, user = uuid.uuid4(), uuid.uuid4()
        WorkspaceBranding.objects.create(workspace_id=ws, ui_density="compact",
                                         locked_fields=["density"])
        # user had previously set a value directly in the row
        UserPreference.objects.create(workspace_id=ws, user_id=user,
                                      values={"density": "comfortable"})
        res = services.resolve_appearance(ws, user_id=user)
        assert res["appearance"]["density"] == "compact"      # workspace wins
        assert res["sources"]["density"] == "workspace_locked"
        assert "density" in res["locked"]

    def test_set_locked_field_raises(self):
        ws, user = uuid.uuid4(), uuid.uuid4()
        WorkspaceBranding.objects.create(workspace_id=ws, locked_fields=["accent"])
        with pytest.raises(services.LockedPreferenceError):
            services.set_user_values(ws, user, {"accent": "#123456"})

    def test_accessibility_key_settable_even_if_listed_locked(self):
        ws, user = uuid.uuid4(), uuid.uuid4()
        # font_scale is accessibility → not lockable even if an admin lists it
        WorkspaceBranding.objects.create(workspace_id=ws, locked_fields=["font_scale"])
        services.set_user_values(ws, user, {"font_scale": 130})
        res = services.resolve_appearance(ws, user_id=user)
        assert res["appearance"]["font_scale"] == 130
        assert "font_scale" not in res["locked"]

    def test_reset_all_and_specific(self):
        ws, user = uuid.uuid4(), uuid.uuid4()
        services.set_user_values(ws, user, {"density": "compact", "font_scale": 120})
        assert services.reset_user_values(ws, user, keys=["density"]) == {"font_scale": 120}
        assert services.reset_user_values(ws, user) == {}

    def test_reset_unknown_key_rejected(self):
        ws, user = uuid.uuid4(), uuid.uuid4()
        services.set_user_values(ws, user, {"density": "compact"})
        with pytest.raises(registry.PersonalizationError):
            services.reset_user_values(ws, user, keys=["bogus"])

    def test_workspace_isolation(self):
        ws_a, ws_b, user = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        services.set_user_values(ws_a, user, {"density": "compact"})
        assert services.get_user_values(ws_a, user) == {"density": "compact"}
        assert services.get_user_values(ws_b, user) == {}


# ── HTTP ───────────────────────────────────────────────────────────────────────
@pytest.fixture
def workspace(db):
    return Workspace.objects.create(name="Acme", slug="acme", is_active=True)


def _client(workspace, role="member", email=None):
    email = email or f"{role}@example.com"
    user = User.objects.create_user(email=email, password=PW, is_verified=True)
    WorkspaceMember.objects.create(workspace=workspace, user=user, role=role, status="active")
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}",
                  HTTP_X_WORKSPACE_SLUG=workspace.slug)
    return c, user


@pytest.mark.django_db
class TestPersonalizationAPI:
    def test_member_can_read_appearance(self, workspace):
        member, _ = _client(workspace, "member")
        r = member.get(f"{BASE}/appearance/")
        assert r.status_code == 200
        assert r.data["appearance"]["theme"] == "system"
        assert "allow_theme_toggle" in r.data

    def test_put_and_get_preferences_roundtrip(self, workspace):
        member, _ = _client(workspace, "member")
        pr = member.put(f"{BASE}/preferences/", {"values": {"density": "compact"}}, format="json")
        assert pr.status_code == 200 and pr.data["values"]["density"] == "compact"
        got = member.get(f"{BASE}/preferences/")
        assert got.data["values"]["density"] == "compact"
        assert "density" in got.data["registry"]                    # catalogue exposed
        # and the effective appearance reflects it
        assert member.get(f"{BASE}/appearance/").data["appearance"]["density"] == "compact"

    def test_put_invalid_value_400(self, workspace):
        member, _ = _client(workspace, "member")
        r = member.put(f"{BASE}/preferences/", {"values": {"theme": "neon"}}, format="json")
        assert r.status_code == 400

    def test_locked_field_put_forbidden_403(self, workspace):
        WorkspaceBranding.objects.create(workspace_id=workspace.id, locked_fields=["accent"])
        member, _ = _client(workspace, "member")
        r = member.put(f"{BASE}/preferences/", {"values": {"accent": "#101010"}}, format="json")
        assert r.status_code == 403

    def test_reset_endpoint(self, workspace):
        member, _ = _client(workspace, "member")
        member.put(f"{BASE}/preferences/", {"values": {"density": "compact"}}, format="json")
        rr = member.post(f"{BASE}/preferences/reset/", {}, format="json")
        assert rr.status_code == 200 and rr.data["values"] == {}

    def test_unauthenticated_rejected(self, workspace):
        anon = APIClient()
        assert anon.get(f"{BASE}/appearance/").status_code in (401, 403)

    def test_cross_workspace_isolation(self, workspace):
        member, user = _client(workspace, "member", email="a@example.com")
        member.put(f"{BASE}/preferences/", {"values": {"density": "compact"}}, format="json")
        other = Workspace.objects.create(name="Other", slug="other", is_active=True)
        WorkspaceMember.objects.create(workspace=other, user=user, role="member", status="active")
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}",
                      HTTP_X_WORKSPACE_SLUG=other.slug)
        # same user, different workspace → no leaked override
        assert c.get(f"{BASE}/preferences/").data["values"] == {}
