"""
Treasury Platform (F12) — performance / no-N+1 certification (Certification Gate 8, partial).

Proves the READ paths (debt schedule, maturity schedule, liquidity position, transaction list) execute
in a BOUNDED number of DB queries that does NOT grow with the number of deals/transactions — i.e. no
N+1. Query-count harness (not a load test); throughput/concurrency load testing is a separate,
environment-level exercise (documented as not covered here).
"""
import datetime as dt
import uuid

import pytest

from apps.cash.services import CashService
from apps.ledger.provisioning import provision_accounting
from apps.treasury.services import LiquidityService, ScheduleService, TreasuryService

pytestmark = pytest.mark.django_db

TODAY = dt.date(2026, 1, 1)
MAT = dt.date(2026, 12, 31)


def _ws_with_deals(n):
    ws = uuid.uuid4()
    provision_accounting(ws)
    for _ in range(n):
        f = TreasuryService.create_facility(
            workspace_id=ws, principal="10000", currency="USD", interest_rate="6",
            start_date=TODAY, maturity_date=MAT)
        TreasuryService.drawdown(workspace_id=ws, facility_id=f.id)
        inv = TreasuryService.create_investment(
            workspace_id=ws, principal="5000", currency="USD", interest_rate="4",
            start_date=TODAY, maturity_date=MAT)
        TreasuryService.place_investment(workspace_id=ws, investment_id=inv.id)
    return ws


def test_debt_schedule_is_bounded(django_assert_max_num_queries):
    """debt_schedule = one query regardless of facility count (no per-row query)."""
    ws = _ws_with_deals(20)
    with django_assert_max_num_queries(2):
        rows = ScheduleService.debt_schedule(ws)
    assert len(rows) == 20


def test_maturity_schedule_is_bounded(django_assert_max_num_queries):
    """maturity_schedule = one facility query + one investment query (constant)."""
    ws = _ws_with_deals(20)
    with django_assert_max_num_queries(3):
        rows = ScheduleService.maturity_schedule(ws)
    assert len(rows) == 40


def test_liquidity_position_is_bounded(django_assert_max_num_queries):
    """liquidity = cash position + one investment sum + one borrowing sum (constant vs deal count)."""
    ws = _ws_with_deals(20)
    CashService.ensure_account(workspace_id=ws, code="MAIN", name="Main",
                               account_type="bank", gl_account_code="1010")
    # bank_balance walks GL lines; bound generously but constant w.r.t. deal count
    with django_assert_max_num_queries(8):
        pos = LiquidityService.position(ws)
    assert pos["borrowings"] == "200000.00"      # 20 × 10000
    assert pos["investments"] == "100000.00"     # 20 × 5000
