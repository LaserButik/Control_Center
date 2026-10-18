# -*- coding: utf-8 -*-
"""HTML components for the Control Center. Every function returns an HTML
string; render it with render(st, html) or
st.markdown(html, unsafe_allow_html=True).

Note: Streamlit's markdown turns indented lines and blank lines inside a
block into code. Every component therefore returns flat HTML with no leading
   indentation and no blank lines — keep it that way when editing.

Text arguments are HTML-escaped. Arguments named *_html or *_svg are
inserted as-is (trusted markup built by this module or icons.py).

Interactive controls: action_button() renders a styled <a>/<button> for
links and visual CTAs only — it cannot trigger Python. For anything that
runs code, use st.button (restyled globally by theme.py). That is the
trade-off: pixel-perfect markup vs. a real Streamlit callback.
"""

from __future__ import annotations

from html import escape

from .theme import ACCENTS, COLORS, GRADIENTS, SHADOWS, SPACING

_KIND_COLOURS = {
    "success": COLORS["success"], "warning": COLORS["warning"],
    "danger": COLORS["danger"], "info": COLORS["info"],
    "neutral": COLORS["text_low"],
}
_TREND = {"up": (COLORS["success"], "trend_up"),
          "down": (COLORS["danger"], "trend_down"),
          "flat": (COLORS["text_low"], "minus")}


def _flat(*parts: str) -> str:
    """Join markup with no newlines or indentation (see module note)."""
    return "".join(p.strip() for p in parts if p)


def render(st, html: str) -> None:
    st.markdown(html, unsafe_allow_html=True)


def _icon_badge(icon_svg: str, colour: str = None, size: int = 36) -> str:
    if not icon_svg:
        return ""
    colour = colour or COLORS["accent_1"]
    return _flat(
        '<span style="display:inline-flex;align-items:center;'
        'justify-content:center;width:%dpx;height:%dpx;border-radius:10px;'
        'color:%s;background:linear-gradient(135deg,rgba(102,126,234,0.18),'
        'rgba(6,182,212,0.10));border:1px solid rgba(102,126,234,0.30);'
        'box-shadow:inset 0 1px 0 rgba(255,255,255,0.08);flex-shrink:0;">'
        % (size, size, colour), icon_svg, '</span>')


def hero(title: str, subtitle: str, icon_svg: str = "") -> str:
    """3D hero: gradient title, aurora glow, thin gradient rule."""
    return _flat(
        '<div class="cc-card" style="padding:32px 32px 28px;margin:0 0 24px;'
        'border-radius:20px;overflow:hidden;background:%s,%s,'
        'rgba(17,20,27,0.72);box-shadow:%s;">'
        % (GRADIENTS["aurora"], GRADIENTS["glass"], SHADOWS["hard"]),
        '<div style="display:flex;align-items:center;gap:16px;">',
        _icon_badge(icon_svg, COLORS["text_hi"], 48),
        '<div style="min-width:0;">',
        '<h1 style="margin:0;font-size:34px;line-height:1.1;font-weight:800;'
        'letter-spacing:-0.03em;background:%s;-webkit-background-clip:text;'
        'background-clip:text;color:transparent;">%s</h1>'
        % (GRADIENTS["primary"], escape(title)),
        '<p style="margin:8px 0 0;font-size:15px;color:%s;">%s</p>'
        % (COLORS["text_mid"], escape(subtitle)) if subtitle else "",
        '</div></div>',
        '<div style="margin-top:22px;height:1px;background:linear-gradient('
        '90deg,rgba(102,126,234,0.65),rgba(118,75,162,0.35) 45%,'
        'rgba(6,182,212,0.0));"></div>',
        '</div>')


def glass_card(title: str, body_html: str, *, accent: str = "indigo",
               padding: int = 5) -> str:
    """A frosted-glass card with depth and a gradient accent edge."""
    colour, glow = ACCENTS.get(accent, ACCENTS["indigo"])
    pad = SPACING.get(padding, SPACING[5])
    head = (('<div style="font-size:13px;font-weight:600;letter-spacing:'
             '0.04em;text-transform:uppercase;color:%s;margin-bottom:10px;">'
             '%s</div>') % (colour, escape(title))) if title else ""
    return _flat(
        '<div class="cc-card card" style="padding:%s;margin:0 0 16px;'
        'border-top:1px solid %s;box-shadow:%s,0 -1px 18px -10px %s;">'
        % (pad, colour, SHADOWS["med"], glow),
        head, '<div style="color:%s;font-size:14px;line-height:1.6;">'
        % COLORS["text_mid"], body_html, '</div></div>')


