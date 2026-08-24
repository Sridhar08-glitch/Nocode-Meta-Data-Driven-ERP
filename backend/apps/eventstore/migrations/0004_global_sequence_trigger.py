"""
Create the PostgreSQL sequence + BEFORE INSERT trigger that populates
``domain_events.global_sequence`` — the total-order key the projection runner
and event replay depend on.

DomainEvent.save() and the model docstring already assume this trigger exists, but
no prior migration created it, so on PostgreSQL global_sequence was left NULL
(SQLite computes it in save() instead). This migration closes that gap.

No-op on SQLite.
"""
from django.db import migrations

FORWARD_SQL = """
CREATE SEQUENCE IF NOT EXISTS domain_event_global_seq;

CREATE OR REPLACE FUNCTION set_domain_event_global_seq()
RETURNS trigger AS $$
BEGIN
    IF NEW.global_sequence IS NULL THEN
        NEW.global_sequence := nextval('domain_event_global_seq');
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_domain_event_global_seq ON domain_events;
CREATE TRIGGER trg_domain_event_global_seq
    BEFORE INSERT ON domain_events
    FOR EACH ROW EXECUTE FUNCTION set_domain_event_global_seq();
"""

REVERSE_SQL = """
DROP TRIGGER IF EXISTS trg_domain_event_global_seq ON domain_events;
DROP FUNCTION IF EXISTS set_domain_event_global_seq();
DROP SEQUENCE IF EXISTS domain_event_global_seq;
"""


def forward(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(FORWARD_SQL)


def reverse(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    schema_editor.execute(REVERSE_SQL)


class Migration(migrations.Migration):
    dependencies = [
        ("eventstore", "0003_domainevent_global_sequence_nullable"),
    ]
    operations = [migrations.RunPython(forward, reverse)]
