"""
Platform capability test: the ``action_generate_document`` workflow step.

CORE platform test (not a package test). Proves the generic, metadata-driven document step
renders a DocumentTemplate to PDF and attaches it to a record by reusing the render engine +
document store (audit/event-store), is idempotent, and respects workspace isolation. No industry
package is referenced.
"""
import uuid
from types import SimpleNamespace

import pytest

from apps.document_templates.models import DocumentTemplate
from apps.documents.models import Document
from apps.metadata.models import EntityDefinition
from apps.records.services import RecordService
from apps.schema_registry.services import SchemaRegistryService
from apps.solution_templates.documents import system_member
from apps.workflows.executors import ExecutorError, exec_generate_document


def _run(ws, record_id=None, actor=None):
    return SimpleNamespace(workspace_id=ws, initiated_by=actor or uuid.uuid4(),
                           record_id=record_id, id=uuid.uuid4())


def _step(config):
    return SimpleNamespace(config=config)


@pytest.fixture
def setup(db):
    ws = uuid.uuid4()
    SchemaRegistryService.create_entity(
        workspace_id=ws, slug="thing", name="Thing", plural_name="Things",
        fields=[{"slug": "name", "name": "Name", "field_type": "text", "is_promoted": True}],
        created_by=None)
    DocumentTemplate.objects.create(
        workspace_id=ws, slug="thing_doc", name="Thing Doc", entity_slug="thing",
        page_config={"title": "Thing"}, blocks=[{"field": "name", "label": "Name"}],
        is_active=True)
    member = system_member(None)
    entity = EntityDefinition.objects.get(workspace_id=ws, slug="thing")
    rec = RecordService.create_record(workspace_id=ws, member=member, entity=entity,
                                      data={"name": "Acme"})
    return ws, member, rec["id"]


@pytest.mark.django_db
def test_generates_and_attaches_pdf(setup):
    ws, member, rid = setup
    out = exec_generate_document(
        _step({"template_slug": "thing_doc", "record_id": rid, "filename": "thing.pdf"}),
        _run(ws, record_id=rid), {}, member)
    assert out["generated"] is True
    doc = Document.objects.get(id=out["document_id"])
    assert doc.workspace_id == ws
    assert str(doc.record_id) == str(rid)
    assert doc.mime_type == "application/pdf"
    assert doc.name == "thing.pdf"
    assert doc.size_bytes > 0


@pytest.mark.django_db
def test_idempotent_never_duplicates(setup):
    ws, member, rid = setup
    cfg = {"template_slug": "thing_doc", "record_id": rid, "filename": "card.pdf"}
    first = exec_generate_document(_step(cfg), _run(ws, record_id=rid), {}, member)
    second = exec_generate_document(_step(cfg), _run(ws, record_id=rid), {}, member)
    assert first["generated"] is True
    assert second["generated"] is False and second["reason"] == "already_generated"
    assert second["document_id"] == first["document_id"]
    assert Document.objects.filter(workspace_id=ws, name="card.pdf").count() == 1


@pytest.mark.django_db
def test_uses_trigger_record_when_no_record_id(setup):
    ws, member, rid = setup
    out = exec_generate_document(
        _step({"template_slug": "thing_doc"}), _run(ws, record_id=rid), {}, member)
    assert out["generated"] is True   # record_id resolved from run.record_id


@pytest.mark.django_db
def test_context_record_id_resolution(setup):
    ws, member, rid = setup
    # record_id is resolved from the run context via {{record.id}} (whole-string template)
    out = exec_generate_document(
        _step({"template_slug": "thing_doc", "record_id": "{{record.id}}",
               "filename": "ctx.pdf"}),
        _run(ws), {"record": {"id": str(rid), "name": "Acme"}}, member)
    assert out["generated"] is True
    doc = Document.objects.get(id=out["document_id"])
    assert str(doc.record_id) == str(rid)


@pytest.mark.django_db
def test_missing_template_raises(setup):
    ws, member, rid = setup
    with pytest.raises(ExecutorError):
        exec_generate_document(
            _step({"template_slug": "ghost", "record_id": rid}), _run(ws), {}, member)


@pytest.mark.django_db
def test_missing_template_slug_raises(setup):
    ws, member, rid = setup
    with pytest.raises(ExecutorError):
        exec_generate_document(_step({}), _run(ws, record_id=rid), {}, member)


@pytest.mark.django_db
def test_no_record_returns_skip(setup):
    ws, member, rid = setup
    out = exec_generate_document(_step({"template_slug": "thing_doc"}), _run(ws), {}, member)
    assert out == {"generated": False, "reason": "no_record"}


@pytest.mark.django_db
def test_workspace_isolation(setup):
    ws, member, rid = setup
    other = uuid.uuid4()
    # the template lives in ws, not in `other` → not found from the other workspace
    with pytest.raises(ExecutorError):
        exec_generate_document(
            _step({"template_slug": "thing_doc", "record_id": rid}),
            _run(other, record_id=rid), {}, member)


@pytest.mark.django_db
def test_registered():
    from apps.workflows.executors import REGISTRY
    assert REGISTRY["action_generate_document"] is exec_generate_document
    assert REGISTRY["generate_document"] is exec_generate_document