def metric_3d(label: str, value: str, *, delta: str = "",
              trend: str = "flat", icon_svg: str = "") -> str:
    """A 3D metric card: big value, delta badge, small icon."""
    colour, trend_icon = _TREND.get(trend, _TREND["flat"])
    from .icons import icon
    delta_html = ""
    if delta:
        delta_html = _flat(
            '<span style="display:inline-flex;align-items:center;gap:4px;'
            'font-size:12px;font-weight:600;color:%s;padding:2px 8px;'
            'border-radius:9999px;background:rgba(255,255,255,0.04);'
            'border:1px solid rgba(255,255,255,0.06);">' % colour,
            icon(trend_icon, 12, 2), escape(str(delta)), '</span>')
    return _flat(
        '<div class="cc-card card" style="padding:18px 18px 16px;'
        'min-height:118px;display:flex;flex-direction:column;'
        'justify-content:space-between;">',
        '<div style="display:flex;align-items:center;justify-content:'
        'space-between;gap:8px;">',
        '<span style="font-size:11.5px;font-weight:600;letter-spacing:'
        '0.07em;text-transform:uppercase;background:%s;'
        '-webkit-background-clip:text;background-clip:text;'
        'color:transparent;">%s</span>' % (GRADIENTS["primary"],
                                          escape(label)),
        _icon_badge(icon_svg, COLORS["accent_3"], 30), '</div>',
        '<div style="display:flex;align-items:baseline;gap:10px;'
        'margin-top:10px;flex-wrap:wrap;">',
        '<span style="font-size:30px;font-weight:700;letter-spacing:'
        '-0.03em;color:%s;font-variant-numeric:tabular-nums;">%s</span>'
        % (COLORS["text_hi"], escape(str(value))),
        delta_html, '</div></div>')


def status_pill(text: str, kind: str = "neutral") -> str:
    """A glass pill with a coloured dot."""
    colour = _KIND_COLOURS.get(kind, _KIND_COLOURS["neutral"])
    pulse = " cc-pulse" if kind == "success" else ""
    return _flat(
        '<span style="display:inline-flex;align-items:center;gap:7px;'
        'padding:4px 11px 4px 9px;border-radius:9999px;font-size:12px;'
        'font-weight:500;color:%s;background:rgba(255,255,255,0.035);'
        'border:1px solid rgba(255,255,255,0.07);backdrop-filter:blur(6px);'
        'margin:2px 4px 2px 0;">' % COLORS["text_mid"],
        '<span class="%s" style="width:7px;height:7px;border-radius:50%%;'
        'background:%s;box-shadow:0 0 8px %s;"></span>'
        % (pulse.strip(), colour, colour),
        escape(text), '</span>')


def action_button(label: str, *, kind: str = "primary", icon_svg: str = "",
                  href: str = "", help: str = "") -> str:
    """A fully styled link-button. Visual / navigation only — it cannot
    run Python; use st.button (themed) for actions."""
    primary = kind == "primary"
    style = (
        "display:inline-flex;align-items:center;gap:8px;padding:10px 18px;"
        "border-radius:8px;font-size:14px;font-weight:600;"
        "text-decoration:none;transition:all 180ms cubic-bezier(.16,1,.3,1);"
        + ("color:#fff;background:%s;border:1px solid rgba(255,255,255,0.12);"
           "box-shadow:%s,0 0 24px rgba(102,126,234,0.3);"
           % (GRADIENTS["primary"], SHADOWS["med"]) if primary else
           "color:%s;background:rgba(255,255,255,0.03);border:1px solid %s;"
           "box-shadow:%s;" % (COLORS["text_hi"], COLORS["border_hi"],
                               SHADOWS["soft"])))
    tag = "a" if href else "span"
    href_attr = ' href="%s" target="_self"' % escape(href) if href else ""
    title_attr = ' title="%s"' % escape(help) if help else ""
    return _flat('<%s class="cc-btn"%s%s style="%s">' % (tag, href_attr,
                                                        title_attr, style),
                 icon_svg, escape(label), '</%s>' % tag)


def section_header(title: str, subtitle: str = "") -> str:
    sub = ('<p style="margin:4px 0 0;font-size:13.5px;color:%s;">%s</p>'
           % (COLORS["text_low"], escape(subtitle))) if subtitle else ""
    return _flat(
        '<div style="margin:28px 0 14px;">',
        '<h3 style="margin:0;font-size:18px;font-weight:650;'
        'letter-spacing:-0.01em;color:%s;display:flex;align-items:center;'
        'gap:10px;">' % COLORS["text_hi"],
        '<span style="width:4px;height:18px;border-radius:2px;'
        'background:%s;"></span>' % GRADIENTS["primary"],
        escape(title), '</h3>', sub, '</div>')


def divider() -> str:
    return ('<div style="height:1px;margin:24px 0;background:linear-gradient('
            '90deg,transparent,rgba(102,126,234,0.45),rgba(6,182,212,0.35),'
            'transparent);"></div>')


def empty_state(title: str, body: str, icon_svg: str = "") -> str:
    return _flat(
        '<div class="cc-card" style="padding:40px 24px;text-align:center;'
        'border-style:dashed;">',
        '<div style="display:flex;justify-content:center;margin-bottom:14px;">',
        _icon_badge(icon_svg, COLORS["text_mid"], 44), '</div>',
        '<div style="font-size:16px;font-weight:600;color:%s;">%s</div>'
        % (COLORS["text_hi"], escape(title)),
        '<div style="margin-top:6px;font-size:13.5px;color:%s;max-width:'
        '520px;margin-left:auto;margin-right:auto;">%s</div>'
        % (COLORS["text_low"], escape(body)), '</div>')


