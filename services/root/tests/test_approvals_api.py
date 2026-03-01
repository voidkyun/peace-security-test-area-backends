"""
法則審査系 Approval API のテスト（Issue #7）。

- 不十分な reason は 400
- Proposal に正しく紐づく
- 監査イベント生成成功
"""
import pytest
from django.conf import settings
from django.test import Client
from django.utils import timezone

from shared.auth import issue_jwt
from shared.auth.scopes import APPROVAL_WRITE, AUDIT_READ
from shared.proposals.models import Proposal, Approval, ProposalKind, ProposalOrigin, ProposalStatus
from audit.models import AuditEvent


@pytest.fixture
def client():
    return Client()


def _jwt(scopes, service_name="judiciary"):
    secret = getattr(settings, "SERVICE_JWT_SECRET", "dev-service-jwt-secret-change-in-production")
    return issue_jwt(service_name=service_name, scopes=scopes, secret=secret, expires_seconds=3600)


@pytest.fixture
def token_approval_write():
    return _jwt([APPROVAL_WRITE])


@pytest.fixture
def token_without_approval():
    return _jwt([AUDIT_READ])


def _future():
    return timezone.now() + timezone.timedelta(days=1)


@pytest.fixture
def proposal_pending(db):
    """承認可能な PENDING の Proposal（立法発議）。"""
    return Proposal.objects.create(
        kind=ProposalKind.LAW_CHANGE,
        origin=ProposalOrigin.LEGISLATIVE,
        status=ProposalStatus.PENDING,
        law_context={"v": 1, "law_id": "L-001"},
        payload={"title": "某法改正"},
        expires_at=_future(),
    )


# --- JWT / スコープ ---


@pytest.mark.django_db
def test_approvals_post_without_jwt_returns_401(client, proposal_pending):
    """POST /approvals/ は JWT 必須。"""
    response = client.post(
        "/approvals/",
        data={
            "proposal_id": str(proposal_pending.proposal_id),
            "reason": "本法案は手続きおよび実体規定に適合することを確認した。",
            "references": ["憲法第73条"],
        },
        content_type="application/json",
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_approvals_post_without_approval_write_returns_403(client, token_without_approval, proposal_pending):
    """POST /approvals/ は approval.write 必須。"""
    response = client.post(
        "/approvals/",
        data={
            "proposal_id": str(proposal_pending.proposal_id),
            "reason": "本法案は手続きおよび実体規定に適合することを確認した。",
            "references": ["憲法第73条"],
        },
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token_without_approval}",
    )
    assert response.status_code == 403
    assert "approval.write" in response.json().get("detail", "")


# --- バリデーション: 不十分な reason は 400 ---


@pytest.mark.django_db
def test_approvals_post_reason_too_short_returns_400(client, token_approval_write, proposal_pending):
    """reason が20文字未満のとき 400。"""
    response = client.post(
        "/approvals/",
        data={
            "proposal_id": str(proposal_pending.proposal_id),
            "reason": "短い理由",
            "references": ["憲法第73条"],
        },
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token_approval_write}",
    )
    assert response.status_code == 400
    assert "reason" in response.json()


@pytest.mark.django_db
def test_approvals_post_references_empty_returns_400(client, token_approval_write, proposal_pending):
    """references が空のとき 400。"""
    response = client.post(
        "/approvals/",
        data={
            "proposal_id": str(proposal_pending.proposal_id),
            "reason": "本法案は手続きおよび実体規定に適合することを確認した。",
            "references": [],
        },
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token_approval_write}",
    )
    assert response.status_code == 400
    assert "references" in response.json()


# --- Proposal 存在確認・状態 ---


@pytest.mark.django_db
def test_approvals_post_nonexistent_proposal_returns_400(client, token_approval_write):
    """存在しない proposal_id のとき 400。"""
    import uuid
    response = client.post(
        "/approvals/",
        data={
            "proposal_id": str(uuid.uuid4()),
            "reason": "本法案は手続きおよび実体規定に適合することを確認した。",
            "references": ["憲法第73条"],
        },
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token_approval_write}",
    )
    assert response.status_code == 400
    errors = response.json()
    assert "proposal_id" in errors
    assert "存在しません" in str(errors["proposal_id"])


@pytest.mark.django_db
def test_approvals_post_finalized_proposal_returns_400(
    client, token_approval_write, proposal_pending
):
    """確定済みの Proposal には承認を追加できず 400。"""
    proposal_pending.status = ProposalStatus.FINALIZED
    proposal_pending.save(update_fields=["status"])
    response = client.post(
        "/approvals/",
        data={
            "proposal_id": str(proposal_pending.proposal_id),
            "reason": "本法案は手続きおよび実体規定に適合することを確認した。",
            "references": ["憲法第73条"],
        },
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token_approval_write}",
    )
    assert response.status_code == 400
    assert "確定済み" in str(response.json().get("proposal_id", ""))


# --- 正常系: Proposal に紐づき監査イベント生成 ---


@pytest.mark.django_db
def test_approvals_post_success_returns_201_and_links_to_proposal(
    client, token_approval_write, proposal_pending
):
    """POST 成功時 201、レスポンスに approval_id / proposal_id / by=JUDICIARY、Proposal に紐づく。"""
    response = client.post(
        "/approvals/",
        data={
            "proposal_id": str(proposal_pending.proposal_id),
            "reason": "本法案は手続きおよび実体規定に適合することを確認した。",
            "references": ["憲法第73条", "法律第1条"],
        },
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token_approval_write}",
    )
    assert response.status_code == 201
    data = response.json()
    assert "approval_id" in data
    assert data["proposal_id"] == str(proposal_pending.proposal_id)
    assert data["by"] == "JUDICIARY"
    assert "request_id" in data

    approval = Approval.objects.get(pk=data["approval_id"])
    assert approval.proposal_id == proposal_pending.pk
    assert approval.by == ProposalOrigin.JUDICIARY
    assert approval.reason == "本法案は手続きおよび実体規定に適合することを確認した。"
    assert approval.references == ["憲法第73条", "法律第1条"]
    assert proposal_pending.approvals.filter(pk=approval.pk).exists()


@pytest.mark.django_db
def test_approvals_post_creates_audit_event(client, token_approval_write, proposal_pending):
    """承認作成時に監査イベントが1件生成される。request_id と law_context が付与される。"""
    initial_count = AuditEvent.objects.count()
    response = client.post(
        "/approvals/",
        data={
            "proposal_id": str(proposal_pending.proposal_id),
            "reason": "本法案は手続きおよび実体規定に適合することを確認した。",
            "references": ["憲法第73条"],
        },
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token_approval_write}",
    )
    assert response.status_code == 201
    assert AuditEvent.objects.count() == initial_count + 1

    event = AuditEvent.objects.order_by("-id").first()
    payload = event.payload
    assert "request_id" in payload
    assert payload["request_id"] == response.json()["request_id"]
    assert payload["law_context"] == proposal_pending.law_context
    assert payload["action"] == "approval_created"
    assert payload["by"] == "JUDICIARY"
    assert payload["proposal_id"] == str(proposal_pending.proposal_id)
