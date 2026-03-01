"""
Scope ベースの権限チェック。

Service JWT ミドルウェアが request.service_scopes を設定した前提で、
指定スコープが含まれない場合に 403 を返す。
DRF 利用時は settings で DEFAULT_AUTHENTICATION_CLASSES=[] とし、
本モジュールの RequireScope でスコープチェックすること。
"""
from functools import wraps

from django.http import JsonResponse
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission


def require_scope(scope: str):
    """
    指定 scope が request.service_scopes に無い場合 403 を返すデコレータ。
    Service JWT ミドルウェアの後に使用する。
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            scopes = getattr(request, "service_scopes", None) or []
            if scope not in scopes:
                return JsonResponse(
                    {"detail": f"Scope '{scope}' required."},
                    status=403,
                )
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator


class RequireScope(BasePermission):
    """
    request.service_scopes に指定スコープが含まれることを要求する。
    不足時は PermissionDenied(detail="Scope '...' required.") で 403。
    スコープは __init__(scope=...) または view.required_scope で指定。
    """

    scope = None

    def __init__(self, scope=None):
        self.required_scope = scope or self.scope
        self.message = (
            f"Scope '{self.required_scope}' required." if self.required_scope else None
        )

    def _get_scope(self, view):
        return self.required_scope or getattr(view, "required_scope", None)

    def has_permission(self, request, view):
        scope = self._get_scope(view)
        if not scope:
            return True
        req_scopes = getattr(request, "service_scopes", None) or []
        if scope in req_scopes:
            return True
        raise PermissionDenied(detail=f"Scope '{scope}' required.")
