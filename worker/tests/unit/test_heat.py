from __future__ import annotations

from datetime import date, timedelta

import pytest

from scam_radar.domain import EvidenceLevel, HeatFeatures
from scam_radar.scoring.heat import calculate_heat, freshness_points


@pytest.mark.parametrize(
    ("days", "expected"),
    [(0, 20), (3, 20), (4, 16), (7, 16), (8, 12), (14, 12), (15, 6), (30, 6), (31, 0)],
)
def test_freshness_boundaries(days: int, expected: int) -> None:
    as_of = date(2026, 8, 16)
    assert freshness_points(as_of - timedelta(days=days), as_of) == expected


def test_heat_is_deterministic_and_sums_components() -> None:
    features = HeatFeatures(
        target_relevance="older_adults",
        harm="major_loss_or_takeover",
        spread="two_provinces",
        novelty="new_script_or_step",
        last_material_change_at=date(2026, 8, 15),
        evidence_ids=["b", "a"],
    )
    first = calculate_heat(features, as_of=date(2026, 8, 16), evidence_level=EvidenceLevel.A)
    second = calculate_heat(features, as_of=date(2026, 8, 16), evidence_level=EvidenceLevel.A)
    assert first.score == 87
    assert first.band == "immediate"
    assert first.active_attention
    assert first.inputs_hash == second.inputs_hash
    assert first.evidence_ids == ["a", "b"]


def test_c_level_never_enters_active_attention() -> None:
    features = HeatFeatures(
        target_relevance="older_adults",
        harm="irreversible_or_severe",
        spread="national_or_three_provinces",
        novelty="new_mechanism",
        last_material_change_at=date(2026, 8, 16),
        evidence_ids=["weak"],
    )
    snapshot = calculate_heat(features, as_of=date(2026, 8, 16), evidence_level=EvidenceLevel.C)
    assert snapshot.score == 100
    assert not snapshot.active_attention


def test_future_material_change_is_rejected() -> None:
    with pytest.raises(ValueError, match="future"):
        freshness_points(date(2026, 8, 17), date(2026, 8, 16))
