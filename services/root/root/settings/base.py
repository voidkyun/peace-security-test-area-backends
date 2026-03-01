"""
Root サービス用 Django 設定（共通）。
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "django-insecure-dev-root-change-me")

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "shared.auth",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "shared.auth.middleware.ServiceJWTAuthenticationMiddleware",
]

# サービス間認証（Service JWT）。本番では環境変数で上書きすること。
SERVICE_JWT_SECRET = os.environ.get("SERVICE_JWT_SECRET", "dev-service-jwt-secret-change-in-production")
SERVICE_NAME = os.environ.get("SERVICE_NAME", "root")
SERVICE_JWT_EXEMPT_PATHS = ()  # JWT 不要にするパス（例: ("/health",)）

# Django REST Framework
# サービス間認証はミドルウェア（ServiceJWTAuthenticationMiddleware）のみで行う。
# DRF の認証を有効にすると perform_authentication() が先に走り、Bearer Service JWT を
# 認識できず 403「認証情報が含まれていません。」を返してしまい、RequireScope に到達しない。
# そのため DEFAULT_AUTHENTICATION_CLASSES を空にし、権限チェックで RequireScope が正しく 403 を返すようにする。
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# drf-spectacular（Swagger / OpenAPI）
SPECTACULAR_SETTINGS = {
    "TITLE": "Root Service API",
    "DESCRIPTION": "平和保障試験区 Root サービス API（公開窓口・監査・Proposal 索引）",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

ROOT_URLCONF = "root.urls"

WSGI_APPLICATION = "root.wsgi.application"

if os.environ.get("POSTGRES_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("POSTGRES_DB", "root_db"),
            "USER": os.environ.get("POSTGRES_USER", "postgres"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", "postgres"),
            "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

LANGUAGE_CODE = "ja-jp"
TIME_ZONE = "Asia/Tokyo"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
