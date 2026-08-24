"""BackupService / RetentionService + API (PROJECT_HANDBOOK.md §33.3–§33.6)."""
import json
import uuid

import pytest
from django.db import connection

from apps.accounts.crypto import get_fernet, hash_token
from apps.backups.models import BackupJob, DataRetentionPolicy
from apps.backups.services import BackupError, BackupService, RetentionService
from apps.documents.storage import get_storage_backend
from apps.eventstore.models import DomainEvent
from apps.nql.services import execute_nql
from apps.records.services import RecordService

BASE = "/api/v1/backups"


@pytest.mark.django_db
class TestBackup:
    def test_execute_backup_encrypts_and_checksums(self, ws, lead, member):
        RecordService.create_record(workspace_id=ws.id, member=member, entity=lead,
                                    data={"name": "Jane", "email": "j@x.com"})
        job = BackupService.create_backup_job(
            workspace_id=ws.id, backup_type="full", initiated_by=member.user_id)
        assert job.status == "completed"
        assert job.checksum_sha256 and job.record_count == 1
        # stored bytes are encrypted (not plaintext JSON) but decrypt back to the payload
        blob = get_storage_backend(ws.id).download(job.storage_key)
        assert b'"schema_version"' not in blob
        payload = json.loads(get_fernet().decrypt(blob).decode())
        assert payload["workspace_id"] == str(ws.id)
        import hashlib
        assert hashlib.sha256(get_fernet().decrypt(blob)).hexdigest() == job.checksum_sha256

    def test_config_only_skips_records(self, ws, lead, member):
        RecordService.create_record(workspace_id=ws.id, member=member, entity=lead,
                                    data={"name": "Jane"})
        job = BackupService.create_backup_job(
            workspace_id=ws.id, backup_type="config_only", initiated_by=member.user_id)
        assert job.status == "completed" and job.record_count == 0


@pytest.mark.django_db
class TestRestoreTokens:
    def test_target_equals_source_rejected(self, ws):
        with pytest.raises(BackupError):
            BackupService.create_restore_job(
                workspace_id=ws.id, restore_type="pitr", target_workspace_id=ws.id,
                target_workspace_slug="acme", initiated_by=ws.id)

    def test_token_hash_stored_plaintext_returned_once(self, ws, target_ws):
        job, token = BackupService.create_restore_job(
            workspace_id=ws.id, restore_type="pitr", target_workspace_id=target_ws.id,
            target_workspace_slug=target_ws.slug, initiated_by=ws.id)
        assert job.confirmation_token_hash == hash_token(token)
        assert job.confirmation_token_hash != token  # raw token never stored

    def test_confirm_wrong_token_rejected(self, ws, target_ws):
        job, _ = BackupService.create_restore_job(
            workspace_id=ws.id, restore_type="pitr", target_workspace_id=target_ws.id,
            target_workspace_slug=target_ws.slug, initiated_by=ws.id)
        with pytest.raises(BackupError):
            BackupService.confirm_restore(job.id, "wrong-token")

    def test_confirm_correct_token_dispatches(self, ws, target_ws):
        job, token = BackupService.create_restore_job(
            workspace_id=ws.id, restore_type="pitr", target_workspace_id=target_ws.id,
            target_workspace_slug=target_ws.slug, initiated_by=ws.id)
        out = BackupService.confirm_restore(job.id, token)
        assert out.confirmed_at is not None
        assert out.status in ("completed", "running")  # ran eagerly


@pytest.mark.django_db
class TestPITR:
    def test_pitr_replays_up_to_sequence(self, ws, lead, target_ws, member):
        r1 = RecordService.create_record(workspace_id=ws.id, member=member, entity=lead,
                                         data={"name": "First", "email": "1@x.com"})
        seq1 = DomainEvent.objects.filter(
            workspace_id=ws.id, aggregate_type="record",
            aggregate_id=r1["id"]).order_by("-global_sequence").first().global_sequence
        RecordService.create_record(workspace_id=ws.id, member=member, entity=lead,
                                    data={"name": "Second", "email": "2@x.com"})

        job, token = BackupService.create_restore_job(
            workspace_id=ws.id, restore_type="pitr", target_workspace_id=target_ws.id,
            target_workspace_slug=target_ws.slug, initiated_by=member.user_id,
            pitr_target_sequence=seq1)
        out = BackupService.confirm_restore(job.id, token)
        assert out.status == "completed"

        rows = execute_nql(workspace_id=target_ws.id, source={"entity": "lead"},
                           user_id=uuid.UUID(int=0))
        names = {r.get("name") for r in rows}
        assert names == {"First"}  # only events up to seq1 replayed


