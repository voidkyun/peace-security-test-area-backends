#!/usr/bin/env python
"""法則審査系（司法）サービス用 Django 管理スクリプト。"""
import sys
from pathlib import Path

_services_dir = Path(__file__).resolve().parent.parent
if str(_services_dir) not in sys.path:
    sys.path.insert(0, str(_services_dir))

import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "judiciary.settings")
django.setup()

from django.core.management import execute_from_command_line

if __name__ == "__main__":
    execute_from_command_line(sys.argv)
