# -*- coding: utf-8 -*-
"""Loads Control_Center/.env into os.environ exactly once.

Every entry point (app.py, each page, scheduler.run_daily, the
atlas_services package) imports this module first, so nobody has to set
$env:SMTP_* by hand. Variables already set in the environment win
(override=False). Values are never printed — env_status() reports only
whether each variable is present.

Control_Center/.env.local, if it exists, is loaded the same way after
.env (older docs mention it).

Tests set CONTROL_CENTER_NO_DOTENV=1 (tests/conftest.py) so the real
credentials never reach the test process.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
_ENV_PATH = ROOT / ".env"
_ENV_LOCAL_PATH = ROOT / ".env.local"

REQUIRED = [
    "SMTP_HOST", "SMTP_PORT", "SMTP_USER",
    "SMTP_PASSWORD", "SMTP_FROM",
    "WHATSAPP_PHONE_ID", "WHATSAPP_TOKEN",
    "SERPER_API_KEY",
    "TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID",
]


def load_env_file(path, override: bool = False) -> bool:
    """One dotenv file into os.environ; False if it does not exist."""
    p = Path(path)
    return p.is_file() and bool(load_dotenv(p, override=override))


def _load_once() -> bool:
    if os.getenv("CONTROL_CENTER_NO_DOTENV") == "1":
        return False
    loaded = load_env_file(_ENV_PATH, override=True)
    load_env_file(_ENV_LOCAL_PATH, override=True)
    return loaded


_LOADED = _load_once()


def env_status() -> dict:
    """Which required env vars are visible: {name: bool}. Never values."""
    return {k: bool(os.getenv(k)) for k in REQUIRED}
