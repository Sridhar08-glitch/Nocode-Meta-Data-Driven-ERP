"""WebSocket consumer connect/auth (PROJECT_HANDBOOK.md §22.4)."""
from asgiref.sync import async_to_sync
from asgiref.testing import ApplicationCommunicator

from apps.notifications.consumers import NotificationConsumer


def _scope(user_id=None):
    return {"type": "websocket", "path": "/ws/notifications/", "query_string": b"",
            "headers": [], "subprotocols": [], "user_id": user_id}


def _run(fn):
    return async_to_sync(fn)()


def test_authed_connect_accepts():
    async def scenario():
        comm = ApplicationCommunicator(
            NotificationConsumer.as_asgi(),
            _scope(user_id="11111111-1111-1111-1111-111111111111"))
        await comm.send_input({"type": "websocket.connect"})
        ev = await comm.receive_output(timeout=2)
        await comm.send_input({"type": "websocket.disconnect", "code": 1000})
        await comm.wait(timeout=2)
        return ev

    assert _run(scenario)["type"] == "websocket.accept"


def test_unauthed_connect_closes():
    async def scenario():
        comm = ApplicationCommunicator(NotificationConsumer.as_asgi(), _scope(user_id=None))
        await comm.send_input({"type": "websocket.connect"})
        return await comm.receive_output(timeout=2)

    ev = _run(scenario)
    assert ev["type"] == "websocket.close"
    assert ev.get("code") == 4401
