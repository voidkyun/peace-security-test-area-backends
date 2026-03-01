from rest_framework import serializers
from .models import AuditEvent


class AuditEventCreateSerializer(serializers.ModelSerializer):
    """POST 用。payload のみ受け取り、prev_hash / event_hash はサーバで計算。"""

    class Meta:
        model = AuditEvent
        fields = ("payload", "signature")
        extra_kwargs = {"signature": {"required": False, "allow_blank": True}}


class AuditEventReadSerializer(serializers.ModelSerializer):
    """GET 用。全フィールドを返す。"""

    class Meta:
        model = AuditEvent
        fields = ("id", "prev_hash", "event_hash", "payload", "signature", "created_at")
        read_only_fields = fields
