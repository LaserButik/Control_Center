# -*- coding: utf-8 -*-
"""The design system: theme tokens, icons, components, and no emoji.
Pure functions — no Streamlit runtime, no network."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui import components as C          # noqa: E402
from ui import icons as I               # noqa: E402
from ui import theme as T               # noqa: E402

# Emoji and pictograph blocks, plus the emoji variation selector and ZWJ.
# Typographic arrows, dashes and the middle dot are deliberately allowed.
EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿"
                   "⌀-⏿️‍]")


def test_theme_defines_required_colors():
    required = {"bg_deep", "bg_base", "bg_elev_1", "bg_elev_2", "bg_elev_3",
                "border_sub", "border_hi", "text_hi", "text_mid", "text_low",
                "accent_1", "accent_2", "accent_3", "success", "warning",
                "danger", "info"}
    assert required <= set(T.COLORS)
    for v in T.COLORS.values():
        assert re.fullmatch(r"#[0-9A-Fa-f]{6}", v), v
    assert T.COLORS["accent_1"] == "#667EEA"
    assert set(T.SPACING) == set(range(1, 9))
    assert T.RADII["lg"] == "12px" and T.RADII["md"] == "8px"
    css = T.build_css()
    for needle in ("Inter", "JetBrains+Mono", "backdrop-filter",
                   "stSidebarNav", "@keyframes cc-fade-in", "::-webkit-scrollbar",
                   "translateY(-2px)", "prefers-reduced-motion"):
        assert needle in css, needle


def test_gradients_include_primary():
    assert {"primary", "subtle", "glass", "aurora"} <= set(T.GRADIENTS)
    p = T.GRADIENTS["primary"]
    assert p.startswith("linear-gradient(135deg")
    for c in ("#667EEA", "#764BA2"):
        assert c in p


def test_shadows_has_three_levels():
    assert {"soft", "med", "hard"} <= set(T.SHADOWS)
    # depth increases: the blur radius of the first layer grows
    blur = [int(re.search(r"0 \d+px (\d+)px", T.SHADOWS[k]).group(1))
            for k in ("soft", "med", "hard")]
    assert blur == sorted(blur) and len(set(blur)) == 3


def test_icons_all_return_svg_strings():
    names = {"home", "spider", "upload", "search", "check", "list", "send",
             "inbox", "bot", "globe", "settings", "users", "link", "sword",
             "flask", "file", "share", "play", "stop", "refresh", "download",
             "external", "alert", "trend_up", "trend_down", "activity",
             "shield", "database", "calendar", "chart", "sparkle",
             "arrow_right", "arrow_up_right", "plus", "minus", "x", "filter",
             "star", "bookmark", "clock", "copy"}
    assert names <= set(I.ICONS)
    for name, svg in I.ICONS.items():
        assert isinstance(svg, str), name
        assert svg.startswith("<svg") and svg.endswith("</svg>"), name
        assert 'stroke="currentColor"' in svg and 'viewBox="0 0 24 24"' in svg
        assert 'width="20"' in svg and 'stroke-width="1.75"' in svg
    assert 'width="32"' in I.icon("home", 32)
    assert I.icon("no-such-icon").startswith("<svg")   # safe fallback


def test_components_return_html_strings():
    outs = {
        "hero": C.hero("Title <x>", "Sub", I.ICONS["home"]),
        "glass_card": C.glass_card("Card", "<b>body</b>", accent="violet"),
        "metric_3d": C.metric_3d("Runs", "12", delta="+3", trend="up",
                                 icon_svg=I.ICONS["activity"]),
        "status_pill": C.status_pill("OK", "success"),
        "action_button": C.action_button("Go", href="/x", help="tip"),
        "section_header": C.section_header("Section", "sub"),
        "divider": C.divider(),
        "empty_state": C.empty_state("Empty", "Nothing yet", I.ICONS["inbox"]),
        "code_block": C.code_block("line1\nline2", "stdout"),
        "kpi_grid": C.kpi_grid([{"label": "A", "value": 1},
                                C.metric_3d("B", "2")], columns=2),
        "wordmark": C.wordmark(), "nav_label": C.nav_label("Pipeline"),
    }
    for name, html in outs.items():
        assert isinstance(html, str) and html.startswith("<"), name
        # flat markup: Streamlit renders indented / multi-line HTML as code
        assert "\n" not in html, name
    assert "Title &lt;x&gt;" in outs["hero"]                 # escaped
    assert "<b>body</b>" in outs["glass_card"]               # trusted html
    assert "line1<br>line2" in outs["code_block"]
    assert outs["kpi_grid"].count("cc-card") == 2
    assert "repeat(2," in outs["kpi_grid"]
    assert "%%" not in "".join(outs.values())                # no fmt leak


def test_no_emoji_in_ui_module_files():
    files = sorted((ROOT / "ui").glob("*.py"))
    assert files, "ui/ has no modules"
    offenders = []
    for f in files:
        for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(),
                                 1):
            if EMOJI.search(line):
                offenders.append("%s:%d" % (f.name, i))
    assert offenders == []


def test_css_is_not_rendered_as_text():
    """Regression: the stylesheet once printed as raw text on the page.
    st.markdown parses CommonMark, where an HTML block that starts with a
    <link> tag ends at the first blank line and 4-space-indented lines turn
    into code blocks. The CSS must be one raw <style> block on one line."""
    import inspect
    css = T.GLOBAL_CSS if hasattr(T, "GLOBAL_CSS") else T.global_css()
    assert isinstance(css, str) and css == T.build_css() == T.global_css()
    # no unfilled format placeholders or %-escape leaks
    assert "{css}" not in css and "={css}" not in css and "%%" not in css
    # one line, no indentation, no blank lines -> nothing becomes markdown
    assert "\n" not in css and "\r" not in css
    assert css == css.strip()
    # starts with <style (CommonMark raw-HTML type 1, ends at </style>),
    # exactly one style block, and no <link> (a blank-line-ended block)
    assert css.startswith("<style>") and css.endswith("</style>")
    assert css.count("<style>") == 1 and css.count("</style>") == 1
    assert "<link" not in css
    assert css.startswith("<style> @import url(")          # fonts first
    assert css.count("{") == css.count("}")
    assert "/*" not in css                                  # comments gone
    # and it is injected as HTML, not as markdown text
    src = inspect.getsource(T.inject_global_css)
    assert "unsafe_allow_html=True" in src and "GLOBAL_CSS" in src


def _css_rules(css):
    """(selector, declarations) for every innermost rule, including those
    nested in @media blocks."""
    return [(sel.strip(), decls.strip())
            for sel, decls in re.findall(r"([^{}]+)\{([^{}]*)\}", css)]


def test_sidebar_collapse_arrow_not_hidden():
    """Hotfix #2: hiding stToolbar hid the 'expand sidebar' arrow, which in
    Streamlit 1.65 lives inside stToolbar inside stHeader — a collapsed
    sidebar could never come back."""
    protected = ("stSidebarCollapseButton", "stSidebarCollapsedControl",
                 "collapsedControl", "stExpandSidebarButton",
                 # its containers in 1.65: hiding either hides the arrow
                 "stToolbar", "stHeader")
    for sel, decls in _css_rules(T.GLOBAL_CSS):
        hides = re.search(r"display:\s*none|visibility:\s*hidden", decls)
        if not hides:
            continue
        for tid in protected:
            assert '"%s"' % tid not in sel, (tid, sel, decls)
    # and the arrows are positively styled to be visible in ink colour
    rules = dict(_css_rules(T.GLOBAL_CSS))
    collapse = [d for s, d in rules.items()
                if '"stSidebarCollapseButton"' in s and "visibility" in d]
    assert collapse and "visible" in collapse[0]
    expand = [d for s, d in rules.items()
              if s.strip() == '[data-testid="stExpandSidebarButton"]'
              and "position" in d]
    assert expand and "fixed" in expand[0]
    assert any('"stExpandSidebarButton"' in s and "var(--text-hi)" in d
               for s, d in rules.items())


def test_no_top_padding_left_on_main():
    rules = _css_rules(T.GLOBAL_CSS)
    main = [d for s, d in rules
            if ("stAppViewContainer" in s or '"stMain"' in s)
            and "padding-top" in d]
    assert any(re.search(r"padding-top:\s*0\s*!important", d) for d in main)
    header = [d for s, d in rules if 'header[data-testid="stHeader"]' in s]
    assert header and re.search(r"height:\s*0\s*!important", header[0])
    assert re.search(r"min-height:\s*0\s*!important", header[0])
    assert re.search(r"background:\s*transparent\s*!important", header[0])


def test_kpi_grid_is_responsive():
    css = T.GLOBAL_CSS
    blocks = {bp: re.search(r"@media \(max-width: %dpx\) \{(.*?\})\s*\}" % bp,
                            css) for bp in (900, 600)}
    assert blocks[900] and blocks[600], "both breakpoints must exist"
    assert ".kpi-grid" in blocks[900].group(1)
    assert "repeat(2, minmax(0, 1fr)) !important" in blocks[900].group(1)
    assert ".kpi-grid" in blocks[600].group(1)
    assert "grid-template-columns: 1fr !important" in blocks[600].group(1)
    # the frozen kpi_grid() markup (inline style, no class) is reached too
    assert "div:has(> .cc-card.card + .cc-card.card)" in blocks[900].group(1)
    assert ".kpi-grid" in css and "repeat(4, minmax(0, 1fr))" in css
