"""
Performance Certification (P2.16 Module 23).

No unrealistic CI datasets. Instead this module provides:
  - `count_queries(fn)` — measure DB queries around a callable (used to PROVE list reads
    are not N+1: query count must stay ~constant as row count grows).
  - `ENTERPRISE_METHODOLOGY` — the documented approach for enterprise-scale workloads
    (100k+ employees/projects, 1M+ inventory txns, large payroll/MRP runs).
Both are read by the certification report and the test suite.
"""
from __future__ import annotations

from django.db import connection
from django.test.utils import CaptureQueriesContext


def count_queries(fn) -> int:
    """Return the number of DB queries executed by fn()."""
    with CaptureQueriesContext(connection) as ctx:
        fn()
    return len(ctx.captured_queries)


def is_constant_query_count(fn_small, fn_large, *, tolerance: int = 3) -> tuple[bool, int, int]:
    """
    True when query count does not scale with row count (no N+1).
    Returns (ok, queries_small, queries_large).
    """
    q_small = count_queries(fn_small)
    q_large = count_queries(fn_large)
    return (q_large - q_small) <= tolerance, q_small, q_large


# Documented methodology — NOT executed in CI (no unrealistic datasets generated).
ENTERPRISE_METHODOLOGY = {
    "principles": [
        "RecordService.list_records performs bulk reads — query count is independent of row count.",
        "FinancialsService / SchedulingService / ResourceService batch-read metadata (no per-row queries).",
        "Inventory uses select_for_update on StockLevel to keep stock race-safe under concurrency.",
        "Payroll uses select_for_update per Payslip within a run.",
        "Idempotency guards (unique constraints + reference dedup) keep retries cheap and correct.",
        "Celery tasks process large batches in chunks; FTS uses GIN indexes + async reindex.",
    ],
    "scale_targets": {
        "employees": "100k+",
        "projects": "100k+",
        "inventory_transactions": "1M+",
        "payroll_run": "large (chunked)",
        "mrp_workload": "large (BOM explosion is iterative + circular-detect)",
    },
    "indexes": [
        "Every tenant table carries a workspace_id index (TenantModel).",
        "Hot lookups (entity slug, code, status) are indexed in each app's Meta.indexes.",
        "Search uses a GIN index on the _fts_vector column (PostgreSQL).",
    ],
    "ci_note": "CI validates the no-N+1 property on small datasets; full-scale load testing is a "
               "documented ops procedure, not a CI gate (avoids unrealistic CI datasets).",
}
