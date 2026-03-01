"""監査 API 用パーミッション。GET は audit.read、POST は audit.write。"""
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from shared.auth.scopes import AUDIT_READ, AUDIT_WRITE


class RequireAuditScopeForMethod(BasePermission):
    """GET のとき audit.read、POST のとき audit.write を要求する。"""

    def has_permission(self, request, view):
        scope = AUDIT_READ if request.method == "GET" else AUDIT_WRITE
        scopes = getattr(request, "service_scopes", None) or []
        if scope in scopes:
            return True
        raise PermissionDenied(detail=f"Scope '{scope}' required.")
