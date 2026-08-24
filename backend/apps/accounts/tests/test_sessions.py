"""Session management tests (Phase 1.27) — /api/v1/auth/sessions/."""
import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import RefreshTokenFamily, User

PW = "Sup3rStr0ng!pw"
BASE = "/api/v1/auth"


@pytest.fixture
def user(db):
    return User.objects.create_user(email="u@example.com", password=PW, is_verified=True)


def _login(email=None):
    """Authenticated APIClient + the access token's user (creates a refresh family per login)."""
    c = APIClient()
    return c


@pytest.mark.django_db
class TestSessions:
    def _auth_client(self, user):
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}")
        return c

    def test_list_active_sessions(self, user):
        # Two logins → two families.
        tokens.issue_token_pair(user, user_agent="Firefox", ip="1.1.1.1")
        tokens.issue_token_pair(user, user_agent="Chrome", ip="2.2.2.2")
        r = self._auth_client(user).get(f"{BASE}/sessions/")
        assert r.status_code == 200
        assert len(r.data) == 2
        agents = {s["user_agent"] for s in r.data}
        assert {"Firefox", "Chrome"} == agents
        assert all("id" in s and "expires_at" in s and "last_seen" in s for s in r.data)

    def test_list_requires_auth(self, user):
        r = APIClient().get(f"{BASE}/sessions/")
        assert r.status_code in (401, 403)

    def test_revoke_single_session(self, user):
        _, _, fam = tokens.issue_token_pair(user, user_agent="A")
        r = self._auth_client(user).delete(f"{BASE}/sessions/{fam.family_id}/")
        assert r.status_code == 204
        fam.refresh_from_db()
        assert fam.is_active is False

    def test_revoke_unknown_session_404(self, user):
        import uuid
        r = self._auth_client(user).delete(f"{BASE}/sessions/{uuid.uuid4()}/")
        assert r.status_code == 404

    def test_cannot_revoke_other_users_session(self, user):
        other = User.objects.create_user(email="other@example.com", password=PW, is_verified=True)
        _, _, fam = tokens.issue_token_pair(other, user_agent="X")
        r = self._auth_client(user).delete(f"{BASE}/sessions/{fam.family_id}/")
        assert r.status_code == 404
        fam.refresh_from_db()
        assert fam.is_active is True

    def test_revoke_all_keeps_current(self, user):
        _, _, fam1 = tokens.issue_token_pair(user, user_agent="A")
        _, refresh2, fam2 = tokens.issue_token_pair(user, user_agent="B")
        r = self._auth_client(user).post(f"{BASE}/sessions/revoke-all/",
                                         {"refresh": refresh2}, format="json")
        assert r.status_code == 200
        assert r.data["revoked"] == 1
        fam1.refresh_from_db()
        fam2.refresh_from_db()
        assert fam1.is_active is False
        assert fam2.is_active is True  # current session preserved

    def test_revoke_all_without_refresh_revokes_everything(self, user):
        tokens.issue_token_pair(user, user_agent="A")
        tokens.issue_token_pair(user, user_agent="B")
        r = self._auth_client(user).post(f"{BASE}/sessions/revoke-all/", {}, format="json")
        assert r.status_code == 200
        assert r.data["revoked"] == 2
        assert RefreshTokenFamily.objects.filter(user=user, is_active=True).count() == 0

    def test_reuse_detection_still_invalidates_family(self, user):
        # Sanity: rotation + reuse detection unaffected by session endpoints.
        _, refresh, fam = tokens.issue_token_pair(user, user_agent="A")
        tokens.rotate_refresh_token(refresh)  # advances current_jti
        from rest_framework.exceptions import AuthenticationFailed
        with pytest.raises(AuthenticationFailed):
            tokens.rotate_refresh_token(refresh)  # stale → reuse detected
        fam.refresh_from_db()
        assert fam.is_active is False
        assert fam.revoked_reason == "reuse_detected"
