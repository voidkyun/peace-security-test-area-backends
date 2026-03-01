"""
秩序実行系モデル（Issue #9, #10）。

- Evaluation: 評価結果の保存。
- ExecutionQueueItem: ダミー実行キュー（確定済み EXEC_ACTION をキューに載せる）。
- Proposal: EXEC_ACTION 提案（発議元リソース・Issue #10）。
- Approval: by=EXECUTIVE の承認（承認元リソース・Issue #10）。
"""
import uuid
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError

from shared.proposals.common import (
    ProposalKind,
    ProposalOrigin,
    ProposalStatus,
    REQUIRED_APPROVALS,
    compute_payload_hash as shared_compute_payload_hash,
    FinalizeConflictError,
    validate_finalize_approvals as shared_validate_finalize_approvals,
)


class Evaluation(models.Model):
    """
    評価結果。POST /evaluations で保存する。
    """
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Evaluation"
        verbose_name_plural = "Evaluations"


class ExecutionQueueItem(models.Model):
    """
    ダミー実行キュー。EXEC_ACTION 確定時に1件追加する。
    """
    class Status(models.TextChoices):
        PENDING = "PENDING", "待機"
        PROCESSING = "PROCESSING", "処理中"
        DONE = "DONE", "完了"
        FAILED = "FAILED", "失敗"

    proposal_id = models.UUIDField(db_index=True)
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "ExecutionQueueItem"
        verbose_name_plural = "ExecutionQueueItems"


# --- Proposal / Approval（Executive 固有・Issue #10）---


class Proposal(models.Model):
    """
    EXEC_ACTION 提案。発議元（Executive）のリソース。executive_db にのみ保持。
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

    def save(self, *args, **kwargs):
        if self._state.adding and not self.proposal_id:
            self.proposal_id = uuid.uuid4()
        if not self.payload_hash and self.payload is not None:
            self.payload_hash = shared_compute_payload_hash(self.payload)
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
    by=EXECUTIVE の承認。承認元（Executive）のリソース。executive_db にのみ保持。
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
            models.UniqueConstraint(fields=["proposal", "by"], name="exec_unique_proposal_by"),
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
