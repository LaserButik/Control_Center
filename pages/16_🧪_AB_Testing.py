# -*- coding: utf-8 -*-
"""Read-only view of the outreach A/B mechanism.

outreach/templates.py is FROZEN; this page PARSES the module file as text
(never imports it) to show the CTA options and categories, counts how often
each CTA appears across queue bodies on disk, and shows a placeholder
outcome table. It changes nothing.
"""

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from ui_common import page_config, render_sidebar
from ui_common import page_header
from ui import components as C
from connectors import outreach, paths

page_config(st, "A/B Testing")
render_sidebar(st)

page_header(st, "A/B testing (view only)", "", "flask")
st.caption("Parses the frozen outreach/templates.py for its CTA pool and "
           "categories, and counts CTA usage across the queue bodies "
           "already on disk. Nothing is modified.")

tmpl = paths.OUTREACH_PKG / "templates.py"


def _parse_assignments(path: Path) -> dict:
    """Return the literal values of CTA_POOL, CTA_CATEGORIES, CATEGORIES,
    LANGUAGES and PRODUCTS from the module, via AST — no import, no code
    execution of the module."""
    out = {}
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError) as e:
        return {"_error": type(e).__name__}
    wanted = {"CTA_POOL", "CTA_CATEGORIES", "CATEGORIES", "LANGUAGES",
              "PRODUCTS"}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id in wanted:
                    try:
                        out[t.id] = ast.literal_eval(node.value)
                    except ValueError:
                        pass
    return out


if not tmpl.exists():
    st.error("templates.py not found at %s" % tmpl)
    st.stop()

parsed = _parse_assignments(tmpl)
if parsed.get("_error"):
    st.error("Could not parse templates.py: %s" % parsed["_error"])
    st.stop()

cta = parsed.get("CTA_POOL", {})
cats = parsed.get("CTA_CATEGORIES", ())
C.render(st, C.section_header("CTA options per language"))
st.caption("Source of truth is templates.py. Note: the pool has %d options "
           "per language (not 5)." % (len(cta.get("en", []))))
for lang in ("en", "ar"):
    options = cta.get(lang, [])
    with st.expander("%s — %d options" % (lang.upper(), len(options)),
                     expanded=(lang == "en")):
        st.table(pd.DataFrame({
            "category": [cats[i] if i < len(cats) else "—"
                         for i in range(len(options))],
            "text": [o[:120] for o in options]}))

C.render(st, C.section_header("Template categories and products"))
c = st.columns(2)
c[0].write({"categories": list(parsed.get("CATEGORIES", []))})
c[1].write({"products": list(parsed.get("PRODUCTS", [])),
            "languages": list(parsed.get("LANGUAGES", []))})

# ── CTA usage across queue bodies on disk ──
C.render(st, C.section_header("CTA distribution in queued messages"))
counts = {lang: [0] * len(cta.get(lang, [])) for lang in cta}
total = 0
for run in outreach.list_runs():
    data = outreach.load_run(run["run_id"])
    for e in data.get("entries", []):
        body = e.get("body") or ""
        lang = e.get("language") if e.get("language") in cta else None
        if not lang:
            continue
        total += 1
        for i, option in enumerate(cta[lang]):
            # the CTA text contains {company_name}; match the stable prefix
            stem = option.split("{")[0].strip()
            if stem and stem in body:
                counts[lang][i] += 1
                break

if total:
    rows = []
    for lang, arr in counts.items():
        for i, n in enumerate(arr):
            rows.append({"language": lang,
                         "category": cats[i] if i < len(cats) else str(i),
                         "used": n})
    dist = pd.DataFrame(rows)
    st.bar_chart(dist.pivot_table(index="category", columns="language",
                                  values="used", fill_value=0))
    st.dataframe(dist, width="stretch", hide_index=True)
    st.caption("Counted across %d queued messages on disk." % total)
else:
    st.info("No queued messages on disk yet to measure CTA usage.")

C.render(st, C.section_header("A/B outcome (placeholder)"))
st.caption("Outcome tracking needs reply/outcome data, which is not "
           "collected yet. This table is a placeholder.")
st.table(pd.DataFrame({
    "variant": ["CTA A", "CTA B", "CTA C", "CTA D"],
    "sent": ["—", "—", "—", "—"],
    "replied": ["—", "—", "—", "—"],
    "reply_rate": ["—", "—", "—", "—"]}))

st.info("templates.py is frozen. Unfreezing it to run true experiments is a "
        "later decision for you.")
