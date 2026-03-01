"""
Service JWT 認証の動作確認（Issue #4）。
- JWT なし通信は 401
- 不正・無効トークンは 401
- 不正 scope は 403
- 正しい JWT + scope で 200
"""
import pytest
from django.conf import settings
from django.test import Client

from shared.auth import issue_jwt
from shared.auth.scopes import PROPOSAL_READ, PROPOSAL_WRITE


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def valid_token():
    secret = getattr(settings, "SERVICE_JWT_SECRET", "dev-service-jwt-secret-change-in-production")
    return issue_jwt(
        service_name="test-service",
        scopes=[PROPOSAL_READ],
        secret=secret,
        expires_seconds=3600,
    )


@pytest.fixture
def token_without_scope():
    """proposal.read を持たないトークン（403 検証用）。"""
    secret = getattr(settings, "SERVICE_JWT_SECRET", "dev-service-jwt-secret-change-in-production")
    return issue_jwt(
        service_name="other",
        scopes=[PROPOSAL_WRITE],
        secret=secret,
        expires_seconds=3600,
    )


def test_root_without_jwt_returns_401(client):
    """JWT なしでルートにアクセスすると 401。"""
    response = client.get("/")
    assert response.status_code == 401
    data = response.json()
    assert "detail" in data
    assert "JWT" in data["detail"] or "token" in data["detail"].lower()


def test_root_with_invalid_token_returns_401(client):
    """不正トークンで 401。"""
    response = client.get("/", HTTP_AUTHORIZATION="Bearer invalid-token")
    assert response.status_code == 401


def test_root_with_valid_jwt_returns_200(client, valid_token):
    """有効な JWT でルートにアクセスすると 200。"""
    response = client.get("/", HTTP_AUTHORIZATION=f"Bearer {valid_token}")
    assert response.status_code == 200


def test_internal_example_without_scope_returns_403(client, token_without_scope):
    """internal/example は proposal.read 必須。持っていないと 403。"""
    response = client.get(
        "/internal/example/",
        HTTP_AUTHORIZATION=f"Bearer {token_without_scope}",
    )
    data = response.json()
    assert response.status_code == 403
    assert "detail" in data
    assert PROPOSAL_READ in data["detail"]


def test_internal_example_with_scope_returns_200(client, valid_token):
    """proposal.read 付き JWT で internal/example は 200。"""
    response = client.get(
        "/internal/example/",
        HTTP_AUTHORIZATION=f"Bearer {valid_token}",
    )
    assert response.status_code == 200
    data = response.json()
    assert data.get("ok") is True
    assert data.get("service") == "test-service"
