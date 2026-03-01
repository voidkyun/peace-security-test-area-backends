"""
LAW_CHANGE 提案・確定 API のテスト（Issue #8）。

- POST /laws/proposals/ で提案作成（proposal.write 必須）
- POST /laws/proposals/{id}/finalize/ で確定（承認2件必須）、不正時は 409
- 正常系で lawset version 更新
"""
import pytest
from django.conf import settings
from django.test import Client
from django.utils import timezone

from shared.auth import issue_jwt
from shared.auth.scopes import PROPOSAL_WRITE, PROPOSAL_FINALIZE, APPROVAL_WRITE
from shared.proposals.models import (
    Proposal,
    Approval,
    ProposalKind,
    ProposalOrigin,
    ProposalStatus,
    REQUIRED_APPROVALS,
)
from laws.models import Lawset, LAWSET_ID_AMATERRACE


@pytest.fixture
def client():
    return Client()


def _jwt(scopes, service_name="legislative"):
    secret = getattr(settings, "SERVICE_JWT_SECRET", "dev-service-jwt-secret-change-in-production")
    return issue_jwt(service_name=service_name, scopes=scopes, secret=secret, expires_seconds=3600)


@pytest.fixture
def token_proposal_write():
    return _jwt([PROPOSAL_WRITE])


@pytest.fixture
def token_proposal_finalize():
    return _jwt([PROPOSAL_FINALIZE])


def _future():
    return timezone.now() + timezone.timedelta(days=1)


# --- POST /laws/proposals/ ---


@pytest.mark.django_db
def test_laws_proposals_post_without_jwt_returns_401(client):
    """POST /laws/proposals/ は JWT 必須。未送信時は 401。"""
    response = client.post(
        "/laws/proposals/",
        data={
            "law_id": "L-001",
            "title": "某法の新設",
            "text": "本法は試験用です。",
        },
        content_type="application/json",
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_laws_proposals_post_with_scope_creates_proposal(client, token_proposal_write):
    """POST /laws/proposals/ で proposal.write ありなら LAW_CHANGE 提案が作成される。"""
    response = client.post(
        "/laws/proposals/",
        data={
            "law_id": "L-001",
            "title": "某法の新設",
            "text": "本法は試験用です。",
        },
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token_proposal_write}",
    )
    assert response.status_code == 201
    data = response.json()
    assert data["kind"] == ProposalKind.LAW_CHANGE
    assert data["origin"] == ProposalOrigin.LEGISLATIVE
    assert data["status"] == ProposalStatus.PENDING
    assert data["payload"]["law_id"] == "L-001"
    assert data["payload"]["title"] == "某法の新設"
    assert "proposal_id" in data
    proposal = Proposal.objects.get(proposal_id=data["proposal_id"])
    assert proposal.kind == ProposalKind.LAW_CHANGE
    assert proposal.origin == ProposalOrigin.LEGISLATIVE


@pytest.mark.django_db
def test_laws_proposals_post_const_rejected(client, token_proposal_write):
    """POST /laws/proposals/ で law_id=CONST は 400。"""
    response = client.post(
        "/laws/proposals/",
        data={
            "law_id": "CONST",
            "title": "憲法改正",
            "text": "対象外",
        },
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token_proposal_write}",
    )
    assert response.status_code == 400


# --- POST /laws/proposals/{id}/finalize/ ---


@pytest.fixture
def proposal_with_two_approvals(db):
    """承認2件付きの PENDING Proposal（finalize 可能）。"""
    future = timezone.now() + timezone.timedelta(days=1)
    p = Proposal.objects.create(
        kind=ProposalKind.LAW_CHANGE,
        origin=ProposalOrigin.LEGISLATIVE,
        status=ProposalStatus.PENDING,
        law_context={"lawset_id": LAWSET_ID_AMATERRACE},
        payload={"law_id": "L-002", "title": "某法改正案", "text": "改正後の本文"},
        expires_at=future,
    )
    Approval.objects.create(
        proposal=p,
        by=ProposalOrigin.JUDICIARY,
        reason="本法案は手続きおよび実体規定に適合することを確認した。",
        references=["憲法第73条"],
    )
    Approval.objects.create(
        proposal=p,
        by=ProposalOrigin.EXECUTIVE,
        reason="本法案は執行上問題ないと判断した。承認する。（20文字以上）",
        references=["憲法第72条"],
    )
    return p


@pytest.mark.django_db
def test_laws_proposals_finalize_success_updates_lawset_version(
    client, token_proposal_finalize, proposal_with_two_approvals
):
    """正常系: finalize で lawset の新 version が発行される。"""
    pid = proposal_with_two_approvals.proposal_id
    current = Lawset.objects.filter(lawset_id=LAWSET_ID_AMATERRACE).order_by("-version").first()
    assert current is not None
    prev_version = current.version

    response = client.post(
        f"/laws/proposals/{pid}/finalize/",
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token_proposal_finalize}",
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == ProposalStatus.FINALIZED
    assert data["lawset_id"] == LAWSET_ID_AMATERRACE
    assert data["version"] == prev_version + 1

    proposal_with_two_approvals.refresh_from_db()
    assert proposal_with_two_approvals.status == ProposalStatus.FINALIZED

    new_lawset = Lawset.objects.get(lawset_id=LAWSET_ID_AMATERRACE, version=prev_version + 1)
    assert new_lawset.digest_hash


@pytest.mark.django_db
def test_laws_proposals_finalize_without_approvals_returns_409(
    client, token_proposal_finalize
):
    """承認0件の Proposal を finalize すると 409。"""
    future = timezone.now() + timezone.timedelta(days=1)
    p = Proposal.objects.create(
        kind=ProposalKind.LAW_CHANGE,
        origin=ProposalOrigin.LEGISLATIVE,
        status=ProposalStatus.PENDING,
        law_context={},
        payload={"law_id": "L-003", "title": "未承認案", "text": ""},
        expires_at=future,
    )
    response = client.post(
        f"/laws/proposals/{p.proposal_id}/finalize/",
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token_proposal_finalize}",
    )
    assert response.status_code == 409
    p.refresh_from_db()
    assert p.status == ProposalStatus.PENDING


@pytest.mark.django_db
def test_laws_proposals_finalize_not_found_returns_404(client, token_proposal_finalize):
    """存在しない proposal_id で finalize すると 404。"""
    import uuid
    response = client.post(
        f"/laws/proposals/{uuid.uuid4()}/finalize/",
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token_proposal_finalize}",
    )
    assert response.status_code == 404
