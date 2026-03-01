"""
司法による承認の正本（Issue #10）。Judiciary DB にのみ保持。Proposal は持たない。
"""
import uuid
from django.db import models
from django.core.exceptions import ValidationError


# by は常に JUDICIARY のため定数
BY_JUDICIARY = "JUDICIARY"


class Approval(models.Model):
    """
    by=JUDICIARY の承認。proposal_id は他サービスで保持する Proposal の UUID 参照のみ。
    """
    proposal_id = models.UUIDField(db_index=True, editable=False)
    reason = models.TextField(default="", help_text="承認理由（20文字以上）")
    references = models.JSONField(
        default=list,
        help_text="参照条文のリスト（1件以上）",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "承認（司法）"
        verbose_name_plural = "承認（司法）"
        constraints = [
            models.UniqueConstraint(fields=["proposal_id"], name="judiciary_unique_proposal_approval"),
        ]

    def __str__(self):
        return f"Approval(proposal_id={self.proposal_id}, by={BY_JUDICIARY})"

    def clean(self):
        if not self.reason or len(self.reason.strip()) < 20:
            raise ValidationError("承認理由は20文字以上で入力してください。")
        if not self.references or not isinstance(self.references, list) or len(self.references) < 1:
            raise ValidationError("参照条文を1件以上指定してください。")
        super().clean()

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
