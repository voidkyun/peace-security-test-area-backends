# Generated manually for Issue #11.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("audit", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="auditevent",
            name="request_id",
            field=models.CharField(db_index=True, default="", max_length=64),
            preserve_default=False,
        ),
    ]
