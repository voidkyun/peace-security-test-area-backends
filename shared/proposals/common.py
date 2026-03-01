"""
Proposal/Approval の定数・検証ロジック（Issue #10）。
モデルは各サービスが固有に保持。shared は Django アプリとして登録しない。
"""
import hashlib
import json
from django.core.exceptions import ValidationError


# --- 定数（Issue #6 準拠） ---
class ProposalKind:
    LAW_CHANGE = "LAW_CHANGE"
    EXEC_ACTION = "EXEC_ACTION"
    JUDGMENT = "JUDGMENT"
    SYSTEM_CHANGE = "SYSTEM_CHANGE"
    CHOICES = [
        (LAW_CHANGE, "LAW_CHANGE"),
        (EXEC_ACTION, "EXEC_ACTION"),
        (JUDGMENT, "JUDGMENT"),
        (SYSTEM_CHANGE, "SYSTEM_CHANGE"),
    ]


class ProposalOrigin:
    LEGISLATIVE = "LEGISLATIVE"
    JUDICIARY = "JUDICIARY"
    EXECUTIVE = "EXECUTIVE"
    CHOICES = [
        (LEGISLATIVE, "LEGISLATIVE"),
        (JUDICIARY, "JUDICIARY"),
        (EXECUTIVE, "EXECUTIVE"),
    ]


class ProposalStatus:
    PENDING = "PENDING"
    APPROVED = "APPROVED"  # 承認2件付いたが未確定の状態（任意）
    REJECTED = "REJECTED"
    FINALIZED = "FINALIZED"
    EXPIRED = "EXPIRED"
    CHOICES = [
        (PENDING, "PENDING"),
        (APPROVED, "APPROVED"),
        (REJECTED, "REJECTED"),
        (FINALIZED, "FINALIZED"),
        (EXPIRED, "EXPIRED"),
    ]


REQUIRED_APPROVALS = 2

# 憲法の law_id（GENESIS 固定）。LAW_CHANGE では改正対象にできない（Issue #20）
LAW_ID_CONST = "CONST"


def compute_payload_hash(payload: dict) -> str:
    """payload の SHA256 ハッシュ（キーソート JSON）を返す。"""
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class FinalizeConflictError(ValidationError):
    """不正な finalize 試行時に送出。API では 409 Conflict にマッピングする。"""
    pass


def validate_finalize_approvals(origin: str, external_approvals: list) -> None:
    """
    他サービスから取得した承認リストを検証する。違反時は FinalizeConflictError を送出。
    origin: 発議元（ProposalOrigin の値）
    external_approvals: list[dict] 各要素は {'by': str, ...}
    """
    if len(external_approvals) != REQUIRED_APPROVALS:
        raise FinalizeConflictError(
            f"承認が{REQUIRED_APPROVALS}件必要です（現在 {len(external_approvals)} 件）。"
        )
    origins_who_approved = {a["by"] for a in external_approvals}
    if origin in origins_who_approved:
        raise FinalizeConflictError("発議元（origin）は承認に含めません。")
    if len(origins_who_approved) != REQUIRED_APPROVALS:
        raise FinalizeConflictError("承認は異なる2系統から各1件必要です。")
