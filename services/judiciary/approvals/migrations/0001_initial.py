# Issue #10: Judiciary approvals (by=JUDICIARY)

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Approval",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("proposal_id", models.UUIDField(db_index=True, editable=False)),
                ("reason", models.TextField(default="", help_text="承認理由（20文字以上）")),
                ("references", models.JSONField(default=list, help_text="参照条文のリスト（1件以上）")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "verbose_name": "承認（司法）",
                "verbose_name_plural": "承認（司法）",
            },
        ),
        migrations.AddConstraint(
            model_name="approval",
            constraint=models.UniqueConstraint(fields=("proposal_id",), name="judiciary_unique_proposal_approval"),
        ),
    ]
