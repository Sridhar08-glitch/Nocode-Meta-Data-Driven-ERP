"""
Country Adapter Framework (Phase P2.8, Module 33).

The architecture for statutory payroll (tax / pension / social security / provident fund /
gratuity / end-of-service) per country. Implementations land later; the EXTENSION POINTS exist
now so no payroll redesign is ever needed. A country adapter contributes extra payslip
components (statutory deductions/contributions) and computes gratuity / end-of-service.

Register an adapter with ``register_adapter``; the calculator calls ``get_adapter(country)``
(falling back to the built-in no-op ``DefaultCountryAdapter`` so payroll always runs).
"""
from __future__ import annotations

from decimal import Decimal

from .formula import money


class CountryAdapter:
    """Base class — override the hooks for a country's statutory rules."""

    code = ""

    def statutory_components(self, *, gross: Decimal, basic: Decimal, context: dict) -> list[dict]:
        """Return extra payslip-component dicts: {code,name,component_type,amount,source}.
        Default: none."""
        return []

    def gratuity(self, *, service_years: Decimal, last_basic: Decimal, context: dict) -> Decimal:
        """End-of-service / gratuity amount. Default: none."""
        return Decimal("0.00")


class DefaultCountryAdapter(CountryAdapter):
    """No statutory rules — used when a workspace has no country adapter (most non-statutory setups)."""
    code = ""


_REGISTRY: dict[str, CountryAdapter] = {}


def register_adapter(adapter: CountryAdapter) -> None:
    _REGISTRY[(adapter.code or "").upper()] = adapter


def get_adapter(country: str | None) -> CountryAdapter:
    return _REGISTRY.get((country or "").upper(), _DEFAULT)


def registered_countries() -> list[str]:
    return sorted(c for c in _REGISTRY if c)


_DEFAULT = DefaultCountryAdapter()


# ── A reference gratuity adapter (Gulf-style: 21 days/yr ≤5y, 30 days/yr after) ──────────────
class GulfGratuityAdapter(CountryAdapter):
    """Reference end-of-service framework for QA/UAE/SA-style gratuity. Demonstrates the
    extension point; a production deployment registers country-exact rules. Not auto-registered
    (statutory adapters are opt-in per workspace/deployment)."""

    def gratuity(self, *, service_years, last_basic, context):
        years = Decimal(str(service_years or 0))
        basic = money(last_basic)
        daily = basic / Decimal("30")
        if years <= 0:
            return Decimal("0.00")
        capped_first = min(years, Decimal("5"))
        amount = capped_first * 21 * daily
        if years > 5:
            amount += (years - 5) * 30 * daily
        return money(amount)
