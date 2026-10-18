# -*- coding: utf-8 -*-
"""The daily run, end to end on fakes: finder, enricher, SMTP, Meta,
Telegram and IMAP are all replaced; data lives in tmp_path."""

import json
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
from scheduler import run_daily as RD                     # noqa: E402

T0 = datetime(2026, 10, 7, 5, 0, tzinfo=timezone.utc)      # Wed 09:00 Dubai
SUNDAY = datetime(2026, 10, 11, 5, 0, tzinfo=timezone.utc)
FOUND = [
    {"company_name": "Smile Dental Clinic", "email": "sara@smileclinic.ae",
     "phone_e164": "+971501234567", "website": "https://smileclinic.ae",
     "sector": "clinics", "country": "AE"},
    {"company_name": "Oasis Realty", "email": None, "phone_e164": None,
     "website": "https://oasisrealty.ae", "sector": "real_estate",
     "country": "AE"},
    {"company_name": "Mystery Co", "email": "a@mystery.ae",
     "sector": "unknown", "country": "AE"},
]


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("real network touched")
    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(socket, "create_connection", boom)


class Clock:
    def __init__(self, t=T0):
        self.t = t

    def __call__(self):
        return self.t


class SMTP:
    def __init__(self):
        self.messages = []

    def __call__(self, host, port, timeout=None):
        return self

    def starttls(self, **kw):
        pass

    def login(self, u, p):
        pass

    def send_message(self, m):
        self.messages.append(m)

    def quit(self):
        pass


class Meta:
    def __init__(self):
        self.calls = []

    def __call__(self, url, headers, body, timeout):
        self.calls.append(body)
        return 200, {"messages": [{"id": "wamid.%d" % len(self.calls)}]}


class Telegram:
    def __init__(self):
        self.daily, self.weekly, self.alerts, self.polls = [], [], [], 0

    def send_daily_report(self, rep):
        self.daily.append(rep)
        return {"ok": True}

    def send_weekly_report(self, week):
        self.weekly.append(week)
        return {"ok": True}

    def send_alert(self, kind, details):
        self.alerts.append((kind, details))
        return {"ok": True}

    def poll_commands(self, **kw):
        self.polls += 1
        return {"ok": True, "handled": []}


class World:
    """Everything a run touches, faked."""
    def __init__(self, tmp_path, clock=None, finder_error=None):
        self.tmp, self.clock = tmp_path, clock or Clock()
        self.smtp, self.meta, self.tg = SMTP(), Meta(), Telegram()
        self.finder_calls, self.finder_error = 0, finder_error
        self.enriched = []

    def find(self, **kw):
        self.finder_calls += 1
        if self.finder_error:
            raise self.finder_error
        return {"ok": True, "total_found": 3, "new": 3, "duplicates": 0,
                "companies": [dict(c) for c in FOUND],
                "serper_calls": 25, "out_path": "x"}

    def enrich(self, companies, max_companies=100):
        self.enriched += companies
        res = [dict(c, email="info@oasisrealty.ae",
                    phones_all=["+97142223333", "+971551112222"])
               if "oasis" in (c.get("website") or "") else dict(c)
               for c in companies]
        return {"processed": len(res), "results": res, "network_calls": 3}

    def build(self, *, dry_run, paths, now):
        et = ET.EmailTracker(paths.email, now=now)
        wt = WT.WhatsAppTracker(paths.whatsapp, now=now)
        es = EmailSender(smtp_host="h", smtp_user="u", smtp_password="p",
                         from_email="saleh@salehhaidar.com",
                         smtp_client=self.smtp, sleep=lambda s: None,
                         tracker=et, now=now, dry_run=dry_run)
        ws = WhatsAppSender(phone_id="1", access_token="t",
                            http_post=self.meta, tracker=wt, now=now,
                            sleep=lambda s: None, dry_run=dry_run,
                            approved_templates={t["name"] for t in
                                                W.all_templates()},
                            day0_fallback=None)
        return UnifiedSequence(EmailSequence(es, et),
                               WhatsAppSequence(ws, wt), channel_router,
                               SequenceStore(paths.scheduler, now=now))

    def deps(self):
        return RD.Deps(find_auto=self.find, enrich=self.enrich,
                       build_unified=self.build, telegram=self.tg,
                       poll_imap=lambda *a, **k: {
                           "skipped": "imap_not_configured", "replies": [],
                           "bounces": []},
                       now=self.clock, load_env=lambda: False,
                       data_root=self.tmp)

    def run(self, **kw):
        return RD.run_daily(deps=self.deps(), language="en", **kw)


