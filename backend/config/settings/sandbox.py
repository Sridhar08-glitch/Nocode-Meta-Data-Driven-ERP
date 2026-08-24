"""Sandbox run settings — real PostgreSQL data, dev conveniences.

Used for local browser validation / screenshots. Connects to the PostgreSQL
`erp` database (via DATABASE_URL from .env) so the running app serves the real
demo workspace/users, while keeping in-process channels/cache and eager Celery
so no extra broker wiring is required for a manual run.
"""

from .base import *  # noqa: F401, F403

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]

# DATABASES inherited from base (reads DATABASE_URL → PostgreSQL `erp`).

# In-process infra so a bare `runserver` needs no extra services beyond PG.
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# Workflows/notifications run through Celery. Set NEXUS_EAGER=1 to run tasks inline
# (no worker needed); otherwise tasks route to Redis and a real `celery worker` must
# be running — which is what lets multi-step workflows actually complete.
import os as _os  # noqa: E402

if _os.environ.get("NEXUS_EAGER") == "1":
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
else:
    CELERY_TASK_ALWAYS_EAGER = False
