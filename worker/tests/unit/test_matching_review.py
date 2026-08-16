from __future__ import annotations

from datetime import date

from scam_radar.domain import EvidenceLevel
from scam_radar.matching.service import PatternDocument, retrieve_candidates
from scam_radar.review.queue import make_review_candidate, review_sort_key


def test_alias_retrieval_maps_user_wording_to_pattern() -> None:
    documents = [
        PatternDocument(
            revision_id="collectibles-v1",
            canonical_name="老物件高价回收骗局",
            aliases=("粮票回收", "古董回购"),
            features=("鉴定费", "保证金"),
        ),
        PatternDocument(
            revision_id="customer-service-v1",
            canonical_name="假客服骗局",
            aliases=("百万保障",),
            features=("屏幕共享",),
        ),
    ]
    matches = retrieve_candidates("高价收粮票", ["粮票回收"], ["鉴定费"], documents)
    assert matches[0].revision_id == "collectibles-v1"
    assert matches[0].score == 100


def test_review_dedupe_key_is_stable() -> None:
    values = dict(
        target_id="pattern-1",
        review_type="new_pattern",
        evidence_level=EvidenceLevel.A,
        heat_score=88,
        material_date=date(2026, 8, 16),
        reason_codes=[],
        payload={"name": "测试"},
    )
    assert make_review_candidate(**values).dedupe_key == make_review_candidate(**values).dedupe_key


def test_gate_regression_sorts_before_hot_candidate() -> None:
    regression = make_review_candidate(
        target_id="published",
        review_type="gate_regression",
        evidence_level=EvidenceLevel.D,
        heat_score=0,
        material_date=date(2026, 8, 1),
        reason_codes=["source_unavailable"],
        payload={"name": "published"},
    )
    hot = make_review_candidate(
        target_id="hot",
        review_type="new_pattern",
        evidence_level=EvidenceLevel.A,
        heat_score=95,
        material_date=date(2026, 8, 16),
        reason_codes=[],
        payload={"name": "hot"},
    )
    assert sorted([hot, regression], key=review_sort_key)[0] == regression
