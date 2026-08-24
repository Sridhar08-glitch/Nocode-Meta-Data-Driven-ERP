"""
Event Store — Pillar 2.
domain_events is the append-only source of truth.
All state mutations flow: Command → domain_events → Projection.
"""
import uuid

from django.db import models
from django.utils import timezone

from apps.core.models import UUIDPrimaryKeyMixin


class DomainEvent(models.Model):
    """
    Append-only event log. NEVER update or delete rows.
    global_sequence is the total order of all events in the system.

    In PostgreSQL:  a BEFORE INSERT trigger populates global_sequence from
                    the domain_event_global_seq sequence.  Django sends NULL;
                    the trigger fills it in before the row is committed.
    In SQLite:      save() computes MAX(global_sequence)+1 so tests work
                    without any DB-side sequence infrastructure.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # null=True so Django sends NULL on INSERT; the PostgreSQL BEFORE INSERT
    # trigger then fills this from the domain_event_global_seq sequence.
    # Unique constraint is still enforced at DB level on non-NULL values.
    global_sequence = models.BigIntegerField(
        unique=True, editable=False, db_index=True, null=True, blank=True
    )

    # What
    event_type = models.CharField(max_length=255, db_index=True)
    event_version = models.SmallIntegerField(default=1)  # schema version for upcasting

    # Aggregate version AFTER this event is applied (optimistic concurrency)
    version = models.BigIntegerField(default=1, db_index=True)

    # Who / where (aggregate identity)
    aggregate_type = models.CharField(max_length=100, db_index=True)
    aggregate_id = models.UUIDField(db_index=True)
    workspace_id = models.UUIDField(db_index=True)

    # Payload
    payload = models.JSONField()

    # Context
    causation_id = models.UUIDField(null=True, blank=True)
    correlation_id = models.UUIDField(null=True, blank=True)
    actor_id = models.UUIDField(null=True, blank=True)
    actor_type = models.CharField(max_length=50, default="user")

    # Metadata
    metadata = models.JSONField(default=dict)
    occurred_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = "domain_events"
        ordering = ["global_sequence"]
        # Index names must match what migrations 0001/0002 created exactly.
        indexes = [
            models.Index(
                fields=["workspace_id", "aggregate_type", "aggregate_id"],
                name="domain_even_workspa_9ac4a0_idx",
            ),
            models.Index(
                fields=["workspace_id", "aggregate_type", "aggregate_id", "version"],
                name="domainevent_ws_agg_version_idx",
            ),
            models.Index(
                fields=["workspace_id", "event_type"],
                name="domain_even_workspa_8f0f8b_idx",
            ),
            models.Index(
                fields=["occurred_at"],
                name="domain_even_occurre_e69e84_idx",
            ),
            models.Index(
                fields=["correlation_id"],
                name="domain_even_correla_67d43d_idx",
            ),
        ]

    def __str__(self):
        return (
            f"[{self.global_sequence}] {self.event_type} on "
            f"{self.aggregate_type}:{self.aggregate_id} v{self.version}"
        )

    def save(self, *args, **kwargs):
        # Immutability guard — events are write-once.
        if self.pk and DomainEvent.objects.filter(pk=self.pk).exists():
            raise ValueError(
                "DomainEvent records are immutable — never update an event."
            )

        # SQLite has no sequence trigger; compute global_sequence here so the
        # NOT NULL-equivalent unique constraint is satisfied.
        # PostgreSQL: trigger fires BEFORE INSERT and sets this from the sequence,
        # so we leave global_sequence as NULL and let the trigger win.
        if self.global_sequence is None:
            from django.db import connection
            if connection.vendor == "sqlite":
                with connection.cursor() as cur:
                    cur.execute(
                        "SELECT COALESCE(MAX(global_sequence), 0) + 1 "
                        "FROM domain_events"
                    )
                    self.global_sequence = cur.fetchone()[0]

        super().save(*args, **kwargs)

        # After a PostgreSQL INSERT the trigger has set global_sequence server-side.
        # Refresh the Python instance so it reflects the committed value.
        if self.global_sequence is None:
            self.refresh_from_db(fields=["global_sequence"])


class AggregateSnapshot(UUIDPrimaryKeyMixin):
    """
    Periodic snapshots of aggregate state to speed up replay.
    """
    aggregate_type = models.CharField(max_length=100, db_index=True)
    aggregate_id = models.UUIDField(db_index=True)
    workspace_id = models.UUIDField(db_index=True)
    version = models.BigIntegerField()
    state = models.JSONField()
    taken_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "aggregate_snapshots"
        unique_together = [("aggregate_type", "aggregate_id", "version")]
        indexes = [
            models.Index(fields=["aggregate_type", "aggregate_id", "-version"]),
        ]


class ProjectionCheckpoint(UUIDPrimaryKeyMixin):
    """
    Tracks the last-processed global_sequence for each projection consumer.
    Guarantees idempotent, ordered event processing.
    """
    projection_name = models.CharField(max_length=100, unique=True, db_index=True)
    last_sequence = models.BigIntegerField(default=0)
    last_event_id = models.UUIDField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    error_count = models.IntegerField(default=0)
    last_error = models.TextField(blank=True)

    class Meta:
        db_table = "projection_checkpoints"

    def advance(self, sequence: int, event_id):
        self.last_sequence = sequence
        self.last_event_id = event_id
        self.error_count = 0
        self.last_error = ""
        self.save(
            update_fields=[
                "last_sequence", "last_event_id",
                "error_count", "last_error", "updated_at",
            ]
        )


class CommandLog(UUIDPrimaryKeyMixin):
    """
    Log of all commands dispatched through the command bus.
    Audit trail only — NOT the source of truth (events are).
    """
    command_type = models.CharField(max_length=255, db_index=True)
    payload = models.JSONField()
    workspace_id = models.UUIDField(null=True, blank=True, db_index=True)
    actor_id = models.UUIDField(null=True, blank=True)
    status = models.CharField(max_length=20, default="pending")
    result_event_ids = models.JSONField(default=list)
    error = models.TextField(blank=True)
    dispatched_at = models.DateTimeField(default=timezone.now, db_index=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    duration_ms = models.IntegerField(null=True, blank=True)

    class Meta:
        db_table = "command_log"
        indexes = [
            models.Index(fields=["workspace_id", "command_type"]),
            models.Index(fields=["dispatched_at"]),
        ]
