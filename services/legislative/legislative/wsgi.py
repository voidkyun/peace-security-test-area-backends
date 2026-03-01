import os
import sys
from pathlib import Path

# プロジェクトルートをパスに追加
_project_root = Path(__file__).resolve().parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "legislative.settings")

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
