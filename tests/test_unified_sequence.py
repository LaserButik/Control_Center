# -*- coding: utf-8 -*-
"""ATLAS unified sequence: both channels on one timeline. SMTP and Meta
are fakes, the clock is injected, storage lives in tmp_path."""

import socket
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from atlas_services import channel_router                 # noqa: E402
from atlas_services import email_tracker as ET            # noqa: E402
from atlas_services import whatsapp_templates as W        # noqa: E402
from atlas_services import whatsapp_tracker as WT         # noqa: E402
from atlas_services.email_sender import EmailSender       # noqa: E402
from atlas_services.email_sequence import EmailSequence   # noqa: E402
from atlas_services.unified_sequence import (             # noqa: E402
    SequenceStore, UnifiedSequence)
from atlas_services.whatsapp_sender import (              # noqa: E402
    WhatsAppSender, WhatsAppSequence)

T0 = datetime(2026, 10, 7, 6, 0, tzinfo=timezone.utc)      # 10:00 Dubai
P = {"email": "sara@smileclinic.ae", "phone_e164": "+971501234567",
     "company_name": "Smile Dental Clinic", "sector": "clinics",
     "country": "AE"}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("real network touched")
    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(socket, "create_connection", boom)


class Clock:
    def __init__(self):
        self.t = T0

    def __call__(self):
        return self.t


class SMTP:
    def __init__(self):
        self.messages = []

    def __call__(self, host, port, timeout=None):
        return self

    def starttls(self, **kw):
        pass

    def login(self, user, password):
        pass

    def send_message(self, msg):
        self.messages.append(msg)

    def quit(self):
        pass


class Meta:
    def __init__(self):
        self.calls = []

    def __call__(self, url, headers, body, timeout):
        self.calls.append(body)
        return 200, {"messages": [{"id": "wamid.%d" % len(self.calls)}],
                     "contacts": [{"wa_id": body["to"]}]}

    def names(self):
        return [c["template"]["name"] for c in self.calls]


def build(tmp_path, clock, *, dry_run=False, email_limit=25, wa_limit=20):
    smtp, meta = SMTP(), Meta()
    et = ET.EmailTracker(tmp_path / "email", now=clock)
    es = EmailSender(smtp_host="smtp.test", smtp_user="u", smtp_password="p",
                     from_email="saleh@salehhaidar.com", smtp_client=smtp,
                     sleep=lambda s: None, tracker=et, now=clock,
                     dry_run=dry_run, daily_limit=email_limit)
    wt = WT.WhatsAppTracker(tmp_path / "wa", now=clock)
    ws = WhatsAppSender(phone_id="1", access_token="t", http_post=meta,
                        tracker=wt, now=clock, sleep=lambda s: None,
                        approved_templates={t["name"] for t in
                                            W.all_templates()},
                        day0_fallback=None, dry_run=dry_run,
                        daily_limit=wa_limit)
    u = UnifiedSequence(EmailSequence(es, et), WhatsAppSequence(ws, wt),
                        channel_router,
                        SequenceStore(tmp_path / "sched", now=clock))
    return u, smtp, meta


def test_start_sends_email_and_whatsapp(tmp_path):
    clock = Clock()
    u, smtp, meta = build(tmp_path, clock)
    out = u.start(P, language="en", confirmed=True)
    assert out["ok"] and out["route"]["channels"] == ["email", "whatsapp"]
    assert out["results"]["email"]["status"] == "sent"
    assert out["results"]["whatsapp"]["status"] == "sent"
    assert smtp.messages[0]["Subject"] == \
        "After-hours patient messages at Smile Dental Clinic"
    assert meta.names() == ["alpha_clinics_en_v1"]
    rec = u.store.find(P["email"])
    assert rec["steps"]["day0_email"]["status"] == "sent"
    assert rec["steps"]["day0_whatsapp"]["status"] == "sent"
    assert rec["status"] == "active" and rec["language"] == "en"
    assert u.store.find(P["phone_e164"])["key"] == P["email"]
    # never started twice
    again = u.start(P, language="en", confirmed=True)
    assert again["reason"] == "already_started"
    assert len(smtp.messages) == 1 and len(meta.calls) == 1
    # without confirmation: nothing sent, nothing stored
    dry = u.start(dict(P, email="b@b.ae", phone_e164="+971551112222"))
    assert {r["status"] for r in dry["results"].values()} == {"dry_run"}
    assert u.store.find("b@b.ae") is None and len(meta.calls) == 1


