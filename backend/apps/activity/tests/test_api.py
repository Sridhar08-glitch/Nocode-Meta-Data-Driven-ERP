"""Activity + comments REST API (PROJECT_HANDBOOK.md §23.3 / §23.4)."""
import uuid

import pytest

from apps.activity.models import ActivityEntry, Comment
from apps.schema_registry.services import SchemaRegistryService
from apps.tenancy.models import Workspace

from .conftest import make_client

DATA = "/api/v1/data/lead"


@pytest.mark.django_db
class TestCommentsApi:
    def test_create_list_get(self, ws, lead, user, client):
        rid = uuid.uuid4()
        r = client.post(f"{DATA}/{rid}/comments/", {"body": "Hello"}, format="json")
        assert r.status_code == 201, r.content
        cid = r.json()["id"]
        assert client.get(f"{DATA}/{rid}/comments/").json()["count"] == 1
        assert client.get(f"{DATA}/{rid}/comments/{cid}/").json()["body"] == "Hello"

    def test_edit_requires_author(self, ws, lead, user, client):
        rid = uuid.uuid4()
        cid = client.post(f"{DATA}/{rid}/comments/", {"body": "x"}, format="json").json()["id"]
        assert client.patch(f"{DATA}/{rid}/comments/{cid}/", {"body": "y"},
                            format="json").json()["body"] == "y"
        # another member cannot edit
        _, other = make_client(ws, "other@acme.com", role="member")
        assert other.patch(f"{DATA}/{rid}/comments/{cid}/", {"body": "z"},
                           format="json").status_code == 403

    def test_delete_author_or_admin(self, ws, lead, client):
        rid = uuid.uuid4()
        _, author = make_client(ws, "author@acme.com", role="member")
        cid = author.post(f"{DATA}/{rid}/comments/", {"body": "x"}, format="json").json()["id"]
        # admin (client) can delete someone else's comment
        assert client.delete(f"{DATA}/{rid}/comments/{cid}/").status_code == 204
        assert Comment.objects.get(id=cid).is_deleted

    def test_pin_unpin_admin_only(self, ws, lead, client):
        rid = uuid.uuid4()
        cid = client.post(f"{DATA}/{rid}/comments/", {"body": "x"}, format="json").json()["id"]
        assert client.post(f"{DATA}/{rid}/comments/{cid}/pin/").json()["is_pinned"] is True
        assert client.post(f"{DATA}/{rid}/comments/{cid}/unpin/").json()["is_pinned"] is False
        _, viewer = make_client(ws, "v@acme.com", role="viewer")
        assert viewer.post(f"{DATA}/{rid}/comments/{cid}/pin/").status_code == 403


@pytest.mark.django_db
class TestActivityApi:
    def _entry(self, ws, lead, **kw):
        from django.utils import timezone
        return ActivityEntry.objects.create(
            workspace_id=ws.id, entity_id=lead.id,
            record_id=kw.pop("record_id", uuid.uuid4()),
            activity_type=kw.pop("activity_type", "record_created"),
            summary="x", occurred_at=timezone.now(), **kw)

    def test_record_activity(self, ws, lead, client):
        rid = uuid.uuid4()
        self._entry(ws, lead, record_id=rid)
        self._entry(ws, lead, record_id=rid, activity_type="record_updated")
        assert client.get(f"{DATA}/{rid}/activity/").json()["count"] == 2

    def test_feed_filters_and_workspace_isolation(self, ws, lead, client):
        self._entry(ws, lead)
        self._entry(ws, lead, activity_type="comment_added")
        # entry in another workspace must not appear
        other = Workspace.objects.create(name="Other", slug="other", is_active=True)
        oent = SchemaRegistryService.create_entity(
            workspace_id=other.id, slug="lead", name="L", plural_name="Ls")
        ActivityEntry.objects.create(
            workspace_id=other.id, entity_id=oent.id, record_id=uuid.uuid4(),
            activity_type="record_created", summary="x",
            occurred_at=__import__("django.utils.timezone", fromlist=["now"]).now())
        body = client.get("/api/v1/activity/feed/").json()
        assert body["count"] == 2
        filtered = client.get("/api/v1/activity/feed/?activity_type=comment_added").json()
        assert filtered["count"] == 1

    def test_feed_requires_workspace(self, ws, lead):
        from rest_framework.test import APIClient
        assert APIClient().get("/api/v1/activity/feed/").status_code in (401, 403)
