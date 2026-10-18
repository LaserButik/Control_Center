# -*- coding: utf-8 -*-
"""Settings store: defaults, persistence, validation, reset."""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui.settings_store import (load_settings, save_settings, reset_settings,
                                DEFAULTS, _SETTINGS_PATH)


def test_settings_file_created_with_defaults(tmp_path, monkeypatch):
    import ui.settings_store as SS
    p = tmp_path / "settings.json"
    monkeypatch.setattr(SS, "_SETTINGS_PATH", p)
    assert not p.exists()
    s = SS.load_settings()
    assert s == DEFAULTS
    SS.save_settings(s)
    assert p.exists()
    raw = json.loads(p.read_bytes().decode("utf-8"))
    assert raw["language"] == "en"
    assert raw["daily_email_limit"] == 25


def test_settings_persist_after_edit(tmp_path, monkeypatch):
    import ui.settings_store as SS
    p = tmp_path / "settings.json"
    monkeypatch.setattr(SS, "_SETTINGS_PATH", p)
    SS.save_settings({"language": "ar", "daily_email_limit": 42,
                      "sender_name": "Ahmad"})
    loaded = SS.load_settings()
    assert loaded["language"] == "ar"
    assert loaded["daily_email_limit"] == 42
    assert loaded["sender_name"] == "Ahmad"


def test_settings_rejects_out_of_range_values(tmp_path, monkeypatch):
    import ui.settings_store as SS
    monkeypatch.setattr(SS, "_SETTINGS_PATH", tmp_path / "settings.json")
    SS.save_settings({"daily_email_limit": 999, "daily_whatsapp_limit": -5,
                      "language": "fr"})
    loaded = SS.load_settings()
    assert loaded["daily_email_limit"] == 100
    assert loaded["daily_whatsapp_limit"] == 1
    assert loaded["language"] == "en"


def test_sender_uses_settings_daily_limit(tmp_path, monkeypatch):
    import ui.settings_store as SS
    from atlas_services.email_sender import EmailSender
    from atlas_services.whatsapp_sender import WhatsAppSender
    from atlas_services import email_tracker as ET
    from atlas_services import whatsapp_tracker as WT
    et = ET.EmailTracker(tmp_path / "email")
    wt = WT.WhatsAppTracker(tmp_path / "wa")
    p = tmp_path / "settings.json"
    monkeypatch.setattr(SS, "_SETTINGS_PATH", p)
    # no settings.json: the hard-coded fallbacks
    assert EmailSender(tracker=et).daily_limit == 25
    assert WhatsAppSender(tracker=wt).daily_limit == 20
    # settings.json wins over the fallback
    SS.save_settings({"daily_email_limit": 7, "daily_whatsapp_limit": 4})
    assert EmailSender(tracker=et).daily_limit == 7
    assert WhatsAppSender(tracker=wt).daily_limit == 4
    # an explicit argument wins over settings.json
    assert EmailSender(tracker=et, daily_limit=3).daily_limit == 3
    assert WhatsAppSender(tracker=wt, daily_limit=2).daily_limit == 2
    # the deliverability ceiling still holds
    SS.save_settings({"daily_email_limit": 90, "daily_whatsapp_limit": 90})
    assert EmailSender(tracker=et).daily_limit == 25
    assert WhatsAppSender(tracker=wt).daily_limit == 20


def test_settings_reset_to_defaults(tmp_path, monkeypatch):
    import ui.settings_store as SS
    p = tmp_path / "settings.json"
    monkeypatch.setattr(SS, "_SETTINGS_PATH", p)
    SS.save_settings({"language": "ar", "daily_email_limit": 77})
    result = SS.reset_settings()
    assert result == DEFAULTS
    loaded = SS.load_settings()
    assert loaded["language"] == "en"
    assert loaded["daily_email_limit"] == 25
