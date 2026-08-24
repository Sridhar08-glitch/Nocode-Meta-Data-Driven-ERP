"""
Business-calendar extension (Phase 1.33) — split-shift weekly_hours in the SLA
calculator + the new fields round-tripping through the API. Legacy single-window
`schedule` behaviour is covered by the existing test_calculator.py.
"""
import datetime as _dt

import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.sla import calculator
from apps.sla.models import BusinessHours
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"


def test_split_shift_skips_lunch_break():
    # Mon 09:00–12:00 and 13:00–17:00 (a lunch break between shifts).
    bh = BusinessHours(weekly_hours={
        "mon": [{"start": "09:00", "end": "12:00"}, {"start": "13:00", "end": "17:00"}]})
    # Monday 2024-01-01 11:00 + 120 business minutes → 60 min to 12:00, then 13:00 + 60 = 14:00.
    start = _dt.datetime(2024, 1, 1, 11, 0, tzinfo=_dt.UTC)
    out = calculator.add_business_minutes(start, 120, bh, set())
    assert (out.hour, out.minute) == (14, 0)


def test_weekly_hours_falls_back_to_schedule_when_absent():
    bh = BusinessHours(schedule={"mon": {"start": "09:00", "end": "17:00"}})
    start = _dt.datetime(2024, 1, 1, 11, 0, tzinfo=_dt.UTC)
    out = calculator.add_business_minutes(start, 120, bh, set())
    assert (out.hour, out.minute) == (13, 0)   # no lunch break in legacy single window


def test_day_intervals_sorted():
    bh = BusinessHours(weekly_hours={
        "tue": [{"start": "13:00", "end": "17:00"}, {"start": "09:00", "end": "12:00"}]})
    intervals = calculator._day_intervals(bh, 1)  # tue
    assert intervals == [(9, 0, 12, 0), (13, 0, 17, 0)]


@pytest.mark.django_db
class TestBusinessCalendarApi:
    def _admin(self, ws):
        u = User.objects.create_user(email="a@acme.com", password=PW, is_verified=True)
        WorkspaceMember.objects.create(workspace=ws, user=u, role="admin", status="active")
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(u)}",
                      HTTP_X_WORKSPACE_SLUG=ws.slug)
        return c

    def test_create_with_weekly_hours_shifts_region(self, db):
        ws = Workspace.objects.create(name="Acme", slug="acme", is_active=True)
        c = self._admin(ws)
        payload = {
            "name": "EU Calendar", "timezone": "Europe/Paris", "region": "EU",
            "weekly_hours": {"mon": [{"start": "09:00", "end": "13:00"},
                                     {"start": "14:00", "end": "18:00"}]},
            "shifts": {"morning": [{"start": "06:00", "end": "14:00"}]},
        }
        r = c.post("/api/v1/sla/business-hours/", payload, format="json")
        assert r.status_code == 201
        assert r.data["region"] == "EU"
        assert r.data["shifts"]["morning"][0]["start"] == "06:00"
        bh = BusinessHours.objects.get(id=r.data["id"])
        assert bh.weekly_hours["mon"][1]["end"] == "18:00"
