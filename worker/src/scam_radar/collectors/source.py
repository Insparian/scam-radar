"""Registry-driven source parser; production orchestration must supply approved config."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup
from pydantic import HttpUrl

from scam_radar.collectors.base import DiscoveredItem, FetchResult, Transport
from scam_radar.collectors.feed import discover_feed
from scam_radar.collectors.sitemap import discover_sitemap
from scam_radar.dedup.service import content_hash, identity_key
from scam_radar.domain import NormalizedItem
from scam_radar.normalize.text import normalize_text
from scam_radar.normalize.url import canonicalize_url


class SourceCollector:
    def __init__(self, source: dict[str, Any], transport: Transport, *, user_agent: str) -> None:
        if (
            not source["enabled"]
            or not source["policy"]["collection_allowed"]
            or not source["policy"]["reviewed_at"]
        ):
            raise ValueError("source_activation_required")
        self.source, self.transport, self.user_agent = source, transport, user_agent
        self.entry = source["collector"]["entry_url"]
        self.origin = urlsplit(self.entry).netloc
        self.robots: RobotFileParser | None = None

    def _validate(self, url: str) -> None:
        parsed = urlsplit(url)
        if (
            parsed.scheme != "https"
            or parsed.netloc != self.origin
            or parsed.username
            or parsed.password
        ):
            raise ValueError("source_url_outside_registry")

    def _fetch(self, url: str) -> FetchResult:
        self._validate(url)
        if self.robots is None or not self.robots.can_fetch(self.user_agent, url):
            raise ValueError("robots_denied")
        return self.transport.get(
            url, timeout_seconds=self.source["limits"]["timeout_seconds"], max_bytes=1_000_000
        )

    def discover(self) -> list[DiscoveredItem]:
        robots_url = self.source["policy"]["robots_url"]
        if not robots_url:
            raise ValueError("robots_review_required")
        self._validate(robots_url)
        response = self.transport.get(robots_url, timeout_seconds=20, max_bytes=100_000)
        if response.status_code != 200:
            raise ValueError("robots_unavailable")
        self.robots = RobotFileParser()
        self.robots.parse(response.body.decode("utf-8", errors="strict").splitlines())
        response = self._fetch(self.entry)
        if response.status_code != 200:
            raise ValueError("source_discovery_failed")
        limit = self.source["limits"]["max_items_per_run"]
        kind = self.source["collector"]["type"]
        if kind == "rss":
            items = discover_feed(response.body, max_items=limit)
        elif kind == "sitemap":
            # Sitemap lastmod is not an article publication date.
            items = [
                DiscoveredItem(url=item.url)
                for item in discover_sitemap(response.body, max_items=limit)
            ]
        elif kind in ("list_page", "html"):
            selector = self.source["parser"]["config"].get("link_selector")
            if not selector:
                raise ValueError("reviewed_link_selector_required")
            soup = BeautifulSoup(response.body, "lxml")
            items = [
                DiscoveredItem(
                    url=urljoin(self.entry, str(node["href"])),
                    title_hint=node.get_text(" ", strip=True),
                )
                for node in soup.select(selector)[:limit]
                if node.has_attr("href")
            ]
        else:
            raise ValueError("unsupported_source_method")
        if not items:
            raise ValueError("empty_source_discovery")
        for item in items:
            self._validate(item.url)
        return list({item.url: item for item in items}.values())

    def collect(self, item: DiscoveredItem) -> NormalizedItem:
        response = self._fetch(item.url)
        if response.status_code != 200 or "html" not in response.content_type.lower():
            raise ValueError("unsupported_source_response")
        soup = BeautifulSoup(response.body, "lxml")
        for node in soup.select("nav, footer, script, style, noscript"):
            node.decompose()
        parser = self.source["parser"]["config"]
        title_node = soup.select_one(parser.get("title_selector", "h1"))
        body_node = soup.select_one(parser.get("body_selector", "article"))
        if title_node is None or body_node is None:
            raise ValueError("source_markup_changed")
        title = normalize_text(title_node.get_text(" ", strip=True), max_chars=500).text
        cleaned = normalize_text(body_node.get_text("\n", strip=True), max_chars=50000)
        if not title or not cleaned.text:
            raise ValueError("empty_source_text")
        published = None
        if item.published_hint:
            parsed = datetime.fromisoformat(item.published_hint.replace("Z", "+00:00"))
            if parsed.tzinfo is not None:
                published = parsed
        url = canonicalize_url(item.url)
        return NormalizedItem(
            source_key=self.source["key"],
            external_id=item.external_id,
            canonical_url=HttpUrl(url),
            title=title,
            clean_text=cleaned.text,
            published_at=published,
            language="zh-CN",
            text_truncated=cleaned.truncated,
            identity_key=identity_key(url, item.external_id),
            content_hash=content_hash(title, cleaned.text),
        )
