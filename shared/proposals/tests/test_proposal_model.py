"""
Proposal 共通モデル・整合性バリデーションの単体テスト（Issue #6）。

- 正常系: 2承認で finalize 成功
- 異常系: 承認不足 / REJECT 混在 / 期限切れ / 誤 by / 再利用 / 二重 finalize
- 不正 finalize は必ず FinalizeConflictError（API では 409）
"""
import pytest
from django.utils import timezone
from django.db import IntegrityError
from django.core.exceptions import ValidationError

from shared.proposals.models import (
    Proposal,
    Approval,
    ProposalKind,
    ProposalOrigin,
    ProposalStatus,
    FinalizeConflictError,
    compute_payload_hash,
    REQUIRED_APPROVALS,
    LAW_ID_CONST,
)


def _future():
    return timezone.now() + timezone.timedelta(days=1)


def _past():
    return timezone.now() - timezone.timedelta(hours=1)


@pytest.fixture
def proposal_legislative(db):
    """立法発議の Proposal（origin=LEGISLATIVE）。承認可能なのは JUDICIARY / EXECUTIVE。"""
    return Proposal.objects.create(
        kind=ProposalKind.LAW_CHANGE,
        origin=ProposalOrigin.LEGISLATIVE,
        status=ProposalStatus.PENDING,
        law_context={"v": 1},
        payload={"title": "test"},
        expires_at=_future(),
    )


# --- 正常系: 2承認で finalize 成功 ---


@pytest.mark.django_db
def test_finalize_success_with_two_approvals(proposal_legislative):
    """2系統から各1件の承認で finalize が成功する。"""
    Approval.objects.create(proposal=proposal_legislative, by=ProposalOrigin.JUDICIARY)
    Approval.objects.create(proposal=proposal_legislative, by=ProposalOrigin.EXECUTIVE)
    proposal_legislative.finalize()
    proposal_legislative.refresh_from_db()
    assert proposal_legislative.status == ProposalStatus.FINALIZED
    assert proposal_legislative.finalized_at is not None


@pytest.mark.django_db
def test_proposal_id_auto_set(db):
    """作成時に proposal_id が未設定なら UUID が自動設定される。"""
    p = Proposal.objects.create(
        kind=ProposalKind.EXEC_ACTION,
        origin=ProposalOrigin.EXECUTIVE,
        law_context={},
        payload={},
        expires_at=_future(),
    )
    assert p.proposal_id is not None
    assert str(p.proposal_id)


@pytest.mark.django_db
def test_payload_hash_computed_on_save(db):
    """保存時に payload_hash が SHA256 で計算される。"""
    p = Proposal.objects.create(
        kind=ProposalKind.JUDGMENT,
        origin=ProposalOrigin.JUDICIARY,
        law_context={},
        payload={"a": 1, "b": 2},
        expires_at=_future(),
    )
    expected = compute_payload_hash({"a": 1, "b": 2})
    assert p.payload_hash == expected


# --- 異常系: 承認不足 / 期限切れ / 二重 finalize ---


@pytest.mark.django_db
def test_finalize_fails_insufficient_approvals(proposal_legislative):
    """承認が1件のみのとき finalize は FinalizeConflictError。"""
    Approval.objects.create(proposal=proposal_legislative, by=ProposalOrigin.JUDICIARY)
    with pytest.raises(FinalizeConflictError) as exc_info:
        proposal_legislative.finalize()
    assert "承認が2件必要" in str(exc_info.value)


@pytest.mark.django_db
def test_finalize_fails_expired(proposal_legislative):
    """期限切れの Proposal は finalize できない。"""
    proposal_legislative.expires_at = _past()
    proposal_legislative.save(update_fields=["expires_at"])
    Approval.objects.create(proposal=proposal_legislative, by=ProposalOrigin.JUDICIARY)
    Approval.objects.create(proposal=proposal_legislative, by=ProposalOrigin.EXECUTIVE)
    with pytest.raises(FinalizeConflictError) as exc_info:
        proposal_legislative.finalize()
    assert "期限切れ" in str(exc_info.value)


@pytest.mark.django_db
def test_finalize_fails_already_finalized(proposal_legislative):
    """確定済みの Proposal を再度 finalize すると FinalizeConflictError。"""
    Approval.objects.create(proposal=proposal_legislative, by=ProposalOrigin.JUDICIARY)
    Approval.objects.create(proposal=proposal_legislative, by=ProposalOrigin.EXECUTIVE)
    proposal_legislative.finalize()
    with pytest.raises(FinalizeConflictError) as exc_info:
        proposal_legislative.finalize()
    assert "既に確定済み" in str(exc_info.value)


