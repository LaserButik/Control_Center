# -*- coding: utf-8 -*-
"""Daily Automation — control the daily auto-outreach task."""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
import pandas as pd

from ui_common import page_config, render_sidebar, page_header, ROOT
from ui import components as C
from ui.i18n import t, get_lang

page_config(st, "Daily Automation")
render_sidebar(st)

lang = get_lang()
page_header(st, "Daily Automation",
            "Automate daily outreach: find → enrich → clean → send → follow-up",
            "schedule")

TASK_NAME = "AI_Mentors_Daily_Auto"
CC = Path(__file__).resolve().parent.parent
BAT = CC / "run_daily.bat"
LOG_DIR = CC / "data" / "scheduler"
LOG_FILE = LOG_DIR / "daily_auto.log"
REPORTS = CC / "data" / "reports"
DUBAI = timezone(timedelta(hours=4))


# ══════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════
def schtasks(*args, timeout=15) -> tuple:
    try:
        r = subprocess.run(
            ["schtasks"] + list(args),
            capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace",
        )
        return r.returncode == 0, (r.stdout or "") + (r.stderr or "")
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


def task_exists() -> bool:
    ok, _ = schtasks("/Query", "/TN", TASK_NAME)
    return ok


def task_info() -> dict:
    if not task_exists():
        return {}
    ok, out = schtasks("/Query", "/TN", TASK_NAME, "/V", "/FO", "LIST")
    if not ok:
        return {}
    info = {}
    for line in out.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            info[k.strip()] = v.strip()
    return info


def is_admin() -> bool:
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def list_reports(days: int = 14) -> list:
    out = []
    if not REPORTS.exists():
        return out
    for f in sorted(REPORTS.glob("daily_*.json"), reverse=True)[:days]:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            m = d.get("metrics", {})
            out.append({
                "date": d.get("date", "?"),
                "run_id": (d.get("run_id", "") or "")[:12],
                "duration_s": d.get("duration_s", 0),
                "serper": m.get("serper_found", 0),
                "enriched": m.get("enriched", 0),
                "sent": m.get("sent", 0),
                "followups": m.get("followups", 0),
                "failed": m.get("failed", 0),
            })
        except Exception:
            continue
    return out


# ══════════════════════════════════════════════════════════
# UI
# ══════════════════════════════════════════════════════════
st.caption("Full pipeline: Find (Serper + Playwright) → Enrich → "
           "Clean → Filter → Send → Follow-ups → Report")

# ── 1. Status ─────────────────────────────────────────────
st.subheader("1 · Status")

exists = task_exists()
info = task_info()
is_enabled = info.get("Scheduled Task State", "").lower() == "enabled"
last_run = info.get("Last Run Time", "—")
next_run = info.get("Next Run Time", "—")
last_result = info.get("Last Result", "—")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Task", "✅ Installed" if exists else "❌ Not installed")
c2.metric("State", "🟢 Enabled" if is_enabled else
          ("⚪ Disabled" if exists else "—"))
c3.metric("Last Run", last_run if exists else "—")
c4.metric("Next Run", next_run if exists else "—")

if exists and last_result not in ("0", "?", "—"):
    st.warning(f"⚠️ Last result code: {last_result}")

if not is_admin():
    st.info("ℹ️ Install/Delete need **Administrator** PowerShell. "
            "Run Now / Enable / Disable work without admin.")

st.divider()

# ── 2. Actions ────────────────────────────────────────────
st.subheader("2 · Actions")

col = st.columns(4)

with col[0]:
    if st.button("📥 Install Task",
                 disabled=exists or not is_admin(),
                 help="Register the daily task at 09:00 Dubai. Needs admin."):
        if not BAT.exists():
            st.error(f"❌ Missing {BAT}")
        else:
            ok, out = schtasks(
                "/Create", "/TN", TASK_NAME,
                "/TR", f'"{BAT}"',
                "/SC", "DAILY", "/ST", "09:00",
                "/RL", "HIGHEST", "/F",
            )
            if ok:
                st.success("✅ Installed")
                st.rerun()
            else:
                st.error(f"Failed: {out[:300]}")

with col[1]:
    if st.button("▶️ Run Now", disabled=not exists,
                 help="Trigger the daily task immediately."):
        ok, out = schtasks("/Run", "/TN", TASK_NAME)
        if ok:
            st.success("✅ Started. Check reports below in ~20 min.")
            st.rerun()
        else:
            st.error(f"Failed: {out[:300]}")

with col[2]:
    if exists and not is_enabled:
        if st.button("🟢 Enable"):
            ok, out = schtasks("/Change", "/TN", TASK_NAME, "/ENABLE")
            if ok:
                st.rerun()
            else:
                st.error(out[:200])
    elif exists and is_enabled:
        if st.button("⏸️ Disable"):
            ok, out = schtasks("/Change", "/TN", TASK_NAME, "/DISABLE")
            if ok:
                st.rerun()
            else:
                st.error(out[:200])

with col[3]:
    if exists and is_admin():
        confirm = st.checkbox("Confirm delete", key="del_confirm")
        if st.button("🗑️ Delete Task", disabled=not confirm):
            ok, out = schtasks("/Delete", "/TN", TASK_NAME, "/F")
            if ok:
                st.success("Deleted")
                st.rerun()
            else:
                st.error(out[:200])

st.divider()

# ── 3. Manual run ─────────────────────────────────────────
st.subheader("3 · Manual Test (without Windows Task)")
st.caption("Run daily_auto.py directly. Safer for testing.")

m1, m2, m3 = st.columns(3)
with m1:
    dry = st.checkbox("Dry run (no emails sent)", value=True,
                      key="manual_dry")
with m2:
    skip_finder = st.checkbox("Skip finder (reuse files)",
                              value=False, key="manual_skip_finder")
with m3:
    skip_send = st.checkbox("Skip sending", value=False,
                            key="manual_skip_send")

if st.button("🚀 Run daily_auto.py now", type="primary"):
    cmd = [str(CC / "venv" / "Scripts" / "python.exe"),
           str(CC / "daily_auto.py")]
    if dry:
        cmd.append("--dry-run")
    if skip_finder:
        cmd.append("--skip-finder")
    if skip_send:
        cmd.append("--skip-send")

    # Fix Unicode crashes on Windows subprocess
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    with st.spinner("Running... may take 5-25 minutes"):
        try:
            r = subprocess.run(cmd, cwd=str(CC), capture_output=True,
                               text=True, timeout=2400,
                               encoding="utf-8", errors="replace",
                               env=env)
            if r.returncode == 0:
                st.success("✅ Finished successfully")
            else:
                st.warning(f"⚠️ Exit code: {r.returncode}")
            with st.expander("stdout", expanded=True):
                st.code(r.stdout[-8000:] if r.stdout else "(empty)")
            if r.stderr:
                with st.expander("stderr"):
                    st.code(r.stderr[-2000:])
        except subprocess.TimeoutExpired:
            st.error("⏱️ Timed out after 40 minutes")
        except Exception as e:
            st.error(f"❌ {e}")

st.divider()

# ── 4. Recent reports ─────────────────────────────────────
st.subheader("4 · Recent Daily Reports")
reports = list_reports(14)
if reports:
    st.dataframe(pd.DataFrame(reports),
                 use_container_width=True, hide_index=True)
else:
    st.info("No reports yet.")

st.divider()
st.caption("💡 Task runs at 09:00 Dubai daily. "
           "Install requires Administrator.")