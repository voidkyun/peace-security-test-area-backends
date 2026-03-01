"""
Service JWT 認証ミドルウェア。Authorization: Bearer <token> を検証し、request に service 情報を付与する。
JWT がない・無効の場合は 401 を返す。
"""
from django.conf import settings
from django.http import JsonResponse

from .jwt import SCOPES_CLAIM, SUB_CLAIM, verify_jwt


def get_secret():
    return getattr(settings, "SERVICE_JWT_SECRET", "")


def get_exempt_paths():
    return getattr(settings, "SERVICE_JWT_EXEMPT_PATHS", ())


class ServiceJWTAuthenticationMiddleware:
    """
    Service JWT を検証するミドルウェア。
    request.service_name / request.service_scopes を設定する。
    JWT が無い・無効の場合は 401 を返す（SERVICE_JWT_EXEMPT_PATHS を除く）。
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        exempt_paths = get_exempt_paths()
        path = request.path.rstrip("/") or "/"
        if any(path == p.rstrip("/") or path.startswith(p.rstrip("/") + "/") for p in exempt_paths):
            return self.get_response(request)

        auth_header = request.META.get("HTTP_AUTHORIZATION") or ""
        if not auth_header.startswith("Bearer "):
            return JsonResponse(
                {"detail": "Service JWT required. Use Authorization: Bearer <token>."},
                status=401,
            )
        token = auth_header[7:].strip()
        if not token:
            return JsonResponse({"detail": "Empty token."}, status=401)

        secret = get_secret()
        if not secret:
            return JsonResponse(
                {"detail": "Server misconfiguration: SERVICE_JWT_SECRET not set."},
                status=500,
            )

        try:
            payload = verify_jwt(token, secret)
        except Exception:
            return JsonResponse({"detail": "Invalid or expired token."}, status=401)

        request.service_name = payload.get(SUB_CLAIM) or ""
        request.service_scopes = list(payload.get(SCOPES_CLAIM) or [])
        return self.get_response(request)
