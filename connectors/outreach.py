# -*- coding: utf-8 -*-
"""Read-only reader and subprocess launcher for the outreach pipeline.

This module deliberately does NOT import the `outreach` package: that would
pull outreach's dependencies into the Control Center venv. Instead it reads
the JSON files the pipeline writes under outreach/data/, and runs pipeline
commands by spawning the OUTREACH venv's python with a list argv (never
shell=True), cwd set to the outreach project.

Every run_* function returns {"ok", "exit_code", "stdout_tail",
"stderr_tail", "cmd"} and never raises for a non-zero exit.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from . import paths

STDOUT_TAIL_LINES = 30
SUBPROCESS_TIMEOUT_S = 1800


# ───────────────────────── read side (JSON on disk) ─────────────────────

def _read_json(path: Path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _run_dir(run_id: str) -> Path:
    return paths.OUTREACH_RUNS / run_id


def list_runs() -> list[dict]:
    """Every run under outreach/data/runs/, newest id first, each with its
    summary (or just the id when the summary is missing)."""
    base = paths.OUTREACH_RUNS
    if not base.is_dir():
        return []
    runs = []
    for d in sorted((p for p in base.iterdir() if p.is_dir()),
                    key=lambda p: p.name, reverse=True):
        summary = _read_json(d / "summary.json") or {}
        runs.append({"run_id": d.name, "path": str(d),
                     "has_queue": (d / "queue.json").exists(),
                     "summary": summary})
    return runs


def load_run(run_id: str) -> dict:
    """A run's summary, queue entries, prospects and send-result files."""
    d = _run_dir(run_id)
    if not d.is_dir():
        return {"ok": False, "reason": "run_not_found", "run_id": run_id}
    queue = _read_json(d / "queue.json") or {}
    prospects = _read_json(d / "prospects.json") or {}
    sends = [_read_json(p) for p in sorted(d.glob("send_results_*.json"))]
    return {"ok": True, "run_id": run_id, "path": str(d),
            "summary": _read_json(d / "summary.json") or {},
            "entries": queue.get("entries", []),
            "prospects": prospects.get("prospects", []),
            "send_results": [s for s in sends if s]}


def load_discovery() -> dict:
    return _read_json(paths.OUTREACH_DATA / "discovery_candidates.json") or {
        "candidates": [], "ok": False}


def load_verifications() -> dict:
    return _read_json(paths.OUTREACH_DATA / "verified_directories.json") or {
        "results": [], "ok": False}


def queue_path(run_id: str) -> Path:
    return _run_dir(run_id) / "queue.json"


# ───────────────────────── run side (subprocess) ─────────────────────────

def _run(argv_tail: list[str], *, cwd: Path | None = None) -> dict:
    """Spawn the outreach venv python with `-m outreach.<...>`. List argv,
    never shell=True. Returns tails of stdout/stderr and the exit code."""
    cmd = [paths.outreach_python(), "-m", *argv_tail]
    out = {"ok": False, "exit_code": None, "stdout_tail": "",
           "stderr_tail": "", "cmd": cmd}
    if not paths.OUTREACH_PROJECT.is_dir():
        out["stderr_tail"] = "outreach project not found: %s" % \
            paths.OUTREACH_PROJECT
        return out
    try:
        p = subprocess.run(cmd, cwd=str(cwd or paths.OUTREACH_PROJECT),
                           capture_output=True, text=True, shell=False,
                           timeout=SUBPROCESS_TIMEOUT_S)
    except subprocess.TimeoutExpired:
        out["stderr_tail"] = "timed out after %ds" % SUBPROCESS_TIMEOUT_S
        return out
    except OSError as e:
        out["stderr_tail"] = "could not launch: %s" % e
        return out
    out["exit_code"] = p.returncode
    out["ok"] = p.returncode == 0
    out["stdout_tail"] = _tail(p.stdout)
    out["stderr_tail"] = _tail(p.stderr)
    return out


def _tail(text: str, n: int = STDOUT_TAIL_LINES) -> str:
    lines = (text or "").splitlines()
    return "\n".join(lines[-n:])


def discover_run(online: bool = False, out: str | None = None) -> dict:
    out = out or str(paths.OUTREACH_DATA / "discovery_candidates.json")
    argv = ["outreach.discover_pipeline", "discover", "--out", out]
    if online:
        argv.append("--online")
    return _run(argv)


def verify_run(inp: str | None = None, out: str | None = None) -> dict:
    inp = inp or str(paths.OUTREACH_DATA / "discovery_candidates.json")
    out = out or str(paths.OUTREACH_DATA / "verified_directories.json")
    return _run(["outreach.discover_pipeline", "verify", "--input", inp,
                 "--out", out, "--online"])


