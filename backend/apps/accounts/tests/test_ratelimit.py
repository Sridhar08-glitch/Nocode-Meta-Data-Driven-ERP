import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework.test import APIClient

from apps.accounts.models import User

STRONG_PW = "Sup3rStr0ng!pw"


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture(autouse=True)
def _ratelimit_on(settings):
    settings.RATELIMIT_ENABLE = True
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
class TestRateLimiting:
    def test_login_throttled_after_5_per_minute(self, api, db):
        User.objects.create_user(email="rl@example.com", password=STRONG_PW, is_verified=True)
        body = {"email": "rl@example.com", "password": "wrongpass!"}
        codes = [api.post(reverse("accounts:login"), body, format="json").status_code for _ in range(6)]
        # First 5 are processed (401 invalid creds), the 6th is rate-limited.
        assert codes[:5] == [401, 401, 401, 401, 401]
        assert codes[5] == 429

    def test_password_reset_throttled_after_3_per_hour(self, api, db):
        body = {"email": "reset@example.com"}
        codes = [api.post(reverse("accounts:password-reset-request"), body, format="json").status_code
                 for _ in range(4)]
        assert codes[:3] == [200, 200, 200]
        assert codes[3] == 429

    def test_limit_is_per_email_for_reset(self, api, db):
        # A different email is tracked in a separate bucket.
        for _ in range(3):
            api.post(reverse("accounts:password-reset-request"), {"email": "a@example.com"}, format="json")
        r = api.post(reverse("accounts:password-reset-request"), {"email": "b@example.com"}, format="json")
        assert r.status_code == 200
