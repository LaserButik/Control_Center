# -*- coding: utf-8 -*-
"""ATLAS service: prepare per-platform text for MANUAL publishing.

Reads a JSON file of items ({title, body, url}) and writes one plain-text
file per platform that the user can copy and paste. It NEVER calls any
social network API and NEVER posts anything — it only writes text files.

Platforms: twitter (280), linkedin (3000 + a first-comment hashtag block),
facebook, telegram (Markdown), generic (raw).

CLI:
    python -m atlas_services.content_distribution --input X \\
        --platforms twitter,linkedin --out-dir Y
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PLATFORMS = ("twitter", "linkedin", "facebook", "telegram", "generic")
LIMITS = {"twitter": 280, "linkedin": 3000, "facebook": 63206,
          "telegram": 4096, "generic": None}


def _slug(text: str, n: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (text or "item").lower()).strip("-")
    return (s or "item")[:n]


def _hashtags(text: str, k: int = 5) -> str:
    words = re.findall(r"[A-Za-z][A-Za-z0-9]{3,}", text or "")
    seen, tags = set(), []
    for w in words:
        wl = w.lower()
        if wl not in seen:
            seen.add(wl)
            tags.append("#" + w)
        if len(tags) >= k:
            break
    return " ".join(tags)


def _twitter(item: dict) -> str:
    base = (item.get("title") or "").strip()
    url = (item.get("url") or "").strip()
    limit = LIMITS["twitter"]
    room = limit - (len(url) + 1 if url else 0)
    body = (item.get("body") or "").strip()
    text = base if base else body
    if len(text) > room:
        text = text[:max(0, room - 1)].rstrip() + "…"
    return (text + ("\n" + url if url else "")).strip()


def _linkedin(item: dict) -> str:
    parts = [p for p in ((item.get("title") or "").strip(),
                         (item.get("body") or "").strip()) if p]
    text = "\n\n".join(parts)[:LIMITS["linkedin"]]
    url = (item.get("url") or "").strip()
    if url:
        text += "\n\n" + url
    tags = _hashtags((item.get("title") or "") + " " +
                     (item.get("body") or ""))
    if tags:
        text += "\n\n---\nFirst comment:\n" + tags
    return text.strip()


def _plain(item: dict, limit) -> str:
    parts = [p for p in ((item.get("title") or "").strip(),
                         (item.get("body") or "").strip(),
                         (item.get("url") or "").strip()) if p]
    text = "\n\n".join(parts)
    return text[:limit] if limit else text


def _render(platform: str, item: dict) -> str:
    if platform == "twitter":
        return _twitter(item)
    if platform == "linkedin":
        return _linkedin(item)
    return _plain(item, LIMITS.get(platform))


def prepare_posts(content_path: str, platforms: list, out_dir: str) -> dict:
    try:
        data = json.loads(Path(content_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return {"ok": False, "reason": "input_unreadable:%s"
                % type(e).__name__, "out_dir": out_dir, "files_written": []}
    items = data.get("items", data) if isinstance(data, dict) else data
    items = [i for i in (items or []) if isinstance(i, dict)]
    chosen = [p for p in (platforms or []) if p in PLATFORMS]
    if not chosen:
        return {"ok": False, "reason": "no_valid_platform",
                "out_dir": out_dir, "files_written": []}
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    written = []
    for i, item in enumerate(items, 1):
        for platform in chosen:
            name = "%02d_%s_%s.txt" % (i, _slug(item.get("title")), platform)
            path = out / name
            path.write_text(_render(platform, item), encoding="utf-8")
            written.append(str(path))
    return {"ok": True, "items": len(items), "files_written": written,
            "out_dir": str(out), "reason": None}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m atlas_services.content_distribution")
    ap.add_argument("--input", required=True)
    ap.add_argument("--platforms", default="generic")
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args(argv)
    platforms = [p.strip() for p in a.platforms.split(",") if p.strip()]
    r = prepare_posts(a.input, platforms, a.out_dir)
    sys.stdout.write(json.dumps({k: r[k] for k in r
                                 if k != "files_written"},
                                ensure_ascii=False) + "\n")
    return 0 if r.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
