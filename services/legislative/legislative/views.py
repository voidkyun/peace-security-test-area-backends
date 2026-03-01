"""
規範生成系（立法）サービス API。法・法体系の参照用（Issue #20）。
"""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from laws.models import Law, Lawset, LAWSET_ID_AMATERRACE


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
