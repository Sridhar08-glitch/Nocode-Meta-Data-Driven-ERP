"""BrandingService + API (PROJECT_HANDBOOK.md §32.1 / §32.4)."""
import pytest

from apps.branding import services as svc
from apps.branding.services import BrandingError, BrandingService, sanitize_css

BASE = "/api/v1/branding"


class TestSanitize:
    def test_strips_dangerous_css(self):
        out = sanitize_css('a{background:url(http://x/y.png)} @import "evil.css"; '
                           'b{width:expression(alert(1))}')
        assert "url(" not in out
        assert "@import" not in out
        assert "expression(" not in out


@pytest.mark.django_db
class TestBrandingService:
    def test_update_sanitizes_css(self, ws):
        obj = BrandingService.update_branding(
            ws.id, {"custom_css": '@import "x"; a{background:url(y)}'})
        assert "@import" not in obj.custom_css and "url(" not in obj.custom_css

    def test_invalid_color_rejected(self, ws):
        with pytest.raises(BrandingError):
            BrandingService.update_branding(ws.id, {"color_primary": "notacolor"})

    def test_valid_color_accepted(self, ws):
        obj = BrandingService.update_branding(ws.id, {"color_primary": "#abc123"})
        assert obj.color_primary == "#abc123"

    def test_personalization_fields_saved(self, ws):
        """Typography + density + radius + login branding persist via the same single service."""
        obj = BrandingService.update_branding(ws.id, {
            "font_family_heading": "Poppins", "font_family_body": "Roboto",
            "ui_density": "compact", "border_radius": "lg",
            "login_headline": "Welcome", "favicon_url": "https://cdn/f.ico"})
        assert obj.font_family_heading == "Poppins" and obj.font_family_body == "Roboto"
        assert obj.ui_density == "compact" and obj.border_radius == "lg"
        assert obj.login_headline == "Welcome" and obj.favicon_url == "https://cdn/f.ico"

    def test_smtp_password_by_reference(self, ws):
        cfg = BrandingService.save_smtp_config(
            ws.id, {"host": "smtp.x", "port": 587, "username": "u",
                    "password_ref": "SMTP_PW", "from_email": "a@x.com"})
        assert cfg.password_ref == "SMTP_PW"
        # no raw password attribute exists on the model
        assert not hasattr(cfg, "password")

    def test_smtp_test_success_and_failure(self, ws, monkeypatch):
        BrandingService.save_smtp_config(
            ws.id, {"host": "smtp.x", "port": 587, "username": "u",
                    "password_ref": "SMTP_PW", "from_email": "a@x.com"})
        monkeypatch.setattr(svc, "_smtp_test", lambda c: {"success": True})
        assert BrandingService.test_smtp(ws.id)["success"] is True
        monkeypatch.setattr(svc, "_smtp_test", lambda c: {"success": False, "error": "auth"})
        res = BrandingService.test_smtp(ws.id)
        assert res["success"] is False and res["error"] == "auth"


@pytest.mark.django_db
class TestBrandingApi:
    def test_get_patch(self, client):
        assert client.get(f"{BASE}/").status_code == 200
        r = client.patch(f"{BASE}/", {"app_name": "MyERP", "color_primary": "#112233"},
                         format="json")
        assert r.status_code == 200 and r.json()["app_name"] == "MyERP"

    def test_invalid_color_400(self, client):
        assert client.patch(f"{BASE}/", {"color_primary": "xxx"}, format="json").status_code == 400

    def test_smtp_password_never_returned(self, client):
        client.patch(f"{BASE}/smtp/", {"host": "smtp.x", "port": 587, "username": "u",
                                       "password_ref": "SMTP_PW", "from_email": "a@x.com"},
                     format="json")
        body = client.get(f"{BASE}/smtp/").json()
        assert "password" not in body   # only the reference name is ever exposed

    def test_smtp_test_endpoint(self, client, monkeypatch):
        monkeypatch.setattr(svc, "_smtp_test", lambda c: {"success": True})
        client.patch(f"{BASE}/smtp/", {"host": "smtp.x", "port": 587, "username": "u",
                                       "password_ref": "SMTP_PW", "from_email": "a@x.com"},
                     format="json")
        assert client.post(f"{BASE}/smtp/test/").json()["success"] is True
