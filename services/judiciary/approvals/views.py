"""承認 API: POST /approvals/、GET /approvals/?proposal_id=xxx（Issue #10）。"""
from uuid import UUID
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, OpenApiParameter

from shared.auth.permissions import RequireScope
from shared.auth.scopes import APPROVAL_WRITE, PROPOSAL_FINALIZE

from .models import Approval
from .serializers import ApprovalCreateSerializer, ApprovalReadSerializer


class RequireApprovalScopeForMethod(RequireScope):
    """GET は PROPOSAL_FINALIZE、POST は APPROVAL_WRITE。"""

    def has_permission(self, request, view):
        scope = PROPOSAL_FINALIZE if request.method == "GET" else APPROVAL_WRITE
        req_scopes = getattr(request, "service_scopes", None) or []
        if scope in req_scopes:
            return True
        from rest_framework.exceptions import PermissionDenied
        raise PermissionDenied(detail=f"Scope '{scope}' required.")


class ApprovalListCreateView(APIView):
    """
    POST /approvals/ — 承認作成（by=JUDICIARY、自 DB に保存）
    GET /approvals/?proposal_id=xxx — 指定 proposal_id の承認一覧（検証用）
    """

    permission_classes = [RequireApprovalScopeForMethod]

    @extend_schema(
        summary="承認一覧（proposal_id 指定）",
        description="proposal_id を指定して当該 Proposal に対する司法の承認を取得。発議元の finalize 検証用。proposal.finalize スコープ必要。",
        parameters=[
            OpenApiParameter("proposal_id", type=str, description="Proposal UUID"),
        ],
        responses={200: ApprovalReadSerializer(many=True)},
    )
    def get(self, request):
        proposal_id = request.query_params.get("proposal_id")
        if not proposal_id:
            return Response(
                {"detail": "proposal_id を指定してください。"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            pid = UUID(proposal_id)
        except ValueError:
            return Response(
                {"detail": "不正な proposal_id です。"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        qs = Approval.objects.filter(proposal_id=pid).order_by("-created_at")
        serializer = ApprovalReadSerializer(qs, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="承認作成（司法）",
        description="by=JUDICIARY 固定。reason 20文字以上、references 1件以上。",
        request=ApprovalCreateSerializer,
        responses={201: ApprovalReadSerializer, 400: {}, 403: {}},
    )
    def post(self, request):
        serializer = ApprovalCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        approval = serializer.save()
        read_ser = ApprovalReadSerializer(instance=approval)
        return Response(read_ser.data, status=status.HTTP_201_CREATED)
