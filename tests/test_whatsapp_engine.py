# -*- coding: utf-8 -*-
"""ATLAS WhatsApp engine: templates and sender. Meta is a fake http_post,
storage lives in tmp_path, sockets and requests refuse."""

import json
import logging
import re
import socket
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from atlas_services import whatsapp_templates as W      # noqa: E402
from atlas_services import whatsapp_sender as WS        # noqa: E402
from atlas_services import whatsapp_tracker as WT       # noqa: E402

TOKEN = "EAAG-secret-token-123"
PHONE_ID = "109876543210"
T0 = datetime(2026, 10, 7, 8, 0, tzinfo=timezone.utc)
P = {"phone_e164": "+971501234567", "company_name": "Smile Dental Clinic",
     "sector": "clinics", "country": "AE"}
ALL_NAMES = {t["name"] for t in W.all_templates()}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("real network touched")
    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(socket, "create_connection", boom)
    if WS.requests is not None:
        monkeypatch.setattr(WS.requests, "post", boom)
    for k in ("WHATSAPP_PHONE_ID", "WHATSAPP_TOKEN", "META_GRAPH_VERSION",
              "WHATSAPP_APPROVED_TEMPLATES", "WHATSAPP_DAY0_FALLBACK"):
        monkeypatch.delenv(k, raising=False)


class Meta:
    """Fake Meta Cloud API."""
    def __init__(self, status=200, data=None, error=None):
        self.calls, self.status, self.error = [], status, error
        self.data = data if data is not None else {
            "messages": [{"id": "wamid.TEST1"}],
            "contacts": [{"wa_id": "971501234567"}]}

    def __call__(self, url, headers, body, timeout):
        self.calls.append({"url": url, "headers": headers, "body": body})
        if self.error:
            raise self.error
        return self.status, self.data


def make(tmp_path, meta=None, **kw):
    kw.setdefault("approved_templates", ALL_NAMES)
    kw.setdefault("day0_fallback", None)
    tracker = WT.WhatsAppTracker(tmp_path, now=lambda: T0)
    return WS.WhatsAppSender(phone_id=PHONE_ID, access_token=TOKEN,
                             http_post=meta if meta is not None else Meta(),
                             tracker=tracker, now=lambda: T0,
                             sleep=lambda s: None, **kw)


def tpl(tid="wa_clinics_en_day0"):
    return W.get_template_by_id(tid)


# ── templates ──

def test_all_twenty_whatsapp_templates_exist():
    ids = W.list_all_ids()
    assert len(ids) == 20 and len(set(ids)) == 20
    names = [W.get_template_by_id(i)["name"] for i in ids]
    assert len(set(names)) == 20
    assert all(re.fullmatch(r"[a-z0-9_]+", n) for n in names)
    assert W.get_template_by_id("wa_clinics_ar_day0")["name"] == \
        "alpha_clinics_ar_v1"
    assert W.get_template_by_id("wa_clinics_ar_day2")["name"] == \
        "alpha_clinics_ar_followup"
    for t in W.all_templates():
        assert t["variables"] == ["{company_name}"]
    assert set(W.LATE_TEMPLATES) == {"ar", "en"}         # day7 nudges


def test_each_sector_has_ar_and_en():
    assert list(W.TEMPLATES) == ["clinics", "real_estate", "restaurants",
                                 "salons", "lawyers"]
    for sector in W.TEMPLATES:
        assert set(W.TEMPLATES[sector]) == {"ar", "en"}
        for lang in ("ar", "en"):
            seq = W.get_sequence(sector, lang)
            assert [t["category"] for t in seq] == ["day0_initial",
                                                    "day2_followup"]
            assert all(t["language"] == lang for t in seq)
    with pytest.raises(KeyError):
        W.get_templates("bakeries", "en")
    with pytest.raises(KeyError):
        W.get_templates("clinics", "fr")


def test_whatsapp_body_under_160_chars():
    for t in W.all_templates():
        assert len(t["body"]) <= 160, (t["id"], len(t["body"]))
        assert W.problems(t) == [], (t["id"], W.problems(t))
        assert t["body"].count("{company_name}") == 1
        assert not t["body"].startswith("{")             # Meta rule
        assert t["body"].rstrip().endswith(("?", "؟")), t["id"]


