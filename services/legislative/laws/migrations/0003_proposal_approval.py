# Legislative 固有の Proposal / Approval（Issue #10）

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("laws", "0002_genesis_data"),
    ]

    operations = [
        migrations.CreateModel(
            name="Proposal",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("proposal_id", models.UUIDField(db_index=True, editable=False, unique=True)),
                ("kind", models.CharField(choices=[("LAW_CHANGE", "LAW_CHANGE"), ("EXEC_ACTION", "EXEC_ACTION"), ("JUDGMENT", "JUDGMENT"), ("SYSTEM_CHANGE", "SYSTEM_CHANGE")], db_index=True, max_length=32)),
                ("origin", models.CharField(choices=[("LEGISLATIVE", "LEGISLATIVE"), ("JUDICIARY", "JUDICIARY"), ("EXECUTIVE", "EXECUTIVE")], db_index=True, max_length=32)),
                ("status", models.CharField(choices=[("PENDING", "PENDING"), ("APPROVED", "APPROVED"), ("REJECTED", "REJECTED"), ("FINALIZED", "FINALIZED"), ("EXPIRED", "EXPIRED")], db_index=True, default="PENDING", max_length=32)),
                ("required_approvals", models.PositiveSmallIntegerField(default=2, editable=False)),
                ("law_context", models.JSONField(default=dict)),
                ("payload", models.JSONField(default=dict)),
                ("payload_hash", models.CharField(editable=False, max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField()),
                ("finalized_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "verbose_name": "Proposal",
                "verbose_name_plural": "Proposals",
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="Approval",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("by", models.CharField(choices=[("LEGISLATIVE", "LEGISLATIVE"), ("JUDICIARY", "JUDICIARY"), ("EXECUTIVE", "EXECUTIVE")], db_index=True, max_length=32)),
                ("reason", models.TextField(default="", help_text="承認理由（20文字以上）")),
                ("references", models.JSONField(default=list, help_text="参照条文のリスト（1件以上）")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("proposal", models.ForeignKey(on_delete=models.CASCADE, related_name="approvals", to="laws.proposal")),
            ],
            options={
                "verbose_name": "Approval",
                "verbose_name_plural": "Approvals",
            },
        ),
        migrations.AddConstraint(
            model_name="approval",
            constraint=models.UniqueConstraint(fields=("proposal", "by"), name="laws_unique_proposal_by"),
        ),
    ]
