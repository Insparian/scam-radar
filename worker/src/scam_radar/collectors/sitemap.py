from __future__ import annotations

from xml.etree import ElementTree

from scam_radar.collectors.base import DiscoveredItem


def discover_sitemap(body: bytes, *, max_items: int = 50) -> list[DiscoveredItem]:
    try:
        root = ElementTree.fromstring(body)
    except ElementTree.ParseError as error:
        raise ValueError("invalid sitemap fixture") from error
    items: list[DiscoveredItem] = []
    for url_node in root.findall("{*}url")[:max_items]:
        location = url_node.findtext("{*}loc")
        if not location:
            continue
        items.append(
            DiscoveredItem(
                url=location.strip(),
                published_hint=(url_node.findtext("{*}lastmod") or "").strip() or None,
            )
        )
    return items
