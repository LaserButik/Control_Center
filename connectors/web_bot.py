# -*- coding: utf-8 -*-
"""Web_Bot_Project connector — start/stop/read stats."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pandas as pd

WEB_BOT_DIR = Path(r"C:\Users\butik\Documents\Web_Bot_Project")
CC_ROOT = Path(__file__).resolve().parent.parent
PID_FILE = CC_ROOT / "data" / "web_bot.pid"
TARGETS_FILE = CC_ROOT / "data" / "web_bot_targets.json"


def _python_exe() -> Path:
    return WEB_BOT_DIR / "venv" / "Scripts" / "python.exe"


def _db_path() -> Path:
    return WEB_BOT_DIR / "bot_data.db"


# ══════════════════════════════════════════════════════
# PID handling
# ══════════════════════════════════════════════════════
def read_pid():
    """Read PID from file. Returns int or None."""
    if not PID_FILE.exists():
        return None
    try:
        data = json.loads(PID_FILE.read_text(encoding="utf-8"))
        return int(data.get("pid"))
    except Exception:
        # old format: plain int
        try:
            return int(PID_FILE.read_text(encoding="utf-8").strip())
        except Exception:
            return None


def _write_pid(pid: int) -> None:
    PID_FILE.parent.mkdir(parents=True, exist_ok=True)
    PID_FILE.write_text(json.dumps({"pid": pid}), encoding="utf-8")


def _clear_pid() -> None:
    try:
        PID_FILE.unlink()
    except FileNotFoundError:
        pass


# ══════════════════════════════════════════════════════
# Process liveness check (Windows-safe)
# ══════════════════════════════════════════════════════
def _is_pid_alive(pid: int) -> bool:
    """Real liveness check on Windows using OpenProcess."""
    if not pid:
        return False
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.windll.kernel32
        h = kernel32.OpenProcess(
            PROCESS_QUERY_LIMITED_INFORMATION, False, pid
        )
        if not h:
            return False
        try:
            code = wintypes.DWORD()
            if kernel32.GetExitCodeProcess(h, ctypes.byref(code)):
                return code.value == STILL_ACTIVE
            return False
        finally:
            kernel32.CloseHandle(h)
    else:
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


def is_running() -> bool:
    """Returns True if the bot process is alive."""
    pid = read_pid()
    if pid is None:
        return False
    if _is_pid_alive(pid):
        return True
    # stale PID
    _clear_pid()
    return False


# ══════════════════════════════════════════════════════
# Start / Stop
# ══════════════════════════════════════════════════════
def start_bot(targets=None, randomize=False) -> dict:
    """Launch bot.py as a subprocess. Returns {ok, pid, reason}."""
    if is_running():
        return {"ok": False, "reason": "already_running",
                "pid": read_pid()}

    if not _python_exe().exists():
        return {"ok": False, "reason": "python_not_found"}

    if not (WEB_BOT_DIR / "bot.py").exists():
        return {"ok": False, "reason": "bot_py_missing"}

    env = os.environ.copy()

    # Write targets file for config.py
    if targets:
        TARGETS_FILE.parent.mkdir(parents=True, exist_ok=True)
        TARGETS_FILE.write_text(
            json.dumps({"targets": targets, "randomize": bool(randomize)},
                       ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        env["WEB_BOT_TARGETS"] = str(TARGETS_FILE)

    try:
        creationflags = 0
        if sys.platform == "win32":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP

        proc = subprocess.Popen(
            [str(_python_exe()), "bot.py"],
            cwd=str(WEB_BOT_DIR),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        _write_pid(proc.pid)
        return {"ok": True, "pid": proc.pid}
    except Exception as e:
        return {"ok": False, "reason": f"launch_failed:{type(e).__name__}"}


def stop_bot() -> dict:
    """Terminate the bot process tree. Returns {ok, reason}."""
    pid = read_pid()
    if pid is None:
        return {"ok": False, "reason": "no_pid"}

    if not _is_pid_alive(pid):
        _clear_pid()
        return {"ok": True, "reason": "already_stopped"}

    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/T", "/F", "/PID", str(pid)],
                capture_output=True, timeout=10,
            )
        else:
            os.kill(pid, 15)
        _clear_pid()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "reason": f"kill_failed:{type(e).__name__}"}


# ══════════════════════════════════════════════════════
# Stats + Sessions (read-only from SQLite)
# ══════════════════════════════════════════════════════
def get_stats() -> dict:
    """Read bot_data.db for aggregate stats."""
    db = _db_path()
    if not db.exists():
        return {"total": 0, "success": 0, "failed": 0, "success_rate": 0}
    try:
        import sqlite3
        conn = sqlite3.connect(str(db))
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT COUNT(*), "
                "SUM(CASE WHEN status='success' THEN 1 ELSE 0 END), "
                "SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) "
                "FROM sessions"
            )
            row = cur.fetchone()
            total = row[0] or 0
            success = row[1] or 0
            failed = row[2] or 0
            rate = (success / total * 100) if total else 0
            return {
                "total": total, "success": success,
                "failed": failed, "success_rate": rate,
            }
        finally:
            conn.close()
    except Exception:
        return {"total": 0, "success": 0, "failed": 0, "success_rate": 0}


def read_sessions(limit: int = 20) -> pd.DataFrame:
    """Read last N sessions from SQLite."""
    db = _db_path()
    if not db.exists():
        return pd.DataFrame()
    try:
        import sqlite3
        conn = sqlite3.connect(str(db))
        try:
            df = pd.read_sql_query(
                "SELECT id, session_id, timestamp, scenario, target, "
                "proxy, device, status, duration_ms, error "
                "FROM sessions ORDER BY id DESC LIMIT ?",
                conn, params=(limit,),
            )
            return df
        finally:
            conn.close()
    except Exception:
        return pd.DataFrame()