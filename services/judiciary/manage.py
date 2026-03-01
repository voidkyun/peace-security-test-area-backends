#!/usr/bin/env python
"""法則審査系（司法）サービス用 Django 管理スクリプト。"""
import sys
from pathlib import Path

# プロジェクトルート（judiciary パッケージを import 可能にする）
_project_root = Path(__file__).resolve().parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "judiciary.settings")
django.setup()

from django.core.management import execute_from_command_line

if __name__ == "__main__":
    execute_from_command_line(sys.argv)
