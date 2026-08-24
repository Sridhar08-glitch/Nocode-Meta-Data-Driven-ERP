"""
Realtime channels (Phase 1.30) — auth/workspace scoping, event delivery, entity
filtering, cross-workspace isolation, presence, and the broadcast producer.

Consumers resolve workspace membership from the DB in a worker thread
(database_sync_to_async), so those tests run with ``transaction=True`` for visibility.
"""
import uuid

import pytest
from asgiref.sync import async_to_sync
from asgiref.testing import ApplicationCommunicator
from channels.layers import get_channel_layer

from apps.accounts.models import User
from apps.realtime import broadcast
from apps.realtime.consumers import (
    PresenceConsumer,
    RecordStreamConsumer,
    WorkflowStreamConsumer,
)
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"


def _scope(path, *, user_id, workspace_slug=None, url_kwargs=None):
    qs = f"workspace={workspace_slug}".encode() if workspace_slug else b""
    scope = {"type": "websocket", "path": path, "query_string": qs,
             "headers": [], "subprotocols": [], "user_id": user_id}
    if url_kwargs is not None:
        scope["url_route"] = {"kwargs": url_kwargs}
    return scope


async def _connect(app, scope):
    comm = ApplicationCommunicator(app, scope)
    await comm.send_input({"type": "websocket.connect"})
    return comm


def _make_member(slug="acme", email="u@example.com", role="member"):
    ws = Workspace.objects.create(name=slug.title(), slug=slug, is_active=True)
    user = User.objects.create_user(email=email, password=PW, is_verified=True)
    WorkspaceMember.objects.create(workspace=ws, user=user, role=role, status="active")
    return ws, user


# ── connect / auth gating ─────────────────────────────────────────────────────
@pytest.mark.django_db(transaction=True)
def test_member_connect_accepts():
    ws, user = _make_member()

    async def scenario():
        comm = await _connect(RecordStreamConsumer.as_asgi(),
                              _scope("/ws/records/", user_id=str(user.id),
                                     workspace_slug="acme", url_kwargs={}))
        ev = await comm.receive_output(timeout=2)
        await comm.send_input({"type": "websocket.disconnect", "code": 1000})
        return ev

    assert async_to_sync(scenario)()["type"] == "websocket.accept"


@pytest.mark.django_db(transaction=True)
def test_unauthenticated_closes_4401():
    async def scenario():
        comm = await _connect(RecordStreamConsumer.as_asgi(),
                              _scope("/ws/records/", user_id=None,
                                     workspace_slug="acme", url_kwargs={}))
        return await comm.receive_output(timeout=2)

    ev = async_to_sync(scenario)()
    assert ev["type"] == "websocket.close" and ev.get("code") == 4401


@pytest.mark.django_db(transaction=True)
def test_non_member_closes_4403():
    ws, _ = _make_member(slug="acme", email="owner@example.com")
    outsider = User.objects.create_user(email="out@example.com", password=PW, is_verified=True)

    async def scenario():
        comm = await _connect(RecordStreamConsumer.as_asgi(),
                              _scope("/ws/records/", user_id=str(outsider.id),
                                     workspace_slug="acme", url_kwargs={}))
        return await comm.receive_output(timeout=2)

    ev = async_to_sync(scenario)()
    assert ev["type"] == "websocket.close" and ev.get("code") == 4403


@pytest.mark.django_db(transaction=True)
def test_unknown_workspace_closes_4403():
    _, user = _make_member()

    async def scenario():
        comm = await _connect(RecordStreamConsumer.as_asgi(),
                              _scope("/ws/records/", user_id=str(user.id),
                                     workspace_slug="ghost", url_kwargs={}))
        return await comm.receive_output(timeout=2)

    ev = async_to_sync(scenario)()
    assert ev["type"] == "websocket.close" and ev.get("code") == 4403


# ── event delivery ────────────────────────────────────────────────────────────
@pytest.mark.django_db(transaction=True)
def test_record_event_delivered_to_workspace_group():
    ws, user = _make_member()

    async def scenario():
        comm = await _connect(RecordStreamConsumer.as_asgi(),
                              _scope("/ws/records/", user_id=str(user.id),
                                     workspace_slug="acme", url_kwargs={}))
        assert (await comm.receive_output(timeout=2))["type"] == "websocket.accept"
        layer = get_channel_layer()
        await layer.group_send(broadcast.group_records(ws.id), {
            "type": "record.event",
            "event": {"event_type": "record.created", "entity_slug": "lead",
                      "record_id": "r1", "data": {}, "actor_id": None}})
        out = await comm.receive_output(timeout=2)
        await comm.send_input({"type": "websocket.disconnect", "code": 1000})
        return out

    out = async_to_sync(scenario)()
    import json
    payload = json.loads(out["text"])
    assert payload["event_type"] == "record.created" and payload["entity_slug"] == "lead"


