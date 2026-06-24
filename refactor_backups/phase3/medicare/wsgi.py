"""Render entrypoint shim for running Django from repository root."""

import os
import sys
from pathlib import Path

from django.core.wsgi import get_wsgi_application

# Ensure apps like `careapp` resolve when the process starts at repo root.
PROJECT_DIR = Path(__file__).resolve().parent
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "medicare.medicare.settings")

application = get_wsgi_application()
