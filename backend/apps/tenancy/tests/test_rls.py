import uuid

import pytest
from django.db import connection

from apps.tenancy import rls


@pytest.mark.django_db
class TestRlsHelper:
    def test_set_get_clear(self):
        ws = uuid.uuid4()
        applied = rls.set_workspace(ws)
        if connection.vendor == "postgresql":
            assert applied is True
            assert rls.get_current_workspace() == str(ws)
            rls.clear_workspace()
            assert rls.get_current_workspace() is None
        else:
            # SQLite: helpers are inert no-ops, never raising.
            assert applied is False
            assert rls.get_current_workspace() is None

    def test_context_manager_sets_and_restores(self):
        ws = uuid.uuid4()
        with rls.workspace_context(ws):
            if connection.vendor == "postgresql":
                assert rls.get_current_workspace() == str(ws)
        # Cleared on exit
        assert rls.get_current_workspace() is None

    def test_context_manager_clears_on_exception(self):
        ws = uuid.uuid4()
        with pytest.raises(ValueError), rls.workspace_context(ws):
            raise ValueError("boom")
        assert rls.get_current_workspace() is None
