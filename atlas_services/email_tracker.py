# -*- coding: utf-8 -*-
"""ATLAS email tracker: what was sent to whom, and what happened next.

Storage (Control_Center/data/email/, git-ignored):
  sent_log.jsonl       append-only, one line per send attempt (sent,
                       dry_run, blocked, failed)
  prospect_state.json  one record per email: sequence step, status,
                       counters and dated events
  suppression.json     emails never to contact again, with the reason

State per prospect:

    (new) --record_sent day0--> active, next_due_day=day3
    active --record_sent day3--> active, next_due_day=completed
    any --record_replied-------> replied       (suppressed)
    any --record_bounced-------> bounced       (suppressed)
    any --record_unsubscribed--> unsubscribed  (suppressed)
    opens / clicks only increment counters.

A reply that is just "STOP" (or "unsubscribe", "إلغاء") is recorded as an
unsubscribe. "Today" is the Dubai calendar day (UTC+4, no DST).
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATA_DIR = ROOT / "data" / "email"
DUBAI = timezone(timedelta(hours=4), "GST")
FOLLOWUP_AFTER = timedelta(days=3)
STOPPED = ("replied", "bounced", "unsubscribed")
STOP_WORDS = {"stop", "unsubscribe", "remove", "إلغاء", "الغاء", "توقف"}

_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,24}")


# ───────────────────────── small helpers ─────────────────────────

def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_iso(value) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def dubai_day(dt: datetime):
    return dt.astimezone(DUBAI).date()


def normalize_email(email) -> str:
    """Lower-cased email, or "" when it is not a valid address."""
    e = str(email or "").strip().strip("<>").lower()
    if e.startswith("mailto:"):
        e = e[7:].split("?")[0]
    return e if _EMAIL.fullmatch(e) else ""


def resolve_dir(data_dir=None) -> Path:
    p = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
    return p if p.is_absolute() else ROOT / p


def _read_json(path: Path, default):
    try:
        return json.loads(path.read_bytes().decode("utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(json.dumps(data, ensure_ascii=False,
                               indent=1).encode("utf-8"))
    os.replace(tmp, path)


def _parse_template_id(template_id: str) -> tuple:
    """"real_estate_ar_day0" -> ("real_estate", "ar", "day0")."""
    parts = str(template_id or "").rsplit("_", 2)
    return tuple(parts) if len(parts) == 3 else ("", "", "")


# ───────────────────────── suppression ─────────────────────────

def suppression_entries(data_dir=None) -> dict:
    """{email: {"reason", "at"}}."""
    data = _read_json(resolve_dir(data_dir) / "suppression.json", {})
    return data if isinstance(data, dict) else {}


def load_suppression(data_dir=None) -> set[str]:
    return set(suppression_entries(data_dir))


def is_suppressed(email, data_dir=None) -> bool:
    e = normalize_email(email)
    return bool(e) and e in suppression_entries(data_dir)


def add_to_suppression(email, reason: str = "manual", data_dir=None,
                       now: datetime | None = None) -> dict:
    e = normalize_email(email)
    if not e:
        return {"ok": False, "email": str(email or ""),
                "reason": "invalid_email"}
    path = resolve_dir(data_dir) / "suppression.json"
    data = suppression_entries(data_dir)
    added = e not in data
    if added:
        data[e] = {"reason": str(reason or "manual"),
                   "at": iso(now or utcnow())}
        _write_json(path, data)
    return {"ok": True, "email": e, "added": added,
            "reason": data[e]["reason"], "at": data[e]["at"]}


# ───────────────────────── sent log ─────────────────────────

def read_sent_log(data_dir=None, limit: int | None = None) -> list[dict]:
    path = resolve_dir(data_dir) / "sent_log.jsonl"
    try:
        lines = path.read_bytes().decode("utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out[-limit:] if limit else out


def get_daily_sent_count(data_dir=None, now: datetime | None = None) -> int:
    """Real sends ("sent") on today's Dubai date."""
    today = dubai_day(now or utcnow())
    n = 0
    for row in read_sent_log(data_dir):
        at = parse_iso(row.get("at"))
        if row.get("status") == "sent" and at and dubai_day(at) == today:
            n += 1
    return n


# ───────────────────────── tracker ─────────────────────────

