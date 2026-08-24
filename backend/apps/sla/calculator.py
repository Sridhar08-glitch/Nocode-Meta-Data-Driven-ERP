"""
SLA business-hours calculator (PROJECT_HANDBOOK.md §28.1).

Computes SLA target/warning timestamps. When a target is ``business_hours_only``
it walks forward through a :class:`~apps.sla.models.BusinessHours` calendar
(skipping non-working days + holidays) in the calendar's timezone; otherwise it is
plain wall-clock. All returned datetimes are timezone-aware UTC.
"""
from __future__ import annotations

import datetime as _dt
from zoneinfo import ZoneInfo

from .models import BusinessHours

_DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
_DEFAULT_WARNING_PCT = 80


def _parse_hhmm(value: str) -> tuple[int, int]:
    h, m = value.split(":")
    return int(h), int(m)


def _holiday_dates(business_hours) -> set:
    out = set()
    for h in (business_hours.holidays or []):
        raw = h.get("date") if isinstance(h, dict) else h
        try:
            out.add(_dt.date.fromisoformat(raw))
        except (TypeError, ValueError):
            continue
    return out


def _day_intervals(bh, weekday: int) -> list[tuple[int, int, int, int]]:
    """Working intervals for a weekday as sorted ``(sh, sm, eh, em)`` tuples.

    Prefers the richer ``weekly_hours`` (a LIST of {start,end} per day — supports split
    shifts); falls back to the legacy single-window ``schedule`` so existing calendars
    keep working unchanged.
    """
    day = _DAYS[weekday]
    weekly = (getattr(bh, "weekly_hours", None) or {}).get(day)
    raw = []
    if weekly:
        raw = [(w["start"], w["end"]) for w in weekly if w.get("start") and w.get("end")]
    else:
        win = (bh.schedule or {}).get(day)
        if win and win.get("start") and win.get("end"):
            raw = [(win["start"], win["end"])]
    out = []
    for start, end in raw:
        sh, sm = _parse_hhmm(start)
        eh, em = _parse_hhmm(end)
        out.append((sh, sm, eh, em))
    out.sort()
    return out


def add_business_minutes(start, minutes, bh, holidays) -> _dt.datetime:
    """Return the datetime *minutes* business-minutes after ``start`` (local, aware)."""
    remaining = float(minutes)
    cur = start
    guard = 0
    while remaining > 0 and guard < 4000:
        guard += 1
        if cur.date() not in holidays:
            for sh, sm, eh, em in _day_intervals(bh, cur.weekday()):
                day_start = cur.replace(hour=sh, minute=sm, second=0, microsecond=0)
                day_end = cur.replace(hour=eh, minute=em, second=0, microsecond=0)
                seg_start = max(cur, day_start)
                if seg_start < day_end:
                    avail = (day_end - seg_start).total_seconds() / 60
                    if avail >= remaining:
                        return seg_start + _dt.timedelta(minutes=remaining)
                    remaining -= avail
        cur = (cur + _dt.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return cur


def _business_hours_for(target: dict, workspace_id):
    bh_id = target.get("business_hours_id")
    if bh_id:
        bh = BusinessHours.objects.filter(id=bh_id, workspace_id=workspace_id).first()
        if bh:
            return bh
    return BusinessHours.objects.filter(workspace_id=workspace_id).first()


def _find_target(policy, metric: str) -> dict | None:
    for t in (policy.targets or []):
        if t.get("metric") == metric:
            return t
    return None


def compute_target_at(policy, metric, started_at, workspace_id):
    """Return ``(target_at, warning_at)`` (aware UTC) for a policy metric."""
    target = _find_target(policy, metric)
    if target is None:
        raise ValueError(f"metric {metric!r} not found on policy {policy.slug!r}")
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=_dt.UTC)
    target_minutes = float(target["target_minutes"])
    warning_pct = float(target.get("warning_at_percent", _DEFAULT_WARNING_PCT))
    warning_minutes = target_minutes * warning_pct / 100.0

    if target.get("business_hours_only"):
        bh = _business_hours_for(target, workspace_id)
        if bh is not None:
            tz = ZoneInfo(bh.timezone or "UTC")
            holidays = _holiday_dates(bh)
            local_start = started_at.astimezone(tz)
            target_local = add_business_minutes(local_start, target_minutes, bh, holidays)
            warning_local = add_business_minutes(local_start, warning_minutes, bh, holidays)
            return target_local.astimezone(_dt.UTC), warning_local.astimezone(_dt.UTC)

    target_at = started_at + _dt.timedelta(minutes=target_minutes)
    warning_at = started_at + _dt.timedelta(minutes=warning_minutes)
    return target_at, warning_at


def compute_elapsed_business_minutes(started_at, paused_seconds, workspace_id) -> int:
    """Business minutes elapsed since ``started_at`` (workspace default calendar),
    excluding ``paused_seconds``. Falls back to wall-clock if no calendar exists."""
    from django.utils import timezone
    now = timezone.now()
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=_dt.UTC)
    bh = BusinessHours.objects.filter(workspace_id=workspace_id).first()
    if bh is None:
        elapsed = (now - started_at).total_seconds() / 60
        return max(int(elapsed - paused_seconds / 60), 0)
    tz = ZoneInfo(bh.timezone or "UTC")
    holidays = _holiday_dates(bh)
    cur = started_at.astimezone(tz)
    end = now.astimezone(tz)
    minutes = 0.0
    guard = 0
    while cur < end and guard < 4000:
        guard += 1
        if cur.date() not in holidays:
            for sh, sm, eh, em in _day_intervals(bh, cur.weekday()):
                day_start = cur.replace(hour=sh, minute=sm, second=0, microsecond=0)
                day_end = cur.replace(hour=eh, minute=em, second=0, microsecond=0)
                seg_start = max(cur, day_start)
                seg_end = min(end, day_end)
                if seg_start < seg_end:
                    minutes += (seg_end - seg_start).total_seconds() / 60
        cur = (cur + _dt.timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(int(minutes - paused_seconds / 60), 0)
