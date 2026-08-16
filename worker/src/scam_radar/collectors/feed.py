from __future__ import annotations

from datetime import datetime

import feedparser

from scam_radar.collectors.base import DiscoveredItem


def discover_feed(body: bytes, *, max_items: int = 50) -> list[DiscoveredItem]:
    parsed = feedparser.parse(body)
    if parsed.bozo and not parsed.entries:
        raise ValueError("invalid RSS/Atom fixture")
    items: list[DiscoveredItem] = []
    for entry in parsed.entries[:max_items]:
        link = str(entry.get("link", ""))
        if not link:
            continue
        published_hint: str | None = None
        if entry.get("published_parsed"):
            published_hint = datetime(*entry.published_parsed[:6]).isoformat()
        items.append(
            DiscoveredItem(
                url=link,
                external_id=str(entry.get("id")) if entry.get("id") else None,
                title_hint=str(entry.get("title")) if entry.get("title") else None,
                published_hint=published_hint,
            )
        )
    return items
