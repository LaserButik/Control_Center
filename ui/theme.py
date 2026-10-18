# -*- coding: utf-8 -*-
"""Design tokens and the global CSS override for the Control Center.

Tokens (COLORS, GRADIENTS, SHADOWS, SPACING, RADII) are the single source
of truth; components.py and the Plotly template read from them.
inject_global_css() restyles Streamlit itself: fonts, background, sidebar,
buttons, inputs, tabs, metrics, scrollbar and motion.
"""

from __future__ import annotations

import re

COLORS = {
    "bg_deep":    "#0F1419",
    "bg_base":    "#0F1419",
    "bg_elev_1":  "#1A1F2E",
    "bg_elev_2":  "#1E2535",
    "bg_elev_3":  "#252D3F",
    "border_sub": "#2D3748",
    "border_hi":  "#4A5568",
    "text_hi":    "#F7FAFC",
    "text_mid":   "#A0AEC0",
    "text_low":   "#718096",
    "accent_1":   "#667EEA",   # indigo
    "accent_2":   "#764BA2",   # violet
    "accent_3":   "#06B6D4",   # cyan
    "success":    "#10B981",
    "warning":    "#F59E0B",
    "danger":     "#EF4444",
    "info":       "#3B82F6",
}

GRADIENTS = {
    "primary": "linear-gradient(135deg, #667EEA 0%, #764BA2 100%)",
    "subtle":  "linear-gradient(180deg, rgba(102,126,234,0.08) 0%, "
               "rgba(102,126,234,0) 100%)",
    "glass":   "linear-gradient(135deg, rgba(255,255,255,0.04) 0%, "
               "rgba(255,255,255,0.01) 100%)",
    "aurora":  "radial-gradient(ellipse at 20% 0%, rgba(102,126,234,0.12), "
               "transparent 50%), radial-gradient(ellipse at 80% 100%, "
               "rgba(6,182,212,0.10), transparent 50%)",
}

SHADOWS = {
    "soft": "0 1px 2px rgba(0,0,0,0.3)",
    "med":  "0 4px 16px rgba(0,0,0,0.35), 0 1px 3px rgba(0,0,0,0.4)",
    "hard": "0 12px 40px rgba(0,0,0,0.5), 0 4px 12px rgba(0,0,0,0.4)",
    "glow": "0 0 40px rgba(102,126,234,0.25)",
}

SPACING = {1: "4px", 2: "8px", 3: "12px", 4: "16px",
           5: "24px", 6: "32px", 7: "48px", 8: "64px"}

RADII = {"sm": "6px", "md": "8px", "lg": "12px",
         "xl": "16px", "2xl": "20px", "full": "9999px"}

FONT_UI = ('"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", '
           'Roboto, "Helvetica Neue", Arial, sans-serif')
FONT_MONO = ('"JetBrains Mono", ui-monospace, SFMono-Regular, Menlo, '
             'Consolas, monospace')

FONTS_URL = ("https://fonts.googleapis.com/css2?"
             "family=Inter:wght@400;500;600;700;800&"
             "family=JetBrains+Mono:wght@400;500&display=swap")

# Accent name -> (solid colour, rgba glow) for components.
ACCENTS = {
    "indigo": (COLORS["accent_1"], "rgba(102,126,234,0.35)"),
    "violet": (COLORS["accent_2"], "rgba(118,75,162,0.35)"),
    "cyan":   (COLORS["accent_3"], "rgba(6,182,212,0.35)"),
    "success": (COLORS["success"], "rgba(16,185,129,0.35)"),
    "warning": (COLORS["warning"], "rgba(245,158,11,0.35)"),
    "danger": (COLORS["danger"], "rgba(239,68,68,0.35)"),
}


def _compact(css: str) -> str:
    """Make CSS markup safe for st.markdown: strip /* comments */, every
    line's indentation and every blank line, and join into ONE line.

    Why: Streamlit parses st.markdown as CommonMark. An HTML block that
    starts with a <link> tag ends at the first blank line, after which the
    rest prints as text and 4-space-indented lines become code blocks —
    that put raw CSS on the page. One line starting with <style> is a raw
    HTML block that runs to </style> whatever it contains.
    """
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return " ".join(line.strip() for line in css.splitlines()
                    if line.strip())


