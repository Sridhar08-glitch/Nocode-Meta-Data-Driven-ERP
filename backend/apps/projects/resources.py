"""
Resource Allocation + Capacity Planning engine (Phase P2.10) — pure, batch-safe.

Computes per-employee utilization (sum of allocation %), over/under-allocation, resource
conflicts, and capacity (available vs allocated hours) from project_member allocation records.
No DB — the service passes allocation dicts so this scales to 10k+ resources without N+1.
"""
from __future__ import annotations

from decimal import Decimal


def _pct(v) -> Decimal:
    try:
        return Decimal(str(v or 0))
    except Exception:  # noqa: BLE001
        return Decimal("0")


def utilization(allocations: list[dict]) -> dict:
    """allocations: [{employee, allocation_percent, project?}]. Returns per-employee totals +
    over-allocation flags + the conflict list (employees > 100%)."""
    by_emp: dict = {}
    for a in allocations:
        emp = str(a.get("employee"))
        if not emp or emp == "None":
            continue
        by_emp.setdefault(emp, {"employee": emp, "total_percent": Decimal("0"), "projects": []})
        by_emp[emp]["total_percent"] += _pct(a.get("allocation_percent"))
        if a.get("project"):
            by_emp[emp]["projects"].append(str(a["project"]))
    result = []
    conflicts = []
    for emp, row in by_emp.items():
        total = row["total_percent"]
        entry = {
            "employee": emp, "total_percent": float(total),
            "over_allocated": total > 100, "under_allocated": total < 100,
            "available_percent": float(Decimal("100") - total),
            "bench": total == 0, "project_count": len(row["projects"]),
        }
        result.append(entry)
        if total > 100:
            conflicts.append({"employee": emp, "total_percent": float(total)})
    return {"utilization": result, "conflicts": conflicts}


def capacity(allocations: list[dict], *, weekly_hours: float = 40.0) -> dict:
    """Per-employee weekly capacity: allocated vs available hours from allocation %."""
    util = utilization(allocations)["utilization"]
    rows = []
    for u in util:
        allocated = weekly_hours * u["total_percent"] / 100.0
        rows.append({
            "employee": u["employee"], "weekly_hours": weekly_hours,
            "allocated_hours": round(allocated, 2),
            "available_hours": round(weekly_hours - allocated, 2),
            "over_capacity": allocated > weekly_hours,
        })
    return {"capacity": rows}


def forecast_capacity(allocations: list[dict], *, weeks: int = 4,
                      weekly_hours: float = 40.0) -> dict:
    """Simple forward capacity forecast (flat allocation across the horizon)."""
    cap = capacity(allocations, weekly_hours=weekly_hours)["capacity"]
    return {"weeks": weeks, "weekly_hours": weekly_hours,
            "forecast": [{"employee": c["employee"],
                          "available_hours": round(c["available_hours"] * weeks, 2),
                          "allocated_hours": round(c["allocated_hours"] * weeks, 2)}
                         for c in cap]}