def test_no_emojis_in_whatsapp_body():
    emoji = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍]")
    for t in W.all_templates():
        assert not emoji.search(t["body"]), t["id"]
        assert not re.search(r"\b[A-Z]{3,}\b", t["body"]), t["id"]
        assert not re.search(r"\b(guarantee\w*|free|urgent|click here)\b",
                             t["body"], re.I), t["id"]
    bad = dict(tpl(), body="Hello {company_name} \U0001F600 is it FREE?")
    assert {"emoji", "banned word", "all-caps word"} <= set(W.problems(bad))


def test_no_links_in_first_message():
    day0 = [t for t in W.all_templates() if t["day"] == "day0"]
    assert len(day0) == 10
    for t in W.all_templates():
        assert not re.search(r"https?://|www\.|\.(com|ae|sa)\b", t["body"],
                             re.I), t["id"]
        assert not re.search(r"\+?\d[\d\s\-]{6,}\d", t["body"]), t["id"]
    bad = dict(tpl(), body="Hi {company_name}, see www.alpha.ae or call "
                           "+971 4 555 0101?")
    assert {"link", "phone number"} <= set(W.problems(bad))


def test_render_produces_meta_payload(tmp_path):
    r = W.render(tpl(), dict(P, company_name="  Smile\tDental\nClinic  "))
    assert r["template_name"] == "alpha_clinics_en_v1"
    assert r["language"] == "en"
    assert r["variables"] == [{"type": "text", "text": "Smile Dental Clinic"}]
    meta = Meta()
    s = make(tmp_path, meta, dry_run=False)
    out = s.send(P, tpl(), confirmed=True)
    assert out["status"] == "sent" and out["message_id"] == "wamid.TEST1"
    assert out["wa_id"] == "971501234567"
    call = meta.calls[0]
    assert call["url"] == ("https://graph.facebook.com/v22.0/%s/messages"
                           % PHONE_ID)
    assert call["headers"]["Authorization"] == "Bearer %s" % TOKEN
    assert call["body"] == {
        "messaging_product": "whatsapp", "to": "971501234567",
        "type": "template",
        "template": {"name": "alpha_clinics_en_v1",
                     "language": {"code": "en"},
                     "components": [{"type": "body", "parameters": [
                         {"type": "text", "text": "Smile Dental Clinic"}]}]}}
    payloads = W.export_for_meta_submission()
    assert len(payloads) == 22                       # 20 + two day7 nudges
    for p in payloads:
        body = p["components"][0]["text"]
        assert "{{1}}" in body and "{company_name}" not in body
        assert p["category"] == "MARKETING" and p["language"] in ("ar", "en")
        assert p["components"][0]["example"]["body_text"] == [
            ["Smile Dental Clinic"]]


def test_dry_run_never_calls_meta_api(tmp_path):
    meta = Meta()
    s = make(tmp_path, meta)                            # dry_run default
    assert s.dry_run is True
    out = s.send(P, tpl(), confirmed=True)
    assert (out["ok"], out["status"], out["reason"]) == (True, "dry_run",
                                                          "dry_run")
    assert meta.calls == []


def test_confirmed_false_never_calls_meta_api(tmp_path):
    meta = Meta()
    s = make(tmp_path, meta, dry_run=False)
    out = s.send(P, tpl())
    assert (out["status"], out["reason"]) == ("dry_run", "not_confirmed")
    assert meta.calls == []


