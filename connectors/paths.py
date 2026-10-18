# -*- coding: utf-8 -*-
"""Where the other two projects live, resolved relative to this folder.

Control_Center, AI_Agent_Test and Web_Bot_Project are expected to be
siblings under the same parent (…/Documents/). An env var overrides each,
so the layout is not pinned to one machine beyond that assumption. Nothing
here is created or written; these are locations to read.
"""

from __future__ import annotations

import os
from pathlib import Path

CC_ROOT = Path(__file__).resolve().parent.parent          # Control_Center/
DOCUMENTS = CC_ROOT.parent                                # its parent


def _resolve(env: str, *rel: str) -> Path:
    override = os.getenv(env)
    if override:
        return Path(override).expanduser()
    return DOCUMENTS.joinpath(*rel)


# The outreach project and the package folder inside it.
OUTREACH_PROJECT = _resolve("CC_OUTREACH_PROJECT",
                            "AI_Agent_Test", "livekit-voice-agent")
OUTREACH_PKG = OUTREACH_PROJECT / "outreach"
OUTREACH_DATA = OUTREACH_PKG / "data"
OUTREACH_RUNS = OUTREACH_DATA / "runs"
OUTREACH_VENV_PY = OUTREACH_PROJECT / ".venv" / "Scripts" / "python.exe"

# The Web Bot project.
WEB_BOT_PROJECT = _resolve("CC_WEB_BOT_PROJECT", "Web_Bot_Project")
WEB_BOT_DB = WEB_BOT_PROJECT / "bot_data.db"
WEB_BOT_LOGS = WEB_BOT_PROJECT / "logs"
WEB_BOT_VENV_PY = WEB_BOT_PROJECT / "venv" / "Scripts" / "python.exe"
WEB_BOT_ENTRY = WEB_BOT_PROJECT / "bot.py"

# Control Center's own writable areas (never inside the other projects).
CC_DATA = CC_ROOT / "data"
CC_REPORTS = CC_ROOT / "reports"
WEB_BOT_PID_FILE = CC_DATA / "web_bot.pid"


def outreach_python() -> str:
    """The outreach venv python if present, else the current interpreter —
    so a subprocess still has a sensible default on a fresh checkout."""
    import sys
    return str(OUTREACH_VENV_PY) if OUTREACH_VENV_PY.exists() else \
        sys.executable


def web_bot_python() -> str:
    import sys
    return str(WEB_BOT_VENV_PY) if WEB_BOT_VENV_PY.exists() else \
        sys.executable


def ensure_cc_data() -> Path:
    CC_DATA.mkdir(parents=True, exist_ok=True)
    return CC_DATA
