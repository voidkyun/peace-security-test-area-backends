"""
秩序実行系 API 用シリアライザ（Issue #9, #10）。
"""
from rest_framework import serializers

from shared.proposals.models import Approval, Proposal, ProposalOrigin, ProposalStatus


class EvaluationCreateSerializer(serializers.Serializer):
    """POST /evaluations のリクエスト body。"""

    payload = serializers.JSONField(default=dict)


class ExecProposalCreateSerializer(serializers.Serializer):
    """POST /exec/proposals のリクエスト body。"""

    payload = serializers.JSONField(default=dict)
    expires_at = serializers.DateTimeField(required=False)


class ExecApprovalCreateSerializer(serializers.Serializer):
    """POST /approvals/ 用（by=EXECUTIVE）。"""

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
            by=ProposalOrigin.EXECUTIVE,
            reason=validated_data["reason"].strip(),
            references=validated_data["references"],
        )
