# -*- coding: utf-8 -*-
"""ATLAS WhatsApp sender: one template message at a time through Meta's
Cloud API, behind the same gates as the email sender.

  1. compliance  an E.164 mobile in AE (+9715X) or SA (+9665X), country
                 AE/SA, not suppressed, not replied / bounced /
                 unsubscribed, under the daily limit, not messaged in the
                 last 20 hours, not twice in one batch, a company name
  2. approval    the template name must be on the approved list
                 (WHATSAPP_APPROVED_TEMPLATES, comma separated; default
                 "alpha_intro_v1_en"). A day0 template that is not yet
                 approved falls back to WHATSAPP_DAY0_FALLBACK (default
                 "alpha_intro_v1_en:en", the template outreach/ already
                 uses, with two parameters: company name and industry).
                 Set WHATSAPP_DAY0_FALLBACK=none to turn that off.
  3. dry_run     True by default
  4. confirmed   False by default; a real send needs both

Credentials come from the environment only — the SAME Meta account as
outreach/, read independently (outreach/ is never imported):
  WHATSAPP_PHONE_ID, WHATSAPP_TOKEN, META_GRAPH_VERSION (v22.0).
The token is never logged, printed, returned or written; error text is
scrubbed of it.

WhatsAppSequence (day0 -> day2) mirrors EmailSequence and is used by the
WhatsApp page and the unified sequence.
"""

from __future__ import annotations

import logging
import os
import re
import time
from datetime import timedelta

from atlas_services import email_tracker as ET
from atlas_services import whatsapp_templates as _templates
from atlas_services import whatsapp_tracker as WT
from atlas_services.email_templates import INDUSTRY

try:
    import requests
except ImportError:                                  # pragma: no cover
    requests = None

log = logging.getLogger(__name__)

GRAPH_URL = "https://graph.facebook.com/%s/%s/messages"
MAX_DAILY_LIMIT = 20
RESEND_WINDOW = timedelta(hours=20)
DEFAULT_APPROVED = "alpha_intro_v1_en"
DEFAULT_FALLBACK = "alpha_intro_v1_en:en"
ALLOWED_COUNTRIES = {"AE", "SA"}
_MOBILE = {"AE": re.compile(r"^\+9715[024568]\d{7}$"),
           "SA": re.compile(r"^\+9665\d{8}$")}
_PREFIX = {"+971": "AE", "+966": "SA"}


# ───────────────────────── module helpers ─────────────────────────

def load_suppression(data_dir=None) -> set[str]:
    return WT.load_suppression(data_dir)


def add_to_suppression(phone, reason="manual", data_dir=None) -> dict:
    return WT.add_to_suppression(phone, reason, data_dir)


def is_suppressed(phone, data_dir=None) -> bool:
    return WT.is_suppressed(phone, data_dir)


def get_daily_sent_count(data_dir=None, now=None) -> int:
    return WT.get_daily_sent_count(data_dir, now)


def phone_country(phone) -> str | None:
    p = WT.normalize_phone(phone)
    return next((c for pre, c in _PREFIX.items() if p.startswith(pre)), None)


def is_mobile(phone) -> bool:
    p = WT.normalize_phone(phone)
    c = phone_country(p)
    return bool(c and _MOBILE[c].match(p))


def mask_phone(phone: str) -> str:
    p = str(phone or "")
    return p[:5] + "*" * max(0, len(p) - 8) + p[-3:] if len(p) > 8 else "***"


def _default_http_post(url, headers, body, timeout):
    if requests is None:
        raise RuntimeError("requests not installed")
    r = requests.post(url, headers=headers, json=body, timeout=timeout)
    try:
        data = r.json() if r.content else {}
    except ValueError:
        data = {}
    return r.status_code, data


def _approved_from_env() -> set[str]:
    raw = os.getenv("WHATSAPP_APPROVED_TEMPLATES")
    names = raw if raw is not None else DEFAULT_APPROVED
    return {n.strip() for n in names.split(",") if n.strip()}


def _fallback_from_env():
    raw = os.getenv("WHATSAPP_DAY0_FALLBACK", DEFAULT_FALLBACK).strip()
    if not raw or raw.lower() == "none":
        return None
    name, _, lang = raw.partition(":")
    return name.strip(), (lang.strip() or "en")


# ───────────────────────── sender ─────────────────────────

