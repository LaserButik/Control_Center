# -*- coding: utf-8 -*-
"""Self-contained ATLAS services built inside the Control Center:
website_monitor, seo_intelligence and content_health. Each has a function
API and a `python -m atlas_services.<name>` CLI, and uses `requests` only.

Importing the package loads Control_Center/.env first (config.py), so
every service and every `python -m atlas_services.<name>` CLI sees the
same keys as the Control Center."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(
    __file__))))
import config  # noqa: F401,E402
