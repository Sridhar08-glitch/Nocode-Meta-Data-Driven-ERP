"""
Treasury → System-Entity descriptors (B0). Publishes the treasury native models so the Generic Runtime
renders them (list/detail/create) with NO bespoke React. Writes reuse `TreasuryService` (accounting
stays in the engine); lifecycle actions point at the existing treasury endpoints. Registered at
`TreasuryConfig.ready()`.
"""
from __future__ import annotations

from apps.system_entities.registry import Action, SystemEntity, register

from .models import TreasuryCounterparty, TreasuryFacility, TreasuryInvestment, TreasuryTransaction
from .services import TreasuryService


def _counterparty_create(*, workspace_id, data, actor_id=None):
    return TreasuryCounterparty.objects.create(
        workspace_id=workspace_id, code=data.get("code", ""), name=data.get("name", ""),
        counterparty_type=data.get("counterparty_type", "bank"),
        credit_rating=data.get("credit_rating", ""), exposure_limit=data.get("exposure_limit", 0) or 0,
        created_by=actor_id)


def _facility_create(*, workspace_id, data, actor_id=None):
    return TreasuryService.create_facility(workspace_id=workspace_id, actor_id=actor_id, **data)


def _investment_create(*, workspace_id, data, actor_id=None):
    return TreasuryService.create_investment(workspace_id=workspace_id, actor_id=actor_id, **data)


def register_system_entities() -> None:
    register(SystemEntity(
        slug="treasury_counterparty", model=TreasuryCounterparty, name="Counterparty",
        plural_name="Counterparties", module="treasury",
        can_create=True, create_fn=_counterparty_create, default_ordering="code"))

    register(SystemEntity(
        slug="treasury_facility", model=TreasuryFacility, name="Facility", plural_name="Facilities",
        module="treasury", can_create=True, create_fn=_facility_create,
        actions=[Action("drawdown", "Drawdown",
                        path="/api/v1/treasury/facilities/{id}/drawdown/"),
                 Action("repay", "Repay Principal",
                        path="/api/v1/treasury/facilities/{id}/repay/")]))

    register(SystemEntity(
        slug="treasury_investment", model=TreasuryInvestment, name="Investment",
        plural_name="Investments", module="treasury", can_create=True, create_fn=_investment_create,
        actions=[Action("place", "Place Investment",
                        path="/api/v1/treasury/investments/{id}/place/"),
                 Action("mature", "Mature",
                        path="/api/v1/treasury/investments/{id}/mature/")]))

    register(SystemEntity(
        slug="treasury_transaction", model=TreasuryTransaction, name="Treasury Transaction",
        plural_name="Treasury Transactions", module="treasury", default_ordering="-value_date"))
