# -*- coding: utf-8 -*-
"""ATLAS channel router: which channels to use for one prospect.

Rules, in the order they are applied:
  1. sector unknown / without templates      -> skip, "blocked_sector"
  2. country not AE or SA                     -> skip, "blocked_country"
     (country from the prospect, else from the phone prefix)
  3. no valid email and no phone              -> skip, "no_contact"
  4. email and WhatsApp both unusable because
     suppressed (or the phone is a landline)  -> skip, "suppressed"
                                                 / "no_contact"
  5. both usable                              -> ["email", "whatsapp"],
                                                 "both_available"
     ...but a role email (info@, contact@, …)
     with a mobile phone puts WhatsApp first  -> ["whatsapp", "email"]
  6. email only                               -> "email_only"
  7. WhatsApp only                            -> "whatsapp_only"
WhatsApp is usable only for an AE (+9715X) or SA (+9665X) mobile.
Channels are never empty unless skip is True.
"""

from __future__ import annotations

from atlas_services import email_templates as ETPL
from atlas_services import email_tracker as ET
from atlas_services import whatsapp_sender as WS
from atlas_services import whatsapp_tracker as WT

ALLOWED_COUNTRIES = {"AE", "SA"}
ROLE_LOCALS = {"info", "contact", "sales", "admin", "office", "hello",
               "enquiries", "enquiry", "inquiries", "inquiry", "reception",
               "booking", "bookings", "reservations"}
STAT_KEYS = ("both", "email_only", "whatsapp_only", "no_contact", "unknown")


def is_role_email(email) -> bool:
    e = ET.normalize_email(email)
    return bool(e) and e.split("@")[0] in ROLE_LOCALS


def _skip(reason, **extra) -> dict:
    return dict({"channels": [], "primary": None, "secondary": None,
                 "skip": True, "reason": reason}, **extra)


def route(prospect: dict, *, email_data_dir=None, wa_data_dir=None,
          suppressed_emails=None, suppressed_phones=None) -> dict:
    """The routing decision for one prospect (see the module docstring).
    Suppression lists are read from the default data folders unless
    given."""
    p = prospect if isinstance(prospect, dict) else {}
    email = ET.normalize_email(p.get("email"))
    phone = WT.normalize_phone(p.get("phone_e164") or p.get("phone"))
    contact = {"email": email or None, "phone_e164": phone or None}
    if p.get("sector") not in ETPL.TEMPLATES:
        return _skip("blocked_sector", **contact)
    country = str(p.get("country") or WS.phone_country(phone) or "").upper()
    if country not in ALLOWED_COUNTRIES:
        return _skip("blocked_country", **contact)
    if not email and not phone:
        return _skip("no_contact", **contact)
    sup_e = (suppressed_emails if suppressed_emails is not None
             else ET.load_suppression(email_data_dir))
    sup_p = (suppressed_phones if suppressed_phones is not None
             else WT.load_suppression(wa_data_dir))
    email_ok = bool(email) and email not in sup_e
    wa_ok = (bool(phone) and WS.is_mobile(phone)
             and WS.phone_country(phone) in ALLOWED_COUNTRIES
             and phone not in sup_p)
    if not email_ok and not wa_ok:
        anything_suppressed = (email and email in sup_e) or \
            (phone and phone in sup_p)
        return _skip("suppressed" if anything_suppressed else "no_contact",
                     **contact)
    if email_ok and wa_ok:
        channels = (["whatsapp", "email"] if is_role_email(email)
                    else ["email", "whatsapp"])
        reason = "both_available"
    elif email_ok:
        channels, reason = ["email"], "email_only"
    else:
        channels, reason = ["whatsapp"], "whatsapp_only"
    return dict({"channels": channels, "primary": channels[0],
                 "secondary": channels[1] if len(channels) > 1 else None,
                 "skip": False, "reason": reason}, **contact)


def route_batch(prospects, **kwargs) -> list[dict]:
    """route() for each prospect; reads each suppression list once."""
    kwargs.setdefault("suppressed_emails",
                      ET.load_suppression(kwargs.get("email_data_dir")))
    kwargs.setdefault("suppressed_phones",
                      WT.load_suppression(kwargs.get("wa_data_dir")))
    return [route(p, **kwargs) for p in (prospects or [])]


def stats(routes) -> dict:
    """{both, email_only, whatsapp_only, no_contact, unknown} plus
    suppressed, blocked_country and total. "unknown" counts unknown
    sectors; "no_contact" counts prospects with nothing to contact."""
    out = dict.fromkeys(STAT_KEYS, 0)
    out.update(suppressed=0, blocked_country=0, total=0)
    key = {"both_available": "both", "email_only": "email_only",
           "whatsapp_only": "whatsapp_only", "no_contact": "no_contact",
           "blocked_sector": "unknown", "suppressed": "suppressed",
           "blocked_country": "blocked_country"}
    for r in routes or []:
        out["total"] += 1
        k = key.get((r or {}).get("reason"))
        if k:
            out[k] += 1
    return out
