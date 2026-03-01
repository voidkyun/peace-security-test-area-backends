"""
秩序実行系（行政）サービス用 Django 設定（共通）。
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("SECRET_KEY", "django-insecure-dev-executive-change-me")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.messages",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "rest_framework",
    "drf_spectacular",
    "shared.auth",
    "exec",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "shared.auth.middleware.ServiceJWTAuthenticationMiddleware",
]

SERVICE_JWT_SECRET = os.environ.get("SERVICE_JWT_SECRET", "dev-service-jwt-secret-change-in-production")
SERVICE_NAME = os.environ.get("SERVICE_NAME", "executive")
ROOT_SERVICE_URL = os.environ.get("ROOT_SERVICE_URL", "").rstrip("/")
JUDICIARY_SERVICE_URL = os.environ.get("JUDICIARY_SERVICE_URL", "").rstrip("/")
LEGISLATIVE_SERVICE_URL = os.environ.get("LEGISLATIVE_SERVICE_URL", "").rstrip("/")
SERVICE_JWT_EXEMPT_PATHS = ("/admin", "/schema", "/swagger")
SERVICE_JWT_NO_EXEMPT_PREFIXES = ("/evaluations", "/exec/proposals")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Executive Service API",
    "DESCRIPTION": "秩序実行系（行政）サービス API",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
}

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

ROOT_URLCONF = "executive.urls"

WSGI_APPLICATION = "executive.wsgi.application"

if os.environ.get("POSTGRES_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("POSTGRES_DB", "executive_db"),
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