class EmailTracker:
    def __init__(self, data_dir="data/email", *, now=None):
        self.data_dir = resolve_dir(data_dir)
        self._now = now or utcnow
        self.log_path = self.data_dir / "sent_log.jsonl"
        self.state_path = self.data_dir / "prospect_state.json"
        self.suppression_path = self.data_dir / "suppression.json"

    # storage
    def _states(self) -> dict:
        data = _read_json(self.state_path, {})
        return data if isinstance(data, dict) else {}

    def _save(self, states: dict) -> None:
        _write_json(self.state_path, states)

    @staticmethod
    def _blank(email: str) -> dict:
        return {"email": email, "company_name": "", "contact_name": "",
                "sector": "", "language": "", "last_sent_day": None,
                "last_sent_at": None, "next_due_day": None,
                "status": "active", "opens": 0, "clicks": 0, "replies": 0,
                "sends": 0, "events": []}

    def _update(self, email, fn) -> dict:
        e = normalize_email(email)
        if not e:
            return {"ok": False, "reason": "invalid_email"}
        states = self._states()
        st = dict(self._blank(e), **states.get(e, {}))
        fn(st)
        states[e] = st
        self._save(states)
        return self._public(st)

    def _event(self, st: dict, kind: str, **extra) -> None:
        st.setdefault("events", []).append(dict(
            {"type": kind, "at": iso(self._now())}, **extra))

    def _public(self, st: dict) -> dict:
        out = dict(st)
        last = parse_iso(st.get("last_sent_at"))
        out["next_due_at"] = (iso(last + FOLLOWUP_AFTER)
                              if last and st.get("next_due_day") == "day3"
                              else None)
        return out

    # recording
    def record_sent(self, prospect: dict, template_id: str,
                    result: dict) -> dict:
        """Append to the log; a real send ("sent") also moves the
        prospect's sequence state."""
        p = prospect if isinstance(prospect, dict) else {}
        r = result if isinstance(result, dict) else {}
        sector, lang, day = _parse_template_id(template_id)
        email = normalize_email(p.get("email"))
        status = r.get("status") or "failed"
        entry = {"at": r.get("sent_at") or iso(self._now()),
                 "email": email or str(p.get("email") or ""),
                 "company_name": p.get("company_name") or "",
                 "sector": p.get("sector") or sector,
                 "language": p.get("language") or lang,
                 "template_id": template_id, "day": day, "status": status,
                 "reason": r.get("reason"),
                 "message_id": r.get("message_id")}
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "ab") as f:
            f.write((json.dumps(entry, ensure_ascii=False) + "\n")
                    .encode("utf-8"))
        if status != "sent" or not email:
            return entry

        def apply(st):
            for k in ("company_name", "contact_name"):
                if p.get(k):
                    st[k] = p[k]
            st["sector"] = entry["sector"]
            st["language"] = entry["language"]
            st["last_sent_day"] = day
            st["last_sent_at"] = entry["at"]
            st["sends"] = int(st.get("sends") or 0) + 1
            st["next_due_day"] = (None if st.get("status") in STOPPED
                                  else "day3" if day == "day0"
                                  else "completed")
            self._event(st, "sent", day=day,
                        message_id=r.get("message_id"))
        return dict(entry, state=self._update(email, apply))

    def record_opened(self, email, message_id: str = "") -> dict:
        def apply(st):
            st["opens"] = int(st.get("opens") or 0) + 1
            self._event(st, "opened", message_id=message_id)
        return self._update(email, apply)

    def record_clicked(self, email, url: str = "") -> dict:
        def apply(st):
            st["clicks"] = int(st.get("clicks") or 0) + 1
            self._event(st, "clicked", url=url)
        return self._update(email, apply)

    def _stop(self, email, status: str, reason: str, counter=None) -> dict:
        def apply(st):
            st["status"] = status
            st["next_due_day"] = None
            if counter:
                st[counter] = int(st.get(counter) or 0) + 1
            self._event(st, status, reason=reason)
        out = self._update(email, apply)
        if out.get("email"):
            add_to_suppression(email, reason, self.data_dir, self._now())
        return out

    def record_replied(self, email, reply_text: str = "") -> dict:
        first = next((ln.strip() for ln in str(reply_text or "")
                      .splitlines() if ln.strip()), "")
        if first.lower().strip(" .!") in STOP_WORDS:
            return self.record_unsubscribed(email, "replied STOP")
        return self._stop(email, "replied", "replied", "replies")

    def record_bounced(self, email, reason: str = "") -> dict:
        return self._stop(email, "bounced",
                          "bounced" + (": %s" % reason if reason else ""))

    def record_unsubscribed(self, email, reason: str = "manual") -> dict:
        return self._stop(email, "unsubscribed",
                          "unsubscribed: %s" % (reason or "manual"))

    # reading
    def get_prospect_state(self, email: str) -> dict:
        e = normalize_email(email)
        st = self._states().get(e) if e else None
        return self._public(dict(self._blank(e), **(st or {})))

    def all_states(self) -> list[dict]:
        return [self._public(dict(self._blank(e), **st))
                for e, st in self._states().items()]

    def get_due_followups(self, now: datetime | None = None) -> list[dict]:
        """Active prospects whose day0 went out at least 3 days ago and who
        have not had day3 yet. Suppressed emails are never due."""
        now = now or self._now()
        suppressed = load_suppression(self.data_dir)
        due = []
        for st in self.all_states():
            last = parse_iso(st.get("last_sent_at"))
            if (st.get("status") == "active"
                    and st.get("next_due_day") == "day3"
                    and st.get("last_sent_day") == "day0"
                    and st["email"] not in suppressed
                    and last and now - last >= FOLLOWUP_AFTER):
                due.append(st)
        return sorted(due, key=lambda s: s["last_sent_at"])

    def events_on(self, day) -> dict:
        """Counts of each event type on a Dubai calendar day."""
        out = {}
        for st in self._states().values():
            for ev in st.get("events") or []:
                at = parse_iso(ev.get("at"))
                if at and dubai_day(at) == day:
                    out[ev.get("type")] = out.get(ev.get("type"), 0) + 1
        return out
