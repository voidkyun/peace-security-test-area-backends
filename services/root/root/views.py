"""Root サービス用 API（DRF）。公開窓口・内部 API。"""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema

from shared.auth.permissions import RequireScope
from shared.auth.scopes import PROPOSAL_READ


class RootView(APIView):
    """トップパス: サービス稼働確認用（Service JWT 必須）。"""

    permission_classes = []

    @extend_schema(
        summary="サービス稼働確認",
        description="Root サービスが稼働していることを返す。Service JWT 必須。",
        responses={
            200: {
                "description": "稼働中",
                "content": {"application/json": {"schema": {"type": "object", "properties": {"message": {"type": "string"}}}}},
            },
        },
    )
    def get(self, request):
        return Response(
            {"message": "Root service is running."},
            status=status.HTTP_200_OK,
        )


class InternalExampleView(APIView):
    """proposal.read スコープが必要な内部 API 例。"""

    permission_classes = [RequireScope]
    required_scope = PROPOSAL_READ

    @extend_schema(
        summary="内部 API 例",
        description="proposal.read スコープが必要。スコープ不足時は 403。",
        responses={
            200: {
                "description": "成功",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "service": {"type": "string", "description": "呼び出し元サービス名"},
                                "ok": {"type": "boolean"},
                            },
                        },
                    },
                },
            },
            403: {"description": "スコープ不足"},
        },
    )
    def get(self, request):
        return Response(
            {
                "service": getattr(request, "service_name", ""),
                "ok": True,
            },
            status=status.HTTP_200_OK,
        )
