# -*- coding: utf-8 -*-
"""ATLAS unified sequence: one schedule across email and WhatsApp.

Per prospect, counted from each channel's own day 0 send:

    day 0   email day0      + WhatsApp day0   (whichever channels apply)
    day 2   WhatsApp day2   follow-up
    day 3   email day3      follow-up
    day 7   WhatsApp day7   soft nudge        (LATE_TEMPLATES)
    day 14  email day14     polite break-up   (EMAIL_DAY14, below)

Rules:
  - The router decides the channels once, at start.
  - A channel's follow-ups go only after that channel's day 0 was sent;
    one step per channel per run, in order.
  - A reply or unsubscribe on EITHER channel stops the whole sequence and
    suppresses the prospect on the other channel too. A bounce or a
    suppression stops only that channel.
  - Steps blocked for a passing reason (daily limit, template not yet
    approved, not configured, a network failure) stay pending and are
    retried on the next run; after 7 days past due they expire.
  - Dry runs never change the stored schedule.
  - Each channel's daily limit applies independently.

Storage: data/scheduler/sequence_state.json (SequenceStore).
"""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from atlas_services import email_templates as ETPL
from atlas_services import email_tracker as ET
from atlas_services import whatsapp_templates as WTPL
from atlas_services import whatsapp_tracker as WT

STEPS = [
    {"key": "day0_email", "day": "day0", "channel": "email", "offset": 0},
    {"key": "day0_whatsapp", "day": "day0", "channel": "whatsapp",
     "offset": 0},
    {"key": "day2_whatsapp", "day": "day2", "channel": "whatsapp",
     "offset": 2},
    {"key": "day3_email", "day": "day3", "channel": "email", "offset": 3},
    {"key": "day7_whatsapp", "day": "day7", "channel": "whatsapp",
     "offset": 7},
    {"key": "day14_email", "day": "day14", "channel": "email",
     "offset": 14},
]
STEP_BY_KEY = {s["key"]: s for s in STEPS}
CHANNELS = ("email", "whatsapp")
RETRY_REASONS = {"daily_limit_reached", "sent_within_20h",
                 "duplicate_in_batch", "template_not_approved",
                 "smtp_not_configured", "whatsapp_not_configured",
                 "not_confirmed", "dry_run"}
MAX_FAILED_ATTEMPTS = 3
EXPIRE_AFTER = timedelta(days=7)
STOP_ALL = ("replied", "unsubscribed")

# ── email day14: the polite break-up (built like the other 20) ──
EMAIL_DAY14 = {
    "en": ("Closing the loop",
           "I have written a couple of times about ALPHA, the AI WhatsApp "
           "employee, and I do not want to crowd your inbox.",
           "If after-hours inquiries are not a priority for {company_name} "
           "right now, that is completely fine. This is my last note.",
           "If it ever becomes useful, just reply to this email and I will "
           "pick it up from there."),
    "ar": ("رسالتي الأخيرة",
           "كتبت لكم مرتين عن ALPHA، الموظف الذكي على واتساب، ولا أريد أن "
           "أُثقل بريدكم.",
           "إن لم تكن استفسارات ما بعد الدوام أولوية لدى {company_name} حالياً "
           "فلا بأس أبداً، وهذه رسالتي الأخيرة.",
           "وإن أصبح الأمر مفيداً يوماً ما، يكفي الرد على هذه الرسالة وسأتابع "
           "معكم من هناك."),
}


def email_day14_template(sector: str, language: str) -> dict:
    subject, p1, p2, cta = EMAIL_DAY14[language]
    return {"id": "%s_%s_day14" % (sector, language), "sector": sector,
            "language": language, "category": "day14_breakup",
            "day": "day14", "subject": subject,
            "body": ETPL._plain(language, p1, p2, cta),
            "body_html": ETPL._html(language, p1, p2, cta)}


# ───────────────────────── store ─────────────────────────

class SequenceStore:
    """One record per prospect, keyed by email (else phone)."""

    def __init__(self, data_dir="data/scheduler", *, now=None):
        p = Path(data_dir)
        self.data_dir = p if p.is_absolute() else ET.ROOT / p
        self.path = self.data_dir / "sequence_state.json"
        self._now = now or ET.utcnow

    def _load(self) -> dict:
        data = ET._read_json(self.path, {})
        return data if isinstance(data, dict) else {}

    def all(self) -> list[dict]:
        return list(self._load().values())

    def get(self, key: str) -> dict | None:
        return self._load().get(key)

    def find(self, email_or_phone) -> dict | None:
        e = ET.normalize_email(email_or_phone)
        p = WT.normalize_phone(email_or_phone)
        for rec in self._load().values():
            if (e and rec.get("email") == e) or \
                    (p and rec.get("phone_e164") == p):
                return rec
        return None

    def put(self, rec: dict) -> None:
        data = self._load()
        data[rec["key"]] = rec
        ET._write_json(self.path, data)