def test_run_daily_dry_run_does_not_send(tmp_path):
    w = World(tmp_path)
    (tmp_path / "prospects").mkdir()
    (tmp_path / "prospects" / "daily_20261006.json").write_bytes(
        json.dumps({"companies": FOUND}).encode("utf-8"))
    r = w.run(dry_run=True)
    assert r["result"] == "ok" and r["mode"] == "dry_run"
    assert w.finder_calls == 0 and w.enriched == []      # no Serper, no web
    assert w.smtp.messages == [] and w.meta.calls == []
    assert w.tg.daily == [] and w.tg.alerts == [] and w.tg.polls == 0
    start = next(s for s in r["steps"] if s["step"] == 4)["summary"]
    assert start["email_dry_run"] == 1 and start["whatsapp_dry_run"] == 1
    assert (tmp_path / "reports" / "daily_20261007_dryrun.json").exists()
    assert not (tmp_path / "scheduler" / "sequence_state.json").exists()
    assert not (tmp_path / "scheduler" / "run.lock").exists()


def test_run_daily_respects_paused_flag(tmp_path):
    w = World(tmp_path)
    (tmp_path / "scheduler").mkdir()
    (tmp_path / "scheduler" / "paused.flag").write_bytes(b"paused")
    r = w.run()
    assert r["result"] == "paused" and r["steps"] == []
    assert w.finder_calls == 0 and w.smtp.messages == [] and \
        w.meta.calls == []
    assert w.tg.polls == 1                        # RESUME can still arrive
    assert RD.read_run_log(RD.Paths(tmp_path))[-1]["result"] == "paused"


def test_run_daily_writes_log(tmp_path):
    w = World(tmp_path)
    r = w.run()
    assert r["result"] == "ok", [s for s in r["steps"]
                                 if s["status"] == "failed"]
    rec = RD.read_run_log(RD.Paths(tmp_path))
    assert len(rec) == 1 and rec[0]["run_id"] == r["run_id"]
    assert [s["step"] for s in rec[0]["steps"]] == [6, 1, 2, 3, 4, 5, 7, 8]
    assert rec[0]["date"] == "2026-10-07" and rec[0]["mode"] == "real"
    assert rec[0]["duration_ms"] >= 0 and rec[0]["log"]
    assert (tmp_path / "scheduler" / "last_run.log").exists()
    assert (tmp_path / "scheduler" / "routes_20261007.json").exists()
    assert not (tmp_path / "scheduler" / "run.lock").exists()
    # enrichment gave Oasis an email and a mobile; the unknown sector
    # was routed out
    assert [c["company_name"] for c in w.enriched] == ["Oasis Realty"]
    route = next(s for s in r["steps"] if s["step"] == 3)["summary"]
    assert (route["routed"], route["unknown"]) == (2, 1)
    assert len(w.smtp.messages) == 2 and len(w.meta.calls) == 2


def test_run_daily_handles_finder_failure(tmp_path):
    w = World(tmp_path, finder_error=RuntimeError("serper down"))
    r = w.run()
    assert r["result"] == "partial"
    find = next(s for s in r["steps"] if s["step"] == 1)
    assert find["status"] == "failed"
    assert "serper down" in find["error"] and "Traceback" in \
        find["traceback"]
    assert ("run_failed", {"step": "1 find new prospects",
                           "error": "RuntimeError: serper down",
                           "run_id": r["run_id"]}) in w.tg.alerts
    later = {s["step"]: s["status"] for s in r["steps"]}
    assert later[5] == "ok" and later[7] == "ok"          # the run went on
    assert len(w.tg.daily) == 1
    assert RD.read_run_log(RD.Paths(tmp_path))[-1]["result"] == "partial"


def test_run_daily_sends_telegram_report(tmp_path):
    w = World(tmp_path)
    w.run()
    assert len(w.tg.daily) == 1
    rep = w.tg.daily[0]
    assert rep["prospects"] == {"found": 3, "new": 3, "skipped": 1}
    assert rep["email"]["sent"] == 2 and rep["whatsapp"]["sent"] == 2
    assert rep["mode"] == "real" and w.tg.weekly == []      # Wednesday
    saved = json.loads((tmp_path / "reports" / "daily_20261007.json")
                       .read_bytes())
    assert saved["email"]["sent"] == 2
    # Sunday: the weekly report goes too
    w2 = World(tmp_path / "sun", Clock(SUNDAY))
    w2.run()
    assert len(w2.tg.weekly) == 1 and len(w2.tg.weekly[0]) == 1
    assert (tmp_path / "sun" / "reports" / "weekly_20261011.json").exists()


def test_run_daily_skips_when_already_ran_today(tmp_path):
    w = World(tmp_path)
    assert w.run()["result"] == "ok"
    r = w.run()
    assert r["result"] == "skipped_already_ran" and w.finder_calls == 1
    assert len(w.smtp.messages) == 2                  # nothing new sent
    assert w.run(dry_run=True)["result"] == "ok"      # dry runs still work
    assert w.run(force=True)["result"] == "ok" and w.finder_calls == 2
    w.clock.t = T0 + timedelta(days=1)                # tomorrow: runs
    assert w.run()["result"] == "ok"
