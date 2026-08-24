"""
Tests for CommandBus.

Uses Django TestCase with SQLite (config.settings.local) so we get real
DB transactions.  RLS set_config is no-op on SQLite — we test the ORM layer.
"""
import uuid
from unittest.mock import patch

import pytest
from django.test import TestCase

from apps.eventstore.bus import CommandBus
from apps.eventstore.commands import SYSTEM_ACTOR, Command
from apps.eventstore.events import DomainEventData
from apps.eventstore.exceptions import (
    CommandHandlerNotFoundError,
    ConcurrencyError,
)
from apps.eventstore.registry import clear_registry, command_handler

# ── Fixture commands ─────────────────────────────────────────────────────────

class CreateThingCommand(Command):
    aggregate_type: str = "Thing"


class UpdateThingCommand(Command):
    aggregate_type: str = "Thing"


def _ws():
    return uuid.uuid4()


def _actor():
    return uuid.uuid4()


def _make_event(ws, agg_id, event_type="thing.created", version=1):
    return DomainEventData(
        event_type=event_type,
        workspace_id=ws,
        aggregate_type="Thing",
        aggregate_id=agg_id,
        payload={"name": "test"},
        actor_id=_actor(),
        version=version,
    )


@pytest.fixture(autouse=True)
def clean_registry():
    clear_registry()
    yield
    clear_registry()


# ── Tests ────────────────────────────────────────────────────────────────────

@pytest.mark.django_db(transaction=True)
class TestCommandBus(TestCase):

    def setUp(self):
        self.bus = CommandBus()
        self.ws = _ws()
        self.agg_id = uuid.uuid4()

    def test_dispatch_no_handler_raises(self):
        cmd = CreateThingCommand(workspace_id=self.ws, issued_by=SYSTEM_ACTOR)
        with pytest.raises(CommandHandlerNotFoundError):
            self.bus.dispatch(cmd)

    def test_dispatch_persists_events(self):
        from apps.eventstore.models import DomainEvent

        @command_handler(CreateThingCommand)
        def handle(cmd):
            return [_make_event(cmd.workspace_id, self.agg_id)]

        cmd = CreateThingCommand(workspace_id=self.ws, issued_by=SYSTEM_ACTOR)
        result = self.bus.dispatch(cmd)

        assert len(result) == 1
        assert DomainEvent.objects.filter(workspace_id=self.ws).count() == 1

    def test_dispatch_stamps_causation_id(self):
        @command_handler(CreateThingCommand)
        def handle(cmd):
            return [_make_event(cmd.workspace_id, self.agg_id)]

        cmd = CreateThingCommand(workspace_id=self.ws, issued_by=SYSTEM_ACTOR)
        result = self.bus.dispatch(cmd)

        assert result[0].causation_id == cmd.correlation_id

    def test_dispatch_multiple_events(self):
        from apps.eventstore.models import DomainEvent

        @command_handler(CreateThingCommand)
        def handle(cmd):
            return [
                _make_event(cmd.workspace_id, self.agg_id, "thing.created", 1),
                _make_event(cmd.workspace_id, self.agg_id, "thing.tagged", 2),
            ]

        cmd = CreateThingCommand(workspace_id=self.ws, issued_by=SYSTEM_ACTOR)
        result = self.bus.dispatch(cmd)

        assert len(result) == 2
        assert DomainEvent.objects.filter(workspace_id=self.ws).count() == 2

    def test_dispatch_handler_returns_empty_list(self):
        @command_handler(CreateThingCommand)
        def handle(cmd):
            return []

        cmd = CreateThingCommand(workspace_id=self.ws, issued_by=SYSTEM_ACTOR)
        result = self.bus.dispatch(cmd)
        assert result == []

    def test_concurrency_check_passes_on_correct_version(self):
        @command_handler(CreateThingCommand)
        def handle_create(cmd):
            return [_make_event(cmd.workspace_id, self.agg_id, version=1)]

        @command_handler(UpdateThingCommand)
        def handle_update(cmd):
            return [_make_event(cmd.workspace_id, self.agg_id, "thing.updated", version=2)]

        # Create v1
        create_cmd = CreateThingCommand(workspace_id=self.ws, issued_by=SYSTEM_ACTOR)
        self.bus.dispatch(create_cmd)

        # Update expecting v1
        update_cmd = UpdateThingCommand(
            workspace_id=self.ws,
            issued_by=SYSTEM_ACTOR,
            aggregate_type="Thing",
            aggregate_id=self.agg_id,
            expected_version=1,
        )
        result = self.bus.dispatch(update_cmd)
        assert len(result) == 1

    def test_concurrency_check_fails_on_stale_version(self):
        @command_handler(CreateThingCommand)
        def handle_create(cmd):
            return [_make_event(cmd.workspace_id, self.agg_id, version=1)]

        @command_handler(UpdateThingCommand)
        def handle_update(cmd):
            return [_make_event(cmd.workspace_id, self.agg_id, "thing.updated", version=2)]

        # Create v1
        create_cmd = CreateThingCommand(workspace_id=self.ws, issued_by=SYSTEM_ACTOR)
        self.bus.dispatch(create_cmd)

        # Update expecting stale version 0
        update_cmd = UpdateThingCommand(
            workspace_id=self.ws,
            issued_by=SYSTEM_ACTOR,
            aggregate_type="Thing",
            aggregate_id=self.agg_id,
            expected_version=0,  # stale!
        )
        with pytest.raises(ConcurrencyError):
            self.bus.dispatch(update_cmd)

    def test_subscriber_called_after_dispatch(self):
        from apps.eventstore.registry import event_subscriber

        calls = []

        @event_subscriber("thing.created")
        def on_thing_created(event):
            calls.append(event.event_type)

        @command_handler(CreateThingCommand)
        def handle(cmd):
            return [_make_event(cmd.workspace_id, self.agg_id)]

        cmd = CreateThingCommand(workspace_id=self.ws, issued_by=SYSTEM_ACTOR)
        self.bus.dispatch(cmd)

        assert calls == ["thing.created"]

    def test_failing_subscriber_does_not_rollback(self):
        """A subscriber that raises must not crash the command."""
        from apps.eventstore.models import DomainEvent
        from apps.eventstore.registry import event_subscriber

        @event_subscriber("thing.created")
        def bad_subscriber(event):
            raise RuntimeError("subscriber exploded")

        @command_handler(CreateThingCommand)
        def handle(cmd):
            return [_make_event(cmd.workspace_id, self.agg_id)]

        cmd = CreateThingCommand(workspace_id=self.ws, issued_by=SYSTEM_ACTOR)
        # Should NOT raise despite bad subscriber
        result = self.bus.dispatch(cmd)
        assert len(result) == 1
        assert DomainEvent.objects.filter(workspace_id=self.ws).count() == 1

    @patch.object(CommandBus, "_dispatch_async_tasks")
    def test_async_tasks_dispatched(self, mock_async):
        @command_handler(CreateThingCommand)
        def handle(cmd):
            return [_make_event(cmd.workspace_id, self.agg_id)]

        cmd = CreateThingCommand(workspace_id=self.ws, issued_by=SYSTEM_ACTOR)
        self.bus.dispatch(cmd)

        mock_async.assert_called_once()
