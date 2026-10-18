# -*- coding: utf-8 -*-
"""Indoctrination Engine — Manages the 5-email trust-building sequence.

State is saved to: data/email/indoctrination_state.json
Logs are saved to: data/email/indoctrination_sent_log.jsonl

Flow:
  Day 0 -> Email 1 (The Truth)
  Day 1 -> Email 2 (The Struggle)
  Day 3 -> Email 3 (The Proof)
  Day 5 -> Email 4 (The Mission)
  Day 7 -> Email 5 (The Invitation)
"""

import json
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Imports from our own system
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from atlas_services import indoctrination_templates as templates
from atlas_services.email_sender import EmailSender

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "email"
STATE_FILE = DATA_DIR / "indoctrination_state.json"
LOG_FILE = DATA_DIR / "indoctrination_sent_log.jsonl"

# The days offsets for each email in the sequence
SEQUENCE_DAYS = {
    "day0_truth": 0,
    "day1_struggle": 1,
    "day3_proof": 3,
    "day5_mission": 5,
    "day7_invitation": 7,
}

DUBAI_TZ = timezone(timedelta(hours=4))

def _load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _save_state(state: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

def _log(entry: dict):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")

def _now():
    return datetime.now(DUBAI_TZ)

def start_sequence(prospect: dict, language: str = "en",
                   dry_run: bool = True, confirmed: bool = False) -> dict:
    """Starts the indoctrination sequence for a new prospect (sends Day 0)."""
    email = prospect.get("email")
    if not email:
        return {"ok": False, "reason": "no_email"}

    state = _load_state()
    if email in state:
        return {"ok": False, "reason": "already_in_sequence"}

    # Get the first email
    seq = templates.get_sequence(language)
    if not seq:
        return {"ok": False, "reason": "no_templates"}

    tpl = seq[0]  # day0_truth
    rendered = templates.render(tpl, prospect)
    
    sender = EmailSender(dry_run=dry_run)
    result = sender.send(prospect, rendered, template_id=tpl["id"], confirmed=confirmed)

    if result.get("status") in ("sent", "dry_run"):
        now = _now().isoformat()
        state[email] = {
            "company_name": prospect.get("company_name", ""),
            "language": language,
            "started_at": now,
            "last_sent_at": now,
            "last_sent_day": "day0_truth",
            "status": "active" if result.get("status") == "sent" else "dry_run",
            "opens": 0, "replies": 0
        }
        _save_state(state)
        _log({"email": email, "template": tpl["id"], "status": result.get("status"), "at": now})
        
    return result

def process_due(dry_run: bool = True, confirmed: bool = False, max_count: int = 25) -> dict:
    """Checks all active prospects and sends the next email if it's due."""
    state = _load_state()
    now = _now()
    
    sent_count = 0
    blocked_count = 0
    failed_count = 0
    
    # Create sender instance
    sender = EmailSender(dry_run=dry_run)

    for email, data in list(state.items()):
        if data.get("status") != "active" and data.get("status") != "dry_run":
            continue
            
        last_day_cat = data.get("last_sent_day")
        if last_day_cat not in SEQUENCE_DAYS:
            continue
            
        last_day_offset = SEQUENCE_DAYS[last_day_cat]
        
        # Find the next day category
        next_cat = None
        next_offset = None
        for cat, offset in sorted(SEQUENCE_DAYS.items(), key=lambda x: x[1]):
            if offset > last_day_offset:
                next_cat = cat
                next_offset = offset
                break
                
        if not next_cat:
            # Sequence completed
            data["status"] = "completed"
            continue

        # Check if enough time has passed
        last_sent_date = datetime.fromisoformat(data["last_sent_at"]).astimezone(DUBAI_TZ)
        days_since = (now - last_sent_date).days
        
        # We use >= to allow catch-up if the system was offline
        if days_since >= (next_offset - last_day_offset):
            # Time to send the next email
            lang = data.get("language", "en")
            seq = templates.get_sequence(lang)
            tpl = next((t for t in seq if t["category"] == next_cat), None)
            
            if not tpl:
                continue
                
            # Reconstruct prospect dict
            prospect = {
                "email": email,
                "company_name": data.get("company_name", ""),
                # We might need contact_name if we had it, but we don't store it in state. 
                # The template will gracefully fall back to "team".
            }
            
            rendered = templates.render(tpl, prospect)
            result = sender.send(prospect, rendered, template_id=tpl["id"], confirmed=confirmed)
            
            status = result.get("status")
            if status in ("sent", "dry_run"):
                data["last_sent_at"] = now.isoformat()
                data["last_sent_day"] = next_cat
                sent_count += 1
                _log({"email": email, "template": tpl["id"], "status": status, "at": data["last_sent_at"]})
            elif status == "blocked":
                blocked_count += 1
                # Don't update last_sent_at so it tries again tomorrow
            else:
                failed_count += 1

    _save_state(state)
    return {"sent": sent_count, "blocked": blocked_count, "failed": failed_count}

def mark_replied(email: str):
    """Stops the sequence for a prospect who replied."""
    state = _load_state()
    if email in state:
        state[email]["status"] = "replied"
        state[email]["replies"] += 1
        _save_state(state)

def get_stats() -> dict:
    state = _load_state()
    stats = {"total": len(state), "active": 0, "completed": 0, "replied": 0, "dry_run": 0}
    for data in state.values():
        s = data.get("status")
        if s in stats:
            stats[s] += 1
    return stats