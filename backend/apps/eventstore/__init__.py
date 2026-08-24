"""
Event store package.

Public API (import from here):

    from apps.eventstore import bus, Command, DomainEventData
    from apps.eventstore import command_handler, event_subscriber, event_projector
    from apps.eventstore.rls import set_workspace_rls, workspace_rls_context

The module is intentionally thin — heavy logic lives in the sub-modules.
"""
from apps.eventstore.bus import CommandBus, bus
from apps.eventstore.commands import SYSTEM_ACTOR, Command
from apps.eventstore.events import DomainEventData, DomainEventFactory
from apps.eventstore.exceptions import (
    CommandHandlerNotFoundError,
    CommandValidationError,
    ConcurrencyError,
    DuplicateEventError,
    EventStoreError,
)
from apps.eventstore.projectors import event_projector, get_projectors
from apps.eventstore.registry import command_handler, event_subscriber

__all__ = [
    # Bus
    "bus",
    "CommandBus",
    # Commands
    "Command",
    "SYSTEM_ACTOR",
    "command_handler",
    # Events
    "DomainEventData",
    "DomainEventFactory",
    "event_subscriber",
    # Projectors
    "event_projector",
    "get_projectors",
    # Exceptions
    "CommandHandlerNotFoundError",
    "CommandValidationError",
    "ConcurrencyError",
    "DuplicateEventError",
    "EventStoreError",
]
