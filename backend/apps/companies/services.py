"""
Company platform services (F11).

``CompanyService`` — the shared entry point for legal entities: create companies, the workspace default
company (the ``company_id=NULL`` semantics), the group tree (``members``), and temporal ownership
(``ownership_pct_at`` → minority interest). Package-independent; every package references companies via
this, none redefines "organization".
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from django.utils import timezone

from .models import Company, CompanyOwnership, CompanyTaxRegistration


class CompanyError(Exception):  # noqa: N818 — domain error
    pass


def _uid(actor_id):
    return uuid.UUID(str(actor_id)) if actor_id else None


class CompanyService:
    @staticmethod
    def ensure_company(*, workspace_id, code, name="", functional_currency="", parent_code="",
                       is_group=False, is_elimination=False, is_default=False,
                       legal_registration="", actor_id=None) -> Company:
        parent = None
        if parent_code:
            parent = Company.objects.filter(workspace_id=workspace_id, code=parent_code).first()
        company, _ = Company.objects.get_or_create(
            workspace_id=workspace_id, code=str(code),
            defaults={"name": name or code, "functional_currency": functional_currency,
                      "parent": parent, "is_group": is_group, "is_elimination": is_elimination,
                      "is_default": is_default, "legal_registration": legal_registration,
                      "created_by": _uid(actor_id)})
        return company

    @staticmethod
    def ensure_default_company(*, workspace_id, actor_id=None) -> Company:
        """Idempotently return the workspace DEFAULT company (the entity that ``company_id=NULL``
        journals belong to). Finance provisioning calls this so every finance workspace has an
        explicit default legal entity available for consolidation membership."""
        existing = Company.objects.filter(workspace_id=workspace_id, is_default=True).first()
        if existing is not None:
            return existing
        return CompanyService.ensure_company(
            workspace_id=workspace_id, code="DEFAULT", name="Default Company", is_default=True,
            actor_id=actor_id)

    @staticmethod
    def add_tax_registration(*, workspace_id, company_code, tax_type="vat", authority="",
                             jurisdiction="", registration_number="", effective_from=None,
                             effective_to=None, actor_id=None) -> CompanyTaxRegistration:
        company = Company.objects.filter(workspace_id=workspace_id, code=company_code).first()
        if company is None:
            raise CompanyError("Company not found.")
        return CompanyTaxRegistration.objects.create(
            workspace_id=workspace_id, company=company, tax_type=tax_type, authority=authority,
            jurisdiction=jurisdiction, registration_number=registration_number,
            effective_from=effective_from, effective_to=effective_to, created_by=_uid(actor_id))

    @staticmethod
    def members(workspace_id, group_id) -> list[Company]:
        """Operating (non-group, non-elimination) descendant companies under a group node."""
        by_parent: dict = {}
        for c in Company.objects.filter(workspace_id=workspace_id, is_active=True):
            by_parent.setdefault(c.parent_id, []).append(c)
        root = Company.objects.filter(workspace_id=workspace_id, id=group_id).first()
        if root is None:
            return []
        out, stack = [], [root]
        while stack:
            node = stack.pop()
            if node.id != root.id and not node.is_group and not node.is_elimination:
                out.append(node)
            stack.extend(by_parent.get(node.id, []))
        return out

    @staticmethod
    def set_ownership(*, workspace_id, parent_code, subsidiary_code, ownership_pct,
                      effective_from=None, effective_to=None, actor_id=None) -> CompanyOwnership:
        parent = Company.objects.filter(workspace_id=workspace_id, code=parent_code).first()
        sub = Company.objects.filter(workspace_id=workspace_id, code=subsidiary_code).first()
        if parent is None or sub is None:
            raise CompanyError("Parent or subsidiary company not found.")
        if parent.id == sub.id:
            raise CompanyError("A company cannot own itself.")
        return CompanyOwnership.objects.create(
            workspace_id=workspace_id, parent_company=parent, subsidiary=sub,
            ownership_pct=Decimal(str(ownership_pct)), effective_from=effective_from,
            effective_to=effective_to, created_by=_uid(actor_id))

    @staticmethod
    def ownership_pct_at(workspace_id, subsidiary_id, *, on_date=None) -> Decimal:
        """The parent's ownership % of a subsidiary effective on a date (100 if none recorded)."""
        day = on_date or timezone.now().date()
        best = None
        for o in CompanyOwnership.objects.filter(
                workspace_id=workspace_id, subsidiary_id=subsidiary_id, is_active=True):
            if o.effective_from and o.effective_from > day:
                continue
            if o.effective_to and o.effective_to < day:
                continue
            if best is None or (o.effective_from or _MIN) >= (best.effective_from or _MIN):
                best = o
        return Decimal(str(best.ownership_pct)) if best is not None else Decimal("100")


_MIN = __import__("datetime").date.min
