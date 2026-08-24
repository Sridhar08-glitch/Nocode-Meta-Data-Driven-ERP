"""
Portal scoped-data service (Phase 1.34).

Portal users read/write ONLY records linked to them. The link is enforced **server-side**:
every query AND-injects ``{link_field} = portal_user.linked_record_id`` (from the matching
:class:`PortalEntityGrant`), so a portal user can never reach another user's rows via any
filter they pass. This is a separate permission layer from workspace RBAC.
"""
from __future__ import annotations

from apps.nql.services import execute_nql
from apps.records import dal
from apps.records.services import resolve_entity

from .models import PortalEntityGrant


class PortalAccessError(Exception):  # noqa: N818 — domain error
    pass


class PortalNotFound(Exception):  # noqa: N818 — domain error
    pass


def _grant(workspace_id, entity_slug, portal_type) -> PortalEntityGrant:
    """The most specific grant for this entity + portal type, or raise PortalAccessError."""
    grant = (PortalEntityGrant.objects
             .filter(workspace_id=workspace_id, entity_slug=entity_slug, portal_type=portal_type)
             .first()
             or PortalEntityGrant.objects
             .filter(workspace_id=workspace_id, entity_slug=entity_slug, portal_type="")
             .first())
    if grant is None:
        raise PortalAccessError(f"Portal access to {entity_slug!r} is not granted.")
    return grant


def _link_value(portal_user, grant):
    """The value the grant's ``link_field`` must equal for this portal user.

    Direct scope (default): the portal user's own ``linked_record_id``. Indirect scope
    (``grant.link_source`` set): the value of ``link_source`` on the portal user's linked record
    — one hop through a parent (e.g. a student's ``school_class``). Resolved SERVER-SIDE from the
    user's own record, so it can never be spoofed. Returns None when it cannot be resolved (the
    caller then returns no rows — fail-closed)."""
    if not grant.link_source:
        return str(portal_user.linked_record_id)
    from apps.metadata.models import EntityDefinition
    subj_entity = EntityDefinition.objects.filter(
        workspace_id=portal_user.workspace_id, id=portal_user.linked_entity_id).first()
    if subj_entity is None:
        return None
    rows = execute_nql(
        workspace_id=portal_user.workspace_id, user_id=None,
        source={"entity": subj_entity.slug,
                "filter": {"field": "id", "op": "=", "value": str(portal_user.linked_record_id)}})
    if not rows:
        return None
    rec = dal.row_to_record(rows[0], dal.FieldMap(subj_entity))
    val = rec.get(grant.link_source)
    return str(val) if val not in (None, "") else None


def _scoped_rows(portal_user, entity, grant, extra_filter=None):
    """Run an NQL list query with the mandatory link filter AND-ed in."""
    value = _link_value(portal_user, grant)
    if value is None:
        return []   # indirect source unresolved → fail-closed (see nothing)
    link_cond = {"field": grant.link_field, "op": "=", "value": value}
    conds = [link_cond]
    if extra_filter:
        conds.append(extra_filter)
    query = {"entity": entity.slug,
             "filter": link_cond if len(conds) == 1 else {"op": "and", "conditions": conds}}
    rows = execute_nql(workspace_id=portal_user.workspace_id, source=query, user_id=None)
    fmap = dal.FieldMap(entity)
    return [dal.row_to_record(r, fmap) for r in rows]


class PortalDataService:
    @staticmethod
    def list_records(portal_user, entity_slug, *, extra_filter=None) -> list[dict]:
        grant = _grant(portal_user.workspace_id, entity_slug, portal_user.portal_type)
        if not grant.can_read:
            raise PortalAccessError(f"Reading {entity_slug!r} is not permitted.")
        if not portal_user.linked_record_id:
            return []   # not linked to any record → sees nothing
        entity = resolve_entity(portal_user.workspace_id, entity_slug)
        return _scoped_rows(portal_user, entity, grant, extra_filter)

    @staticmethod
    def retrieve_record(portal_user, entity_slug, record_id) -> dict:
        grant = _grant(portal_user.workspace_id, entity_slug, portal_user.portal_type)
        if not grant.can_read:
            raise PortalAccessError(f"Reading {entity_slug!r} is not permitted.")
        if not portal_user.linked_record_id:
            raise PortalNotFound("Record not found.")
        entity = resolve_entity(portal_user.workspace_id, entity_slug)
        rows = _scoped_rows(portal_user, entity, grant,
                            extra_filter={"field": "id", "op": "=", "value": str(record_id)})
        if not rows:
            raise PortalNotFound("Record not found.")   # not linked → indistinguishable from missing
        return rows[0]

    @staticmethod
    def create_record(portal_user, entity_slug, data: dict) -> dict:
        grant = _grant(portal_user.workspace_id, entity_slug, portal_user.portal_type)
        if not grant.can_create:
            raise PortalAccessError(f"Creating {entity_slug!r} is not permitted.")
        if not portal_user.linked_record_id:
            raise PortalAccessError("Portal user is not linked to a record.")
        entity = resolve_entity(portal_user.workspace_id, entity_slug)
        # Force the link field to the portal user's (resolved) scope — clients cannot spoof it.
        value = _link_value(portal_user, grant)
        if value is None:
            raise PortalAccessError("Portal user scope could not be resolved.")
        payload = dict(data)
        payload[grant.link_field] = value
        member = _PortalActor(portal_user)
        from apps.records.services import RecordService
        return RecordService.create_record(
            workspace_id=portal_user.workspace_id, member=member, entity=entity, data=payload)


class _PortalActor:
    """Minimal member-like actor so RecordService can run a portal-originated create
    (rules / computed fields / events). The real gate is the PortalEntityGrant
    (checked before this is used) plus the forced link field; workspace RBAC is
    satisfied with a baseline role so the shared write path executes."""
    role = "member"

    def __init__(self, portal_user):
        self.user_id = portal_user.id
        self.id = portal_user.id
        self.custom_role_id = None