def code_block(text: str, lang: str = "") -> str:
    label = ('<div style="font-size:11px;letter-spacing:0.08em;'
             'text-transform:uppercase;color:%s;margin-bottom:8px;">%s</div>'
             % (COLORS["text_low"], escape(lang))) if lang else ""
    body = escape(text or "").replace("\n", "<br>")
    return _flat(
        '<div style="background:rgba(8,9,12,0.75);border:1px solid %s;'
        'border-radius:8px;padding:14px 16px;margin:8px 0 14px;'
        'box-shadow:inset 0 1px 0 rgba(255,255,255,0.03);overflow-x:auto;">'
        % COLORS["border_sub"], label,
        '<div class="cc-mono" style="font-size:12.5px;line-height:1.65;'
        'color:%s;white-space:nowrap;">%s</div></div>'
        % (COLORS["text_mid"], body))


def kpi_grid(items: list, columns: int = 4) -> str:
    """Lay out metric cards in a CSS grid. Each item is either an HTML
    string or a dict of metric_3d(**item) arguments."""
    cells = [it if isinstance(it, str) else metric_3d(**it)
             for it in (items or [])]
    return _flat(
        '<div style="display:grid;grid-template-columns:repeat(%d,minmax(0,'
        '1fr));gap:16px;margin:0 0 8px;">' % max(1, int(columns)),
        *cells, '</div>')


_DELTA_TONES = ("good", "bad", "info", "muted")


def kpi_card_3d(label: str, value, *, delta: str = "", tone: str = "info",
                icon_svg: str = "") -> str:
    """A raised KPI card (.kpi-card-3d): label and gradient icon on top, big
    number, optional plain-word delta badge coloured by meaning."""
    tone = tone if tone in _DELTA_TONES else "info"
    badge = ('<span class="kpi-delta %s">%s</span>' % (tone, escape(str(delta)))
             if delta else "")
    icon_html = ('<span class="kpi-icon-3d">%s</span>' % icon_svg
                 if icon_svg else "")
    return _flat(
        '<div class="kpi-card-3d">',
        '<div class="kpi-head"><span class="kpi-label">%s</span>%s</div>'
        % (escape(label), icon_html),
        '<div class="kpi-value">%s</div>' % escape(str(value)),
        badge, '</div>')


def kpi_grid_3d(items: list) -> str:
    """kpi_card_3d cards in the responsive .kpi-grid (4 / 2 / 1 columns)."""
    cells = [it if isinstance(it, str) else kpi_card_3d(**it)
             for it in (items or [])]
    return _flat('<div class="kpi-grid" style="margin:0 0 8px;">', *cells,
                 '</div>')


def chart_header(title: str, subtitle: str = "") -> str:
    """Title and one-line explanation at the top of a chart container."""
    sub = ('<div style="margin-top:4px;font-size:12.5px;color:%s;">%s</div>'
           % (COLORS["text_low"], escape(subtitle))) if subtitle else ""
    return _flat('<div style="margin-bottom:6px;">',
                 '<div style="font-size:15px;font-weight:650;color:%s;">%s'
                 '</div>' % (COLORS["text_hi"], escape(title)), sub, '</div>')


def wordmark(text: str = "AI Mentors", sub: str = "Control Center") -> str:
    """The gradient wordmark with an SVG logo mark, for the sidebar."""
    mark = ('<svg width="28" height="28" viewBox="0 0 32 32" fill="none" '
            'aria-hidden="true"><defs><linearGradient id="ccg" x1="0" y1="0" '
            'x2="32" y2="32"><stop stop-color="#6366F1"/>'
            '<stop offset=".5" stop-color="#8B5CF6"/>'
            '<stop offset="1" stop-color="#06B6D4"/></linearGradient></defs>'
            '<rect x="1" y="1" width="30" height="30" rx="9" '
            'stroke="url(#ccg)" stroke-width="2"/>'
            '<path d="M9 22 15 9l3 7 2-3 3 9" stroke="url(#ccg)" '
            'stroke-width="2.2" stroke-linecap="round" '
            'stroke-linejoin="round"/></svg>')
    return _flat(
        '<div style="display:flex;align-items:center;gap:11px;'
        'padding:6px 4px 14px;">', mark, '<div>',
        '<div style="font-size:17px;font-weight:800;letter-spacing:-0.02em;'
        'background:%s;-webkit-background-clip:text;background-clip:text;'
        'color:transparent;line-height:1.1;">%s</div>'
        % (GRADIENTS["primary"], escape(text)),
        '<div style="font-size:11.5px;color:%s;letter-spacing:0.04em;">%s'
        '</div>' % (COLORS["text_low"], escape(sub)), '</div></div>')


def nav_label(text: str) -> str:
    """A small uppercase section label for the sidebar nav."""
    return ('<div style="font-size:10.5px;font-weight:600;letter-spacing:'
            '0.12em;text-transform:uppercase;color:%s;margin:14px 0 4px 6px;">'
            '%s</div>' % (COLORS["text_low"], escape(text)))
