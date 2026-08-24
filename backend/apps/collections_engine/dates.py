"""Pure date helpers for building a due schedule (no third-party deps)."""
from __future__ import annotations

import calendar
import datetime as dt


def add_months(base: dt.date, months: int) -> dt.date:
    m = base.month - 1 + months
    year = base.year + m // 12
    month = m % 12 + 1
    day = min(base.day, calendar.monthrange(year, month)[1])
    return dt.date(year, month, day)


def due_date_for(start: dt.date, frequency: str, n: int, interval_days: int = 0) -> dt.date:
    """The due date of the n-th installment (0-based) from ``start``."""
    if frequency == "weekly":
        return start + dt.timedelta(days=7 * n)
    if frequency == "monthly":
        return add_months(start, n)
    if frequency == "quarterly":
        return add_months(start, 3 * n)
    if frequency == "yearly":
        return add_months(start, 12 * n)
    if frequency == "custom":
        return start + dt.timedelta(days=(interval_days or 0) * n)
    return add_months(start, n)  # sensible default
