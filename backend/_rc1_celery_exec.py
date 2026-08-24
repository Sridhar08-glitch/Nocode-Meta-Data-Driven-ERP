import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings._rc1_live")
django.setup()
from apps.projections.tasks import health_check
r = health_check.delay()
print("enqueued task id:", r.id)
try:
    out = r.get(timeout=30)
    print("WORKER EXECUTED -> result:", out)
except Exception as e:
    print("FAILED to get result:", repr(e))
