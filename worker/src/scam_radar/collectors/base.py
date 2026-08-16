from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from scam_radar.domain import NormalizedItem


@dataclass(frozen=True)
class DiscoveredItem:
    url: str
    external_id: str | None = None
    title_hint: str | None = None
    published_hint: str | None = None


@dataclass(frozen=True)
class FetchResult:
    url: str
    body: bytes
    content_type: str
    status_code: int = 200
    etag: str | None = None
    last_modified: str | None = None


class Transport(Protocol):
    def get(self, url: str, *, timeout_seconds: int, max_bytes: int) -> FetchResult: ...


class Collector(Protocol):
    def discover(
        self, transport: Transport, state: dict[str, str], config: dict[str, object]
    ) -> Iterable[DiscoveredItem]: ...

    def fetch(
        self, transport: Transport, item: DiscoveredItem, config: dict[str, object]
    ) -> FetchResult: ...

    def normalize(
        self, item: DiscoveredItem, fetched: FetchResult, config: dict[str, object]
    ) -> NormalizedItem: ...


class FixtureTransport:
    """In-memory transport used by every offline collector test."""

    def __init__(self, responses: dict[str, FetchResult]) -> None:
        self._responses = responses
        self.requests: list[str] = []

    def get(self, url: str, *, timeout_seconds: int, max_bytes: int) -> FetchResult:
        del timeout_seconds
        self.requests.append(url)
        if url not in self._responses:
            raise ValueError(f"fixture transport has no response for {url}")
        response = self._responses[url]
        if len(response.body) > max_bytes:
            raise ValueError("fixture response exceeds max_bytes")
        return response
