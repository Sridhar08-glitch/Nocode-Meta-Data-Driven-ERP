"""LocalizationService + API (PROJECT_HANDBOOK.md §32.2 / §32.4)."""
import uuid

import pytest

from apps.localization.services import LocalizationError, LocalizationService

BASE = "/api/v1/localization"


@pytest.mark.django_db
class TestLocale:
    def test_valid_set(self, ws):
        obj = LocalizationService.set_locale(
            ws.id, {"default_locale": "fr-FR", "default_timezone": "Europe/Paris",
                    "default_currency": "EUR"})
        assert obj.default_locale == "fr-FR"

    def test_invalid_locale(self, ws):
        with pytest.raises(LocalizationError):
            LocalizationService.set_locale(ws.id, {"default_locale": "not_a_locale!"})

    def test_invalid_timezone(self, ws):
        with pytest.raises(LocalizationError):
            LocalizationService.set_locale(ws.id, {"default_timezone": "Mars/Phobos"})

    def test_invalid_currency(self, ws):
        with pytest.raises(LocalizationError):
            LocalizationService.set_locale(ws.id, {"default_currency": "ZZZ"})


@pytest.mark.django_db
class TestTranslations:
    def test_merge_and_override_precedence(self, ws, save_key):
        base = LocalizationService.get_translations(ws.id, "fr-FR")
        assert base["ui.button.save"] == "Save"   # system default
        LocalizationService.set_override(ws.id, save_key.id, "fr-FR", "Enregistrer")
        merged = LocalizationService.get_translations(ws.id, "fr-FR")
        assert merged["ui.button.save"] == "Enregistrer"   # override wins + cache invalidated

    def test_remove_override_reverts(self, ws, save_key):
        LocalizationService.set_override(ws.id, save_key.id, "fr-FR", "Enregistrer")
        LocalizationService.remove_override(ws.id, save_key.id, "fr-FR")
        assert LocalizationService.get_translations(ws.id, "fr-FR")["ui.button.save"] == "Save"


@pytest.mark.django_db
class TestEntityLabels:
    def test_xor_enforced(self, ws):
        eid, fid = uuid.uuid4(), uuid.uuid4()
        with pytest.raises(LocalizationError):
            LocalizationService.set_entity_label(ws.id, entity_id=eid, field_id=fid,
                                                 locale="fr-FR", singular="x")
        with pytest.raises(LocalizationError):
            LocalizationService.set_entity_label(ws.id, locale="fr-FR", singular="x")
        ok = LocalizationService.set_entity_label(ws.id, entity_id=eid, locale="fr-FR",
                                                  singular="Client", plural="Clients")
        assert ok.singular == "Client"


@pytest.mark.django_db
class TestApi:
    def test_locale_get_patch(self, client):
        assert client.get(f"{BASE}/locale/").status_code == 200
        r = client.patch(f"{BASE}/locale/", {"default_currency": "EUR"}, format="json")
        assert r.json()["default_currency"] == "EUR"

    def test_invalid_currency_400(self, client):
        assert client.patch(f"{BASE}/locale/", {"default_currency": "ZZZ"},
                            format="json").status_code == 400

    def test_translations_and_override(self, client, ws, save_key):
        body = client.get(f"{BASE}/translations/?locale=fr-FR").json()
        assert body["translations"]["ui.button.save"] == "Save"
        r = client.patch(f"{BASE}/translations/{save_key.id}/",
                         {"locale": "fr-FR", "value": "Enregistrer"}, format="json")
        assert r.json()["updated"] is True
        body2 = client.get(f"{BASE}/translations/?locale=fr-FR").json()
        assert body2["translations"]["ui.button.save"] == "Enregistrer"

    def test_keys_list(self, client, save_key):
        assert client.get(f"{BASE}/keys/").json()["count"] == 1

    def test_entity_label_both_set_400(self, client):
        r = client.post(f"{BASE}/entity-labels/",
                        {"entity_id": str(uuid.uuid4()), "field_id": str(uuid.uuid4()),
                         "locale": "fr-FR", "singular": "x"}, format="json")
        assert r.status_code == 400
