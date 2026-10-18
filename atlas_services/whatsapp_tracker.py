# -*- coding: utf-8 -*-
"""ATLAS WhatsApp tracker — the EmailTracker shape, keyed by phone_e164.

Storage (Control_Center/data/whatsapp/, git-ignored):
  sent_log.jsonl       append-only, one line per send attempt
  prospect_state.json  one record per phone
  suppression.json     phones never to message again, with the reason
  webhooks/            Meta webhook payloads dropped here as *.json are
                       processed by record_webhook (scheduler step 6)

State per prospect:
    (new) --sent day0--> active, next_due_day=day2
    active --sent day2--> active, next_due_day=completed
    any --replied / bounced / unsubscribed--> stopped + suppressed
    delivered / read / failed only update counters.
A reply that is just "STOP" (or "إلغاء") is an unsubscribe. A Meta
failure with code 131026 (undeliverable: not on WhatsApp) is a bounce.
"""

from __future__ import annotations

import json
import re
from datetime import timedelta
from pathlib import Path

from atlas_services import email_tracker as ET

ROOT = ET.ROOT
DEFAULT_DATA_DIR = ROOT / "data" / "whatsapp"
FOLLOWUP_AFTER = timedelta(days=2)
STOPPED = ET.STOPPED
UNDELIVERABLE_CODES = {131026}

_E164 = re.compile(r"^\+\d{10,15}$")


def normalize_phone(phone) -> str:
    """"+971 50 123 4567" / "00971501234567" -> "+971501234567"; "" when
    it is not an international number."""
    s = re.sub(r"[\s\-().‎‏]", "", str(phone or ""))
    if s.lower().startswith("tel:"):
        s = s[4:]
    if s.startswith("00"):
        s = "+" + s[2:]
    if not s.startswith("+") and s.isdigit() and s[:3] in ("971", "966"):
        s = "+" + s
    return s if _E164.match(s) else ""


def resolve_dir(data_dir=None) -> Path:
    p = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
    return p if p.is_absolute() else ROOT / p


# ───────────────────────── suppression ─────────────────────────

def suppression_entries(data_dir=None) -> dict:
    data = ET._read_json(resolve_dir(data_dir) / "suppression.json", {})
    return data if isinstance(data, dict) else {}


def load_suppression(data_dir=None) -> set[str]:
    return set(suppression_entries(data_dir))


def is_suppressed(phone, data_dir=None) -> bool:
    p = normalize_phone(phone)
    return bool(p) and p in suppression_entries(data_dir)


def add_to_suppression(phone, reason: str = "manual", data_dir=None,
                       now=None) -> dict:
    p = normalize_phone(phone)
    if not p:
        return {"ok": False, "phone": str(phone or ""),
                "reason": "invalid_phone"}
    data = suppression_entries(data_dir)
    added = p not in data
    if added:
        data[p] = {"reason": str(reason or "manual"),
                   "at": ET.iso(now or ET.utcnow())}
        ET._write_json(resolve_dir(data_dir) / "suppression.json", data)
    return {"ok": True, "phone": p, "added": added,
            "reason": data[p]["reason"], "at": data[p]["at"]}


# ───────────────────────── sent log ─────────────────────────

def read_sent_log(data_dir=None, limit: int | None = None) -> list[dict]:
    return ET.read_sent_log(resolve_dir(data_dir), limit)


def get_daily_sent_count(data_dir=None, now=None) -> int:
    return ET.get_daily_sent_count(resolve_dir(data_dir), now)


def parse_template_id(template_id: str) -> tuple:
    """"wa_real_estate_ar_day2" -> ("real_estate", "ar", "day2")."""
    tid = str(template_id or "")
    if tid.startswith("wa_"):
        tid = tid[3:]
    return ET._parse_template_id(tid)


# ───────────────────────── tracker ─────────────────────────

