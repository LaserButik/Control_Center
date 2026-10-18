# -*- coding: utf-8 -*-
"""The daily outreach run (scheduler.run_daily) and its Windows Task
Scheduler setup. See scheduler/README.md."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(
    __file__))))
import config  # noqa: F401,E402  (loads Control_Center/.env)
