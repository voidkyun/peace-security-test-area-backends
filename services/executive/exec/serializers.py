"""
秩序実行系 API 用シリアライザ（Issue #9）。
"""
from rest_framework import serializers


class EvaluationCreateSerializer(serializers.Serializer):
    """POST /evaluations のリクエスト body。"""

    payload = serializers.JSONField(default=dict)


class ExecProposalCreateSerializer(serializers.Serializer):
    """POST /exec/proposals のリクエスト body。"""

    payload = serializers.JSONField(default=dict)
    expires_at = serializers.DateTimeField(required=False)
