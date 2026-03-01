"""
監査イベントモデル（ハッシュチェーン・追記専用）。

- prev_hash: 直前イベントの event_hash（先頭は空文字）
- event_hash: SHA256(prev_hash + serialized_event) で改ざん検出
- append-only: 更新・削除は禁止
"""
import hashlib
import json
from django.db import models
from django.core.exceptions import ValidationError


def _serialize_payload(payload: dict) -> bytes:
    """改ざん検出用にキーソート済み JSON でシリアライズする。"""
    return json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")


def compute_event_hash(prev_hash: str, serialized_event: bytes) -> str:
    """prev_hash とシリアライズ済みイベントから event_hash を計算する。"""
    data = (prev_hash + "\n").encode("utf-8") + serialized_event
    return hashlib.sha256(data).hexdigest()


class AppendOnlyManager(models.Manager):
    """監査イベントは削除禁止のため、QuerySet.delete() を無効化する。"""

    def delete(self):
        raise ValidationError("監査イベントは削除できません。")


class AuditEvent(models.Model):
    """
    監査イベント。追記専用。prev_hash でチェーンし、event_hash で改ざん検出可能。
    """

    prev_hash = models.CharField(max_length=64, blank=True, db_index=True)
    event_hash = models.CharField(max_length=64, unique=True, db_index=True)
    payload = models.JSONField(default=dict)
    # 将来の署名用（未使用）
    signature = models.CharField(max_length=512, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = AppendOnlyManager()

    class Meta:
        ordering = ["created_at", "id"]
        verbose_name = "監査イベント"
        verbose_name_plural = "監査イベント"

    def __str__(self):
        return f"AuditEvent({self.pk}, hash={self.event_hash[:16]}...)"

    def save(self, *args, **kwargs):
        if self.pk is not None:
            raise ValidationError("監査イベントは追記専用のため更新できません。")
        if not self.event_hash:
            last = (
                AuditEvent.objects.order_by("-created_at", "-id")
                .values_list("event_hash", flat=True)
                .first()
            )
            prev = last if last else ""
            self.prev_hash = prev
            serialized = _serialize_payload(self.payload)
            self.event_hash = compute_event_hash(self.prev_hash, serialized)
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("監査イベントは削除できません。")
