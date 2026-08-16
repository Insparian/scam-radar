from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class EvidenceHashInput:
    evidence_id: str
    source_version_content_hash: str
    origin_group_key: str
    evidence_family_id: str
    evidence_type: str

    def serialize(self) -> str:
        values = (
            self.evidence_id,
            self.source_version_content_hash,
            self.origin_group_key,
            self.evidence_family_id,
            self.evidence_type,
        )
        if any(not value or ":" in value or "|" in value for value in values):
            raise ValueError("evidence hash fields must be non-empty and cannot contain ':' or '|'")
        return ":".join(values)


def evidence_set_hash(items: Iterable[EvidenceHashInput]) -> str:
    """Match the immutable evidence serialization enforced by PostgreSQL."""

    ordered = sorted(items, key=lambda item: item.evidence_id)
    evidence_ids = [item.evidence_id for item in ordered]
    if len(evidence_ids) != len(set(evidence_ids)):
        raise ValueError("evidence IDs must be unique")
    payload = "|".join(item.serialize() for item in ordered)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
