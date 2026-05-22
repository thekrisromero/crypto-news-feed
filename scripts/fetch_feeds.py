#!/usr/bin/env python3
"""
Fetch all configured RSS feeds, normalize the items, score by relevance,
and write data/latest.json + data/archive/YYYY-MM-DD.json.

Designed to run as a scheduled GitHub Action. Errors are tolerated per-feed:
a single broken feed shouldn't break the whole run.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import feedparser
import requests
from dateutil import parser as dateparser

REPO_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = REPO_ROOT / "feeds.json"
LATEST_PATH = REPO_ROOT / "data" / "latest.json"
ARCHIVE_DIR = REPO_ROOT / "data" / "archive"

USER_AGENT = "crypto-news-feed/1.0 (+https://github.com/)"
TIMEOUT_SECONDS = 25
MAX_SUMMARY_CHARS = 600


def load_config() -> dict[str, Any]:
    with CONFIG_PATH.open() as f:
        return json.load(f)


def parse_date(raw: Any) -> datetime | None:
    if not raw:
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    try:
        dt = dateparser.parse(str(raw))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def score_item(title: str, summary: str, priority_keywords: list[str]) -> int:
    haystack = f"{title} {summary}".lower()
    return sum(1 for kw in priority_keywords if kw.lower() in haystack)


def is_excluded(title: str, summary: str, negative_keywords: list[str]) -> bool:
    haystack = f"{title} {summary}".lower()
    return any(kw.lower() in haystack for kw in negative_keywords)


def fetch_one_feed(feed_config: dict[str, Any], cutoff: datetime, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    url = feed_config["url"]
    name = feed_config["name"]
    items: list[dict[str, Any]] = []
    try:
        resp = requests.get(url, timeout=TIMEOUT_SECONDS, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        parsed = feedparser.parse(resp.content)
    except Exception as exc:
        print(f"[WARN] {name} fetch failed: {exc}", file=sys.stderr)
        return []

    for entry in parsed.entries[: cfg.get("max_items_per_feed", 25)]:
        published_raw = (
            entry.get("published")
            or entry.get("updated")
            or entry.get("pubDate")
            or entry.get("created")
        )
        published = parse_date(published_raw)
        if published is None or published < cutoff:
            continue

        title = strip_html(entry.get("title", "")).strip()
        summary = strip_html(
            entry.get("summary") or entry.get("description") or ""
        )[:MAX_SUMMARY_CHARS]

        if not title:
            continue

        if is_excluded(title, summary, cfg.get("filter_keywords_negative", [])):
            continue

        link = entry.get("link") or ""
        score = score_item(title, summary, cfg.get("filter_keywords_priority", []))

        items.append({
            "source": name,
            "tier": feed_config.get("tier"),
            "topics": feed_config.get("topics", []),
            "title": title,
            "summary": summary,
            "link": link,
            "published": published.astimezone(timezone.utc).isoformat(),
            "relevance_score": score,
        })

    print(f"[OK]   {name}: kept {len(items)} items", file=sys.stderr)
    return items


def main() -> int:
    cfg = load_config()
    lookback_days = cfg.get("lookback_days", 8)
    cutoff = datetime.now(timezone.utc) - timedelta(days=lookback_days)

    all_items: list[dict[str, Any]] = []
    feed_status: list[dict[str, Any]] = []

    for feed_cfg in cfg.get("feeds", []):
        items = fetch_one_feed(feed_cfg, cutoff, cfg)
        all_items.extend(items)
        feed_status.append({"name": feed_cfg["name"], "url": feed_cfg["url"], "kept": len(items)})

    # Sort by relevance descending, then date descending
    all_items.sort(key=lambda x: (-x["relevance_score"], x["published"]), reverse=False)
    all_items.sort(key=lambda x: x["published"], reverse=True)
    all_items.sort(key=lambda x: x["relevance_score"], reverse=True)

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "lookback_days": lookback_days,
        "total_items": len(all_items),
        "feed_status": feed_status,
        "items": all_items,
    }

    LATEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    LATEST_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False))

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    archive_path = ARCHIVE_DIR / f"{today}.json"
    archive_path.write_text(json.dumps(output, indent=2, ensure_ascii=False))

    print(
        f"\nWrote {len(all_items)} items across {len(feed_status)} feeds → {LATEST_PATH.relative_to(REPO_ROOT)}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
