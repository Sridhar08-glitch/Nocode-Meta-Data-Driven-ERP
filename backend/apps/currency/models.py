"""
Multi-Currency master (Financial Platform — multi-currency).

The reusable Core capability for foreign-currency accounting. ``Currency`` is the per-workspace
currency master (one flagged ``is_base`` = the functional/reporting currency); ``ExchangeRate`` is the
effective-dated rate history (spot / average / closing / historical). ``CurrencyService`` resolves a
rate on a date and converts amounts. GLBus consumes these to record each journal line's base-currency
equivalent so the ledger always balances + reports in the base currency, while transactions keep their
foreign amount. BACKWARD-COMPATIBLE: a workspace with no currency master behaves exactly as before
(rate 1, base == transaction). Workspace-scoped (``TenantModel`` + RLS migration 0002).
"""
from django.db import models

from apps.core.models import TenantModel

RATE = {"max_digits": 20, "decimal_places": 8, "default": 1}

RATE_TYPES = [("spot", "Spot"), ("average", "Average"), ("closing", "Closing"),
              ("historical", "Historical")]


class Currency(TenantModel):
    """A currency the workspace transacts in. Exactly one row per workspace has ``is_base=True``."""

    code = models.CharField(max_length=3)                # ISO-4217 (USD/EUR/KES)
    name = models.CharField(max_length=64, blank=True)
    symbol = models.CharField(max_length=8, blank=True)
    decimal_places = models.PositiveSmallIntegerField(default=2)
    is_base = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "currencies"
        unique_together = [("workspace_id", "code")]
        indexes = [
            models.Index(fields=["workspace_id", "code"]),
            models.Index(fields=["workspace_id", "is_base"]),
        ]

    def __str__(self):
        return self.code


class ExchangeRate(TenantModel):
    """The rate to convert 1 unit of ``from_currency`` into ``to_currency`` on/after
    ``effective_date``. The most-recent rate on or before a date is used."""

    from_currency = models.CharField(max_length=3)
    to_currency = models.CharField(max_length=3)
    rate = models.DecimalField(**RATE)
    rate_type = models.CharField(max_length=12, choices=RATE_TYPES, default="spot")
    effective_date = models.DateField(null=True, blank=True)     # null → always
    is_active = models.BooleanField(default=True)
    created_by = models.UUIDField(null=True, blank=True)

    class Meta:
        db_table = "exchange_rates"
        indexes = [
            models.Index(fields=["workspace_id", "from_currency", "to_currency", "effective_date"]),
        ]

    def __str__(self):
        return f"{self.from_currency}->{self.to_currency} @ {self.rate}"
