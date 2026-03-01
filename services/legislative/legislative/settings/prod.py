"""
規範生成系（立法）サービス用 Django 設定（本番環境）。
"""
from .base import *

DEBUG = False

ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "").split(",")
if not any(ALLOWED_HOSTS):
    raise ValueError("本番では ALLOWED_HOSTS を環境変数で設定してください")