def test_both_flags_required(tmp_path):
    meta = Meta()
    s = make(tmp_path, meta, dry_run=False)
    assert s.send(P, tpl(), confirmed=True)["status"] == "sent"
    assert len(meta.calls) == 1
    # not configured: fails before any call
    meta2 = Meta()
    s2 = WS.WhatsAppSender(http_post=meta2, dry_run=False, now=lambda: T0,
                           approved_templates=ALL_NAMES, day0_fallback=None,
                           tracker=WT.WhatsAppTracker(tmp_path / "b",
                                                      now=lambda: T0))
    r = s2.send(P, tpl(), confirmed=True)
    assert r["reason"] == "whatsapp_not_configured" and meta2.calls == []
    # a template Meta has not approved is never sent...
    meta3 = Meta()
    s3 = make(tmp_path / "c", meta3, dry_run=False, approved_templates=set())
    r = s3.send(P, tpl(), confirmed=True)
    assert r["reason"] == "template_not_approved" and meta3.calls == []
    # ...except day0, through the approved fallback (two parameters)
    meta4 = Meta()
    s4 = make(tmp_path / "d", meta4, dry_run=False,
              approved_templates={"alpha_intro_v1_en"},
              day0_fallback=("alpha_intro_v1_en", "en"))
    r = s4.send(P, W.get_template_by_id("wa_clinics_ar_day0"),
                confirmed=True)
    assert r["status"] == "sent" and r["fallback"] is True
    t = meta4.calls[0]["body"]["template"]
    assert t["name"] == "alpha_intro_v1_en" and t["language"]["code"] == "en"
    assert [p["text"] for p in t["components"][0]["parameters"]] == [
        "Smile Dental Clinic", "healthcare"]
    r = s4.send(dict(P, phone_e164="+971551112222"),
                tpl("wa_clinics_en_day2"), confirmed=True)
    assert r["reason"] == "template_not_approved"     # no fallback for day2
    # Meta error answers are failures, not exceptions
    bad = Meta(status=400, data={"error": {"message": "Template name does "
                                           "not exist", "code": 132001}})
    r = make(tmp_path / "e", bad, dry_run=False).send(P, tpl(),
                                                      confirmed=True)
    assert r["status"] == "failed" and "132001" in r["reason"]


def test_rejects_non_mobile_phone(tmp_path):
    meta = Meta()
    s = make(tmp_path, meta, dry_run=False)
    for phone in ("+97142223333", "+966112345678", "+97180012345"):
        r = s.send(dict(P, phone_e164=phone, country=WS.phone_country(
            phone)), tpl(), confirmed=True)
        assert r["reason"] == "not_mobile", phone
    for bad in ("", None, "12345", "0501234567x"):
        assert s.send(dict(P, phone_e164=bad), tpl(),
                      confirmed=True)["reason"] == "invalid_phone", bad
    assert meta.calls == []
    assert WS.is_mobile("+966501234567") and WS.is_mobile("00971 50 123 4567")
    ok = make(tmp_path / "sa").send(dict(P, phone_e164="+966501234567",
                                         country="SA"), tpl())
    assert ok["status"] == "dry_run"


def test_rejects_non_target_country(tmp_path):
    meta = Meta()
    s = make(tmp_path, meta, dry_run=False)
    r = s.send(dict(P, phone_e164="+923001234567", country="PK"), tpl(),
               confirmed=True)
    assert r["reason"] == "country_not_allowed"
    r = s.send(dict(P, country="KW"), tpl(), confirmed=True)
    assert r["reason"] == "country_not_allowed"
    r = s.send(dict(P, country="SA"), tpl(), confirmed=True)
    assert r["reason"] == "country_mismatch"
    assert meta.calls == []
    # suppression and replies block too
    WS.add_to_suppression("+971 50 123 4567", "asked", data_dir=tmp_path)
    assert WS.is_suppressed(P["phone_e164"], tmp_path)
    assert s.send(P, tpl(), confirmed=True)["reason"] == "suppressed"


def test_never_logs_access_token(tmp_path, caplog, capsys):
    caplog.set_level(logging.DEBUG)
    ok_meta = Meta()
    s = make(tmp_path, ok_meta, dry_run=False)
    ok = s.send(P, tpl(), confirmed=True)
    s.tracker.record_sent(P, "wa_clinics_en_day0", ok)
    denied = Meta(status=401, data={"error": {
        "message": "Invalid OAuth access token %s" % TOKEN, "code": 190}})
    s2 = make(tmp_path / "b", denied, dry_run=False)
    r2 = s2.send(P, tpl(), confirmed=True)
    s2.tracker.record_sent(P, "wa_clinics_en_day0", r2)
    boom = Meta(error=RuntimeError("connection reset for token=%s" % TOKEN))
    s3 = make(tmp_path / "c", boom, dry_run=False)
    r3 = s3.send(P, tpl(), confirmed=True)
    assert r2["status"] == r3["status"] == "failed"
    assert "***" in r2["reason"] and "***" in r3["reason"]
    out = capsys.readouterr()
    seen = [caplog.text, out.out, out.err, repr(s), json.dumps(
        s.config_summary()), json.dumps([ok, r2, r3])]
    for f in tmp_path.rglob("*"):
        if f.is_file():
            seen.append(f.read_bytes().decode("utf-8", "replace"))
    for text in seen:
        assert TOKEN not in text
        assert PHONE_ID not in text
    assert s.config_summary()["token_set"] is True
