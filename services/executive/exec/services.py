"""
EXEC_ACTION 確定時のダミー実行キュー登録と監査ログ送信（Issue #9）。
"""
import logging
from django.conf import settings

from shared.auth import issue_jwt
from shared.auth.scopes import AUDIT_WRITE, INDEX_WRITE, PROPOSAL_FINALIZE

from .models import ExecutionQueueItem

logger = logging.getLogger(__name__)


def enqueue_execution(proposal_id):
    """
    確定済み EXEC_ACTION をダミー実行キューに1件追加する。
    """
    ExecutionQueueItem.objects.create(
        proposal_id=proposal_id,
        status=ExecutionQueueItem.Status.PENDING,
    )
    logger.info("実行キューに追加: proposal_id=%s", proposal_id)


def send_audit_event(payload):
    """
    Root サービスの /audit/events/ に監査イベントを POST する。
    ROOT_SERVICE_URL が未設定の場合は送信しない（開発時用）。
    """
    base_url = getattr(settings, "ROOT_SERVICE_URL", "").rstrip("/")
    if not base_url:
        logger.warning("ROOT_SERVICE_URL が未設定のため監査ログを送信しません。")
        return

    try:
        import requests
    except ImportError:
        logger.warning("requests が利用できないため監査ログを送信しません。")
        return

    url = f"{base_url}/audit/events/"
    secret = getattr(settings, "SERVICE_JWT_SECRET", "")
    token = issue_jwt(
        service_name=getattr(settings, "SERVICE_NAME", "executive"),
        scopes=[AUDIT_WRITE],
        secret=secret,
        expires_seconds=60,
    )
    try:
        resp = requests.post(
            url,
            json={"payload": payload},
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=10,
        )
        if resp.status_code not in (200, 201):
            logger.warning(
                "監査ログ送信失敗: %s %s", resp.status_code, resp.text[:200]
            )
        else:
            logger.info("監査ログ送信成功: proposal_id=%s", payload.get("proposal_id"))
    except requests.exceptions.RequestException as e:
        logger.warning("監査ログ送信エラー（接続失敗等）: %s", e)


def register_index(proposal):
    """Root の索引に Proposal を登録する（Issue #10）。"""
    base_url = getattr(settings, "ROOT_SERVICE_URL", "").rstrip("/")
    if not base_url:
        logger.warning("ROOT_SERVICE_URL が未設定のため索引を登録しません。")
        return
    try:
        import requests
    except ImportError:
        logger.warning("requests が利用できないため索引を登録しません。")
        return
    url = f"{base_url}/index/entries/"
    secret = getattr(settings, "SERVICE_JWT_SECRET", "")
    token = issue_jwt(
        service_name=getattr(settings, "SERVICE_NAME", "executive"),
        scopes=[INDEX_WRITE],
        secret=secret,
        expires_seconds=60,
    )
    payload = {
        "proposal_id": str(proposal.proposal_id),
        "kind": proposal.kind,
        "origin": proposal.origin,
        "status": proposal.status,
        "payload": proposal.payload,
        "created_at": proposal.created_at.isoformat(),
        "expires_at": proposal.expires_at.isoformat(),
    }
    try:
        resp = requests.post(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=10,
        )
        if resp.status_code not in (200, 201):
            logger.warning("索引登録失敗: %s %s", resp.status_code, resp.text[:200])
        else:
            logger.info("索引登録成功: proposal_id=%s", proposal.proposal_id)
    except requests.exceptions.RequestException as e:
        logger.warning("索引登録エラー: %s", e)


def update_index_status(proposal_id, status, finalized_at=None):
    """Root の索引の status を更新する（Issue #10）。"""
    base_url = getattr(settings, "ROOT_SERVICE_URL", "").rstrip("/")
    if not base_url:
        logger.warning("ROOT_SERVICE_URL が未設定のため索引を更新しません。")
        return
    try:
        import requests
    except ImportError:
        logger.warning("requests が利用できないため索引を更新しません。")
        return
    url = f"{base_url}/index/entries/{proposal_id}/"
    secret = getattr(settings, "SERVICE_JWT_SECRET", "")
    token = issue_jwt(
        service_name=getattr(settings, "SERVICE_NAME", "executive"),
        scopes=[INDEX_WRITE],
        secret=secret,
        expires_seconds=60,
    )
    payload = {"status": status}
    if finalized_at is not None:
        payload["finalized_at"] = finalized_at.isoformat()
    try:
        resp = requests.patch(
            url,
            json=payload,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            timeout=10,
        )
        if resp.status_code != 200:
            logger.warning("索引更新失敗: %s %s", resp.status_code, resp.text[:200])
        else:
            logger.info("索引更新成功: proposal_id=%s status=%s", proposal_id, status)
    except requests.exceptions.RequestException as e:
        logger.warning("索引更新エラー: %s", e)


def fetch_approvals_from_service(base_url, proposal_id):
    """他サービスの GET /approvals?proposal_id=xxx を呼び、承認リストを返す。"""
    if not base_url:
        return []
    try:
        import requests
    except ImportError:
        return []
    url = f"{base_url}/approvals/"
    secret = getattr(settings, "SERVICE_JWT_SECRET", "")
    token = issue_jwt(
        service_name=getattr(settings, "SERVICE_NAME", "executive"),
        scopes=[PROPOSAL_FINALIZE],
        secret=secret,
        expires_seconds=60,
    )
    try:
        resp = requests.get(
            url,
            params={"proposal_id": str(proposal_id)},
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
    except requests.exceptions.RequestException:
        return []
    if resp.status_code != 200:
        logger.warning("承認取得失敗 %s: %s %s", base_url, resp.status_code, resp.text[:200])
        return []
    data = resp.json()
    if not isinstance(data, list):
        return []
    return [
        {"by": item["by"], "reason": item["reason"], "references": item["references"]}
        for item in data
        if isinstance(item, dict) and "by" in item and "reason" in item and "references" in item
    ]
