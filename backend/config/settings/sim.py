"""Simulation / acceptance-test RUN PROFILE — operational config ONLY.

No ERP/business logic. Identical stack to base (real PostgreSQL + real Redis
broker + Celery worker + Channels); the ONLY differences are:
  * points at an ISOLATED database `nexus_sim` (never production `erp`)
  * DEBUG on + localhost/testserver allowed hosts
Tasks are NOT eager: a real Celery worker consumes from Redis so Celery,
the queue, retries and Channels are all genuinely exercised.
"""

import os

os.environ.setdefault(
    "DATABASE_URL", "postgresql://postgres:holora@localhost:5432/nexus_sim"
)

from .base import *  # noqa: F401,F403,E402

DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver", "0.0.0.0"]
