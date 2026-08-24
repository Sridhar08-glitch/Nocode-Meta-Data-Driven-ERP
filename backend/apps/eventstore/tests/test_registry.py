"""Tests for command handler registry and event subscriber registry."""
import uuid

import pytest

from apps.eventstore.commands import SYSTEM_ACTOR, Command
from apps.eventstore.exceptions import CommandHandlerNotFoundError
from apps.eventstore.registry import (
    clear_registry,
    command_handler,
    event_subscriber,
    get_all_registered_commands,
    get_handler,
    get_subscribers,
)


class CmdA(Command):
    pass


class CmdB(Command):
    pass


@pytest.fixture(autouse=True)
def isolated_registry():
    """Each test starts with a clean registry."""
    clear_registry()
    yield
    clear_registry()


def _make_cmd(cls=CmdA):
    return cls(workspace_id=uuid.uuid4(), issued_by=SYSTEM_ACTOR)


# ── command_handler ──────────────────────────────────────────────────────────

def test_register_and_retrieve_handler():
    @command_handler(CmdA)
    def handle_a(cmd):
        return []

    retrieved = get_handler(_make_cmd(CmdA))
    assert retrieved is handle_a


def test_handler_not_found_raises():
    with pytest.raises(CommandHandlerNotFoundError):
        get_handler(_make_cmd(CmdA))


def test_duplicate_handler_raises():
    @command_handler(CmdA)
    def handle_a1(cmd):
        return []

    with pytest.raises(RuntimeError, match="Duplicate handler"):
        @command_handler(CmdA)
        def handle_a2(cmd):
            return []


def test_multiple_handlers_different_commands():
    @command_handler(CmdA)
    def handle_a(cmd):
        return []

    @command_handler(CmdB)
    def handle_b(cmd):
        return []

    assert get_handler(_make_cmd(CmdA)) is handle_a
    assert get_handler(_make_cmd(CmdB)) is handle_b


def test_get_all_registered_commands():
    @command_handler(CmdA)
    def handle_a(cmd):
        return []

    @command_handler(CmdB)
    def handle_b(cmd):
        return []

    all_cmds = get_all_registered_commands()
    assert CmdA in all_cmds
    assert CmdB in all_cmds


# ── event_subscriber ─────────────────────────────────────────────────────────

def test_subscriber_registration_and_retrieval():
    @event_subscriber("record.created")
    def on_record_created(event):
        pass

    subs = get_subscribers("record.created")
    assert on_record_created in subs


def test_no_subscribers_returns_empty_list():
    assert get_subscribers("nonexistent.event") == []


def test_subscriber_multiple_event_types():
    @event_subscriber("record.created", "record.updated")
    def on_record_change(event):
        pass

    assert on_record_change in get_subscribers("record.created")
    assert on_record_change in get_subscribers("record.updated")


def test_multiple_subscribers_same_event():
    calls = []

    @event_subscriber("record.created")
    def sub1(event):
        calls.append("sub1")

    @event_subscriber("record.created")
    def sub2(event):
        calls.append("sub2")

    subs = get_subscribers("record.created")
    assert len(subs) == 2
