from __future__ import annotations

import hashlib
import re


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def identity_key(canonical_url: str, external_id: str | None = None) -> str:
    return (
        external_id.strip() if external_id and external_id.strip() else sha256_text(canonical_url)
    )


def content_hash(title: str, clean_text: str) -> str:
    return sha256_text(f"{title.strip()}\n{clean_text.strip()}")


def origin_group_key(title: str, clean_text: str) -> str:
    normalized = re.sub(r"\s+", "", f"{title}\n{clean_text}").lower()
    return sha256_text(normalized[:20_000])
