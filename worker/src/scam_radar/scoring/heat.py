from __future__ import annotations

import hashlib
import json
from datetime import date

from scam_radar.domain import EvidenceLevel, HeatFeatures, HeatSnapshot

TARGET_POINTS = {
    "older_adults": 30,
    "retirees_or_pensions": 27,
    "broad_with_older_risk": 20,
    "general_adults": 10,
    "incidental_older_relevance": 5,
    "none": 0,
    "unknown": 0,
}
HARM_POINTS = {
    "irreversible_or_severe": 20,
    "major_loss_or_takeover": 15,
    "moderate_loss": 10,
    "data_or_grooming": 5,
    "unknown": 0,
}
SPREAD_POINTS = {
    "national_or_three_provinces": 15,
    "two_provinces": 12,
    "multiple_cities": 10,
    "multiple_cases_one_region": 7,
    "single_case": 3,
    "unknown": 0,
}
NOVELTY_POINTS = {
    "new_mechanism": 15,
    "new_technology": 13,
    "new_script_or_step": 10,
    "new_packaging": 6,
    "minor_variation": 3,
    "longstanding_unchanged": 2,
    "unknown": 0,
}


def freshness_points(last_material_change_at: date | None, as_of: date) -> int:
    if last_material_change_at is None:
        return 0
    age = (as_of - last_material_change_at).days
    if age < 0:
        raise ValueError("material change cannot be in the future")
    if age <= 3:
        return 20
    if age <= 7:
        return 16
    if age <= 14:
        return 12
    if age <= 30:
        return 6
    return 0


def score_band(score: int) -> str:
    if score >= 80:
        return "immediate"
    if score >= 65:
        return "recent"
    if score >= 50:
        return "observe"
    return "database"


def calculate_heat(
    features: HeatFeatures, *, as_of: date, evidence_level: EvidenceLevel
) -> HeatSnapshot:
    components = {
        "target_relevance": TARGET_POINTS[features.target_relevance],
        "freshness": freshness_points(features.last_material_change_at, as_of),
        "harm": HARM_POINTS[features.harm],
        "spread": SPREAD_POINTS[features.spread],
        "novelty": NOVELTY_POINTS[features.novelty],
    }
    score = sum(components.values())
    active = (
        evidence_level in {EvidenceLevel.A, EvidenceLevel.B}
        and features.last_material_change_at is not None
        and 0 <= (as_of - features.last_material_change_at).days <= 30
    )
    feature_values: dict[str, str | None] = {
        "target_relevance": features.target_relevance,
        "harm": features.harm,
        "spread": features.spread,
        "novelty": features.novelty,
        "last_material_change_at": (
            features.last_material_change_at.isoformat()
            if features.last_material_change_at is not None
            else None
        ),
    }
    hash_input = json.dumps(
        {
            "as_of": as_of.isoformat(),
            "evidence_level": evidence_level,
            "features": feature_values,
            "evidence_ids": sorted(features.evidence_ids),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return HeatSnapshot(
        score=score,
        band=score_band(score),  # type: ignore[arg-type]
        active_attention=active,
        as_of=as_of,
        components=components,
        feature_values=feature_values,
        evidence_ids=sorted(features.evidence_ids),
        inputs_hash=hashlib.sha256(hash_input.encode()).hexdigest(),
    )