def test_start_respects_router_decision(tmp_path):
    clock = Clock()
    u, smtp, meta = build(tmp_path, clock)
    email_only = u.start({"email": "x@x.ae", "phone_e164": "+97142223333",
                          "company_name": "X", "sector": "lawyers",
                          "country": "AE"}, confirmed=True)
    assert email_only["route"]["reason"] == "email_only"
    assert list(email_only["results"]) == ["email"] and meta.calls == []
    assert set(u.store.find("x@x.ae")["steps"]) == {"day0_email",
                                                    "day3_email",
                                                    "day14_email"}
    skipped = u.start(dict(P, sector="unknown"), confirmed=True)
    assert skipped["skipped"] and skipped["results"] == {}
    assert skipped["reason"] == "blocked_sector"
    role = u.start({"email": "info@pearl.ae", "phone_e164": "+971559998888",
                    "company_name": "Pearl", "sector": "salons",
                    "country": "AE"}, confirmed=True)
    assert list(role["results"]) == ["whatsapp", "email"]    # WA first
    assert len(smtp.messages) == 2 and len(meta.calls) == 1


def test_process_due_finds_day2_whatsapp(tmp_path):
    clock = Clock()
    u, smtp, meta = build(tmp_path, clock)
    u.start(P, language="en", confirmed=True)
    clock.t = T0 + timedelta(days=1, hours=23)
    assert u.process_due(confirmed=True)["processed"] == 0
    clock.t = T0 + timedelta(days=2, minutes=1)
    s = u.process_due(confirmed=True)
    assert [i["step"] for i in s["items"]] == ["day2_whatsapp"]
    assert s["sent"] == 1 and meta.names()[-1] == "alpha_clinics_en_followup"
    assert len(smtp.messages) == 1                    # email waits for day 3
    assert u.store.find(P["email"])["steps"]["day2_whatsapp"]["status"] == \
        "sent"


def test_process_due_finds_day3_email(tmp_path):
    clock = Clock()
    u, smtp, meta = build(tmp_path, clock)
    u.start(P, language="en", confirmed=True)
    clock.t = T0 + timedelta(days=3, minutes=1)
    s = u.process_due(confirmed=True)
    assert sorted(i["step"] for i in s["items"]) == ["day2_whatsapp",
                                                     "day3_email"]
    assert smtp.messages[-1]["Subject"] == "A quick thought for Smile " \
        "Dental Clinic"
    clock.t = T0 + timedelta(days=7, minutes=1)
    assert [i["step"] for i in u.process_due(confirmed=True)["items"]] == [
        "day7_whatsapp"]
    assert meta.names()[-1] == "alpha_nudge_en_v1"
    clock.t = T0 + timedelta(days=14, minutes=1)
    assert [i["step"] for i in u.process_due(confirmed=True)["items"]] == [
        "day14_email"]
    assert smtp.messages[-1]["Subject"] == "Closing the loop"
    assert u.store.find(P["email"])["status"] == "completed"
    assert (len(smtp.messages), len(meta.calls)) == (3, 3)


def test_process_due_respects_daily_limits(tmp_path):
    clock = Clock()
    u, smtp, meta = build(tmp_path, clock, email_limit=1)
    second = dict(P, email="b@b.ae", phone_e164="+971551112222",
                  company_name="B Clinic")
    a = u.start(P, language="en", confirmed=True)
    b = u.start(second, language="en", confirmed=True)
    assert a["results"]["email"]["status"] == "sent"
    assert b["results"]["email"]["reason"] == "daily_limit_reached"
    assert b["results"]["whatsapp"]["status"] == "sent"   # independent
    rec = u.store.find("b@b.ae")
    assert rec["steps"]["day0_email"]["status"] == "pending"
    s = u.process_due(confirmed=True)                   # same day
    assert s["limit_hit"]["email"] and len(smtp.messages) == 1
    # the next day's run (a fresh process, as the scheduler starts one)
    clock.t = T0 + timedelta(days=1)
    u2, smtp2, meta2 = build(tmp_path, clock, email_limit=1)
    s = u2.process_due(confirmed=True)
    assert len(smtp2.messages) == 1 and s["sent"] == 1
    assert u2.store.find("b@b.ae")["steps"]["day0_email"]["status"] == "sent"
    assert not s["limit_hit"]["whatsapp"] and meta2.calls == []
    # a long-lived WhatsApp sender also starts the new day at zero
    assert u.wa_sender.remaining_today(real=True) == 20


