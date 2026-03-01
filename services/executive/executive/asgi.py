import os
import sys
from pathlib import Path

_services_dir = Path(__file__).resolve().parent.parent.parent
if str(_services_dir) not in sys.path:
    sys.path.insert(0, str(_services_dir))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "executive.settings")

from django.core.asgi import get_asgi_application

application = get_asgi_application()
