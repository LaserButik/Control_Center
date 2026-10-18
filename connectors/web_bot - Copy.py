# -*- coding: utf-8 -*-
"""Read-only reader and process controller for the Web Bot project.

Reads its SQLite database and log files, and can start or stop its bot.py
as a subprocess — the same command the user could run by hand. It edits
nothing in Web_Bot_Project: the PID file it writes lives under
Control_Center/data/, never inside the bot's folder.
"""

from __future__ import annotations

import json
import os
import signal
import sqlite3
import subprocess
import time
from pathlib import Path

import pandas as pd

from . import paths

_EMPTY_SESSIONS = ["id", "session_id", "timestamp", "scenario", "target",
                   "proxy", "device", "status", "duration_ms", "error"]
_EMPTY_EVENTS = ["id", "session_id", "timestamp", "level", "message",
                 "extra"]


def _query(sql: str, columns: list[str]) -> pd.DataFrame:
    if not paths.WEB_BOT_DB.exists():
        return pd.DataFrame(columns=columns)
    try:
        conn = sqlite3.connect("file:%s?mode=ro" % paths.WEB_BOT_DB.as_posix(),
                               uri=True)
    except sqlite3.Error:
        conn = sqlite3.connect(str(paths.WEB_BOT_DB))
    try:
        return pd.read_sql_query(sql, conn)
    except Exception:
        return pd.DataFrame(columns=columns)
    finally:
        conn.close()


def read_sessions(limit: int = 200) -> pd.DataFrame:
    return _query("SELECT * FROM sessions ORDER BY timestamp DESC LIMIT %d"
                  % int(limit), _EMPTY_SESSIONS)


def read_events(limit: int = 200) -> pd.DataFrame:
    return _query("SELECT * FROM events ORDER BY timestamp DESC LIMIT %d"
                  % int(limit), _EMPTY_EVENTS)


def get_stats() -> dict:
    df = read_sessions(limit=100000)
    total = len(df)
    if total == 0:
        return {"total": 0, "success": 0, "failed": 0, "success_rate": 0.0,
                "avg_duration_ms": 0}
    success = int((df["status"] == "success").sum())
    failed = int((df["status"] == "failed").sum())
    avg = int(pd.to_numeric(df["duration_ms"], errors="coerce").mean() or 0)
    return {"total": total, "success": success, "failed": failed,
            "success_rate": round(success / total * 100, 1),
            "avg_duration_ms": avg}


# ───────────────────────── process control ─────────────────────────

_WINDOWS = os.name == "nt"
STOP_WAIT_S = 5.0


def _win_process_info(pid: int) -> tuple[bool, float | None, str | None]:
    """(alive, creation time as epoch seconds, executable path) via the
    Win32 API. os.kill(pid, 0) is NOT a probe on Windows: signal 0 is
    CTRL_C_EVENT, so it sends a console Ctrl+C instead of testing."""
    import ctypes
    from ctypes import wintypes
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.restype = wintypes.HANDLE
    k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    k32.GetExitCodeProcess.argtypes = [wintypes.HANDLE,
                                       ctypes.POINTER(wintypes.DWORD)]
    k32.GetProcessTimes.argtypes = [wintypes.HANDLE] + \
        [ctypes.POINTER(wintypes.FILETIME)] * 4
    k32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD)]
    handle = k32.OpenProcess(0x1000, False, int(pid))  # QUERY_LIMITED_INFO
    if not handle:
        return ctypes.get_last_error() == 5, None, None  # 5: access denied
    try:
        code = wintypes.DWORD()
        alive = bool(k32.GetExitCodeProcess(handle, ctypes.byref(code))) \
            and code.value == 259                        # STILL_ACTIVE
        times = [wintypes.FILETIME() for _ in range(4)]
        created = None
        if k32.GetProcessTimes(handle, *(ctypes.byref(t) for t in times)):
            ticks = (times[0].dwHighDateTime << 32) | times[0].dwLowDateTime
            created = ticks / 1e7 - 11644473600          # 1601 -> 1970
        buf = ctypes.create_unicode_buffer(1024)
        size = wintypes.DWORD(1024)
        exe = buf.value if k32.QueryFullProcessImageNameW(
            handle, 0, buf, ctypes.byref(size)) else None
        return alive, created, exe
    finally:
        k32.CloseHandle(handle)


def _read_record() -> dict | None:
    """{"pid", "created"} from the PID file. Accepts the old plain-number
    format too (then "created" is None)."""
    try:
        raw = paths.WEB_BOT_PID_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    if isinstance(data, int):
        return {"pid": data, "created": None}
    if isinstance(data, dict) and isinstance(data.get("pid"), int):
        return {"pid": data["pid"], "created": data.get("created")}
    return None


def _read_pid() -> int | None:
    rec = _read_record()
    return rec["pid"] if rec else None


def _remove_pid_file() -> None:
    try:
        paths.WEB_BOT_PID_FILE.unlink()
    except OSError:
        pass


