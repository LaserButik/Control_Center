# -*- coding: utf-8 -*-
"""Sidebar groups: all pages present, group structure, Settings standalone,
and 8 KPIs on Home."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EXPECTED_PREFIXES = [
    "1_", "2_", "3_", "4_", "5_", "6_", "7_", "8_", "9_", "10_",
    "11_", "12_", "13_", "14_", "15_", "16_", "17_", "18_", "19_",
    "20_", "21_", "22_", "23_", "24_",
]


def test_all_expected_pages_exist():
    for prefix in EXPECTED_PREFIXES:
        matches = list((ROOT / "pages").glob(prefix + "*.py"))
        assert matches, "no page file with prefix %s" % prefix


def test_sidebar_group_definitions_present():
    from ui_common import SIDEBAR_GROUPS
    assert isinstance(SIDEBAR_GROUPS, dict)
    assert set(SIDEBAR_GROUPS) == {"overview", "pipeline", "atlas", "system"}
    for key, group in SIDEBAR_GROUPS.items():
        assert "label" in group, "%s missing label" % key
        assert "pages" in group and len(group["pages"]) >= 1, (
            "%s has no pages" % key)


def test_settings_is_not_in_any_group():
    from ui_common import SIDEBAR_GROUPS
    for key, group in SIDEBAR_GROUPS.items():
        page_nums = [p[0] for p in group["pages"]]
        assert 11 not in page_nums, (
            "Settings (page 11) must not be in group %s" % key)


def test_home_shows_eight_kpis():
    src = (ROOT / "app.py").read_text(encoding="utf-8")
    kpis = [
        "home.outreach_runs",
        "home.messages_queued",
        "home.messages_sent",
        "home.replies_total",
        "home.discovery_candidates",
        "home.directories_ready",
        "home.bot_sessions",
        "home.bot_success_rate",
    ]
    for k in kpis:
        assert k in src, "KPI %s not found in app.py" % k
