"""
LocalizationService (PROJECT_HANDBOOK.md §32.2).

Per-workspace locale settings (validated against BCP-47 / IANA tz / ISO 4217),
plus translations = system ``TranslationKey`` defaults merged with workspace
``TranslationOverride`` (cached per workspace+locale), and entity/field label
translations.
"""
from __future__ import annotations

import re
from zoneinfo import available_timezones

from django.core.cache import cache

from .models import (
    EntityLabelTranslation,
    TranslationKey,
    TranslationOverride,
    WorkspaceLocale,
)

_LOCALE_RE = re.compile(r"^[a-z]{2,3}(-[A-Z]{2})?$")
_CACHE_TTL = 300
# A practical ISO 4217 subset; extend as needed.
_CURRENCIES = {
    "USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD", "CNY", "INR", "BRL",
    "ZAR", "SEK", "NOK", "DKK", "PLN", "RUB", "TRY", "MXN", "SGD", "HKD", "AED",
    "SAR", "KRW", "THB", "IDR", "MYR", "PHP", "CZK", "HUF", "ILS", "NGN", "KES",
}
_TZS = available_timezones()


class LocalizationError(Exception):  # noqa: N818 — domain error
    pass


def _cache_key(workspace_id, locale):
    return f"i18n:{workspace_id}:{locale}"


class LocalizationService:
    @staticmethod
    def get_locale(workspace_id) -> WorkspaceLocale:
        obj, _ = WorkspaceLocale.objects.get_or_create(workspace_id=workspace_id)
        return obj

    @staticmethod
    def set_locale(workspace_id, data: dict) -> WorkspaceLocale:
        obj = LocalizationService.get_locale(workspace_id)
        if "default_locale" in data and not _LOCALE_RE.match(data["default_locale"] or ""):
            raise LocalizationError(f"Invalid locale tag: {data.get('default_locale')!r}")
        if "default_timezone" in data and data["default_timezone"] not in _TZS:
            raise LocalizationError(f"Unknown timezone: {data.get('default_timezone')!r}")
        if "default_currency" in data and data["default_currency"] not in _CURRENCIES:
            raise LocalizationError(f"Unknown currency: {data.get('default_currency')!r}")
        if "enabled_locales" in data:
            for loc in data["enabled_locales"] or []:
                if not _LOCALE_RE.match(loc):
                    raise LocalizationError(f"Invalid locale tag: {loc!r}")
        for key in ("default_locale", "default_timezone", "default_currency",
                    "enabled_locales", "date_format", "time_format",
                    "number_decimal_separator", "number_thousands_separator"):
            if key in data:
                setattr(obj, key, data[key])
        obj.save()
        return obj

    @staticmethod
    def get_translations(workspace_id, locale, namespace=None) -> dict:
        cache_key = _cache_key(workspace_id, locale) + (f":{namespace}" if namespace else "")
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
        keys = TranslationKey.objects.all()
        if namespace:
            keys = keys.filter(namespace=namespace)
        merged = {f"{k.namespace}.{k.key}": k.default_value for k in keys}
        key_ids = {str(k.id): f"{k.namespace}.{k.key}" for k in keys}
        overrides = TranslationOverride.objects.filter(
            workspace_id=workspace_id, locale=locale, key_id__in=list(key_ids.keys()))
        for ov in overrides:
            flat = key_ids.get(str(ov.key_id))
            if flat:
                merged[flat] = ov.value
        cache.set(cache_key, merged, _CACHE_TTL)
        return merged

    @staticmethod
    def set_override(workspace_id, key_id, locale, value, updated_by=None) -> TranslationOverride:
        if not _LOCALE_RE.match(locale or ""):
            raise LocalizationError(f"Invalid locale tag: {locale!r}")
        if not TranslationKey.objects.filter(id=key_id).exists():
            raise LocalizationError("Unknown translation key")
        obj, _ = TranslationOverride.objects.update_or_create(
            workspace_id=workspace_id, key_id=key_id, locale=locale,
            defaults={"value": value, "updated_by": updated_by})
        LocalizationService._invalidate(workspace_id, locale)
        return obj

    @staticmethod
    def remove_override(workspace_id, key_id, locale) -> int:
        deleted, _ = TranslationOverride.objects.filter(
            workspace_id=workspace_id, key_id=key_id, locale=locale).delete()
        LocalizationService._invalidate(workspace_id, locale)
        return deleted

    @staticmethod
    def _invalidate(workspace_id, locale):
        # Bump both the bare and namespaced cache entries (namespaced ones expire by TTL).
        cache.delete(_cache_key(workspace_id, locale))

    @staticmethod
    def set_entity_label(workspace_id, *, entity_id=None, field_id=None, locale,
                         singular="", plural="") -> EntityLabelTranslation:
        if bool(entity_id) == bool(field_id):
            raise LocalizationError("Exactly one of entity_id or field_id must be set")
        if not _LOCALE_RE.match(locale or ""):
            raise LocalizationError(f"Invalid locale tag: {locale!r}")
        obj, _ = EntityLabelTranslation.objects.update_or_create(
            workspace_id=workspace_id, locale=locale, entity_id=entity_id, field_id=field_id,
            defaults={"singular": singular, "plural": plural})
        return obj

    @staticmethod
    def list_entity_labels(workspace_id, locale=None):
        qs = EntityLabelTranslation.objects.filter(workspace_id=workspace_id)
        if locale:
            qs = qs.filter(locale=locale)
        return qs
