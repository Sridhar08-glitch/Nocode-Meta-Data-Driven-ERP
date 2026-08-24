"""Notifications REST API (PROJECT_HANDBOOK.md §22.5 / §22.6)."""
import pytest

from apps.notifications.models import Notification
from apps.tenancy.models import Workspace

from .conftest import make_client

BASE = "/api/v1/notifications"


def _notif(ws, recipient, **kw):
    return Notification.objects.create(
        workspace_id=ws.id, recipient_id=recipient, channel="in_app",
        status="sent", body=kw.pop("body", "hello"), **kw)


@pytest.mark.django_db
class TestRecipientApi:
    def test_list_and_unread_count(self, ws, user, client):
        _notif(ws, user.id)
        _notif(ws, user.id)
        assert client.get(f"{BASE}/").json()["count"] == 2
        assert client.get(f"{BASE}/unread-count/").json()["count"] == 2

    def test_unread_filter(self, ws, user, client):
        n = _notif(ws, user.id)
        _notif(ws, user.id)
        client.post(f"{BASE}/{n.id}/read/")
        assert client.get(f"{BASE}/?unread=1").json()["count"] == 1

    def test_mark_read_and_read_all(self, ws, user, client):
        n = _notif(ws, user.id)
        assert client.post(f"{BASE}/{n.id}/read/").status_code == 200
        _notif(ws, user.id)
        assert client.post(f"{BASE}/read-all/").json()["updated"] == 1
        assert client.get(f"{BASE}/unread-count/").json()["count"] == 0

    def test_cannot_read_other_users_notification(self, ws, user, client):
        import uuid
        other = _notif(ws, uuid.uuid4())
        assert client.post(f"{BASE}/{other.id}/read/").status_code == 404


@pytest.mark.django_db
class TestTemplateApi:
    def test_crud(self, client):
        r = client.post(f"{BASE}/templates/",
                        {"slug": "welcome", "name": "Welcome", "channel": "in_app",
                         "subject_template": "Hi", "body_template": "Hello ${actor_name}"},
                        format="json")
        assert r.status_code == 201, r.content
        tid = r.json()["id"]
        assert client.get(f"{BASE}/templates/").json()["count"] == 1
        assert client.patch(f"{BASE}/templates/{tid}/", {"name": "Welcome!"},
                            format="json").json()["name"] == "Welcome!"
        assert client.delete(f"{BASE}/templates/{tid}/").status_code == 204

    def test_duplicate_slug_channel_rejected(self, client):
        body = {"slug": "x", "name": "X", "channel": "in_app", "body_template": "b"}
        assert client.post(f"{BASE}/templates/", body, format="json").status_code == 201
        assert client.post(f"{BASE}/templates/", body, format="json").status_code == 400

    def test_test_endpoint_creates_notification(self, ws, user, client):
        tid = client.post(f"{BASE}/templates/",
                          {"slug": "welcome", "name": "W", "channel": "in_app",
                           "body_template": "Hi ${actor_name}"}, format="json").json()["id"]
        r = client.post(f"{BASE}/templates/{tid}/test/",
                        {"context": {"actor_name": "Me"}}, format="json")
        assert r.status_code == 201
        assert r.json()["sent"] == 1
        assert Notification.objects.filter(workspace_id=ws.id, recipient_id=user.id).count() == 1


@pytest.mark.django_db
class TestApiAuthz:
    def test_viewer_cannot_create_template(self, ws):
        _, c = make_client(ws, "viewer@acme.com", role="viewer")
        r = c.post(f"{BASE}/templates/",
                   {"slug": "t", "name": "T", "channel": "in_app", "body_template": "b"},
                   format="json")
        assert r.status_code == 403

    def test_workspace_isolation_on_templates(self, ws, client):
        tid = client.post(f"{BASE}/templates/",
                          {"slug": "t", "name": "T", "channel": "in_app",
                           "body_template": "b"}, format="json").json()["id"]
        other = Workspace.objects.create(name="Other", slug="other", is_active=True)
        _, c2 = make_client(other, "x@other.com", role="admin")
        assert c2.get(f"{BASE}/templates/{tid}/").status_code == 404
