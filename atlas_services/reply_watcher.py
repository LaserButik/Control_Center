# -*- coding: utf-8 -*-
"""Reply Watcher — Connects to Zoho IMAP to detect replies.

If a prospect replies, it marks their Indoctrination sequence as "replied"
so no further automated emails are sent, and sends a Telegram alert.
"""

import email
import imaplib
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from email.header import decode_header
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from atlas_services import indoctrination_engine as engine

# Configuration
IMAP_SERVER = "imap.zoho.com"
IMAP_PORT = 993

DUBAI_TZ = timezone(timedelta(hours=4))

def _get_credentials():
    user = os.getenv("ZOHO_EMAIL", "").strip()
    password = os.getenv("ZOHO_APP_PASSWORD", "").strip()
    
    # Fallback to .env if not in environment
    if not user or not password:
        env_file = Path(__file__).resolve().parent.parent / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                if line.startswith("ZOHO_EMAIL="):
                    user = line.split("=", 1)[1].strip()
                elif line.startswith("ZOHO_APP_PASSWORD="):
                    password = line.split("=", 1)[1].strip()
    return user, password

def check_replies(dry_run: bool = False) -> dict:
    """Connects to IMAP, reads unseen emails, and updates state."""
    user, password = _get_credentials()
    
    if not user or not password:
        return {"ok": False, "reason": "missing_zoho_credentials", "replies": 0}

    if dry_run:
        return {"ok": True, "reason": "dry_run", "replies": 0}

    try:
        # Connect to Zoho
        mail = imaplib.IMAP4_SSL(IMAP_SERVER, IMAP_PORT)
        mail.login(user, password)
        mail.select("inbox")

        # Search for ALL emails (or UNSEEN). We use ALL to catch past replies
        # In a real environment, you might only search since the last check.
        status, messages = mail.search(None, "UNSEEN")
        if status != "OK":
            return {"ok": False, "reason": "imap_search_failed", "replies": 0}

        email_ids = messages[0].split()
        if not email_ids:
            mail.logout()
            return {"ok": True, "reason": "no_new_emails", "replies": 0}

        state = engine._load_state()
        replied_count = 0
        alerts_sent = []

        for e_id in email_ids:
            # Fetch the email (RFC822)
            status, msg_data = mail.fetch(e_id, "(RFC822)")
            if status != "OK":
                continue

            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    # Extract sender email
                    from_header = msg.get("From", "")
                    email_match = re.search(r'[\w\.-]+@[\w\.-]+', from_header)
                    if not email_match:
                        continue
                    
                    sender_email = email_match.group(0).lower()
                    
                    # Check if this sender is in our Indoctrination state
                    if sender_email in state and state[sender_email].get("status") in ("active", "dry_run"):
                        state[sender_email]["status"] = "replied"
                        state[sender_email]["replies"] += 1
                        replied_count += 1
                        alerts_sent.append(sender_email)
                        
                        # Log it
                        now = datetime.now(DUBAI_TZ).isoformat()
                        engine._log({
                            "email": sender_email, 
                            "event": "reply_detected", 
                            "at": now
                        })

        # Mark these emails as Seen so we don't process them again
        if email_ids:
            mail.store(b",".join(email_ids), "+FLAGS", "\\Seen")

        mail.logout()

        if replied_count > 0:
            engine._save_state(state)
            
            # Send Telegram Alert
            try:
                from atlas_services.telegram_reporter import send_message
                alert_text = (
                    f"🔥 *رد جديد تم التقاطه!*\n\n"
                    f"تم إيقاف التسلسل التلقائي للعملاء التالين:\n"
                    f"{chr(10).join(alerts_sent)}\n\n"
                    f"اذهب إلى Zoho Inbox للرد عليهم."
                )
                send_message(alert_text)
            except Exception as e:
                print(f"Telegram alert failed: {e}")

        return {"ok": True, "replies": replied_count, "emails": alerts_sent}

    except Exception as e:
        return {"ok": False, "reason": str(e), "replies": 0}