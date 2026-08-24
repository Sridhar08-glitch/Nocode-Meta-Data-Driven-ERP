"""AV scan task (PROJECT_HANDBOOK.md §24.3 / §24.5)."""
import pytest

from apps.documents import tasks
from apps.documents.services import DocumentService
from apps.notifications.models import Notification


def _doc(ws, user):
    return DocumentService.upload_document(
        file_obj=b"data", filename="a.txt", uploaded_by=user.id, workspace_id=ws.id)


@pytest.mark.django_db
class TestAvScan:
    def test_clean(self, ws, user, monkeypatch):
        monkeypatch.setattr(tasks, "_av_scan", lambda data: "clean")
        doc = _doc(ws, user)
        tasks.scan_document_av(str(doc.id))
        doc.refresh_from_db()
        assert doc.av_clean is True
        assert doc.status == "ready"
        assert doc.av_scanned_at is not None

    def test_infected_quarantines_and_notifies(self, ws, user, monkeypatch):
        monkeypatch.setattr(tasks, "_av_scan", lambda data: "infected")
        doc = _doc(ws, user)
        tasks.scan_document_av(str(doc.id))
        doc.refresh_from_db()
        assert doc.av_clean is False
        assert doc.status == "quarantined"
        assert doc.is_deleted
        assert Notification.objects.filter(
            workspace_id=ws.id, recipient_id=user.id).exists()

    def test_skipped_when_no_scanner(self, ws, user):
        # pyclamd is not installed → _av_scan returns "skipped"
        doc = _doc(ws, user)
        assert tasks.scan_document_av(str(doc.id)) == "skipped"
        doc.refresh_from_db()
        assert doc.av_clean is None
        assert not doc.is_deleted
