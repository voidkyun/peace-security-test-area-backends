"""
規範生成系（立法）サービス API。法・法体系の参照用（Issue #20）。
LAW_CHANGE 提案・確定フロー（Issue #8）。承認 API と finalize 他サービス取得（Issue #10）。
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

from laws.models import Law, Lawset, LAWSET_ID_AMATERRACE
from laws.services import (
    create_new_lawset_version_from_proposal,
    send_audit_event,
    register_index,
    update_index_status,
    fetch_approvals_from_service,
)

from .serializers import LawProposalCreateSerializer, LawApprovalCreateSerializer


class LawDetailView(APIView):
    """
    GET /laws/<law_id>/?version=
    指定 law_id の法を返す。version 省略時はその law_id の最新 law_version を返す。
    """

    permission_classes = []

    def get(self, request, law_id):
        version_param = request.query_params.get("version")
        if version_param is not None:
            try:
                version = int(version_param)
            except ValueError:
                return Response(
                    {"detail": "version は整数で指定してください。"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            qs = Law.objects.filter(law_id=law_id, law_version=version)
        else:
            qs = Law.objects.filter(law_id=law_id).order_by("-law_version")
        law = qs.first()
        if not law:
            return Response(
                {"detail": "指定された法が見つかりません。"},
                status=status.HTTP_404_NOT_FOUND,
            )
        return Response(
            {
                "law_id": law.law_id,
                "law_version": law.law_version,
                "title": law.title,
                "status": law.status,
                "text": law.text,
                "created_at": law.created_at.isoformat(),
            },
            status=status.HTTP_200_OK,
        )


class LawsetCurrentView(APIView):
    """
    GET /lawsets/current/
    現在の法体系（LAWSET-AMATERRACE の最新 version）を返す。
    """

    permission_classes = []

    def get(self, request):
        lawset = (
            Lawset.objects.filter(lawset_id=LAWSET_ID_AMATERRACE)
            .order_by("-version")
            .first()
        )
        if not lawset:
            return Response(
                {"detail": "法体系が見つかりません。"},
                status=status.HTTP_404_NOT_FOUND,
            )
        memberships = lawset.memberships.select_related("law").order_by("order", "law__law_id")
        laws = [
            {
                "law_id": m.law.law_id,
                "law_version": m.law.law_version,
                "title": m.law.title,
            }
            for m in memberships
        ]
        return Response(
            {
                "lawset_id": lawset.lawset_id,
                "version": lawset.version,
                "effective_at": lawset.effective_at.isoformat(),
                "digest_hash": lawset.digest_hash,
                "laws": laws,
                "created_at": lawset.created_at.isoformat(),
            },
            status=status.HTTP_200_OK,
        )


# --- 承認 API（Issue #10）---


class RequireApprovalScopeForMethod(RequireScope):
    """GET は PROPOSAL_FINALIZE、POST は APPROVAL_WRITE。"""

    def has_permission(self, request, view):
        from rest_framework.exceptions import PermissionDenied
        scope = PROPOSAL_FINALIZE if request.method == "GET" else APPROVAL_WRITE
        req_scopes = getattr(request, "service_scopes", None) or []
        if scope in req_scopes:
            return True
        raise PermissionDenied(detail=f"Scope '{scope}' required.")


class LawApprovalListCreateView(APIView):
    """
    GET /approvals/?proposal_id=xxx — 当該 Proposal の承認一覧（by=LEGISLATIVE のみ、自 DB）
    POST /approvals/ — 承認作成（by=LEGISLATIVE）
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
        data = [
            {"by": a.by, "reason": a.reason, "references": a.references}
            for a in qs
        ]
        return Response(data)

    @extend_schema(
        summary="承認作成（立法）",
        request=LawApprovalCreateSerializer,
        responses={201: {}, 400: {}},
    )
    def post(self, request):
        ser = LawApprovalCreateSerializer(data=request.data)
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


# --- LAW_CHANGE 提案・確定（Issue #8） ---


class LawProposalCreateView(APIView):
    """
    POST /laws/proposals/
    LAW_CHANGE 提案を作成する。proposal.write スコープ必須。
    """

    permission_classes = [RequireScope]
    required_scope = PROPOSAL_WRITE

    def post(self, request):
        ser = LawProposalCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data
        expires_at = data.get("expires_at")
        if expires_at is None:
            expires_at = timezone.now() + timezone.timedelta(days=30)
        payload = {
            "law_id": data["law_id"],
            "title": data["title"],
            "text": data.get("text", ""),
        }
        proposal = Proposal.objects.create(
            kind=ProposalKind.LAW_CHANGE,
            origin=ProposalOrigin.LEGISLATIVE,
            status=ProposalStatus.PENDING,
            law_context={"lawset_id": LAWSET_ID_AMATERRACE},
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


class LawProposalFinalizeView(APIView):
    """
    POST /laws/proposals/{id}/finalize/
    承認2件済みの Proposal を確定し、新 lawset version を発行する。proposal.finalize スコープ必須。
    不正な場合は 409 Conflict。
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
        if proposal.kind != ProposalKind.LAW_CHANGE:
            return Response(
                {"detail": "LAW_CHANGE 以外の提案はこのエンドポイントでは確定できません。"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # 他2系の承認を API で取得（Issue #10）
        judiciary_url = getattr(settings, "JUDICIARY_SERVICE_URL", "").rstrip("/")
        executive_url = getattr(settings, "EXECUTIVE_SERVICE_URL", "").rstrip("/")
        external = []
        external.extend(fetch_approvals_from_service(judiciary_url, id))
        external.extend(fetch_approvals_from_service(executive_url, id))
        try:
            proposal.finalize_with_approvals(external)
        except FinalizeConflictError as e:
            return Response(
                {"detail": str(e)},
                status=status.HTTP_409_CONFLICT,
            )
        # 新 lawset version 発行
        try:
            new_lawset = create_new_lawset_version_from_proposal(proposal)
        except Exception as e:
            return Response(
                {"detail": f"法体系の更新に失敗しました: {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        # 監査ログ送信
        send_audit_event({
            "event_type": "LAW_FINALIZED",
            "proposal_id": str(proposal.proposal_id),
            "lawset_id": new_lawset.lawset_id,
            "version": new_lawset.version,
            "effective_at": new_lawset.effective_at.isoformat(),
        })
        update_index_status(proposal.proposal_id, ProposalStatus.FINALIZED, proposal.finalized_at)
        return Response(
            {
                "proposal_id": str(proposal.proposal_id),
                "status": proposal.status,
                "lawset_id": new_lawset.lawset_id,
                "version": new_lawset.version,
                "effective_at": new_lawset.effective_at.isoformat(),
            },
            status=status.HTTP_200_OK,
        )
