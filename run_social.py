import sys
from pathlib import Path
from datetime import datetime

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

CC = Path(__file__).resolve().parent
sys.path.insert(0, str(CC))

from atlas_services import social_engine

if __name__ == "__main__":
    res = social_engine.run_daily_social(dry_run=False, image_mode="auto")
    print(f"[{datetime.now().strftime('%H:%M')}] Social Post Result: {res}")