def scrape_argv(url: str, max_prospects: int = 5, delay: float = 5.0,
                out: str | None = None) -> list[str]:
    """The `-m ...` argv scrape_url runs — exposed so a page can preview
    the exact command without running it."""
    out = out or str(paths.OUTREACH_DATA / "scrapes" / "scrape_cc.json")
    return ["outreach.real_scrape", "--target-url", url, "--output", out,
            "--max-prospects", str(int(max_prospects)),
            "--delay", str(float(delay)), "--acknowledge-tos"]


def scrape_url(url: str, max_prospects: int = 5, delay: float = 5.0,
               out: str | None = None) -> dict:
    return _run(scrape_argv(url, max_prospects, delay, out))


def import_csv(csv_path: str, source_url: str = "",
               out_dir: str | None = None) -> dict:
    out_dir = out_dir or str(paths.OUTREACH_RUNS)
    return _run(["outreach.pipeline", "import", "--csv", csv_path,
                 "--source-url", source_url, "--out-dir", out_dir])


def score_run(scrape_path: str, out: str | None = None,
              site_check: bool = True) -> dict:
    out = out or (scrape_path.replace(".json", "_scored.json"))
    argv = ["outreach.discover_pipeline", "score", "--input", scrape_path,
            "--out", out]
    if not site_check:
        argv.append("--no-site-check")
    return _run(argv)


def approve_queue_entry(run_id: str, queue_id: str,
                        by: str = "control_center") -> dict:
    return _run(["outreach.queue_cli", "--queue-path",
                 str(queue_path(run_id)), "approve", queue_id, "--by", by])


def reject_queue_entry(run_id: str, queue_id: str, by: str = "control_center",
                       reason: str = "") -> dict:
    return _run(["outreach.queue_cli", "--queue-path",
                 str(queue_path(run_id)), "reject", queue_id, "--by", by,
                 "--reason", reason])


# Verified with Meta: the approved template is "alpha_intro_v1_en" in
# language "en" (not en_US). Without explicit flags the pipeline falls back
# to "alpha_intro_v1"/"ar", which fails with Meta error #132001.
DEFAULT_TEMPLATE_NAME = "alpha_intro_v1_en"
DEFAULT_TEMPLATE_LANGUAGE = "en"


def resolve_template(template_name: str | None = None,
                     template_language: str | None = None
                     ) -> tuple[str, str]:
    """The (name, language) actually sent: blank or None -> the verified
    defaults."""
    return ((template_name or "").strip() or DEFAULT_TEMPLATE_NAME,
            (template_language or "").strip() or DEFAULT_TEMPLATE_LANGUAGE)


def send_whatsapp(run_id: str, confirmed: bool = False,
                  template_name: str = DEFAULT_TEMPLATE_NAME,
                  template_language: str = DEFAULT_TEMPLATE_LANGUAGE) -> dict:
    """Dry run unless confirmed=True, which adds --send-real --confirmed.
    The outreach pipeline still applies its own approved-queue gate. The
    template flags are always passed, so the pipeline never falls back to
    its own default."""
    name, language = resolve_template(template_name, template_language)
    argv = ["outreach.pipeline", "send", "--run-dir",
            str(_run_dir(run_id)), "--approved-only"]
    argv += (["--send-real", "--confirmed"] if confirmed else ["--dry-run"])
    argv += ["--template-name", name, "--template-language", language]
    return _run(argv)


# ───────────────────────── Supabase (read-only check) ─────────────────────

def supabase_status() -> dict:
    """Whether outreach's db.py would find Supabase configured. Runs in the
    outreach venv so its dotenv/.env.local is what answers; no row is read,
    nothing is printed. {"configured": bool} or a reason."""
    code = ("import json,db;"
            "print(json.dumps({'configured': bool(db.configured())}))")
    r = _run_raw([paths.outreach_python(), "-c", code])
    if r["ok"]:
        try:
            return {"ok": True, **json.loads(r["stdout_tail"].splitlines()
                                             [-1])}
        except (ValueError, IndexError):
            return {"ok": False, "configured": False, "reason": "bad_output"}
    return {"ok": False, "configured": False,
            "reason": (r["stderr_tail"] or "db.py unavailable")[:120]}


def _run_raw(cmd: list[str]) -> dict:
    out = {"ok": False, "exit_code": None, "stdout_tail": "",
           "stderr_tail": "", "cmd": cmd}
    try:
        p = subprocess.run(cmd, cwd=str(paths.OUTREACH_PROJECT),
                           capture_output=True, text=True, shell=False,
                           timeout=60)
    except (OSError, subprocess.TimeoutExpired) as e:
        out["stderr_tail"] = str(e)[:200]
        return out
    out.update(ok=p.returncode == 0, exit_code=p.returncode,
               stdout_tail=_tail(p.stdout), stderr_tail=_tail(p.stderr))
    return out


def reachable() -> bool:
    return paths.OUTREACH_PKG.is_dir()
