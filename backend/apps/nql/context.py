"""
NQL execution context + server-side resolution of ``@`` magic values.

Magic values are NEVER trusted from the client as raw SQL — they resolve to
concrete parameters here (master spec §12 / PROJECT_HANDBOOK.md §14):

    @me          → context.user_id
    @today       → today's date
    @last_week   → 7 days ago
    @this_month  → first day of the current month
    @now         → current timestamp
"""
from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass


@dataclass
class NQLContext:
    workspace_id: object                 # uuid.UUID
    user_id: object | None = None        # uuid.UUID — resolves @me
    now: _dt.datetime | None = None      # injectable for deterministic tests

    def _now(self) -> _dt.datetime:
        return self.now or _dt.datetime.now(_dt.UTC)

    def resolve_magic(self, token: str):
        """Resolve an ``@token`` to a concrete value, or return ``token`` unchanged."""
        if not isinstance(token, str) or not token.startswith("@"):
            return token
        key = token.lower()
        now = self._now()
        if key == "@me":
            if self.user_id is None:
                raise ValueError("@me used without an authenticated user")
            return str(self.user_id)
        if key == "@today":
            return now.date().isoformat()
        if key == "@yesterday":
            return (now.date() - _dt.timedelta(days=1)).isoformat()
        if key == "@last_week":
            return (now.date() - _dt.timedelta(days=7)).isoformat()
        if key == "@this_month":
            return now.date().replace(day=1).isoformat()
        if key == "@now":
            return now.isoformat()
        raise ValueError(f"Unknown NQL magic value: {token!r}")
