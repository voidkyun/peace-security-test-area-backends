"""
監査イベント API とハッシュチェーン・append-only のテスト（Issue #5）。
"""
import pytest
from django.conf import settings
from django.test import Client
from django.core.exceptions import ValidationError

from shared.auth import issue_jwt
from shared.auth.scopes import AUDIT_READ, AUDIT_WRITE
from audit.models import AuditEvent, compute_event_hash


@pytest.fixture
def client():
    return Client()


def _jwt(scopes, service_name="test-service"):
    secret = getattr(settings, "SERVICE_JWT_SECRET", "dev-service-jwt-secret-change-in-production")
    return issue_jwt(service_name=service_name, scopes=scopes, secret=secret, expires_seconds=3600)


@pytest.fixture
def token_read():
    return _jwt([AUDIT_READ])


@pytest.fixture
def token_write():
    return _jwt([AUDIT_WRITE])


@pytest.fixture
def token_read_write():
    return _jwt([AUDIT_READ, AUDIT_WRITE])


# --- API: JWT / スコープ ---


@pytest.mark.django_db
def test_audit_events_list_without_jwt_returns_401(client):
    """GET /audit/events/ は JWT 必須。"""
    response = client.get("/audit/events/")
    assert response.status_code == 401


@pytest.mark.django_db
def test_audit_events_post_without_jwt_returns_401(client):
    """POST /audit/events/ は JWT 必須。"""
    response = client.post("/audit/events/", data={"payload": {}}, content_type="application/json")
    assert response.status_code == 401


@pytest.mark.django_db
def test_audit_events_list_without_audit_read_returns_403(client, token_write):
    """GET /audit/events/ は audit.read 必須。"""
    response = client.get(
        "/audit/events/",
        HTTP_AUTHORIZATION=f"Bearer {token_write}",
    )
    assert response.status_code == 403
    assert "audit.read" in response.json().get("detail", "")


@pytest.mark.django_db
def test_audit_events_post_without_audit_write_returns_403(client, token_read):
    """POST /audit/events/ は audit.write 必須。"""
    response = client.post(
        "/audit/events/",
        data={"payload": {"a": 1}},
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token_read}",
    )
    assert response.status_code == 403
    assert "audit.write" in response.json().get("detail", "")


# --- API: 正常系 ---


@pytest.mark.django_db
def test_audit_events_post_returns_201_and_chain(client, token_write):
    """POST で 1 件登録すると 201、prev_hash/event_hash が設定される。"""
    response = client.post(
        "/audit/events/",
        data={"payload": {"action": "test", "id": 1}},
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token_write}",
    )
    assert response.status_code == 201
    data = response.json()
    assert data["prev_hash"] == ""
    assert len(data["event_hash"]) == 64
    assert data["payload"] == {"action": "test", "id": 1}
    assert "id" in data
    assert "created_at" in data


@pytest.mark.django_db
def test_audit_events_hash_chain(client, token_write):
    """2 件登録すると 2 件目の prev_hash が 1 件目の event_hash と一致する。"""
    r1 = client.post(
        "/audit/events/",
        data={"payload": {"n": 1}},
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token_write}",
    )
    assert r1.status_code == 201
    h1 = r1.json()["event_hash"]

    r2 = client.post(
        "/audit/events/",
        data={"payload": {"n": 2}},
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token_write}",
    )
    assert r2.status_code == 201
    data2 = r2.json()
    assert data2["prev_hash"] == h1
    assert data2["event_hash"] != h1


@pytest.mark.django_db
def test_audit_events_list_returns_200(client, token_read_write, token_write):
    """GET /audit/events/ で一覧取得。audit.read で 200。"""
    client.post(
        "/audit/events/",
        data={"payload": {"x": 1}},
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token_write}",
    )
    response = client.get(
        "/audit/events/",
        HTTP_AUTHORIZATION=f"Bearer {token_read_write}",
    )
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    assert "event_hash" in data[0] and "payload" in data[0]


@pytest.mark.django_db
def test_audit_events_detail_returns_200(client, token_read_write, token_write):
    """GET /audit/events/{id}/ で 1 件取得。"""
    r = client.post(
        "/audit/events/",
        data={"payload": {"detail": "ok"}},
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token_write}",
    )
    assert r.status_code == 201
    eid = r.json()["id"]
    response = client.get(
        f"/audit/events/{eid}/",
        HTTP_AUTHORIZATION=f"Bearer {token_read_write}",
    )
    assert response.status_code == 200
    assert response.json()["id"] == eid
    assert response.json()["payload"] == {"detail": "ok"}


# --- モデル: append-only / ハッシュ ---


@pytest.mark.django_db
def test_audit_event_append_only_no_update():
    """既存レコードの save（更新）は ValidationError。"""
    e = AuditEvent.objects.create(
        prev_hash="",
        event_hash="a" * 64,
        payload={"x": 1},
    )
    e.payload = {"x": 2}
    with pytest.raises(ValidationError) as exc_info:
        e.save()
    assert "更新" in str(exc_info.value) or "追記" in str(exc_info.value)


@pytest.mark.django_db
def test_audit_event_no_delete():
    """インスタンス delete は ValidationError。"""
    e = AuditEvent.objects.create(
        prev_hash="",
        event_hash="b" * 64,
        payload={},
    )
    with pytest.raises(ValidationError) as exc_info:
        e.delete()
    assert "削除" in str(exc_info.value)


@pytest.mark.django_db
def test_audit_event_compute_event_hash_deterministic():
    """compute_event_hash は同じ入力で同じハッシュ。"""
    h1 = compute_event_hash("", b'{"a":1}')
    h2 = compute_event_hash("", b'{"a":1}')
    assert h1 == h2
    assert len(h1) == 64
