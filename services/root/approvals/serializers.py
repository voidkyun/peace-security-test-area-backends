"""Approval 作成用シリアライザ。by=JUDICIARY 固定（法則審査系）。"""
import uuid

from rest_framework import serializers

from shared.proposals.models import Approval, Proposal, ProposalOrigin, ProposalStatus


class ApprovalCreateSerializer(serializers.Serializer):
    """POST /approvals 用。reason 20文字以上、references 1件以上。"""

    proposal_id = serializers.UUIDField(help_text="承認対象の Proposal の UUID")
    reason = serializers.CharField(min_length=20, help_text="承認理由（20文字以上）")
    references = serializers.ListField(
        child=serializers.CharField(),
        min_length=1,
        help_text="参照条文のリスト（1件以上）",
    )

    def validate_proposal_id(self, value):
        """Proposal が存在し、承認可能な状態であることを確認する。"""
        try:
            proposal = Proposal.objects.get(proposal_id=value)
        except Proposal.DoesNotExist:
            raise serializers.ValidationError("指定された Proposal が存在しません。")
        if proposal.status in (ProposalStatus.FINALIZED, ProposalStatus.EXPIRED):
            raise serializers.ValidationError(
                "確定済みまたは期限切れの Proposal には承認を追加できません。"
            )
        if proposal.status == ProposalStatus.REJECTED:
            raise serializers.ValidationError("却下済みの Proposal には承認を追加できません。")
        return value

    def create(self, validated_data):
        proposal = Proposal.objects.get(proposal_id=validated_data["proposal_id"])
        return Approval.objects.create(
            proposal=proposal,
            by=ProposalOrigin.JUDICIARY,
            reason=validated_data["reason"].strip(),
            references=validated_data["references"],
        )
