from __future__ import annotations

from scam_radar.collectors.base import FetchResult, FixtureTransport
from scam_radar.collectors.feed import discover_feed
from scam_radar.collectors.fixture import FixtureListCollector
from scam_radar.collectors.sitemap import discover_sitemap


def test_fixture_collector_discovers_and_normalizes_without_network(repository_root) -> None:  # type: ignore[no-untyped-def]
    entry_url = "https://fixture.example.invalid/list"
    detail_url = "https://fixture.example.invalid/reports/million-protection"
    list_body = (repository_root / "evals/fixtures/sources/generic-list.html").read_bytes()
    detail_body = """
    <html><body><nav>menu</nav><main><h1>警惕百万保障骗局</h1>
    <article>警方提醒：不要共享屏幕，不要转账到安全账户。</article></main><footer>footer</footer></body></html>
    """.encode()
    transport = FixtureTransport(
        {
            entry_url: FetchResult(entry_url, list_body, "text/html"),
            detail_url: FetchResult(detail_url, detail_body, "text/html"),
        }
    )
    collector = FixtureListCollector()
    config = {
        "entry_url": entry_url,
        "source_key": "fixture-authority",
        "timeout_seconds": 20,
        "max_response_bytes": 100_000,
        "max_clean_text_chars": 50_000,
    }
    items = list(collector.discover(transport, {}, config))
    assert [item.external_id for item in items] == ["fixture-million-protection"]
    normalized = collector.normalize(items[0], collector.fetch(transport, items[0], config), config)
    assert normalized.title == "警惕百万保障骗局"
    assert "共享屏幕" in normalized.clean_text
    assert "footer" not in normalized.clean_text


def test_feed_and_sitemap_contracts() -> None:
    feed = b"""<?xml version='1.0'?><rss version='2.0'><channel><title>x</title><link>https://example.invalid</link><description>x</description><item><guid>a</guid><title>Alert</title><link>https://example.invalid/a</link></item></channel></rss>"""
    sitemap = b"""<?xml version='1.0'?><urlset xmlns='http://www.sitemaps.org/schemas/sitemap/0.9'><url><loc>https://example.invalid/a</loc><lastmod>2026-08-15</lastmod></url></urlset>"""
    assert discover_feed(feed)[0].external_id == "a"
    assert discover_sitemap(sitemap)[0].url == "https://example.invalid/a"


def test_fixture_transport_enforces_response_size() -> None:
    url = "https://fixture.example.invalid/oversized"
    transport = FixtureTransport({url: FetchResult(url, b"12345", "text/plain")})
    try:
        transport.get(url, timeout_seconds=1, max_bytes=4)
    except ValueError as error:
        assert "max_bytes" in str(error)
    else:
        raise AssertionError("oversized fixture was accepted")
