"""
Root サービス用 Django 設定（開発環境）。
"""
from .base import *

DEBUG = True

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0"]
