# -*- coding: utf-8 -*-
"""Generate PDF reports with reportlab. English only in this phase.

- report_for_run(run_id, data_dir, out_path): a run's summary, queue status
  and the first 50 prospects.
- report_for_atlas(report_type, payload, out_path): a one-page summary of a
  reputation / backlinks / competitive result.

Generated PDFs are written wherever out_path points; the report pages put
them under Control_Center/reports/out/ (git-ignored). reportlab is imported
lazily so the module imports even when it is not installed.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

AGENCY = "AI Mentors Agency"


def _reportlab():
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.lib.units import mm
        from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                        Table, TableStyle)
        return {"colors": colors, "A4": A4, "styles": getSampleStyleSheet(),
                "mm": mm, "Doc": SimpleDocTemplate, "P": Paragraph,
                "Spacer": Spacer, "Table": Table, "TableStyle": TableStyle}
    except ImportError:
        return None


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _header(rl, title: str) -> list:
    s = rl["styles"]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return [rl["P"]("<b>%s</b>" % AGENCY, s["Title"]),
            rl["P"](title, s["Heading2"]),
            rl["P"]("Generated %s" % now, s["Normal"]),
            rl["Spacer"](1, 8)]


def _kv_table(rl, rows: list) -> "object":
    t = rl["Table"]([[str(k), str(v)] for k, v in rows],
                    colWidths=[70 * rl["mm"], 90 * rl["mm"]])
    t.setStyle(rl["TableStyle"]([
        ("GRID", (0, 0), (-1, -1), 0.4, rl["colors"].grey),
        ("BACKGROUND", (0, 0), (0, -1), rl["colors"].whitesmoke),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return t


def _grid(rl, header: list, data: list, widths: list) -> "object":
    t = rl["Table"]([header] + data, colWidths=[w * rl["mm"] for w in widths])
    t.setStyle(rl["TableStyle"]([
        ("GRID", (0, 0), (-1, -1), 0.3, rl["colors"].lightgrey),
        ("BACKGROUND", (0, 0), (-1, 0), rl["colors"].HexColor("#222a44")),
        ("TEXTCOLOR", (0, 0), (-1, 0), rl["colors"].white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return t


def _build(out_path: str, story) -> dict:
    rl = _reportlab()
    if rl is None:
        return {"ok": False, "reason": "reportlab_not_installed",
                "out_path": out_path}
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    doc = rl["Doc"](out_path, pagesize=rl["A4"], title=AGENCY)
    try:
        doc.build(story(rl))
    except Exception as e:
        return {"ok": False, "reason": "build_failed:%s" % type(e).__name__,
                "out_path": out_path}
    return {"ok": True, "out_path": out_path,
            "size_bytes": Path(out_path).stat().st_size}


def report_for_run(run_id: str, data_dir: str, out_path: str) -> dict:
    run = Path(data_dir) / "runs" / run_id
    if not run.is_dir():
        return {"ok": False, "reason": "run_not_found", "out_path": out_path}
    summary = _read_json(run / "summary.json") or {}
    queue = (_read_json(run / "queue.json") or {}).get("entries", [])
    prospects = (_read_json(run / "prospects.json") or {}).get("prospects",
                                                               [])
    status_counts = {}
    for e in queue:
        s = e.get("status", "?")
        status_counts[s] = status_counts.get(s, 0) + 1

    def story(rl):
        s = rl["styles"]
        els = _header(rl, "Outreach run report — %s" % run_id)
        els.append(rl["P"]("Summary", s["Heading3"]))
        els.append(_kv_table(rl, [(k, v) for k, v in summary.items()]))
        els.append(rl["Spacer"](1, 10))
        els.append(rl["P"]("Queue status", s["Heading3"]))
        els.append(_kv_table(rl, [("Total entries", len(queue))]
                             + list(status_counts.items())))
        els.append(rl["Spacer"](1, 10))
        els.append(rl["P"]("Prospects (first 50)", s["Heading3"]))
        rows = [[str(p.get("company_name") or "")[:34],
                 str(p.get("phone_e164") or p.get("phone") or "")[:16],
                 str(p.get("tier") or "")[:2],
                 str(p.get("score") or "")[:4],
                 str(p.get("csv_skip_reason") or "")[:18]]
                for p in prospects[:50]]
        els.append(_grid(rl, ["Company", "Phone", "Tier", "Score", "Skip"],
                         rows or [["(none)", "", "", "", ""]],
                         [58, 36, 12, 16, 38]))
        return els
    return _build(out_path, story)


def report_for_atlas(report_type: str, payload: dict, out_path: str) -> dict:
    report_type = (report_type or "").lower()
    if report_type not in ("reputation", "backlinks", "competitive"):
        return {"ok": False, "reason": "unknown_report_type",
                "out_path": out_path}
    payload = payload or {}

    def story(rl):
        s = rl["styles"]
        titles = {"reputation": "Reputation report",
                  "backlinks": "Backlink report",
                  "competitive": "Competitive analysis report"}
        els = _header(rl, titles[report_type])
        if report_type == "reputation":
            kv = [("Brand", payload.get("brand")),
                  ("Country", payload.get("country")),
                  ("Total mentions", payload.get("total_mentions")),
                  ("Unique sources", payload.get("unique_sources")),
                  ("Positive", payload.get("positive_hits")),
                  ("Negative", payload.get("negative_hits")),
                  ("Neutral", payload.get("neutral_hits"))]
            els.append(_kv_table(rl, kv))
            els.append(rl["Spacer"](1, 10))
            els.append(rl["P"]("Top sources", s["Heading3"]))
            rows = [[str(x.get("sentiment") or "")[:8],
                     str(x.get("title") or "")[:60]]
                    for x in payload.get("top_sources", [])[:20]]
            els.append(_grid(rl, ["Sentiment", "Title"],
                             rows or [["", "(none)"]], [24, 136]))
        elif report_type == "backlinks":
            kv = [("Domain", payload.get("domain")),
                  ("Estimated backlinks", payload.get("estimated_backlinks")),
                  ("Referring domains",
                   payload.get("referring_domains_count"))]
            els.append(_kv_table(rl, kv))
            els.append(rl["Spacer"](1, 10))
            els.append(rl["P"]("Referring domains (sample)", s["Heading3"]))
            rows = [[d] for d in
                    payload.get("referring_domains_sample", [])[:30]]
            els.append(_grid(rl, ["Domain"], rows or [["(none)"]], [160]))
        else:
            kv = [("Domain A", payload.get("domain_a")),
                  ("Score A", payload.get("score_a")),
                  ("Domain B", payload.get("domain_b")),
                  ("Score B", payload.get("score_b")),
                  ("Winner", payload.get("winner"))]
            els.append(_kv_table(rl, kv))
        return els
    return _build(out_path, story)
