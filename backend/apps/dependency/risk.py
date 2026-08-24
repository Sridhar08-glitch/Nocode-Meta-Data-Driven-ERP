"""
Risk scoring engine (Phase P2.14) — pure.

Assigns low/medium/high/critical risk to a change from its dependency footprint: dependency count
+ whether workflows depend on it (automation breakage is higher-risk) + approximate references.
"""
from __future__ import annotations

_PRODUCTION_TYPES = {"workflow", "rule"}  # automation/business-logic dependents = higher risk


def score(dependents: list[dict]) -> dict:
    n = len(dependents)
    has_automation = any(d.get("type") in _PRODUCTION_TYPES for d in dependents)
    exact = sum(1 for d in dependents if not d.get("approximate"))
    if n == 0:
        level = "low"
    elif n >= 50:
        level = "critical"
    elif n >= 20 or has_automation:
        level = "high"
    elif n >= 5:
        level = "medium"
    else:
        level = "low"
    raw = exact * 2 + (n - exact) + (40 if has_automation else 0)
    return {"level": level, "count": n, "exact": exact, "has_automation": has_automation,
            "score": min(100, raw)}


def is_blocking(risk: dict) -> bool:
    """Promotion is blocked on critical risk (high warns but does not block)."""
    return risk.get("level") == "critical"
