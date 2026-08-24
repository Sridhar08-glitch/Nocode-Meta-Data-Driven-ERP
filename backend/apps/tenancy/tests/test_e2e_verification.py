"""
P2.17 zero-trust runtime verification of Workspace & Identity Administration.

NOT a code review — this drives the REAL HTTP API end to end (full middleware →
auth → permissions → serializers → services → DB), using real JWTs and real email
tokens read from the outbox (as a customer would from their inbox). No ORM is used
to *perform* any operation; ORM reads appear only to assert audit/event outcomes.

Runs identically on SQLite and PostgreSQL (`--ds=config.settings.test_pg`).
"""
import re

import pytest
from django.core import mail
from rest_framework.test import APIClient

from apps.eventstore.models import DomainEvent

OWNER_PW = "Sup3rStr0ng!pw"
HIRE_PW = "An0therStr0ng!pw"


def _token_from_last_email() -> str:
    assert mail.outbox, "expected an email to have been sent"
    body = mail.outbox[-1].body
    m = re.search(r"token=([A-Za-z0-9_\-]+)", body)
    assert m, f"no token in email body: {body!r}"
    return m.group(1)


def _bearer(access: str) -> APIClient:
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    return c


@pytest.mark.django_db
def test_full_customer_journey_through_the_real_api():
    """Visitor → … → ownership transfer, executed through HTTP only."""
    mail.outbox = []
    anon = APIClient()

    # 1. Register --------------------------------------------------------------
    r = anon.post("/api/v1/auth/register/",
                  {"email": "founder@acme.test", "password": OWNER_PW,
                   "full_name": "Founder"}, format="json")
    assert r.status_code == 201, r.data

    # 2. Verify email (token from the verification email) ----------------------
    r = anon.post("/api/v1/auth/verify-email/",
                  {"token": _token_from_last_email()}, format="json")
    assert r.status_code == 200, r.data

    # 3. Login -----------------------------------------------------------------
    r = anon.post("/api/v1/auth/login/",
                  {"email": "founder@acme.test", "password": OWNER_PW}, format="json")
    assert r.status_code == 200, r.data
    owner = _bearer(r.data["access"])

    # 4. Create workspace → become owner --------------------------------------
    r = owner.post("/api/v1/workspaces/", {"name": "Acme Manufacturing"}, format="json")
    assert r.status_code == 201, r.data
    slug = r.data["slug"]
    assert r.data["role"] == "owner"
    assert DomainEvent.objects.filter(
        aggregate_id=r.data["id"], event_type="workspace.created").exists()
    # it now appears in the membership listing
    assert any(w["slug"] == slug for w in owner.get("/api/v1/workspaces/").data)

    # 5. Install ERP (a seeded solution template) ------------------------------
    templates = anon.get("/api/v1/solution-templates/").data
    tpl = (templates[0] if isinstance(templates, list) and templates
           else (templates.get("results") or [None])[0] if isinstance(templates, dict) else None)
    if tpl:
        r = owner.post(f"/api/v1/solution-templates/{tpl['id']}/install/",
                       {}, format="json", HTTP_X_WORKSPACE_SLUG=slug)
        assert r.status_code in (200, 201), r.data
        installed = owner.get("/api/v1/solution-templates/installed/",
                              HTTP_X_WORKSPACE_SLUG=slug)
        assert installed.status_code == 200 and len(installed.data) >= 1

    # 6. Open dashboard (tenant health) ---------------------------------------
    r = owner.get("/api/v1/admin/health/", HTTP_X_WORKSPACE_SLUG=slug)
    assert r.status_code == 200, r.data

    # 7. Configure workspace ---------------------------------------------------
    r = owner.patch(f"/api/v1/workspaces/{slug}/",
                    {"name": "Acme Mfg", "plan": "pro"}, format="json")
    assert r.status_code == 200 and r.data["plan"] == "pro"

    # 8. Invite a user (creates the account + emails a set-password link) ------
    mail.outbox = []
    r = owner.post(f"/api/v1/workspaces/{slug}/members/",
                   {"email": "hire@acme.test", "full_name": "New Hire", "role": "member"},
                   format="json")
    assert r.status_code == 201 and r.data["created_user"] is True
    member_id = r.data["id"]

    # 9. Second user sets their password (the emailed link) -------------------
    set_token = _token_from_last_email()
    r = anon.post("/api/v1/auth/password-reset/confirm/",
                  {"token": set_token, "password": HIRE_PW}, format="json")
    assert r.status_code == 200, r.data

    # 10. Second user logs in --------------------------------------------------
    r = anon.post("/api/v1/auth/login/",
                  {"email": "hire@acme.test", "password": HIRE_PW}, format="json")
    assert r.status_code == 200, r.data
    hire = _bearer(r.data["access"])

    # 11. Second user switches into the workspace -----------------------------
    his = hire.get("/api/v1/workspaces/").data
    assert any(w["slug"] == slug and w["role"] == "member" for w in his)
    assert hire.get(f"/api/v1/workspaces/{slug}/members/").status_code == 200

    # 12. Owner assigns a role -------------------------------------------------
    r = owner.patch(f"/api/v1/workspaces/{slug}/members/{member_id}/",
                    {"role": "admin"}, format="json")
    assert r.status_code == 200 and r.data["role"] == "admin"

    # 13. Owner suspends the user → access denied immediately ------------------
    r = owner.post(f"/api/v1/workspaces/{slug}/members/{member_id}/suspend/")
    assert r.status_code == 200 and r.data["status"] == "suspended"
    assert hire.get(f"/api/v1/workspaces/{slug}/members/").status_code == 403
    assert all(w["slug"] != slug for w in hire.get("/api/v1/workspaces/").data)

    # 14. Owner reactivates → access restored ---------------------------------
    r = owner.post(f"/api/v1/workspaces/{slug}/members/{member_id}/reactivate/")
    assert r.status_code == 200 and r.data["status"] == "active"
    assert hire.get(f"/api/v1/workspaces/{slug}/members/").status_code == 200

    # 15. Owner transfers ownership -------------------------------------------
    r = owner.post(f"/api/v1/workspaces/{slug}/transfer-ownership/",
                   {"member_id": member_id}, format="json")
    assert r.status_code == 200 and r.data["role"] == "owner"

    # 16. Old owner is now admin; new owner manages ---------------------------
    members = hire.get(f"/api/v1/workspaces/{slug}/members/").data
    founder = next(m for m in members if m["email"] == "founder@acme.test")
    assert founder["role"] == "admin"
    # 17. Old owner CANNOT perform an owner-only action (transfer) ------------
    r = owner.post(f"/api/v1/workspaces/{slug}/transfer-ownership/",
                   {"member_id": founder["id"]}, format="json")
    assert r.status_code == 403
    # 18. New owner can administer the workspace ------------------------------
    assert hire.patch(f"/api/v1/workspaces/{slug}/",
                      {"plan": "enterprise"}, format="json").status_code == 200


