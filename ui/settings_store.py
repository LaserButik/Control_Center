# -*- coding: utf-8 -*-
"""Read and write data/settings.json.

Non-secret values only (language, limits, sender identity). The file is
safe to commit. Secret values stay in .env.
"""

from __future__ import annotations

import json
from pathlib import Path

_SETTINGS_PATH = Path(__file__).resolve().parent.parent / "data" / "settings.json"

DEFAULTS = {
    "language": "en",
    "theme": "dark",
    "daily_email_limit": 25,
    "daily_whatsapp_limit": 20,
    "sender_name": "Saleh",
    "sender_title": "Founder, AI Mentors Agency",
    "physical_address": "AI Mentors Agency, Business Bay, Dubai, UAE",
    "follow_up_days": [0, 2, 3, 7, 14],
    "sidebar_groups": {"overview": True, "pipeline": True,
                       "atlas": True, "system": True},
}

_VALIDATORS = {
    "language": lambda v: v if v in ("ar", "en") else DEFAULTS["language"],
    "daily_email_limit": lambda v: max(1, min(100, int(v))),
    "daily_whatsapp_limit": lambda v: max(1, min(100, int(v))),
    "sender_name": lambda v: str(v).strip() or DEFAULTS["sender_name"],
    "sender_title": lambda v: str(v).strip() or DEFAULTS["sender_title"],
    "physical_address": lambda v: str(v).strip() or DEFAULTS["physical_address"],
    "follow_up_days": lambda v: v if isinstance(v, list) and all(
        isinstance(d, int) and 0 <= d <= 30 for d in v
    ) else DEFAULTS["follow_up_days"],
    "sidebar_groups": lambda v: {
        k: bool(v.get(k, True)) for k in ("overview", "pipeline", "atlas", "system")
    } if isinstance(v, dict) else DEFAULTS["sidebar_groups"],
}


def load_settings() -> dict:
    merged = dict(DEFAULTS)
    if _SETTINGS_PATH.is_file():
        try:
            raw = json.loads(_SETTINGS_PATH.read_bytes().decode("utf-8"))
            if isinstance(raw, dict):
                merged.update(raw)
        except (json.JSONDecodeError, OSError):
            pass
    return merged


def save_settings(data: dict) -> None:
    validated = {}
    for k, default in DEFAULTS.items():
        raw = data.get(k, default)
        fn = _VALIDATORS.get(k)
        try:
            validated[k] = fn(raw) if fn else raw
        except (ValueError, TypeError):
            validated[k] = default
    _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _SETTINGS_PATH.write_bytes(
        json.dumps(validated, ensure_ascii=False, indent=2).encode("utf-8")
    )


def settings_limit(key: str, fallback: int) -> int:
    """An integer setting (e.g. daily_email_limit) from settings.json, or
    `fallback` when the file is missing or the value is unusable."""
    try:
        if not _SETTINGS_PATH.is_file():
            return int(fallback)
        return int(load_settings().get(key, fallback))
    except (TypeError, ValueError):
        return int(fallback)


def reset_settings() -> dict:
    save_settings(dict(DEFAULTS))
    return dict(DEFAULTS)
