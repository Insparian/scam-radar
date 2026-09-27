"""Resolve a reviewed candidate without choosing a production winner."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, cast
from urllib.parse import urlsplit

import yaml

from scam_radar.collectors.http import BoundedHttpTransport
from scam_radar.llm.http_provider import HttpModelProvider


def evaluation_provider(
    root: Path,
    candidate: str,
    *,
    local_endpoint: str,
    max_calls: int = 10,
    input_char_limit: int = 10000,
) -> HttpModelProvider:
    config = yaml.safe_load((root / "config/models.yaml").read_text())
    selected = config["evaluation_candidates"][candidate]
    protocol = selected["protocol"]
    if protocol not in ("openai", "gemini"):
        raise ValueError("unsupported_provider_protocol")
    parts = urlsplit(local_endpoint)
    transport = BoundedHttpTransport(
        allowed_origins={f"{parts.scheme}://{parts.netloc}"},
        max_requests=max(1, max_calls),
        min_interval=0,
    )
    return HttpModelProvider(
        root=root,
        transport=transport,
        endpoint=local_endpoint,
        model=selected["model"],
        protocol=cast(Literal["openai", "gemini"], protocol),
        max_calls=max_calls,
        input_char_limit=input_char_limit,
    )
