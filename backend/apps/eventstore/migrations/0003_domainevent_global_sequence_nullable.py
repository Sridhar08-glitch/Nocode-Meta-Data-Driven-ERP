"""
Make global_sequence nullable so Django can INSERT NULL and let the
PostgreSQL BEFORE INSERT trigger populate it from the sequence.

In SQLite (test env): DomainEvent.save() computes the value before INSERT,
so null=True is never actually stored — it just avoids the column-level
NOT NULL constraint that prevented saving in the previous schema.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("eventstore", "0002_domainevent_version"),
    ]

    operations = [
        migrations.AlterField(
            model_name="domainevent",
            name="global_sequence",
            field=models.BigIntegerField(
                blank=True,
                db_index=True,
                editable=False,
                null=True,
                unique=True,
            ),
        ),
    ]
