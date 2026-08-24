"""Config VCS — commit / diff / rollback (master spec §26)."""
import uuid

import pytest

from apps.config_vcs import services as cvcs
from apps.schema_registry.services import SchemaRegistryService


@pytest.fixture
def ws(db):
    w = uuid.uuid4()
    SchemaRegistryService.create_entity(workspace_id=w, slug="lead", name="Lead", plural_name="Leads")
    return w


@pytest.mark.django_db
class TestConfigVCS:
    def test_commit_diff_rollback(self, ws):
        c1 = cvcs.commit(workspace_id=ws, message="init")
        SchemaRegistryService.update_entity(workspace_id=ws, slug="lead", updates={"name": "Prospect"})
        c2 = cvcs.commit(workspace_id=ws, message="rename")
        assert c1.sha != c2.sha and c2.parent_sha == c1.sha

        d = cvcs.diff_commits(workspace_id=ws, sha_a=c1.sha, sha_b=c2.sha)
        assert len(d["entities"]["modified"]) == 1

        cvcs.rollback(workspace_id=ws, sha=c1.sha)
        from apps.metadata.models import EntityDefinition
        assert EntityDefinition.objects.get(workspace_id=ws, slug="lead").name == "Lead"

    def test_no_change_commit_rejected(self, ws):
        cvcs.commit(workspace_id=ws, message="init")
        with pytest.raises(cvcs.ConfigVCSError):
            cvcs.commit(workspace_id=ws, message="again")   # nothing changed

    def test_list_commits(self, ws):
        cvcs.commit(workspace_id=ws, message="c1")
        SchemaRegistryService.update_entity(workspace_id=ws, slug="lead", updates={"name": "X"})
        cvcs.commit(workspace_id=ws, message="c2")
        commits = cvcs.list_commits(workspace_id=ws)
        assert len(commits) == 2
        assert {c.message for c in commits} == {"c1", "c2"}
