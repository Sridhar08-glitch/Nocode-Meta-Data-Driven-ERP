"""
Document async tasks (PROJECT_HANDBOOK.md §24.3).

AV scanning is always asynchronous and never blocks upload. If ClamAV (pyclamd)
is unavailable the scan is recorded as ``skipped``; an infected file is
quarantined (soft-deleted) and the uploader is notified.
"""
from __future__ import annotations

from django.utils import timezone

from celery import shared_task

from .models import Document


def _av_scan(data: bytes) -> str:
    """Return "clean" | "infected" | "skipped". ClamAV via pyclamd when available."""
    try:
        import pyclamd
    except Exception:  # noqa: BLE001 — pyclamd not installed → scanning unavailable
        return "skipped"
    try:
        cd = pyclamd.ClamdUnixSocket()
        if not cd.ping():
            return "skipped"
        result = cd.scan_stream(data)
    except Exception:  # noqa: BLE001 — daemon unreachable
        return "skipped"
    return "infected" if result else "clean"


@shared_task(name="documents.scan_document_av")
def scan_document_av(document_id: str) -> str:
    doc = Document.objects.filter(id=document_id).first()
    if doc is None:
        return "missing"
    from .storage import get_storage_backend
    try:
        data = get_storage_backend(doc.workspace_id).download(doc.storage_key)
    except Exception:  # noqa: BLE001
        data = b""
    verdict = _av_scan(data)
    doc.av_scanned_at = timezone.now()
    if verdict == "clean":
        doc.av_clean = True
        doc.status = "ready"
        doc.save(update_fields=["av_clean", "status", "av_scanned_at"])
    elif verdict == "infected":
        doc.av_clean = False
        doc.status = "quarantined"
        doc.save(update_fields=["av_clean", "status", "av_scanned_at"])
        doc.soft_delete(None)
        _notify_uploader(doc)
    else:  # skipped
        doc.av_clean = None
        doc.save(update_fields=["av_clean", "av_scanned_at"])
    return verdict


def _notify_uploader(doc) -> None:
    if not doc.created_by:
        return
    try:
        from apps.notifications.services import NotificationService
    except Exception:  # noqa: BLE001
        return
    NotificationService.send(
        recipient_id=doc.created_by, recipient_type="member",
        template_slug="document_quarantined",
        context={"event_type": "document_quarantined", "subject": "File quarantined",
                 "body": f"Your upload '{doc.name}' failed an antivirus scan and was removed."},
        workspace_id=doc.workspace_id, channels=["in_app"])
