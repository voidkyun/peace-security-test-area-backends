"""
shared.proposals の定数・validate_finalize_approvals の単体テスト（Issue #10）。
Proposal/Approval モデルは各サービスに移したため、ここでは定数と検証関数のみ検証。
"""
import pytest
from shared.proposals.common import (
    ProposalKind,
    ProposalOrigin,
    ProposalStatus,
    FinalizeConflictError,
    compute_payload_hash,
    validate_finalize_approvals,
    REQUIRED_APPROVALS,
    LAW_ID_CONST,
)


def test_required_approvals_constant():
    """REQUIRED_APPROVALS は 2 固定。"""
    assert REQUIRED_APPROVALS == 2


def test_law_id_const():
    """LAW_ID_CONST は CONST。"""
    assert LAW_ID_CONST == "CONST"


def test_compute_payload_hash():
    """compute_payload_hash はキーソート JSON の SHA256。"""
    h = compute_payload_hash({"a": 1, "b": 2})
    assert h == compute_payload_hash({"b": 2, "a": 1})
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_validate_finalize_approvals_success():
    """2系統から各1件の承認なら検証通過。"""
    validate_finalize_approvals(
        ProposalOrigin.LEGISLATIVE,
        [{"by": ProposalOrigin.JUDICIARY}, {"by": ProposalOrigin.EXECUTIVE}],
    )


def test_validate_finalize_approvals_insufficient():
    """承認が1件のみなら FinalizeConflictError。"""
    with pytest.raises(FinalizeConflictError) as exc_info:
        validate_finalize_approvals(
            ProposalOrigin.LEGISLATIVE,
            [{"by": ProposalOrigin.JUDICIARY}],
        )
    assert "承認が2件必要" in str(exc_info.value)


def test_validate_finalize_approvals_origin_included():
    """発議元が承認に含まれると FinalizeConflictError。"""
    with pytest.raises(FinalizeConflictError) as exc_info:
        validate_finalize_approvals(
            ProposalOrigin.LEGISLATIVE,
            [{"by": ProposalOrigin.LEGISLATIVE}, {"by": ProposalOrigin.EXECUTIVE}],
        )
    assert "発議元" in str(exc_info.value)


def test_validate_finalize_approvals_same_branch_twice():
    """同一系統が2件あると FinalizeConflictError（異なる2系統から各1件必要）。"""
    with pytest.raises(FinalizeConflictError) as exc_info:
        validate_finalize_approvals(
            ProposalOrigin.LEGISLATIVE,
            [{"by": ProposalOrigin.JUDICIARY}, {"by": ProposalOrigin.JUDICIARY}],
        )
    assert "異なる2系統" in str(exc_info.value)