class WhatsAppSender:
    def __init__(self, *, phone_id=None, access_token=None, api_version=None,
                 daily_limit=None, delay_between_sends_s=30.0,
                 dry_run=True, http_post=None, tracker=None, now=None,
                 sleep=time.sleep, clock=time.monotonic,
                 approved_templates=None, day0_fallback="env"):
        env = os.environ
        self.phone_id = (phone_id if phone_id is not None
                         else env.get("WHATSAPP_PHONE_ID", "")).strip()
        self.__token = (access_token if access_token is not None
                        else env.get("WHATSAPP_TOKEN", "")).strip()
        self.api_version = (api_version or env.get("META_GRAPH_VERSION")
                            or "v22.0").strip()
        if daily_limit is None:                 # settings.json, else 20
            from atlas_services.email_sender import _settings_limit
            daily_limit = _settings_limit("daily_whatsapp_limit",
                                          MAX_DAILY_LIMIT)
        self.daily_limit = max(0, min(int(daily_limit), MAX_DAILY_LIMIT))
        self.delay_between_sends_s = max(0.0, float(delay_between_sends_s))
        self.dry_run = bool(dry_run)
        self._post = http_post or _default_http_post
        self.tracker = tracker or WT.WhatsAppTracker(now=now)
        self._now = now or ET.utcnow
        self._sleep, self._clock = sleep, clock
        self.approved = (set(approved_templates) if approved_templates
                         is not None else _approved_from_env())
        self.day0_fallback = (_fallback_from_env() if day0_fallback == "env"
                              else day0_fallback)
        self._last_send = None
        self._session_sent = 0
        self._session_dry = 0
        self._seen = {"dry": {}, "real": {}}

    def __repr__(self):
        return ("WhatsAppSender(phone_id_set=%r, token_set=%r, version=%r, "
                "dry_run=%r)" % (bool(self.phone_id), bool(self.__token),
                                 self.api_version, self.dry_run))

    def config_summary(self) -> dict:
        return {"phone_id_set": bool(self.phone_id),
                "token_set": bool(self.__token),
                "api_version": self.api_version,
                "approved_templates": sorted(self.approved),
                "day0_fallback": ("%s:%s" % self.day0_fallback
                                  if self.day0_fallback else None),
                "daily_limit": self.daily_limit}

    def is_configured(self) -> bool:
        return bool(self.phone_id and self.__token)

    def _scrub(self, text) -> str:
        text = str(text or "")
        for secret in (self.__token, self.phone_id):
            if secret:
                text = text.replace(secret, "***")
        return text

    def _roll_day(self) -> None:
        """Session counters belong to one Dubai day; a sender that lives
        past midnight starts the new day at zero."""
        day = ET.dubai_day(self._now())
        if day != getattr(self, "_session_day", None):
            self._session_day = day
            self._session_sent = self._session_dry = 0

    def sent_today(self) -> int:
        self._roll_day()
        logged = WT.get_daily_sent_count(self.tracker.data_dir, self._now())
        return max(logged, self._session_sent)

    def remaining_today(self, real: bool = False) -> int:
        used = self.sent_today() + (0 if real else self._session_dry)
        return max(0, self.daily_limit - used)

    # ── gates ──
    def _check_compliance(self, prospect, *, real: bool = False) -> tuple:
        p = prospect if isinstance(prospect, dict) else {}
        phone = WT.normalize_phone(p.get("phone_e164") or p.get("phone"))
        if not phone:
            return False, "invalid_phone"
        pc = phone_country(phone)
        country = str(p.get("country") or pc or "").upper()
        if country not in ALLOWED_COUNTRIES or pc not in ALLOWED_COUNTRIES:
            return False, "country_not_allowed"
        if country != pc:
            return False, "country_mismatch"
        if not _MOBILE[pc].match(phone):
            return False, "not_mobile"
        if WT.is_suppressed(phone, self.tracker.data_dir):
            return False, "suppressed"
        state = self.tracker.get_prospect_state(phone)
        for status in (str(p.get("status") or "").lower(),
                       state.get("status")):
            if status in STOPPED:
                return False, "status_%s" % status
        if self.remaining_today(real) <= 0:
            return False, "daily_limit_reached"
        seen = self._seen["real" if real else "dry"].get(phone)
        if seen and self._now() - seen < RESEND_WINDOW:
            return False, "duplicate_in_batch"
        last = ET.parse_iso(state.get("last_sent_at"))
        if last and self._now() - last < RESEND_WINDOW:
            return False, "sent_within_20h"
        return True, None

    def resolve_template(self, template: dict, prospect: dict) -> dict:
        """The Meta name, language and parameters that would be sent —
        the template itself if approved, the day0 fallback if not."""
        t = template or {}
        r = _templates.render(t, prospect)
        r.update(fallback=False, approved=r["template_name"] in self.approved)
        if r["approved"]:
            return r
        if t.get("day") == "day0" and self.day0_fallback and \
                self.day0_fallback[0] in self.approved:
            name, lang = self.day0_fallback
            sector = (prospect or {}).get("sector") or t.get("sector")
            industry = (str((prospect or {}).get("industry") or "").strip()
                        or INDUSTRY.get(sector, {}).get("en", "business"))
            r.update(template_name=name, language=lang, fallback=True,
                     approved=True,
                     variables=[r["variables"][0],
                                {"type": "text", "text": " ".join(
                                    industry.split())[:60]}],
                     preview="(approved template %s with: %s, %s)" % (
                         name, r["variables"][0]["text"], industry))
        return r

    @staticmethod
    def _result(ok, status, reason=None, message_id=None, sent_at=None,
                wa_id=None, **extra) -> dict:
        return dict({"ok": ok, "status": status, "reason": reason,
                     "message_id": message_id, "sent_at": sent_at,
                     "wa_id": wa_id}, **extra)

    def send(self, prospect: dict, template: dict, *,
             confirmed: bool = False) -> dict:
        p = prospect if isinstance(prospect, dict) else {}
        phone = WT.normalize_phone(p.get("phone_e164") or p.get("phone"))
        t = template or {}
        extra = {"phone": phone or str(p.get("phone_e164") or ""),
                 "template_id": t.get("id", ""),
                 "template_name": t.get("name", "")}
        real = not self.dry_run and bool(confirmed)
        ok, why = self._check_compliance(p, real=real)
        if not ok:
            log.info("[whatsapp] blocked %s (%s) template=%s",
                     mask_phone(phone), why, extra["template_id"])
            return self._result(False, "blocked", why, **extra)
        if not _templates.company_param(p):
            return self._result(False, "blocked", "missing_company_name",
                                **extra)
        msg = self.resolve_template(t, p)
        extra.update(template_name=msg["template_name"],
                     fallback=msg["fallback"])
        if not msg["approved"]:
            return self._result(False, "blocked", "template_not_approved",
                                **extra)
        if not real:
            self._session_dry += 1
            self._seen["dry"][phone] = self._now()
            return self._result(True, "dry_run", "dry_run" if self.dry_run
                                else "not_confirmed", **extra)
        if not self.is_configured():
            return self._result(False, "failed", "whatsapp_not_configured",
                                **extra)
        if self._last_send is not None:
            wait = self.delay_between_sends_s - (self._clock()
                                                 - self._last_send)
            if wait > 0:
                self._sleep(wait)
        try:
            info = self._send_meta(phone, msg["template_name"],
                                   msg["language"], msg["variables"])
        except Exception as e:                        # noqa: BLE001
            self._last_send = self._clock()
            reason = self._scrub("meta_error:%s: %s" % (type(e).__name__, e))
            log.warning("[whatsapp] failed %s: %s", mask_phone(phone), reason)
            return self._result(False, "failed", reason[:300], **extra)
        self._last_send = self._clock()
        self._session_sent += 1
        self._seen["real"][phone] = self._now()
        log.info("[whatsapp] sent %s template=%s", mask_phone(phone),
                 msg["template_name"])
        return self._result(True, "sent", None, info.get("message_id"),
                            ET.iso(self._now()), info.get("wa_id"), **extra)

    def _send_meta(self, phone, template_name, language, variables) -> dict:
        """POST /{version}/{phone_id}/messages. Raises MetaError on an
        error answer."""
        url = GRAPH_URL % (self.api_version, self.phone_id)
        body = {"messaging_product": "whatsapp", "to": phone.lstrip("+"),
                "type": "template",
                "template": {"name": template_name,
                             "language": {"code": language},
                             "components": [{"type": "body",
                                             "parameters": list(variables)}]}}
        status, data = self._post(url, {"Authorization": "Bearer %s"
                                        % self.__token,
                                        "Content-Type": "application/json"},
                                  body, 20)
        data = data or {}
        if not 200 <= int(status) < 300:
            err = data.get("error") or {}
            raise MetaError("http %s, code %s: %s" % (
                status, err.get("code"), self._scrub(err.get("message"))))
        return {"message_id": ((data.get("messages") or [{}])[0]).get("id"),
                "wa_id": ((data.get("contacts") or [{}])[0]).get("wa_id")}


