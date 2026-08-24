"""
RelationshipService — the relationship builder.

Provisions typed links between entities by reusing the schema engine:

- ``one_to_one``  → a unique promoted ``lookup`` (FK) column on the **source** entity.
- ``one_to_many`` → a promoted ``lookup`` (FK) column on the **target** entity
  (the "many" side holds the foreign key back to the "one").
- ``many_to_many`` → no DDL; instance links are stored in ``RecordRelationship``.

All physical-column work goes through ``SchemaRegistryService`` (which drives
``PhysicalTableGenerator`` + schema versioning) — no duplicate DDL logic here.
"""
import contextlib
import uuid

from django.db import connection, transaction

from apps.metadata.models import EntityDefinition
from apps.schema_registry.services import SchemaRegistryService, _validate_slug

from .models import RecordRelationship, RelationshipDefinition

VALID_CARDINALITIES = {c[0] for c in RelationshipDefinition.CARDINALITY}


def _emit_rel(rel, event_type: str, payload: dict, actor_id) -> None:
    """Append a relationship change to the event store (audit/replay — §11)."""
    from apps.eventstore.events import DomainEventData, DomainEventFactory
    DomainEventFactory.persist_one(DomainEventData(
        event_type=event_type, workspace_id=rel.workspace_id,
        aggregate_type="relationship", aggregate_id=rel.id,
        payload=payload, actor_id=actor_id or uuid.UUID(int=0),
    ))


class RelationshipError(Exception):
    """Base error for relationship operations."""


class RelationshipNotFoundError(RelationshipError):
    pass


class RelationshipValidationError(RelationshipError):
    pass