# ───────────────────────── sequence ─────────────────────────

class UnifiedSequence:
    def __init__(self, email_seq, wa_seq, router, tracker):
        """email_seq: EmailSequence; wa_seq: WhatsAppSequence; router:
        the channel_router module (anything with route()); tracker: a
        SequenceStore."""
        self.email_seq, self.wa_seq = email_seq, wa_seq
        self.router, self.store = router, tracker
        self.email_sender, self.email_tracker = email_seq.sender, \
            email_seq.tracker
        self.wa_sender, self.wa_tracker = wa_seq.sender, wa_seq.tracker

    def _now(self):
        return self.email_sender._now()

    def _is_real(self, confirmed: bool) -> bool:
        return bool(confirmed) and not (self.email_sender.dry_run
                                        and self.wa_sender.dry_run)

    @staticmethod
    def _prospect(rec: dict) -> dict:
        return {"email": rec.get("email"), "phone_e164": rec.get(
            "phone_e164"), "company_name": rec.get("company_name"),
            "contact_name": rec.get("contact_name"),
            "sector": rec.get("sector"), "country": rec.get("country"),
            "industry": rec.get("industry")}

    # ── one step ──
    def _send(self, rec, step, language, confirmed) -> dict:
        p = self._prospect(rec)
        ch, day = step["channel"], step["day"]
        if ch == "email":
            state = self.email_tracker.get_prospect_state(p["email"])
            if day == "day0":
                out = self.email_seq.start(p, language=language,
                                           confirmed=confirmed)
                r = dict(out["result"], template_id=out["template_id"])
                if r["reason"] == "already_started":
                    r = self._elsewhere(state, r)
                return r
            if (day == "day3" and state.get("last_sent_day") in
                    ("day3", "day14")) or (day == "day14" and state.get(
                        "last_sent_day") == "day14"):
                return self._elsewhere(state, {"template_id": ""})
            tpl = (ETPL.get_sequence(p["sector"], language)[1]
                   if day == "day3"
                   else email_day14_template(p["sector"], language))
            rendered = ETPL.render(tpl, p)
            r = self.email_sender.send(p, rendered, template_id=tpl["id"],
                                       confirmed=confirmed)
            self.email_tracker.record_sent(dict(p, language=language),
                                           tpl["id"], r)
            return dict(r, template_id=tpl["id"])
        state = self.wa_tracker.get_prospect_state(p["phone_e164"])
        if day == "day0":
            out = self.wa_seq.start(p, language=language,
                                    confirmed=confirmed)
            r = out["result"]
            if r["reason"] == "already_started":
                r = self._elsewhere(state, r)
            return r
        if (day == "day2" and state.get("last_sent_day") in
                ("day2", "day7")) or (day == "day7" and state.get(
                    "last_sent_day") == "day7"):
            return self._elsewhere(state, {"template_id": ""})
        tpl = (WTPL.get_sequence(p["sector"], language)[1] if day == "day2"
               else WTPL.late_template(language))
        r = self.wa_sender.send(p, tpl, confirmed=confirmed)
        self.wa_tracker.record_sent(dict(p, language=language), tpl["id"], r)
        return r

    @staticmethod
    def _elsewhere(state, r) -> dict:
        """Already sent from the Email or WhatsApp page: count it."""
        return dict(r, ok=True, status="sent", reason="sent_elsewhere",
                    sent_at=state.get("last_sent_at"))

    def _apply(self, rec, step, r, now) -> None:
        s = rec["steps"].setdefault(step["key"], {"status": "pending",
                                                  "attempts": 0})
        status, reason = r.get("status"), r.get("reason")
        s["last_try"] = ET.iso(now)
        s["template_id"] = r.get("template_id") or s.get("template_id")
        if status == "sent":
            s.update(status="sent", at=r.get("sent_at") or ET.iso(now),
                     reason=reason, message_id=r.get("message_id"))
        elif status == "dry_run":
            return
        elif status == "failed" or reason in RETRY_REASONS:
            if status == "failed":
                s["attempts"] = int(s.get("attempts") or 0) + 1
            s.update(status="skipped" if s["attempts"] >= MAX_FAILED_ATTEMPTS
                     else "pending", reason=reason)
        else:
            s.update(status="skipped", reason=reason)

    # ── start ──
    def start(self, prospect: dict, *, language: str = "ar",
              confirmed: bool = False) -> dict:
        p = dict(prospect or {})
        now = self._now()
        route = self.router.route(p, email_data_dir=self.email_tracker
                                  .data_dir,
                                  wa_data_dir=self.wa_tracker.data_dir)
        out = {"ok": False, "skipped": route["skip"], "route": route,
               "results": {}, "key": None, "reason": route["reason"]}
        if route["skip"]:
            return out
        email, phone = route.get("email"), route.get("phone_e164")
        if (email and self.store.find(email)) or \
                (phone and self.store.find(phone)):
            return dict(out, reason="already_started")
        rec = {"key": email or phone, "email": email, "phone_e164": phone,
               "company_name": p.get("company_name") or "",
               "contact_name": p.get("contact_name") or "",
               "sector": p.get("sector"), "country": (
                   p.get("country") or "").upper() or None,
               "industry": p.get("industry") or "", "language": language,
               "channels": route["channels"], "route_reason":
               route["reason"], "started_at": ET.iso(now),
               "status": "active", "stop_reason": None,
               "steps": {s["key"]: {"status": "pending", "attempts": 0}
                         for s in STEPS if s["channel"] in route["channels"]}}
        for ch in route["channels"]:
            step = STEP_BY_KEY["day0_%s" % ch]
            r = self._send(rec, step, language, confirmed)
            out["results"][ch] = r
            self._apply(rec, step, r, now)
        out.update(ok=True, key=rec["key"])
        if self._is_real(confirmed):
            self._settle(rec, now)
            self.store.put(rec)
            out["record"] = rec
        return out

    # ── due steps ──
    def _due_at(self, rec, step):
        if step["day"] == "day0":
            return ET.parse_iso(rec.get("started_at"))
        d0 = rec["steps"].get("day0_%s" % step["channel"]) or {}
        at = ET.parse_iso(d0.get("at")) if d0.get("status") == "sent" \
            else None
        return at + timedelta(days=step["offset"]) if at else None

    def _next_step(self, rec, channel, now):
        """The first unfinished step of a channel if it is due now. Marks
        steps that can no longer go as skipped."""
        for step in STEPS:
            if step["channel"] != channel:
                continue
            s = rec["steps"].setdefault(step["key"], {"status": "pending",
                                                      "attempts": 0})
            if s["status"] in ("sent", "skipped"):
                continue
            d0 = rec["steps"].get("day0_%s" % channel) or {}
            if step["day"] != "day0" and d0.get("status") == "skipped":
                s.update(status="skipped", reason="no_day0")
                continue
            due = self._due_at(rec, step)
            if due is None or now < due:
                return None
            if now - due > EXPIRE_AFTER:
                s.update(status="skipped", reason="expired")
                continue
            return step
        return None

    def _channel_states(self, rec) -> dict:
        return {"email": self.email_tracker.get_prospect_state(
                    rec.get("email")) if rec.get("email") else {},
                "whatsapp": self.wa_tracker.get_prospect_state(
                    rec.get("phone_e164")) if rec.get("phone_e164") else {}}

    def _stop_reason(self, rec):
        for ch, st in self._channel_states(rec).items():
            if st.get("status") in STOP_ALL:
                return "%s_%s" % (st["status"], ch)
        return None

    def _channel_closed(self, rec, channel) -> str | None:
        st = self._channel_states(rec)[channel]
        if st.get("status") == "bounced":
            return "bounced"
        if channel == "email" and rec.get("email") and ET.is_suppressed(
                rec["email"], self.email_tracker.data_dir):
            return "suppressed"
        if channel == "whatsapp" and rec.get("phone_e164") and \
                WT.is_suppressed(rec["phone_e164"], self.wa_tracker.data_dir):
            return "suppressed"
        return None

    def stop(self, rec: dict, reason: str, now=None) -> dict:
        """Stop every channel and suppress the prospect everywhere."""
        now = now or self._now()
        rec.update(status="stopped", stop_reason=reason,
                   stopped_at=ET.iso(now))
        for s in rec["steps"].values():
            if s["status"] == "pending":
                s.update(status="skipped", reason="stopped: %s" % reason)
        if rec.get("email"):
            ET.add_to_suppression(rec["email"], "stopped: %s" % reason,
                                  self.email_tracker.data_dir, now)
        if rec.get("phone_e164"):
            WT.add_to_suppression(rec["phone_e164"], "stopped: %s" % reason,
                                  self.wa_tracker.data_dir, now)
        return rec

    def _settle(self, rec, now) -> None:
        """Close channels that can no longer send; mark completed."""
        for ch in rec["channels"]:
            why = self._channel_closed(rec, ch)
            if why:
                for step in STEPS:
                    s = rec["steps"].get(step["key"])
                    if step["channel"] == ch and s and \
                            s["status"] == "pending":
                        s.update(status="skipped", reason=why)
        if rec["status"] == "active" and all(
                s["status"] in ("sent", "skipped")
                for s in rec["steps"].values()):
            rec["status"] = "completed"

    def process_due(self, *, language_pref=None, confirmed: bool = False,
                    max_count: int = 50, now=None) -> dict:
        now = now or self._now()
        real = self._is_real(confirmed)
        limit_hit = {"email": False, "whatsapp": False}
        summary = {"checked": 0, "processed": 0, "sent": 0, "dry_run": 0,
                   "blocked": 0, "failed": 0, "stopped": 0, "completed": 0,
                   "limit_hit": limit_hit, "items": []}
        for rec in self.store.all():
            if rec.get("status") != "active":
                continue
            summary["checked"] += 1
            why = self._stop_reason(rec)
            if why:
                if real:
                    self.stop(rec, why, now)
                    self.store.put(rec)
                summary["stopped"] += 1
                continue
            self._settle(rec, now)
            for ch in rec["channels"]:
                if limit_hit[ch] or summary["processed"] >= max_count:
                    continue
                step = self._next_step(rec, ch, now)
                if not step:
                    continue
                lang = language_pref or rec.get("language") or "ar"
                r = self._send(rec, step, lang, confirmed)
                self._apply(rec, step, r, now)
                summary["processed"] += 1
                summary[r["status"]] = summary.get(r["status"], 0) + 1
                summary["items"].append({
                    "key": rec["key"], "company_name": rec.get(
                        "company_name"), "step": step["key"],
                    "template_id": r.get("template_id"),
                    "status": r["status"], "reason": r.get("reason")})
                if r.get("reason") == "daily_limit_reached":
                    limit_hit[ch] = True
            if real:
                self._settle(rec, now)
                summary["completed"] += rec["status"] == "completed"
                self.store.put(rec)
        return summary

    # ── reporting ──
    def due_counts(self, now=None) -> dict:
        now = now or self._now()
        tomorrow = ET.dubai_day(now) + timedelta(days=1)
        due_now = due_tomorrow = queue = 0
        for rec in self.store.all():
            if rec.get("status") != "active":
                continue
            for step in STEPS:
                s = rec["steps"].get(step["key"])
                if not s or s["status"] != "pending":
                    continue
                at = self._due_at(rec, step)
                if not at:
                    continue
                if at <= now:
                    due_now += 1
                    queue += step["day"] == "day0"
                elif ET.dubai_day(at) == tomorrow:
                    due_tomorrow += 1
        return {"due_now": due_now, "due_tomorrow": due_tomorrow,
                "queue": queue}

    def daily_report(self, now=None) -> dict:
        now = now or self._now()
        e = self.email_seq.daily_report(now)
        w = self.wa_seq.daily_report(now)
        today = ET.dubai_day(now)
        followups = 0
        for rows in (ET.read_sent_log(self.email_tracker.data_dir),
                     WT.read_sent_log(self.wa_tracker.data_dir)):
            for row in rows:
                at = ET.parse_iso(row.get("at"))
                if at and ET.dubai_day(at) == today and row.get(
                        "status") == "sent" and row.get("day") != "day0":
                    followups += 1
        due = self.due_counts(now)
        return {
            "date": today.isoformat(),
            "email": {k: e.get(k, 0) for k in ("sent", "dry_run", "blocked",
                                               "failed", "opens", "clicks")}
            | {"limit": self.email_sender.daily_limit,
               "replies": e.get("replies", 0)},
            "whatsapp": {"sent": w["sent"], "delivered": w["delivered"],
                         "read": w["read"], "failed": w["failed"]
                         + w["meta_failed"], "replies": w["replies"],
                         "dry_run": w["dry_run"], "blocked": w["blocked"],
                         "limit": self.wa_sender.daily_limit},
            "combined": {"replies": e.get("replies", 0) + w["replies"],
                         "unsubscribes": e.get("unsubscribes", 0)
                         + w["unsubscribes"],
                         "bounces": e.get("bounces", 0) + w["bounces"],
                         "followups_sent": followups,
                         "due_now": due["due_now"],
                         "due_tomorrow": due["due_tomorrow"],
                         "queue_remaining": due["queue"]},
        }

    def get_schedule(self, email_or_phone: str) -> list[dict]:
        rec = self.store.find(email_or_phone)
        if not rec:
            return []
        out = []
        for step in STEPS:
            applies = step["channel"] in rec["channels"]
            s = rec["steps"].get(step["key"]) or {}
            due = self._due_at(rec, step) if applies else None
            out.append({"step": step["key"], "day": step["day"],
                        "channel": step["channel"],
                        "offset_days": step["offset"],
                        "status": (s.get("status", "pending") if applies
                                   else "not_applicable"),
                        "due_at": ET.iso(due) if due else None,
                        "sent_at": s.get("at"),
                        "template_id": s.get("template_id"),
                        "reason": s.get("reason"),
                        "sequence_status": rec["status"]})
        return out
