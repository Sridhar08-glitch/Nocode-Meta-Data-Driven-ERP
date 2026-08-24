"""PublicFormService + API (PROJECT_HANDBOOK.md §33.1 / §33.2 / §33.6)."""
import pytest
from django.core.cache import cache

from apps.public_forms.models import FormSubmission
from apps.public_forms.services import PublicFormService, _spam_score

BASE = "/api/v1/public-forms"


class TestSpamScore:
    def test_all_caps_and_repeats_scores_over_half(self):
        assert _spam_score({"message": "AAAAAAAA BUY NOW CHEAP"}) > 0.5

    def test_clean_text_scores_zero(self):
        assert _spam_score({"message": "Hello, I would like more info."}) == 0.0


@pytest.mark.django_db
class TestPublicFormService:
    def test_honeypot_silent_spam_no_record(self, ws, form):
        sub = PublicFormService.submit(
            form_id=form.id, raw_data={"name": "Bot"}, honeypot_value="gotcha")
        assert sub.honeypot_triggered is True
        assert sub.status == "spam"
        assert sub.created_record_id is None

    def test_missing_required_field_rejected_no_record(self, ws, form, lead):
        sub = PublicFormService.submit(form_id=form.id, raw_data={"message": "hi"})
        assert sub.status == "rejected"
        assert any(e["field"] == "name" for e in sub.validation_errors)
        assert sub.created_record_id is None

    def test_valid_submission_creates_record(self, ws, form, lead):
        sub = PublicFormService.submit(
            form_id=form.id, raw_data={"name": "Jane", "message": "Interested"})
        assert sub.status == "accepted"
        assert not sub.validation_errors
        assert sub.created_record_id is not None

    def test_needs_approval_holds_pending(self, ws, lead):
        from apps.metadata.models import FormDefinition
        f = FormDefinition.objects.create(
            workspace_id=ws.id, entity_id=lead.id, name="Gated", is_public=True,
            settings={"needs_approval": True})
        sub = PublicFormService.submit(form_id=f.id, raw_data={"name": "Jane"})
        assert sub.status == "pending"
        assert sub.created_record_id is None

    def test_private_form_rejected(self, ws, lead):
        from apps.metadata.models import FormDefinition
        from apps.public_forms.services import PublicFormError
        f = FormDefinition.objects.create(
            workspace_id=ws.id, entity_id=lead.id, name="Private", is_public=False)
        with pytest.raises(PublicFormError):
            PublicFormService.submit(form_id=f.id, raw_data={"name": "x"})

    def test_approve_pending_creates_record(self, ws, lead):
        from apps.metadata.models import FormDefinition
        f = FormDefinition.objects.create(
            workspace_id=ws.id, entity_id=lead.id, name="Gated", is_public=True,
            settings={"needs_approval": True})
        sub = PublicFormService.submit(form_id=f.id, raw_data={"name": "Jane"})
        out = PublicFormService.approve_submission(sub.id, ws.id)
        assert out.status == "accepted"
        assert out.created_record_id is not None

    def test_reject_sets_status(self, ws, form):
        sub = PublicFormService.submit(form_id=form.id, raw_data={"name": "Jane"})
        out = PublicFormService.reject_submission(sub.id, ws.id, reason="dup")
        assert out.status == "rejected" and out.rejection_reason == "dup"


@pytest.mark.django_db
class TestPublicSubmitEndpoint:
    def test_submit_anonymous_returns_success(self, client, form):
        from rest_framework.test import APIClient
        anon = APIClient()
        r = anon.post(f"{BASE}/{form.id}/submit/", {"name": "Jane"}, format="json")
        assert r.status_code == 200 and r.json()["success"] is True
        assert FormSubmission.objects.filter(form_id=form.id, status="accepted").exists()

    def test_honeypot_via_endpoint(self, form):
        from rest_framework.test import APIClient
        anon = APIClient()
        r = anon.post(f"{BASE}/{form.id}/submit/",
                      {"name": "Bot", "_hp": "x"}, format="json")
        assert r.status_code == 200
        assert FormSubmission.objects.get(form_id=form.id).honeypot_triggered is True

    def test_rate_limit_returns_429(self, form):
        from rest_framework.test import APIClient
        cache.clear()
        anon = APIClient()
        for _ in range(5):
            assert anon.post(f"{BASE}/{form.id}/submit/", {"name": "J"},
                             format="json").status_code == 200
        assert anon.post(f"{BASE}/{form.id}/submit/", {"name": "J"},
                         format="json").status_code == 429

    def test_unknown_form_silent_success(self):
        import uuid

        from rest_framework.test import APIClient
        cache.clear()
        anon = APIClient()
        r = anon.post(f"{BASE}/{uuid.uuid4()}/submit/", {"name": "J"}, format="json")
        assert r.status_code == 200 and r.json()["success"] is True


@pytest.mark.django_db
class TestFormAdminApi:
    def test_form_crud(self, client, lead):
        r = client.post(f"{BASE}/forms/",
                        {"entity": str(lead.id), "name": "Contact", "is_public": True},
                        format="json")
        assert r.status_code == 201
        fid = r.json()["id"]
        assert client.get(f"{BASE}/forms/").json()["results"]
        assert client.patch(f"{BASE}/forms/{fid}/", {"name": "Renamed"},
                            format="json").json()["name"] == "Renamed"
        assert client.delete(f"{BASE}/forms/{fid}/").status_code == 204

    def test_submission_list_and_review(self, client, form):
        sub = PublicFormService.submit(form_id=form.id, raw_data={"name": "Jane"})
        listing = client.get(f"{BASE}/forms/{form.id}/submissions/").json()
        assert listing["count"] == 1
        r = client.post(f"{BASE}/forms/{form.id}/submissions/{sub.id}/reject/",
                        {"reason": "spam"}, format="json")
        assert r.status_code == 200 and r.json()["status"] == "rejected"

    def test_other_workspace_cannot_see_form(self, client, form):
        from rest_framework.test import APIClient

        from apps.accounts import tokens
        from apps.accounts.models import User
        from apps.public_forms.tests.conftest import PW
        from apps.tenancy.models import Workspace, WorkspaceMember
        other = Workspace.objects.create(name="Other", slug="other", is_active=True)
        u = User.objects.create_user(email="o@o.com", password=PW, is_verified=True)
        WorkspaceMember.objects.create(workspace=other, user=u, role="admin", status="active")
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(u)}",
                      HTTP_X_WORKSPACE_SLUG=other.slug)
        assert c.get(f"{BASE}/forms/{form.id}/").status_code == 404


@pytest.mark.django_db
class TestPublicSchemaEndpoint:
    def test_public_schema_returned_for_public_form(self, form, lead):
        from rest_framework.test import APIClient
        anon = APIClient()  # unauthenticated
        r = anon.get(f"{BASE}/{form.id}/schema/")
        assert r.status_code == 200
        assert r.data["entity_slug"] == "lead"
        assert r.data["honeypot_field"] == "_hp"
        assert "schema" in r.data and "sections" in r.data["schema"]

    def test_private_form_schema_404(self, ws, lead):
        from rest_framework.test import APIClient

        from apps.metadata.models import FormDefinition
        priv = FormDefinition.objects.create(
            workspace_id=ws.id, entity_id=lead.id, name="Private", is_public=False, layout=[], settings={})
        anon = APIClient()
        assert anon.get(f"{BASE}/{priv.id}/schema/").status_code == 404
