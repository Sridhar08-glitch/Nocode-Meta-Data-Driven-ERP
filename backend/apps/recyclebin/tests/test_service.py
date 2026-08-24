"""RecycleBinService (PROJECT_HANDBOOK.md §31.1 / §31.5)."""
import datetime as dt

import pytest
from django.utils import timezone

from apps.records import dal
from apps.records.services import RecordNotFound, RecordService, resolve_entity
from apps.recyclebin.models import RecycleBinEntry
from apps.recyclebin.services import RETENTION_DAYS, RecycleBinService


@pytest.mark.django_db
class TestSoftDeleteHook:
    def test_delete_creates_entry_with_purge_after(self, ws, deleted_record):
        rid, entry = deleted_record()
        assert entry.is_purged is False
        delta = entry.purge_after - entry.deleted_at
        assert abs(delta.days - RETENTION_DAYS) <= 1

    def test_cascade_entries_stored(self, ws, lead):
        import uuid
        child = uuid.uuid4()
        entry = RecycleBinService.on_record_deleted(
            record_id=uuid.uuid4(), entity_id=lead.id, entity_slug="lead",
            record_title="P", workspace_id=ws.id,
            cascade_entries=[{"entity_slug": "lead", "record_id": str(child)}])
        assert entry.cascade_entries[0]["record_id"] == str(child)


@pytest.mark.django_db
class TestRestore:
    def test_restore_clears_deleted_at(self, ws, member, lead, deleted_record):
        rid, entry = deleted_record()
        # confirm it is soft-deleted (retrieve raises)
        with pytest.raises(RecordNotFound):
            RecordService.retrieve_record(workspace_id=ws.id, member=member, entity=lead,
                                          record_id=rid)
        RecycleBinService.restore(entry.id, member.user_id)
        rec = RecordService.retrieve_record(workspace_id=ws.id, member=member, entity=lead,
                                            record_id=rid)
        assert rec["id"] == rid
        assert not RecycleBinEntry.objects.filter(id=entry.id).exists()

    def test_restore_brings_back_children(self, ws, member, lead):
        parent = RecordService.create_record(workspace_id=ws.id, member=member, entity=lead,
                                             data={"name": "P"})
        child = RecordService.create_record(workspace_id=ws.id, member=member, entity=lead,
                                            data={"name": "C"})
        entity = resolve_entity(ws.id, "lead")
        dal.soft_delete_row(entity, parent["id"], actor_id=member.user_id)
        dal.soft_delete_row(entity, child["id"], actor_id=member.user_id)
        entry = RecycleBinService.on_record_deleted(
            record_id=parent["id"], entity_id=lead.id, entity_slug="lead",
            workspace_id=ws.id,
            cascade_entries=[{"entity_slug": "lead", "record_id": str(child["id"])}])
        RecycleBinService.restore(entry.id, member.user_id)
        # both parent and child are restored
        assert RecordService.retrieve_record(workspace_id=ws.id, member=member, entity=lead,
                                             record_id=child["id"])["id"] == child["id"]


@pytest.mark.django_db
class TestPurge:
    def test_purge_entry_hard_deletes(self, ws, member, lead, deleted_record):
        rid, entry = deleted_record()
        RecycleBinService.purge_entry(entry.id, member.user_id)
        entity = resolve_entity(ws.id, "lead")
        fmap = dal.FieldMap(entity)
        assert dal.get_row(entity, fmap, rid, include_deleted=True) is None
        entry.refresh_from_db()
        assert entry.is_purged and entry.purged_at is not None

    def test_purge_expired_only_past_due(self, ws, member, lead, deleted_record):
        rid1, e1 = deleted_record("A")
        rid2, e2 = deleted_record("B")
        RecycleBinEntry.objects.filter(id=e1.id).update(
            purge_after=timezone.now() - dt.timedelta(days=1))
        assert RecycleBinService.purge_expired() == 1
        e1.refresh_from_db()
        e2.refresh_from_db()
        assert e1.is_purged is True
        assert e2.is_purged is False
