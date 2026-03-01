"""承認 API 用シリアライザ（Issue #10）。"""
from rest_framework import serializers
from .models import Approval

BY_JUDICIARY = "JUDICIARY"


class ApprovalCreateSerializer(serializers.Serializer):
    """POST /approvals/ 用。"""

    proposal_id = serializers.UUIDField(help_text="承認対象の Proposal の UUID")
    reason = serializers.CharField(min_length=20, help_text="承認理由（20文字以上）")
    references = serializers.ListField(
        child=serializers.CharField(),
        min_length=1,
        help_text="参照条文のリスト（1件以上）",
    )

    def create(self, validated_data):
        return Approval.objects.create(
            proposal_id=validated_data["proposal_id"],
            reason=validated_data["reason"].strip(),
            references=validated_data["references"],
        )


class ApprovalReadSerializer(serializers.ModelSerializer):
    """GET 用。by は常に JUDICIARY。"""

    by = serializers.SerializerMethodField()

    class Meta:
        model = Approval
        fields = ["id", "proposal_id", "by", "reason", "references", "created_at"]

    def get_by(self, obj):
        return BY_JUDICIARY
