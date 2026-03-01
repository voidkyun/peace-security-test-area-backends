"""
秩序実行系モデル（Issue #9）。

- Evaluation: 評価結果の保存。
- ExecutionQueueItem: ダミー実行キュー（確定済み EXEC_ACTION をキューに載せる）。
"""
from django.db import models


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
