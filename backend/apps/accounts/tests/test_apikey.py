from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts import services
from apps.accounts.models import ApiKey, User

STRONG_PW = "Sup3rStr0ng!pw"


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user(email="key@example.com", password=STRONG_PW, is_verified=True)


@pytest.mark.django_db
class TestApiKeyAuth:
    def test_valid_key_authenticates(self, api, user):
        raw, _ = services.create_api_key(user, "ci")
        api.credentials(HTTP_X_API_KEY=raw)
        # logout requires authentication; a 200 proves the key authenticated.
        r = api.post(reverse("accounts:logout"), {}, format="json")
        assert r.status_code == 200

    def test_last_used_updated(self, api, user):
        raw, key = services.create_api_key(user, "ci")
        assert key.last_used_at is None
        api.credentials(HTTP_X_API_KEY=raw)
        api.post(reverse("accounts:logout"), {}, format="json")
        key.refresh_from_db()
        assert key.last_used_at is not None

    def test_bad_secret_rejected(self, api, user):
        raw, _ = services.create_api_key(user, "ci")
        api.credentials(HTTP_X_API_KEY=raw + "tampered")
        r = api.post(reverse("accounts:logout"), {}, format="json")
        assert r.status_code in (401, 403)

    def test_malformed_key_rejected(self, api, user):
        api.credentials(HTTP_X_API_KEY="nokey-no-dot")
        r = api.post(reverse("accounts:logout"), {}, format="json")
        assert r.status_code in (401, 403)

    def test_inactive_key_rejected(self, api, user):
        raw, key = services.create_api_key(user, "ci")
        key.is_active = False
        key.save(update_fields=["is_active"])
        api.credentials(HTTP_X_API_KEY=raw)
        r = api.post(reverse("accounts:logout"), {}, format="json")
        assert r.status_code in (401, 403)

    def test_expired_key_rejected(self, api, user):
        raw, key = services.create_api_key(user, "ci", expires_at=timezone.now() - timedelta(hours=1))
        api.credentials(HTTP_X_API_KEY=raw)
        r = api.post(reverse("accounts:logout"), {}, format="json")
        assert r.status_code in (401, 403)

    def test_rotation_grace_fields_present(self, user):
        # Rotation grace window fields exist and default to null (§5.3).
        _, key = services.create_api_key(user, "ci")
        assert key.rotated_at is None
        assert key.grace_period_ends_at is None

    def test_only_hash_persisted(self, user):
        raw, key = services.create_api_key(user, "ci")
        secret = raw.split(".", 1)[1]
        assert key.key_hash != raw
        assert secret not in key.key_hash
        assert ApiKey.objects.filter(key_hash=key.key_hash).exists()
