# -*- coding: utf-8 -*-
"""Themed Plotly figures. Plotly is imported lazily: every function returns
None when it is not installed, and callers show an empty state instead.

Bars use a colour scale along the brand gradient (indigo -> violet -> cyan)
so each bar carries a step of the gradient — Plotly cannot paint a CSS
gradient inside one bar.
"""

from __future__ import annotations

from .theme import COLORS, plotly_layout

BRAND_SCALE = [[0.0, COLORS["accent_1"]], [0.5, COLORS["accent_2"]],
               [1.0, COLORS["accent_3"]]]


def _go():
    try:
        import plotly.graph_objects as go
        return go
    except ImportError:
        return None


def available() -> bool:
    return _go() is not None


def line(x, y, *, title: str = "", height: int = 280):
    go = _go()
    if go is None:
        return None
    fig = go.Figure(go.Scatter(
        x=list(x), y=list(y), mode="lines+markers",
        line={"width": 2.5, "color": COLORS["accent_1"], "shape": "spline"},
        marker={"size": 6, "color": COLORS["accent_3"],
                "line": {"width": 1.5, "color": COLORS["bg_base"]}},
        fill="tozeroy", fillcolor="rgba(99,102,241,0.12)",
        hovertemplate="%{x}<br><b>%{y}</b><extra></extra>"))
    fig.update_layout(**plotly_layout(title={"text": title, "x": 0,
                                             "font": {"size": 13}},
                                      height=height, showlegend=False))
    return fig


def donut(labels, values, *, title: str = "", height: int = 280):
    go = _go()
    if go is None:
        return None
    palette = [COLORS["accent_1"], COLORS["accent_2"], COLORS["accent_3"],
               COLORS["text_low"], COLORS["success"], COLORS["warning"]]
    fig = go.Figure(go.Pie(
        labels=list(labels), values=list(values), hole=0.66, sort=False,
        marker={"colors": palette[:len(list(labels))],
                "line": {"color": COLORS["bg_base"], "width": 3}},
        textinfo="none",
        hovertemplate="%{label}: <b>%{value}</b> (%{percent})<extra></extra>"))
    total = sum(values) if values else 0
    fig.update_layout(**plotly_layout(
        title={"text": title, "x": 0, "font": {"size": 13}}, height=height,
        annotations=[{"text": "<b>%s</b><br><span style='font-size:11px'>"
                      "total</span>" % total, "showarrow": False,
                      "font": {"size": 22, "color": COLORS["text_hi"]}}],
        legend={"orientation": "h", "y": -0.08, "x": 0.5,
                "xanchor": "center", "bgcolor": "rgba(0,0,0,0)"}))
    return fig


def bars(labels, values, *, title: str = "", height: int = 300,
         horizontal: bool = False):
    go = _go()
    if go is None:
        return None
    labels, values = list(labels), list(values)
    common = {"marker": {"color": values or [0], "colorscale": BRAND_SCALE,
                         "line": {"width": 0}, "cornerradius": 6},
              "hovertemplate": "%{label}<br><b>%{value}</b><extra></extra>"
              if not horizontal else "%{y}<br><b>%{x}</b><extra></extra>"}
    if horizontal:
        trace = go.Bar(x=values, y=labels, orientation="h", **common)
    else:
        trace = go.Bar(x=labels, y=values, **common)
    fig = go.Figure(trace)
    fig.update_layout(**plotly_layout(title={"text": title, "x": 0,
                                             "font": {"size": 13}},
                                      height=height, showlegend=False,
                                      bargap=0.35))
    return fig


def histogram(values, *, title: str = "", height: int = 280, nbins: int = 20):
    go = _go()
    if go is None:
        return None
    fig = go.Figure(go.Histogram(
        x=list(values), nbinsx=nbins,
        marker={"color": COLORS["accent_2"], "line": {"width": 0},
                "opacity": 0.9},
        hovertemplate="score %{x}<br><b>%{y}</b> prospects<extra></extra>"))
    fig.update_layout(**plotly_layout(title={"text": title, "x": 0,
                                             "font": {"size": 13}},
                                      height=height, showlegend=False,
                                      bargap=0.08))
    return fig


def show(st, fig, *, empty_title: str = "Chart unavailable",
         empty_body: str = "Install plotly to see this chart.") -> None:
    """Render a figure, or an empty state if Plotly is missing."""
    from . import components as C
    from .icons import ICONS
    if fig is None:
        C.render(st, C.empty_state(empty_title, empty_body, ICONS["chart"]))
        return
    st.plotly_chart(fig, width="stretch",
                    config={"displayModeBar": False, "responsive": True})
