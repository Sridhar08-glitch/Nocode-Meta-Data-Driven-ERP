"""
Proves the event-sourcing loop for metadata: a schema change appends a DomainEvent,
and the projection runner builds the audit trail from it (Pillar 2 / §11).
"""
import uuid

import pytest

from apps.audit.models import AuditLog
from apps.eventstore.models import DomainEvent
from apps.projections.services import rebuild_projection, run_projections
from apps.relationships.services import RelationshipService
from apps.schema_registry.services import SchemaRegistryService


@pytest.mark.django_db
class TestMetadataProjection:
    def test_create_entity_emits_event(self):
        ws = uuid.uuid4()
        SchemaRegistryService.create_entity(
            workspace_id=ws, slug="lead", name="Lead", plural_name="Leads")
        assert DomainEvent.objects.filter(event_type="entity.created", workspace_id=ws).count() == 1

    def test_projection_builds_audit_trail(self):
        ws = uuid.uuid4()
        SchemaRegistryService.create_entity(
            workspace_id=ws, slug="lead", name="Lead", plural_name="Leads")
        SchemaRegistryService.add_field(
            workspace_id=ws, entity_slug="lead", slug="amount", name="Amount", field_type="decimal")
        n = run_projections()
        assert n >= 2
        actions = set(AuditLog.objects.filter(workspace_id=ws).values_list("action", flat=True))
        assert {"entity.created", "field.added"} <= actions

    def test_projection_idempotent_and_rebuildable(self):
        ws = uuid.uuid4()
        SchemaRegistryService.create_entity(
            workspace_id=ws, slug="lead", name="Lead", plural_name="Leads")
        run_projections()
        count = AuditLog.objects.count()
        run_projections()                       # no new events → no new audit rows
        assert AuditLog.objects.count() == count
        rebuild_projection()                    # replay all → idempotent (keyed on event_id)
        assert AuditLog.objects.count() == count

    def test_relationship_events_emitted(self):
        ws = uuid.uuid4()
        a = SchemaRegistryService.create_entity(
            workspace_id=ws, slug="account", name="Account", plural_name="Accounts")
        b = SchemaRegistryService.create_entity(
            workspace_id=ws, slug="contact", name="Contact", plural_name="Contacts")
        RelationshipService.create_relationship(
            workspace_id=ws, name="AC", slug="ac", source_entity_id=a.id,
            target_entity_id=b.id, cardinality="many_to_many")
        run_projections()
        assert AuditLog.objects.filter(action="relationship.created", workspace_id=ws).count() == 1
