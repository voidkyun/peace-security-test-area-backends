"""監査イベント API。POST は内部専用（audit.write）、GET は audit.read。"""
from rest_framework import status
from rest_framework.generics import RetrieveAPIView
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from shared.auth.permissions import RequireScope
from shared.auth.scopes import AUDIT_READ, AUDIT_WRITE
from shared.tracing import get_current_request_id, normalize_request_id

from .models import AuditEvent
from .permissions import RequireAuditScopeForMethod
from .serializers import AuditEventCreateSerializer, AuditEventReadSerializer


class AuditEventListCreateView(APIView):
    """
    GET /audit/events — 一覧（audit.read）
    POST /audit/events — 登録・内部専用（audit.write）
    """

    permission_classes = [RequireAuditScopeForMethod]

    @extend_schema(
        summary="監査イベント一覧",
        description="audit.read スコープが必要。",
        responses={200: AuditEventReadSerializer(many=True), 403: {"description": "スコープ不足"}},
    )
    def get(self, request):
        qs = AuditEvent.objects.all()
        serializer = AuditEventReadSerializer(qs, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="監査イベント登録（内部専用）",
        description="audit.write スコープが必要。payload から prev_hash / event_hash を自動計算し追記する。",
        request=AuditEventCreateSerializer,
        responses={
            201: AuditEventReadSerializer,
            400: {"description": "バリデーションエラー"},
            403: {"description": "スコープ不足"},
        },
    )
    def post(self, request):
        serializer = AuditEventCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request_id = (
            normalize_request_id(getattr(request, "request_id", ""))
            or normalize_request_id(get_current_request_id())
            or normalize_request_id(serializer.validated_data.get("request_id"))
        )
        if not request_id:
            return Response(
                {"request_id": ["request_id is required."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        serializer.save(request_id=request_id)
        read_serializer = AuditEventReadSerializer(instance=serializer.instance)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED)


class AuditEventDetailView(RetrieveAPIView):
    """GET /audit/events/{id} — 1件取得。audit.read 必須。"""

    queryset = AuditEvent.objects.all()
    serializer_class = AuditEventReadSerializer
    permission_classes = [RequireScope]
    required_scope = AUDIT_READ

    @extend_schema(
        summary="監査イベント詳細",
        description="audit.read スコープが必要。",
        responses={200: AuditEventReadSerializer, 403: {"description": "スコープ不足"}, 404: {"description": "Not Found"}},
    )
    def get(self, request, *args, **kwargs):
        return self.retrieve(request, *args, **kwargs)
