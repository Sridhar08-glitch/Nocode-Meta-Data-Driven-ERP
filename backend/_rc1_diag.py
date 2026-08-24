import os, django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.base")
django.setup()
from django.db import connection
with connection.cursor() as c:
    c.execute("SELECT column_name FROM information_schema.columns WHERE table_name=%s ORDER BY ordinal_position", ["number_sequences"])
    cols = [r[0] for r in c.fetchall()]
    print("number_sequences columns:", cols)
    print("has initialized:", "initialized" in cols)
    c.execute("SELECT name FROM django_migrations WHERE app=%s ORDER BY id", ["numbering"])
    print("numbering migrations recorded applied:", [r[0] for r in c.fetchall()])
    c.execute("SELECT current_user, (SELECT rolsuper FROM pg_roles WHERE rolname=current_user)")
    print("connected as / superuser:", c.fetchone())
