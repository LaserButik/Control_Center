# -*- coding: utf-8 -*-
"""Control Center connectors. All offline: the outreach/web-bot paths are
redirected into tmp_path, subprocess is stubbed, and sockets refuse."""

import json
import socket
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from connectors import paths              # noqa: E402
from connectors import outreach as OC     # noqa: E402
from connectors import web_bot as WB      # noqa: E402


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("real network touched")
    monkeypatch.setattr(socket.socket, "connect", boom)


@pytest.fixture
def layout(tmp_path, monkeypatch):
    """Redirect both projects and the CC data dir into tmp_path."""
    runs = tmp_path / "outreach" / "data" / "runs"
    runs.mkdir(parents=True)
    monkeypatch.setattr(paths, "OUTREACH_PROJECT", tmp_path / "outreach_proj")
    monkeypatch.setattr(paths, "OUTREACH_PKG", tmp_path / "outreach")
    monkeypatch.setattr(paths, "OUTREACH_DATA", tmp_path / "outreach" / "data")
    monkeypatch.setattr(paths, "OUTREACH_RUNS", runs)
    monkeypatch.setattr(paths, "WEB_BOT_PROJECT", tmp_path / "webbot")
    monkeypatch.setattr(paths, "WEB_BOT_DB", tmp_path / "webbot" /
                        "bot_data.db")
    monkeypatch.setattr(paths, "WEB_BOT_PID_FILE", tmp_path / "cc_data" /
                        "web_bot.pid")
    monkeypatch.setattr(paths, "CC_DATA", tmp_path / "cc_data")
    return tmp_path


def _make_run(runs: Path, run_id: str):
    d = runs / run_id
    d.mkdir(parents=True)
    (d / "summary.json").write_text(json.dumps(
        {"run_id": run_id, "rows_imported": 39, "mobile_found": 24,
         "messages_queued": 24, "tier_c": 13}), encoding="utf-8")
    (d / "queue.json").write_text(json.dumps(
        {"entries": [{"queue_id": "abc123def456", "status": "pending",
                      "prospect_email": "+971501234567"}]}), encoding="utf-8")
    (d / "prospects.json").write_text(json.dumps({"prospects": []}),
                                      encoding="utf-8")
    return d


def test_outreach_reads_runs_dir_when_present(layout):
    _make_run(paths.OUTREACH_RUNS, "20261007T010101Z")
    _make_run(paths.OUTREACH_RUNS, "20261007T020202Z")
    runs = OC.list_runs()
    assert [r["run_id"] for r in runs] == ["20261007T020202Z",
                                           "20261007T010101Z"]  # newest first
    assert runs[0]["summary"]["mobile_found"] == 24
    one = OC.load_run("20261007T010101Z")
    assert one["ok"] and len(one["entries"]) == 1
    assert one["entries"][0]["queue_id"] == "abc123def456"


def test_outreach_handles_missing_dir(layout):
    # the runs dir exists but is empty, and a bad id is handled
    assert OC.list_runs() == []
    missing = OC.load_run("nope")
    assert missing["ok"] is False and missing["reason"] == "run_not_found"
    assert OC.load_discovery() == {"candidates": [], "ok": False}
    assert OC.load_verifications() == {"results": [], "ok": False}


def test_outreach_run_uses_list_argv_no_shell(layout, monkeypatch):
    captured = {}

    class FakeCompleted:
        returncode = 0
        stdout = "queued 24\nOK"
        stderr = ""

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return FakeCompleted()

    # OUTREACH_PROJECT is a Path; make the "project exists" check pass
    monkeypatch.setattr(Path, "is_dir", lambda self: True)
    monkeypatch.setattr(OC.subprocess, "run", fake_run)
    monkeypatch.setattr(paths, "outreach_python", lambda: "PYEXE")

    r = OC.discover_run(online=True)
    assert r["ok"] and r["exit_code"] == 0
    assert captured["kwargs"]["shell"] is False       # never shell=True
    assert isinstance(captured["cmd"], list)
    assert captured["cmd"][:4] == ["PYEXE", "-m",
                                   "outreach.discover_pipeline", "discover"]
    assert "--online" in captured["cmd"]
    assert r["stdout_tail"].endswith("OK")

    # approve builds the queue_cli argv with the right queue path
    _make_run(paths.OUTREACH_RUNS, "20261007T030303Z")
    OC.approve_queue_entry("20261007T030303Z", "abc123", by="cc")
    cmd = captured["cmd"]
    assert cmd[2:5] == ["outreach.queue_cli", "--queue-path",
                        str(paths.OUTREACH_RUNS / "20261007T030303Z" /
                            "queue.json")]
    assert cmd[5:] == ["approve", "abc123", "--by", "cc"]


def test_web_bot_is_running_false_when_no_pid(layout):
    assert WB.is_running() is False          # no pid file at all
    paths.CC_DATA.mkdir(parents=True, exist_ok=True)
    paths.WEB_BOT_PID_FILE.write_text("999999999", encoding="utf-8")
    assert WB.is_running() is False          # stale pid -> cleaned up
    assert not paths.WEB_BOT_PID_FILE.exists()
    assert WB.stop_bot()["reason"] == "no_pid_file"


