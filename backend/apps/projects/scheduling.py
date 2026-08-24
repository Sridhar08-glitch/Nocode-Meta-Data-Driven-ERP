"""
Scheduling / Critical Path engine (Phase P2.10) — pure, batch-safe (no DB, no N+1).

Implements the Critical Path Method: forward pass (earliest start/finish), backward pass (latest
start/finish), total float, and the critical path. Dependencies are finish-to-start with optional
lag by default; start-to-start / finish-to-finish / start-to-finish are handled as CPM variants.
Used by ``services`` over task + task_dependency metadata; also powers Gantt + delay propagation.
"""
from __future__ import annotations


class SchedulingError(Exception):  # noqa: N818 — domain error
    pass


def _topo_order(task_ids, edges):
    """Kahn topological sort over predecessor→successor edges. Raises on a cycle."""
    indeg = {t: 0 for t in task_ids}
    adj: dict = {t: [] for t in task_ids}
    for e in edges:
        p, s = e["predecessor"], e["successor"]
        if p in adj and s in indeg:
            adj[p].append(s)
            indeg[s] += 1
    queue = [t for t in task_ids if indeg[t] == 0]
    order = []
    while queue:
        n = queue.pop(0)
        order.append(n)
        for m in adj[n]:
            indeg[m] -= 1
            if indeg[m] == 0:
                queue.append(m)
    if len(order) != len(task_ids):
        raise SchedulingError("Dependency cycle detected — schedule is invalid.")
    return order, adj


def critical_path(tasks: list[dict], dependencies: list[dict]) -> dict:
    """tasks: [{id, duration}] (duration in days). dependencies: [{predecessor, successor,
    dependency_type?, lag_days?}]. Returns ES/EF/LS/LF/float per task, the critical task ids,
    and the project duration."""
    dur = {t["id"]: max(float(t.get("duration", 0) or 0), 0) for t in tasks}
    ids = list(dur.keys())
    edges = [e for e in dependencies
             if e.get("predecessor") in dur and e.get("successor") in dur]
    order, adj = _topo_order(ids, edges)
    preds: dict = {t: [] for t in ids}
    for e in edges:
        preds[e["successor"]].append(e)

    es, ef = {}, {}
    for t in order:
        start = 0.0
        for e in preds[t]:
            p = e["predecessor"]
            lag = float(e.get("lag_days", 0) or 0)
            dtype = e.get("dependency_type", "finish_to_start")
            if dtype == "start_to_start":
                start = max(start, es.get(p, 0) + lag)
            elif dtype == "finish_to_finish":
                start = max(start, ef.get(p, 0) + lag - dur[t])
            elif dtype == "start_to_finish":
                start = max(start, es.get(p, 0) + lag - dur[t])
            else:  # finish_to_start
                start = max(start, ef.get(p, 0) + lag)
        es[t] = max(start, 0.0)
        ef[t] = es[t] + dur[t]

    project_duration = max(ef.values()) if ef else 0.0
    ls, lf = {}, {}
    for t in reversed(order):
        succ = adj[t]
        if not succ:
            lf[t] = project_duration
        else:
            lf[t] = min(ls.get(s, project_duration) for s in succ)
        ls[t] = lf[t] - dur[t]

    total_float = {t: round(ls[t] - es[t], 4) for t in ids}
    critical = [t for t in ids if abs(total_float[t]) < 1e-9]
    return {
        "project_duration": project_duration,
        "earliest_start": es, "earliest_finish": ef,
        "latest_start": ls, "latest_finish": lf,
        "total_float": total_float, "critical_task_ids": critical,
    }


def gantt_bars(tasks: list[dict], dependencies: list[dict], *, start_offset=0) -> list[dict]:
    """Gantt-ready bars (offset days from project start) with the critical flag — pure, for the UI."""
    cp = critical_path(tasks, dependencies)
    crit = set(cp["critical_task_ids"])
    bars = []
    for t in tasks:
        tid = t["id"]
        bars.append({
            "id": tid, "start": cp["earliest_start"].get(tid, 0) + start_offset,
            "finish": cp["earliest_finish"].get(tid, 0) + start_offset,
            "float": cp["total_float"].get(tid, 0), "critical": tid in crit,
        })
    return bars
