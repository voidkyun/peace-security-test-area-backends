from rest_framework import serializers
from .models import AuditEvent


class AuditEventCreateSerializer(serializers.ModelSerializer):
    """POST 用。payload のみ受け取り、prev_hash / event_hash はサーバで計算。"""

    class Meta:
        model = AuditEvent
        fields = ("payload", "request_id", "signature")
        extra_kwargs = {
            "request_id": {"required": False, "allow_blank": True},
            "signature": {"required": False, "allow_blank": True},
        }


class AuditEventReadSerializer(serializers.ModelSerializer):
    """GET 用。全フィールドを返す。"""

    class Meta:
        model = AuditEvent
        fields = (
            "id",
            "request_id",
            "prev_hash",
            "event_hash",
            "payload",
            "signature",
            "created_at",
        )
        read_only_fields = fields
