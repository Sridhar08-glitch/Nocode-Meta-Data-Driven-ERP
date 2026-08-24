"""
Command base classes.

A Command is an intent message — it says "please do X" and is validated
before dispatch.  Commands are NOT persisted; only their resulting
DomainEvents are persisted.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class Command:
    """Base class for all domain commands."""

    # Every command carries workspace context and the issuing member.
    workspace_id: uuid.UUID
    issued_by: uuid.UUID  # member_id (or system UUID for background tasks)

    # Idempotency: callers MAY supply a correlation_id to deduplicate retries.
    correlation_id: uuid.UUID = field(default_factory=uuid.uuid4)
    issued_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Optional: aggregate type + id for optimistic concurrency check.
    aggregate_type: str = ""
    aggregate_id: uuid.UUID | None = None
    expected_version: int | None = None  # None = no concurrency check

    def to_dict(self) -> dict[str, Any]:
        """Serialise for logging / tracing."""
        return {
            "command_type": type(self).__name__,
            "workspace_id": str(self.workspace_id),
            "issued_by": str(self.issued_by),
            "correlation_id": str(self.correlation_id),
            "issued_at": self.issued_at.isoformat(),
            "aggregate_type": self.aggregate_type,
            "aggregate_id": str(self.aggregate_id) if self.aggregate_id else None,
            "expected_version": self.expected_version,
        }


# ── System sentinel ─────────────────────────────────────────────────────────

# Use this as `issued_by` for background / system-generated commands.
SYSTEM_ACTOR = uuid.UUID("00000000-0000-0000-0000-000000000000")