class MetaError(RuntimeError):
    pass


STOPPED = WT.STOPPED


# ───────────────────────── sequence (day0 -> day2) ─────────────────────

class WhatsAppSequence:
    def __init__(self, sender, tracker, templates_module=None):
        self.sender = sender
        self.tracker = tracker
        self.T = templates_module or _templates

    def _template(self, step: int, prospect: dict, language: str):
        sector = (prospect or {}).get("sector")
        if sector not in self.T.TEMPLATES:
            return None, "unknown_sector"
        if language not in self.T.TEMPLATES[sector]:
            return None, "unknown_language"
        return self.T.get_sequence(sector, language)[step], None

    def preview(self, prospect: dict, *, day: str = "day0",
                language: str = "ar") -> dict:
        tpl, why = self._template(0 if day == "day0" else 1, prospect,
                                  language)
        if not tpl:
            return {"ok": False, "reason": why}
        msg = self.sender.resolve_template(tpl, prospect)
        return dict(msg, ok=True, reason=None, body=tpl["body"],
                    text=self.T.preview_text(tpl, prospect))

    def _record(self, prospect, tpl_id, result, language):
        self.tracker.record_sent(dict(prospect, language=language), tpl_id,
                                 result)

    def start(self, prospect: dict, *, language: str = "ar",
              confirmed: bool = False) -> dict:
        p = dict(prospect or {})
        tpl, why = self._template(0, p, language)
        tpl_id = tpl["id"] if tpl else ""
        phone = WT.normalize_phone(p.get("phone_e164") or p.get("phone"))
        if not why and self.tracker.get_prospect_state(phone).get(
                "last_sent_day"):
            why = "already_started"
        if why:
            result = WhatsAppSender._result(False, "blocked", why,
                                            phone=phone, template_id=tpl_id)
        else:
            result = self.sender.send(p, tpl, confirmed=confirmed)
        self._record(p, tpl_id, result, language)
        return {"phone": phone, "template_id": tpl_id, "result": result,
                "state": self.tracker.get_prospect_state(phone)}

    def process_due_followups(self, *, language_pref=None,
                              confirmed: bool = False, max_count: int = 20,
                              now=None) -> dict:
        due = self.tracker.get_due_followups(now)
        summary = {"due": len(due), "processed": 0, "sent": 0, "dry_run": 0,
                   "blocked": 0, "failed": 0, "stopped_at_daily_limit": False,
                   "items": []}
        for st in due[:max(0, int(max_count))]:
            lang = language_pref or st.get("language") or "ar"
            p = {"phone_e164": st["phone"], "company_name":
                 st.get("company_name"), "sector": st.get("sector")}
            tpl, why = self._template(1, p, lang)
            tpl_id = tpl["id"] if tpl else ""
            result = (WhatsAppSender._result(False, "blocked", why,
                                             phone=st["phone"],
                                             template_id=tpl_id)
                      if why else self.sender.send(p, tpl,
                                                   confirmed=confirmed))
            self._record(p, tpl_id, result, lang)
            summary["processed"] += 1
            summary[result["status"]] = summary.get(result["status"], 0) + 1
            summary["items"].append({
                "phone": st["phone"], "company_name": st.get("company_name"),
                "template_id": tpl_id,
                "template_name": result.get("template_name"),
                "status": result["status"], "reason": result["reason"]})
            if result["reason"] == "daily_limit_reached":
                summary["stopped_at_daily_limit"] = True
                break
        return summary

    def daily_report(self, now=None) -> dict:
        now = now or self.sender._now()
        today = ET.dubai_day(now)
        rep = {"sent": 0, "dry_run": 0, "blocked": 0, "failed": 0}
        for row in WT.read_sent_log(self.tracker.data_dir):
            at = ET.parse_iso(row.get("at"))
            if at and ET.dubai_day(at) == today and row.get("status") in rep:
                rep[row["status"]] += 1
        ev = self.tracker.events_on(today)
        rep.update({"delivered": ev.get("delivered", 0),
                    "read": ev.get("read", 0),
                    "replies": ev.get("replied", 0),
                    "unsubscribes": ev.get("unsubscribed", 0),
                    "bounces": ev.get("bounced", 0),
                    "meta_failed": ev.get("failed", 0),
                    "due_now": len(self.tracker.get_due_followups(now)),
                    "daily_limit": self.sender.daily_limit,
                    "remaining": max(0, self.sender.daily_limit
                                     - rep["sent"])})
        return rep
