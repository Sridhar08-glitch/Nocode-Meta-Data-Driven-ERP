"""Event store exceptions."""


class CommandValidationError(Exception):
    """Raised when a command fails validation before dispatch."""
    def __init__(self, errors: dict):
        self.errors = errors
        super().__init__(str(errors))


class CommandHandlerNotFoundError(Exception):
    """Raised when no handler is registered for a command type."""


class EventStoreError(Exception):
    """Generic event store failure."""


class DuplicateEventError(EventStoreError):
    """Attempted to persist a duplicate event (same idempotency key)."""


class ConcurrencyError(EventStoreError):
    """Optimistic-concurrency check failed — expected version mismatch."""