@pytest.mark.django_db
def test_finalize_fails_when_status_expired(proposal_legislative):
    """status=EXPIRED のとき finalize は FinalizeConflictError。"""
    Approval.objects.create(proposal=proposal_legislative, by=ProposalOrigin.JUDICIARY)
    Approval.objects.create(proposal=proposal_legislative, by=ProposalOrigin.EXECUTIVE)
    proposal_legislative.status = ProposalStatus.EXPIRED
    proposal_legislative.save(update_fields=["status"])
    with pytest.raises(FinalizeConflictError) as exc_info:
        proposal_legislative.finalize()
    assert "期限切れ" in str(exc_info.value)


@pytest.mark.django_db
def test_finalize_fails_when_status_rejected(proposal_legislative):
    """status=REJECTED のとき finalize は FinalizeConflictError。"""
    proposal_legislative.status = ProposalStatus.REJECTED
    proposal_legislative.save(update_fields=["status"])
    with pytest.raises(FinalizeConflictError) as exc_info:
        proposal_legislative.finalize()
    assert "却下済み" in str(exc_info.value)


@pytest.mark.django_db
def test_finalize_fails_when_approval_by_origin(proposal_legislative):
    """承認に origin が含まれる場合（不正データ）finalize は FinalizeConflictError。"""
    # 通常は Approval.clean で弾かれるが、不正に origin 承認が入った場合の finalize 拒否を検証
    Approval.objects.bulk_create([
        Approval(proposal=proposal_legislative, by=ProposalOrigin.JUDICIARY),
        Approval(proposal=proposal_legislative, by=ProposalOrigin.LEGISLATIVE),
    ])
    with pytest.raises(FinalizeConflictError) as exc_info:
        proposal_legislative.finalize()
    assert "発議元" in str(exc_info.value) or "承認" in str(exc_info.value)


# --- 承認の承認禁止・再利用不可・最大2件 ---


@pytest.mark.django_db
def test_approval_by_origin_forbidden(proposal_legislative):
    """発議元（origin）による承認は ValidationError。"""
    with pytest.raises(ValidationError):
        Approval.objects.create(proposal=proposal_legislative, by=ProposalOrigin.LEGISLATIVE)


@pytest.mark.django_db
def test_approval_reuse_same_branch_forbidden(proposal_legislative):
    """同一 (proposal, by) の2件目は UniqueConstraint で拒否。"""
    Approval.objects.create(proposal=proposal_legislative, by=ProposalOrigin.JUDICIARY)
    with pytest.raises((IntegrityError, ValidationError)):
        Approval.objects.create(proposal=proposal_legislative, by=ProposalOrigin.JUDICIARY)


@pytest.mark.django_db
def test_approval_on_finalized_proposal_forbidden(proposal_legislative):
    """確定済みの Proposal に承認を追加すると ValidationError。"""
    Approval.objects.create(proposal=proposal_legislative, by=ProposalOrigin.JUDICIARY)
    Approval.objects.create(proposal=proposal_legislative, by=ProposalOrigin.EXECUTIVE)
    proposal_legislative.finalize()
    with pytest.raises(ValidationError) as exc_info:
        Approval.objects.create(proposal=proposal_legislative, by=ProposalOrigin.EXECUTIVE)
    assert "確定済み" in str(exc_info.value) or "期限切れ" in str(exc_info.value)


@pytest.mark.django_db
def test_required_approvals_constant():
    """required_approvals は 2 固定。"""
    assert REQUIRED_APPROVALS == 2


# --- LAW_CHANGE で憲法（CONST）は対象外（Issue #20） ---


@pytest.mark.django_db
def test_law_change_with_const_law_id_rejected(db):
    """LAW_CHANGE で payload.law_id が CONST のとき保存で ValidationError。"""
    with pytest.raises(ValidationError) as exc_info:
        Proposal.objects.create(
            kind=ProposalKind.LAW_CHANGE,
            origin=ProposalOrigin.LEGISLATIVE,
            law_context={},
            payload={"law_id": LAW_ID_CONST, "title": "憲法改正"},
            expires_at=_future(),
        )
    assert "CONST" in str(exc_info.value)


@pytest.mark.django_db
def test_law_change_with_other_law_id_accepted(db):
    """LAW_CHANGE で payload.law_id が CONST でなければ保存できる。"""
    p = Proposal.objects.create(
        kind=ProposalKind.LAW_CHANGE,
        origin=ProposalOrigin.LEGISLATIVE,
        law_context={},
        payload={"law_id": "L-000120", "title": "某法改正"},
        expires_at=_future(),
    )
    assert p.pk is not None