def test_web_bot_reads_sqlite_if_present(layout):
    paths.WEB_BOT_PROJECT.mkdir(parents=True)
    conn = sqlite3.connect(str(paths.WEB_BOT_DB))
    conn.executescript(
        "CREATE TABLE sessions (id INTEGER PRIMARY KEY, session_id INTEGER,"
        " timestamp TEXT, scenario TEXT, target TEXT, proxy TEXT,"
        " device TEXT, status TEXT, duration_ms INTEGER, error TEXT);"
        "CREATE TABLE events (id INTEGER PRIMARY KEY, session_id INTEGER,"
        " timestamp TEXT, level TEXT, message TEXT, extra TEXT);")
    conn.executemany(
        "INSERT INTO sessions (session_id,timestamp,target,status,"
        "duration_ms) VALUES (?,?,?,?,?)",
        [(1, "2026-10-07T01:00:00", "Wikipedia AR", "success", 1200),
         (2, "2026-10-07T01:01:00", "BBC Arabic", "success", 1500),
         (3, "2026-10-07T01:02:00", "Al Jazeera", "failed", 800)])
    conn.commit()
    conn.close()
    df = WB.read_sessions()
    assert len(df) == 3 and "target" in df.columns
    stats = WB.get_stats()
    assert stats == {"total": 3, "success": 2, "failed": 1,
                     "success_rate": 66.7, "avg_duration_ms": 1166}
    # a missing db yields an empty frame, not an error
    paths.WEB_BOT_DB.unlink()
    assert WB.read_sessions().empty and WB.get_stats()["total"] == 0


# ───────────── Phase J+K: PDF report generator ─────────────

def _make_full_run(runs, run_id):
    d = runs / run_id
    d.mkdir(parents=True)
    (d / "summary.json").write_text(json.dumps(
        {"run_id": run_id, "rows_imported": 39, "mobile_found": 24,
         "messages_queued": 24, "tier_c": 13, "tier_d": 11}),
        encoding="utf-8")
    (d / "queue.json").write_text(json.dumps({"entries": [
        {"queue_id": "q1", "status": "approved", "prospect_email": "+9715...",
         "subject": "S1", "body": "B1"},
        {"queue_id": "q2", "status": "pending", "prospect_email": "+9715...",
         "subject": "S2", "body": "B2"}]}), encoding="utf-8")
    (d / "prospects.json").write_text(json.dumps({"prospects": [
        {"company_name": "Shop %d" % i, "phone_e164": "+97150000%02d" % i,
         "tier": "C", "score": 45} for i in range(60)]}), encoding="utf-8")
    return d


def test_pdf_generator_requires_reportlab(layout, monkeypatch):
    from reports import pdf_generator as PG
    _make_full_run(paths.OUTREACH_RUNS, "20261007T090909Z")
    monkeypatch.setattr(PG, "_reportlab", lambda: None)
    out = paths.CC_DATA / "r.pdf"
    r = PG.report_for_run("20261007T090909Z",
                          str(paths.OUTREACH_RUNS.parent), str(out))
    assert r == {"ok": False, "reason": "reportlab_not_installed",
                 "out_path": str(out)}
    assert not out.exists()


def test_pdf_generator_writes_pdf_for_fixture_run(layout):
    reportlab = pytest.importorskip("reportlab")
    from reports import pdf_generator as PG
    _make_full_run(paths.OUTREACH_RUNS, "20261007T101010Z")
    out = paths.CC_DATA / "out" / "run.pdf"
    r = PG.report_for_run("20261007T101010Z",
                          str(paths.OUTREACH_RUNS.parent), str(out))
    assert r["ok"] and out.exists()
    head = out.read_bytes()[:5]
    assert head == b"%PDF-" and r["size_bytes"] > 800
    # an unknown run id is reported, not raised
    bad = PG.report_for_run("nope", str(paths.OUTREACH_RUNS.parent),
                            str(out))
    assert bad["reason"] == "run_not_found"
    # the atlas report path works too
    rep = PG.report_for_atlas("backlinks",
                              {"domain": "x.ae", "estimated_backlinks": 10,
                               "referring_domains_count": 2,
                               "referring_domains_sample": ["a.ae", "b.ae"]},
                              str(paths.CC_DATA / "out" / "bl.pdf"))
    assert rep["ok"] and (paths.CC_DATA / "out" / "bl.pdf").exists()


# ───────────── Hotfix #3: verified WhatsApp template defaults ─────────────

def test_send_whatsapp_defaults_to_alpha_intro_en(layout, monkeypatch):
    # the helper with no arguments resolves to the Meta-verified values
    assert OC.resolve_template() == ("alpha_intro_v1_en", "en")
    # blank inputs (an emptied text box) fall back to them too
    assert OC.resolve_template("", "  ") == ("alpha_intro_v1_en", "en")
    assert OC.resolve_template("custom_tpl", "ar") == ("custom_tpl", "ar")

    captured = []

    class Done:
        returncode, stdout, stderr = 0, "", ""

    monkeypatch.setattr(Path, "is_dir", lambda self: True)
    monkeypatch.setattr(OC.subprocess, "run",
                        lambda cmd, **kw: captured.append((cmd, kw)) or Done())
    monkeypatch.setattr(paths, "outreach_python", lambda: "PYEXE")

    OC.send_whatsapp("20261007T053653Z")              # no template args
    cmd, kw = captured[-1]
    assert kw["shell"] is False
    i = cmd.index("--template-name")
    assert cmd[i + 1] == "alpha_intro_v1_en"
    j = cmd.index("--template-language")
    assert cmd[j + 1] == "en" and "en_US" not in cmd
    # the security gate is unchanged: a dry run unless confirmed
    assert "--dry-run" in cmd and "--send-real" not in cmd
    OC.send_whatsapp("20261007T053653Z", confirmed=True)
    real = captured[-1][0]
    assert "--send-real" in real and "--confirmed" in real
    assert "--dry-run" not in real
    assert real[real.index("--template-name") + 1] == "alpha_intro_v1_en"
