# -*- coding: utf-8 -*-
"""ATLAS Telegram reporter: format, alerts, commands. The Bot API is a
fake; no request leaves the machine."""

import json
import logging
import socket
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from atlas_services import telegram_reporter as TG      # noqa: E402

TOKEN = "123456:AA-secret-bot-token"
CHAT = "987654"
REPORT = {"date": "2026-10-08",
          "prospects": {"found": 45, "new": 32, "skipped": 13},
          "email": {"sent": 25, "limit": 25, "opens": 14},
          "whatsapp": {"sent": 18, "limit": 20},
          "combined": {"followups_sent": 12, "replies": 3, "bounces": 1,
                       "unsubscribes": 0, "due_tomorrow": 22,
                       "queue_remaining": 8}}
EXPECTED = """AI MENTORS — Daily Report
Date: 2026-10-08

PROSPECTS
Found today     : 45
New in system   : 32
Skipped         : 13

SENDING
Email sent      : 25 (limit 25)
WhatsApp sent   : 18 (limit 20)
Follow-ups sent : 12

ENGAGEMENT
Opens           : 14
Replies         : 3
Bounces         : 1
Unsubscribes    : 0

TOMORROW
Due follow-ups  : 22
Queue remaining : 8

Reply "STATUS" to see today's progress anytime."""


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("real network touched")
    monkeypatch.setattr(socket, "socket", boom)
    monkeypatch.setattr(socket, "create_connection", boom)
    if TG.requests is not None:
        monkeypatch.setattr(TG.requests, "post", boom)
        monkeypatch.setattr(TG.requests, "get", boom)
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TELEGRAM_CHAT_ID", raising=False)


class Bot:
    def __init__(self, status=200, data=None, error=None, updates=None):
        self.sent, self.status, self.error = [], status, error
        self.data = data if data is not None else {
            "ok": True, "result": {"message_id": 77}}
        self.updates = updates or []
        self.urls = []

    def post(self, url, body, timeout):
        self.urls.append(url)
        if self.error:
            raise self.error
        self.sent.append(body)
        return self.status, self.data

    def get(self, url, params, timeout):
        self.urls.append(url)
        return 200, {"ok": True, "result": self.updates}


def test_send_message_requires_token(monkeypatch):
    bot = Bot()
    assert TG.send_message("hi", http_post=bot.post) == {
        "ok": False, "reason": "telegram_not_configured"}
    assert TG.send_message("hi", token=TOKEN, http_post=bot.post)[
        "reason"] == "telegram_not_configured"            # no chat id
    assert bot.sent == [] and not TG.is_configured()
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", TOKEN)
    monkeypatch.setenv("TELEGRAM_CHAT_ID", CHAT)
    r = TG.send_message("hi", http_post=bot.post)
    assert r == {"ok": True, "message_id": 77}
    assert bot.sent == [{"chat_id": CHAT, "text": "hi",
                         "disable_web_page_preview": True}]
    assert bot.urls[0].endswith("/sendMessage")


def test_send_daily_report_formats_correctly():
    assert TG.format_daily_report(REPORT) == EXPECTED
    bot = Bot()
    r = TG.send_daily_report(REPORT, token=TOKEN, chat_id=CHAT,
                             http_post=bot.post)
    assert r["ok"] and bot.sent[0]["text"] == EXPECTED
    assert "parse_mode" not in bot.sent[0]                # plain text
    dry = TG.format_daily_report(dict(REPORT, mode="dry_run"))
    assert "(DRY RUN — nothing was sent)" in dry
    empty = TG.format_daily_report({})
    assert "Email sent      : 0 (limit 25)" in empty      # never crashes
    week = TG.format_weekly_report([REPORT, dict(REPORT, date="2026-10-09")])
    assert "Days: 2 (2026-10-08 to 2026-10-09)" in week
    assert "Reply rate      : 7.0%" in week               # 6 / 86


