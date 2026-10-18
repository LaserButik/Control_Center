# -*- coding: utf-8 -*-
"""ATLAS email engine: templates, sender, tracker, sequence. SMTP is a
fake client factory, storage lives in tmp_path, the clock is injected,
and sockets refuse — no email can leave the machine."""

import inspect
import json
import logging
import re
import smtplib
import socket
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from atlas_services import email_templates as T         # noqa: E402
from atlas_services import email_sender as ES           # noqa: E402
from atlas_services import email_tracker as ET          # noqa: E402
from atlas_services.email_sequence import EmailSequence  # noqa: E402

PASSWORD = "s3cret-PASS-9"
T0 = datetime(2026, 10, 7, 8, 0, tzinfo=timezone.utc)      # 12:00 Dubai
P = {"email": "info@smileclinic.ae", "company_name": "Smile Dental Clinic",
     "sector": "clinics"}


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("real network touched")
    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(socket, "create_connection", boom)
    monkeypatch.setattr(smtplib, "SMTP", boom)
    for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM",
              "SMTP_DISABLE_TLS", "SMTP_PORT"):
        monkeypatch.delenv(k, raising=False)


class Clock:
    def __init__(self, t=T0):
        self.t = t

    def __call__(self):
        return self.t


class FakeSMTP:
    """Factory and client in one: records every call."""
    def __init__(self, fail=None):
        self.calls, self.messages, self.fail = [], [], fail

    def __call__(self, host, port, timeout=None):
        self.calls.append(("connect", host, port))
        return self

    def starttls(self, **kw):
        self.calls.append(("starttls",))

    def login(self, user, password):
        self.calls.append(("login", user, password))
        if self.fail:
            raise self.fail

    def send_message(self, msg):
        self.calls.append(("send",))
        self.messages.append(msg)

    def quit(self):
        self.calls.append(("quit",))


def make(tmp_path, clock=None, smtp=None, **kw):
    clock = clock or Clock()
    tracker = ET.EmailTracker(tmp_path, now=clock)
    sender = ES.EmailSender(
        smtp_host="smtp.test", smtp_port=587, smtp_user="user@test",
        smtp_password=PASSWORD, from_email="saleh@salehhaidar.com",
        smtp_client=smtp if smtp is not None else FakeSMTP(),
        sleep=lambda s: None, tracker=tracker, now=clock, **kw)
    return sender, tracker


def rendered(tid="clinics_en_day0", prospect=P):
    return T.render(T.get_template_by_id(tid), prospect)


def sent_result(at):
    return {"ok": True, "status": "sent", "reason": None,
            "message_id": "<x@test>", "sent_at": ET.iso(at)}


# ── templates ──

def test_all_twenty_templates_exist():
    ids = T.list_all_template_ids()
    assert len(ids) == 20 and len(set(ids)) == 20
    assert T.count_by_sector() == {s: 4 for s in ("clinics", "real_estate",
                                                  "restaurants", "salons",
                                                  "lawyers")}
    for tid in ids:
        t = T.get_template_by_id(tid)
        assert t["subject"] and t["body"] and t["body_html"], tid
    assert T.get_template_by_id("nope") is None


def test_each_sector_has_ar_and_en():
    for sector in T.TEMPLATES:
        assert set(T.TEMPLATES[sector]) == {"ar", "en"}
        for lang in ("ar", "en"):
            assert len(T.get_templates(sector, lang)) == 2
    with pytest.raises(KeyError):
        T.get_templates("bakeries", "en")
    with pytest.raises(KeyError):
        T.get_templates("clinics", "fr")


def test_each_sector_has_day0_and_day3():
    for sector in T.TEMPLATES:
        for lang in ("ar", "en"):
            seq = T.get_sequence(sector, lang)
            assert [t["category"] for t in seq] == ["day0_initial",
                                                    "day3_followup"]
            assert [t["id"] for t in seq] == ["%s_%s_day0" % (sector, lang),
                                              "%s_%s_day3" % (sector, lang)]


def test_no_fabricated_stats():
    stats = re.compile(r"\d+(\.\d+)?\s*[%٪]|[%٪]\s*\d+|\b\d+\s*x\b|"
                       r"\bguarantee|\bproven\b|مضمون|نضمن|بضمان", re.I)
    generic = re.compile(r"dear sir|madam|to whom it may concern|"
                         r"عزيزي العميل|السيد/ة", re.I)
    for tid in T.list_all_template_ids():
        t = T.get_template_by_id(tid)
        text = t["subject"] + "\n" + t["body"]
        assert not stats.search(text), (tid, stats.search(text).group())
        assert not generic.search(text), tid
        body = T.render(t, P)["body"]
        assert T.word_count(body) <= 120, (tid, T.word_count(body))