class WhatsAppTracker:
    def __init__(self, data_dir="data/whatsapp", *, now=None):
        self.data_dir = resolve_dir(data_dir)
        self._now = now or ET.utcnow
        self.log_path = self.data_dir / "sent_log.jsonl"
        self.state_path = self.data_dir / "prospect_state.json"
        self.suppression_path = self.data_dir / "suppression.json"
        self.webhook_dir = self.data_dir / "webhooks"

    def _states(self) -> dict:
        data = ET._read_json(self.state_path, {})
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _blank(phone: str) -> dict:
        return {"phone": phone, "company_name": "", "sector": "",
                "language": "", "email": "", "last_sent_day": None,
                "last_sent_at": None, "next_due_day": None,
                "status": "active", "sends": 0, "delivered": 0, "read": 0,
                "failed": 0, "replies": 0, "message_ids": [], "events": []}

    def _update(self, phone, fn) -> dict:
        p = normalize_phone(phone)
        if not p:
            return {"ok": False, "reason": "invalid_phone"}
        states = self._states()
        st = dict(self._blank(p), **states.get(p, {}))
        fn(st)
        states[p] = st
        ET._write_json(self.state_path, states)
        return self._public(st)

    def _event(self, st, kind, **extra):
        st.setdefault("events", []).append(dict(
            {"type": kind, "at": ET.iso(self._now())}, **extra))

    def _public(self, st: dict) -> dict:
        out = dict(st)
        last = ET.parse_iso(st.get("last_sent_at"))
        out["next_due_at"] = (ET.iso(last + FOLLOWUP_AFTER)
                              if last and st.get("next_due_day") == "day2"
                              else None)
        return out

    # recording
    def record_sent(self, prospect: dict, template_id: str,
                    result: dict) -> dict:
        p = prospect if isinstance(prospect, dict) else {}
        r = result if isinstance(result, dict) else {}
        sector, lang, day = parse_template_id(template_id)
        phone = normalize_phone(p.get("phone_e164") or p.get("phone"))
        status = r.get("status") or "failed"
        entry = {"at": r.get("sent_at") or ET.iso(self._now()),
                 "phone": phone or str(p.get("phone_e164") or ""),
                 "company_name": p.get("company_name") or "",
                 "sector": p.get("sector") or sector,
                 "language": p.get("language") or lang,
                 "template_id": template_id,
                 "template_name": r.get("template_name"), "day": day,
                 "status": status, "reason": r.get("reason"),
                 "message_id": r.get("message_id")}
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.log_path, "ab") as f:
            f.write((json.dumps(entry, ensure_ascii=False) + "\n")
                    .encode("utf-8"))
        if status != "sent" or not phone:
            return entry

        def apply(st):
            for k in ("company_name", "email"):
                if p.get(k):
                    st[k] = p[k]
            st["sector"] = entry["sector"]
            st["language"] = entry["language"]
            st["last_sent_day"] = day
            st["last_sent_at"] = entry["at"]
            st["sends"] = int(st.get("sends") or 0) + 1
            if r.get("message_id"):
                st.setdefault("message_ids", []).append(r["message_id"])
            st["next_due_day"] = (None if st.get("status") in STOPPED
                                  else "day2" if day == "day0"
                                  else "completed")
            self._event(st, "sent", day=day, message_id=r.get("message_id"))
        return dict(entry, state=self._update(phone, apply))

    def _count(self, phone, field, kind, **extra) -> dict:
        def apply(st):
            st[field] = int(st.get(field) or 0) + 1
            self._event(st, kind, **extra)
        return self._update(phone, apply)

    def record_delivered(self, phone, message_id: str = "") -> dict:
        return self._count(phone, "delivered", "delivered",
                           message_id=message_id)

    def record_read(self, phone, message_id: str = "") -> dict:
        return self._count(phone, "read", "read", message_id=message_id)

    def record_failed(self, phone, reason: str = "", code=None) -> dict:
        if code is not None and int(code) in UNDELIVERABLE_CODES:
            return self.record_bounced(phone, "meta %s: %s" % (code, reason))
        return self._count(phone, "failed", "failed", reason=reason,
                           code=code)

    def _stop(self, phone, status, reason, counter=None) -> dict:
        def apply(st):
            st["status"] = status
            st["next_due_day"] = None
            if counter:
                st[counter] = int(st.get(counter) or 0) + 1
            self._event(st, status, reason=reason)
        out = self._update(phone, apply)
        if out.get("phone"):
            add_to_suppression(phone, reason, self.data_dir, self._now())
        return out

    def record_replied(self, phone, reply_text: str = "") -> dict:
        first = next((ln.strip() for ln in str(reply_text or "")
                      .splitlines() if ln.strip()), "")
        if first.lower().strip(" .!") in ET.STOP_WORDS:
            return self.record_unsubscribed(phone, "replied STOP")
        return self._stop(phone, "replied", "replied", "replies")

    def record_bounced(self, phone, reason: str = "") -> dict:
        return self._stop(phone, "bounced",
                          "bounced" + (": %s" % reason if reason else ""))

    def record_unsubscribed(self, phone, reason: str = "manual") -> dict:
        return self._stop(phone, "unsubscribed",
                          "unsubscribed: %s" % (reason or "manual"))

    def record_webhook(self, payload: dict) -> dict:
        """A Meta webhook body: incoming messages become replies; statuses
        update delivered / read / failed. Returns what was recorded."""
        out = {"messages": 0, "replies": [], "delivered": 0, "read": 0,
               "failed": 0, "bounced": 0, "ignored": 0}
        try:
            entries = (payload or {}).get("entry") or []
        except AttributeError:
            return dict(out, error="not_a_webhook_payload")
        for entry in entries:
            for change in (entry or {}).get("changes") or []:
                value = (change or {}).get("value") or {}
                for msg in value.get("messages") or []:
                    phone = normalize_phone("+" + str(msg.get("from", "")))
                    text = ((msg.get("text") or {}).get("body")
                            or (msg.get("button") or {}).get("text") or "")
                    if not phone:
                        out["ignored"] += 1
                        continue
                    st = self.record_replied(phone, text)
                    out["messages"] += 1
                    out["replies"].append({"phone": phone,
                                           "status": st.get("status"),
                                           "text": text[:200]})
                for s in value.get("statuses") or []:
                    phone = normalize_phone("+" + str(s.get("recipient_id",
                                                            "")))
                    kind, mid = s.get("status"), s.get("id", "")
                    if not phone:
                        out["ignored"] += 1
                    elif kind == "delivered":
                        self.record_delivered(phone, mid)
                        out["delivered"] += 1
                    elif kind == "read":
                        self.record_read(phone, mid)
                        out["read"] += 1
                    elif kind == "failed":
                        err = (s.get("errors") or [{}])[0]
                        st = self.record_failed(phone, err.get("title", ""),
                                                err.get("code"))
                        out["bounced" if st.get("status") == "bounced"
                            else "failed"] += 1
                    else:
                        out["ignored"] += 1
        return out

    def process_webhook_folder(self) -> dict:
        """Every *.json in webhooks/ through record_webhook, then moved to
        webhooks/processed/."""
        total = {"files": 0, "replies": [], "delivered": 0, "read": 0,
                 "failed": 0, "bounced": 0, "errors": []}
        if not self.webhook_dir.is_dir():
            return total
        done = self.webhook_dir / "processed"
        for f in sorted(self.webhook_dir.glob("*.json")):
            try:
                payload = json.loads(f.read_bytes().decode("utf-8"))
            except (OSError, ValueError) as e:
                total["errors"].append("%s: %s" % (f.name, type(e).__name__))
                continue
            r = self.record_webhook(payload)
            total["files"] += 1
            total["replies"] += r["replies"]
            for k in ("delivered", "read", "failed", "bounced"):
                total[k] += r[k]
            done.mkdir(parents=True, exist_ok=True)
            f.replace(done / f.name)
        return total

    # reading
    def get_prospect_state(self, phone) -> dict:
        p = normalize_phone(phone)
        st = self._states().get(p) if p else None
        return self._public(dict(self._blank(p), **(st or {})))

    def all_states(self) -> list[dict]:
        return [self._public(dict(self._blank(k), **v))
                for k, v in self._states().items()]

    def get_due_followups(self, now=None) -> list[dict]:
        now = now or self._now()
        suppressed = load_suppression(self.data_dir)
        due = []
        for st in self.all_states():
            last = ET.parse_iso(st.get("last_sent_at"))
            if (st.get("status") == "active"
                    and st.get("next_due_day") == "day2"
                    and st.get("last_sent_day") == "day0"
                    and st["phone"] not in suppressed
                    and last and now - last >= FOLLOWUP_AFTER):
                due.append(st)
        return sorted(due, key=lambda s: s["last_sent_at"])

    def events_on(self, day) -> dict:
        out = {}
        for st in self._states().values():
            for ev in st.get("events") or []:
                at = ET.parse_iso(ev.get("at"))
                if at and ET.dubai_day(at) == day:
                    out[ev.get("type")] = out.get(ev.get("type"), 0) + 1
        return out
