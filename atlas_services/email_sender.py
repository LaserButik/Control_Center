# -*- coding: utf-8 -*-
"""ATLAS email sender: one email at a time over SMTP, behind three gates.

  1. compliance  valid address, not suppressed, not replied / bounced /
                 unsubscribed, under the daily limit, not emailed in the
                 last 20 hours, not twice in one batch
  2. dry_run     True by default: nothing leaves the machine
  3. confirmed   False by default: a real send needs dry_run=False AND
                 confirmed=True

SMTP settings come from the environment only:
  SMTP_HOST, SMTP_PORT (587), SMTP_USER, SMTP_PASSWORD, SMTP_FROM,
  SMTP_DISABLE_TLS (STARTTLS is used unless this is "true").
The password is kept in a private attribute and is never logged,
printed, returned or written to a file; error text is scrubbed of it.

The sender does not write the sent log itself: EmailSequence records
every attempt with EmailTracker.record_sent. Call it yourself if you use
send() directly, so the daily count stays right.
"""

from __future__ import annotations

import logging
import os
import smtplib
import ssl
import time
from datetime import timedelta
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid

from atlas_services import email_tracker as ET

log = logging.getLogger(__name__)

MAX_DAILY_LIMIT = 25           # a new sending domain stays low
RESEND_WINDOW = timedelta(hours=20)
DEFAULT_FROM_NAME = "Saleh from AI Mentors"
DEFAULT_REPLY_TO = "info@salehhaidar.com"


# ───────────────────────── module helpers ─────────────────────────

def load_suppression(data_dir=None) -> set[str]:
    return ET.load_suppression(data_dir)


def add_to_suppression(email, reason="manual", data_dir=None) -> dict:
    return ET.add_to_suppression(email, reason, data_dir)


def is_suppressed(email, data_dir=None) -> bool:
    return ET.is_suppressed(email, data_dir)


def get_daily_sent_count(data_dir=None, now=None) -> int:
    return ET.get_daily_sent_count(data_dir, now)


def _settings_limit(key: str, fallback: int) -> int:
    try:
        from ui.settings_store import settings_limit
    except ImportError:
        return fallback
    return settings_limit(key, fallback)


