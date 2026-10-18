# -*- coding: utf-8 -*-
"""The daily outreach run — what Windows Task Scheduler starts each
morning.

    python -m scheduler.run_daily                 real run
    python -m scheduler.run_daily --dry-run       nothing is sent or paid
    python -m scheduler.run_daily --skip-finder   no Serper search today
    python -m scheduler.run_daily --report-only   report + Telegram only
    python -m scheduler.run_daily --force         run again today

Before anything: load Control_Center/.env through config.py (values are
never printed); main() stops with exit code 2 if SMTP_* or
SERPER_API_KEY is missing for a real run; answer pending Telegram
commands, stop if paused.flag exists (real runs), stop if a real run
already finished today, take a lock.

Steps (each isolated: a failure is logged with its traceback, alerted on
Telegram, and the run goes on with the next step):
  6  poll replies and bounces   IMAP (if IMAP_* set) + Meta webhook files
     — runs FIRST, so nobody who replied overnight gets a follow-up today
  1  find new prospects         prospect_finder.find_prospects_auto
                                (5 sectors x 20, ~25 Serper calls)
  2  enrich                     prospect_enricher, new prospects that
                                have a website and lack an email/mobile
  3  route channels             channel_router.route_batch
  4  start day 0                unified_sequence.start (confirmed — the
                                scheduler is the confirming authority on
                                a real run)
  5  process due follow-ups     unified_sequence.process_due
  7  daily report               data/reports/daily_<date>.json + Telegram
  8  weekly report              Sundays (Dubai): last 7 daily reports
  9  log                        data/scheduler/run_log.jsonl

A dry run makes no Serper call, fetches no website, sends nothing and
sends no Telegram message; it works on the newest daily_*.json and saves
its report as daily_<date>_dryrun.json.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(
    __file__))))
import config  # noqa: F401,E402  (loads .env before anything else)

import argparse                                                # noqa: E402
import email                                                   # noqa: E402
import imaplib                                                 # noqa: E402
import json                                                    # noqa: E402
import re                                                      # noqa: E402
import time                                                    # noqa: E402
import traceback                                              # noqa: E402
import uuid                                                    # noqa: E402
from datetime import timedelta                                 # noqa: E402
from email.utils import parseaddr                              # noqa: E402
from pathlib import Path                                       # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from atlas_services import channel_router                     # noqa: E402
from atlas_services import email_tracker as ET                # noqa: E402
from atlas_services import telegram_reporter as TG            # noqa: E402
from atlas_services import whatsapp_tracker as WT             # noqa: E402
from atlas_services.email_sender import EmailSender           # noqa: E402
from atlas_services.email_sequence import EmailSequence       # noqa: E402
from atlas_services.unified_sequence import (                 # noqa: E402
    SequenceStore, UnifiedSequence)
from atlas_services.whatsapp_sender import (                  # noqa: E402
    WhatsAppSender, WhatsAppSequence, is_mobile)

DATA = ROOT / "data"
TASK_NAME = "AI_Mentors_Daily_Run"
LOCK_STALE_AFTER = timedelta(hours=3)
MAX_PER_SECTOR = 20
MAX_REPLY_ALERTS = 10


# ───────────────────────── environment ─────────────────────────

def load_env(path=None) -> bool:
    """Control_Center/.env (and .env.local, if present) into os.environ;
    existing variables win. config.py already did this at import — this
    is kept for callers that pass another file. A scheduled task does not
    inherit a PowerShell session's variables, so this is where SMTP_*,
    WHATSAPP_*, TELEGRAM_*, SERPER_API_KEY and IMAP_* come from. Values
    are never printed."""
    if os.getenv("CONTROL_CENTER_NO_DOTENV") == "1" and path is None:
        return False
    if path:
        return config.load_env_file(path)
    loaded = config.load_env_file(config._ENV_PATH)
    return config.load_env_file(config._ENV_LOCAL_PATH) or loaded


class Paths:
    def __init__(self, data_root=None):
        root = Path(data_root) if data_root else DATA
        self.root = root
        self.email = root / "email"
        self.whatsapp = root / "whatsapp"
        self.scheduler = root / "scheduler"
        self.reports = root / "reports"
        self.prospects = root / "prospects"
        self.run_log = self.scheduler / "run_log.jsonl"
        self.pause_flag = self.scheduler / "paused.flag"
        self.lock = self.scheduler / "run.lock"
        self.imap_seen = self.scheduler / "imap_seen.json"
        self.last_log = self.scheduler / "last_run.log"


def build_unified(*, dry_run: bool, paths: Paths, now=None):
    et = ET.EmailTracker(paths.email, now=now)
    wt = WT.WhatsAppTracker(paths.whatsapp, now=now)
    es = EmailSender(dry_run=dry_run, tracker=et, now=now)
    ws = WhatsAppSender(dry_run=dry_run, tracker=wt, now=now)
    return UnifiedSequence(EmailSequence(es, et), WhatsAppSequence(ws, wt),
                           channel_router,
                           SequenceStore(paths.scheduler, now=now))


# ───────────────────────── replies: IMAP ─────────────────────────

_FINAL_RCPT = re.compile(r"(?:Final|Original)-Recipient:\s*rfc822;\s*"
                         r"<?([^\s<>;]+@[^\s<>;]+)>?", re.I)


def _first_text(msg) -> str:
    for part in msg.walk() if msg.is_multipart() else [msg]:
        if part.get_content_type() == "text/plain":
            try:
                return part.get_payload(decode=True).decode(
                    part.get_content_charset() or "utf-8", "replace")
            except Exception:                           # noqa: BLE001
                return ""
    return ""


def poll_imap_replies(email_tracker, *, seen_path, imap_factory=None,
                      now=None, days: int = 3) -> dict:
    """Read-only scan of the inbox (IMAP_HOST, IMAP_PORT=993, IMAP_USER,
    IMAP_PASSWORD, IMAP_FOLDER=INBOX). A message from an address we have
    emailed is a reply; a delivery report naming one is a bounce;
    auto-replies are ignored. Messages are never marked read or moved."""
    host, user = os.getenv("IMAP_HOST", ""), os.getenv("IMAP_USER", "")
    pw = os.getenv("IMAP_PASSWORD", "")
    if not (host and user and pw):
        return {"skipped": "imap_not_configured", "replies": [],
                "bounces": []}
    known = {s["email"] for s in email_tracker.all_states()
             if s.get("sends")}
    try:
        seen = set(json.loads(Path(seen_path).read_bytes() or b"[]"))
    except (OSError, ValueError):
        seen = set()
    out = {"replies": [], "bounces": [], "checked": 0, "auto_replies": 0}
    conn = (imap_factory or imaplib.IMAP4_SSL)(
        host, int(os.getenv("IMAP_PORT") or 993))
    try:
        conn.login(user, pw)
        conn.select(os.getenv("IMAP_FOLDER") or "INBOX", readonly=True)
        since = ((now or ET.utcnow()) - timedelta(days=days)).strftime(
            "%d-%b-%Y")
        _typ, data = conn.search(None, "SINCE", since)
        for num in (data[0].split() if data and data[0] else [])[-300:]:
            _typ, parts = conn.fetch(num, "(BODY.PEEK[]<0.30000>)")
            raw = next((p[1] for p in parts or [] if isinstance(p, tuple)),
                       b"")
            msg = email.message_from_bytes(raw or b"")
            mid = (msg.get("Message-ID") or "").strip() or "num:%s" % num
            if mid in seen:
                continue
            seen.add(mid)
            out["checked"] += 1
            sender = parseaddr(msg.get("From", ""))[1].lower()
            text = _first_text(msg)
            is_report = msg.get_content_type() == "multipart/report" or \
                sender.split("@")[0] in ("mailer-daemon", "postmaster")
            if is_report:
                for rcpt in set(_FINAL_RCPT.findall(raw.decode(
                        "utf-8", "replace"))):
                    r = ET.normalize_email(rcpt)
                    if r in known:
                        email_tracker.record_bounced(r, "delivery report")
                        out["bounces"].append(r)
                continue
            auto = (msg.get("Auto-Submitted", "no").lower() != "no"
                    or msg.get("X-Autoreply") or msg.get("X-Autorespond"))
            if sender in known:
                if auto:
                    out["auto_replies"] += 1
                    continue
                st = email_tracker.record_replied(sender, text)
                out["replies"].append({
                    "channel": "email", "contact": sender,
                    "subject": (msg.get("Subject") or "")[:120],
                    "text": " ".join(text.split())[:200],
                    "status": st.get("status")})
    finally:
        try:
            conn.logout()
        except Exception:                               # noqa: BLE001
            pass
    p = Path(seen_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(json.dumps(sorted(seen)[-5000:]).encode("utf-8"))
    return out


# ───────────────────────── run log ─────────────────────────

def read_run_log(paths: Paths | None = None, limit: int | None = None):
    paths = paths or Paths()
    try:
        lines = paths.run_log.read_bytes().decode("utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out[-limit:] if limit else out


def _ran_today(paths: Paths, today: str) -> dict | None:
    for rec in reversed(read_run_log(paths)):
        if rec.get("date") == today and rec.get("mode") == "real" and \
                rec.get("result") in ("ok", "partial"):
            return rec
    return None


def _take_lock(paths: Paths, now) -> bool:
    paths.scheduler.mkdir(parents=True, exist_ok=True)
    if paths.lock.exists():
        try:
            info = json.loads(paths.lock.read_bytes())
            started = ET.parse_iso(info.get("started_at"))
        except (OSError, ValueError):
            started = None
        if started and now - started < LOCK_STALE_AFTER:
            return False
    paths.lock.write_bytes(json.dumps({"pid": os.getpid(), "started_at":
                                       ET.iso(now)}).encode("utf-8"))
    return True


def _known(unified, prospect) -> bool:
    e = ET.normalize_email(prospect.get("email"))
    p = WT.normalize_phone(prospect.get("phone_e164"))
    if (e and unified.store.find(e)) or (p and unified.store.find(p)):
        return True
    if e and unified.email_tracker.get_prospect_state(e).get("sends"):
        return True
    return bool(p and unified.wa_tracker.get_prospect_state(p).get("sends"))


def _latest_daily(paths: Paths) -> tuple[list, str | None]:
    files = sorted(paths.prospects.glob("daily_*.json")) \
        if paths.prospects.is_dir() else []
    for f in reversed(files):
        try:
            return (json.loads(f.read_bytes().decode("utf-8")).get(
                "companies") or [], f.name)
        except (OSError, ValueError, AttributeError):
            continue
    return [], None


# ───────────────────────── dependencies (tests replace) ──────────────

class Deps:
    def __init__(self, **kw):
        self.find_auto = kw.get("find_auto")
        self.enrich = kw.get("enrich")
        self.build_unified = kw.get("build_unified", build_unified)
        self.telegram = kw.get("telegram", TG)
        self.poll_imap = kw.get("poll_imap", poll_imap_replies)
        self.now = kw.get("now", ET.utcnow)
        self.load_env = kw.get("load_env", load_env)
        self.data_root = kw.get("data_root", DATA)
        if self.find_auto is None:
            from atlas_services.prospect_finder import find_prospects_auto
            self.find_auto = find_prospects_auto
        if self.enrich is None:
            from atlas_services.prospect_enricher import enrich_many
            self.enrich = enrich_many


# ───────────────────────── the run ─────────────────────────

def run_daily(*, dry_run: bool = False, skip_finder: bool = False,
              report_only: bool = False, force: bool = False,
              language: str | None = None, country: str | None = None,
              deps: Deps | None = None, echo=None) -> dict:
    deps = deps or Deps()
    try:
        deps.load_env()
    except Exception:                                   # noqa: BLE001
        pass
    paths = Paths(deps.data_root)
    now = deps.now()
    today = ET.dubai_day(now)
    mode = ("report_only" if report_only else "dry_run" if dry_run
            else "real")
    real = mode == "real"
    language = language or os.getenv("ATLAS_LANGUAGE") or "ar"
    country = (country or os.getenv("ATLAS_COUNTRY") or "AE").upper()
    run = {"run_id": uuid.uuid4().hex[:12], "date": today.isoformat(),
           "started_at": ET.iso(now), "mode": mode, "language": language,
           "country": country, "result": None, "steps": [], "log": []}
    t_start = time.perf_counter()

    def say(msg: str) -> None:
        line = "%s  %s" % (time.strftime("%H:%M:%S"), msg)
        run["log"].append(line)
        if echo:
            echo(line)

    def alert(kind, details):
        if mode == "dry_run":
            return
        try:
            deps.telegram.send_alert(kind, details)
        except Exception:                               # noqa: BLE001
            pass

    def finish(result: str) -> dict:
        run["result"] = result
        run["finished_at"] = ET.iso(deps.now())
        run["duration_ms"] = int((time.perf_counter() - t_start) * 1000)
        say("result: %s (%d ms)" % (result, run["duration_ms"]))
        rec = dict(run, log=run["log"][-400:])
        paths.scheduler.mkdir(parents=True, exist_ok=True)
        with open(paths.run_log, "ab") as f:
            f.write((json.dumps(rec, ensure_ascii=False) + "\n")
                    .encode("utf-8"))
        paths.last_log.write_bytes("\n".join(run["log"]).encode("utf-8"))
        return run

    say("daily run %s · mode %s · %s · language %s" % (
        run["run_id"], mode, today, language))

    # commands, pause, once a day, lock
    if real:
        try:
            r = deps.telegram.poll_commands(
                status_fn=lambda: current_status(paths),
                flag_path=paths.pause_flag)
            if r.get("handled"):
                say("telegram: answered %d command(s)" % len(r["handled"]))
        except Exception as e:                          # noqa: BLE001
            say("telegram commands not read: %s" % type(e).__name__)
    if real and paths.pause_flag.exists():
        say("paused.flag found — nothing done (send RESUME or remove the "
            "flag)")
        return finish("paused")
    if real and not force:
        prev = _ran_today(paths, run["date"])
        if prev:
            say("a real run already finished today (%s, %s) — skipped; use "
                "--force to run again" % (prev.get("run_id"),
                                         prev.get("result")))
            return finish("skipped_already_ran")
    if not report_only and not _take_lock(paths, now):
        say("another run holds the lock — skipped")
        return finish("skipped_locked")

    ctx = {"prospects": {"found": 0, "new": 0, "skipped": 0},
           "companies": [], "routed": []}

    try:
        unified = deps.build_unified(dry_run=not real, paths=paths,
                                     now=deps.now)

        def step(num, name, fn):
            t0 = time.perf_counter()
            entry = {"step": num, "name": name}
            try:
                summary = fn() or {}
                entry.update(status="skipped" if summary.get("skipped")
                             else "ok", summary=summary)
                say("step %s %s: %s" % (num, name, summary.get("skipped")
                                        or _short(summary)))
            except Exception as e:                      # noqa: BLE001
                entry.update(status="failed",
                             error=("%s: %s" % (type(e).__name__, e))[:500],
                             traceback=traceback.format_exc()[-4000:])
                say("step %s %s FAILED: %s" % (num, name, entry["error"]))
                alert("run_failed", {"step": "%s %s" % (num, name),
                                     "error": entry["error"],
                                     "run_id": run["run_id"]})
            entry["duration_ms"] = int((time.perf_counter() - t0) * 1000)
            run["steps"].append(entry)
            return entry

        # 6 — replies first
        def poll_replies():
            if not real:
                return {"skipped": "only on a real run"}
            imap = deps.poll_imap(unified.email_tracker,
                                  seen_path=paths.imap_seen, now=now)
            hooks = unified.wa_tracker.process_webhook_folder()
            wa_replies = [dict(r, channel="whatsapp", contact=r["phone"])
                          for r in hooks.get("replies", [])]
            replies = imap.get("replies", []) + wa_replies
            for r in replies[:MAX_REPLY_ALERTS]:
                alert("reply_received", {
                    "channel": r.get("channel"), "from": r.get("contact"),
                    "status": r.get("status"), "text": r.get("text", "")})
            if len(replies) > MAX_REPLY_ALERTS:
                alert("reply_received", {"more": "%d more replies — see "
                                         "the Control Center"
                                         % (len(replies) - MAX_REPLY_ALERTS)})
            return {"imap": imap.get("skipped") or "%d checked" % imap.get(
                "checked", 0), "email_replies": len(imap.get("replies", [])),
                "email_bounces": len(imap.get("bounces", [])),
                "webhook_files": hooks.get("files", 0),
                "whatsapp_replies": len(wa_replies)}

        # 1 — find
        def find():
            if report_only:
                return {"skipped": "report only"}
            if dry_run or skip_finder:
                rows, name = _latest_daily(paths)
                fresh = [c for c in rows if isinstance(c, dict)
                         and not _known(unified, c)]
                ctx["companies"] = fresh
                ctx["prospects"].update(found=len(rows), new=len(fresh))
                return {"source": name or "no daily file yet",
                        "note": "dry run: no Serper call" if dry_run
                        else "--skip-finder", "candidates": len(fresh)}
            r = deps.find_auto(country=country, max_per_sector=MAX_PER_SECTOR,
                               out_dir=str(paths.prospects))
            fresh = [c for c in r.get("companies") or []
                     if isinstance(c, dict) and not _known(unified, c)]
            ctx["companies"] = fresh
            ctx["prospects"].update(found=r.get("total_found", 0),
                                    new=len(fresh))
            return {"found": r.get("total_found", 0), "new": len(fresh),
                    "duplicates": r.get("duplicates", 0),
                    "serper_calls": r.get("serper_calls", 0),
                    "out_path": r.get("out_path")}

        # 2 — enrich
        def enrich():
            if report_only:
                return {"skipped": "report only"}
            todo = [c for c in ctx["companies"] if c.get("website") and (
                not ET.normalize_email(c.get("email"))
                or not is_mobile(c.get("phone_e164")))]
            if not todo:
                return {"skipped": "nothing to enrich (no website or "
                                   "already complete)"}
            if not real:
                return {"skipped": "dry run: would enrich %d" % len(todo)}
            r = deps.enrich(todo, max_companies=100)
            by_id = {id(c): c for c in todo}
            improved = 0
            for comp, res in zip(todo, r.get("results") or []):
                c = by_id[id(comp)]
                before = (c.get("email"), c.get("phone_e164"))
                if not ET.normalize_email(c.get("email")) and \
                        res.get("email"):
                    c["email"] = res["email"]
                if not is_mobile(c.get("phone_e164")):
                    mob = next((p for p in res.get("phones_all") or []
                                if is_mobile(p)), None)
                    if mob:
                        c["phone_e164"] = mob
                improved += (c.get("email"), c.get("phone_e164")) != before
            return {"processed": r.get("processed", 0),
                    "improved": improved,
                    "network_calls": r.get("network_calls", 0)}

        # 3 — route
        def route():
            if report_only:
                return {"skipped": "report only"}
            routes = channel_router.route_batch(
                ctx["companies"], email_data_dir=paths.email,
                wa_data_dir=paths.whatsapp)
            ctx["routed"] = [c for c, r in zip(ctx["companies"], routes)
                             if not r["skip"]]
            ctx["prospects"]["skipped"] = len(routes) - len(ctx["routed"])
            st = channel_router.stats(routes)
            paths.scheduler.mkdir(parents=True, exist_ok=True)
            name = "routes_%s%s.json" % (today.strftime("%Y%m%d"),
                                         "" if real else "_dryrun")
            (paths.scheduler / name).write_bytes(json.dumps(
                {"stats": st, "routes": [
                    {"company_name": c.get("company_name"), **r}
                    for c, r in zip(ctx["companies"], routes)]},
                ensure_ascii=False, indent=1).encode("utf-8"))
            return dict(st, routed=len(ctx["routed"]))

        # 4 — start day 0
        def start():
            if report_only:
                return {"skipped": "report only"}
            counts = {}
            for c in ctx["routed"]:
                r = unified.start(c, language=language, confirmed=real)
                for ch, res in r.get("results", {}).items():
                    k = "%s_%s" % (ch, res.get("status"))
                    counts[k] = counts.get(k, 0) + 1
            return dict(counts, prospects=len(ctx["routed"]))

        # 5 — follow-ups
        def due():
            if report_only:
                return {"skipped": "report only"}
            s = unified.process_due(confirmed=real, max_count=100)
            return {k: s[k] for k in ("checked", "processed", "sent",
                                      "dry_run", "blocked", "failed",
                                      "stopped", "completed")}

        # 7 — daily report
        def report():
            rep = unified.daily_report()
            prev_path = paths.reports / ("daily_%s.json"
                                         % today.strftime("%Y%m%d"))
            if report_only and prev_path.exists():
                try:
                    ctx["prospects"] = json.loads(prev_path.read_bytes())\
                        .get("prospects") or ctx["prospects"]
                except ValueError:
                    pass
            rep.update(prospects=ctx["prospects"], mode=mode,
                       run_id=run["run_id"], generated_at=ET.iso(deps.now()))
            paths.reports.mkdir(parents=True, exist_ok=True)
            out = paths.reports / ("daily_%s%s.json" % (
                today.strftime("%Y%m%d"), "_dryrun" if dry_run else ""))
            out.write_bytes(json.dumps(rep, ensure_ascii=False, indent=1)
                            .encode("utf-8"))
            ctx["report"] = rep
            say(TG.format_daily_report(rep).replace("\n", " | "))
            sent = None
            if not dry_run:
                sent = deps.telegram.send_daily_report(rep).get("ok")
                comb, em, wa = rep["combined"], rep["email"], rep["whatsapp"]
                total = em["sent"] + wa["sent"]
                if comb["bounces"] >= 3 and total and \
                        comb["bounces"] / total >= 0.1:
                    alert("bounce_spike", {"bounces": comb["bounces"],
                                           "sent_today": total})
                full = [n for n, ch in (("email", em), ("whatsapp", wa))
                        if ch["sent"] >= ch["limit"]]
                if full and comb["queue_remaining"]:
                    alert("daily_limit_hit", {
                        "channels": ", ".join(full),
                        "queue_remaining": comb["queue_remaining"]})
            return {"path": str(out), "telegram": sent}

        # 8 — weekly (Sunday, Dubai)
        def weekly():
            if dry_run or today.weekday() != 6:
                return {"skipped": "only on Sundays (real run)"}
            week = []
            for i in range(7):
                d = today - timedelta(days=i)
                f = paths.reports / ("daily_%s.json" % d.strftime("%Y%m%d"))
                try:
                    week.append(json.loads(f.read_bytes()))
                except (OSError, ValueError):
                    continue
            totals = TG.week_totals(week)
            out = paths.reports / ("weekly_%s.json"
                                   % today.strftime("%Y%m%d"))
            out.write_bytes(json.dumps({"totals": totals, "days": week},
                                       ensure_ascii=False, indent=1)
                            .encode("utf-8"))
            sent = deps.telegram.send_weekly_report(week).get("ok")
            return dict(totals, telegram=sent)

        step(6, "poll replies and bounces", poll_replies)
        step(1, "find new prospects", find)
        step(2, "enrich", enrich)
        step(3, "route channels", route)
        step(4, "start day 0", start)
        step(5, "process due follow-ups", due)
        step(7, "daily report", report)
        step(8, "weekly report", weekly)
    except Exception as e:                              # noqa: BLE001
        run["error"] = ("%s: %s" % (type(e).__name__, e))[:500]
        run["traceback"] = traceback.format_exc()[-4000:]
        say("RUN FAILED: %s" % run["error"])
        alert("run_failed", {"step": "setup", "error": run["error"],
                             "run_id": run["run_id"]})
        result = "failed"
    else:
        failed = [s for s in run["steps"] if s["status"] == "failed"]
        result = "partial" if failed else "ok"
    finally:
        if not report_only:
            try:
                paths.lock.unlink()
            except OSError:
                pass
    run["report"] = ctx.get("report")
    return finish(result)


def _short(summary: dict) -> str:
    return ", ".join("%s=%s" % (k, v) for k, v in summary.items()
                     if not isinstance(v, (dict, list)))[:300]


def current_status(paths: Paths | None = None) -> dict:
    """Today's numbers without sending anything (Telegram STATUS, the
    Scheduler page)."""
    paths = paths or Paths()
    rep = build_unified(dry_run=True, paths=paths).daily_report()
    f = paths.reports / ("daily_%s.json" % rep["date"].replace("-", ""))
    try:
        rep["prospects"] = json.loads(f.read_bytes()).get("prospects") or {}
    except (OSError, ValueError):
        rep["prospects"] = {}
    return rep


# ───────────────────────── CLI ─────────────────────────

def _echo(line: str) -> None:
    try:
        print(line, flush=True)
    except UnicodeEncodeError:
        sys.stdout.buffer.write((line + "\n").encode("utf-8"))
        sys.stdout.flush()


CRITICAL_PREFIXES = ("SMTP_", "SERPER_")


def main(argv=None) -> int:
    from config import env_status
    missing = [k for k, ok in env_status().items() if not ok]
    critical = [k for k in missing if k.startswith(CRITICAL_PREFIXES)]
    args = sys.argv[1:] if argv is None else list(argv)
    # a dry run and a report-only run use neither SMTP nor Serper, so they
    # still work while keys are missing
    if critical and not ({"--dry-run", "--report-only", "-h", "--help"}
                         & set(args)):
        print("STOPPED: missing critical env vars: %s" % critical)
        print("Add them to %s (names only are shown, never values)."
              % config._ENV_PATH)
        return 2
    if missing:
        print("note: not set (those features stay off): %s" % missing)
    ap = argparse.ArgumentParser(prog="python -m scheduler.run_daily")
    ap.add_argument("--dry-run", action="store_true",
                    help="send nothing, call no paid API")
    ap.add_argument("--skip-finder", action="store_true",
                    help="no Serper search; use the newest daily file")
    ap.add_argument("--report-only", action="store_true",
                    help="only build and send today's report")
    ap.add_argument("--force", action="store_true",
                    help="run even if a real run finished today")
    ap.add_argument("--language", choices=["ar", "en"], default=None)
    ap.add_argument("--country", choices=["AE", "SA"], default=None)
    a = ap.parse_args(argv)
    r = run_daily(dry_run=a.dry_run, skip_finder=a.skip_finder,
                  report_only=a.report_only, force=a.force,
                  language=a.language, country=a.country, echo=_echo)
    return 1 if r["result"] in ("failed", "partial") else 0


if __name__ == "__main__":
    sys.exit(main())
