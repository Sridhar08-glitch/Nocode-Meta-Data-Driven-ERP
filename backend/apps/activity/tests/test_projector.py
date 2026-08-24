"""ActivityProjector + field diff (PROJECT_HANDBOOK.md §23.1 / §23.4)."""
import pytest

from apps.activity.models import ActivityEntry
from apps.activity.projectors import (
    EVENT_ACTIVITY_MAP,
    project_activity,
    project_field_diff,
)


class TestFieldDiff:
    def test_only_changed_fields(self):
        diff = project_field_diff(
            {"status": "open", "name": "A"}, {"status": "closed", "name": "A"},
            [{"slug": "status", "label": "Status"}, {"slug": "name", "label": "Name"}])
        assert "status" in diff
        assert "name" not in diff
        assert diff["status"]["before"] == "open"
        assert diff["status"]["after"] == "closed"

    def test_pii_masked(self):
        diff = project_field_diff(
            {"ssn": "111-22-3333"}, {"ssn": "999-88-7777"},
            [{"slug": "ssn", "label": "SSN", "is_pii": True}])
        assert diff["ssn"]["before"] == "***"
        assert diff["ssn"]["after"] == "***"


@pytest.mark.django_db
class TestProjector:
    def test_all_mapped_event_types_create_entries(self, ws, lead, make_event):
        for event_type, activity_type in EVENT_ACTIVITY_MAP.items():
            ev = make_event(event_type, entity_id=lead.id)
            project_activity(ev)
            assert ActivityEntry.objects.filter(
                event_id=ev.id, activity_type=activity_type).exists(), event_type

    def test_idempotent_on_event(self, ws, lead, make_event):
        ev = make_event("record.created", entity_id=lead.id)
        project_activity(ev)
        project_activity(ev)
        assert ActivityEntry.objects.filter(event_id=ev.id).count() == 1

    def test_unmapped_event_skipped(self, ws, lead, make_event):
        ev = make_event("workflow.step.completed", entity_id=lead.id)
        project_activity(ev)
        assert ActivityEntry.objects.filter(event_id=ev.id).count() == 0

    def test_unresolvable_record_skipped(self, ws, make_event):
        # no entity_id and no entity_slug match → cannot place on a timeline
        ev = make_event("record.created", entity_slug="", aggregate_type="other")
        project_activity(ev)
        assert ActivityEntry.objects.filter(event_id=ev.id).count() == 0

    def test_record_updated_builds_changes(self, ws, lead, make_event):
        ev = make_event("record.updated", entity_id=lead.id,
                        payload={"data": {"status": "won"}})
        project_activity(ev)
        entry = ActivityEntry.objects.get(event_id=ev.id)
        assert entry.activity_type == "record_updated"
        assert any(c["field_slug"] == "status" and c["new"] == "won"
                   for c in entry.changes)

    def test_actor_name_snapshot(self, ws, lead, user, make_event):
        ev = make_event("record.created", entity_id=lead.id, actor_id=user.id)
        project_activity(ev)
        assert ActivityEntry.objects.get(event_id=ev.id).actor_name == "Ada Lovelace"
