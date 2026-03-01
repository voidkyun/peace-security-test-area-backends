"""
POST /evaluations/ のテスト（Issue #9）。
Evaluation 保存。proposal.write 必須。未認証は 401。
"""
import pytest
from django.conf import settings
from django.test import Client

from shared.auth import issue_jwt
from shared.auth.scopes import PROPOSAL_WRITE
from exec.models import Evaluation


@pytest.fixture
def client():
    return Client()


def _jwt(scopes, service_name="executive"):
    secret = getattr(settings, "SERVICE_JWT_SECRET", "dev-service-jwt-secret-change-in-production")
    return issue_jwt(service_name=service_name, scopes=scopes, secret=secret, expires_seconds=3600)


@pytest.fixture
def token_proposal_write():
    return _jwt([PROPOSAL_WRITE])


@pytest.mark.django_db
def test_evaluations_post_without_jwt_returns_401(client):
    """POST /evaluations/ は JWT 必須。未送信時は 401。"""
    response = client.post(
        "/evaluations/",
        data={"payload": {"subject": "test", "result": "ok"}},
        content_type="application/json",
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_evaluations_post_with_scope_creates_evaluation(client, token_proposal_write):
    """POST /evaluations/ で proposal.write ありなら Evaluation が保存される。"""
    payload = {"subject": "秩序評価", "result": "PASS"}
    response = client.post(
        "/evaluations/",
        data={"payload": payload},
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token_proposal_write}",
    )
    assert response.status_code == 201
    data = response.json()
    assert data["payload"] == payload
    assert "id" in data
    assert "created_at" in data
    evaluation = Evaluation.objects.get(pk=data["id"])
    assert evaluation.payload == payload