def _env_true(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in ("1", "true", "yes", "on")


# ───────────────────────── sender ─────────────────────────

class EmailSender:
    def __init__(self, *, smtp_host=None, smtp_port=None, smtp_user=None,
                 smtp_password=None, from_email=None,
                 from_name=DEFAULT_FROM_NAME, reply_to=DEFAULT_REPLY_TO,
                 daily_limit=None, delay_between_sends_s=45.0,
                 dry_run=True, smtp_client=None, sleep=time.sleep,
                 clock=time.monotonic, tracker=None, now=None):
        """Reads SMTP_* env vars for every parameter left as None.
        daily_limit: the argument if given, else daily_email_limit from
        data/settings.json, else 25 — never above MAX_DAILY_LIMIT.
        `smtp_client` is a factory (host, port, timeout=) -> client, used
        by tests; `tracker` supplies state, suppression and the sent log;
        `now` returns an aware datetime (tests)."""
        env = os.environ
        self.smtp_host = (smtp_host if smtp_host is not None
                          else env.get("SMTP_HOST", "")).strip()
        try:
            self.smtp_port = int(smtp_port if smtp_port is not None
                                 else env.get("SMTP_PORT") or 587)
        except ValueError:
            self.smtp_port = 587
        self.smtp_user = (smtp_user if smtp_user is not None
                          else env.get("SMTP_USER", "")).strip()
        self.__password = (smtp_password if smtp_password is not None
                           else env.get("SMTP_PASSWORD", ""))
        self.from_email = (from_email if from_email is not None
                           else env.get("SMTP_FROM", "")).strip()
        self.from_name = from_name or DEFAULT_FROM_NAME
        self.reply_to = reply_to or DEFAULT_REPLY_TO
        self.use_tls = not _env_true("SMTP_DISABLE_TLS")
        if daily_limit is None:
            daily_limit = _settings_limit("daily_email_limit",
                                          MAX_DAILY_LIMIT)
        self.daily_limit = max(0, min(int(daily_limit), MAX_DAILY_LIMIT))
        self.delay_between_sends_s = max(0.0, float(delay_between_sends_s))
        self.dry_run = bool(dry_run)
        self._smtp_client = smtp_client
        self._sleep, self._clock = sleep, clock
        self.tracker = tracker or ET.EmailTracker(now=now)
        self._now = now or ET.utcnow
        self._last_send = None
        self._session_sent = 0          # real sends by this instance
        self._session_dry = 0           # dry runs by this instance
        # email -> when this instance last handled it, per mode, so a
        # batch never hits one address twice and a dry run does not block
        # the real send that follows it
        self._seen = {"dry": {}, "real": {}}

    def __repr__(self):
        return ("EmailSender(host=%r, port=%r, user=%r, from=%r, tls=%r, "
                "password_set=%r, dry_run=%r)" % (
                    self.smtp_host, self.smtp_port, self.smtp_user,
                    self.from_email, self.use_tls, bool(self.__password),
                    self.dry_run))

    def config_summary(self) -> dict:
        """Presence only for the password."""
        return {"host": self.smtp_host, "port": self.smtp_port,
                "user": self.smtp_user, "from_email": self.from_email,
                "from_name": self.from_name, "reply_to": self.reply_to,
                "starttls": self.use_tls,
                "password_set": bool(self.__password),
                "daily_limit": self.daily_limit}

    def is_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_user and self.__password
                    and ET.normalize_email(self.from_email))

    def _scrub(self, text: str) -> str:
        text = str(text or "")
        return text.replace(self.__password, "***") if self.__password \
            else text

    # ── counts ──
    def sent_today(self) -> int:
        logged = ET.get_daily_sent_count(self.tracker.data_dir, self._now())
        return max(logged, self._session_sent)

    def remaining_today(self, real: bool = False) -> int:
        """Real sends left today. In a dry run the batch's own previews
        count too, so the preview shows where the limit would cut."""
        used = self.sent_today() + (0 if real else self._session_dry)
        return max(0, self.daily_limit - used)

    # ── gates ──
    def _check_compliance(self, prospect: dict, *,
                          real: bool = False) -> tuple[bool, str | None]:
        p = prospect if isinstance(prospect, dict) else {}
        email = ET.normalize_email(p.get("email"))
        if not email:
            return False, "invalid_email"
        if ET.is_suppressed(email, self.tracker.data_dir):
            return False, "suppressed"
        state = self.tracker.get_prospect_state(email)
        for status in (str(p.get("status") or "").lower(),
                       state.get("status")):
            if status in ET.STOPPED:
                return False, "status_%s" % status
        if self.remaining_today(real) <= 0:
            return False, "daily_limit_reached"
        seen = self._seen["real" if real else "dry"].get(email)
        if seen and self._now() - seen < RESEND_WINDOW:
            return False, "duplicate_in_batch"
        for value in (state.get("last_sent_at"), p.get("last_sent_at")):
            last = ET.parse_iso(value)
            if last and self._now() - last < RESEND_WINDOW:
                return False, "sent_within_20h"
        return True, None

    @staticmethod
    def _result(ok, status, reason=None, message_id=None, sent_at=None,
                **extra) -> dict:
        return dict({"ok": ok, "status": status, "reason": reason,
                     "message_id": message_id, "sent_at": sent_at}, **extra)

    def send(self, prospect: dict, rendered: dict, *, template_id: str,
             confirmed: bool = False) -> dict:
        p = prospect if isinstance(prospect, dict) else {}
        r = rendered if isinstance(rendered, dict) else {}
        email = ET.normalize_email(p.get("email"))
        extra = {"email": email or str(p.get("email") or ""),
                 "template_id": template_id}
        real = not self.dry_run and bool(confirmed)
        ok, why = self._check_compliance(p, real=real)
        if not ok:
            log.info("blocked %s (%s) template=%s", extra["email"], why,
                     template_id)
            return self._result(False, "blocked", why, **extra)
        if not r.get("subject") or not r.get("body"):
            return self._result(False, "blocked", "empty_message", **extra)
        if not real:
            self._session_dry += 1
            self._seen["dry"][email] = self._now()
            return self._result(True, "dry_run", "dry_run" if self.dry_run
                                else "not_confirmed", **extra)
        if not self.is_configured():
            return self._result(False, "failed", "smtp_not_configured",
                                **extra)
        if self._last_send is not None:
            wait = self.delay_between_sends_s - (self._clock()
                                                 - self._last_send)
            if wait > 0:
                self._sleep(wait)
        try:
            info = self._send_smtp(email, r["subject"], r["body"],
                                   r.get("body_html") or "")
        except Exception as e:                      # noqa: BLE001
            self._last_send = self._clock()
            reason = self._scrub("smtp_error:%s: %s" % (type(e).__name__, e))
            log.warning("failed %s template=%s: %s", email, template_id,
                        reason)
            return self._result(False, "failed", reason[:300], **extra)
        self._last_send = self._clock()
        self._session_sent += 1
        self._seen["real"][email] = self._now()
        log.info("sent %s template=%s", email, template_id)
        return self._result(True, "sent", None, info.get("message_id"),
                            ET.iso(self._now()), **extra)

    def _send_smtp(self, to_email, subject, body, body_html) -> dict:
        """Real SMTP. The injected client factory is used in tests."""
        msg = EmailMessage()
        msg["From"] = formataddr((self.from_name, self.from_email))
        msg["To"] = to_email
        msg["Reply-To"] = self.reply_to
        msg["Subject"] = subject
        msg["Date"] = formatdate(localtime=False)
        mid = make_msgid(domain=self.from_email.split("@")[-1] or None)
        msg["Message-ID"] = mid
        msg["List-Unsubscribe"] = "<mailto:%s?subject=unsubscribe>" \
            % self.reply_to
        msg.set_content(body)
        if body_html:
            msg.add_alternative(body_html, subtype="html")
        factory = self._smtp_client or smtplib.SMTP
        client = factory(self.smtp_host, self.smtp_port, timeout=30)
        try:
            if self.use_tls:
                client.starttls(context=ssl.create_default_context())
            if self.smtp_user:
                client.login(self.smtp_user, self.__password)
            client.send_message(msg)
        finally:
            try:
                client.quit()
            except Exception:                       # noqa: BLE001
                pass
        return {"message_id": mid}