class RelationshipService:
    @staticmethod
    def _entity(workspace_id, entity_id) -> EntityDefinition:
        ent = EntityDefinition.objects.filter(workspace_id=workspace_id, id=entity_id).first()
        if ent is None:
            raise RelationshipValidationError(f"Entity {entity_id} not found in workspace.")
        return ent

    @classmethod
    def create_relationship(
        cls, *, workspace_id: uuid.UUID, name: str, slug: str,
        source_entity_id, target_entity_id, cardinality: str,
        on_delete: str = "detach", source_field_slug: str | None = None,
        created_by: uuid.UUID | None = None,
    ) -> RelationshipDefinition:
        _validate_slug(slug, "relationship slug")
        if cardinality not in VALID_CARDINALITIES:
            raise RelationshipValidationError(
                f"Invalid cardinality {cardinality!r}. One of {sorted(VALID_CARDINALITIES)}.")

        source = cls._entity(workspace_id, source_entity_id)
        target = cls._entity(workspace_id, target_entity_id)

        if RelationshipDefinition.objects.filter(
            workspace_id=workspace_id, source_entity_id=source_entity_id, slug=slug
        ).exists():
            raise RelationshipValidationError(
                f"Relationship {slug!r} already exists on this source entity.")

        with transaction.atomic():
            src_field = ""
            tgt_field = ""
            if cardinality in ("one_to_one", "one_to_many", "self_ref"):
                if cardinality == "one_to_one":
                    holder, points_to = source, target
                elif cardinality == "one_to_many":
                    holder, points_to = target, source   # the "many" side holds the FK
                else:  # self_ref — FK on the entity pointing back to itself
                    holder, points_to = source, source
                default_slug = "parent_ref" if cardinality == "self_ref" else f"{points_to.slug}_ref"
                fslug = source_field_slug or default_slug
                _validate_slug(fslug, "lookup field slug")
                # SQLite cannot ADD COLUMN ... UNIQUE; apply the DB-level unique
                # constraint only on PostgreSQL (production). The relationship
                # definition records the one_to_one semantics regardless.
                unique = cardinality == "one_to_one" and connection.vendor == "postgresql"
                SchemaRegistryService.add_field(
                    workspace_id=workspace_id, entity_slug=holder.slug,
                    slug=fslug, name=f"{points_to.name}", field_type="lookup",
                    is_promoted=True, is_unique=unique,
                    config={"target_entity_slug": points_to.slug, "relationship_slug": slug},
                    updated_by=created_by,
                )
                if cardinality == "one_to_many":
                    tgt_field = fslug
                else:  # one_to_one or self_ref → FK lives on the source side
                    src_field = fslug

            rel = RelationshipDefinition.objects.create(
                workspace_id=workspace_id, name=name, slug=slug,
                source_entity_id=source_entity_id, target_entity_id=target_entity_id,
                source_field_slug=src_field, target_field_slug=tgt_field,
                cardinality=cardinality, on_delete=on_delete, junction_table="",
            )
            _emit_rel(rel, "relationship.created",
                      {"slug": slug, "cardinality": cardinality}, created_by)
        return rel

    @classmethod
    def list_relationships(cls, *, workspace_id, entity_id=None):
        qs = RelationshipDefinition.objects.filter(workspace_id=workspace_id)
        if entity_id is not None:
            from django.db.models import Q
            qs = qs.filter(Q(source_entity_id=entity_id) | Q(target_entity_id=entity_id))
        return qs.order_by("name")

    @classmethod
    def get_relationship(cls, *, workspace_id, relationship_id) -> RelationshipDefinition:
        rel = RelationshipDefinition.objects.filter(
            workspace_id=workspace_id, id=relationship_id).first()
        if rel is None:
            raise RelationshipNotFoundError(f"Relationship {relationship_id} not found.")
        return rel

    @classmethod
    def delete_relationship(cls, *, workspace_id, relationship_id, deleted_by=None) -> None:
        rel = cls.get_relationship(workspace_id=workspace_id, relationship_id=relationship_id)
        with transaction.atomic():
            # Drop the provisioned FK column (if any) from whichever entity holds it.
            if rel.cardinality in ("one_to_one", "self_ref") and rel.source_field_slug:
                holder_id, fslug = rel.source_entity_id, rel.source_field_slug
            elif rel.cardinality == "one_to_many" and rel.target_field_slug:
                holder_id, fslug = rel.target_entity_id, rel.target_field_slug
            else:
                holder_id, fslug = None, ""
            if holder_id and fslug:
                holder = cls._entity(workspace_id, holder_id)
                # Field may already be gone; removal is best-effort.
                with contextlib.suppress(Exception):
                    SchemaRegistryService.remove_field(
                        workspace_id=workspace_id, entity_slug=holder.slug,
                        field_slug=fslug, updated_by=deleted_by)
            RecordRelationship.objects.filter(
                workspace_id=workspace_id, definition_id=rel.id).delete()
            _emit_rel(rel, "relationship.deleted", {"slug": rel.slug}, deleted_by)
            rel.delete()

    # ── Instance links (many-to-many / flexible) ──────────────────────────────
    @classmethod
    def link_records(cls, *, workspace_id, relationship_id, source_record_id,
                     target_record_id, created_by=None) -> RecordRelationship:
        rel = cls.get_relationship(workspace_id=workspace_id, relationship_id=relationship_id)
        link, _ = RecordRelationship.objects.get_or_create(
            workspace_id=workspace_id, definition_id=rel.id,
            source_record_id=source_record_id, target_record_id=target_record_id,
            defaults={
                "source_entity_id": rel.source_entity_id,
                "target_entity_id": rel.target_entity_id,
                "created_by": created_by,
            },
        )
        return link

    @classmethod
    def unlink_records(cls, *, workspace_id, relationship_id, source_record_id,
                       target_record_id) -> int:
        rel = cls.get_relationship(workspace_id=workspace_id, relationship_id=relationship_id)
        deleted, _ = RecordRelationship.objects.filter(
            workspace_id=workspace_id, definition_id=rel.id,
            source_record_id=source_record_id, target_record_id=target_record_id).delete()
        return deleted
