# -*- coding: utf-8 -*-
"""The ATLAS catalogue: all 17 services with a status, and the three
network-free / Serper services runnable here. Deeper ones have their own
pages (Reputation, Backlinks, Competitive)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pandas as pd
import streamlit as st

from ui_common import page_config, render_sidebar
from ui.i18n import t, get_lang
from ui_common import page_header
from ui import components as C
from ui.icons import ICONS
from atlas_services import website_monitor, seo_intelligence, content_health

page_config(st, "ATLAS Services")
render_sidebar(st)

page_header(st, "ATLAS services", "", "globe")

# (name, status: available | partial | soon, where to find it, icon)
CATALOGUE = [
    ("Website Monitoring", "available", "Run below", "activity"),
    ("SEO Intelligence", "available", "Run below", "trend_up"),
    ("Competitive Analysis", "available", "Competitive page (new)", "sword"),
    ("B2B Client Acquisition", "available",
     "Via outreach: Discovery, Verify, Scrape", "users"),
    ("Personalized Outreach", "available", "Via outreach: Queue, Send",
     "send"),
    ("Content Health", "available", "Run below", "shield"),
    ("Backlink Intelligence", "available", "Backlinks page (new)", "link"),
    ("Reputation Monitoring", "available", "Reputation page (new)", "star"),
    ("Content Distribution", "available",
     "Distribution page (new, manual-only)", "share"),
    ("A/B and Conversion", "partial", "A/B Testing page (view-only)",
     "flask"),
    ("Client Dashboards", "available", "This Control Center", "chart"),
    ("Prospect Enrichment", "available",
     "Extract contact info from company websites. "
     "<a href='/ATLAS_Enrichment' target='_self'>Open →</a>",
     "search"),
    ("Prospect Finder", "available",
     "Find new prospects with emails from public directories "
     "and search. "
     "<a href='/ATLAS_Finder' target='_self'>Open →</a>",
     "users"),
    ("Email Engine", "available",
     "Sector email templates (AR/EN), gated sending, tracking and "
     "day 0 / day 3 sequences. "
     "<a href='/ATLAS_Email' target='_self'>Open →</a>",
     "send"),
    ("WhatsApp Engine", "available",
     "Meta-ready WhatsApp templates (AR/EN), gated Cloud API sending, "
     "delivery and reply tracking. "
     "<a href='/ATLAS_WhatsApp' target='_self'>Open →</a>",
     "inbox"),
    ("Scheduler", "available",
     "The daily 24/7 run: find, enrich, route, send, follow up, report. "
     "<a href='/Scheduler' target='_self'>Open →</a>",
     "clock"),
    ("Reports", "available",
     "Daily and weekly outreach numbers by channel and sector. "
     "<a href='/Outreach_Reports' target='_self'>Open →</a>",
     "chart"),
]
_STATUS = {"available": ("Available", "success"),
           "partial": ("Partial · view-only", "warning"),
           "soon": ("Coming soon", "danger")}

C.render(st, C.section_header("Catalogue", "%d services · %d available · "
                              "%d partial" % (len(CATALOGUE),
                                  sum(s == "available" for _, s, _, _ in
                                      CATALOGUE),
                                  sum(s == "partial" for _, s, _, _ in
                                      CATALOGUE))))
cards = []
for i, (name, status, where, ic) in enumerate(CATALOGUE, 1):
    text, kind = _STATUS[status]
    cards.append(C.glass_card(
        "%02d" % i,
        "<div style='display:flex;align-items:center;gap:10px;"
        "margin-bottom:8px;color:#F4F6FB;font-weight:600;font-size:15px;'>"
        "%s%s</div><div style='margin-bottom:10px;'>%s</div>%s"
        % (ICONS[ic], name, where, C.status_pill(text, kind)),
        accent={"available": "indigo", "partial": "warning",
                "soon": "danger"}[status], padding=4))
C.render(st, "<div style='display:grid;grid-template-columns:repeat(auto-fill,"
         "minmax(260px,1fr));gap:16px;'>%s</div>" % "".join(cards))

st.divider()
C.render(st, C.section_header("Run here"))
lang = get_lang()
tab1, tab2, tab3 = st.tabs([t("services.tab_monitor", lang),
                            t("services.tab_seo", lang),
                            t("services.tab_health", lang)])

EXAMPLE_URL = "https://salehhaidar.com"
SLOW_MS = 3000
_ROW_BG = {"ok": "rgba(16,185,129,0.16)", "warn": "rgba(245,158,11,0.18)",
           "error": "rgba(239,68,68,0.18)"}
_CODE_BY_MESSAGE = {v: k for k, v in website_monitor.MESSAGES.items()}


def _reason_text(code, fallback=""):
    key = "net.%s" % (code or "request_failed")
    text = t(key, lang)
    return text if text != key else (fallback or t("net.request_failed",
                                                    lang))


def _http_text(code: int) -> str:
    key = {403: "net.http_403", 404: "net.http_404"}.get(
        code, "net.http_5xx" if code >= 500 else "net.http_error")
    return t(key, lang).replace("{code}", str(code))


def _row(url, level, status_code, ms, note) -> tuple[str, dict]:
    label = t("net.level_" + level, lang)
    return level, {
        t("net.col_url", lang): url,
        t("net.col_status", lang): "%s · %s" % (label, status_code)
        if status_code else label,
        t("net.col_time", lang): ms if ms is not None else "—",
        t("net.col_notes", lang): note}


def _show_table(rows: list[tuple[str, dict]]) -> None:
    levels = [lvl for lvl, _ in rows]
    df = pd.DataFrame([r for _, r in rows])
    styled = df.style.apply(
        lambda row: ["background-color: %s" % _ROW_BG[levels[row.name]]]
        * len(row), axis=1)
    st.dataframe(styled, width="stretch", hide_index=True)


def _fill(key: str) -> None:
    st.session_state[key] = EXAMPLE_URL


with tab1:
    st.caption(t("net.monitor_caption", lang))
    st.button(t("net.try_example", lang), icon=":material/auto_awesome:",
              on_click=_fill, args=("wm_urls",), key="wm_example")
    raw = st.text_area(t("net.urls_label", lang), key="wm_urls",
                       placeholder="salehhaidar.com\nhttps://example.com")
    if st.button(t("net.check_button", lang), type="primary",
                 icon=":material/network_check:", key="wm_go"):
        urls = [u.strip() for u in (raw or "").splitlines() if u.strip()]
        if not urls:
            st.warning(t("net.enter_url", lang))
        else:
            with st.spinner(t("net.checking", lang).replace(
                    "{n}", str(len(urls)))):
                results = website_monitor.check_many(urls)
            rows = []
            for r in results:
                shown = r.get("checked_url") or r["url"]
                code, ms = r.get("status_code"), r.get("response_ms")
                if code is None:
                    rows.append(_row(shown, "error", None, ms, _reason_text(
                        r.get("reason"), r.get("message"))))
                elif code >= 400:
                    rows.append(_row(shown, "error", code, ms,
                                     _http_text(code)))
                elif (ms or 0) > SLOW_MS:
                    rows.append(_row(shown, "warn", code, ms,
                                     t("net.slow", lang)))
                else:
                    rows.append(_row(shown, "ok", code, ms,
                                     t("net.site_up", lang)))
            _show_table(rows)

with tab2:
    st.caption("Uses SERPER_API_KEY from the environment. Without it, no "
               "network call is made.")
    domain = st.text_input("Domain", placeholder="example.ae")
    if st.button("Check domain"):
        with st.spinner("Querying Serper…"):
            st.json(seo_intelligence.check_domain(domain))

with tab3:
    st.caption(t("net.health_caption", lang))
    st.button(t("net.try_example", lang), icon=":material/auto_awesome:",
              on_click=_fill, args=("ch_base",), key="ch_example")
    base = st.text_input(t("net.base_label", lang), key="ch_base",
                         placeholder="salehhaidar.com")
    maxp = st.number_input(t("net.max_pages", lang), 1, 100, 20,
                           key="ch_max")
    if st.button(t("net.scan_button", lang), type="primary",
                 icon=":material/travel_explore:", key="ch_go"):
        if not (base or "").strip():
            st.warning(t("net.enter_url", lang))
        else:
            with st.spinner(t("net.scanning", lang)):
                report = content_health.scan_site(base, max_pages=int(maxp))
            reason = report.get("reason") or ""
            if not report.get("ok"):
                if reason == "invalid_url":
                    st.error(_reason_text(
                        website_monitor.normalize_url(base)[1]))
                elif reason.startswith("robots_unreachable:HTTP"):
                    st.error(t("net.robots_server_error", lang).replace(
                        "{code}", reason.rsplit(" ", 1)[-1]))
                else:
                    st.error(_reason_text(_CODE_BY_MESSAGE.get(
                        report.get("message")), report.get("message")))
            else:
                pages = report.get("pages", [])
                blocked = sum(1 for p in pages if p.get("skipped"))
                m1, m2, m3 = st.columns(3)
                m1.metric(t("net.pages_scanned", lang),
                          report.get("pages_scanned", 0))
                m2.metric(t("net.broken", lang),
                          report.get("broken_count", 0))
                m3.metric(t("net.blocked", lang), blocked)
                rows = []
                for p in pages:
                    code, ms = p.get("status_code"), p.get("response_ms")
                    if p.get("skipped"):
                        rows.append(_row(p["url"], "warn", None, ms,
                                         _reason_text("robots_disallowed")))
                    elif code is None:
                        rows.append(_row(p["url"], "error", None, ms,
                                         _reason_text(p.get("reason"),
                                                      p.get("message"))))
                    elif code >= 400:
                        rows.append(_row(p["url"], "error", code, ms,
                                         _http_text(code)))
                    elif (ms or 0) > SLOW_MS:
                        rows.append(_row(p["url"], "warn", code, ms,
                                         t("net.slow", lang)))
                    else:
                        rows.append(_row(p["url"], "ok", code, ms, t(
                            "net.page_ok", lang).replace(
                                "{n}", str(p.get("links", 0)))))
                if rows:
                    _show_table(rows)
