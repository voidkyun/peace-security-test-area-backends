# サービス間認証で用いる scope 定数（Issue #4）

PROPOSAL_READ = "proposal.read"
PROPOSAL_WRITE = "proposal.write"
APPROVAL_WRITE = "approval.write"
PROPOSAL_FINALIZE = "proposal.finalize"
AUDIT_WRITE = "audit.write"
AUDIT_READ = "audit.read"
INDEX_WRITE = "index.write"
INDEX_READ = "index.read"

ALL_SCOPES = (
    PROPOSAL_READ,
    PROPOSAL_WRITE,
    APPROVAL_WRITE,
    PROPOSAL_FINALIZE,
    AUDIT_WRITE,
    AUDIT_READ,
    INDEX_WRITE,
    INDEX_READ,
)