def test_send_alert_on_failure():
    bot = Bot()
    r = TG.send_alert("run_failed", {"step": "1 find new prospects",
                                     "error": "RuntimeError: boom"},
                      token=TOKEN, chat_id=CHAT, http_post=bot.post)
    assert r["ok"]
    assert bot.sent[0]["text"] == ("AI MENTORS — ALERT: RUN FAILED\n"
                                   "step: 1 find new prospects\n"
                                   "error: RuntimeError: boom")
    for kind in ("reply_received", "bounce_spike", "daily_limit_hit"):
        assert TG.send_alert(kind, {"x": 1}, token=TOKEN, chat_id=CHAT,
                             http_post=bot.post)["ok"]
    assert TG.send_alert("nonsense", {}, token=TOKEN, chat_id=CHAT,
                         http_post=bot.post) == {
        "ok": False, "reason": "unknown_alert_kind"}
    # Telegram errors come back as results, never as exceptions
    down = Bot(status=502, data={"ok": False, "description": "Bad Gateway"})
    r = TG.send_alert("run_failed", {}, token=TOKEN, chat_id=CHAT,
                      http_post=down.post)
    assert r == {"ok": False, "reason": "http_502: Bad Gateway"}
    r = TG.send_alert("run_failed", {}, token=TOKEN, chat_id=CHAT,
                      http_post=Bot(error=OSError("no route")).post)
    assert r["ok"] is False and "OSError" in r["reason"]


def test_status_command_returns_daily_numbers(tmp_path):
    flag = tmp_path / "paused.flag"
    text = TG.handle_command("STATUS", status_fn=lambda: REPORT,
                             flag_path=flag)
    assert text.startswith("AI MENTORS — Status")
    assert "Email sent      : 25 (limit 25)" in text
    assert "WhatsApp sent   : 18 (limit 20)" in text
    assert TG.handle_command("/status@aimentors_bot",
                             status_fn=lambda: REPORT) == text
    assert "Paused" in TG.handle_command("pause", flag_path=flag)
    assert flag.exists() and TG.is_paused(flag)
    assert "Resumed" in TG.handle_command("RESUME", flag_path=flag)
    assert not flag.exists()
    assert TG.handle_command("hello there") is None
    # polling: only the configured chat is answered; the offset is kept
    bot = Bot(updates=[
        {"update_id": 10, "message": {"chat": {"id": int(CHAT)},
                                      "text": "STATUS"}},
        {"update_id": 11, "message": {"chat": {"id": 555},
                                      "text": "PAUSE"}}])
    off = tmp_path / "offset.json"
    r = TG.poll_commands(token=TOKEN, chat_id=CHAT, http_get=bot.get,
                         http_post=bot.post, offset_path=off,
                         status_fn=lambda: REPORT, flag_path=flag)
    assert r["ok"] and r["ignored"] == 1 and len(r["handled"]) == 1
    assert bot.sent[0]["text"] == text and not flag.exists()
    assert json.loads(off.read_bytes()) == {"offset": 12}


def test_never_logs_bot_token(tmp_path, caplog, capsys):
    caplog.set_level(logging.DEBUG)
    results = [
        TG.send_message("x", token=TOKEN, chat_id=CHAT, http_post=Bot(
            error=RuntimeError("HTTPSConnectionPool: /bot%s/sendMessage"
                               % TOKEN)).post),
        TG.send_message("x", token=TOKEN, chat_id=CHAT, http_post=Bot(
            status=401, data={"ok": False, "description":
                              "Unauthorized for %s" % TOKEN}).post),
        TG.send_message("x", token=TOKEN, chat_id=CHAT,
                        http_post=Bot().post),
        TG.poll_commands(token=TOKEN, chat_id=CHAT,
                         offset_path=tmp_path / "o.json",
                         http_get=lambda *a: (_ for _ in ()).throw(
                             OSError("GET /bot%s/getUpdates" % TOKEN)))]
    assert results[0]["ok"] is False and "***" in results[0]["reason"]
    assert results[1]["ok"] is False and "***" in results[1]["reason"]
    out = capsys.readouterr()
    for text in (caplog.text, out.out, out.err, json.dumps(results)):
        assert TOKEN not in text
