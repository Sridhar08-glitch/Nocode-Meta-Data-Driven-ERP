"""
ONE-TIME TENANT BOOTSTRAP — runs EXACTLY ONCE for the whole simulation.

Scope of the approved ORM exception (nothing else):
  * 1 Workspace
  * 1 initial administrator user (owner)
  * 1 WorkspaceMember (owner, active)
  * email-verification state (is_verified=True on the admin)
  * auth bootstrap to obtain API access

Why ORM: NexusERP exposes NO public UI page, NO REST endpoint, and NO
service-layer function to create a Workspace or WorkspaceMember. Proof:
  - OpenAPI (479 paths): /api/v1/workspaces/ is GET-only; no create/invite.
  - Frontend route scan: no create-workspace / onboarding page.
  - grep of all non-test code: no Workspace.objects.create / WorkspaceService.
The canonical creation pattern lives only in integration/acceptance test
conftests (Workspace.objects.create + WorkspaceMember.objects.create).

AFTER this script, the DB is NEVER written directly again for ANY business data.
"""
import os, sys, django, json
sys.path.insert(0, "E:/erp/backend")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.sim")
django.setup()

from django.utils import timezone
from apps.accounts.models import User
from apps.tenancy.models import Workspace, WorkspaceMember

WS_NAME = "Nexus Manufacturing & Trading Group"
WS_SLUG = "nexus-mtg"
PW = "NexusSim!2026"
ADMIN_EMAIL = "ceo@nexus.test"

owner, created = User.objects.get_or_create(
    email=ADMIN_EMAIL,
    defaults=dict(full_name="Aria Khan (CEO / System Administrator)",
                  is_verified=True, is_active=True, is_staff=True),
)
if created:
    owner.set_password(PW)
owner.is_staff = True; owner.is_verified = True; owner.is_active = True
owner.set_password(PW); owner.save()

ws, _ = Workspace.objects.get_or_create(
    slug=WS_SLUG,
    defaults=dict(name=WS_NAME, plan="enterprise", is_active=True, owner=owner,
                  max_members=999, max_entities=9999, max_records=10_000_000,
                  max_storage_bytes=10 * 1024**3),
)
ws.name = WS_NAME; ws.plan = "enterprise"; ws.owner = owner
ws.max_members = 999; ws.max_entities = 9999; ws.max_records = 10_000_000; ws.save()

WorkspaceMember.objects.get_or_create(
    workspace=ws, user=owner,
    defaults=dict(role="owner", status="active", joined_at=timezone.now()),
)

state = {
    "workspace_slug": WS_SLUG, "workspace_id": str(ws.id), "workspace_name": WS_NAME,
    "password": PW, "admin_email": ADMIN_EMAIL,
    "objects_created": ["Workspace:%s" % ws.id, "User:%s" % owner.id,
                        "WorkspaceMember(owner,active)"],
    "ts": timezone.now().isoformat(),
}
with open("E:/erp/sim/state/roster.json", "w") as f:
    json.dump(state, f, indent=2)
print("OK", ws.slug, ws.id, "| admin", owner.email, "staff", owner.is_staff,
      "verified", owner.is_verified, "| members",
      WorkspaceMember.objects.filter(workspace=ws).count())
