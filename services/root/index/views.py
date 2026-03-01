"""Proposal 索引 API（Issue #10）。発議元が登録・更新する。"""
import uuid
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema

from .models import ProposalIndexEntry
from .permissions import RequireIndexScopeForMethod
from .serializers import (
    ProposalIndexEntryCreateSerializer,
    ProposalIndexEntryUpdateStatusSerializer,
    ProposalIndexEntryReadSerializer,
)


class IndexEntryListCreateView(APIView):
    """
    GET /index/entries/ — 索引一覧（index.read）
    POST /index/entries/ — 索引登録（index.write）。発議元が Proposal 作成後に呼ぶ。
    """

    permission_classes = [RequireIndexScopeForMethod]

    @extend_schema(
        summary="索引一覧",
        description="index.read スコープが必要。",
        responses={200: ProposalIndexEntryReadSerializer(many=True)},
    )
    def get(self, request):
        qs = ProposalIndexEntry.objects.all()
        serializer = ProposalIndexEntryReadSerializer(qs, many=True)
        return Response(serializer.data)

    @extend_schema(
        summary="索引登録",
        description="発議元が Proposal 作成後に呼ぶ。index.write スコープが必要。",
        request=ProposalIndexEntryCreateSerializer,
        responses={201: ProposalIndexEntryReadSerializer, 400: {}, 403: {}},
    )
    def post(self, request):
        serializer = ProposalIndexEntryCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        entry = serializer.save()
        read_ser = ProposalIndexEntryReadSerializer(instance=entry)
        return Response(read_ser.data, status=status.HTTP_201_CREATED)


class IndexEntryDetailView(APIView):
    """
    GET /index/entries/<proposal_id>/ — 1件取得（index.read）
    PATCH /index/entries/<proposal_id>/ — 状態更新（index.write）。発議元が finalize 後に呼ぶ。
    """

    permission_classes = [RequireIndexScopeForMethod]

    @extend_schema(
        summary="索引1件取得",
        responses={200: ProposalIndexEntryReadSerializer, 404: {}},
    )
    def get(self, request, proposal_id):
        try:
            pid = uuid.UUID(str(proposal_id))
        except ValueError:
            return Response(
                {"detail": "不正な proposal_id です。"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        entry = ProposalIndexEntry.objects.filter(proposal_id=pid).first()
        if not entry:
            return Response(
                {"detail": "指定された索引が見つかりません。"},
                status=status.HTTP_404_NOT_FOUND,
            )
        serializer = ProposalIndexEntryReadSerializer(instance=entry)
        return Response(serializer.data)

    @extend_schema(
        summary="索引状態更新",
        description="発議元が finalize 成功後に status=FINALIZED 等で更新。index.write 必須。",
        request=ProposalIndexEntryUpdateStatusSerializer,
        responses={200: ProposalIndexEntryReadSerializer, 400: {}, 403: {}, 404: {}},
    )
    def patch(self, request, proposal_id):
        try:
            pid = uuid.UUID(str(proposal_id))
        except ValueError:
            return Response(
                {"detail": "不正な proposal_id です。"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        entry = ProposalIndexEntry.objects.filter(proposal_id=pid).first()
        if not entry:
            return Response(
                {"detail": "指定された索引が見つかりません。"},
                status=status.HTTP_404_NOT_FOUND,
            )
        ser = ProposalIndexEntryUpdateStatusSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        entry.status = ser.validated_data["status"]
        if "finalized_at" in ser.validated_data:
            entry.finalized_at = ser.validated_data["finalized_at"]
        entry.save(update_fields=["status", "finalized_at", "updated_at"])
        read_ser = ProposalIndexEntryReadSerializer(instance=entry)
        return Response(read_ser.data)
