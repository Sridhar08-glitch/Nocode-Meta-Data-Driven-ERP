"""
Activity Feed — human-readable timeline of changes per record/workspace.
Projected from DomainEvents; this table is a read model / projection.
"""
from django.db import models

from apps.core.models import UUIDPrimaryKeyMixin


class ActivityEntry(UUIDPrimaryKeyMixin):
    """
    A single human-readable activity item on a record's timeline.
    Written by the projection worker; never edited after creation.
    """
    ACTIVITY_TYPE = [
        ("record_created", "Record Created"),
        ("record_updated", "Record Updated"),
        ("record_deleted", "Record Deleted"),
        ("record_restored", "Record Restored"),
        ("field_changed", "Field Changed"),
        ("comment_added", "Comment Added"),
        ("comment_edited", "Comment Edited"),
        ("comment_deleted", "Comment Deleted"),
        ("file_attached", "File Attached"),
        ("file_removed", "File Removed"),
        ("relationship_linked", "Relationship Linked"),
        ("relationship_unlinked", "Relationship Unlinked"),
        ("workflow_started", "Workflow Started"),
        ("workflow_completed", "Workflow Completed"),
        ("workflow_failed", "Workflow Failed"),
        ("approval_requested", "Approval Requested"),
        ("approval_approved", "Approved"),
        ("approval_rejected", "Rejected"),
        ("assignment_changed", "Assigned"),
        ("stage_changed", "Stage Changed"),
        ("tag_added", "Tag Added"),
        ("tag_removed", "Tag Removed"),
        ("sla_warning", "SLA Warning"),
        ("sla_breached", "SLA Breached"),
        ("sla_met", "SLA Met"),
        ("email_sent", "Email Sent"),
        ("note_added", "Note Added"),
        ("custom", "Custom"),
    ]

    workspace_id = models.UUIDField(db_index=True)
    entity_id = models.UUIDField(db_index=True)
    record_id = models.UUIDField(db_index=True)

    activity_type = models.CharField(max_length=30, choices=ACTIVITY_TYPE)

    # Actor
    actor_id = models.UUIDField(null=True, blank=True)
    actor_type = models.CharField(
        max_length=20,
        choices=[
            ("user", "User"),
            ("system", "System"),
            ("workflow", "Workflow"),
            ("api_key", "API Key"),
            ("portal_user", "Portal User"),
        ],
        default="user",
    )
    actor_name = models.CharField(max_length=255, blank=True)  # snapshot

    # Human-readable summary
    summary = models.TextField()

    # Structured diff (for field_changed entries)
    changes = models.JSONField(default=list)
    # [{"field_slug": "status", "field_label": "Status", "old": "open", "new": "closed"}]

    # Source event
    event_id = models.UUIDField(null=True, blank=True)
    event_sequence = models.BigIntegerField(null=True, blank=True, db_index=True)

    occurred_at = models.DateTimeField(db_index=True)

    # Pinned activities show at top of feed
    is_pinned = models.BooleanField(default=False)

    class Meta:
        db_table = "activity_entries"
        indexes = [
            models.Index(fields=["workspace_id", "record_id", "-occurred_at"]),
            models.Index(fields=["workspace_id", "entity_id", "-occurred_at"]),
        ]


class Comment(UUIDPrimaryKeyMixin):
    """
    A threaded comment on a record.
    Comments fire DomainEvents which become ActivityEntry rows.
    """
    workspace_id = models.UUIDField(db_index=True)
    entity_id = models.UUIDField()
    record_id = models.UUIDField(db_index=True)

    author_id = models.UUIDField()
    author_type = models.CharField(
        max_length=20,
        choices=[("member", "Member"), ("portal_user", "Portal User")],
        default="member",
    )

    parent_id = models.UUIDField(null=True, blank=True, db_index=True)  # thread reply
    body = models.TextField()
    body_format = models.CharField(
        max_length=10,
        choices=[("markdown", "Markdown"), ("plain", "Plain")],
        default="markdown",
    )

    # Mentions: [{type: "member"|"team", id: uuid}]
    mentions = models.JSONField(default=list)

    is_edited = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    is_pinned = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "comments"
        indexes = [
            models.Index(fields=["workspace_id", "record_id", "created_at"]),
            models.Index(fields=["parent_id"]),
        ]
