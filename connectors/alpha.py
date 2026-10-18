# -*- coding: utf-8 -*-
"""Read-only view of ALPHA WhatsApp activity, from the outreach run data.

This phase never calls Meta's API. Inbound replies are not collected by the
pipeline yet (Phase I sends only), so `load_recent_replies` returns [] until
that exists. `load_conversations` summarises the outbound WhatsApp attempts
recorded in each run's wa_send_log.jsonl, so the page has something real to
show.
"""

from __future__ import annotations

import json

from . import paths


def _runs():
    base = paths.OUTREACH_RUNS
    if not base.is_dir():
        return []
    return sorted((p for p in base.iterdir() if p.is_dir()),
                  key=lambda p: p.name, reverse=True)


def load_recent_replies(limit: int = 50) -> list[dict]:
    """Inbound WhatsApp replies. Empty until inbound handling is built; the
    function exists so the page degrades cleanly."""
    return []


def load_conversations(limit: int = 50) -> list[dict]:
    """Recent outbound WhatsApp attempts, newest first, across all runs.
    Reads wa_send_log.jsonl (sent / blocked / failed rows). Phone numbers
    are not stored there in clear — only a hash — so nothing sensitive is
    surfaced."""
    rows = []
    for run in _runs():
        log = run / "wa_send_log.jsonl"
        if not log.exists():
            continue
        try:
            text = log.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in text.splitlines():
            try:
                r = json.loads(line)
            except ValueError:
                continue
            rows.append({"run_id": run.name, "at": r.get("at"),
                         "status": r.get("status"), "reason": r.get("reason"),
                         "mode": r.get("mode"),
                         "provider_id": r.get("provider_id"),
                         "to_hash": (r.get("to_hash") or "")[:12]})
    rows.sort(key=lambda r: r.get("at") or "", reverse=True)
    return rows[:int(limit)]
