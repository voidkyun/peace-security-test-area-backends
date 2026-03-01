"""法則審査系 Approval 作成 API（Issue #7）。POST /approvals、by=JUDICIARY 固定。"""
import uuid

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from shared.auth.permissions import RequireScope
from shared.auth.scopes import APPROVAL_WRITE

from audit.models import AuditEvent

from .serializers import ApprovalCreateSerializer


class ApprovalCreateView(APIView):
    """
    POST /approvals — 承認作成（法則審査系・by=JUDICIARY 固定）。
    approval.write スコープ必須。作成後に監査イベントを送信する。
    """

    permission_classes = [RequireScope]
    required_scope = APPROVAL_WRITE

    @extend_schema(
        summary="承認作成（司法）",
        description="法則審査系。by=JUDICIARY 固定。reason は20文字以上、references は1件以上必須。"
        "Proposal 存在確認後、監査イベントを送信する。",
        request=ApprovalCreateSerializer,
        responses={
            201: {"description": "承認を作成した"},
            400: {"description": "バリデーションエラー（不十分な reason 等）"},
            403: {"description": "approval.write スコープ不足"},
            404: {"description": "Proposal が存在しない"},
        },
    )
    def post(self, request):
        serializer = ApprovalCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        approval = serializer.save()
        request_id = str(uuid.uuid4())
        proposal = approval.proposal
        # 監査イベント送信（README: request_id と law_context を付与）
        AuditEvent.objects.create(
            payload={
                "request_id": request_id,
                "law_context": proposal.law_context,
                "action": "approval_created",
                "approval_id": approval.pk,
                "proposal_id": str(proposal.proposal_id),
                "by": approval.by,
            }
        )
        return Response(
            {
                "approval_id": approval.pk,
                "proposal_id": str(approval.proposal.proposal_id),
                "by": approval.by,
                "request_id": request_id,
            },
            status=status.HTTP_201_CREATED,
        )