def build_css() -> str:
    """The full stylesheet as ONE line, <style>…</style>, ready for
    st.markdown(..., unsafe_allow_html=True). Testable without Streamlit."""
    return _compact(_source_css())


def global_css() -> str:
    """Alias of build_css()."""
    return build_css()


def _source_css() -> str:
    """The readable stylesheet. Fonts load through @import inside <style>
    (a <link> tag would start a blank-line-terminated HTML block)."""
    c, g, s, r = COLORS, GRADIENTS, SHADOWS, RADII
    return f"""
<style>
@import url('{FONTS_URL}');
:root {{
  --bg-deep: {c['bg_deep']}; --bg-base: {c['bg_base']};
  --elev-1: {c['bg_elev_1']}; --elev-2: {c['bg_elev_2']};
  --elev-3: {c['bg_elev_3']};
  --border-sub: {c['border_sub']}; --border-hi: {c['border_hi']};
  --text-hi: {c['text_hi']}; --text-mid: {c['text_mid']};
  --text-low: {c['text_low']};
  --a1: {c['accent_1']}; --a2: {c['accent_2']}; --a3: {c['accent_3']};
  --success: {c['success']}; --warning: {c['warning']};
  --danger: {c['danger']}; --info: {c['info']};
  --grad: {g['primary']};
  --sh-soft: {s['soft']}; --sh-med: {s['med']}; --sh-hard: {s['hard']};
  --sh-glow: {s['glow']};
  --r-sm: {r['sm']}; --r-md: {r['md']}; --r-lg: {r['lg']};
  --r-xl: {r['xl']}; --r-2xl: {r['2xl']};
  --ease: cubic-bezier(0.16, 1, 0.3, 1);
  --font-ui: {FONT_UI}; --font-mono: {FONT_MONO};
}}

/* ── base ───────────────────────────────────────────── */
html, body, [class*="css"], .stApp, .stMarkdown, p, li, label, input,
textarea, select, button {{
  font-family: var(--font-ui) !important;
  -webkit-font-smoothing: antialiased;
}}
code, pre, kbd, samp, .cc-mono {{ font-family: var(--font-mono) !important; }}

html, body {{ background-color: var(--bg-base); }}
.stApp {{
  background-color: var(--bg-base);   /* solid fallback below the fold */
  background-image: {g['aurora']},
              linear-gradient(180deg, var(--bg-deep) 0%, var(--bg-base) 100%);
  background-attachment: fixed;
  color: var(--text-hi);
}}
[data-testid="stAppViewContainer"] > .main .block-container,
[data-testid="stMainBlockContainer"] {{
  padding-bottom: 64px; max-width: 1320px;
  animation: cc-fade-in 320ms var(--ease) both;
}}

h1, h2, h3, h4 {{ color: var(--text-hi); letter-spacing: -0.02em; }}
p, li {{ color: var(--text-mid); }}
a {{ color: var(--a3); }}

/* ── Streamlit chrome ───────────────────────────────────
   Hotfix #2: in Streamlit 1.65 the "expand sidebar" arrow
   (stExpandSidebarButton) lives INSIDE stToolbar inside stHeader. Hiding
   stToolbar made a collapsed sidebar impossible to bring back. So the
   toolbar stays; only the items inside it that we do not want are hidden,
   and the header takes no height (no 60px strip) but lets the arrow show. */
[data-testid="stAppViewContainer"] > .main,
[data-testid="stMain"] {{ padding-top: 0 !important; }}
[data-testid="stMainBlockContainer"] {{ padding-top: 1rem !important; }}
header[data-testid="stHeader"] {{
  height: 0 !important; min-height: 0 !important;
  background: transparent !important; overflow: visible !important;
  z-index: 999990;
}}
[data-testid="stMainMenu"], [data-testid="stAppDeployButton"],
[data-testid="stStatusWidget"], [data-testid="stToolbarActions"],
[data-testid="stDecoration"], #MainMenu, footer {{ display: none !important; }}

/* the two sidebar arrows: always visible, in the theme's ink colour */
[data-testid="stSidebarCollapseButton"] {{ visibility: visible !important; }}
[data-testid="stSidebarCollapseButton"] button,
[data-testid="stExpandSidebarButton"] {{
  color: var(--text-hi) !important;
  background: rgba(26,31,46,0.85) !important;
  border: 1px solid var(--border-hi) !important;
  border-radius: var(--r-md) !important;
  box-shadow: var(--sh-med) !important;
  backdrop-filter: blur(10px);
  transition: border-color 180ms var(--ease), box-shadow 180ms var(--ease);
}}
[data-testid="stSidebarCollapseButton"] button:hover,
[data-testid="stExpandSidebarButton"]:hover {{
  border-color: rgba(102,126,234,0.65) !important;
  box-shadow: var(--sh-med), var(--sh-glow) !important;
}}
[data-testid="stExpandSidebarButton"] {{
  position: fixed !important; top: 12px; left: 12px;
  width: 36px; height: 36px; z-index: 999991;
  display: inline-flex !important; align-items: center;
  justify-content: center;
}}
/* collapsed: leave room so the arrow never sits on the page hero */
[data-testid="stAppViewContainer"]:has([data-testid="stSidebar"][aria-expanded="false"])
  [data-testid="stMainBlockContainer"] {{ padding-top: 3.5rem !important; }}
/* default page list is replaced by our own nav in the sidebar */
[data-testid="stSidebarNav"], [data-testid="stSidebarNavSeparator"] {{
  display: none !important;
}}

/* ── sidebar: glass ─────────────────────────────────── */
[data-testid="stSidebar"] {{
  background: linear-gradient(180deg, rgba(26,31,46,0.85) 0%,
              rgba(15,20,25,0.92) 100%) !important;
  backdrop-filter: blur(20px) saturate(140%);
  -webkit-backdrop-filter: blur(20px) saturate(140%);
  border-inline-end: 1px solid transparent;
  border-image: linear-gradient(180deg, rgba(102,126,234,0.45),
                rgba(118,75,162,0.15) 50%, rgba(6,182,212,0.35)) 1;
  box-shadow: var(--sh-hard);
}}
[data-testid="stSidebar"] [data-testid="stSidebarContent"] {{
  padding-top: 8px;
}}
[data-testid="stSidebar"] [data-testid="stPageLink"] a,
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] {{
  border-radius: var(--r-md); padding: 7px 12px; margin: 1px 0;
  color: var(--text-mid) !important; border: 1px solid transparent;
  transition: all 180ms var(--ease);
}}
[data-testid="stSidebar"] [data-testid="stPageLink"] a:hover,
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"]:hover {{
  background: rgba(255,255,255,0.04); color: var(--text-hi) !important;
  border-color: var(--border-sub); transform: translateX(2px);
  box-shadow: var(--sh-soft);
}}
[data-testid="stSidebar"] [data-testid="stPageLink"] a[aria-current="page"],
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"][aria-current="page"] {{
  background: linear-gradient(135deg, rgba(102,126,234,0.22),
              rgba(118,75,162,0.14) 60%, rgba(6,182,212,0.10));
  border-color: rgba(102,126,234,0.45); color: var(--text-hi) !important;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.06), var(--sh-glow);
}}
[data-testid="stSidebar"] [data-testid="stPageLink"] span,
[data-testid="stSidebar"] [data-testid="stPageLink-NavLink"] span {{
  font-size: 13.5px; font-weight: 500;
}}

/* ── quick actions: page links in the main area as glass tiles ── */
[data-testid="stMain"] [data-testid="stPageLink"] a,
[data-testid="stMain"] [data-testid="stPageLink-NavLink"] {{
  display: flex; align-items: center; gap: 10px; width: 100%;
  padding: 14px 16px; border-radius: var(--r-lg);
  background: {g['glass']}, rgba(26,31,46,0.72);
  border: 1px solid var(--border-sub); color: var(--text-hi) !important;
  box-shadow: var(--sh-med), inset 0 1px 0 rgba(255,255,255,0.04);
  backdrop-filter: blur(12px); font-weight: 600;
  transition: transform 200ms var(--ease), box-shadow 200ms var(--ease),
              border-color 200ms var(--ease);
}}
[data-testid="stMain"] [data-testid="stPageLink"] a:hover,
[data-testid="stMain"] [data-testid="stPageLink-NavLink"]:hover {{
  transform: translateY(-2px); border-color: rgba(102,126,234,0.55);
  box-shadow: var(--sh-hard), var(--sh-glow); text-decoration: none;
}}

/* ── buttons: gradient primary, ghost secondary, 3D press ── */
.stButton > button, .stDownloadButton > button,
[data-testid="stFormSubmitButton"] > button {{
  border-radius: var(--r-md); font-weight: 600; font-size: 14px;
  padding: 8px 18px; border: 1px solid var(--border-hi);
  background: rgba(255,255,255,0.03); color: var(--text-hi);
  box-shadow: var(--sh-soft), inset 0 1px 0 rgba(255,255,255,0.05);
  transition: transform 160ms var(--ease), box-shadow 200ms var(--ease),
              border-color 200ms var(--ease), background 200ms var(--ease);
}}
.stButton > button:hover, .stDownloadButton > button:hover {{
  border-color: rgba(102,126,234,0.6); background: rgba(102,126,234,0.08);
  transform: translateY(-1px); box-shadow: var(--sh-med);
  color: var(--text-hi);
}}
.stButton > button:active, .stDownloadButton > button:active {{
  transform: translateY(1px) scale(0.99); box-shadow: var(--sh-soft);
}}
.stButton > button[kind="primary"],
.stButton > button[data-testid="stBaseButton-primary"],
[data-testid="stFormSubmitButton"] > button[kind="primary"] {{
  background: var(--grad); border: 1px solid rgba(255,255,255,0.12);
  color: #fff; box-shadow: var(--sh-med), 0 0 24px rgba(102,126,234,0.30),
  inset 0 1px 0 rgba(255,255,255,0.25);
}}
.stButton > button[kind="primary"]:hover,
.stButton > button[data-testid="stBaseButton-primary"]:hover {{
  filter: brightness(1.08); box-shadow: var(--sh-hard), var(--sh-glow);
}}
.stButton > button:disabled {{ opacity: 0.45; transform: none; }}
.stButton > button:focus-visible {{
  outline: 2px solid var(--a3); outline-offset: 2px;
}}

/* ── inputs: dark glass, accent focus ring ───────────── */
.stTextInput input, .stNumberInput input, .stTextArea textarea,
.stDateInput input, [data-baseweb="select"] > div,
[data-baseweb="input"] {{
  background: rgba(26,31,46,0.75) !important;
  border: 1px solid var(--border-sub) !important;
  border-radius: var(--r-sm) !important; color: var(--text-hi) !important;
  transition: border-color 160ms var(--ease), box-shadow 160ms var(--ease);
}}
.stTextInput input:focus, .stNumberInput input:focus,
.stTextArea textarea:focus {{
  border-color: var(--a1) !important;
  box-shadow: 0 0 0 3px rgba(102,126,234,0.25) !important;
}}
label, .stCheckbox label p, [data-testid="stWidgetLabel"] p {{
  color: var(--text-mid) !important; font-size: 13px; font-weight: 500;
}}

/* ── tabs: pill, gradient underline on active ────────── */
.stTabs [data-baseweb="tab-list"] {{
  gap: 6px; background: rgba(26,31,46,0.6); padding: 6px;
  border-radius: var(--r-full, 9999px); border: 1px solid var(--border-sub);
  width: fit-content;
}}
.stTabs [data-baseweb="tab"] {{
  border-radius: 9999px; padding: 6px 16px; color: var(--text-mid);
  background: transparent; transition: all 180ms var(--ease);
}}
.stTabs [aria-selected="true"] {{
  background: rgba(102,126,234,0.16); color: var(--text-hi);
  box-shadow: inset 0 -2px 0 0 var(--a2);
}}
.stTabs [data-baseweb="tab-highlight"],
.stTabs [data-baseweb="tab-border"] {{ display: none; }}

/* ── native st.metric: card ─────────────────────────── */
[data-testid="stMetric"] {{
  background: {g['glass']}, var(--elev-1);
  border: 1px solid var(--border-sub); border-radius: var(--r-lg);
  padding: 16px 18px; box-shadow: var(--sh-med);
  transition: transform 200ms var(--ease), box-shadow 200ms var(--ease);
}}
[data-testid="stMetric"]:hover {{
  transform: translateY(-2px); box-shadow: var(--sh-hard);
}}
[data-testid="stMetricLabel"] p {{
  background: var(--grad); -webkit-background-clip: text;
  background-clip: text; color: transparent !important;
  font-weight: 600; text-transform: uppercase; letter-spacing: 0.06em;
  font-size: 11.5px;
}}
[data-testid="stMetricValue"] {{
  color: var(--text-hi); font-weight: 700; letter-spacing: -0.02em;
}}

/* ── dataframes, code, alerts, expanders ─────────────── */
[data-testid="stDataFrame"], [data-testid="stTable"] {{
  border: 1px solid var(--border-sub); border-radius: var(--r-lg);
  overflow: hidden; box-shadow: var(--sh-med);
}}
[data-testid="stCode"], .stCodeBlock, pre {{
  background: rgba(15,20,25,0.7) !important;
  border: 1px solid var(--border-sub); border-radius: var(--r-md);
}}
[data-testid="stAlert"] {{
  border-radius: var(--r-lg); border: 1px solid var(--border-sub);
  background: rgba(26,31,46,0.7); backdrop-filter: blur(8px);
}}
[data-testid="stExpander"] {{
  border: 1px solid var(--border-sub) !important;
  border-radius: var(--r-lg) !important;
  background: rgba(26,31,46,0.5);
}}
hr {{ border: none; height: 1px; background: linear-gradient(90deg,
     transparent, var(--border-hi), transparent); }}

/* ── custom components ──────────────────────────────── */
.cc-card {{
  position: relative; background: {g['glass']}, rgba(26,31,46,0.72);
  border: 1px solid var(--border-sub); border-radius: var(--r-lg);
  box-shadow: var(--sh-med), inset 0 1px 0 rgba(255,255,255,0.04);
  backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
  transition: transform 220ms var(--ease), box-shadow 220ms var(--ease),
              border-color 220ms var(--ease);
  animation: cc-slide-in 360ms var(--ease) both;
}}
.cc-card:hover, .card:hover {{
  transform: translateY(-2px) scale(1.005); box-shadow: var(--sh-hard);
  border-color: var(--border-hi);
}}
.cc-pulse {{ animation: cc-pulse 2s ease-in-out infinite; }}

/* ── 3D KPI cards and chart containers ───────────────── */
.kpi-card-3d {{
  background: linear-gradient(145deg, #1E2535 0%, #171C28 100%);
  border-radius: 16px;
  border: 1px solid rgba(102, 126, 234, 0.15);
  padding: 1.25rem 1.5rem;
  box-shadow: 0 1px 0 rgba(255,255,255,0.04) inset,
              0 8px 24px rgba(0,0,0,0.25), 0 2px 4px rgba(0,0,0,0.15);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  position: relative; overflow: hidden;
  min-height: 140px; display: flex; flex-direction: column;
}}
.kpi-card-3d::before {{
  content: ""; position: absolute; top: 0; left: 0; right: 0; height: 1px;
  background: linear-gradient(90deg, transparent, rgba(102,126,234,0.5),
                              transparent);
}}
.kpi-card-3d:hover {{
  transform: translateY(-2px);
  box-shadow: 0 1px 0 rgba(255,255,255,0.06) inset,
              0 12px 32px rgba(102,126,234,0.18), 0 4px 8px rgba(0,0,0,0.2);
}}
.kpi-card-3d .kpi-head {{
  display: flex; align-items: flex-start; justify-content: space-between;
  gap: 10px;
}}
.kpi-card-3d .kpi-label {{
  font-size: 11.5px; font-weight: 600; letter-spacing: 0.07em;
  text-transform: uppercase; color: var(--text-mid); line-height: 1.4;
}}
.kpi-card-3d .kpi-value {{
  font-size: 2.2rem; font-weight: 700; line-height: 1.1;
  letter-spacing: -0.02em; color: var(--text-hi); margin-top: 10px;
  font-variant-numeric: tabular-nums;
}}
.kpi-icon-3d {{
  width: 40px; height: 40px; border-radius: 10px; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center; color: #fff;
  background: linear-gradient(145deg, #667EEA 0%, #764BA2 100%);
  box-shadow: 0 4px 12px rgba(102,126,234,0.35),
              0 1px 0 rgba(255,255,255,0.15) inset;
}}
.kpi-delta {{
  display: inline-flex; align-self: flex-start; margin-top: 10px;
  font-size: 12px; font-weight: 600; padding: 3px 10px;
  border-radius: 9999px; border: 1px solid transparent;
}}
.kpi-delta.good {{ color: #34D399; background: rgba(16,185,129,0.12);
  border-color: rgba(16,185,129,0.30); }}
.kpi-delta.bad {{ color: #F87171; background: rgba(239,68,68,0.12);
  border-color: rgba(239,68,68,0.30); }}
.kpi-delta.info {{ color: #A3B3F5; background: rgba(102,126,234,0.12);
  border-color: rgba(102,126,234,0.30); }}
.kpi-delta.muted {{ color: var(--text-mid); background: rgba(160,174,192,0.08);
  border-color: rgba(160,174,192,0.20); }}
.chart-container-3d,
[class*="st-key-chart3d"] {{
  background: linear-gradient(145deg, #1A1F2E 0%, #151922 100%);
  border-radius: 16px;
  border: 1px solid rgba(102, 126, 234, 0.12);
  padding: 1.5rem;
  box-shadow: 0 8px 24px rgba(0,0,0,0.25),
              0 1px 0 rgba(255,255,255,0.04) inset;
}}

/* ── clearer buttons: solid gradient primary, raised secondary ── */
.btn-primary,
.stApp .stButton > button[kind="primary"],
.stApp .stButton > button[data-testid="stBaseButton-primary"],
.stApp [data-testid="stFormSubmitButton"] > button[kind="primary"] {{
  background: linear-gradient(135deg, #667EEA 0%, #764BA2 100%);
  color: #FFFFFF; font-weight: 600; border: none; border-radius: 10px;
  padding: 0.65rem 1.25rem; box-shadow: 0 4px 12px rgba(102,126,234,0.35);
  transition: all 0.15s ease;
}}
.btn-primary:hover,
.stApp .stButton > button[kind="primary"]:hover,
.stApp .stButton > button[data-testid="stBaseButton-primary"]:hover,
.stApp [data-testid="stFormSubmitButton"] > button[kind="primary"]:hover {{
  filter: brightness(1.1); box-shadow: 0 6px 16px rgba(102,126,234,0.5);
  transform: translateY(-1px); color: #FFFFFF;
}}
.btn-primary:disabled,
.stApp .stButton > button[kind="primary"]:disabled,
.stApp [data-testid="stFormSubmitButton"] > button[kind="primary"]:disabled {{
  opacity: 0.5; filter: grayscale(0.3); box-shadow: none; transform: none;
}}
.btn-secondary,
.stApp .stButton > button[kind="secondary"],
.stApp .stDownloadButton > button,
.stApp [data-testid="stFormSubmitButton"] > button[kind="secondary"],
[data-testid="stMain"] .st-key-quick_actions [data-testid="stPageLink-NavLink"] {{
  background: #252D3F; color: #F7FAFC; font-weight: 500;
  border: 1px solid #4A5568; border-radius: 10px; padding: 0.65rem 1.25rem;
}}
.btn-secondary:hover,
.stApp .stButton > button[kind="secondary"]:hover,
.stApp .stDownloadButton > button:hover,
.stApp [data-testid="stFormSubmitButton"] > button[kind="secondary"]:hover,
[data-testid="stMain"] .st-key-quick_actions [data-testid="stPageLink-NavLink"]:hover {{
  background: #2D3748; border-color: #667EEA; color: #FFFFFF;
}}
[data-testid="stMain"] .st-key-quick_actions [data-testid="stPageLink-NavLink"] {{
  min-height: 64px; padding: 1rem 1.25rem; font-size: 15px; font-weight: 600;
  box-shadow: 0 4px 12px rgba(0,0,0,0.25), 0 1px 0 rgba(255,255,255,0.05) inset;
}}
[data-testid="stMain"] .st-key-quick_actions [data-testid="stPageLink-NavLink"] [data-testid="stIconMaterial"] {{
  color: #8FA2F2; font-size: 22px;
}}

/* ── responsive KPI grid: 4 -> 2 (<900px) -> 1 (<600px) columns ──
   .kpi-grid is the class form. components.kpi_grid() (frozen) emits an
   inline 4-column style and no class, so the same breakpoints also target
   it structurally — any grid of .cc-card cards — with !important, which
   is the only way a stylesheet beats an inline style. */
.kpi-grid {{
  display: grid; grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1rem;
}}
@media (max-width: 900px) {{
  .kpi-grid,
  [data-testid="stMarkdownContainer"] div:has(> .cc-card.card + .cc-card.card) {{
    grid-template-columns: repeat(2, minmax(0, 1fr)) !important;
  }}
}}
@media (max-width: 600px) {{
  .kpi-grid,
  [data-testid="stMarkdownContainer"] div:has(> .cc-card.card + .cc-card.card) {{
    grid-template-columns: 1fr !important;
  }}
}}

/* ── scrollbar ───────────────────────────────────────── */
::-webkit-scrollbar {{ width: 8px; height: 8px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{
  background: rgba(168,178,196,0.14); border-radius: 9999px;
}}
::-webkit-scrollbar-thumb:hover {{ background: rgba(102,126,234,0.55); }}
* {{ scrollbar-width: thin; scrollbar-color: rgba(168,178,196,0.18) transparent; }}

/* ── motion ──────────────────────────────────────────── */
@keyframes cc-fade-in {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
@keyframes cc-slide-in {{
  from {{ opacity: 0; transform: translateY(6px); }}
  to   {{ opacity: 1; transform: translateY(0); }}
}}
@keyframes cc-pulse {{
  0%, 100% {{ box-shadow: 0 0 0 0 rgba(16,185,129,0.45); }}
  50%      {{ box-shadow: 0 0 0 6px rgba(16,185,129,0); }}
}}
@media (prefers-reduced-motion: reduce) {{
  *, *::before, *::after {{
    animation-duration: 1ms !important; transition-duration: 1ms !important;
  }}
}}
</style>
"""


