# -*- coding: utf-8 -*-
"""i18n: translations, RTL, and language toggle."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui.i18n import TRANSLATIONS, t, is_rtl


def test_translation_function_returns_key_when_missing():
    assert t("no.such.key.xyz", "en") == "no.such.key.xyz"
    assert t("no.such.key.xyz", "ar") == "no.such.key.xyz"


def test_all_nav_keys_exist_in_ar_and_en():
    en = TRANSLATIONS["en"]
    ar = TRANSLATIONS["ar"]
    nav_keys = [k for k in en if k.startswith("nav.")]
    assert len(nav_keys) >= 10
    for k in nav_keys:
        assert k in ar, "missing Arabic translation for %s" % k
        assert ar[k], "empty Arabic translation for %s" % k


def test_translated_pages_have_all_keys():
    """Every t("...") key used by Home, the shared helpers and the
    translated pages exists, non-empty, in both English and Arabic."""
    import re
    files = [ROOT / "app.py", ROOT / "ui_common.py"] + [
        p for p in (ROOT / "pages").glob("*.py")
        if re.match(r"(2|3|4|5|6|7|8|10|11|12)_", p.name)]
    assert len(files) == 12
    used = set()
    for f in files:
        used |= {k for k in re.findall(r'\bt\(\s*"([a-z_]+\.[a-z0-9_.]+)"',
                                       f.read_text(encoding="utf-8"))
                 if not k.endswith(("_", "."))}   # prefix of a built key
    assert len(used) > 150
    for lang in ("en", "ar"):
        missing = sorted(k for k in used if not TRANSLATIONS[lang].get(k))
        assert missing == [], (lang, missing)
    # Arabic strings really are Arabic, not copied English
    for k in used:
        en, ar = TRANSLATIONS["en"][k], TRANSLATIONS["ar"][k]
        if re.search(r"[A-Za-z]{4,}", en) and en == ar:
            raise AssertionError("untranslated: %s" % k)


def test_rtl_when_arabic():
    assert is_rtl("ar") is True
    assert is_rtl("en") is False


def test_settings_json_roundtrip(tmp_path, monkeypatch):
    from ui import settings_store as SS
    monkeypatch.setattr(SS, "_SETTINGS_PATH", tmp_path / "settings.json")
    SS.save_settings({"language": "ar", "daily_email_limit": 50})
    loaded = SS.load_settings()
    assert loaded["language"] == "ar"
    assert loaded["daily_email_limit"] == 50
    assert loaded["sender_name"] == SS.DEFAULTS["sender_name"]


def test_settings_defaults_present():
    from ui.settings_store import DEFAULTS
    required = {"language", "theme", "daily_email_limit",
                "daily_whatsapp_limit", "sender_name", "sender_title",
                "physical_address", "follow_up_days"}
    assert required <= set(DEFAULTS)
    assert DEFAULTS["daily_email_limit"] == 25
    assert DEFAULTS["daily_whatsapp_limit"] == 20
