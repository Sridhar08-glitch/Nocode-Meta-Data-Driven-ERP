"""CRON evaluator unit tests (dependency-free scheduler)."""
import datetime as dt

import pytest

from apps.workflows.cron import cron_is_due, cron_matches, parse_cron


def test_parse_basic():
    minute, hour, dom, month, dow = parse_cron("*/15 9-17 * * 1-5")
    assert minute == {0, 15, 30, 45}
    assert hour == set(range(9, 18))
    assert dow == {1, 2, 3, 4, 5}


def test_wildcard_matches_any():
    when = dt.datetime(2026, 6, 21, 14, 33, tzinfo=dt.UTC)
    assert cron_matches("* * * * *", when)


def test_specific_minute_hour():
    when = dt.datetime(2026, 6, 21, 9, 0, tzinfo=dt.UTC)
    assert cron_matches("0 9 * * *", when)
    assert not cron_matches("30 9 * * *", when)


def test_day_of_week_sunday():
    sunday = dt.datetime(2026, 6, 21, 0, 0, tzinfo=dt.UTC)  # 2026-06-21 is a Sunday
    assert cron_matches("0 0 * * 0", sunday)
    assert cron_matches("0 0 * * 7", sunday)
    assert not cron_matches("0 0 * * 1", sunday)


def test_is_due_window():
    now = dt.datetime(2026, 6, 21, 9, 2, tzinfo=dt.UTC)
    # last fired at 09:00 → 09:01 and 09:02 are in window; "0,1,2 9" matches 09:01/09:02
    assert cron_is_due("* 9 * * *", dt.datetime(2026, 6, 21, 9, 0, tzinfo=dt.UTC), now)
    # last fired now → no future minute ≤ now
    assert not cron_is_due("* * * * *", now, now)


def test_is_due_first_run():
    now = dt.datetime(2026, 6, 21, 9, 0, tzinfo=dt.UTC)
    assert cron_is_due("0 9 * * *", None, now)
    assert not cron_is_due("0 10 * * *", None, now)


def test_invalid_field_count():
    with pytest.raises(ValueError):
        parse_cron("* * *")
