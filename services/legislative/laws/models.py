"""
法データモデル（MVP）。規範生成系（legislative）に正本を置き、他は参照のみ。

- Lawset: 法体系のバージョン（施行日・digest_hash）
- Law: 個別法（憲法 CONST / 下位法）
- LawsetMembership: ある Lawset が採用する Law の一覧
- Proposal: LAW_CHANGE 提案（発議元リソース・Issue #10）
- Approval: by=LEGISLATIVE の承認（承認元リソース・Issue #10）
"""
import hashlib
import uuid
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError

from shared.proposals.common import (
    ProposalKind,
    ProposalOrigin,
    ProposalStatus,
    REQUIRED_APPROVALS,
    LAW_ID_CONST as SHARED_LAW_ID_CONST,
    compute_payload_hash as shared_compute_payload_hash,
    FinalizeConflictError,
    validate_finalize_approvals as shared_validate_finalize_approvals,
)


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
LAWSET_ID_AMATERRACE = "LAWSET-AMATERRACE"


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
    lawset_id = models.CharField(max_length=64, db_index=True)  # 例: LAWSET-AMATERRACE
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
                name="laws_lawset_unique_id_version",
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
                name="laws_law_unique_id_version",
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
                name="laws_membership_unique_lawset_law",
            ),
        ]
        ordering = ["lawset", "order", "law"]

    def __str__(self):
        return f"{self.lawset} includes {self.law}"


# --- Proposal / Approval（Legislative 固有・Issue #10）---


class Proposal(models.Model):
    """
    LAW_CHANGE 提案。発議元（Legislative）のリソース。legislative_db にのみ保持。
    """
    proposal_id = models.UUIDField(unique=True, editable=False, db_index=True)
    kind = models.CharField(max_length=32, choices=ProposalKind.CHOICES)
    origin = models.CharField(max_length=32, choices=ProposalOrigin.CHOICES, db_index=True)
    status = models.CharField(
        max_length=32,
        choices=ProposalStatus.CHOICES,
        default=ProposalStatus.PENDING,
        db_index=True,
    )
    required_approvals = models.PositiveSmallIntegerField(default=REQUIRED_APPROVALS, editable=False)
    law_context = models.JSONField(default=dict)
    payload = models.JSONField(default=dict)
    payload_hash = models.CharField(max_length=64, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    finalized_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Proposal"
        verbose_name_plural = "Proposals"

    def __str__(self):
        return f"Proposal({self.proposal_id}, origin={self.origin}, status={self.status})"

    def clean(self):
        super().clean()
        if self.kind == ProposalKind.LAW_CHANGE and self.payload:
            law_id = self.payload.get("law_id")
            if law_id == SHARED_LAW_ID_CONST:
                raise ValidationError(
                    "憲法（CONST）は GENESIS 固定のため、LAW_CHANGE の対象にできません。"
                )

    def save(self, *args, **kwargs):
        if self._state.adding and not self.proposal_id:
            self.proposal_id = uuid.uuid4()
        if not self.payload_hash and self.payload is not None:
            self.payload_hash = shared_compute_payload_hash(self.payload)
        self.clean()
        super().save(*args, **kwargs)

    def finalize_with_approvals(self, external_approvals):
        """他サービスから取得した承認で確定。shared の検証を利用。"""
        if self.status == ProposalStatus.FINALIZED:
            raise FinalizeConflictError("既に確定済みです。")
        if self.status == ProposalStatus.EXPIRED:
            raise FinalizeConflictError("期限切れのため確定できません。")
        if self.status == ProposalStatus.REJECTED:
            raise FinalizeConflictError("却下済みのため確定できません。")
        if timezone.now() > self.expires_at:
            raise FinalizeConflictError("期限切れのため確定できません。")
        shared_validate_finalize_approvals(self.origin, external_approvals)
        self.status = ProposalStatus.FINALIZED
        self.finalized_at = timezone.now()
        self.save(update_fields=["status", "finalized_at"])


class Approval(models.Model):
    """
    by=LEGISLATIVE の承認。承認元（Legislative）のリソース。legislative_db にのみ保持。
    """
    proposal = models.ForeignKey(
        Proposal,
        on_delete=models.CASCADE,
        related_name="approvals",
    )
    by = models.CharField(max_length=32, choices=ProposalOrigin.CHOICES, db_index=True)
    reason = models.TextField(default="", help_text="承認理由（20文字以上）")
    references = models.JSONField(
        default=list,
        help_text="参照条文のリスト（1件以上）",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Approval"
        verbose_name_plural = "Approvals"
        constraints = [
            models.UniqueConstraint(fields=["proposal", "by"], name="laws_unique_proposal_by"),
        ]

    def __str__(self):
        return f"Approval(proposal={self.proposal_id}, by={self.by})"

    def clean(self):
        if not self.reason or len(self.reason.strip()) < 20:
            raise ValidationError("承認理由は20文字以上で入力してください。")
        if not self.references or not isinstance(self.references, list) or len(self.references) < 1:
            raise ValidationError("参照条文を1件以上指定してください。")
        if self.proposal_id and self.proposal:
            if self.by == self.proposal.origin:
                raise ValidationError("発議元（origin）は承認できません。承認の承認は禁止です。")
            if self.proposal.status in (ProposalStatus.FINALIZED, ProposalStatus.EXPIRED):
                raise ValidationError("確定済みまたは期限切れの Proposal には承認を追加できません。")
            if self.proposal.approvals.count() >= REQUIRED_APPROVALS and not self.pk:
                raise ValidationError(f"承認は最大{REQUIRED_APPROVALS}件までです。")
        super().clean()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
