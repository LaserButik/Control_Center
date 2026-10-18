# -*- coding: utf-8 -*-
"""ATLAS channel router: which channels each prospect gets."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from atlas_services import channel_router as R          # noqa: E402
from atlas_services import email_tracker as ET          # noqa: E402
from atlas_services import whatsapp_tracker as WT       # noqa: E402

BASE = {"company_name": "Smile Dental Clinic", "sector": "clinics",
        "country": "AE"}
NONE = {"suppressed_emails": set(), "suppressed_phones": set()}


def r(**kw):
    return R.route(dict(BASE, **kw), **NONE)


def test_both_available_routes_to_both():
    out = r(email="sara@smileclinic.ae", phone_e164="+971501234567")
    assert out == {"channels": ["email", "whatsapp"], "primary": "email",
                   "secondary": "whatsapp", "skip": False,
                   "reason": "both_available",
                   "email": "sara@smileclinic.ae",
                   "phone_e164": "+971501234567"}
    # a role address with a mobile: still both, WhatsApp first
    role = r(email="info@smileclinic.ae", phone_e164="+971 50 123 4567")
    assert role["channels"] == ["whatsapp", "email"]
    assert (role["primary"], role["secondary"], role["reason"]) == (
        "whatsapp", "email", "both_available")
    # a Saudi prospect works the same way
    sa = r(email="sara@clinic.sa", phone_e164="+966501234567", country="SA")
    assert sa["reason"] == "both_available"


def test_email_only_routes_to_email():
    for kw in ({"email": "sara@smileclinic.ae"},
               {"email": "sara@smileclinic.ae", "phone_e164": "+97142223333"}):
        out = r(**kw)                                  # none / a landline
        assert (out["channels"], out["primary"], out["secondary"],
                out["reason"]) == (["email"], "email", None, "email_only")


def test_whatsapp_only_routes_to_whatsapp():
    out = r(phone_e164="+971501234567")
    assert (out["channels"], out["primary"], out["secondary"],
            out["reason"], out["skip"]) == (["whatsapp"], "whatsapp", None,
                                            "whatsapp_only", False)
    # country taken from the phone when the prospect has none
    out = R.route({"company_name": "X", "sector": "salons",
                   "phone_e164": "+966551234567"}, **NONE)
    assert out["reason"] == "whatsapp_only"


def test_unknown_sector_skips():
    for sector in ("unknown", None, "bakeries"):
        out = r(sector=sector, email="sara@smileclinic.ae",
                phone_e164="+971501234567")
        assert out["skip"] and out["channels"] == [] and \
            out["reason"] == "blocked_sector", sector
    assert r(email="a@b.kw", country="KW")["reason"] == "blocked_country"
    assert r()["reason"] == "no_contact"
    assert r(email="not-an-email")["reason"] == "no_contact"
    for out in (r(sector="unknown"), r(), r(country="KW", email="a@b.kw")):
        assert out["skip"] is True and out["primary"] is None


def test_both_suppressed_skips(tmp_path):
    p = dict(BASE, email="sara@smileclinic.ae", phone_e164="+971501234567")
    ET.add_to_suppression(p["email"], "replied", tmp_path / "email")
    WT.add_to_suppression(p["phone_e164"], "replied", tmp_path / "wa")
    dirs = {"email_data_dir": tmp_path / "email",
            "wa_data_dir": tmp_path / "wa"}
    out = R.route(p, **dirs)
    assert out["skip"] and out["reason"] == "suppressed" and \
        out["channels"] == []
    # only one suppressed: the other channel alone
    out = R.route(dict(p, phone_e164="+971551112222"), **dirs)
    assert out["channels"] == ["whatsapp"] and out["reason"] == \
        "whatsapp_only"
    out = R.route(dict(p, email="new@smileclinic.ae"), **dirs)
    assert out["channels"] == ["email"]


def test_stats_counts_correctly():
    rows = [dict(BASE, email="a@a.ae", phone_e164="+971501111111"),
            dict(BASE, email="b@b.ae", phone_e164="+971502222222"),
            dict(BASE, email="c@c.ae"),
            dict(BASE, phone_e164="+971503333333"),
            dict(BASE),
            dict(BASE, sector="unknown", email="d@d.ae"),
            dict(BASE, country="KW", email="e@e.kw"),
            dict(BASE, email="f@f.ae", phone_e164="+971504444444")]
    routes = R.route_batch(rows, suppressed_emails={"f@f.ae"},
                           suppressed_phones={"+971504444444"})
    assert len(routes) == len(rows)
    st = R.stats(routes)
    assert {k: st[k] for k in R.STAT_KEYS} == {
        "both": 2, "email_only": 1, "whatsapp_only": 1, "no_contact": 1,
        "unknown": 1}
    assert (st["suppressed"], st["blocked_country"], st["total"]) == (1, 1, 8)
    assert R.stats([]) == dict(dict.fromkeys(R.STAT_KEYS, 0), suppressed=0,
                               blocked_country=0, total=0)
