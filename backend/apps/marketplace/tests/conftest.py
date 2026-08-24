"""Shared fixtures for marketplace tests."""
import hashlib
import json

import pytest
from rest_framework.test import APIClient

from apps.accounts import tokens
from apps.accounts.models import User
from apps.marketplace.models import MarketplacePlugin, PluginVersion
from apps.tenancy.models import Workspace, WorkspaceMember

PW = "Sup3rStr0ng!pw"


def make_manifest(*, extra_field=False):
    fields = [{"slug": "subject", "name": "Subject", "field_type": "text",
               "is_promoted": True, "is_required": True},
              {"slug": "priority", "name": "Priority", "field_type": "text",
               "is_promoted": True}]
    if extra_field:
        fields.append({"slug": "category", "name": "Category", "field_type": "text",
                       "is_promoted": True})
    return {
        "schema_version": 1,
        "entities": [{"slug": "ticket", "name": "Ticket", "plural_name": "Tickets",
                      "fields": fields}],
        "workflows": [{"slug": "notify", "name": "Notify", "trigger_type": "record_created",
                       "entity_slug": "ticket",
                       "steps": [{"slug": "s1", "step_type": "action_send_notification",
                                  "name": "Notify", "is_entry": True}],
                       "edges": []}],
        "rules": [{"slug": "auto_high", "name": "Auto High", "entity_slug": "ticket",
                   "trigger_on": "before_create", "condition_nql": 'priority = "high"',
                   "actions": [{"type": "set_field", "field": "priority", "value": "high"}]}],
        "notification_templates": [{"slug": "ticket_created", "name": "Ticket Created",
                                    "channels": ["in_app"], "subject_template": "New ticket",
                                    "body_template": "A ticket was created."}],
        "permissions": [{"slug": "ticket_manage", "name": "Manage Tickets",
                         "description": "Manage tickets"}],
    }


@pytest.fixture
def ws(db):
    return Workspace.objects.create(name="Acme", slug="acme", is_active=True)


@pytest.fixture
def user(ws):
    return User.objects.create_user(email="mk@acme.com", password=PW, is_verified=True)


@pytest.fixture
def member(ws, user):
    return WorkspaceMember.objects.create(
        workspace=ws, user=user, role="admin", status="active")


@pytest.fixture
def client(ws, user, member):
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(user)}",
                  HTTP_X_WORKSPACE_SLUG=ws.slug)
    return c


@pytest.fixture
def staff_client(db):
    u = User.objects.create_user(email="pub@nexus.com", password=PW, is_verified=True)
    u.is_staff = True
    u.save(update_fields=["is_staff"])
    c = APIClient()
    c.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.issue_access_token(u)}")
    return c


def _make_version(plugin, version, manifest):
    return PluginVersion.objects.create(
        plugin_id=plugin.id, version=version, manifest=manifest,
        manifest_hash=hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
        is_published=True)


@pytest.fixture
def plugin(db):
    p = MarketplacePlugin.objects.create(
        slug="helpdesk", name="Helpdesk", tagline="Support tickets",
        description="A helpdesk plugin", category="support", status="published",
        publisher_name="Nexus", latest_version="1.0.0")
    v = _make_version(p, "1.0.0", make_manifest())
    return p, v
