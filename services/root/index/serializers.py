"""Proposal 索引 API 用シリアライザ（Issue #10）。"""
from rest_framework import serializers
from .models import ProposalIndexEntry


class ProposalIndexEntryCreateSerializer(serializers.Serializer):
    """POST /index/entries/ 用。発議元が Proposal 作成後に登録する。"""

    proposal_id = serializers.UUIDField()
    kind = serializers.CharField(max_length=32)
    origin = serializers.CharField(max_length=32)
    status = serializers.CharField(max_length=32)
    payload = serializers.JSONField(default=dict)
    created_at = serializers.DateTimeField()
    expires_at = serializers.DateTimeField()

    def create(self, validated_data):
        return ProposalIndexEntry.objects.create(**validated_data)


class ProposalIndexEntryUpdateStatusSerializer(serializers.Serializer):
    """PATCH /index/entries/<proposal_id>/ 用。status と finalized_at の更新。"""
    status = serializers.CharField(max_length=32)
    finalized_at = serializers.DateTimeField(allow_null=True, required=False)


class ProposalIndexEntryReadSerializer(serializers.ModelSerializer):
    """GET 用読み取り。"""

    class Meta:
        model = ProposalIndexEntry
        fields = [
            "proposal_id",
            "kind",
            "origin",
            "status",
            "payload",
            "created_at",
            "expires_at",
            "finalized_at",
            "updated_at",
        ]
