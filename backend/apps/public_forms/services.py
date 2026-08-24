"""
PublicFormService (PROJECT_HANDBOOK.md §33.1).

Handles external form submissions: honeypot detection, a simple spam heuristic,
required-field validation, optional record creation, and form-submitted workflow
dispatch. Form layouts live in ``metadata.FormDefinition``; this app owns
``FormSubmission`` and the public endpoint.
"""
from __future__ import annotations

import re
import uuid

from django.utils import timezone

from apps.eventstore.events import DomainEventData, DomainEventFactory
from apps.metadata.models import FormDefinition

from .models import FormSubmission

_URL_RE = re.compile(r"https?://", re.IGNORECASE)


class PublicFormError(Exception):  # noqa: N818 — domain error
    pass


def _emit(submission, event_type, payload):
    DomainEventFactory.persist_one(DomainEventData(
        event_type=event_type, workspace_id=submission.workspace_id,
        aggregate_type="form_submission", aggregate_id=submission.id, version=1,
        payload=payload, actor_id=uuid.UUID(int=0)))


def _spam_score(data: dict) -> float:
    """Heuristic 0.0–1.0: all-caps, repeated chars, suspicious URLs."""
    text = " ".join(str(v) for v in (data or {}).values() if v)
    if not text:
        return 0.0
    score = 0.0
    letters = [c for c in text if c.isalpha()]
    if letters and sum(1 for c in letters if c.isupper()) / len(letters) > 0.7:
        score += 0.5
    if re.search(r"(.)\1{5,}", text):
        score += 0.3
    if len(_URL_RE.findall(text)) >= 3:
        score += 0.4
    return min(score, 1.0)


def _system_member(workspace_id):
    from apps.workflows.executors import SystemMember
    sid = uuid.UUID(int=0)
    return SystemMember(user_id=sid, id=sid)


class PublicFormService:
    @staticmethod
    def submit(form_id, raw_data, submitter_ip=None, honeypot_value="",
               portal_user_id=None, submitter_name="", submitter_email="") -> FormSubmission:
        form = FormDefinition.objects.filter(id=form_id).first()
        if form is None or not form.is_public:
            raise PublicFormError("Form not found or not public")
        settings = form.settings or {}
        needs_approval = bool(settings.get("needs_approval"))

        # honeypot: accept silently, mark as spam, never create a record
        if honeypot_value:
            sub = FormSubmission.objects.create(
                form_id=form.id, workspace_id=form.workspace_id, entity_id=form.entity_id,
                status="spam", data=raw_data or {}, honeypot_triggered=True, spam_score=1.0,
                submitter_ip=submitter_ip, submitter_name=submitter_name[:255],
                submitter_email=submitter_email[:254], portal_user_id=portal_user_id)
            return sub

        score = _spam_score(raw_data)
        errors = PublicFormService._validate(form, raw_data)
        status = "rejected" if errors else ("pending" if needs_approval else "accepted")
        sub = FormSubmission.objects.create(
            form_id=form.id, workspace_id=form.workspace_id, entity_id=form.entity_id,
            status=status, data=raw_data or {}, spam_score=score,
            validation_errors=errors, submitter_ip=submitter_ip,
            submitter_name=submitter_name[:255], submitter_email=submitter_email[:254],
            portal_user_id=portal_user_id)
        _emit(sub, "form.submitted", {"form_id": str(form.id), "status": status})
        if status == "accepted" and not errors:
            PublicFormService._create_record(form, sub)
            PublicFormService._dispatch_workflows(form, sub)
        return sub

    @staticmethod
    def _validate(form, raw_data) -> list:
        from apps.records import dal
        from apps.records.services import resolve_entity
        errors = []
        try:
            entity = resolve_entity(form.workspace_id, form.entity.slug)
        except Exception:  # noqa: BLE001
            return errors
        fmap = dal.FieldMap(entity)
        for slug, fd in fmap.fields.items():
            if fd.is_required and not fd.is_system and not (raw_data or {}).get(slug):
                errors.append({"field": slug, "message": "required"})
        return errors

    @staticmethod
    def _create_record(form, submission):
        from apps.records.services import RecordService, resolve_entity
        try:
            entity = resolve_entity(form.workspace_id, form.entity.slug)
            fmap_fields = {fd.slug for fd in entity.fields.filter(is_deleted=False)}
            data = {k: v for k, v in (submission.data or {}).items() if k in fmap_fields}
            rec = RecordService.create_record(
                workspace_id=form.workspace_id, member=_system_member(form.workspace_id),
                entity=entity, data=data)
            submission.created_record_id = rec.get("id")
            submission.save(update_fields=["created_record_id"])
        except Exception:  # noqa: BLE001 — record creation failure must not 500 the public endpoint
            pass

    @staticmethod
    def _dispatch_workflows(form, submission):
        try:
            from apps.workflows.dispatcher import run_record_event
            run_record_event(
                event_type="form_submitted", entity_slug=form.entity.slug,
                entity_id=form.entity_id, record_id=submission.created_record_id or submission.id,
                record={"entity_slug": form.entity.slug, **(submission.data or {})},
                workspace_id=form.workspace_id)
        except Exception:  # noqa: BLE001
            pass

    @staticmethod
    def approve_submission(submission_id, actor_id) -> FormSubmission:
        sub = FormSubmission.objects.filter(id=submission_id).first()
        if sub is None:
            raise PublicFormError("Submission not found")
        sub.status = "accepted"
        sub.reviewed_by = actor_id
        sub.reviewed_at = timezone.now()
        sub.save(update_fields=["status", "reviewed_by", "reviewed_at"])
        form = FormDefinition.objects.filter(id=sub.form_id).first()
        if form and not sub.created_record_id:
            PublicFormService._create_record(form, sub)
        return sub

    @staticmethod
    def reject_submission(submission_id, actor_id, reason="") -> FormSubmission:
        sub = FormSubmission.objects.filter(id=submission_id).first()
        if sub is None:
            raise PublicFormError("Submission not found")
        sub.status = "rejected"
        sub.reviewed_by = actor_id
        sub.reviewed_at = timezone.now()
        sub.rejection_reason = reason[:500]
        sub.save(update_fields=["status", "reviewed_by", "reviewed_at", "rejection_reason"])
        return sub
