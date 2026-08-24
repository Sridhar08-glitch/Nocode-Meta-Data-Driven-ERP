"""
Command handler registry.

Handlers are registered with @command_handler(SomeCommand) and are
discovered automatically when apps are ready (via AppConfig.ready()).

Each command type maps to exactly ONE handler function.  If you need
multiple side effects, the handler should emit multiple DomainEventData
objects and registered projectors/subscribers handle them.
"""
from __future__ import annotations

import logging
from collections.abc import Callable

from apps.eventstore.commands import Command
from apps.eventstore.exceptions import CommandHandlerNotFoundError

logger = logging.getLogger(__name__)

# { CommandClass: handler_callable }
_HANDLER_REGISTRY: dict[type[Command], Callable] = {}

# { event_type_str: [subscriber_callable, ...] }
_EVENT_SUBSCRIBERS: dict[str, list[Callable]] = {}


# ── Registration decorators ──────────────────────────────────────────────────

def command_handler(command_class: type[Command]):
    """
    Decorator to register a function as the handler for a command type.

    The decorated function must accept (command: CommandSubclass) and return
    list[DomainEventData].

    Example:
        @command_handler(CreateRecordCommand)
        def handle_create_record(cmd: CreateRecordCommand) -> list[DomainEventData]:
            ...
            return [DomainEventData(...)]
    """
    def decorator(fn: Callable) -> Callable:
        if command_class in _HANDLER_REGISTRY:
            existing = _HANDLER_REGISTRY[command_class].__qualname__
            raise RuntimeError(
                f"Duplicate handler for {command_class.__name__}: "
                f"already registered as '{existing}', tried to register '{fn.__qualname__}'"
            )
        _HANDLER_REGISTRY[command_class] = fn
        logger.debug("Registered handler %s → %s", command_class.__name__, fn.__qualname__)
        return fn
    return decorator


def event_subscriber(*event_types: str):
    """
    Decorator to register a function as a subscriber for one or more event types.

    Subscribers are called AFTER events are persisted, within the same
    transaction.  They should be fast (heavy work → Celery task).

    Example:
        @event_subscriber("record.created", "record.updated")
        def on_record_change(event: DomainEvent) -> None:
            from apps.search.tasks import reindex_record
            reindex_record.delay(str(event.aggregate_id))
    """
    def decorator(fn: Callable) -> Callable:
        for event_type in event_types:
            _EVENT_SUBSCRIBERS.setdefault(event_type, []).append(fn)
            logger.debug("Registered subscriber %s → %s", event_type, fn.__qualname__)
        return fn
    return decorator


# ── Look-up helpers ─────────────────────────────────────────────────────────

def get_handler(command: Command) -> Callable:
    """Return the handler for *command* or raise CommandHandlerNotFoundError."""
    handler = _HANDLER_REGISTRY.get(type(command))
    if handler is None:
        raise CommandHandlerNotFoundError(
            f"No handler registered for command type: {type(command).__name__}"
        )
    return handler


def get_subscribers(event_type: str) -> list[Callable]:
    """Return all subscribers for *event_type* (empty list if none)."""
    return list(_EVENT_SUBSCRIBERS.get(event_type, []))


def get_all_registered_commands() -> list[type[Command]]:
    """Utility: return a list of all registered command types (useful in tests)."""
    return list(_HANDLER_REGISTRY.keys())


def clear_registry() -> None:
    """
    Clear all registrations.  ONLY for use in tests — never call in production.
    """
    _HANDLER_REGISTRY.clear()
    _EVENT_SUBSCRIBERS.clear()
