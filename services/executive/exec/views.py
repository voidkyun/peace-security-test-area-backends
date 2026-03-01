"""
秩序実行系 API: Evaluation 保存・EXEC_ACTION 提案・確定（Issue #9）。承認 API と finalize 他サービス取得（Issue #10）。
"""
from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema, OpenApiParameter

from shared.auth.permissions import RequireScope
from shared.auth.scopes import PROPOSAL_WRITE, PROPOSAL_FINALIZE, APPROVAL_WRITE
from shared.proposals.models import (
    Proposal,
    Approval,
    ProposalKind,
    ProposalOrigin,
    ProposalStatus,
    FinalizeConflictError,
)

from .models import Evaluation
from .serializers import EvaluationCreateSerializer, ExecProposalCreateSerializer, ExecApprovalCreateSerializer
from .services import (
    enqueue_execution,
    send_audit_event,
    register_index,
    update_index_status,
    fetch_approvals_from_service,
)


class RequireApprovalScopeForMethod(RequireScope):
    """GET は PROPOSAL_FINALIZE、POST は APPROVAL_WRITE。"""

    def has_permission(self, request, view):
        from rest_framework.exceptions import PermissionDenied
        scope = PROPOSAL_FINALIZE if request.method == "GET" else APPROVAL_WRITE
        req_scopes = getattr(request, "service_scopes", None) or []
        if scope in req_scopes:
            return True
        raise PermissionDenied(detail=f"Scope '{scope}' required.")


class ExecApprovalListCreateView(APIView):
    """
    GET /approvals/?proposal_id=xxx — 当該 Proposal の承認一覧（by=EXECUTIVE のみ）
    POST /approvals/ — 承認作成（by=EXECUTIVE）
    """

    permission_classes = [RequireApprovalScopeForMethod]

    @extend_schema(
        summary="承認一覧（proposal_id 指定）",
        parameters=[OpenApiParameter("proposal_id", type=str)],
        responses={200: {}},
    )
    def get(self, request):
        proposal_id = request.query_params.get("proposal_id")
        if not proposal_id:
            return Response(
                {"detail": "proposal_id を指定してください。"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            from uuid import UUID
            pid = UUID(proposal_id)
        except ValueError:
            return Response(
                {"detail": "不正な proposal_id です。"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        qs = Approval.objects.filter(proposal__proposal_id=pid).order_by("-created_at")
        data = [{"by": a.by, "reason": a.reason, "references": a.references} for a in qs]
        return Response(data)

    @extend_schema(
        summary="承認作成（執行）",
        request=ExecApprovalCreateSerializer,
        responses={201: {}, 400: {}},
    )
    def post(self, request):
        ser = ExecApprovalCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        approval = ser.save()
        return Response(
            {
                "id": approval.pk,
                "proposal_id": str(approval.proposal.proposal_id),
                "by": approval.by,
                "reason": approval.reason,
                "references": approval.references,
                "created_at": approval.created_at.isoformat(),
            },
            status=status.HTTP_201_CREATED,
        )


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
        register_index(proposal)
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
        judiciary_url = getattr(settings, "JUDICIARY_SERVICE_URL", "").rstrip("/")
        legislative_url = getattr(settings, "LEGISLATIVE_SERVICE_URL", "").rstrip("/")
        external = []
        external.extend(fetch_approvals_from_service(judiciary_url, id))
        external.extend(fetch_approvals_from_service(legislative_url, id))
        try:
            proposal.finalize_with_approvals(external)
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
        update_index_status(proposal.proposal_id, ProposalStatus.FINALIZED, proposal.finalized_at)
        return Response(
            {
                "proposal_id": str(proposal.proposal_id),
                "status": proposal.status,
            },
            status=status.HTTP_200_OK,
        )
