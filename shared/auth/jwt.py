"""
Service JWT の発行・検証。対称鍵（HS256）を使用。将来 mTLS 追加時は非対称鍵に拡張可能。
"""
import time
from typing import Any

from jose import JWTError, jwt

ALGORITHM = "HS256"
SUB_CLAIM = "sub"
SCOPES_CLAIM = "scopes"


def issue_jwt(
    service_name: str,
    scopes: list[str],
    secret: str,
    expires_seconds: int = 3600,
    key_id: str | None = None,
) -> str:
    """
    サービス名とスコープで JWT を発行する。

    Args:
        service_name: 発行元サービス名（sub クレーム）
        scopes: 付与するスコープ一覧
        secret: 署名用シークレット（全サービスで共有を想定）
        expires_seconds: 有効期限（秒）
        key_id: オプション。将来 mTLS 用

    Returns:
        エンコードされた JWT 文字列
    """
    now = int(time.time())
    payload: dict[str, Any] = {
        SUB_CLAIM: service_name,
        SCOPES_CLAIM: scopes,
        "iat": now,
        "exp": now + expires_seconds,
    }
    if key_id:
        payload["kid"] = key_id
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def verify_jwt(token: str, secret: str) -> dict[str, Any]:
    """
    JWT を検証しペイロードを返す。

    Args:
        token: Bearer 除去前後の JWT 文字列
        secret: 検証用シークレット

    Returns:
        sub, scopes, iat, exp 等を含むペイロード

    Raises:
        JWTError: トークンが無効または期限切れの場合
    """
    return jwt.decode(token.strip(), secret, algorithms=[ALGORITHM])