def inject_global_css() -> None:
    """Inject the full CSS override into Streamlit."""
    import streamlit as st
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)


def plotly_layout(**overrides) -> dict:
    """A Plotly layout dict matching the theme: transparent background,
    Inter, subtle grid. Merge into fig.update_layout(...)."""
    layout = {
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
        "font": {"family": FONT_UI, "color": COLORS["text_mid"],
                 "size": 12},
        "margin": {"l": 8, "r": 8, "t": 28, "b": 8},
        "xaxis": {"gridcolor": "rgba(255,255,255,0.05)",
                  "zerolinecolor": "rgba(255,255,255,0.08)",
                  "linecolor": COLORS["border_sub"]},
        "yaxis": {"gridcolor": "rgba(255,255,255,0.05)",
                  "zerolinecolor": "rgba(255,255,255,0.08)",
                  "linecolor": COLORS["border_sub"]},
        "legend": {"bgcolor": "rgba(0,0,0,0)",
                   "font": {"color": COLORS["text_mid"]}},
        "hoverlabel": {"bgcolor": COLORS["bg_elev_2"],
                       "bordercolor": COLORS["border_hi"],
                       "font": {"family": FONT_UI,
                                "color": COLORS["text_hi"]}},
        "colorway": [COLORS["accent_1"], COLORS["accent_2"],
                     COLORS["accent_3"], COLORS["success"],
                     COLORS["warning"], COLORS["danger"]],
    }
    layout.update(overrides)
    return layout


# Built once at import: the single-line, Streamlit-safe stylesheet.
GLOBAL_CSS = build_css()
