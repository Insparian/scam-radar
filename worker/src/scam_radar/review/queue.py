from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any

from scam_radar.domain import EvidenceLevel, ReviewCandidate


def stable_hash(value: dict[str, Any]) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def make_review_candidate(
    *,
    target_id: str,
    review_type: str,
    evidence_level: EvidenceLevel,
    heat_score: int,
    material_date: date | None,
    reason_codes: list[str],
    payload: dict[str, Any],
) -> ReviewCandidate:
    candidate_hash = stable_hash(payload)
    dedupe_key = hashlib.sha256(f"{review_type}:{target_id}:{candidate_hash}".encode()).hexdigest()
    return ReviewCandidate(
        target_id=target_id,
        review_type=review_type,  # type: ignore[arg-type]
        evidence_level=evidence_level,
        heat_score=heat_score,
        material_date=material_date,
        reason_codes=reason_codes,
        candidate_payload=payload,
        candidate_hash=candidate_hash,
        dedupe_key=dedupe_key,
    )


def review_sort_key(candidate: ReviewCandidate) -> tuple[int, int, int, int]:
    if candidate.review_type == "gate_regression":
        group = 0
    elif candidate.heat_score >= 80:
        group = 1
    elif candidate.evidence_level == EvidenceLevel.A and candidate.review_type == "new_pattern":
        group = 2
    elif candidate.review_type == "merge":
        group = 3
    elif candidate.heat_score >= 65:
        group = 4
    else:
        group = 5
    evidence_order = {
        EvidenceLevel.A: 0,
        EvidenceLevel.B: 1,
        EvidenceLevel.C: 2,
        EvidenceLevel.D: 3,
    }
    material_ordinal = candidate.material_date.toordinal() if candidate.material_date else 0
    return (
        group,
        -material_ordinal,
        evidence_order[candidate.evidence_level],
        -candidate.heat_score,
    )