def test_unsubscribe_line_present():
    for tid in T.list_all_template_ids():
        t = T.get_template_by_id(tid)
        assert "{unsubscribe_line}" in t["body"]
        r = T.render(t, P)
        assert "Reply STOP to unsubscribe." in r["body"], tid
        assert "Reply STOP to unsubscribe." in r["body_html"], tid
        assert r["unsubscribe_line"] in r["body"]


def test_physical_address_present_in_body():
    addr = "AI Mentors Agency, Business Bay, Dubai, UAE"
    for tid in T.list_all_template_ids():
        t = T.get_template_by_id(tid)
        r = T.render(t, P)
        assert r["body"].rstrip().endswith(addr), tid
        assert addr in r["body_html"], tid
        page = r["body_html"]
        # inline CSS only, nothing loaded from outside
        assert not re.search(r"<link|<script|<img|src=|url\(|@import|"
                             r"<style", page, re.I), tid
        for colour in ("#667eea", "#764ba2", "#2d3748"):
            assert colour in page, (tid, colour)
        want = 'dir="rtl"' if t["language"] == "ar" else 'dir="ltr"'
        assert want in page and ('dir="rtl"' if want.endswith('ltr"')
                                 else 'dir="ltr"') not in page, tid


def test_render_fills_all_placeholders():
    for tid in T.list_all_template_ids():
        t = T.get_template_by_id(tid)
        for prospect in (dict(P, contact_name="Dr. Sara"), P, {}, None,
                         {"company_name": "  "}):
            r = T.render(t, prospect)
            for k in ("subject", "body", "body_html"):
                assert "{" not in r[k] and "}" not in r[k], (tid, k)
    en = T.render(T.get_template_by_id("clinics_en_day0"),
                  dict(P, contact_name="Dr. Sara"))
    assert en["body"].startswith("Hi Dr. Sara,")
    assert T.render(T.get_template_by_id("clinics_en_day0"), P)[
        "body"].startswith("Hi Smile Dental Clinic team,")
    assert T.render(T.get_template_by_id("clinics_ar_day0"), P)[
        "body"].startswith("مرحباً فريق Smile Dental Clinic،")
    signed = T.render(T.get_template_by_id("lawyers_en_day3"), P)["body"]
    assert "Saleh\nFounder, AI Mentors Agency" in signed
    # values are escaped in HTML, plain in text
    odd = T.render(T.get_template_by_id("salons_en_day3"),
                   {"company_name": "<b>A&B</b>"})
    assert "<b>A&B</b>" in odd["subject"]
    assert "&lt;b&gt;A&amp;B&lt;/b&gt;" in odd["body_html"]
    assert "<b>A&B</b>" not in odd["body_html"]


# ── sender ──

def test_dry_run_never_calls_smtp(tmp_path):
    smtp = FakeSMTP()
    sender, _ = make(tmp_path, smtp=smtp)                # dry_run default
    assert sender.dry_run is True
    r = sender.send(P, rendered(), template_id="clinics_en_day0",
                    confirmed=True)
    assert (r["ok"], r["status"], r["reason"]) == (True, "dry_run",
                                                    "dry_run")
    assert r["message_id"] is None and r["sent_at"] is None
    assert smtp.calls == []


def test_confirmed_false_never_calls_smtp(tmp_path):
    smtp = FakeSMTP()
    sender, _ = make(tmp_path, smtp=smtp, dry_run=False)
    r = sender.send(P, rendered(), template_id="clinics_en_day0")
    assert (r["status"], r["reason"]) == ("dry_run", "not_confirmed")
    assert smtp.calls == []
    sig = inspect.signature(ES.EmailSender.send)
    assert sig.parameters["confirmed"].default is False
    assert inspect.signature(ES.EmailSender).parameters[
        "dry_run"].default is True