def _alive(pid: int) -> bool:
    if pid is None:
        return False
    if _WINDOWS:
        return _win_process_info(pid)[0]
    try:
        os.kill(pid, 0)                      # POSIX: signal 0 is a probe
    except ProcessLookupError:
        return False
    except PermissionError:
        return True                          # exists, not ours to signal
    except OSError:
        return False
    return True


def _is_ours(rec: dict) -> bool:
    """Is the live process with this PID the one we started? Windows reuses
    PIDs, so a stale file must never get an unrelated program killed: match
    the creation time we recorded, or (old file format) a python image."""
    if not _WINDOWS:
        return True
    alive, created, exe = _win_process_info(rec["pid"])
    if not alive:
        return False
    if rec.get("created") is not None and created is not None:
        return abs(created - float(rec["created"])) < 2.0
    return os.path.basename(exe or "").lower().startswith("python")


def is_running() -> bool:
    rec = _read_record()
    if rec is None:
        return False
    if _alive(rec["pid"]) and _is_ours(rec):
        return True
    _remove_pid_file()                       # stale: the process is gone
    return False


def start_bot(total_visits: int | None = None) -> dict:
    """Launch Web_Bot_Project/bot.py in its own venv, cwd = its folder.
    List argv, never shell=True. Writes the PID under Control_Center/data/."""
    if is_running():
        return {"ok": False, "reason": "already_running", "pid": _read_pid()}
    if not paths.WEB_BOT_ENTRY.exists():
        return {"ok": False, "reason": "bot_entry_not_found",
                "path": str(paths.WEB_BOT_ENTRY)}
    paths.ensure_cc_data()
    env = dict(os.environ)
    if total_visits is not None:
        # The bot reads TOTAL_VISITS from its env/config; we pass it through
        # without editing the bot's own .env.
        env["TOTAL_VISITS"] = str(int(total_visits))
    cmd = [paths.web_bot_python(), "bot.py"]
    try:
        proc = subprocess.Popen(cmd, cwd=str(paths.WEB_BOT_PROJECT),
                                env=env, shell=False,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                                start_new_session=not _WINDOWS)
    except OSError as e:
        return {"ok": False, "reason": "launch_failed", "error": str(e)[:200]}
    created = _win_process_info(proc.pid)[1] if _WINDOWS else None
    paths.WEB_BOT_PID_FILE.write_text(json.dumps(
        {"pid": proc.pid, "created": created}), encoding="utf-8")
    return {"ok": True, "pid": proc.pid, "cmd": cmd,
            "cwd": str(paths.WEB_BOT_PROJECT)}


def _terminate_tree(pid: int) -> str | None:
    """End the process and everything it started (a Windows venv python.exe
    is a launcher whose child is the real interpreter, so killing only the
    PID we hold leaves the bot running). Returns an error text or None."""
    if _WINDOWS:
        try:
            p = subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"],
                               capture_output=True, timeout=20, shell=False)
        except (OSError, subprocess.SubprocessError) as e:
            return "%s: %s" % (type(e).__name__, str(e)[:160])
        if p.returncode != 0:
            return (p.stderr or p.stdout).decode("utf-8", "replace") \
                .strip()[:200] or "taskkill exit %s" % p.returncode
        return None
    try:
        os.killpg(os.getpgid(pid), signal.SIGTERM)
    except OSError:
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError as e:
            return "%s: %s" % (type(e).__name__, str(e)[:160])
    return None


def stop_bot(wait_s: float = STOP_WAIT_S) -> dict:
    """Stop the bot we started. {"ok", "pid", "was_alive"} on success;
    {"ok": False, "reason", "error"} when it could not be stopped."""
    rec = _read_record()
    if rec is None:
        return {"ok": False, "reason": "no_pid_file"}
    pid = rec["pid"]
    if not _alive(pid) or not _is_ours(rec):
        _remove_pid_file()                   # already gone (or PID reused)
        return {"ok": True, "pid": pid, "was_alive": False}
    error = _terminate_tree(pid)
    deadline = time.monotonic() + max(0.0, wait_s)
    while _alive(pid) and time.monotonic() < deadline:
        time.sleep(0.2)
    if _alive(pid):
        return {"ok": False, "reason": "still_running", "pid": pid,
                "error": error or "the process did not exit"}
    _remove_pid_file()
    return {"ok": True, "pid": pid, "was_alive": True}


def tail_log(lines: int = 40) -> list[str]:
    log_dir = paths.WEB_BOT_LOGS
    if not log_dir.is_dir():
        return []
    files = [p for p in log_dir.iterdir() if p.is_file()]
    if not files:
        return []
    newest = max(files, key=lambda p: p.stat().st_mtime)
    try:
        return newest.read_text(encoding="utf-8",
                                errors="replace").splitlines()[-int(lines):]
    except OSError:
        return []


def reachable() -> bool:
    return paths.WEB_BOT_PROJECT.is_dir()
