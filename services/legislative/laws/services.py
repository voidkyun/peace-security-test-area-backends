"""
LAW_CHANGE 確定時の lawset 新バージョン発行と監査ログ送信（Issue #8）。
"""
import logging
from django.conf import settings
from django.utils import timezone

from shared.auth import issue_jwt
from shared.auth.scopes import AUDIT_WRITE, INDEX_WRITE, PROPOSAL_FINALIZE

from .models import (
    LAWSET_ID_AMATERRACE,
    Law,
    Lawset,
    LawsetMembership,
    LawStatus,
    compute_lawset_digest,
)

logger = logging.getLogger(__name__)


def create_new_lawset_version_from_proposal(proposal):
    """
    確定済み LAW_CHANGE Proposal に基づき新 Lawset バージョンを発行する。
    - 現在の LAWSET-AMATERRACE の最新版をベースに、payload の law_id に対応する Law を新 version で作成し、
      新 Lawset (version+1) と LawsetMembership を作成する。
    - 既存の law_id の場合は Law を law_version+1 で追加。新規 law_id の場合は Law@1 を追加し membership に含める。
    """
    payload = proposal.payload
    law_id = payload.get("law_id")
    title = payload.get("title", "")
    text = payload.get("text", "")

    current = (
        Lawset.objects.filter(lawset_id=LAWSET_ID_AMATERRACE)
        .order_by("-version")
        .first()
    )
    if not current:
        raise ValueError("法体系 LAWSET-AMATERRACE が存在しません。")

    next_version = current.version + 1
    effective_at = timezone.now()

    # 対象 law_id の既存最新 Law を取得
    existing_law = (
        Law.objects.filter(law_id=law_id).order_by("-law_version").first()
    )
    if existing_law:
        new_law = Law.objects.create(
            law_id=law_id,
            law_version=existing_law.law_version + 1,
            title=title,
            status=LawStatus.EFFECTIVE,
            text=text,
        )
    else:
        new_law = Law.objects.create(
            law_id=law_id,
            law_version=1,
            title=title,
            status=LawStatus.EFFECTIVE,
            text=text,
        )

    new_lawset = Lawset.objects.create(
        lawset_id=LAWSET_ID_AMATERRACE,
        version=next_version,
        effective_at=effective_at,
        digest_hash="",  # 下で更新
    )

    # 既存 membership をコピー。対象 law_id のものは new_law に差し替え。それ以外は同じ Law。新規 law_id の場合は末尾に追加。
    memberships_old = (
        LawsetMembership.objects.filter(lawset=current)
        .order_by("order", "law__law_id")
        .select_related("law")
    )
    order = 0
    replaced = False
    for m in memberships_old:
        if m.law.law_id == law_id:
            LawsetMembership.objects.create(
                lawset=new_lawset, law=new_law, order=order
            )
            replaced = True
        else:
            LawsetMembership.objects.create(
                lawset=new_lawset, law=m.law, order=order
            )
        order += 1
    if not replaced:
        # 新規 law_id のため末尾に追加
        LawsetMembership.objects.create(
            lawset=new_lawset, law=new_law, order=order
        )

    parts = []
    for m in (
        LawsetMembership.objects.filter(lawset=new_lawset)
        .order_by("order", "law__law_id")
        .select_related("law")
    ):
        parts.append((m.law.law_id, m.law.law_version, m.law.text))
    new_lawset.digest_hash = compute_lawset_digest(parts)
    new_lawset.save(update_fields=["digest_hash"])

    return new_lawset


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
        service_name=getattr(settings, "SERVICE_NAME", "legislative"),
        scopes=[AUDIT_WRITE],
        secret=secret,
        expires_seconds=60,
    )
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


def register_index(proposal):
    """
    Root の索引に Proposal を登録する（Issue #10）。提案作成後に発議元が呼ぶ。
    """
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
        service_name=getattr(settings, "SERVICE_NAME", "legislative"),
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


def update_index_status(proposal_id, status, finalized_at=None):
    """Root の索引の status を更新する（Issue #10）。finalize 成功後に発議元が呼ぶ。"""
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
        service_name=getattr(settings, "SERVICE_NAME", "legislative"),
        scopes=[INDEX_WRITE],
        secret=secret,
        expires_seconds=60,
    )
    payload = {"status": status}
    if finalized_at is not None:
        payload["finalized_at"] = finalized_at.isoformat()
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


def fetch_approvals_from_service(base_url, proposal_id):
    """
    他サービスの GET /approvals?proposal_id=xxx を呼び、承認リストを返す。
    戻り値: list[dict] 各要素は {"by": str, "reason": str, "references": list}
    失敗時は空リストまたは例外。
    """
    if not base_url:
        return []
    try:
        import requests
    except ImportError:
        return []
    url = f"{base_url}/approvals/"
    secret = getattr(settings, "SERVICE_JWT_SECRET", "")
    token = issue_jwt(
        service_name=getattr(settings, "SERVICE_NAME", "legislative"),
        scopes=[PROPOSAL_FINALIZE],
        secret=secret,
        expires_seconds=60,
    )
    resp = requests.get(
        url,
        params={"proposal_id": str(proposal_id)},
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
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