@pytest.mark.django_db
class TestRuntimeSecurity:
    """Negative + security cases driven through real auth and HTTP."""

    def _register_login(self, email):
        anon = APIClient()
        mail.outbox = []
        anon.post("/api/v1/auth/register/",
                  {"email": email, "password": OWNER_PW, "full_name": email}, format="json")
        anon.post("/api/v1/auth/verify-email/",
                  {"token": _token_from_last_email()}, format="json")
        r = anon.post("/api/v1/auth/login/",
                      {"email": email, "password": OWNER_PW}, format="json")
        return _bearer(r.data["access"])

    def _owner_with_ws(self, email, name):
        c = self._register_login(email)
        slug = c.post("/api/v1/workspaces/", {"name": name}, format="json").data["slug"]
        return c, slug

    def test_create_requires_auth(self):
        assert APIClient().post("/api/v1/workspaces/",
                                {"name": "x"}, format="json").status_code in (401, 403)

    def test_invalid_bearer_rejected(self):
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION="Bearer not.a.real.token")
        assert c.get("/api/v1/workspaces/").status_code == 401

    def test_blank_name_rejected(self):
        owner = self._register_login("blank@acme.test")
        assert owner.post("/api/v1/workspaces/",
                          {"name": "   "}, format="json").status_code == 400

    def test_invalid_email_rejected(self):
        owner, slug = self._owner_with_ws("ie@acme.test", "IE")
        r = owner.post(f"/api/v1/workspaces/{slug}/members/",
                       {"email": "not-an-email"}, format="json")
        assert r.status_code == 400

    def test_duplicate_active_member_rejected(self):
        owner, slug = self._owner_with_ws("dup@acme.test", "Dup")
        owner.post(f"/api/v1/workspaces/{slug}/members/",
                   {"email": "t@acme.test"}, format="json")
        r = owner.post(f"/api/v1/workspaces/{slug}/members/",
                       {"email": "t@acme.test"}, format="json")
        assert r.status_code == 400

    def test_assign_owner_via_role_rejected(self):
        owner, slug = self._owner_with_ws("ar@acme.test", "AR")
        mid = owner.post(f"/api/v1/workspaces/{slug}/members/",
                         {"email": "m@acme.test"}, format="json").data["id"]
        r = owner.patch(f"/api/v1/workspaces/{slug}/members/{mid}/",
                        {"role": "owner"}, format="json")
        assert r.status_code == 400

    def test_cannot_remove_owner(self):
        owner, slug = self._owner_with_ws("ro@acme.test", "RO")
        members = owner.get(f"/api/v1/workspaces/{slug}/members/").data
        owner_mid = members[0]["id"]
        assert owner.delete(f"/api/v1/workspaces/{slug}/members/{owner_mid}/").status_code == 400

    def test_non_admin_cannot_add_member(self):
        owner, slug = self._owner_with_ws("na@acme.test", "NA")
        # seat a plain member, set their password, log them in
        mail.outbox = []
        owner.post(f"/api/v1/workspaces/{slug}/members/",
                   {"email": "plain@acme.test", "role": "member"}, format="json")
        APIClient().post("/api/v1/auth/password-reset/confirm/",
                         {"token": _token_from_last_email(), "password": HIRE_PW}, format="json")
        r = APIClient().post("/api/v1/auth/login/",
                             {"email": "plain@acme.test", "password": HIRE_PW}, format="json")
        plain = _bearer(r.data["access"])
        resp = plain.post(f"/api/v1/workspaces/{slug}/members/",
                          {"email": "z@acme.test"}, format="json")
        assert resp.status_code == 403

    def test_removed_user_loses_access(self):
        owner, slug = self._owner_with_ws("rm@acme.test", "RM")
        mail.outbox = []
        mid = owner.post(f"/api/v1/workspaces/{slug}/members/",
                         {"email": "gone@acme.test"}, format="json").data["id"]
        APIClient().post("/api/v1/auth/password-reset/confirm/",
                         {"token": _token_from_last_email(), "password": HIRE_PW}, format="json")
        gone = _bearer(APIClient().post("/api/v1/auth/login/",
                       {"email": "gone@acme.test", "password": HIRE_PW},
                       format="json").data["access"])
        assert gone.get(f"/api/v1/workspaces/{slug}/members/").status_code == 200
        assert owner.delete(f"/api/v1/workspaces/{slug}/members/{mid}/").status_code == 204
        assert gone.get(f"/api/v1/workspaces/{slug}/members/").status_code == 403

    def test_wrong_workspace_and_non_member_denied(self):
        owner_a, slug_a = self._owner_with_ws("wa@acme.test", "WA")
        owner_b, slug_b = self._owner_with_ws("wb@acme.test", "WB")
        # owner_b is not a member of A → 403 on A's roster
        assert owner_b.get(f"/api/v1/workspaces/{slug_a}/members/").status_code == 403
        # unknown workspace → 404
        assert owner_a.get("/api/v1/workspaces/does-not-exist/members/").status_code == 404

    def test_non_owner_cannot_transfer(self):
        owner, slug = self._owner_with_ws("nt@acme.test", "NT")
        mail.outbox = []
        owner.post(f"/api/v1/workspaces/{slug}/members/",
                   {"email": "adm@acme.test", "role": "admin"}, format="json")
        APIClient().post("/api/v1/auth/password-reset/confirm/",
                         {"token": _token_from_last_email(), "password": HIRE_PW}, format="json")
        admin = _bearer(APIClient().post("/api/v1/auth/login/",
                        {"email": "adm@acme.test", "password": HIRE_PW},
                        format="json").data["access"])
        owner_mid = next(m["id"] for m in admin.get(f"/api/v1/workspaces/{slug}/members/").data
                         if m["email"] == "nt@acme.test")
        assert admin.post(f"/api/v1/workspaces/{slug}/transfer-ownership/",
                          {"member_id": owner_mid}, format="json").status_code == 403

    def test_invalid_invitation_token_rejected(self):
        assert APIClient().post("/api/v1/auth/password-reset/confirm/",
                                {"token": "bogus-token", "password": HIRE_PW},
                                format="json").status_code == 400
