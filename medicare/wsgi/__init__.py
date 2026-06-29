import os
import sys
from pathlib import Path
from django.core.wsgi import get_wsgi_application

# Ensure app modules are discoverable from the repository root
PROJECT_DIR = Path(__file__).resolve().parent.parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "medicare.medicare.settings")

application = get_wsgi_application()
