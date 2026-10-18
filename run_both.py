"""Run Serper + Playwright together for max coverage.

Usage:
    .\\venv\\Scripts\\python.exe run_both.py
"""
import subprocess
import sys
from pathlib import Path

CC = Path(__file__).resolve().parent
PY = CC / "venv" / "Scripts" / "python.exe"


def run(mode, max_results, country="AE"):
    cmd = [
        str(PY), "-m", "atlas_services.prospect_finder",
        "--all-sectors",
        "--country", country,
        "--mode", mode,
        "--max", str(max_results),
    ]
    print(f"\n{'='*60}\n{mode.upper()} mode — {country} — max {max_results}\n{'='*60}")
    subprocess.run(cmd, cwd=str(CC))


if __name__ == "__main__":
    country = sys.argv[1] if len(sys.argv) > 1 else "AE"
    run("serper", 20, country)      # ~30-60 with emails
    run("playwright", 60, country)  # ~100 with names+phones
    print("\n✅ Done. Check data/prospects/")