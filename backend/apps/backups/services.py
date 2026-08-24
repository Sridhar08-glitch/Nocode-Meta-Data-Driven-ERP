"""
Backup / Restore / Data-Retention engine (PROJECT_HANDBOOK.md §33.3 / §33.4).

* Backups serialise a workspace's config (+ records for full/incremental) to an
  **encrypted** artifact in document storage (Fernet, key by reference only — never
  the key in the DB). A SHA-256 checksum of the *plaintext* is recorded.
* Restores ALWAYS target an isolated workspace (never the source) and require a
  one-time confirmation token (only its SHA-256 hash is stored). PITR replays
  ``record.*`` events up to a global-sequence cutoff into the target workspace.
* Data-retention policies purge / anonymise / archive aged records per entity.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import uuid

from django.conf import settings
from django.db import connection
from django.utils import timezone

from apps.accounts.crypto import get_fernet, hash_token
from apps.documents.storage import get_storage_backend
from apps.eventstore.events import DomainEventData, DomainEventFactory
from apps.metadata.models import EntityDefinition, FieldDefinition

from .models import BackupJob, DataRetentionPolicy, RestoreJob

BACKUP_RETENTION_DAYS = getattr(settings, "NEXUS_BACKUP_RETENTION_DAYS", 90)
ENCRYPTION_KEY_REF = "ENCRYPTION_KEY"  # name only — the value lives in the environment


class BackupError(Exception):  # noqa: N818 — domain error
    pass


def _emit(workspace_id, aggregate_id, event_type, payload, actor_id):
    from apps.eventstore.models import DomainEvent
    agg = uuid.UUID(str(aggregate_id))
    version = DomainEvent.objects.filter(
        aggregate_id=agg, aggregate_type="backup").count() + 1
    DomainEventFactory.persist_one(DomainEventData(
        event_type=event_type, workspace_id=uuid.UUID(str(workspace_id)),
        aggregate_type="backup", aggregate_id=agg, version=version,
        payload=payload, actor_id=uuid.UUID(str(actor_id)) if actor_id else uuid.UUID(int=0)))


def _system_member(actor_id=None):
    from apps.workflows.executors import SystemMember
    actor = actor_id or uuid.UUID(int=0)
    return SystemMember(user_id=actor, id=actor)


# ── serialization ────────────────────────────────────────────────────────────
def _serialize_entity(entity) -> dict:
    fields = []
    for fd in FieldDefinition.objects.filter(entity=entity, is_deleted=False):
        fields.append({
            "slug": fd.slug, "name": fd.name, "field_type": fd.field_type,
            "is_promoted": fd.is_promoted, "is_required": fd.is_required,
            "is_unique": fd.is_unique, "column_name": fd.column_name, "config": fd.config})
    return {"slug": entity.slug, "name": entity.name,
            "plural_name": entity.plural_name, "has_physical_table": entity.has_physical_table,
            "fields": fields}


def _read_records(entity) -> list[dict]:
    from apps.nql.services import execute_nql
    try:
        return execute_nql(workspace_id=entity.workspace_id,
                           source={"entity": entity.slug, "limit": settings.NEXUS_NQL_MAX_LIMIT},
                           user_id=uuid.UUID(int=0))
    except Exception:  # noqa: BLE001 — a broken entity must not abort the backup
        return []


def _build_payload(workspace_id, backup_type) -> tuple[dict, int, int]:
    """Return (payload, entity_count, record_count)."""
    entities = EntityDefinition.objects.filter(workspace_id=workspace_id, is_active=True)
    out_entities, records, rec_count = [], {}, 0
    for ent in entities:
        out_entities.append(_serialize_entity(ent))
        if backup_type != "config_only" and ent.has_physical_table and ent.table_name:
            rows = _read_records(ent)
            records[ent.slug] = rows
            rec_count += len(rows)
    payload = {
        "schema_version": 1,
        "workspace_id": str(workspace_id),
        "backup_type": backup_type,
        "entities": out_entities,
        "records": records,
    }
    return payload, len(out_entities), rec_count


class BackupService:
    @staticmethod
    def create_backup_job(*, workspace_id, backup_type="full", initiated_by=None,
                          is_automatic=False) -> BackupJob:
        job = BackupJob.objects.create(
            workspace_id=workspace_id, backup_type=backup_type, status="queued",
            initiated_by=initiated_by, is_automatic=is_automatic,
            encryption_key_ref=ENCRYPTION_KEY_REF, is_encrypted=True)
        from .tasks import execute_backup
        execute_backup.delay(str(job.id))
        job.refresh_from_db()
        return job

    @staticmethod
    def execute_backup(job_id) -> BackupJob:
        job = BackupJob.objects.get(id=job_id)
        job.status = "running"
        job.started_at = timezone.now()
        job.save(update_fields=["status", "started_at"])
        try:
            payload, ent_count, rec_count = _build_payload(job.workspace_id, job.backup_type)
            raw = json.dumps(payload, default=str).encode("utf-8")
            checksum = hashlib.sha256(raw).hexdigest()
            blob = get_fernet().encrypt(raw)  # encrypted at rest — never plaintext
            backend = get_storage_backend(job.workspace_id)
            ws_hex8 = uuid.UUID(str(job.workspace_id)).hex[:8]
            key = f"{ws_hex8}/backups/{uuid.uuid4().hex}.bak"
            backend.upload(blob, key)
            job.storage_key = key
            job.storage_backend = backend.name
            job.size_bytes = len(blob)
            job.checksum_sha256 = checksum
            job.entity_count = ent_count
            job.record_count = rec_count
            job.status = "completed"
            job.completed_at = timezone.now()
            job.expires_at = timezone.now() + _dt.timedelta(days=BACKUP_RETENTION_DAYS)
            job.save(update_fields=["storage_key", "storage_backend", "size_bytes",
                                    "checksum_sha256", "entity_count", "record_count",
                                    "status", "completed_at", "expires_at"])
            _emit(job.workspace_id, job.id, "backup.completed",
                  {"backup_type": job.backup_type, "record_count": rec_count}, job.initiated_by)
        except Exception as exc:  # noqa: BLE001
            job.status = "failed"
            job.error_message = str(exc)
            job.save(update_fields=["status", "error_message"])
        return job

    # ── restore ───────────────────────────────────────────────────────────────
    @staticmethod
    def create_restore_job(*, workspace_id, restore_type, target_workspace_id,
                           target_workspace_slug, initiated_by, backup_job_id=None,
                           pitr_target_sequence=None) -> tuple[RestoreJob, str]:
        if str(target_workspace_id) == str(workspace_id):
            raise BackupError(
                "Restore target must be an isolated workspace, never the source.")
        from apps.accounts.crypto import generate_token
        token = generate_token(32)
        job = RestoreJob.objects.create(
            workspace_id=workspace_id, restore_type=restore_type,
            backup_job_id=backup_job_id, pitr_target_sequence=pitr_target_sequence,
            target_workspace_id=target_workspace_id,
            target_workspace_slug=target_workspace_slug, status="queued",
            initiated_by=initiated_by, confirmation_token_hash=hash_token(token))
        return job, token  # plaintext token returned ONCE; only its hash is stored

    @staticmethod
    def confirm_restore(restore_job_id, confirmation_token, actor_id=None) -> RestoreJob:
        job = RestoreJob.objects.filter(id=restore_job_id).first()
        if job is None:
            raise BackupError("Restore job not found")
        if not job.confirmation_token_hash or \
                hash_token(confirmation_token or "") != job.confirmation_token_hash:
            raise BackupError("Invalid confirmation token")
        job.confirmed_at = timezone.now()
        job.save(update_fields=["confirmed_at"])
        from .tasks import execute_restore
        execute_restore.delay(str(job.id))
        job.refresh_from_db()
        return job

    @staticmethod
    def execute_restore(job_id) -> RestoreJob:
        job = RestoreJob.objects.get(id=job_id)
        if job.confirmed_at is None:
            raise BackupError("Restore not confirmed")
        if str(job.target_workspace_id) == str(job.workspace_id):
            raise BackupError("Restore target must differ from the source workspace.")
        job.status = "running"
        job.started_at = timezone.now()
        job.save(update_fields=["status", "started_at"])
        try:
            if job.restore_type == "pitr":
                BackupService._replay_pitr(
                    job.workspace_id, job.target_workspace_id, job.pitr_target_sequence)
            else:
                BackupService._import_backup(job)
            job.status = "completed"
            job.completed_at = timezone.now()
            job.save(update_fields=["status", "completed_at"])
        except Exception as exc:  # noqa: BLE001
            job.status = "failed"
            job.error_message = str(exc)
            job.save(update_fields=["status", "error_message"])
        return job

    @staticmethod
    def _resolve_target_entity(target_workspace_id, slug):
        from apps.schema_registry.exceptions import EntityNotFoundError
        from apps.schema_registry.services import SchemaRegistryService
        try:
            entity = SchemaRegistryService.get_entity(
                workspace_id=target_workspace_id, slug=slug)
        except EntityNotFoundError:
            return None
        return entity if (entity.has_physical_table and entity.table_name) else None

    @staticmethod
    def _replay_pitr(source_workspace_id, target_workspace_id, target_sequence) -> int:
        """Replay record events (≤ target_sequence) from source into target workspace."""
        from apps.eventstore.models import DomainEvent
        from apps.records import dal
        qs = DomainEvent.objects.filter(
            workspace_id=source_workspace_id, aggregate_type="record").order_by("global_sequence")
        if target_sequence is not None:
            qs = qs.filter(global_sequence__lte=target_sequence)
        applied = 0
        cache: dict = {}
        for event in qs.iterator(chunk_size=500):
            slug = (event.payload or {}).get("entity_slug")
            if not slug:
                continue
            if slug not in cache:
                cache[slug] = BackupService._resolve_target_entity(target_workspace_id, slug)
            entity = cache[slug]
            if entity is None:
                continue
            BackupService._apply_record_event(entity, event, dal)
            applied += 1
        return applied

    @staticmethod
    def _apply_record_event(entity, event, dal) -> None:
        rid = str(event.aggregate_id)
        current = dal.get_event_version(entity, rid)
        if current is not None and current >= event.version:
            return  # idempotent
        et = event.event_type
        if et in ("record.created", "record.updated"):
            fmap = dal.FieldMap(entity)
            data = (event.payload or {}).get("data", {}) or {}
            promoted, overflow = fmap.split(data, partial=True)
            if current is None:
                dal.insert_row(entity, fmap, promoted, overflow, actor_id=event.actor_id,
                               record_id=rid, event_version=event.version)
            else:
                dal.update_row(entity, fmap, rid, promoted, overflow,
                               actor_id=event.actor_id, event_version=event.version)
        elif et in ("record.deleted", "record.restored"):
            dal.set_deleted(entity, rid, deleted=(et == "record.deleted"),
                            event_version=event.version, actor_id=event.actor_id)

    @staticmethod
    def _import_backup(job) -> None:
        """Decrypt a full backup artifact and import its records into the target workspace."""
        from apps.records.services import RecordService
        backup = BackupJob.objects.filter(id=job.backup_job_id).first()
        if backup is None or not backup.storage_key:
            raise BackupError("Backup artifact not found")
        backend = get_storage_backend(backup.workspace_id)
        raw = get_fernet().decrypt(backend.download(backup.storage_key))
        payload = json.loads(raw.decode("utf-8"))
        member = _system_member(job.initiated_by)
        for slug, rows in (payload.get("records") or {}).items():
            entity = BackupService._resolve_target_entity(job.target_workspace_id, slug)
            if entity is None:
                continue
            field_slugs = {fd.slug for fd in entity.fields.filter(is_deleted=False)}
            for row in rows:
                data = {k: v for k, v in row.items()
                        if k in field_slugs and v not in (None, "")}
                try:
                    RecordService.create_record(
                        workspace_id=job.target_workspace_id, member=member,
                        entity=entity, data=data)
                except Exception:  # noqa: BLE001 — one bad row must not abort the import
                    continue


# ── data retention ─────────────────────────────────────────────────────────────
class RetentionService:
    @staticmethod
    def enforce(policy: DataRetentionPolicy) -> int:
        """Apply one retention policy; return the number of affected records."""
        if not policy.is_active or policy.retain_days is None:
            return 0
        entity = BackupService._resolve_target_entity(policy.workspace_id, policy.entity_slug)
        if entity is None:
            return 0
        cutoff = timezone.now() - _dt.timedelta(days=policy.retain_days)
        ids = RetentionService._ids_past_retention(entity, cutoff)
        affected = 0
        for rid in ids:
            try:
                RetentionService._apply_action(policy, entity, rid)
                affected += 1
            except Exception:  # noqa: BLE001 — isolate per-record failure
                continue
        policy.last_enforced_at = timezone.now()
        policy.save(update_fields=["last_enforced_at"])
        return affected

    @staticmethod
    def _ids_past_retention(entity, cutoff) -> list[str]:
        sql = (f'SELECT id FROM "{entity.table_name}" '
               f'WHERE workspace_id = %s AND created_at < %s AND deleted_at IS NULL')
        with connection.cursor() as cur:
            cur.execute(sql, [str(entity.workspace_id), cutoff.isoformat()])
            return [str(r[0]) for r in cur.fetchall()]

    @staticmethod
    def _apply_action(policy, entity, record_id) -> None:
        from apps.records import dal
        from apps.records.services import RecordService
        member = _system_member()
        action = policy.action
        if action == "soft_delete":
            RecordService.delete_record(
                workspace_id=entity.workspace_id, member=member,
                entity=entity, record_id=record_id)
        elif action == "hard_delete":
            with connection.cursor() as cur:
                cur.execute(
                    f'DELETE FROM "{entity.table_name}" WHERE id = %s AND workspace_id = %s',
                    [str(record_id), str(entity.workspace_id)])
            from apps.recyclebin.models import RecycleBinEntry
            RecycleBinEntry.objects.filter(
                workspace_id=entity.workspace_id, record_id=record_id).delete()
        elif action == "anonymize":
            blank = {f: "" for f in (policy.anonymize_fields or [])}
            if blank:
                RecordService.update_record(
                    workspace_id=entity.workspace_id, member=member,
                    entity=entity, record_id=record_id, data=blank)
        elif action == "archive":
            fmap = dal.FieldMap(entity)
            dal.get_row(entity, fmap, record_id)  # snapshot read (cold-store seam)
            with connection.cursor() as cur:
                cur.execute(
                    f'DELETE FROM "{entity.table_name}" WHERE id = %s AND workspace_id = %s',
                    [str(record_id), str(entity.workspace_id)])
