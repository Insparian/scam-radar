from __future__ import annotations

from dataclasses import dataclass, field

from scam_radar.domain import NormalizedItem, ReviewCandidate


@dataclass
class MemoryStore:
    """Deterministic fixture store; never used as production durability."""

    item_versions: dict[tuple[str, str], NormalizedItem] = field(default_factory=dict)
    content_hashes: dict[str, tuple[str, str]] = field(default_factory=dict)
    review_items: dict[str, ReviewCandidate] = field(default_factory=dict)

    def upsert_item(self, item: NormalizedItem) -> bool:
        key = (item.source_key, item.identity_key)
        version_key = (f"{key[0]}:{key[1]}", item.content_hash)
        if version_key in self.item_versions:
            return False
        self.item_versions[version_key] = item
        self.content_hashes.setdefault(item.content_hash, version_key)
        return True

    def is_origin_duplicate(self, content_hash: str) -> bool:
        return content_hash in self.content_hashes

    def upsert_review(self, candidate: ReviewCandidate) -> bool:
        if candidate.dedupe_key in self.review_items:
            return False
        self.review_items[candidate.dedupe_key] = candidate
        return True
