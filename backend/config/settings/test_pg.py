"""
PostgreSQL test settings — same as ``test`` but against a real PostgreSQL backend.

pytest-django creates/drops a throwaway ``test_erp`` database; the production ``erp``
database is never touched. Use with::

    pytest --ds=config.settings.test_pg

This exercises the PostgreSQL-only paths that SQLite cannot: RLS policies, JSONB
casts, ``::uuid``/``::timestamptz`` placeholders, tsvector FTS, and DDL semantics.
"""
import os

from .test import *  # noqa: F401, F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("NEXUS_PG_DB", "erp"),
        "USER": os.environ.get("NEXUS_PG_USER", "postgres"),
        "PASSWORD": os.environ.get("NEXUS_PG_PASSWORD", "holora"),
        "HOST": os.environ.get("NEXUS_PG_HOST", "localhost"),
        "PORT": os.environ.get("NEXUS_PG_PORT", "5432"),
    }
}
