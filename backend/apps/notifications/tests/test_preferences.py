"""Notification preferences endpoint (Phase F2.7 backfill)."""
import pytest

from apps.notifications.models import NotificationPreference

URL = "/api/v1/notifications/preferences/"


@pytest.mark.django_db
class TestNotificationPreferences:
    def test_empty_then_upsert_then_list(self, client, user, ws):
        # starts empty
        r = client.get(URL)
        assert r.status_code == 200
        assert r.json() == {"results": [], "count": 0}

        # upsert a preference
        r = client.put(URL, {"event_type": "record_assigned", "channel": "email", "enabled": False}, format="json")
        assert r.status_code == 200
        assert r.json()["enabled"] is False
        # scoped to the caller (member_id == user.id, matching the send-time lookup)
        pref = NotificationPreference.objects.get(workspace_id=ws.id, member_id=user.id)
        assert pref.event_type == "record_assigned" and pref.channel == "email" and pref.enabled is False

        # now lists it
        r = client.get(URL)
        body = r.json()
        assert body["count"] == 1
        assert body["results"][0]["event_type"] == "record_assigned"

    def test_upsert_is_idempotent_on_event_and_channel(self, client, user, ws):
        client.put(URL, {"event_type": "comment_mention", "channel": "in_app", "enabled": True}, format="json")
        client.put(URL, {"event_type": "comment_mention", "channel": "in_app", "enabled": False}, format="json")
        rows = NotificationPreference.objects.filter(workspace_id=ws.id, member_id=user.id, event_type="comment_mention", channel="in_app")
        assert rows.count() == 1
        assert rows.first().enabled is False

    def test_requires_event_type_and_channel(self, client):
        assert client.put(URL, {"channel": "email"}, format="json").status_code == 400
        assert client.put(URL, {"event_type": "x"}, format="json").status_code == 400

    def test_requires_workspace_header(self, user):
        from rest_framework.test import APIClient

        from apps.accounts import tokens
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}")
        assert c.get(URL).status_code == 403

    def test_preferences_are_per_member(self, client, ws):
        from apps.notifications.tests.conftest import make_client
        client.put(URL, {"event_type": "record_assigned", "channel": "email", "enabled": False}, format="json")
        _, other = make_client(ws, "other@acme.com")
        # the other member sees none of the first member's prefs
        assert other.get(URL).json()["count"] == 0