def test_both_flags_required_to_send(tmp_path, monkeypatch):
    smtp = FakeSMTP()
    sender, _ = make(tmp_path, smtp=smtp, dry_run=False)
    msg = rendered()
    r = sender.send(P, msg, template_id="clinics_en_day0", confirmed=True)
    assert (r["ok"], r["status"]) == (True, "sent")
    assert r["message_id"] and r["sent_at"] == ET.iso(T0)
    assert [c[0] for c in smtp.calls] == ["connect", "starttls", "login",
                                          "send", "quit"]
    assert smtp.calls[0] == ("connect", "smtp.test", 587)
    m = smtp.messages[0]
    assert m["To"] == P["email"] and m["Subject"] == msg["subject"]
    assert m["Reply-To"] == "info@salehhaidar.com"
    assert "Saleh from AI Mentors" in m["From"]
    assert m["List-Unsubscribe"]
    # SMTP_DISABLE_TLS=true skips STARTTLS; config comes from env
    monkeypatch.setenv("SMTP_DISABLE_TLS", "true")
    monkeypatch.setenv("SMTP_HOST", "smtp-relay.example")
    smtp2 = FakeSMTP()
    s2 = ES.EmailSender(smtp_user="u", smtp_password="p",
                        from_email="a@b.ae", smtp_client=smtp2,
                        tracker=ET.EmailTracker(tmp_path / "b",
                                                now=Clock()),
                        now=Clock(), dry_run=False)
    assert s2.smtp_host == "smtp-relay.example" and s2.smtp_port == 587
    s2.send(P, msg, template_id="clinics_en_day0", confirmed=True)
    assert "starttls" not in [c[0] for c in smtp2.calls]
    # not configured: a real send fails before any connection
    smtp3 = FakeSMTP()
    s3 = ES.EmailSender(smtp_client=smtp3, dry_run=False, now=Clock(),
                        tracker=ET.EmailTracker(tmp_path / "c",
                                                now=Clock()))
    r3 = s3.send(P, msg, template_id="clinics_en_day0", confirmed=True)
    assert r3["reason"] == "smtp_not_configured" and smtp3.calls == []


def test_daily_limit_enforced(tmp_path):
    smtp = FakeSMTP()
    sender, tracker = make(tmp_path, smtp=smtp, dry_run=False,
                           daily_limit=999)
    assert sender.daily_limit == 25                     # hard cap
    for i in range(25):
        tracker.record_sent({"email": "c%d@clinic%d.ae" % (i, i),
                             "sector": "clinics"}, "clinics_en_day0",
                            sent_result(T0 - timedelta(minutes=i)))
    assert ES.get_daily_sent_count(tmp_path, T0) == 25
    assert sender.remaining_today() == 0
    r = sender.send(P, rendered(), template_id="clinics_en_day0",
                    confirmed=True)
    assert (r["status"], r["reason"]) == ("blocked", "daily_limit_reached")
    assert smtp.calls == []
    # dry runs count inside one batch, so a preview shows the cut-off
    s2, _ = make(tmp_path / "dry", daily_limit=3)
    out = [s2.send({"email": "x%d@a%d.ae" % (i, i)}, rendered(),
                   template_id="clinics_en_day0")["status"]
           for i in range(4)]
    assert out == ["dry_run"] * 3 + ["blocked"]
    # yesterday's sends do not count today (Dubai calendar day)
    assert ES.get_daily_sent_count(tmp_path, T0 + timedelta(days=1)) == 0


def test_suppressed_email_blocked(tmp_path):
    smtp = FakeSMTP()
    sender, _ = make(tmp_path, smtp=smtp, dry_run=False)
    added = ES.add_to_suppression("INFO@SmileClinic.ae", "asked",
                                  data_dir=tmp_path)
    assert added["ok"] and added["email"] == P["email"]
    assert ES.is_suppressed(P["email"], tmp_path)
    assert ES.load_suppression(tmp_path) == {P["email"]}
    r = sender.send(dict(P, email="Info@SmileClinic.AE"), rendered(),
                    template_id="clinics_en_day0", confirmed=True)
    assert (r["status"], r["reason"]) == ("blocked", "suppressed")
    for bad in ("", None, "not-an-email"):
        assert sender.send({"email": bad}, rendered(),
                           template_id="clinics_en_day0",
                           confirmed=True)["reason"] == "invalid_email"
    assert smtp.calls == []


