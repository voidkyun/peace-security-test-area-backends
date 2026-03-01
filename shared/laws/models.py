"""
法データモデル（MVP）。規範生成系（legislative）に正本を置き、他は参照のみ。

- Lawset: 法体系のバージョン（施行日・digest_hash）
- Law: 個別法（憲法 CONST / 下位法）
- LawsetMembership: ある Lawset が採用する Law の一覧
"""
import hashlib
from django.db import models


# --- 定数（Issue #20 準拠） ---
class LawStatus:
    EFFECTIVE = "EFFECTIVE"
    REPEALED = "REPEALED"
    CHOICES = [
        (EFFECTIVE, "EFFECTIVE"),
        (REPEALED, "REPEALED"),
    ]


# 憲法の law_id（GENESIS 固定。LAW_CHANGE では変更不可）
LAW_ID_CONST = "CONST"
# 初期法体系 ID
LAWSET_ID_AMATERAS = "LAWSET-AMATERAS"


def compute_lawset_digest(memberships_with_law_text):
    """
    membership に含まれる (law_id, law_version, text) を決め打ち順序で連結→SHA256。
    memberships_with_law_text: [(law_id, law_version, text), ...] の順序付きイテラブル
    """
    parts = []
    for law_id, law_version, text in memberships_with_law_text:
        parts.append(f"{law_id}\n{law_version}\n{text or ''}")
    raw = "\n---\n".join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class Lawset(models.Model):
    """
    法体系のバージョン。version は単調増加。
    """
    lawset_id = models.CharField(max_length=64, db_index=True)  # 例: LAWSET-AMATERAS
    version = models.PositiveIntegerField()
    effective_at = models.DateTimeField()
    digest_hash = models.CharField(max_length=64)  # 監査用（membership から計算）
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Lawset"
        verbose_name_plural = "Lawsets"
        constraints = [
            models.UniqueConstraint(
                fields=["lawset_id", "version"],
                name="shared_laws_lawset_unique_id_version",
            ),
        ]
        ordering = ["lawset_id", "-version"]

    def __str__(self):
        return f"{self.lawset_id}@{self.version}"


class Law(models.Model):
    """
    個別法。law_id 例: CONST（憲法）, L-000120。
    """
    law_id = models.CharField(max_length=64, db_index=True)
    law_version = models.PositiveIntegerField(default=1)
    title = models.CharField(max_length=256)
    status = models.CharField(
        max_length=32,
        choices=LawStatus.CHOICES,
        default=LawStatus.EFFECTIVE,
        db_index=True,
    )
    text = models.TextField(blank=True)  # 本文（Markdown 可）
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Law"
        verbose_name_plural = "Laws"
        constraints = [
            models.UniqueConstraint(
                fields=["law_id", "law_version"],
                name="shared_laws_law_unique_id_version",
            ),
        ]
        ordering = ["law_id", "law_version"]

    def __str__(self):
        return f"{self.law_id}@{self.law_version}"


class LawsetMembership(models.Model):
    """
    ある Lawset が採用する Law。決め打ち順序で digest_hash 計算に使う。
    """
    lawset = models.ForeignKey(
        Lawset,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    law = models.ForeignKey(
        Law,
        on_delete=models.CASCADE,
        related_name="lawset_memberships",
    )
    order = models.PositiveSmallIntegerField(default=0)  # 同一 lawset 内の並び順

    class Meta:
        verbose_name = "LawsetMembership"
        verbose_name_plural = "LawsetMemberships"
        constraints = [
            models.UniqueConstraint(
                fields=["lawset", "law"],
                name="shared_laws_membership_unique_lawset_law",
            ),
        ]
        ordering = ["lawset", "order", "law"]

    def __str__(self):
        return f"{self.lawset} includes {self.law}"
