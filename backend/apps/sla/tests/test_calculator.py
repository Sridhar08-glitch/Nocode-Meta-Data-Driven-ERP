"""SLA business-hours calculator (PROJECT_HANDBOOK.md §28.1 / §28.5)."""
import datetime as dt

import pytest

from apps.sla.calculator import compute_target_at


def _policy(make_policy, business_hours_only=True, warning=80, minutes=60):
    return make_policy([{"metric": "resolution", "target_minutes": minutes,
                         "warning_at_percent": warning,
                         "business_hours_only": business_hours_only}])


@pytest.mark.django_db
class TestBusinessHours:
    def test_skips_weekend(self, ws, lead, make_policy, business_hours):
        business_hours()
        policy = _policy(make_policy)
        # Friday 2026-06-19 16:30 UTC + 60 business min → Monday 2026-06-22 09:30
        start = dt.datetime(2026, 6, 19, 16, 30, tzinfo=dt.UTC)
        target, _warning = compute_target_at(policy, "resolution", start, ws.id)
        assert target == dt.datetime(2026, 6, 22, 9, 30, tzinfo=dt.UTC)

    def test_holiday_shifts_to_next_business_day(self, ws, lead, make_policy, business_hours):
        business_hours(holidays=[{"date": "2026-06-22", "name": "Holiday"}])
        policy = _policy(make_policy)
        start = dt.datetime(2026, 6, 19, 16, 30, tzinfo=dt.UTC)
        target, _ = compute_target_at(policy, "resolution", start, ws.id)
        # Monday is a holiday → remaining 30 min lands Tuesday 09:30
        assert target == dt.datetime(2026, 6, 23, 9, 30, tzinfo=dt.UTC)

    def test_warning_before_target(self, ws, lead, make_policy, business_hours):
        business_hours()
        policy = _policy(make_policy, warning=50, minutes=60)
        start = dt.datetime(2026, 6, 19, 9, 0, tzinfo=dt.UTC)  # Friday 09:00
        target, warning = compute_target_at(policy, "resolution", start, ws.id)
        assert target == dt.datetime(2026, 6, 19, 10, 0, tzinfo=dt.UTC)   # +60 min
        assert warning == dt.datetime(2026, 6, 19, 9, 30, tzinfo=dt.UTC)  # +30 min (50%)


@pytest.mark.django_db
class TestLinear:
    def test_wall_clock(self, ws, lead, make_policy):
        policy = _policy(make_policy, business_hours_only=False, warning=75, minutes=120)
        start = dt.datetime(2026, 6, 21, 12, 0, tzinfo=dt.UTC)  # Sunday — ignored
        target, warning = compute_target_at(policy, "resolution", start, ws.id)
        assert target == start + dt.timedelta(minutes=120)
        assert warning == start + dt.timedelta(minutes=90)
