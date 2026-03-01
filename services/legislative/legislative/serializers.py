"""
規範生成系（立法）サービス用シリアライザ（Issue #8）。
"""
from rest_framework import serializers

from shared.proposals.models import LAW_ID_CONST


class LawProposalCreateSerializer(serializers.Serializer):
    """POST /laws/proposals/ のリクエスト body。"""

    law_id = serializers.CharField(max_length=64)
    title = serializers.CharField(max_length=256)
    text = serializers.CharField(allow_blank=True, default="")
    expires_at = serializers.DateTimeField(required=False)

    def validate_law_id(self, value):
        if value == LAW_ID_CONST:
            raise serializers.ValidationError(
                "憲法（CONST）は LAW_CHANGE の対象にできません。"
            )
        return value
