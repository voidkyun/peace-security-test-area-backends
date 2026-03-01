"""
EXEC_ACTION 確定時のダミー実行キュー登録と監査ログ送信（Issue #9）。
"""
import logging
from django.conf import settings

from shared.auth import issue_jwt
from shared.auth.scopes import AUDIT_WRITE

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
