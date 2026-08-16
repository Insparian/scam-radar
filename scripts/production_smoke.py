from __future__ import annotations

import argparse
import json
import os
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
    try:
        release = get_json(urljoin(args.base_url.rstrip("/") + "/", "release.json"))
    except (urllib.error.URLError, TimeoutError) as error:
        raise RuntimeError(
            "production release metadata could not be reached"
        ) from error
    if release.get("release_id") != args.release_id:
        raise RuntimeError("production release ID does not match the approved release")
    print(f"production smoke ok: release_id={args.release_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