@pytest.mark.django_db(transaction=True)
def test_entity_scoped_consumer_filters_other_entities():
    ws, user = _make_member()

    async def scenario():
        comm = await _connect(RecordStreamConsumer.as_asgi(),
                              _scope("/ws/records/lead/", user_id=str(user.id),
                                     workspace_slug="acme", url_kwargs={"entity_slug": "lead"}))
        assert (await comm.receive_output(timeout=2))["type"] == "websocket.accept"
        layer = get_channel_layer()
        # event for a different entity → filtered out
        await layer.group_send(broadcast.group_records(ws.id), {
            "type": "record.event",
            "event": {"event_type": "record.created", "entity_slug": "deal",
                      "record_id": "d1", "data": {}, "actor_id": None}})
        nothing = await comm.receive_nothing(timeout=0.3)
        # event for the subscribed entity → delivered
        await layer.group_send(broadcast.group_records(ws.id), {
            "type": "record.event",
            "event": {"event_type": "record.created", "entity_slug": "lead",
                      "record_id": "l1", "data": {}, "actor_id": None}})
        out = await comm.receive_output(timeout=2)
        await comm.send_input({"type": "websocket.disconnect", "code": 1000})
        return nothing, out

    nothing, out = async_to_sync(scenario)()
    import json
    assert nothing is True
    assert json.loads(out["text"])["entity_slug"] == "lead"


@pytest.mark.django_db(transaction=True)
def test_cross_workspace_isolation():
    ws_a, user_a = _make_member(slug="acme", email="a@example.com")
    ws_b, _ = _make_member(slug="other", email="b@example.com")

    async def scenario():
        comm = await _connect(RecordStreamConsumer.as_asgi(),
                              _scope("/ws/records/", user_id=str(user_a.id),
                                     workspace_slug="acme", url_kwargs={}))
        assert (await comm.receive_output(timeout=2))["type"] == "websocket.accept"
        layer = get_channel_layer()
        # event broadcast to workspace B must NOT reach the A subscriber
        await layer.group_send(broadcast.group_records(ws_b.id), {
            "type": "record.event",
            "event": {"event_type": "record.created", "entity_slug": "lead",
                      "record_id": "x", "data": {}, "actor_id": None}})
        nothing = await comm.receive_nothing(timeout=0.3)
        await comm.send_input({"type": "websocket.disconnect", "code": 1000})
        return nothing

    assert async_to_sync(scenario)() is True


@pytest.mark.django_db(transaction=True)
def test_workflow_event_delivered():
    ws, user = _make_member()

    async def scenario():
        comm = await _connect(WorkflowStreamConsumer.as_asgi(),
                              _scope("/ws/workflows/", user_id=str(user.id),
                                     workspace_slug="acme", url_kwargs={}))
        assert (await comm.receive_output(timeout=2))["type"] == "websocket.accept"
        layer = get_channel_layer()
        await layer.group_send(broadcast.group_workflows(ws.id), {
            "type": "workflow.event",
            "event": {"event_type": "workflow.run.completed", "run_id": "run1",
                      "status": "completed"}})
        out = await comm.receive_output(timeout=2)
        await comm.send_input({"type": "websocket.disconnect", "code": 1000})
        return out

    import json
    assert json.loads(async_to_sync(scenario)()["text"])["event_type"] == "workflow.run.completed"


@pytest.mark.django_db(transaction=True)
def test_presence_join_and_heartbeat():
    ws, user = _make_member()

    async def scenario():
        comm = await _connect(PresenceConsumer.as_asgi(),
                              _scope("/ws/presence/", user_id=str(user.id),
                                     workspace_slug="acme", url_kwargs={}))
        assert (await comm.receive_output(timeout=2))["type"] == "websocket.accept"
        join = await comm.receive_output(timeout=2)             # own join announcement
        await comm.send_input({"type": "websocket.receive", "text": "ping"})
        beat = await comm.receive_output(timeout=2)             # heartbeat re-broadcast
        await comm.send_input({"type": "websocket.disconnect", "code": 1000})
        return join, beat

    import json
    join, beat = async_to_sync(scenario)()
    assert json.loads(join["text"])["action"] == "join"
    assert json.loads(beat["text"])["action"] == "heartbeat"


# ── broadcast producer (sync, no running loop) ────────────────────────────────
def test_broadcast_record_producer():
    layer = get_channel_layer()
    ws_id = uuid.uuid4()
    channel = async_to_sync(layer.new_channel)()
    async_to_sync(layer.group_add)(broadcast.group_records(ws_id), channel)
    broadcast.broadcast_record(
        workspace_id=ws_id, entity_slug="lead", event_type="record.created",
        record_id="r1", data={"name": "X"}, on_commit=False)
    msg = async_to_sync(layer.receive)(channel)
    assert msg["type"] == "record.event"
    assert msg["event"]["entity_slug"] == "lead"
    assert msg["event"]["event_type"] == "record.created"


def test_broadcast_workflow_producer():
    layer = get_channel_layer()
    ws_id = uuid.uuid4()
    channel = async_to_sync(layer.new_channel)()
    async_to_sync(layer.group_add)(broadcast.group_workflows(ws_id), channel)
    broadcast.broadcast_workflow(
        workspace_id=ws_id, event_type="workflow.run.started", run_id="run1",
        status="running", on_commit=False)
    msg = async_to_sync(layer.receive)(channel)
    assert msg["event"]["event_type"] == "workflow.run.started"
