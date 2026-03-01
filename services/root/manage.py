#!/usr/bin/env python
"""Root サービス用 Django 管理スクリプト。"""
import sys
from pathlib import Path

# 同一リポジトリの services をパスに追加（root パッケージを import 可能にする）
_services_dir = Path(__file__).resolve().parent.parent
if str(_services_dir) not in sys.path:
    sys.path.insert(0, str(_services_dir))

import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "root.settings")
django.setup()

from django.core.management import execute_from_command_line

if __name__ == "__main__":
    execute_from_command_line(sys.argv)
