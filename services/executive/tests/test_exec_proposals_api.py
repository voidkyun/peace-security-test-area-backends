"""
EXEC_ACTION 提案・確定 API のテスト（Issue #9）。

- POST /exec/proposals/ で提案作成（proposal.write 必須）
- POST /exec/proposals/{id}/finalize/ で確定（承認2件必須）、不正時は 409
- 確定時にダミー実行キューに1件追加・監査ログ送信
"""
import uuid
import pytest
from django.conf import settings
from django.test import Client
from django.utils import timezone

from shared.auth import issue_jwt
from shared.auth.scopes import PROPOSAL_WRITE, PROPOSAL_FINALIZE
from shared.proposals.common import ProposalKind, ProposalOrigin, ProposalStatus
from exec.models import Proposal, Approval
from exec.models import ExecutionQueueItem


@pytest.fixture
def client():
    return Client()


def _jwt(scopes, service_name="executive"):
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


# --- POST /exec/proposals/ ---


@pytest.mark.django_db
def test_exec_proposals_post_without_jwt_returns_401(client):
    """POST /exec/proposals/ は JWT 必須。未送信時は 401。"""
    response = client.post(
        "/exec/proposals/",
        data={"payload": {"action": "test"}},
        content_type="application/json",
    )
    assert response.status_code == 401


@pytest.mark.django_db
def test_exec_proposals_post_with_scope_creates_proposal(client, token_proposal_write):
    """POST /exec/proposals/ で proposal.write ありなら EXEC_ACTION 提案が作成される。"""
    from unittest.mock import patch
    with patch("exec.views.register_index"):
        response = client.post(
            "/exec/proposals/",
            data={"payload": {"action": "NOTIFY", "target": "user-1"}},
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token_proposal_write}",
        )
    assert response.status_code == 201
    data = response.json()
    assert data["kind"] == ProposalKind.EXEC_ACTION
    assert data["origin"] == ProposalOrigin.EXECUTIVE
    assert data["status"] == ProposalStatus.PENDING
    assert data["payload"]["action"] == "NOTIFY"
    assert "proposal_id" in data
    proposal = Proposal.objects.get(proposal_id=data["proposal_id"])
    assert proposal.kind == ProposalKind.EXEC_ACTION
    assert proposal.origin == ProposalOrigin.EXECUTIVE


# --- POST /exec/proposals/{id}/finalize/ ---


@pytest.fixture
def exec_proposal_with_two_approvals(db):
    """承認2件付きの PENDING EXEC_ACTION Proposal（finalize 可能）。"""
    p = Proposal.objects.create(
        kind=ProposalKind.EXEC_ACTION,
        origin=ProposalOrigin.EXECUTIVE,
        status=ProposalStatus.PENDING,
        law_context={},
        payload={"action": "EXEC", "id": "1"},
        expires_at=_future(),
    )
    Approval.objects.create(
        proposal=p,
        by=ProposalOrigin.LEGISLATIVE,
        reason="本法案は手続きおよび実体規定に適合することを確認した。",
        references=["憲法第73条"],
    )
    Approval.objects.create(
        proposal=p,
        by=ProposalOrigin.JUDICIARY,
        reason="本法案は執行上問題ないと判断した。承認する。（20文字以上）",
        references=["憲法第72条"],
    )
    return p


@pytest.mark.django_db
def test_exec_proposals_finalize_success_enqueues_and_returns_200(
    client, token_proposal_finalize, exec_proposal_with_two_approvals
):
    """正常系: finalize で status=FINALIZED、実行キューに1件追加（他2系の承認は API 取得をモック）。"""
    from unittest.mock import patch
    p = exec_proposal_with_two_approvals
    pid = p.proposal_id
    external = [
        {"by": "JUDICIARY", "reason": "本法案は手続きおよび実体規定に適合する。", "references": ["憲法第81条"]},
        {"by": "LEGISLATIVE", "reason": "本法案は執行上問題ないと判断した。承認する。（20文字以上）", "references": ["憲法第72条"]},
    ]
    with patch("exec.views.fetch_approvals_from_service") as mock_fetch, patch(
        "exec.views.update_index_status"
    ):
        mock_fetch.side_effect = [[external[0]], [external[1]]]
        response = client.post(
            f"/exec/proposals/{pid}/finalize/",
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token_proposal_finalize}",
        )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == ProposalStatus.FINALIZED
    assert data["proposal_id"] == str(pid)
    p.refresh_from_db()
    assert p.status == ProposalStatus.FINALIZED
    item = ExecutionQueueItem.objects.filter(proposal_id=pid).first()
    assert item is not None
    assert item.status == ExecutionQueueItem.Status.PENDING


@pytest.mark.django_db
def test_exec_proposals_finalize_without_approvals_returns_409(client, token_proposal_finalize):
    """承認0件の Proposal を finalize すると 409。"""
    p = Proposal.objects.create(
        kind=ProposalKind.EXEC_ACTION,
        origin=ProposalOrigin.EXECUTIVE,
        status=ProposalStatus.PENDING,
        law_context={},
        payload={"action": "test"},
        expires_at=_future(),
    )
    response = client.post(
        f"/exec/proposals/{p.proposal_id}/finalize/",
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token_proposal_finalize}",
    )
    assert response.status_code == 409
    p.refresh_from_db()
    assert p.status == ProposalStatus.PENDING
    assert ExecutionQueueItem.objects.filter(proposal_id=p.proposal_id).count() == 0


@pytest.mark.django_db
def test_exec_proposals_finalize_not_found_returns_404(client, token_proposal_finalize):
    """存在しない proposal_id で finalize すると 404。"""
    response = client.post(
        f"/exec/proposals/{uuid.uuid4()}/finalize/",
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token_proposal_finalize}",
    )
    assert response.status_code == 404


@pytest.mark.django_db
def test_exec_proposals_finalize_wrong_kind_returns_400(client, token_proposal_finalize):
    """LAW_CHANGE 提案を /exec/proposals/{id}/finalize/ で確定しようとすると 400。"""
    p = Proposal.objects.create(
        kind=ProposalKind.LAW_CHANGE,
        origin=ProposalOrigin.LEGISLATIVE,
        status=ProposalStatus.PENDING,
        law_context={},
        payload={"law_id": "L-1", "title": "某法", "text": ""},
        expires_at=_future(),
    )
    response = client.post(
        f"/exec/proposals/{p.proposal_id}/finalize/",
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {token_proposal_finalize}",
    )
    assert response.status_code == 400
