from __future__ import annotations

from typing import Any

import pytest

from scam_radar.collectors.base import DiscoveredItem, FetchResult, FixtureTransport
from scam_radar.collectors.source import SourceCollector


def setup_source(robots: str = "User-agent: *\nAllow: /") -> tuple[SourceCollector, dict[str, Any]]:
    origin = "https://source.example.invalid"
    source = {
        "key": "local-test",
        "enabled": True,
        "policy": {
            "collection_allowed": True,
            "reviewed_at": "2026-09-18",
            "robots_url": origin + "/robots.txt",
        },
        "collector": {"type": "rss", "entry_url": origin + "/feed"},
        "limits": {"max_items_per_run": 2, "timeout_seconds": 1},
        "parser": {"config": {}},
    }
    transport = FixtureTransport(
        {
            origin + "/robots.txt": FetchResult(
                origin + "/robots.txt", robots.encode(), "text/plain"
            ),
            origin + "/feed": FetchResult(
                origin + "/feed",
                b'<rss version="2.0"><channel><title>Local</title><item><title>Case</title><link>https://source.example.invalid/case</link></item></channel></rss>',
                "application/xml",
            ),
            origin + "/case": FetchResult(
                origin + "/case",
                "<html><h1>合成提醒</h1><nav>导航</nav><article>不要提供验证码。13812345678</article></html>".encode(),
                "text/html",
            ),
        }
    )
    return SourceCollector(source, transport, user_agent="ScamRadarTest"), source


def test_registry_source_discovery_normalization_and_stable_identity() -> None:
    collector, _ = setup_source()
    items = collector.discover()
    first = collector.collect(items[0])
    second = collector.collect(items[0])
    assert first.content_hash == second.content_hash
    assert first.identity_key == second.identity_key
    assert "13812345678" not in first.clean_text
    assert "导航" not in first.clean_text
    assert first.published_at is None


def test_robots_refusal_precedes_article_fetch() -> None:
    collector, _ = setup_source("User-agent: *\nDisallow: /")
    with pytest.raises(ValueError, match="robots_denied"):
        collector.discover()


def test_disabled_registry_never_collects() -> None:
    collector, source = setup_source()
    source["enabled"] = False
    with pytest.raises(ValueError, match="source_activation_required"):
        SourceCollector(source, collector.transport, user_agent="test")


def test_offsite_discovery_fails_before_article_request() -> None:
    collector, _ = setup_source()
    origin = "https://source.example.invalid"
    collector.transport._responses[origin + "/feed"] = FetchResult(
        origin + "/feed",
        b'<rss version="2.0"><channel><item><link>https://other.example.invalid/case</link></item></channel></rss>',
        "application/xml",
    )
    with pytest.raises(ValueError, match="source_url_outside_registry"):
        collector.discover()
    assert collector.transport.requests == [origin + "/robots.txt", origin + "/feed"]


def test_changed_article_markup_fails_without_producing_evidence() -> None:
    collector, _ = setup_source()
    origin = "https://source.example.invalid"
    collector.discover()
    collector.transport._responses[origin + "/case"] = FetchResult(
        origin + "/case", b"<html><h1>changed</h1><main>no article</main></html>", "text/html"
    )
    with pytest.raises(ValueError, match="source_markup_changed"):
        collector.collect(DiscoveredItem(url=origin + "/case"))