def test_daily_report_shape(tmp_path):
    clock = Clock()
    u, smtp, meta = build(tmp_path, clock)
    u.start(P, language="ar", confirmed=True)
    u.wa_tracker.record_webhook({"entry": [{"changes": [{"value": {
        "statuses": [{"id": "wamid.1", "status": "delivered",
                      "recipient_id": "971501234567"}]}}]}]})
    rep = u.daily_report()
    assert set(rep["email"]) >= {"sent", "dry_run", "blocked", "failed",
                                 "opens", "clicks"}
    assert set(rep["whatsapp"]) >= {"sent", "delivered", "read", "failed",
                                    "replies"}
    assert set(rep["combined"]) >= {"replies", "unsubscribes", "bounces",
                                    "due_now", "due_tomorrow"}
    assert (rep["email"]["sent"], rep["whatsapp"]["sent"],
            rep["whatsapp"]["delivered"]) == (1, 1, 1)
    assert rep["date"] == "2026-10-07"
    clock.t = T0 + timedelta(days=1)
    assert u.daily_report()["combined"]["due_tomorrow"] == 1   # day 2 WA


def test_reply_stops_all_channels(tmp_path):
    clock = Clock()
    u, smtp, meta = build(tmp_path, clock)
    u.start(P, language="en", confirmed=True)
    r = u.wa_tracker.record_webhook({"entry": [{"changes": [{"value": {
        "messages": [{"from": "971501234567", "id": "in1", "type": "text",
                      "text": {"body": "Interested, call me"}}]}}]}]})
    assert r["replies"][0]["status"] == "replied"
    clock.t = T0 + timedelta(days=3, minutes=1)
    s = u.process_due(confirmed=True)
    assert s["stopped"] == 1 and s["processed"] == 0
    assert (len(smtp.messages), len(meta.calls)) == (1, 1)
    rec = u.store.find(P["email"])
    assert rec["status"] == "stopped" and \
        rec["stop_reason"] == "replied_whatsapp"
    assert ET.is_suppressed(P["email"], u.email_tracker.data_dir)
    assert all(st["status"] in ("sent", "skipped")
               for st in rec["steps"].values())
    clock.t = T0 + timedelta(days=15)
    assert u.process_due(confirmed=True)["processed"] == 0


def test_get_schedule_returns_full_timeline(tmp_path):
    clock = Clock()
    u, smtp, meta = build(tmp_path, clock)
    u.start(P, language="en", confirmed=True)
    tl = u.get_schedule(P["phone_e164"])
    assert [(x["day"], x["channel"]) for x in tl] == [
        ("day0", "email"), ("day0", "whatsapp"), ("day2", "whatsapp"),
        ("day3", "email"), ("day7", "whatsapp"), ("day14", "email")]
    assert [x["status"] for x in tl] == ["sent", "sent"] + ["pending"] * 4
    due = {x["day"]: x["due_at"] for x in tl}
    for day, n in (("day2", 2), ("day3", 3), ("day7", 7), ("day14", 14)):
        assert due[day] == ET.iso(T0 + timedelta(days=n)), day
    u.start({"email": "e@e.ae", "company_name": "E", "sector": "clinics",
             "country": "AE"}, confirmed=True)
    only = u.get_schedule("e@e.ae")
    assert [x["status"] for x in only if x["channel"] == "whatsapp"] == [
        "not_applicable"] * 3
    assert u.get_schedule("nobody@x.ae") == []
