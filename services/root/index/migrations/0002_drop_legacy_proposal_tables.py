# Issue #10: Root から Proposal/Approval 正本を排除（テーブル削除）

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("index", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS shared_proposals_approval CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql="DROP TABLE IF EXISTS shared_proposals_proposal CASCADE;",
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
