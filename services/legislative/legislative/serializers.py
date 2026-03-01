"""
規範生成系（立法）サービス用シリアライザ（Issue #8, #10）。
"""
from rest_framework import serializers

from shared.proposals.models import Approval, Proposal, ProposalOrigin, ProposalStatus, LAW_ID_CONST


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


class LawApprovalCreateSerializer(serializers.Serializer):
    """POST /approvals/ 用（by=LEGISLATIVE）。"""

    proposal_id = serializers.UUIDField()
    reason = serializers.CharField(min_length=20)
    references = serializers.ListField(child=serializers.CharField(), min_length=1)

    def validate_proposal_id(self, value):
        try:
            p = Proposal.objects.get(proposal_id=value)
        except Proposal.DoesNotExist:
            raise serializers.ValidationError("指定された Proposal が存在しません。")
        if p.status in (ProposalStatus.FINALIZED, ProposalStatus.EXPIRED):
            raise serializers.ValidationError(
                "確定済みまたは期限切れの Proposal には承認を追加できません。"
            )
        if p.status == ProposalStatus.REJECTED:
            raise serializers.ValidationError("却下済みの Proposal には承認を追加できません。")
        return value

    def create(self, validated_data):
        proposal = Proposal.objects.get(proposal_id=validated_data["proposal_id"])
        return Approval.objects.create(
            proposal=proposal,
            by=ProposalOrigin.LEGISLATIVE,
            reason=validated_data["reason"].strip(),
            references=validated_data["references"],
        )
