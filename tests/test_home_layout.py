# -*- coding: utf-8 -*-
"""Home layout: eight KPIs, the Activity charts, and the 3D theme classes."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui.i18n import TRANSLATIONS  # noqa: E402

KPI_KEYS = ["outreach_runs", "messages_queued", "messages_sent",
            "replies_total", "discovery_candidates", "directories_ready",
            "bot_sessions", "bot_success_rate"]


def _app() -> str:
    return (ROOT / "app.py").read_text(encoding="utf-8")


def test_home_has_eight_kpis():
    src = _app()
    labels = re.findall(r'"label":\s*t\("home\.(\w+)"', src)
    assert labels == KPI_KEYS
    assert "home.bot_failed" not in src            # a delta, not a 9th card
    assert "kpi_grid_3d(" in src


def test_home_has_activity_section():
    src = _app()
    en = TRANSLATIONS["en"]
    assert en["home.chart_runs"] == "Outreach runs per day"
    assert en["home.chart_tiers"] == "Tier distribution"
    for key in ("home.chart_runs", "home.chart_tiers",
                "home.chart_runs_sub", "home.chart_tiers_sub"):
        assert '"%s"' % key in src, key
        assert TRANSLATIONS["ar"].get(key), key
    assert "go.Pie(" in src and "hole=0.6" in src
    assert '"displayModeBar": False' in src


def test_theme_has_3d_classes():
    src = (ROOT / "ui" / "theme.py").read_text(encoding="utf-8")
    for cls in ("kpi-card-3d", "kpi-icon-3d", "chart-container-3d",
                "btn-primary", "btn-secondary"):
        assert "." + cls in src, cls
    from ui import theme as T
    assert ".kpi-card-3d" in T.GLOBAL_CSS
    assert ".chart-container-3d" in T.GLOBAL_CSS