def test_replied_email_not_re_sent(tmp_path):
    clock = Clock()
    smtp = FakeSMTP()
    sender, tracker = make(tmp_path, clock, smtp, dry_run=False)
    tracker.record_replied(P["email"], "Thanks, call me tomorrow")
    r = sender.send(P, rendered(), template_id="clinics_en_day3",
                    confirmed=True)
    assert r["status"] == "blocked" and r["reason"] in ("suppressed",
                                                        "status_replied")
    # a status on the prospect record blocks too
    r = sender.send({"email": "a@b.ae", "status": "replied"}, rendered(),
                    template_id="clinics_en_day0", confirmed=True)
    assert r["reason"] == "status_replied"
    # the same address is not emailed twice within 20 hours
    tracker.record_sent({"email": "c@d.ae", "sector": "clinics"},
                        "clinics_en_day0",
                        sent_result(T0 - timedelta(hours=2)))
    r = sender.send({"email": "c@d.ae"}, rendered(),
                    template_id="clinics_en_day3", confirmed=True)
    assert r["reason"] == "sent_within_20h"
    assert smtp.calls == []
    clock.t = T0 + timedelta(hours=19)               # 21 h after
    r = sender.send({"email": "c@d.ae"}, rendered(),
                    template_id="clinics_en_day3", confirmed=True)
    assert r["status"] == "sent"


def test_password_never_logged(tmp_path, caplog, capsys):
    caplog.set_level(logging.DEBUG)
    smtp = FakeSMTP()
    sender, tracker = make(tmp_path, smtp=smtp, dry_run=False)
    ok = sender.send(P, rendered(), template_id="clinics_en_day0",
                     confirmed=True)
    tracker.record_sent(P, "clinics_en_day0", ok)
    bad_smtp = FakeSMTP(fail=smtplib.SMTPAuthenticationError(
        535, ("auth failed for %s" % PASSWORD).encode()))
    s2, t2 = make(tmp_path / "b", smtp=bad_smtp, dry_run=False)
    fail = s2.send(P, rendered(), template_id="clinics_en_day0",
                   confirmed=True)
    t2.record_sent(P, "clinics_en_day0", fail)
    assert fail["status"] == "failed" and "***" in fail["reason"]
    out = capsys.readouterr()
    seen = [caplog.text, out.out, out.err, repr(sender), repr(s2),
            json.dumps(sender.config_summary()), json.dumps(ok),
            json.dumps(fail), str(vars(sender).get("smtp_password", ""))]
    for path in list(tmp_path.rglob("*")):
        if path.is_file():
            seen.append(path.read_bytes().decode("utf-8", "replace"))
    for text in seen:
        assert PASSWORD not in text
    assert sender.config_summary()["password_set"] is True
    assert "password" not in vars(sender)
    assert ("login", "user@test", PASSWORD) in smtp.calls   # used, not shown


# ── tracker ──

def test_record_sent_creates_state(tmp_path):
    tracker = ET.EmailTracker(tmp_path, now=Clock())
    entry = tracker.record_sent(dict(P, contact_name="Sara"),
                                "clinics_ar_day0", sent_result(T0))
    st = tracker.get_prospect_state(P["email"])
    assert (st["last_sent_day"], st["next_due_day"], st["status"]) == (
        "day0", "day3", "active")
    assert (st["sector"], st["language"], st["company_name"]) == (
        "clinics", "ar", "Smile Dental Clinic")
    assert st["last_sent_at"] == ET.iso(T0)
    assert st["next_due_at"] == ET.iso(T0 + timedelta(days=3))
    assert entry["status"] == "sent"
    assert (tmp_path / "prospect_state.json").exists()
    assert len(ET.read_sent_log(tmp_path)) == 1
    # a dry run is logged but does not move the sequence
    tracker.record_sent({"email": "dry@a.ae", "sector": "clinics"},
                        "clinics_en_day0",
                        {"ok": True, "status": "dry_run", "reason": "dry_run"})
    assert tracker.get_prospect_state("dry@a.ae")["last_sent_day"] is None
    assert [r["status"] for r in ET.read_sent_log(tmp_path)] == [
        "sent", "dry_run"]
    # opens and clicks only count
    tracker.record_opened(P["email"])
    tracker.record_clicked(P["email"], "https://x")
    st2 = tracker.get_prospect_state(P["email"])
    assert (st2["opens"], st2["clicks"]) == (1, 1)
    assert (st2["status"], st2["next_due_day"]) == ("active", "day3")
    # day3 completes the sequence
    tracker.record_sent(P, "clinics_ar_day3",
                        sent_result(T0 + timedelta(days=3)))
    assert tracker.get_prospect_state(P["email"])["next_due_day"] == \
        "completed"


