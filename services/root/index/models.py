"""
Root が保持する Proposal の公開用索引（Issue #10 ハイブリッドモデル）。
Proposal/Approval の正本は持たず、索引と監査ログのみ管理する。
"""
import uuid
from django.db import models


class ProposalIndexEntry(models.Model):
    """
    公開用 Proposal 索引。発議元が作成・確定時に登録・更新する。
    """
    proposal_id = models.UUIDField(unique=True, db_index=True, editable=False)
    kind = models.CharField(max_length=32, db_index=True)
    origin = models.CharField(max_length=32, db_index=True)
    status = models.CharField(max_length=32, db_index=True)
    payload = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=False)  # 発議元の created_at をそのまま
    expires_at = models.DateTimeField()
    finalized_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Proposal 索引"
        verbose_name_plural = "Proposal 索引"

    def __str__(self):
        return f"ProposalIndexEntry({self.proposal_id}, {self.origin}, {self.status})"

    def save(self, *args, **kwargs):
        if self._state.adding and not self.proposal_id:
            self.proposal_id = uuid.uuid4()
        super().save(*args, **kwargs)
