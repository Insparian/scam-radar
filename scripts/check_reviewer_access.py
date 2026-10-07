from __future__ import annotations

import argparse
import os
import re
import urllib.error
import urllib.request
from urllib.parse import urlparse


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(  # type: ignore[override]
        self,
        request: urllib.request.Request,
        file_pointer: object,
        code: int,
        message: str,
        headers: object,
        new_url: str,
    ) -> None:
        return None


def validate_access_redirect(
    status: int, location: str | None, expected_host: str
) -> None:
    if not re.fullmatch(
        r"[a-z0-9]+(?:-[a-z0-9]+)*\.cloudflareaccess\.com", expected_host
    ):
        raise RuntimeError("dedicated Access login hostname is missing or invalid")
    if status not in {301, 302, 303, 307, 308} or not location:
        raise RuntimeError("reviewer URL is not blocked by an Access redirect")
    target = urlparse(location)
    if (
        target.scheme != "https"
        or target.hostname != expected_host
        or target.username
        or target.password
        or target.port
        or not target.path.startswith("/cdn-cgi/access/")
    ):
        raise RuntimeError(
            "reviewer URL did not redirect to dedicated Cloudflare Access"
        )


def assert_access_protected(url: str, expected_host: str) -> None:
    parsed = urlparse(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or not parsed.hostname.endswith(".pages.dev")
    ):
        raise RuntimeError("reviewer Access check requires an https pages.dev URL")

    request = urllib.request.Request(
        url,
        method="HEAD",
        headers={"User-Agent": "ScamRadarReviewerAccessCheck/0.1"},
    )
    opener = urllib.request.build_opener(NoRedirect)
    try:
        with opener.open(request, timeout=15) as response:
            status = response.status
            location = response.headers.get("Location")
    except urllib.error.HTTPError as error:
        status = error.code
        location = error.headers.get("Location")
    validate_access_redirect(status, location, expected_host)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fail unless the reviewer Pages URL is protected by Cloudflare Access."
    )
    parser.add_argument("--url", required=True)
    parser.add_argument("--access-host", required=True)
    args = parser.parse_args()
    if os.getenv("SCAM_RADAR_ALLOW_REVIEWER_SMOKE") != "true":
        raise RuntimeError(
            "reviewer Access check is disabled; use only after activation approval"
        )
    assert_access_protected(args.url, args.access_host)
    print("reviewer access boundary ok: unauthenticated request blocked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
