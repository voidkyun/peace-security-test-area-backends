"""
秩序実行系 API: Evaluation 保存・EXEC_ACTION 提案・確定（Issue #9）。
"""
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from shared.auth.permissions import RequireScope
from shared.auth.scopes import PROPOSAL_WRITE, PROPOSAL_FINALIZE
from shared.proposals.models import (
    Proposal,
    ProposalKind,
    ProposalOrigin,
    ProposalStatus,
    FinalizeConflictError,
)

from .models import Evaluation
from .serializers import EvaluationCreateSerializer, ExecProposalCreateSerializer
from .services import enqueue_execution, send_audit_event


class EvaluationCreateView(APIView):
    """
    POST /evaluations
    Evaluation を保存する。proposal.write スコープ必須。
    """

    permission_classes = [RequireScope]
    required_scope = PROPOSAL_WRITE

    def post(self, request):
        ser = EvaluationCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        payload = ser.validated_data.get("payload", {})
        evaluation = Evaluation.objects.create(payload=payload)
        return Response(
            {
                "id": evaluation.pk,
                "payload": evaluation.payload,
                "created_at": evaluation.created_at.isoformat(),
            },
            status=status.HTTP_201_CREATED,
        )


class ExecProposalCreateView(APIView):
    """
    POST /exec/proposals
    EXEC_ACTION 提案を作成する。proposal.write スコープ必須。
    """

    permission_classes = [RequireScope]
    required_scope = PROPOSAL_WRITE

    def post(self, request):
        ser = ExecProposalCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        expires_at = data.get("expires_at")
        if expires_at is None:
            expires_at = timezone.now() + timezone.timedelta(days=30)
        payload = data.get("payload", {})
        proposal = Proposal.objects.create(
            kind=ProposalKind.EXEC_ACTION,
            origin=ProposalOrigin.EXECUTIVE,
            status=ProposalStatus.PENDING,
            law_context={},
            payload=payload,
            expires_at=expires_at,
        )
        return Response(
            {
                "proposal_id": str(proposal.proposal_id),
                "kind": proposal.kind,
                "origin": proposal.origin,
                "status": proposal.status,
                "payload": proposal.payload,
                "expires_at": proposal.expires_at.isoformat(),
                "created_at": proposal.created_at.isoformat(),
            },
            status=status.HTTP_201_CREATED,
        )


class ExecProposalFinalizeView(APIView):
    """
    POST /exec/proposals/{id}/finalize
    承認2件済みの EXEC_ACTION Proposal を確定する。proposal.finalize スコープ必須。
    確定後にダミー実行キューへ追加し、監査ログを送信する。不正時は 409。
    """

    permission_classes = [RequireScope]
    required_scope = PROPOSAL_FINALIZE

    def post(self, request, id):
        try:
            proposal = Proposal.objects.get(proposal_id=id)
        except Proposal.DoesNotExist:
            return Response(
                {"detail": "指定された提案が見つかりません。"},
                status=status.HTTP_404_NOT_FOUND,
            )
        if proposal.kind != ProposalKind.EXEC_ACTION:
            return Response(
                {"detail": "EXEC_ACTION 以外の提案はこのエンドポイントでは確定できません。"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            proposal.finalize()
        except FinalizeConflictError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_409_CONFLICT,
            )
        enqueue_execution(proposal.proposal_id)
        send_audit_event({
            "event_type": "EXEC_ACTION_FINALIZED",
            "proposal_id": str(proposal.proposal_id),
            "payload": proposal.payload,
        })
        return Response(
            {
                "proposal_id": str(proposal.proposal_id),
                "status": proposal.status,
            },
            status=status.HTTP_200_OK,
        )
