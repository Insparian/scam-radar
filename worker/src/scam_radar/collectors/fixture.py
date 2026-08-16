from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from pydantic import HttpUrl

from scam_radar.collectors.base import DiscoveredItem, FetchResult, Transport
from scam_radar.dedup.service import content_hash, identity_key
from scam_radar.domain import NormalizedItem
from scam_radar.normalize.text import normalize_text
from scam_radar.normalize.url import canonicalize_url


def _integer_config(config: dict[str, object], key: str, default: int) -> int:
    value = config.get(key, default)
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise TypeError(f"{key} must be an integer")
    return int(value)


class FixtureListCollector:
    def discover(
        self, transport: Transport, state: dict[str, str], config: dict[str, object]
    ) -> Iterable[DiscoveredItem]:
        del state
        entry_url = str(config["entry_url"])
        allowed_host = urlsplit(entry_url).hostname
        response = transport.get(
            entry_url,
            timeout_seconds=_integer_config(config, "timeout_seconds", 20),
            max_bytes=_integer_config(config, "max_response_bytes", 1_000_000),
        )
        if response.status_code != 200:
            raise ValueError(f"list fetch failed with status {response.status_code}")
        soup = BeautifulSoup(response.body, "lxml")
        items: list[DiscoveredItem] = []
        for article in soup.select("article[data-id]"):
            link = article.select_one("a[href]")
            if link is None:
                continue
            url = urljoin(entry_url, str(link.get("href")))
            if urlsplit(url).hostname != allowed_host and not str(urlsplit(url).hostname).endswith(
                ".example.invalid"
            ):
                raise ValueError("discovered URL escaped the allowlisted fixture domain")
            time = article.select_one("time[datetime]")
            items.append(
                DiscoveredItem(
                    url=url,
                    external_id=str(article.get("data-id")),
                    title_hint=link.get_text(" ", strip=True),
                    published_hint=str(time.get("datetime")) if time else None,
                )
            )
        return items

    def fetch(
        self, transport: Transport, item: DiscoveredItem, config: dict[str, object]
    ) -> FetchResult:
        return transport.get(
            item.url,
            timeout_seconds=_integer_config(config, "timeout_seconds", 20),
            max_bytes=_integer_config(config, "max_response_bytes", 1_000_000),
        )

    def normalize(
        self, item: DiscoveredItem, fetched: FetchResult, config: dict[str, object]
    ) -> NormalizedItem:
        if fetched.status_code != 200:
            raise ValueError(f"detail fetch failed with status {fetched.status_code}")
        soup = BeautifulSoup(fetched.body, "lxml")
        for node in soup.select("nav, footer, script, style, noscript"):
            node.decompose()
        title_node = soup.select_one("h1")
        body_node = soup.select_one("article") or soup.select_one("main")
        title = title_node.get_text(" ", strip=True) if title_node else item.title_hint or ""
        body = body_node.get_text("\n", strip=True) if body_node else ""
        cleaned = normalize_text(
            body,
            max_chars=_integer_config(config, "max_clean_text_chars", 50_000),
        )
        if not title or not cleaned.text:
            raise ValueError("normalized fixture item is empty")
        canonical_url = canonicalize_url(fetched.url)
        published = (
            datetime.fromisoformat(item.published_hint).astimezone()
            if item.published_hint and "T" in item.published_hint
            else None
        )
        return NormalizedItem(
            source_key=str(config["source_key"]),
            external_id=item.external_id,
            canonical_url=HttpUrl(canonical_url),
            title=title,
            clean_text=cleaned.text,
            published_at=published,
            language="zh-CN",
            text_truncated=cleaned.truncated,
            identity_key=identity_key(canonical_url, item.external_id),
            content_hash=content_hash(title, cleaned.text),
        )
