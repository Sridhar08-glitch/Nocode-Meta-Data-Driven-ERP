"""
Manufacturing engines (Phase P2.12) — pure functions, batch-safe (no DB, no N+1).

  * bom_explode        — multi-level BOM explosion with scrap + circular detection (Module 6)
  * mrp_plan           — net requirement = demand − available → planned orders / purchase reqs (M14)
  * standard_cost      — material + labor + overhead cost rollup (Modules 29/30)
  * oee                — Availability × Performance × Quality (Module 42)
  * yield_percent      — output / input (Module 44)

Services feed these from native rows so they scale (100k components) without per-node queries.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

CENTS = Decimal("0.01")


def money(v) -> Decimal:
    try:
        return Decimal(str(v or 0)).quantize(CENTS, rounding=ROUND_HALF_UP)
    except Exception:  # noqa: BLE001
        return Decimal("0.00")


def qty(v) -> Decimal:
    try:
        return Decimal(str(v or 0))
    except Exception:  # noqa: BLE001
        return Decimal("0")


class BOMError(Exception):  # noqa: N818 — domain error
    pass


def bom_explode(product_item_id, quantity, components_by_item, *, _path=None) -> dict:
    """Explode ``quantity`` of ``product_item_id`` into total component requirements at ALL levels.

    ``components_by_item``: {item_id: [{component_item_id, quantity, scrap_percent}]}. Items absent
    from the map are leaves (raw materials). Raises ``BOMError`` on a circular BOM.
    """
    _path = _path or []
    if product_item_id in _path:
        raise BOMError(f"Circular BOM detected at {product_item_id}.")
    requirements: dict = {}
    for comp in components_by_item.get(product_item_id, []) or []:
        cid = comp["component_item_id"]
        scrap = qty(comp.get("scrap_percent", 0)) / Decimal("100")
        need = qty(quantity) * qty(comp["quantity"]) * (Decimal("1") + scrap)
        requirements[cid] = requirements.get(cid, Decimal("0")) + need
        for sub_id, sub_qty in bom_explode(
                cid, need, components_by_item, _path=[*_path, product_item_id]).items():
            requirements[sub_id] = requirements.get(sub_id, Decimal("0")) + sub_qty
    return requirements


def mrp_plan(rows: list[dict]) -> list[dict]:
    """rows: [{item_id, demand, available, has_bom}]. Returns one result per item with the net
    requirement + suggested action (manufacture if it has a BOM, else purchase)."""
    out = []
    for r in rows:
        demand = qty(r.get("demand"))
        available = qty(r.get("available"))
        net = max(Decimal("0"), demand - available)
        action = "none"
        if net > 0:
            action = "manufacture" if r.get("has_bom") else "purchase"
        out.append({"item_id": r["item_id"], "demand": demand, "available": available,
                    "net_requirement": net, "suggested_qty": net, "action": action})
    return out


def standard_cost(*, material_cost, labor_minutes, labor_rate_per_hour, overhead_percent=0,
                  machine_cost=0) -> dict:
    """Standard cost rollup: material + labor (minutes × rate) + machine + overhead (% of the rest)."""
    material = money(material_cost)
    labor = money(qty(labor_minutes) / Decimal("60") * money(labor_rate_per_hour))
    machine = money(machine_cost)
    base = material + labor + machine
    overhead = money(base * qty(overhead_percent) / Decimal("100"))
    return {"material": str(material), "labor": str(labor), "machine": str(machine),
            "overhead": str(overhead), "total": str(money(base + overhead))}


def oee(*, planned_minutes, downtime_minutes, ideal_cycle_minutes, good_qty, reject_qty) -> dict:
    """OEE = Availability × Performance × Quality (each a 0–1 ratio)."""
    planned = qty(planned_minutes)
    runtime = max(Decimal("0"), planned - qty(downtime_minutes))
    total = qty(good_qty) + qty(reject_qty)
    availability = (runtime / planned) if planned > 0 else Decimal("0")
    performance = ((qty(ideal_cycle_minutes) * total) / runtime) if runtime > 0 else Decimal("0")
    performance = min(performance, Decimal("1"))
    quality = (qty(good_qty) / total) if total > 0 else Decimal("0")
    score = availability * performance * quality
    return {"availability": float(round(availability, 4)),
            "performance": float(round(performance, 4)),
            "quality": float(round(quality, 4)), "oee": float(round(score, 4))}


def yield_percent(*, input_qty, output_qty) -> float:
    i = qty(input_qty)
    return float(round((qty(output_qty) / i * Decimal("100")), 2)) if i > 0 else 0.0
