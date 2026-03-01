"""
Proposal 共通モデル（意思決定の最小単位）。

- 相互承認: origin 以外の2系統から各1件の承認が必要（required_approvals=2）
- 整合性はコードで強制（不正確定・期限切れは必ず拒否）
"""
import hashlib
import json
import uuid
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError


# --- 定数（Issue #6 準拠） ---
class ProposalKind:
    LAW_CHANGE = "LAW_CHANGE"
    EXEC_ACTION = "EXEC_ACTION"
    JUDGMENT = "JUDGMENT"
    SYSTEM_CHANGE = "SYSTEM_CHANGE"
    CHOICES = [
        (LAW_CHANGE, "LAW_CHANGE"),
        (EXEC_ACTION, "EXEC_ACTION"),
        (JUDGMENT, "JUDGMENT"),
        (SYSTEM_CHANGE, "SYSTEM_CHANGE"),
    ]


class ProposalOrigin:
    LEGISLATIVE = "LEGISLATIVE"
    JUDICIARY = "JUDICIARY"
    EXECUTIVE = "EXECUTIVE"
    CHOICES = [
        (LEGISLATIVE, "LEGISLATIVE"),
        (JUDICIARY, "JUDICIARY"),
        (EXECUTIVE, "EXECUTIVE"),
    ]


class ProposalStatus:
    PENDING = "PENDING"
    APPROVED = "APPROVED"  # 承認2件付いたが未確定の状態（任意）
    REJECTED = "REJECTED"
    FINALIZED = "FINALIZED"
    EXPIRED = "EXPIRED"
    CHOICES = [
        (PENDING, "PENDING"),
        (APPROVED, "APPROVED"),
        (REJECTED, "REJECTED"),
        (FINALIZED, "FINALIZED"),
        (EXPIRED, "EXPIRED"),
    ]


REQUIRED_APPROVALS = 2

# 憲法の law_id（GENESIS 固定）。LAW_CHANGE では改正対象にできない（Issue #20）
LAW_ID_CONST = "CONST"


def compute_payload_hash(payload: dict) -> str:
    """payload の SHA256 ハッシュ（キーソート JSON）を返す。"""
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class FinalizeConflictError(ValidationError):
    """不正な finalize 試行時に送出。API では 409 Conflict にマッピングする。"""
    pass


class Proposal(models.Model):
    """
    意思決定の最小単位。origin が保持し、他2系統の承認2件で確定可能。
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
    law_context = models.JSONField(default=dict)  # 作成時固定
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
            if law_id == LAW_ID_CONST:
                raise ValidationError(
                    "憲法（CONST）は GENESIS 固定のため、LAW_CHANGE の対象にできません。"
                )

    def save(self, *args, **kwargs):
        if self._state.adding and not self.proposal_id:
            self.proposal_id = uuid.uuid4()
        if not self.payload_hash and self.payload is not None:
            self.payload_hash = compute_payload_hash(self.payload)
        self.clean()  # LAW_CHANGE で CONST 拒否など（full_clean は既存挙動を変えるため呼ばない）
        super().save(*args, **kwargs)

    def _validate_finalize_approvals(self, origins_who_approved):
        """承認2件・2系統の検証。"""
        if len(origins_who_approved) != REQUIRED_APPROVALS:
            raise FinalizeConflictError(
                f"承認が{REQUIRED_APPROVALS}件必要です（現在 {len(origins_who_approved)} 件）。"
            )
        if self.origin in origins_who_approved:
            raise FinalizeConflictError("発議元（origin）は承認に含めません。")
        if len(set(origins_who_approved)) != REQUIRED_APPROVALS:
            raise FinalizeConflictError("承認は異なる2系統から各1件必要です。")

    def finalize(self):
        """
        確定処理（自 DB の approvals を参照）。条件を満たす場合のみ FINALIZED にし、そうでなければ FinalizeConflictError。
        - APPROVE が2件（origin 以外の2系統から各1件）
        - 期限内
        - 既に FINALIZED / EXPIRED でない
        """
        if self.status == ProposalStatus.FINALIZED:
            raise FinalizeConflictError("既に確定済みです。")
        if self.status == ProposalStatus.EXPIRED:
            raise FinalizeConflictError("期限切れのため確定できません。")
        if self.status == ProposalStatus.REJECTED:
            raise FinalizeConflictError("却下済みのため確定できません。")
        if timezone.now() > self.expires_at:
            raise FinalizeConflictError("期限切れのため確定できません。")
        approvals = self.approvals.all()
        if approvals.count() != REQUIRED_APPROVALS:
            raise FinalizeConflictError(
                f"承認が{REQUIRED_APPROVALS}件必要です（現在 {approvals.count()} 件）。"
            )
        origins_who_approved = {a.by for a in approvals}
        self._validate_finalize_approvals(origins_who_approved)
        self.status = ProposalStatus.FINALIZED
        self.finalized_at = timezone.now()
        self.save(update_fields=["status", "finalized_at"])

    def finalize_with_approvals(self, external_approvals):
        """
        他サービスから取得した承認リストで確定する（ハイブリッドモデル・Issue #10）。
        external_approvals: list[dict] 各要素は {'by': str, 'reason': str, 'references': list}
        """
        if self.status == ProposalStatus.FINALIZED:
            raise FinalizeConflictError("既に確定済みです。")
        if self.status == ProposalStatus.EXPIRED:
            raise FinalizeConflictError("期限切れのため確定できません。")
        if self.status == ProposalStatus.REJECTED:
            raise FinalizeConflictError("却下済みのため確定できません。")
        if timezone.now() > self.expires_at:
            raise FinalizeConflictError("期限切れのため確定できません。")
        if len(external_approvals) != REQUIRED_APPROVALS:
            raise FinalizeConflictError(
                f"承認が{REQUIRED_APPROVALS}件必要です（現在 {len(external_approvals)} 件）。"
            )
        origins_who_approved = {a["by"] for a in external_approvals}
        self._validate_finalize_approvals(origins_who_approved)
        self.status = ProposalStatus.FINALIZED
        self.finalized_at = timezone.now()
        self.save(update_fields=["status", "finalized_at"])


class Approval(models.Model):
    """
    他系統による承認。1 Proposal につき最大2件（origin 以外の2系統のみ）。
    同一 (proposal, by) の重複は禁止（Approval 再利用不可の一環）。
    理由（reason）と参照条文（references）は法的根拠として必須（Issue #7）。
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
        help_text="参照条文のリスト（1件以上）。例: [\"憲法第73条\", \"法律第1条\"]",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Approval"
        verbose_name_plural = "Approvals"
        constraints = [
            models.UniqueConstraint(fields=["proposal", "by"], name="unique_proposal_by"),
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
