"""
Add `version` field to DomainEvent.

`version` records the aggregate's version number AFTER this event is applied.
Used for optimistic concurrency (expected_version checks in CommandBus) and
aggregate replay ordering when replaying from the event store.

Distinct from `event_version` which is the schema version of the event *type*
(used for upcasting — incrementing when the payload shape changes).
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("eventstore", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="domainevent",
            name="version",
            field=models.BigIntegerField(default=1, db_index=True),
        ),
        migrations.AddIndex(
            model_name="domainevent",
            index=models.Index(
                fields=["workspace_id", "aggregate_type", "aggregate_id", "version"],
                name="domainevent_ws_agg_version_idx",
            ),
        ),
    ]
