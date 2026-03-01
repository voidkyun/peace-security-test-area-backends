"""
Root Proposal 索引 API のテスト（Issue #10）。
"""
import uuid
import pytest
from django.test import Client
from django.utils import timezone

from shared.auth import issue_jwt
from shared.auth.scopes import INDEX_WRITE, INDEX_READ

from index.models import ProposalIndexEntry


@pytest.fixture
def client():
    return Client()


def _jwt(scopes, service_name="legislative"):
    from django.conf import settings
    secret = getattr(settings, "SERVICE_JWT_SECRET", "dev-service-jwt-secret-change-in-production")
    return issue_jwt(service_name=service_name, scopes=scopes, secret=secret, expires_seconds=3600)


@pytest.fixture
def token_index_write():
    return _jwt([INDEX_WRITE])


@pytest.fixture
def token_index_read():
    return _jwt([INDEX_READ])


@pytest.mark.django_db
def test_index_post_without_jwt_returns_401(client):
    """POST /index/entries/ は JWT 必須。"""
    response = client.post(
        "/index/entries/",
        data={
            "proposal_id": str(uuid.uuid4()),
            "kind": "LAW_CHANGE",
            "origin": "LEGISLATIVE",
            "status": "PENDING",
            "payload": {},
            "created_at": timezone.now().isoformat(),
            "expires_at": (timezone.now() + timezone.timedelta(days=30)).isoformat(),
        },
        content_type="application/json",
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_index_post_success_creates_entry(client, token_index_write):
    """POST /index/entries/ で索引が1件作成される。"""
    pid = uuid.uuid4()
    created = timezone.now()
    expires = created + timezone.timedelta(days=30)
    response = client.post(
        "/index/entries/",
        data={
            "proposal_id": str(pid),
            "kind": "LAW_CHANGE",
            "origin": "LEGISLATIVE",
            "status": "PENDING",
            "payload": {"law_id": "L-1", "title": "某法"},
            "created_at": created.isoformat(),
            "expires_at": expires.isoformat(),
        },
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token_index_write}",
    )
    assert response.status_code == 201
    data = response.json()
    assert data["proposal_id"] == str(pid)
    assert data["kind"] == "LAW_CHANGE"
    assert data["status"] == "PENDING"
    entry = ProposalIndexEntry.objects.get(proposal_id=pid)
    assert entry.origin == "LEGISLATIVE"


@pytest.mark.django_db
def test_index_patch_updates_status(client, token_index_write):
    """PATCH /index/entries/<id>/ で status を更新できる。"""
    entry = ProposalIndexEntry.objects.create(
        proposal_id=uuid.uuid4(),
        kind="LAW_CHANGE",
        origin="LEGISLATIVE",
        status="PENDING",
        payload={},
        created_at=timezone.now(),
        expires_at=timezone.now() + timezone.timedelta(days=30),
    )
    response = client.patch(
        f"/index/entries/{entry.proposal_id}/",
        data={"status": "FINALIZED", "finalized_at": timezone.now().isoformat()},
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token_index_write}",
    )
    assert response.status_code == 200
    entry.refresh_from_db()
    assert entry.status == "FINALIZED"
    assert entry.finalized_at is not None


@pytest.mark.django_db
def test_index_get_list_requires_read_scope(client, token_index_read):
    """GET /index/entries/ は index.read で一覧取得できる。"""
    response = client.get(
        "/index/entries/",
        HTTP_AUTHORIZATION=f"Bearer {token_index_read}",
    )
    assert response.status_code == 200
    assert isinstance(response.json(), list)