def test_reply_sets_status_and_suppresses(tmp_path):
    clock = Clock()
    tracker = ET.EmailTracker(tmp_path, now=clock)
    tracker.record_sent(P, "clinics_en_day0", sent_result(T0))
    st = tracker.record_replied(P["email"], "Interested, please call")
    assert (st["status"], st["next_due_day"], st["replies"]) == (
        "replied", None, 1)
    assert ET.is_suppressed(P["email"], tmp_path)
    assert ET.suppression_entries(tmp_path)[P["email"]]["reason"] == \
        "replied"
    assert tracker.get_due_followups(T0 + timedelta(days=4)) == []
    # "STOP" is an unsubscribe; a bounce is suppressed too
    st = tracker.record_replied("b@b.ae", "STOP")
    assert st["status"] == "unsubscribed" and ET.is_suppressed("b@b.ae",
                                                               tmp_path)
    st = tracker.record_bounced("c@c.ae", "mailbox full")
    assert st["status"] == "bounced" and ET.is_suppressed("c@c.ae", tmp_path)
    st = tracker.record_unsubscribed("d@d.ae")
    assert (st["status"], st["next_due_day"]) == ("unsubscribed", None)
    assert ET.load_suppression(tmp_path) == {P["email"], "b@b.ae", "c@c.ae",
                                             "d@d.ae"}


# ── sequence ──

def test_start_sends_day0_and_marks_state(tmp_path):
    smtp = FakeSMTP()
    sender, tracker = make(tmp_path, smtp=smtp, dry_run=False)
    seq = EmailSequence(sender, tracker)
    out = seq.start(P, language="en", confirmed=True)
    assert out["result"]["status"] == "sent"
    assert out["template_id"] == "clinics_en_day0"
    assert smtp.messages[0]["Subject"] == out["subject"] == \
        rendered()["subject"]
    st = tracker.get_prospect_state(P["email"])
    assert (st["last_sent_day"], st["next_due_day"]) == ("day0", "day3")
    # never started twice
    again = seq.start(P, language="en", confirmed=True)
    assert again["result"]["reason"] == "already_started"
    assert len(smtp.messages) == 1
    # without confirmation: a dry run that leaves the state alone
    dry = seq.start({"email": "x@y.ae", "company_name": "Y",
                     "sector": "salons"}, language="ar")
    assert dry["result"]["status"] == "dry_run"
    assert dry["template_id"] == "salons_ar_day0"
    assert tracker.get_prospect_state("x@y.ae")["last_sent_day"] is None
    # an unknown sector is blocked and logged
    bad = seq.start({"email": "z@z.ae", "sector": "unknown"},
                    confirmed=True)
    assert bad["result"]["reason"] == "unknown_sector"
    assert len(smtp.messages) == 1
    rep = seq.daily_report()
    assert (rep["sent"], rep["dry_run"], rep["blocked"]) == (1, 1, 2)
    assert rep["remaining"] == 24


def test_process_due_followups_only_after_3_days(tmp_path):
    clock = Clock()
    smtp = FakeSMTP()
    sender, tracker = make(tmp_path, clock, smtp, dry_run=False)
    seq = EmailSequence(sender, tracker)
    seq.start(P, language="en", confirmed=True)
    clock.t = T0 + timedelta(days=2)
    assert seq.daily_report()["due_tomorrow"] == 1
    clock.t = T0 + timedelta(days=2, hours=23)
    early = seq.process_due_followups(confirmed=True)
    assert early["due"] == 0 and len(smtp.messages) == 1
    clock.t = T0 + timedelta(days=3, minutes=1)
    # a dry run first: shows the email, sends nothing, keeps it due
    dry = seq.process_due_followups()
    assert (dry["due"], dry["dry_run"]) == (1, 1) and len(smtp.messages) == 1
    assert dry["items"][0]["template_id"] == "clinics_en_day3"
    done = seq.process_due_followups(confirmed=True)
    assert (done["due"], done["sent"]) == (1, 1)
    assert smtp.messages[1]["Subject"] == T.render(
        T.get_template_by_id("clinics_en_day3"), P)["subject"]
    st = tracker.get_prospect_state(P["email"])
    assert (st["last_sent_day"], st["next_due_day"]) == ("day3",
                                                         "completed")
    assert seq.process_due_followups(confirmed=True)["due"] == 0
    # a reply before day 3 stops the follow-up
    other = {"email": "r@r.ae", "company_name": "R", "sector": "lawyers"}
    clock.t = T0
    seq.start(other, language="ar", confirmed=True)
    tracker.record_replied("r@r.ae", "yes please")
    clock.t = T0 + timedelta(days=5)
    assert seq.process_due_followups(confirmed=True)["due"] == 0
