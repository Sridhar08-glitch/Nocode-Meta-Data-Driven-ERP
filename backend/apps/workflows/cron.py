"""
Minimal, dependency-free 5-field CRON evaluator for scheduled workflows.

Standard fields:  ``minute hour day-of-month month day-of-week``
Supported tokens per field: ``*``, ``a``, ``a-b`` (range), ``a-b/n`` / ``*/n``
(step), and comma-separated lists of any of those. Day-of-week: 0 or 7 = Sunday.

We avoid the ``croniter`` dependency (not installed in the project venv) — the
engine only needs "is this expression due in the (last_fired, now] window?", which
this covers exactly. All times are UTC.
"""
from __future__ import annotations

import datetime as _dt

_FIELD_RANGES = [
    (0, 59),   # minute
    (0, 23),   # hour
    (1, 31),   # day of month
    (1, 12),   # month
    (0, 7),    # day of week (0 or 7 = Sun)
]


def _parse_field(token: str, lo: int, hi: int) -> set[int]:
    values: set[int] = set()
    for part in token.split(","):
        part = part.strip()
        if not part:
            continue
        step = 1
        if "/" in part:
            part, step_s = part.split("/", 1)
            step = int(step_s)
        if part in ("*", ""):
            start, end = lo, hi
        elif "-" in part:
            start_s, end_s = part.split("-", 1)
            start, end = int(start_s), int(end_s)
        else:
            start = end = int(part)
        for v in range(start, end + 1, step):
            if lo <= v <= hi:
                values.add(v)
    return values


def parse_cron(expr: str) -> list[set[int]]:
    """Parse a 5-field CRON string into a list of allowed-value sets per field."""
    fields = expr.split()
    if len(fields) != 5:
        raise ValueError(f"CRON expression must have 5 fields, got {len(fields)}: {expr!r}")
    parsed = []
    for token, (lo, hi) in zip(fields, _FIELD_RANGES, strict=False):
        parsed.append(_parse_field(token, lo, hi))
    return parsed


def cron_matches(expr: str, when: _dt.datetime) -> bool:
    """True if ``when`` (UTC, minute resolution) satisfies the CRON expression."""
    minute, hour, dom, month, dow = parse_cron(expr)
    # Python weekday(): Mon=0..Sun=6 → convert to cron Sun=0..Sat=6
    cron_dow = (when.weekday() + 1) % 7
    dow_match = cron_dow in dow or (cron_dow == 0 and 7 in dow)
    return (
        when.minute in minute
        and when.hour in hour
        and when.day in dom
        and when.month in month
        and dow_match
    )


def cron_is_due(expr: str, last_fired_at: _dt.datetime | None, now: _dt.datetime) -> bool:
    """True if the CRON expression has a firing minute in ``(last_fired_at, now]``.

    Scans minute-by-minute from just after ``last_fired_at`` up to ``now`` (capped
    at one week of look-back so a long-dormant schedule can't loop forever).
    """
    now = now.replace(second=0, microsecond=0)
    if last_fired_at is None:
        return cron_matches(expr, now)
    start = last_fired_at.replace(second=0, microsecond=0) + _dt.timedelta(minutes=1)
    floor = now - _dt.timedelta(days=7)
    if start < floor:
        start = floor
    cursor = start
    while cursor <= now:
        if cron_matches(expr, cursor):
            return True
        cursor += _dt.timedelta(minutes=1)
    return False
