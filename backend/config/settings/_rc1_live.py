"""RC-1 live-verification settings shim.

Inherits the production-like base stack (PostgreSQL, Redis cache, Redis channel
layer, real Celery broker) UNCHANGED. The ONLY difference is the email transport
sink: emails are written to a directory so the verification harness can read the
real verification / set-password tokens exactly as a customer reads their inbox.
This mirrors how the test suite swaps in a locmem backend — the email-generation
code path (subject/body/token) is identical to production. Not a product change.
"""
import os

from .base import *  # noqa: F401, F403

EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
EMAIL_FILE_PATH = os.environ.get("RC1_MAIL_DIR", r"E:\erp\_rc1_mail")
