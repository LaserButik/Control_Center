# -*- coding: utf-8 -*-
"""Sales Sequence — Sends payment or meeting links to interested prospects."""

import os
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from atlas_services.email_sender import EmailSender
from atlas_services import email_templates as et

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "email"
SALES_LOG = DATA_DIR / "sales_log.jsonl"
DUBAI_TZ = timezone(timedelta(hours=4))

def send_meeting_link(prospect: dict, dry_run: bool = False) -> dict:
    """Sends a Calendly link to book a meeting."""
    calendly = os.getenv("CALENDLY_LINK", "https://calendly.com/salehhaidar/15min")
    
    subject = f"Let's talk about {prospect.get('company_name', 'your business')}"
    body = f"""Hi {prospect.get('contact_name', 'there')},

Great to hear you're interested in AI Mentors Agency.

Let's jump on a quick 15-minute call. I'll show you exactly how ALPHA can work for your business.

Book a time that suits you here: {calendly}

Talk soon,
Saleh Haidar"""

    sender = EmailSender(dry_run=dry_run)
    res = sender.send(prospect, {"subject": subject, "body": body, "body_html": f"<p>{body.replace(chr(10), '<br>')}</p>"}, template_id="sales_meeting", confirmed=not dry_run)
    
    _log_sale(prospect.get('email'), "meeting_link", res)
    return res

def send_payment_link(prospect: dict, dry_run: bool = False) -> dict:
    """Sends a Stripe payment link."""
    stripe_link = os.getenv("STRIPE_PAYMENT_LINK", "https://buy.stripe.com/test_xxx")
    
    subject = f"Your ALPHA Setup for {prospect.get('company_name', 'your business')}"
    body = f"""Hi {prospect.get('contact_name', 'there')},

Ready to automate your customer service and stop losing leads at night?

Here is your secure payment link for the ALPHA Setup & Subscription:
{stripe_link}

Once paid, reply to this email and we will start your onboarding immediately.

Best,
Saleh Haidar"""

    sender = EmailSender(dry_run=dry_run)
    res = sender.send(prospect, {"subject": subject, "body": body, "body_html": f"<p>{body.replace(chr(10), '<br>')}</p>"}, template_id="sales_payment", confirmed=not dry_run)
    
    _log_sale(prospect.get('email'), "payment_link", res)
    return res

def _log_sale(email, action, res):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with SALES_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"email": email, "action": action, "status": res.get("status"), "at": datetime.now(DUBAI_TZ).isoformat()}, ensure_ascii=False) + "\n")