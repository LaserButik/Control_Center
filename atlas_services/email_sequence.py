# -*- coding: utf-8 -*-
"""ATLAS email sequence: walks a prospect through day0 -> day3.

It sends nothing by itself. It picks and renders the template, hands the
message to EmailSender (which applies every gate: compliance, dry_run,
confirmed, daily limit) and records each attempt with EmailTracker. A
scheduler can call process_due_followups() later; nothing here runs on a
timer.
"""

from __future__ import annotations

from datetime import timedelta

from atlas_services import email_templates as _templates
from atlas_services import email_tracker as ET


class EmailSequence:
    def __init__(self, sender, tracker, templates_module=None):
        self.sender = sender
        self.tracker = tracker
        self.T = templates_module or _templates

    def _render(self, step: int, prospect: dict, language: str):
        sector = (prospect or {}).get("sector")
        if sector not in self.T.TEMPLATES:
            return None, None, "unknown_sector"
        if language not in self.T.TEMPLATES[sector]:
            return None, None, "unknown_language"
        tpl = self.T.get_sequence(sector, language)[step]
        return tpl, self.T.render(tpl, prospect), None

    def preview(self, prospect: dict, *, day: str = "day0",
                language: str = "ar") -> dict:
        """The exact email that start()/process_due_followups() would
        send — no gate, no record."""
        tpl, rendered, why = self._render(0 if day == "day0" else 1,
                                          prospect, language)
        return {"ok": why is None, "reason": why,
                "template_id": tpl["id"] if tpl else None,
                **(rendered or {})}

    def _send(self, prospect, tpl_id, rendered, confirmed, language):
        result = self.sender.send(prospect, rendered, template_id=tpl_id,
                                  confirmed=confirmed)
        self.tracker.record_sent(dict(prospect, language=language), tpl_id,
                                 result)
        return result

    def _blocked(self, prospect, tpl_id, reason, language):
        result = {"ok": False, "status": "blocked", "reason": reason,
                  "message_id": None, "sent_at": None,
                  "email": ET.normalize_email(prospect.get("email")),
                  "template_id": tpl_id}
        self.tracker.record_sent(dict(prospect, language=language),
                                 tpl_id or "", result)
        return result

    def start(self, prospect: dict, *, language: str = "ar",
              confirmed: bool = False) -> dict:
        """The day0 email for the prospect's sector. A prospect who already
        had day0 is not started again."""
        p = dict(prospect or {})
        tpl, rendered, why = self._render(0, p, language)
        tpl_id = tpl["id"] if tpl else ""
        state = self.tracker.get_prospect_state(p.get("email"))
        if why is None and state.get("last_sent_day"):
            why = "already_started"
        result = (self._blocked(p, tpl_id, why, language) if why
                  else self._send(p, tpl_id, rendered, confirmed, language))
        return {"email": result["email"], "template_id": tpl_id,
                "subject": (rendered or {}).get("subject"),
                "rendered": rendered, "result": result,
                "state": self.tracker.get_prospect_state(p.get("email"))}

    def process_due_followups(self, *, language_pref=None,
                              confirmed: bool = False, max_count: int = 25,
                              now=None) -> dict:
        """day3 for every prospect whose follow-up is due. Stops at the
        daily limit."""
        due = self.tracker.get_due_followups(now)
        summary = {"due": len(due), "processed": 0, "sent": 0, "dry_run": 0,
                   "blocked": 0, "failed": 0, "stopped_at_daily_limit": False,
                   "items": []}
        for st in due[:max(0, int(max_count))]:
            lang = language_pref or st.get("language") or "ar"
            p = {"email": st["email"], "company_name": st.get("company_name"),
                 "contact_name": st.get("contact_name"),
                 "sector": st.get("sector")}
            tpl, rendered, why = self._render(1, p, lang)
            tpl_id = tpl["id"] if tpl else ""
            result = (self._blocked(p, tpl_id, why, lang) if why
                      else self._send(p, tpl_id, rendered, confirmed, lang))
            summary["processed"] += 1
            summary[result["status"]] = summary.get(result["status"], 0) + 1
            summary["items"].append({
                "email": st["email"], "company_name": st.get("company_name"),
                "template_id": tpl_id,
                "subject": (rendered or {}).get("subject"),
                "status": result["status"], "reason": result["reason"]})
            if result["reason"] == "daily_limit_reached":
                summary["stopped_at_daily_limit"] = True
                break
        return summary

    def daily_report(self, now=None) -> dict:
        """Today's totals (Dubai calendar day)."""
        now = now or self.sender._now()
        today = ET.dubai_day(now)
        rep = {"sent": 0, "dry_run": 0, "blocked": 0, "failed": 0}
        for row in ET.read_sent_log(self.tracker.data_dir):
            at = ET.parse_iso(row.get("at"))
            if at and ET.dubai_day(at) == today and row.get("status") in rep:
                rep[row["status"]] += 1
        ev = self.tracker.events_on(today)
        tomorrow = today + timedelta(days=1)
        due_tomorrow = 0
        for st in self.tracker.all_states():
            at = ET.parse_iso(st.get("next_due_at"))
            if st.get("status") == "active" and at and \
                    ET.dubai_day(at) == tomorrow:
                due_tomorrow += 1
        rep.update({"opens": ev.get("opened", 0),
                    "clicks": ev.get("clicked", 0),
                    "replies": ev.get("replied", 0),
                    "unsubscribes": ev.get("unsubscribed", 0),
                    "bounces": ev.get("bounced", 0),
                    "due_now": len(self.tracker.get_due_followups(now)),
                    "due_tomorrow": due_tomorrow,
                    "daily_limit": self.sender.daily_limit,
                    "remaining": max(0, self.sender.daily_limit
                                     - rep["sent"])})
        return rep
