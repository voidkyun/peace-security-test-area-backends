"""
サービス識別情報（設定ベース）。将来的に mTLS 証明書と連携可能。
"""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ServiceIdentity:
    """呼び出し元サービスの識別情報。"""

    name: str
    key_id: Optional[str] = None  # 将来 mTLS 用
