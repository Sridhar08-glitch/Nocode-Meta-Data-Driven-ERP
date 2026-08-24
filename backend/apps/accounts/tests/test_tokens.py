import uuid

import pytest
from rest_framework.exceptions import AuthenticationFailed

from apps.accounts import tokens
from apps.accounts.models import RefreshTokenFamily, User


@pytest.fixture
def user(db):
    return User.objects.create_user(email="tok@example.com", password="Sup3rStr0ng!pw", is_verified=True)


@pytest.mark.django_db
class TestAccessToken:
    def test_issue_and_decode(self, user):
        raw = tokens.issue_access_token(user)
        payload = tokens.decode_token(raw, expected_type="access")
        assert payload["user_id"] == str(user.id)
        assert payload["email"] == user.email
        assert payload["token_type"] == "access"
        assert "workspace_id" not in payload

    def test_workspace_claim(self, user):
        ws = uuid.uuid4()
        payload = tokens.decode_token(tokens.issue_access_token(user, ws), expected_type="access")
        assert payload["workspace_id"] == str(ws)

    def test_wrong_type_rejected(self, user):
        raw = tokens.issue_access_token(user)
        with pytest.raises(AuthenticationFailed):
            tokens.decode_token(raw, expected_type="refresh")


@pytest.mark.django_db
class TestRefreshRotation:
    def test_issue_creates_family(self, user):
        raw, family = tokens.issue_refresh_token(user, user_agent="UA", ip="1.2.3.4")
        assert family.is_active
        assert RefreshTokenFamily.objects.filter(family_id=family.family_id).exists()
        payload = tokens.decode_token(raw, expected_type="refresh")
        assert payload["family_id"] == str(family.family_id)

    def test_rotation_advances_jti(self, user):
        raw, family = tokens.issue_refresh_token(user)
        old_jti = family.current_jti
        access, new_refresh = tokens.rotate_refresh_token(raw)
        family.refresh_from_db()
        assert family.current_jti != old_jti
        assert tokens.decode_token(access, expected_type="access")["user_id"] == str(user.id)
        # The new refresh token works for a subsequent rotation
        tokens.rotate_refresh_token(new_refresh)

    def test_reuse_detection_revokes_family(self, user):
        raw, family = tokens.issue_refresh_token(user)
        tokens.rotate_refresh_token(raw)  # raw is now stale
        with pytest.raises(AuthenticationFailed, match="reuse"):
            tokens.rotate_refresh_token(raw)  # reusing the stale token
        family.refresh_from_db()
        assert not family.is_active
        assert family.revoked_reason == "reuse_detected"

    def test_rotation_after_revoke_fails(self, user):
        raw, family = tokens.issue_refresh_token(user)
        tokens.revoke_family(family.family_id)
        with pytest.raises(AuthenticationFailed):
            tokens.rotate_refresh_token(raw)

    def test_revoke_all_for_user(self, user):
        tokens.issue_refresh_token(user)
        tokens.issue_refresh_token(user)
        n = tokens.revoke_all_for_user(user)
        assert n == 2
        assert RefreshTokenFamily.objects.filter(user=user, is_active=True).count() == 0


@pytest.mark.django_db
class TestMfaChallenge:
    def test_mfa_token_type(self, user):
        raw = tokens.issue_mfa_challenge_token(user)
        payload = tokens.decode_token(raw, expected_type="mfa_challenge")
        assert payload["user_id"] == str(user.id)
