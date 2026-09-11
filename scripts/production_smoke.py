from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urljoin, urlparse


def get_json(url: str) -> dict[str, object]:
    request = urllib.request.Request(url, headers={"User-Agent": "ScamRadarSmoke/0.1"})
    with urllib.request.urlopen(request, timeout=15) as response:
        if response.status != 200:
            raise RuntimeError(f"smoke check returned HTTP {response.status}")
        payload = json.loads(response.read(100_000))
    if not isinstance(payload, dict):
        raise TypeError("release metadata was not a JSON object")
    return payload


def get_json_with_retry(
    url: str, *, attempts: int = 6, initial_delay_seconds: float = 2.0
) -> dict[str, object]:
    """Allow the Pages alias a short propagation window after deployment."""
    if attempts < 1:
        raise ValueError("smoke check attempts must be positive")
    delay_seconds = initial_delay_seconds
    for attempt in range(1, attempts + 1):
        try:
            return get_json(url)
        except (urllib.error.URLError, TimeoutError) as error:
            if attempt == attempts:
                raise RuntimeError(
                    "production release metadata could not be reached"
                ) from error
            print(
                f"production smoke retry {attempt}/{attempts - 1} after transient error",
                file=sys.stderr,
            )
            time.sleep(delay_seconds)
            delay_seconds = min(delay_seconds * 2, 30)
    raise AssertionError("unreachable")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only production release check; activation approval is required."
    )
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--release-id", required=True)
    args = parser.parse_args()
    if os.getenv("SCAM_RADAR_ALLOW_PRODUCTION_SMOKE") != "true":
        raise RuntimeError(
            "production smoke is disabled; set SCAM_RADAR_ALLOW_PRODUCTION_SMOKE=true only "
            "after Rui approves activation"
        )
    parsed = urlparse(args.base_url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise RuntimeError("production smoke requires an https base URL")
    release = get_json_with_retry(
        urljoin(args.base_url.rstrip("/") + "/", "release.json")
    )
    if release.get("release_id") != args.release_id:
        raise RuntimeError("production release ID does not match the approved release")
    print(f"production smoke ok: release_id={args.release_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
