from __future__ import annotations

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PREFIXES = ("utm_",)
TRACKING_KEYS = {"from", "source", "spm", "ref", "referer", "fbclid", "gclid"}


def canonicalize_url(url: str, meaningful_query_parameters: set[str] | None = None) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
        raise ValueError("URL must be absolute http(s)")
    scheme = "https" if parts.scheme.lower() == "https" else "http"
    hostname = parts.hostname.lower().rstrip(".")
    port = parts.port
    netloc = hostname
    if port and not ((scheme == "https" and port == 443) or (scheme == "http" and port == 80)):
        netloc = f"{hostname}:{port}"

    path = parts.path or "/"
    while "//" in path:
        path = path.replace("//", "/")
    if path != "/":
        path = path.rstrip("/")

    meaningful = meaningful_query_parameters or set()
    filtered: list[tuple[str, str]] = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        lowered = key.lower()
        if key in meaningful or (
            lowered not in TRACKING_KEYS
            and not lowered.startswith(TRACKING_PREFIXES)
            and not meaningful
        ):
            filtered.append((key, value))
    filtered.sort()
    return urlunsplit((scheme, netloc, path, urlencode(filtered, doseq=True), ""))
