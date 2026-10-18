# -*- coding: utf-8 -*-
"""ATLAS Telegram reporter: daily and weekly reports, alerts, and three
commands, through the Telegram Bot API (plain text, no Markdown, so a
company name can never break the message).

Environment: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID. The token is part of
every API URL, so it is scrubbed from every error and never logged.

Commands (send them to the bot from the configured chat; any other chat
is ignored):
  STATUS   today's numbers
  PAUSE    creates data/scheduler/paused.flag — the daily run skips
  RESUME   removes it
  HELP     the list
Commands are read when something polls the bot: the daily run polls once
at start, and `python -m atlas_services.telegram_reporter --listen`
keeps polling while it runs.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

try:
    import requests
except ImportError:                                  # pragma: no cover
    requests = None

ROOT = Path(__file__).resolve().parent.parent
SCHED_DIR = ROOT / "data" / "scheduler"
PAUSE_FLAG = SCHED_DIR / "paused.flag"
OFFSET_FILE = SCHED_DIR / "telegram_offset.json"
API = "https://api.telegram.org/bot%s/%s"
MAX_LEN = 4000
ALERT_KINDS = {"run_failed": "RUN FAILED",
               "reply_received": "NEW REPLY",
               "bounce_spike": "BOUNCE SPIKE",
               "daily_limit_hit": "DAILY LIMIT HIT"}

log = logging.getLogger(__name__)


# ───────────────────────── transport ─────────────────────────

def _config(token=None, chat_id=None) -> tuple[str, str]:
    t = token if token is not None else os.getenv("TELEGRAM_BOT_TOKEN", "")
    c = chat_id if chat_id is not None else os.getenv("TELEGRAM_CHAT_ID", "")
    return str(t or "").strip(), str(c or "").strip()


def _scrub(text, token: str) -> str:
    text = str(text or "")
    return text.replace(token, "***") if token else text


def _default_post(url, body, timeout):
    r = requests.post(url, json=body, timeout=timeout)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, {}


def _default_get(url, params, timeout):
    r = requests.get(url, params=params, timeout=timeout)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, {}


def is_configured(token=None, chat_id=None) -> bool:
    t, c = _config(token, chat_id)
    return bool(t and c)


def send_message(text: str, *, token=None, chat_id=None,
                 http_post=None) -> dict:
    """{"ok", "message_id"} or {"ok": False, "reason"}. Never raises."""
    t, c = _config(token, chat_id)
    if not t or not c:
        return {"ok": False, "reason": "telegram_not_configured"}
    if requests is None and http_post is None:
        return {"ok": False, "reason": "requests_not_installed"}
    body = {"chat_id": c, "text": str(text or "")[:MAX_LEN],
            "disable_web_page_preview": True}
    try:
        status, data = (http_post or _default_post)(API % (t, "sendMessage"),
                                                    body, 15)
    except Exception as e:                             # noqa: BLE001
        reason = _scrub("request_failed:%s: %s" % (type(e).__name__, e), t)
        log.warning("telegram send failed: %s", reason)
        return {"ok": False, "reason": reason[:300]}
    data = data or {}
    if status == 200 and data.get("ok"):
        log.info("telegram message sent (%d chars)", len(body["text"]))
        return {"ok": True, "message_id": (data.get("result") or {}).get(
            "message_id")}
    reason = _scrub("http_%s: %s" % (status, data.get("description")), t)
    log.warning("telegram send failed: %s", reason)
    return {"ok": False, "reason": reason[:300]}


# ───────────────────────── formatting ─────────────────────────

def _n(d, *keys, default=0):
    for k in keys:
        d = (d or {}).get(k) if isinstance(d, dict) else None
    return default if d is None else d


def _row(label, value) -> str:
    return "%-16s: %s" % (label, value)


def format_daily_report(report: dict, *, title: str = "Daily Report") -> str:
    r = report or {}
    lines = ["AI MENTORS — %s" % title, "Date: %s" % r.get("date", "")]
    if r.get("mode") == "dry_run":
        lines.append("(DRY RUN — nothing was sent)")
    lines += [
        "", "PROSPECTS",
        _row("Found today", _n(r, "prospects", "found")),
        _row("New in system", _n(r, "prospects", "new")),
        _row("Skipped", _n(r, "prospects", "skipped")),
        "", "SENDING",
        _row("Email sent", "%s (limit %s)" % (_n(r, "email", "sent"),
                                              _n(r, "email", "limit",
                                                 default=25))),
        _row("WhatsApp sent", "%s (limit %s)" % (
            _n(r, "whatsapp", "sent"), _n(r, "whatsapp", "limit",
                                          default=20))),
        _row("Follow-ups sent", _n(r, "combined", "followups_sent")),
        "", "ENGAGEMENT",
        _row("Opens", _n(r, "email", "opens")),
        _row("Replies", _n(r, "combined", "replies")),
        _row("Bounces", _n(r, "combined", "bounces")),
        _row("Unsubscribes", _n(r, "combined", "unsubscribes")),
        "", "TOMORROW",
        _row("Due follow-ups", _n(r, "combined", "due_tomorrow")),
        _row("Queue remaining", _n(r, "combined", "queue_remaining")),
        "", 'Reply "STATUS" to see today\'s progress anytime.']
    return "\n".join(lines)


def week_totals(week: list) -> dict:
    days = [d for d in (week or []) if isinstance(d, dict)]
    tot = {"days": len(days),
           "found": sum(_n(d, "prospects", "found") for d in days),
           "new": sum(_n(d, "prospects", "new") for d in days),
           "email_sent": sum(_n(d, "email", "sent") for d in days),
           "whatsapp_sent": sum(_n(d, "whatsapp", "sent") for d in days),
           "followups": sum(_n(d, "combined", "followups_sent")
                            for d in days),
           "replies": sum(_n(d, "combined", "replies") for d in days),
           "bounces": sum(_n(d, "combined", "bounces") for d in days),
           "unsubscribes": sum(_n(d, "combined", "unsubscribes")
                               for d in days)}
    sent = tot["email_sent"] + tot["whatsapp_sent"]
    tot["reply_rate"] = round(100.0 * tot["replies"] / sent, 1) if sent \
        else 0.0
    return tot


def format_weekly_report(week: list) -> str:
    t = week_totals(week)
    dates = sorted(d.get("date", "") for d in week or [] if isinstance(d,
                                                                       dict))
    span = "%s to %s" % (dates[0], dates[-1]) if dates else "no data"
    return "\n".join([
        "AI MENTORS — Weekly Report", "Days: %s (%s)" % (t["days"], span),
        "", "PROSPECTS",
        _row("Found", t["found"]), _row("New in system", t["new"]),
        "", "SENDING",
        _row("Email sent", t["email_sent"]),
        _row("WhatsApp sent", t["whatsapp_sent"]),
        _row("Follow-ups sent", t["followups"]),
        "", "ENGAGEMENT",
        _row("Replies", t["replies"]),
        _row("Reply rate", "%s%%" % t["reply_rate"]),
        _row("Bounces", t["bounces"]),
        _row("Unsubscribes", t["unsubscribes"])])


def format_alert(kind: str, details: dict) -> str:
    lines = ["AI MENTORS — ALERT: %s" % ALERT_KINDS.get(kind, kind)]
    for k, v in (details or {}).items():
        text = " ".join(str(v).split()) if not isinstance(v, str) else v
        lines.append("%s: %s" % (k, text[:600]))
    return "\n".join(lines)


# ───────────────────────── public senders ─────────────────────────

def send_daily_report(report: dict, **kw) -> dict:
    return send_message(format_daily_report(report), **kw)


def send_weekly_report(week: list, **kw) -> dict:
    return send_message(format_weekly_report(week), **kw)


def send_alert(kind: str, details: dict, **kw) -> dict:
    """kinds: run_failed, reply_received, bounce_spike, daily_limit_hit."""
    if kind not in ALERT_KINDS:
        return {"ok": False, "reason": "unknown_alert_kind"}
    return send_message(format_alert(kind, details), **kw)


# ───────────────────────── commands ─────────────────────────

HELP_TEXT = ("AI MENTORS bot commands:\nSTATUS - today's numbers\n"
             "PAUSE - skip the daily run until RESUME\nRESUME - run again\n"
             "HELP - this list")


def _default_status():
    from scheduler.run_daily import current_status
    return current_status()


def is_paused(flag_path=None) -> bool:
    return Path(flag_path or PAUSE_FLAG).exists()


def set_paused(paused: bool, flag_path=None, by: str = "manual") -> bool:
    p = Path(flag_path or PAUSE_FLAG)
    if paused:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(("paused by %s at %s\n" % (
            by, time.strftime("%Y-%m-%d %H:%M:%S"))).encode("utf-8"))
    elif p.exists():
        p.unlink()
    return p.exists()


def handle_command(text: str, *, status_fn=None, flag_path=None):
    """The reply text for a command, or None if the text is not one."""
    words = str(text or "").strip().split()
    if not words:
        return None
    cmd = words[0].lstrip("/").split("@")[0].upper()
    if cmd == "STATUS":
        try:
            report = (status_fn or _default_status)()
        except Exception as e:                          # noqa: BLE001
            return "Status unavailable: %s" % type(e).__name__
        return format_daily_report(report, title="Status")
    if cmd == "PAUSE":
        set_paused(True, flag_path, "telegram")
        return "Paused. The daily run will skip until you send RESUME."
    if cmd == "RESUME":
        set_paused(False, flag_path)
        return "Resumed. The next daily run will go ahead."
    if cmd in ("HELP", "START"):
        return HELP_TEXT
    return None


def poll_commands(*, token=None, chat_id=None, http_get=None, http_post=None,
                  offset_path=None, status_fn=None, flag_path=None,
                  timeout: int = 0) -> dict:
    """Read new messages once (getUpdates), answer commands from the
    configured chat only, and remember the offset."""
    t, c = _config(token, chat_id)
    if not t or not c:
        return {"ok": False, "reason": "telegram_not_configured",
                "handled": []}
    off_path = Path(offset_path or OFFSET_FILE)
    try:
        offset = int(json.loads(off_path.read_bytes() or b"{}")
                     .get("offset", 0))
    except (OSError, ValueError):
        offset = 0
    params = {"timeout": int(timeout), "allowed_updates": '["message"]'}
    if offset:
        params["offset"] = offset
    try:
        status, data = (http_get or _default_get)(API % (t, "getUpdates"),
                                                  params, int(timeout) + 15)
    except Exception as e:                             # noqa: BLE001
        return {"ok": False, "handled": [], "reason": _scrub(
            "request_failed:%s: %s" % (type(e).__name__, e), t)[:300]}
    if status != 200 or not (data or {}).get("ok"):
        return {"ok": False, "handled": [], "reason": _scrub(
            "http_%s: %s" % (status, (data or {}).get("description")), t)}
    handled, ignored = [], 0
    for upd in data.get("result") or []:
        offset = max(offset, int(upd.get("update_id", 0)) + 1)
        msg = upd.get("message") or {}
        if str((msg.get("chat") or {}).get("id", "")) != c:
            ignored += 1                     # not our chat: never answered
            continue
        reply = handle_command(msg.get("text", ""), status_fn=status_fn,
                               flag_path=flag_path)
        if reply:
            sent = send_message(reply, token=t, chat_id=c,
                                http_post=http_post)
            handled.append({"command": msg.get("text", "")[:20],
                            "sent": sent.get("ok")})
    off_path.parent.mkdir(parents=True, exist_ok=True)
    off_path.write_bytes(json.dumps({"offset": offset}).encode("utf-8"))
    return {"ok": True, "handled": handled, "ignored": ignored,
            "offset": offset}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m atlas_services.telegram_reporter")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--once", action="store_true",
                   help="answer pending commands once and exit")
    g.add_argument("--listen", action="store_true",
                   help="keep answering commands until Ctrl+C")
    a = ap.parse_args(argv)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    try:
        from scheduler.run_daily import load_env
        load_env()
    except Exception:                                  # noqa: BLE001
        pass
    if a.once:
        r = poll_commands()
        print("handled %d command(s)%s" % (len(r.get("handled", [])), (
            "" if r.get("ok") else " — %s" % r.get("reason"))))
        return 0 if r.get("ok") else 1
    print("Listening for STATUS / PAUSE / RESUME. Ctrl+C to stop.")
    try:
        while True:
            r = poll_commands(timeout=50)
            if not r.get("ok"):
                print("poll failed: %s" % r.get("reason"))
                time.sleep(30)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
