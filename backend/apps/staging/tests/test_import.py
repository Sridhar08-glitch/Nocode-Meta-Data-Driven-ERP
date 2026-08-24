"""Import pipeline (PROJECT_HANDBOOK.md §29.1 / §29.4)."""
import pytest

from apps.records.services import RecordService, resolve_entity
from apps.staging.models import ImportRow
from apps.staging.services import ImportError, ImportService

from .conftest import csv_file, xlsx_file


def _count(ws, slug, member):
    entity = resolve_entity(ws.id, slug)
    return len(RecordService.list_records(workspace_id=ws.id, member=member, entity=entity))


@pytest.mark.django_db
class TestParse:
    def test_csv_parse_creates_rows_and_mapping(self, ws, member, lead):
        job = ImportService.create_job(
            entity_slug="lead", file_obj=csv_file("name,value\nAlice,10\nBob,20\n"),
            filename="data.csv", initiated_by=member.user_id, workspace_id=ws.id)
        job.refresh_from_db()
        assert job.total_rows == 2
        assert job.column_mapping["name"] == "name"   # auto-mapped by header
        assert ImportRow.objects.filter(job_id=job.id).count() == 2
        assert job.status == "awaiting_confirm"
        assert job.valid_rows == 2

    def test_xlsx_parse(self, ws, member, lead):
        job = ImportService.create_job(
            entity_slug="lead",
            file_obj=xlsx_file([["name", "value"], ["Carol", 5], ["Dan", 7]]),
            filename="data.xlsx", initiated_by=member.user_id, workspace_id=ws.id)
        job.refresh_from_db()
        assert job.total_rows == 2
        assert job.valid_rows == 2


@pytest.mark.django_db
class TestValidation:
    def test_required_missing_is_invalid(self, ws, member, lead):
        job = ImportService.create_job(
            entity_slug="lead", file_obj=csv_file("name,value\n,10\nBob,20\n"),
            filename="d.csv", initiated_by=member.user_id, workspace_id=ws.id)
        job.refresh_from_db()
        assert job.valid_rows == 1 and job.invalid_rows == 1
        bad = ImportRow.objects.get(job_id=job.id, row_number=1)
        assert bad.status == "invalid"
        assert any(e["field"] == "name" for e in bad.validation_errors)

    def test_set_mapping_unknown_field_rejected(self, ws, member, lead):
        job = ImportService.create_job(
            entity_slug="lead", file_obj=csv_file("a,b\n1,2\n"), filename="d.csv",
            initiated_by=member.user_id, workspace_id=ws.id)
        with pytest.raises(ImportError):
            ImportService.set_column_mapping(job.id, {"a": "nonexistent"})


@pytest.mark.django_db
class TestExecute:
    def test_import_creates_records(self, ws, member, lead):
        job = ImportService.create_job(
            entity_slug="lead", file_obj=csv_file("name,value\nAlice,10\nBob,20\n"),
            filename="d.csv", initiated_by=member.user_id, workspace_id=ws.id)
        ImportService.confirm_import(job.id, member.user_id)
        job.refresh_from_db()
        assert job.status == "completed"
        assert job.imported_rows == 2
        assert _count(ws, "lead", member) == 2

    def test_duplicate_skip(self, ws, member, lead):
        RecordService.create_record(workspace_id=ws.id, member=member,
                                    entity=lead, data={"name": "Alice", "value": 1})
        job = ImportService.create_job(
            entity_slug="lead", file_obj=csv_file("name,value\nAlice,99\nBob,5\n"),
            filename="d.csv", initiated_by=member.user_id, workspace_id=ws.id,
            duplicate_strategy="skip", match_field_slug="name")
        ImportService.confirm_import(job.id, member.user_id)
        job.refresh_from_db()
        assert job.skipped_rows == 1 and job.imported_rows == 1
        # Alice not overwritten
        entity = resolve_entity(ws.id, "lead")
        rows = RecordService.list_records(workspace_id=ws.id, member=member, entity=entity,
                                          filter_source={"field": "name", "op": "=",
                                                         "value": "Alice"})
        assert str(rows[0]["value"]) in ("1", "1.0")

    def test_duplicate_update(self, ws, member, lead):
        RecordService.create_record(workspace_id=ws.id, member=member,
                                    entity=lead, data={"name": "Alice", "value": 1})
        job = ImportService.create_job(
            entity_slug="lead", file_obj=csv_file("name,value\nAlice,99\n"),
            filename="d.csv", initiated_by=member.user_id, workspace_id=ws.id,
            duplicate_strategy="update", match_field_slug="name")
        ImportService.confirm_import(job.id, member.user_id)
        entity = resolve_entity(ws.id, "lead")
        rows = RecordService.list_records(workspace_id=ws.id, member=member, entity=entity,
                                          filter_source={"field": "name", "op": "=",
                                                         "value": "Alice"})
        assert str(rows[0]["value"]) in ("99", "99.0")

    def test_partial_success_recorded(self, ws, member, lead):
        # one valid, one invalid (missing name) → import only the valid one
        job = ImportService.create_job(
            entity_slug="lead", file_obj=csv_file("name,value\nAlice,10\n,20\n"),
            filename="d.csv", initiated_by=member.user_id, workspace_id=ws.id)
        ImportService.confirm_import(job.id, member.user_id)
        job.refresh_from_db()
        assert job.imported_rows == 1
        assert job.invalid_rows == 1


@pytest.mark.django_db
class TestIsolation:
    def test_cannot_import_into_unknown_entity(self, ws, member):
        with pytest.raises(ImportError):
            ImportService.create_job(
                entity_slug="ghost", file_obj=csv_file("a\n1\n"), filename="d.csv",
                initiated_by=member.user_id, workspace_id=ws.id)
