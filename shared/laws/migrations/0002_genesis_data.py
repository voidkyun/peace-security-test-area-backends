# GENESIS: 憲法 CONST@1 と LAWSET-AMATERAS@1 を投入（Issue #20）

from django.db import migrations
from django.utils import timezone

from shared.laws.models import (
    LAW_ID_CONST,
    LAWSET_ID_AMATERAS,
    compute_lawset_digest,
)


def create_genesis(apps, schema_editor):
    Law = apps.get_model("shared_laws", "Law")
    Lawset = apps.get_model("shared_laws", "Lawset")
    LawsetMembership = apps.get_model("shared_laws", "LawsetMembership")

    # 憲法（GENESIS）
    const, _ = Law.objects.get_or_create(
        law_id=LAW_ID_CONST,
        law_version=1,
        defaults={
            "title": "憲法（GENESIS）",
            "status": "EFFECTIVE",
            "text": "# 憲法（創世データ）\n\n本法は GENESIS として登録された創世データです。\n通常の LAW_CHANGE による改正の対象外です。",
        },
    )

    # 法体系 LAWSET-AMATERAS version=1（仮 digest で作成し、後で更新）
    effective_at = timezone.now()
    lawset, _ = Lawset.objects.get_or_create(
        lawset_id=LAWSET_ID_AMATERAS,
        version=1,
        defaults={
            "effective_at": effective_at,
            "digest_hash": "",  # 下で更新
        },
    )

    # membership: CONST@1 を含める（order=0）
    LawsetMembership.objects.get_or_create(
        lawset=lawset,
        law=const,
        defaults={"order": 0},
    )

    # digest_hash: membership の (law_id, law_version, text) を順序で連結→SHA256
    memberships = (
        LawsetMembership.objects.filter(lawset=lawset).order_by("order", "law__law_id").select_related("law")
    )
    parts = [(m.law.law_id, m.law.law_version, m.law.text) for m in memberships]
    lawset.digest_hash = compute_lawset_digest(parts)
    lawset.save(update_fields=["digest_hash"])


def remove_genesis(apps, schema_editor):
    LawsetMembership = apps.get_model("shared_laws", "LawsetMembership")
    Lawset = apps.get_model("shared_laws", "Lawset")
    Law = apps.get_model("shared_laws", "Law")

    LawsetMembership.objects.filter(lawset__lawset_id=LAWSET_ID_AMATERAS, lawset__version=1).delete()
    Lawset.objects.filter(lawset_id=LAWSET_ID_AMATERAS, version=1).delete()
    Law.objects.filter(law_id=LAW_ID_CONST, law_version=1).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("shared_laws", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_genesis, remove_genesis),
    ]
