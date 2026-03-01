"""索引 API 用パーミッション。GET は index.read、POST/PATCH は index.write（Issue #10）。"""
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from shared.auth.scopes import INDEX_READ, INDEX_WRITE


class RequireIndexScopeForMethod(BasePermission):
    """GET のとき index.read、POST/PATCH のとき index.write を要求する。"""

    def has_permission(self, request, view):
        if request.method == "GET":
            scope = INDEX_READ
        else:
            scope = INDEX_WRITE
        scopes = getattr(request, "service_scopes", None) or []
        if scope in scopes:
            return True
        raise PermissionDenied(detail=f"Scope '{scope}' required.")
