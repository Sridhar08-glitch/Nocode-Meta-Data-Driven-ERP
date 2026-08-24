"""
Test settings — always SQLite, fast, fully isolated.

Never reads the .env DATABASE_URL; always uses a file-based SQLite
so migrations apply cleanly and there is no network dependency.
"""
import os
import tempfile

from .base import *  # noqa: F401, F403, E402

# OS-agnostic temp path: tempfile.gettempdir() resolves to /tmp on POSIX and
# %TEMP% on Windows, so the file-based test DB works on every host.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(tempfile.gettempdir(), "nexus_test.sqlite3"),
    }
}

# Faster password hashing in tests
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Rate limiting is disabled by default so it never contaminates unrelated tests
# (shared locmem cache + identical client IP). The dedicated rate-limit test
# re-enables it via override_settings.
RATELIMIT_ENABLE = False

# Login lockout disabled by default in tests (shared cache + identical IP would
# contaminate unrelated login tests); the dedicated lockout test re-enables it.
LOGIN_LOCKOUT_ENABLED = False

# Suppress email sends
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# ── Celery ──────────────────────────────────────────────────────────────────
# Run tasks synchronously so command bus tests work without a broker.
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
# Use in-memory cache backend so result storage never touches Redis.
CELERY_RESULT_BACKEND = "cache+memory://"
CELERY_BROKER_URL = "memory://"
# Ignore task results entirely — nothing in tests cares about stored results.
CELERY_TASK_IGNORE_RESULT = True

# No Redis needed for channels
CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
