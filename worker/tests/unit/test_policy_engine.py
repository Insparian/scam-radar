from __future__ import annotations

from typing import Any

import pytest

from scam_radar.domain import EvidenceLevel, GateOutcome, PolicyInput, PolicyOutcome
from scam_radar.policy.engine import evaluate_policy, load_publication_policy


def _safe_input(**updates: Any) -> PolicyInput:
    values: dict[str, Any] = {
        "target_id": "pattern-1",
        "candidate_hash": "a" * 64,
        "review_type": "pattern_update",
        "gate_outcome": GateOutcome.ELIGIBLE,
        "evidence_level": EvidenceLevel.A,
        "existing_public_pattern": True,
        "material_change": False,
        "public_copy_changed": False,
        "claims_fully_supported": True,
        "all_supporting_evidence_verified": True,
        "named_entity_risk": False,
        "legal_status_changed": False,
        "evidence_level_changed": False,
        "source_regression": False,
        "requires_merge_or_split": False,
        "relevance_confidence": 0.95,
        "pattern_match_confidence": 0.95,
    }
    values.update(updates)
    return PolicyInput.model_validate(values)


def test_shadow_policy_records_safe_candidate_without_publication_authority(
    repository_root,
) -> None:  # type: ignore[no-untyped-def]
    policy = load_publication_policy(repository_root / "config/publication-policy-v0.1.yaml")
    decision = evaluate_policy(policy, _safe_input())
    assert decision.gate_version == "evidence-gate-v0.1"
    assert decision.rules_outcome == PolicyOutcome.SAFE_TO_AUTOMATE
    assert decision.outcome == PolicyOutcome.SAFE_TO_AUTOMATE
    assert decision.shadow_mode is True
    assert decision.publication_authorized is False
    assert decision.model_confidence_downgrade is False


def test_same_policy_class_can_grant_authority_after_separate_live_activation(
    repository_root,
    tmp_path,
) -> None:  # type: ignore[no-untyped-def]
    source = repository_root / "config/publication-policy-v0.1.yaml"
    content = (
        source.read_text(encoding="utf-8")
        .replace("shadow_mode: true", "shadow_mode: false")
        .replace("live_auto_publish_enabled: false", "live_auto_publish_enabled: true")
    )
    path = tmp_path / "live-policy.yaml"
    path.write_text(content, encoding="utf-8")
    live_policy = load_publication_policy(path)
    decision = evaluate_policy(live_policy, _safe_input())
    assert decision.outcome == PolicyOutcome.SAFE_TO_AUTOMATE
    assert decision.shadow_mode is False
    assert decision.publication_authorized is True


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("relevance_confidence", 0.4, "relevance_confidence_low"),
        ("pattern_match_confidence", None, "pattern_match_confidence_unknown"),
    ],
)
def test_model_uncertainty_can_only_downgrade_safe_candidate(
    repository_root, field: str, value: object, reason: str
) -> None:  # type: ignore[no-untyped-def]
    policy = load_publication_policy(repository_root / "config/publication-policy-v0.1.yaml")
    decision = evaluate_policy(policy, _safe_input(**{field: value}))
    assert decision.rules_outcome == PolicyOutcome.SAFE_TO_AUTOMATE
    assert decision.outcome == PolicyOutcome.REVIEW_REQUIRED
    assert decision.publication_authorized is False
    assert decision.model_confidence_downgrade is True
    assert reason in decision.reason_codes


def test_high_model_confidence_cannot_upgrade_ineligible_policy_class(
    repository_root,
) -> None:  # type: ignore[no-untyped-def]
    policy = load_publication_policy(repository_root / "config/publication-policy-v0.1.yaml")
    decision = evaluate_policy(
        policy,
        _safe_input(
            review_type="new_pattern",
            existing_public_pattern=False,
            relevance_confidence=1,
            pattern_match_confidence=1,
        ),
    )
    assert decision.rules_outcome == PolicyOutcome.REVIEW_REQUIRED
    assert decision.outcome == PolicyOutcome.REVIEW_REQUIRED
    assert decision.publication_authorized is False
    assert decision.model_confidence_downgrade is False
    assert "first_publication_requires_review" in decision.reason_codes


@pytest.mark.parametrize(
    "updates",
    [
        {"evidence_level": EvidenceLevel.B},
        {"material_change": True},
        {"public_copy_changed": True},
        {"claims_fully_supported": False},
        {"all_supporting_evidence_verified": False},
        {"named_entity_risk": True},
        {"legal_status_changed": True},
        {"evidence_level_changed": True},
        {"source_regression": True},
        {"requires_merge_or_split": True},
    ],
)
def test_high_confidence_never_removes_a_deterministic_review_reason(
    repository_root, updates: dict[str, object]
) -> None:  # type: ignore[no-untyped-def]
    policy = load_publication_policy(repository_root / "config/publication-policy-v0.1.yaml")
    decision = evaluate_policy(
        policy,
        _safe_input(
            **updates,
            relevance_confidence=1,
            pattern_match_confidence=1,
        ),
    )
    assert decision.outcome == PolicyOutcome.REVIEW_REQUIRED
    assert decision.publication_authorized is False
    assert decision.model_confidence_downgrade is False


def test_evidence_gate_block_cannot_be_overridden_by_confidence(repository_root) -> None:  # type: ignore[no-untyped-def]
    policy = load_publication_policy(repository_root / "config/publication-policy-v0.1.yaml")
    decision = evaluate_policy(
        policy,
        _safe_input(
            gate_outcome=GateOutcome.BLOCKED,
            relevance_confidence=1,
            pattern_match_confidence=1,
        ),
    )
    assert decision.outcome == PolicyOutcome.BLOCKED
    assert decision.publication_authorized is False


def test_shadow_and_live_auto_cannot_be_enabled_together(repository_root, tmp_path) -> None:  # type: ignore[no-untyped-def]
    source = repository_root / "config/publication-policy-v0.1.yaml"
    content = source.read_text(encoding="utf-8").replace(
        "live_auto_publish_enabled: false", "live_auto_publish_enabled: true"
    )
    path = tmp_path / "invalid-policy.yaml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match="shadow mode cannot grant"):
        load_publication_policy(path)


def test_unknown_policy_version_fails_closed(repository_root, tmp_path) -> None:  # type: ignore[no-untyped-def]
    source = repository_root / "config/publication-policy-v0.1.yaml"
    content = source.read_text(encoding="utf-8").replace(
        "publication-policy-v0.1", "publication-policy-unknown"
    )
    path = tmp_path / "unknown-policy.yaml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ValueError, match=r"publication-policy-v0\.1"):
        load_publication_policy(path)


def test_policy_and_input_hashes_are_stable(repository_root) -> None:  # type: ignore[no-untyped-def]
    path = repository_root / "config/publication-policy-v0.1.yaml"
    first_policy = load_publication_policy(path)
    second_policy = load_publication_policy(path)
    first = evaluate_policy(first_policy, _safe_input())
    second = evaluate_policy(second_policy, _safe_input())
    assert first.policy_hash == second.policy_hash
    assert first.input_hash == second.input_hash


def test_policy_decision_model_rejects_an_authority_upgrade(repository_root) -> None:  # type: ignore[no-untyped-def]
    policy = load_publication_policy(repository_root / "config/publication-policy-v0.1.yaml")
    decision = evaluate_policy(policy, _safe_input(material_change=True))
    with pytest.raises(ValueError, match="cannot differ without"):
        type(decision).model_validate(
            {
                **decision.model_dump(mode="json"),
                "outcome": PolicyOutcome.SAFE_TO_AUTOMATE,
                "publication_authorized": True,
            }
        )
