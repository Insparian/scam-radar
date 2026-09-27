"""Bounded HTTP transport; loopback rehearsal is independent of external activation."""

from __future__ import annotations

import ipaddress
import time
from collections.abc import Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

from scam_radar.collectors.base import FetchResult


class TransportError(RuntimeError):
    """Reason codes only: response bodies and credential-bearing URLs are never logged."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self, req: Request, fp: object, code: int, msg: str, headers: object, newurl: str
    ) -> None:
        return None


class BoundedHttpTransport:
    def __init__(
        self,
        *,
        allowed_origins: set[str],
        local_only: bool = True,
        external_enabled: bool = False,
        max_requests: int = 100,
        min_interval: float = 1.5,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if not 1 <= max_requests <= 250 or not 0 <= min_interval <= 60:
            raise ValueError("invalid_transport_limits")
        self.allowed_origins = allowed_origins
        self.local_only = local_only
        self.external_enabled = external_enabled
        self.max_requests = max_requests
        self.min_interval = min_interval
        self.sleep = sleep
        self.requests = 0
        self.last_request: float | None = None
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def validate_url(self, url: str) -> None:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if parts.username or parts.password or parts.fragment or origin not in self.allowed_origins:
            raise TransportError("destination_not_approved")
        if self.local_only:
            try:
                loopback = ipaddress.ip_address(parts.hostname or "").is_loopback
            except ValueError:
                loopback = False
            if not loopback or parts.scheme != "http":
                raise TransportError("local_transport_requires_loopback")
        elif not self.external_enabled or parts.scheme != "https":
            raise TransportError("external_activation_required")

    def request(
        self,
        url: str,
        *,
        method: str = "GET",
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
        timeout_seconds: int = 20,
        max_bytes: int = 2_000_000,
        retries: int = 2,
    ) -> FetchResult:
        self.validate_url(url)
        if (
            not 1 <= timeout_seconds <= 60
            or not 1 <= max_bytes <= 2_000_000
            or not 0 <= retries <= 3
        ):
            raise ValueError("invalid_request_limits")
        for attempt in range(retries + 1):
            if self.requests >= self.max_requests:
                raise TransportError("request_budget_exhausted")
            if self.last_request is not None:
                self.sleep(max(0, self.min_interval - (time.monotonic() - self.last_request)))
            self.requests += 1
            self.last_request = time.monotonic()
            try:
                request = Request(url, data=body, method=method, headers=headers or {})
                with self.opener.open(request, timeout=timeout_seconds) as response:
                    data = response.read(max_bytes + 1)
                    if len(data) > max_bytes:
                        raise TransportError("response_too_large")
                    return FetchResult(
                        url=url,
                        body=data,
                        content_type=response.headers.get("Content-Type", ""),
                        status_code=response.status,
                        etag=response.headers.get("ETag"),
                        last_modified=response.headers.get("Last-Modified"),
                    )
            except HTTPError as error:
                if error.code not in (408, 429) and error.code < 500:
                    raise TransportError(f"http_{error.code}") from None
                retry_after = error.headers.get("Retry-After", "")
                if retry_after:
                    try:
                        delay = float(retry_after)
                    except ValueError:
                        # An HTTP-date we cannot safely satisfy is deferred to the next run.
                        raise TransportError("retry_after_deferred") from None
                    if delay < 0 or delay > 60:
                        raise TransportError("retry_after_deferred") from None
                else:
                    delay = min(2**attempt, 60)
                error.close()
            except (URLError, TimeoutError, OSError):
                delay = min(2**attempt, 60)
            if attempt == retries:
                raise TransportError("transient_retries_exhausted")
            self.sleep(delay)
        raise AssertionError("unreachable")

    def get(self, url: str, *, timeout_seconds: int, max_bytes: int) -> FetchResult:
        return self.request(url, timeout_seconds=timeout_seconds, max_bytes=max_bytes)
