# サービス間認証（Service JWT + 将来 mTLS）

from shared.auth.jwt import issue_jwt, verify_jwt
from shared.auth.permissions import RequireScope, require_scope
from shared.auth.scopes import (
    ALL_SCOPES,
    APPROVAL_WRITE,
    AUDIT_READ,
    AUDIT_WRITE,
    PROPOSAL_FINALIZE,
    PROPOSAL_READ,
    PROPOSAL_WRITE,
)
from shared.auth.service_identity import ServiceIdentity

__all__ = [
    "issue_jwt",
    "verify_jwt",
    "RequireScope",
    "require_scope",
    "ServiceIdentity",
    "ALL_SCOPES",
    "PROPOSAL_READ",
    "PROPOSAL_WRITE",
    "APPROVAL_WRITE",
    "PROPOSAL_FINALIZE",
    "AUDIT_READ",
    "AUDIT_WRITE",
]