@pytest.mark.django_db
class TestRetention:
    def test_anonymize_blanks_only_listed_fields(self, ws, lead, member):
        rec = RecordService.create_record(workspace_id=ws.id, member=member, entity=lead,
                                          data={"name": "Jane", "email": "secret@x.com"})
        # age the record well past the retention window
        with connection.cursor() as cur:
            cur.execute(f'UPDATE "{lead.table_name}" SET created_at = %s WHERE id = %s',
                        ["2000-01-01T00:00:00+00:00", rec["id"]])
        policy = DataRetentionPolicy.objects.create(
            workspace_id=ws.id, entity_id=lead.id, entity_slug="lead", retain_days=30,
            action="anonymize", anonymize_fields=["email"], is_active=True)
        affected = RetentionService.enforce(policy)
        assert affected == 1
        out = RecordService.retrieve_record(workspace_id=ws.id, member=member,
                                            entity=lead, record_id=rec["id"])
        assert out["email"] in ("", None)       # listed field blanked
        assert out["name"] == "Jane"            # unlisted field preserved

    def test_fresh_records_untouched(self, ws, lead, member):
        rec = RecordService.create_record(workspace_id=ws.id, member=member, entity=lead,
                                          data={"name": "Fresh", "email": "f@x.com"})
        policy = DataRetentionPolicy.objects.create(
            workspace_id=ws.id, entity_id=lead.id, entity_slug="lead", retain_days=30,
            action="hard_delete", is_active=True)
        assert RetentionService.enforce(policy) == 0
        out = RecordService.retrieve_record(workspace_id=ws.id, member=member,
                                            entity=lead, record_id=rec["id"])
        assert out["name"] == "Fresh"

    def test_soft_delete_action(self, ws, lead, member):
        rec = RecordService.create_record(workspace_id=ws.id, member=member, entity=lead,
                                          data={"name": "Old"})
        with connection.cursor() as cur:
            cur.execute(f'UPDATE "{lead.table_name}" SET created_at = %s WHERE id = %s',
                        ["2000-01-01T00:00:00+00:00", rec["id"]])
        policy = DataRetentionPolicy.objects.create(
            workspace_id=ws.id, entity_id=lead.id, entity_slug="lead", retain_days=1,
            action="soft_delete", is_active=True)
        assert RetentionService.enforce(policy) == 1
        rows = execute_nql(workspace_id=ws.id, source={"entity": "lead"}, user_id=uuid.UUID(int=0))
        assert all(r["id"] != rec["id"] for r in rows)


@pytest.mark.django_db
class TestExpireBackups:
    def test_expire_old_backups_deletes_file(self, ws, lead, member):
        from datetime import timedelta

        from django.utils import timezone

        from apps.backups.tasks import expire_old_backups
        job = BackupService.create_backup_job(workspace_id=ws.id, initiated_by=member.user_id)
        key = job.storage_key
        assert get_storage_backend(ws.id).exists(key)
        BackupJob.objects.filter(id=job.id).update(
            expires_at=timezone.now() - timedelta(days=1))
        expire_old_backups()
        job.refresh_from_db()
        assert job.status == "expired"
        assert not get_storage_backend(ws.id).exists(key)


@pytest.mark.django_db
class TestBackupApi:
    def test_create_and_list_backup(self, client, lead, member):
        r = client.post(f"{BASE}/jobs/", {"backup_type": "config_only"}, format="json")
        assert r.status_code == 201
        body = r.json()
        assert "storage_key" not in body  # artifact key never exposed
        assert client.get(f"{BASE}/jobs/").json()["results"]

    def test_restore_job_flow_exposes_token_once(self, client, ws, target_ws):
        r = client.post(f"{BASE}/restore-jobs/",
                        {"restore_type": "pitr", "target_workspace_id": str(target_ws.id),
                         "target_workspace_slug": target_ws.slug}, format="json")
        assert r.status_code == 201
        token = r.json()["confirmation_token"]
        rid = r.json()["id"]
        # detail must never re-expose the token
        detail = client.get(f"{BASE}/restore-jobs/{rid}/").json()
        assert "confirmation_token" not in detail
        # wrong token rejected, right token accepted
        assert client.post(f"{BASE}/restore-jobs/{rid}/confirm/",
                           {"token": "nope"}, format="json").status_code == 400
        ok = client.post(f"{BASE}/restore-jobs/{rid}/confirm/",
                         {"token": token}, format="json")
        assert ok.status_code == 200

    def test_restore_into_self_rejected(self, client, ws):
        r = client.post(f"{BASE}/restore-jobs/",
                        {"restore_type": "pitr", "target_workspace_id": str(ws.id),
                         "target_workspace_slug": ws.slug}, format="json")
        assert r.status_code == 400

    def test_retention_policy_crud(self, client, lead):
        r = client.post(f"{BASE}/retention-policies/",
                        {"entity_id": str(lead.id), "entity_slug": "lead", "retain_days": 90,
                         "action": "soft_delete"}, format="json")
        assert r.status_code == 201
        pid = r.json()["id"]
        assert client.patch(f"{BASE}/retention-policies/{pid}/",
                            {"retain_days": 30}, format="json").json()["retain_days"] == 30
        assert client.delete(f"{BASE}/retention-policies/{pid}/").status_code == 204

    def test_non_admin_cannot_backup(self, ws, target_ws):
        from rest_framework.test import APIClient

        from apps.accounts import tokens
        from apps.accounts.models import User
        from apps.tenancy.models import WorkspaceMember
        u = User.objects.create_user(email="v@x.com", password="Sup3rStr0ng!pw", is_verified=True)
        WorkspaceMember.objects.create(workspace=ws, user=u, role="viewer", status="active")
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(u)}",
                      HTTP_X_WORKSPACE_SLUG=ws.slug)
        assert c.post(f"{BASE}/jobs/", {"backup_type": "full"}, format="json").status_code == 403
